"""Shared screenshot constants and save/export helpers."""

from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QStandardPaths
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication, QFileDialog, QWidget

HANDLE = 8
MIN_SIZE = 5
SNAP = 12  # magnet distance to monitor edges (px)

UI = {
    "bg": "#2c2c2c",
    "border": "#3f3f3f",
    "hover": "#3a3a3a",
    "text": "#f0f0f0",
    "accent": "#00aeff",
}


def default_save_dir() -> Path:
    """User Pictures/Screenshots directory."""
    pics = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.PicturesLocation)
    if not pics:
        pics = str(Path.home() / "Pictures")
    return Path(pics) / "Screenshots"


def export_pixmap(pix: QPixmap, *, save: bool, parent: QWidget | None = None) -> bool:
    """
    Copy pixmap to clipboard, or open a save dialog.

    Returns False if the user cancelled a save dialog.
    """
    if not save:
        QApplication.clipboard().setPixmap(pix)
        return True
    folder = default_save_dir()
    folder.mkdir(parents=True, exist_ok=True)
    initial = str(folder / f"{datetime.now():%Y%m%d_%H%M%S_%f}.png")
    path, _ = QFileDialog.getSaveFileName(parent, "Save Screenshot", initial, "PNG Image (*.png);;All Files (*)")
    if not path:
        return False
    pix.save(path, "PNG")
    return True
