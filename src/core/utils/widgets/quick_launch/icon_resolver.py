import logging
import math
import os

from PyQt6.QtCore import QThread, pyqtSignal

from core.utils.win32.icon_extractor import IconExtractorUtil

# Standard icon sizes found in ICO / PE resources.
# 48 is the minimum - the 48px ICO resource is typically higher quality
# artwork than 32px, so downscaling from 48 looks better than from 32.
_STANDARD_SIZES = (48, 64, 96, 128, 256)


def compute_extraction_size(icon_size: int, dpr: float) -> int:
    """Return the optimal extraction size for a given logical icon size and DPR.

    Snaps *up* to the nearest standard ICO resource size that covers the
    physical pixel requirement (``ceil(icon_size * dpr)``), with a floor
    of 48.  This ensures the UI only ever *downscales* (sharp) and never
    upscales (blurry).
    """
    needed = math.ceil(icon_size * dpr)
    for s in _STANDARD_SIZES:
        if s >= needed:
            return s
    return _STANDARD_SIZES[-1]


class IconResolverWorker(QThread):
    """Background thread that resolves icons for discovered apps."""

    icon_ready = pyqtSignal(str, str)

    def __init__(self, apps: list[tuple[str, str, object]], icons_dir: str, size: int = 48):
        super().__init__()
        self._apps = apps
        self._icons_dir = icons_dir
        self._size = size
        self._should_stop = False

    def stop(self):
        self._should_stop = True

    def run(self):
        self._default_icon = IconExtractorUtil.extract_default_icon(self._icons_dir, size=self._size)
        for name, path, _ in self._apps:
            if self._should_stop:
                break
            app_key = f"{name}::{path}"
            try:
                icon_path = self._resolve_icon(path)
                if not icon_path or not os.path.isfile(icon_path):
                    icon_path = self._default_icon
                if icon_path and os.path.isfile(icon_path):
                    self.icon_ready.emit(app_key, icon_path)
            except Exception as e:
                logging.debug(f"Icon resolve failed for {name}: {e}")
                if self._default_icon:
                    self.icon_ready.emit(app_key, self._default_icon)

    def _resolve_icon(self, path: str) -> str | None:
        sz = self._size
        if path.startswith("UWP::"):
            appid = path.replace("UWP::", "")
            return IconExtractorUtil.extract_shell_appid_icon(appid, self._icons_dir, size=sz)
        if path.startswith("CPL::"):
            return IconExtractorUtil.extract_cpl_icon(path, self._icons_dir, size=sz)
        ext = os.path.splitext(path)[1].lower()
        if ext == ".lnk":
            return IconExtractorUtil.extract_lnk_icon(path, self._icons_dir, size=sz)
        if ext == ".url":
            return IconExtractorUtil.extract_url_icon(path, self._icons_dir, size=sz)
        if os.path.isfile(path):
            return IconExtractorUtil.extract_icon_with_index(path, 0, self._icons_dir, size=sz)
        return None
