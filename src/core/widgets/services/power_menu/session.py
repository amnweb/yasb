import logging
from collections.abc import Callable

from PyQt6.QtCore import QObject, QUrl, pyqtSignal, pyqtSlot

from core.utils.qml import qml_property
from core.utils.win32.bindings.kernel32 import GetTickCount64
from core.widgets.services.power_menu.power_commands import PowerOperations
from core.widgets.services.power_menu.user_info import (
    get_account_type,
    get_user_avatar_path,
    get_user_email,
    get_windows_username,
)


class PowerSession(QObject):
    """The signed-in user, how long Windows has been running, and the power commands."""

    uptimeChanged = pyqtSignal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._uptime = 0
        operations = PowerOperations()
        self._actions: dict[str, Callable[[], None]] = {
            "lock": operations.lock,
            "signout": operations.signout,
            "sleep": operations.sleep,
            "hibernate": operations.hibernate,
            "restart": operations.restart,
            "shutdown": operations.shutdown,
            "force_restart": operations.force_restart,
            "force_shutdown": operations.force_shutdown,
        }

    @qml_property(str, constant=True)
    def userName(self) -> str:
        return get_windows_username()

    @qml_property(str, constant=True)
    def email(self) -> str:
        return get_user_email() or ""

    # Administrator or Standard User
    @qml_property(str, constant=True)
    def accountType(self) -> str:
        return get_account_type()

    # The Windows account picture, empty when there is none
    @qml_property(QUrl, constant=True)
    def avatar(self) -> QUrl:
        path = get_user_avatar_path()
        return QUrl.fromLocalFile(path) if path else QUrl()

    # Seconds since Windows started, as of the last refresh()
    @qml_property(int, notify=uptimeChanged)
    def uptime(self) -> int:
        return self._uptime

    @pyqtSlot()
    def refresh(self) -> None:
        self._uptime = GetTickCount64() // 1000
        self.uptimeChanged.emit()

    # lock, signout, sleep, hibernate, restart, shutdown, force_restart or force_shutdown
    @pyqtSlot(str)
    def run(self, action: str) -> None:
        if (command := self._actions.get(action)) is None:
            logging.warning("Power menu: unknown action %r", action)
            return
        command()
