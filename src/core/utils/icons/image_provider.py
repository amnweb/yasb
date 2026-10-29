import base64

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtQuick import QQuickImageProvider

from core.utils.icons.service import IconService
from core.utils.icons.sources import AppIcon, FileIcon, IconSource, ProcessIcon, WindowIcon

ICON_PROVIDER = "icon"


def window_icon_url(hwnd: int, revision: int) -> str:
    """The revision makes QML ask again once IconService has finished loading the icon."""
    return f"image://{ICON_PROVIDER}/window/{hwnd}/{revision}"


def icon_url(source: IconSource, revision: int) -> str:
    """The URL of any icon source. Paths and app ids are base64 so they survive as one URL segment."""
    match source:
        case WindowIcon(hwnd):
            return window_icon_url(hwnd, revision)
        case ProcessIcon(pid):
            kind, value = "process", str(pid)
        case AppIcon(aumid):
            kind, value = "app", base64.urlsafe_b64encode(aumid.encode()).decode()
        case FileIcon(path):
            kind, value = "file", base64.urlsafe_b64encode(path.encode()).decode()
    return f"image://{ICON_PROVIDER}/{kind}/{value}/{revision}"


def _source(kind: str, value: str) -> IconSource | None:
    try:
        match kind:
            case "window" if value.isdigit():
                return WindowIcon(int(value))
            case "process" if value.isdigit():
                return ProcessIcon(int(value))
            case "app":
                return AppIcon(base64.urlsafe_b64decode(value).decode())
            case "file":
                return FileIcon(base64.urlsafe_b64decode(value).decode())
            case _:
                return None
    except ValueError:
        return None


class IconImageProvider(QQuickImageProvider):
    def __init__(self) -> None:
        super().__init__(QQuickImageProvider.ImageType.Pixmap)

    def requestPixmap(self, id: str | None, requestedSize: QSize) -> tuple[QPixmap, QSize]:
        kind, _, rest = (id or "").partition("/")
        source = _source(kind, rest.split("/", 1)[0])
        size = requestedSize.width() if requestedSize.width() > 0 else 16
        pixmap = IconService.instance().get_icon(source, size, 1.0) if source is not None else None
        if pixmap is None:
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.GlobalColor.transparent)
        return pixmap, pixmap.size()
