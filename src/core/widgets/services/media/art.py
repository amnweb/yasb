import threading

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QImage
from PyQt6.QtQuick import QQuickImageProvider

MEDIA_ART_PROVIDER = "media-art"

_lock = threading.Lock()
_art: dict[int, bytes] = {}


def art_url(revision: int) -> str:
    return f"image://{MEDIA_ART_PROVIDER}/{revision}" if revision else ""


def keep_art(art: dict[int, bytes]) -> None:
    """Replaces the album art QML can load, keyed by revision."""
    with _lock:
        _art.clear()
        _art.update(art)


class MediaArtProvider(QQuickImageProvider):
    def __init__(self) -> None:
        super().__init__(QQuickImageProvider.ImageType.Image)

    def requestImage(self, id: str | None, requestedSize: QSize) -> tuple[QImage, QSize]:
        with _lock:
            data = _art.get(int(id)) if id and id.isdigit() else None
        image = QImage.fromData(data) if data else QImage()
        original = image.size()
        if not image.isNull() and (requestedSize.width() > 0 or requestedSize.height() > 0):
            width = requestedSize.width() if requestedSize.width() > 0 else image.width()
            height = requestedSize.height() if requestedSize.height() > 0 else image.height()
            image = image.scaled(
                width, height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
        return image, original
