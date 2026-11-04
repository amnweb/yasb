import os

from PyQt6.QtCore import QObject, pyqtSlot


class Environment(QObject):
    """Environment variables for QML, such as a token kept in YASB's .env file instead of a widget file.

    In QML it is a singleton, used as token: Environment.value("GITHUB_TOKEN").
    """

    @pyqtSlot(str, result="QString")
    def value(self, name: str) -> str:
        """The variable's value, or "" when it is not set."""
        return os.environ.get(name, "")
