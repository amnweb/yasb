from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import pyqtProperty, pyqtSignal


def qml_property(
    kind: type | str, *, constant: bool = False, notify: pyqtSignal | None = None
) -> Callable[[Callable[[Any], Any]], pyqtProperty]:
    # pyright matches pyqtProperty(kind) to the functional overload and asks for fget, an explicit None
    # selects the decorator overload. At runtime notify must be a signal or left out, never None.
    if notify is None:
        return pyqtProperty(kind, None, constant=constant)
    return pyqtProperty(kind, None, constant=constant, notify=notify)
