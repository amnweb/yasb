from PyQt6.QtCore import pyqtProperty, pyqtSignal


def qml_property[T](
    kind: type[T] | str, *, constant: bool = False, notify: pyqtSignal | None = None
) -> pyqtProperty[T]:
    if notify is None:
        return pyqtProperty(kind, None, constant=constant)
    return pyqtProperty(kind, None, constant=constant, notify=notify)
