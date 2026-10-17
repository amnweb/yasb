import logging
from contextlib import suppress
from ctypes import byref, c_void_p

from comtypes import COMError  # pyright: ignore[reportMissingTypeStubs]
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from core.events.service import EventService
from core.utils.win32.bindings.ntdll import (
    RtlSubscribeWnfStateChangeNotification,
    RtlUnsubscribeWnfStateChangeNotification,
    WnfCallbackType,
)
from core.utils.win32.bindings.ole32 import CoInitialize, CoUninitialize, create_com_object
from core.utils.win32.bindings.shell32 import CLSID_QuietHoursSettings, IQuietHoursSettings, get_user_selected_profile
from core.utils.win32.constants import CLSCTX_LOCAL_SERVER
from core.utils.win32.typecheck import CFunctionType
from core.utils.win32.undocumented import WNF_SHEL_QUIETHOURS_ACTIVE_PROFILE_CHANGED


class DndService:
    """A lightweight service to query and control Windows Focus Assist/Do Not Disturb."""

    _wnf_subscription_handle = c_void_p()
    _wnf_callback_reference: CFunctionType | None = None
    _wnf_is_active = False

    PROFILES = {
        "Microsoft.QuietHoursProfile.Unrestricted": "disabled",
        "Microsoft.QuietHoursProfile.PriorityOnly": "priority",
        "Microsoft.QuietHoursProfile.AlarmsOnly": "alarms",
    }
    MODES = {v: k for k, v in PROFILES.items()}

    # The settings object lives only inside these two helpers, so it is released before CoUninitialize
    @staticmethod
    def _read_profile() -> str | None:
        settings = create_com_object(CLSID_QuietHoursSettings, IQuietHoursSettings, CLSCTX_LOCAL_SERVER)
        return get_user_selected_profile(settings) if settings is not None else None

    @staticmethod
    def _write_profile(profile: str) -> None:
        settings = create_com_object(CLSID_QuietHoursSettings, IQuietHoursSettings, CLSCTX_LOCAL_SERVER)
        if settings is not None:
            with suppress(COMError):
                settings.put_UserSelectedProfile(profile)

    @classmethod
    def get_status(cls) -> str:
        """Returns: 'disabled', 'priority', or 'alarms'"""
        CoInitialize(None)
        try:
            profile = cls._read_profile()
        except Exception:
            profile = None
        finally:
            CoUninitialize()
        return cls.PROFILES.get(profile, "unknown") if profile else "unknown"

    @classmethod
    def set_status(cls, mode: str) -> None:
        """Write UserSelectedProfile. mode: 'disabled', 'priority', or 'alarms'."""
        if mode not in cls.MODES:
            raise ValueError(f"Invalid DND mode '{mode}'. Use: {list(cls.MODES.keys())}")
        CoInitialize(None)
        try:
            cls._write_profile(cls.MODES[mode])
        finally:
            CoUninitialize()

    @staticmethod
    def _wnf_callback(
        state_name: int,
        change_stamp: int,
        type_id: int | None,
        context: int | None,
        buffer: int | None,
        buffer_size: int,
    ) -> int:
        try:
            status = DndService.get_status()
            EventService().emit_event("dnd_status_changed", status)
        except Exception:
            logging.error("DND WNF Callback failed", exc_info=True)
        return 0

    @classmethod
    def initialize_wnf_listener(cls):
        """Initializes the DndService listener."""
        if cls._wnf_is_active:
            return  # Already listening

        try:
            # Store the callback reference so it isn't garbage collected
            cls._wnf_callback_reference = WnfCallbackType(cls._wnf_callback)

            status = RtlSubscribeWnfStateChangeNotification(
                byref(cls._wnf_subscription_handle),
                WNF_SHEL_QUIETHOURS_ACTIVE_PROFILE_CHANGED,
                0,
                cls._wnf_callback_reference,
                None,
                None,
                0,
                0,
            )
            if status == 0:
                cls._wnf_is_active = True
                logging.info("DndService initialized...")
                # Ensure cleanup is run when YASB exits
                app = QApplication.instance()
                if app:
                    app.aboutToQuit.connect(cls.shutdown_wnf_listener, Qt.ConnectionType.UniqueConnection)  # pyright: ignore[reportCallIssue]
            else:
                logging.warning("DndService failed with status: 0x%08X", status & 0xFFFFFFFF)
        except Exception:
            logging.exception("Failed to initialize DndService.")

    @classmethod
    def shutdown_wnf_listener(cls):
        """Unsubscribes from the WNF notification."""
        if not cls._wnf_is_active:
            return

        status = RtlUnsubscribeWnfStateChangeNotification(cls._wnf_subscription_handle)
        if status != 0:
            logging.warning("DndService shutdown failed with status: 0x%08X", status & 0xFFFFFFFF)
        else:
            logging.info("Stopping DndService...")

        cls._wnf_subscription_handle = c_void_p()
        cls._wnf_callback_reference = None
        cls._wnf_is_active = False
