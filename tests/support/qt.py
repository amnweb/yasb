from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtQuick import QQuickItem


def wait(ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def find_item(parent: QQuickItem, name: str) -> QQuickItem | None:
    for child in parent.childItems():
        if child.objectName() == name:
            return child
        if (found := find_item(child, name)) is not None:
            return found
    return None
