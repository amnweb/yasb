import logging
import os
import winsound

from PyQt6.QtCore import QObject, QUrl, pyqtSlot

from core.app.windows.toast import ToastNotifier
from settings import APP_ICON_TRANSPARENT, SCRIPT_PATH

DEFAULT_SOUND = os.path.join(SCRIPT_PATH, "assets", "sound", "notification01.wav")


class Notifier(QObject):
    """Toasts and sounds for widgets.

    In QML it is a singleton: Notifier.toast("Pomodoro", "Time for a break"), Notifier.playSound() for YASB's sound or
    Notifier.playSound(Qt.resolvedUrl("ding.wav")) for a WAV beside the widget, and Notifier.stopSound().
    """

    @pyqtSlot(str, str)
    def toast(self, title: str, message: str) -> None:
        """Shows a Windows toast under YASB's name and icon."""
        try:
            ToastNotifier().show(APP_ICON_TRANSPARENT, title, message)
        except Exception:
            logging.exception("Could not show the toast %r", title)

    @pyqtSlot()
    @pyqtSlot(str)
    def playSound(self, source: str = "") -> None:
        """Plays a WAV file, given as a path or file URL, or YASB's notification sound when none is given."""
        url = QUrl(source)
        path = (url.toLocalFile() if url.isLocalFile() else source) or DEFAULT_SOUND
        if not os.path.isfile(path):
            logging.warning("The sound %s does not exist", path)
            return
        try:
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        except RuntimeError:
            logging.warning("Could not play the sound %s", path)

    @pyqtSlot()
    def stopSound(self) -> None:
        winsound.PlaySound(None, 0)
