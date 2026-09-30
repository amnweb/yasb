import hashlib
import os
import threading
import time
from contextlib import suppress

from PyQt6.QtGui import QImage

from core.utils.system import app_data_path

FOLDER = app_data_path("wallpaper_thumbnails")
MAX_BYTES = 100 * 1024 * 1024
MAX_AGE_SECONDS = 30 * 24 * 60 * 60
CACHE_VERSION = 1


def key(image_path: str, width: int, height: int) -> str | None:
    """The cache file name for *image_path* drawn at *width* x *height* pixels, or None if the image is gone."""
    try:
        stat = os.stat(image_path)
    except OSError:
        return None
    source = os.path.normcase(os.path.normpath(image_path))
    identity = f"{CACHE_VERSION}|{source}|{stat.st_mtime_ns}|{stat.st_size}|{width}x{height}"
    return hashlib.blake2b(identity.encode(), digest_size=16).hexdigest() + ".png"


def load(name: str) -> QImage | None:
    image = QImage(os.path.join(FOLDER, name))
    return None if image.isNull() else image


def save(name: str, image: QImage) -> None:
    path = os.path.join(FOLDER, name)
    partial = f"{path}.{threading.get_ident()}.tmp"
    try:
        os.makedirs(FOLDER, exist_ok=True)
        if image.save(partial, "PNG"):
            os.replace(partial, path)
            return
    except OSError:
        pass
    with suppress(OSError):
        os.remove(partial)


def prune() -> None:
    """Deletes thumbnails older than MAX_AGE_SECONDS, then the oldest ones until the rest fit in MAX_BYTES."""
    entries = []
    try:
        with os.scandir(FOLDER) as scan:
            for entry in scan:
                stat = entry.stat()
                entries.append((stat.st_mtime, stat.st_size, entry.path))
    except OSError:
        return

    entries.sort()
    total = sum(size for _, size, _ in entries)
    expired = time.time() - MAX_AGE_SECONDS
    for modified, size, path in entries:
        if modified >= expired and total <= MAX_BYTES:
            break
        with suppress(OSError):
            os.remove(path)
            total -= size
