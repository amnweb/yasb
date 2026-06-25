import ctypes
import logging
from ctypes import POINTER, byref, c_void_p, wintypes

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from core.events.service import EventService
from core.utils.win32.structs import GUID

# Load isolated DLL instances to avoid mutating global bindings
_ole32 = ctypes.WinDLL("ole32")
_ntdll = ctypes.WinDLL("ntdll")

COM_CLASS_ID_QUIET_HOURS = GUID(0xF53321FA, 0x34F8, 0x4B7F, (0xB9, 0xA3, 0x36, 0x18, 0x77, 0xCB, 0x94, 0xCF))
COM_INTERFACE_ID_QUIET_HOURS = GUID(0x6BFF4732, 0x81EC, 0x4FFB, (0xAE, 0x67, 0xB6, 0xC1, 0xBC, 0x29, 0x63, 0x1F))

# COM initialize/uninitialize signatures
_CoInitialize = _ole32.CoInitialize
_CoInitialize.restype = wintypes.HRESULT
_CoInitialize.argtypes = [c_void_p]

_CoUninitialize = _ole32.CoUninitialize
_CoUninitialize.restype = None
_CoUninitialize.argtypes = []

_CoCreateInstance = _ole32.CoCreateInstance
_CoCreateInstance.restype = wintypes.HRESULT
_CoCreateInstance.argtypes = [
    POINTER(GUID),
    c_void_p,
    wintypes.DWORD,
    POINTER(GUID),
    POINTER(c_void_p),
]

_CoTaskMemFree = _ole32.CoTaskMemFree
_CoTaskMemFree.restype = None
_CoTaskMemFree.argtypes = [c_void_p]

# WNF signatures
WnfCallbackType = ctypes.WINFUNCTYPE(
    ctypes.c_long,  # NTSTATUS
    ctypes.c_uint64,  # StateName
    ctypes.c_ulong,  # ChangeStamp
    c_void_p,  # TypeId
    c_void_p,  # CallbackContext
    c_void_p,  # Buffer
    ctypes.c_ulong,  # BufferSize
)

_RtlSubscribeWnfStateChangeNotification = _ntdll.RtlSubscribeWnfStateChangeNotification
_RtlSubscribeWnfStateChangeNotification.restype = ctypes.c_long
_RtlSubscribeWnfStateChangeNotification.argtypes = [
    POINTER(c_void_p),  # Subscription
    ctypes.c_uint64,  # StateName
    ctypes.c_ulong,  # ChangeStamp
    WnfCallbackType,  # Callback
    c_void_p,  # CallbackContext
    c_void_p,  # TypeId
    ctypes.c_ulong,  # SerializationGroup
    ctypes.c_ulong,  # Unknown
]

_RtlUnsubscribeWnfStateChangeNotification = _ntdll.RtlUnsubscribeWnfStateChangeNotification
_RtlUnsubscribeWnfStateChangeNotification.restype = ctypes.c_long
_RtlUnsubscribeWnfStateChangeNotification.argtypes = [c_void_p]


class DndService:
    """A lightweight service to query and control Windows Focus Assist/Do Not Disturb."""

    # 0xD83063EA3BF1C75 = WNF_SHEL_QUIETHOURS_ACTIVE_PROFILE_CHANGED
    WNF_STATE_QUIET_HOURS_CHANGED = 0xD83063EA3BF1C75

    _wnf_subscription_handle = c_void_p()
    _wnf_callback_reference = None
    _wnf_is_active = False

    PROFILES = {
        "Microsoft.QuietHoursProfile.Unrestricted": "disabled",
        "Microsoft.QuietHoursProfile.PriorityOnly": "priority",
        "Microsoft.QuietHoursProfile.AlarmsOnly": "alarms",
    }
    MODES = {v: k for k, v in PROFILES.items()}

    @staticmethod
    def _get_com_method_from_vtable(com_object_pointer, vtable_index, return_type, *argument_types):
        """Extracts a C function pointer from a COM object's virtual method table."""
        vtable = ctypes.cast(com_object_pointer, POINTER(POINTER(c_void_p)))
        return ctypes.WINFUNCTYPE(return_type, *argument_types)(vtable[0][vtable_index])

    @classmethod
    def _connect_to_quiet_hours_service(cls):
        """Initializes COM and creates an instance of the QuietHoursSettings COM service."""
        _CoInitialize(None)
        try:
            com_object_pointer = c_void_p()
            hresult_code = _CoCreateInstance(
                byref(COM_CLASS_ID_QUIET_HOURS),
                None,
                4,  # CLSCTX_LOCAL_SERVER
                byref(COM_INTERFACE_ID_QUIET_HOURS),
                byref(com_object_pointer),
            )
            if hresult_code != 0:
                raise RuntimeError(f"CoCreateInstance failed with status: 0x{hresult_code & 0xFFFFFFFF:08X}")
            return com_object_pointer
        except Exception:
            _CoUninitialize()
            raise

    @classmethod
    def _release_com_object(cls, com_object_pointer):
        """Calls the Release() method on the COM object and uninitializes COM."""
        try:
            vtable = ctypes.cast(com_object_pointer, POINTER(POINTER(c_void_p)))
            release_method = ctypes.WINFUNCTYPE(wintypes.ULONG, c_void_p)(vtable[0][2])
            release_method(com_object_pointer)
        finally:
            _CoUninitialize()

    @classmethod
    def get_status(cls) -> str:
        """Returns: 'disabled', 'priority', or 'alarms'"""
        try:
            com_object_pointer = cls._connect_to_quiet_hours_service()
        except Exception:
            return "unknown"

        try:
            # vtable index 3 is get_UserSelectedProfile
            com_method = cls._get_com_method_from_vtable(
                com_object_pointer, 3, wintypes.HRESULT, c_void_p, POINTER(c_void_p)
            )
            profile_id_buffer = c_void_p()
            if com_method(com_object_pointer, byref(profile_id_buffer)) == 0:
                try:
                    if profile_id_buffer.value:
                        profile_str = ctypes.wstring_at(profile_id_buffer.value)
                        return cls.PROFILES.get(profile_str, "unknown")
                finally:
                    if profile_id_buffer.value:
                        _CoTaskMemFree(profile_id_buffer)
            return "unknown"
        except Exception:
            return "unknown"
        finally:
            cls._release_com_object(com_object_pointer)

    @classmethod
    def set_status(cls, mode: str) -> None:
        """Write UserSelectedProfile. mode: 'disabled', 'priority', or 'alarms'."""
        if mode not in cls.MODES:
            raise ValueError(f"Invalid DND mode '{mode}'. Use: {list(cls.MODES.keys())}")
        profile = cls.MODES[mode]

        try:
            com_object_pointer = cls._connect_to_quiet_hours_service()
        except Exception:
            return

        try:
            # vtable index 4 is put_UserSelectedProfile
            com_method = cls._get_com_method_from_vtable(
                com_object_pointer, 4, wintypes.HRESULT, c_void_p, ctypes.c_wchar_p
            )
            com_method(com_object_pointer, profile)
        finally:
            cls._release_com_object(com_object_pointer)

    @staticmethod
    def _wnf_callback(state_name, change_stamp, type_id, context, buffer, buffer_size):
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

            status = _RtlSubscribeWnfStateChangeNotification(
                byref(cls._wnf_subscription_handle),
                ctypes.c_uint64(cls.WNF_STATE_QUIET_HOURS_CHANGED),
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
                if QApplication.instance():
                    QApplication.instance().aboutToQuit.connect(
                        cls.shutdown_wnf_listener, Qt.ConnectionType.UniqueConnection
                    )
            else:
                logging.warning("DndService failed with status: 0x%08X", status & 0xFFFFFFFF)
        except Exception:
            logging.exception("Failed to initialize DndService.")

    @classmethod
    def shutdown_wnf_listener(cls):
        """Unsubscribes from the WNF notification."""
        if not cls._wnf_is_active:
            return

        status = _RtlUnsubscribeWnfStateChangeNotification(cls._wnf_subscription_handle)
        if status != 0:
            logging.warning("DndService shutdown failed with status: 0x%08X", status & 0xFFFFFFFF)
        else:
            logging.info("Stopping DndService...")

        cls._wnf_subscription_handle = c_void_p()
        cls._wnf_callback_reference = None
        cls._wnf_is_active = False
