from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtQuick import QQuickImageProvider

from core.utils.icons.service import IconService, WindowIcon

ICON_PROVIDER = "icon"


def window_icon_url(hwnd: int, revision: int) -> str:
    """The revision makes QML ask again once IconService has finished loading the icon."""
    return f"image://{ICON_PROVIDER}/window/{hwnd}/{revision}"


class IconImageProvider(QQuickImageProvider):
    def __init__(self) -> None:
        super().__init__(QQuickImageProvider.ImageType.Pixmap)

    def requestPixmap(self, id: str | None, requestedSize: QSize) -> tuple[QPixmap, QSize]:
        kind, _, rest = (id or "").partition("/")
        hwnd = rest.split("/", 1)[0]
        size = requestedSize.width() if requestedSize.width() > 0 else 16
        pixmap = None
        if kind == "window" and hwnd.isdigit():
            pixmap = IconService.instance().get_icon(WindowIcon(int(hwnd)), size, 1.0)
        if pixmap is None:
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.GlobalColor.transparent)
        return pixmap, pixmap.size()
