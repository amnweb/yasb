"""YASB Icon Service

    icons = IconService.instance()
    icons.icons_changed.connect(self._refresh_icons)
    pixmap = icons.get_icon(WindowIcon(hwnd), size, dpr)

get_icon() returns the icon at once when it is in memory; otherwise a transparent pixmap of its size, and the icon is
loaded on the icon thread. icons_changed is emitted when an icon asked for with get_icon() was loaded or changed;
widgets then ask again for the icons they show. Icons are kept in memory only, for the running YASB. Which picture a
request gets is decided in core.utils.icons.resolve.
"""

import itertools
import logging
import queue
import threading
from collections import OrderedDict
from collections.abc import Iterable
from ctypes import byref
from ctypes.wintypes import DWORD
from dataclasses import dataclass, field
from enum import IntEnum
from typing import ClassVar, NamedTuple

from PIL import Image
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QApplication

from core.utils.icons.resolve import AppIcon, FileIcon, IconSource, ProcessIcon, WindowIcon, load_icon
from core.utils.win32.aumid import ensure_com_initialized
from core.utils.win32.bindings.user32 import GetClassName, GetWindowThreadProcessId, InternalGetWindowText, IsWindow
from core.utils.win32.utils import get_process_path

logger = logging.getLogger("icon_service")

CACHE_LIMIT_BYTES = 16 * 1024 * 1024

EXPLORER_WINDOW_CLASS = "CabinetWClass"


class _Priority(IntEnum):
    # a widget is showing a blank for it
    SHOWN = 0
    # preloads, and windows that didn't answer in time
    LATER = 1


class _Key(NamedTuple):
    source: IconSource
    # size * dpr
    physical: int
    grayscale: bool


@dataclass
class _Icon:
    # None if there's no icon at all
    image: QImage | None
    # window pid / process exe at load time, to catch reused handles and pids
    owner: object
    # Explorer windows show their folder's icon
    title: str | None
    # False if the window didn't answer in time
    complete: bool
    # per dpr
    pixmaps: dict[float, QPixmap] = field(default_factory=dict[float, QPixmap])


class IconService(QObject):
    icons_changed = pyqtSignal()
    # emitted on the icon thread
    _icon_loaded = pyqtSignal()

    _instance: ClassVar[IconService | None] = None
    _instance_lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()
        # LRU order
        self._cache: OrderedDict[_Key, _Icon] = OrderedDict()
        self._cache_bytes = 0
        # key -> priority it's queued at
        self._waiting: dict[_Key, _Priority] = {}
        # (priority, request number, key); a None key stops the thread
        self._load_queue: queue.PriorityQueue[tuple[int, int, _Key | None]] = queue.PriorityQueue()
        # keeps the asked order within a priority
        self._request_numbers = itertools.count()
        # keys widgets asked for (not just preloaded), never evicted
        self._shown: set[_Key] = set()
        # an icons_changed is already on its way, don't send another
        self._change_pending = False
        # transparent placeholders by (size, dpr)
        self._blank_pixmaps: dict[tuple[int, float], QPixmap] = {}
        self._icon_loaded.connect(self._on_icon_loaded)

        threading.Thread(target=self._run_icon_thread, daemon=True, name="IconService").start()

        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._stop)

    @classmethod
    def instance(cls) -> IconService:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def get_icon(self, source: IconSource, size: int, dpr: float, *, grayscale: bool = False) -> QPixmap | None:
        """The icon of source, for size px on a screen with this dpr; a transparent pixmap of that size while it loads,
        None when there is no icon to show."""
        physical = int(size * dpr)
        if physical <= 0 or _is_empty(source):
            return None
        key = _Key(source, physical, grayscale)
        owner, title = _owner_and_title(source)
        with self._lock:
            self._shown.add(key)
            icon = self._cache.get(key)
            if icon is not None and icon.owner != owner:
                icon = None
            if icon is not None:
                self._cache.move_to_end(key)
            if icon is None or icon.title != title:
                self._enqueue(key, _Priority.SHOWN)
            elif not icon.complete:
                self._enqueue(key, _Priority.LATER)
            if icon is None and grayscale:
                # show the colored icon until the gray one is ready
                colored = self._cache.get(_Key(source, physical, False))
                icon = colored if colored is not None and colored.owner == owner else None

        if icon is None:
            return self._blank_pixmap(physical, dpr)
        if icon.image is None:
            return None
        pixmap = icon.pixmaps.get(dpr)
        if pixmap is None:
            pixmap = QPixmap.fromImage(icon.image)
            pixmap.setDevicePixelRatio(dpr)
            icon.pixmaps[dpr] = pixmap
        return pixmap

    def _blank_pixmap(self, physical: int, dpr: float) -> QPixmap:
        pixmap = self._blank_pixmaps.get((physical, dpr))
        if pixmap is None:
            image = QImage(physical, physical, QImage.Format.Format_ARGB32_Premultiplied)
            # fill(0): filling with a Qt color costs ~12 ms the first time
            image.fill(0)
            pixmap = QPixmap.fromImage(image)
            pixmap.setDevicePixelRatio(dpr)
            self._blank_pixmaps[(physical, dpr)] = pixmap
        return pixmap

    def preload(self, sources: Iterable[IconSource], size: int, dpr: float) -> None:
        """Load icons a widget will need soon, after the ones widgets show now."""
        physical = int(size * dpr)
        if physical <= 0:
            return
        with self._lock:
            for source in sources:
                key = _Key(source, physical, False)
                if not _is_empty(source) and key not in self._cache:
                    self._enqueue(key, _Priority.LATER)

    def _enqueue(self, key: _Key, priority: _Priority) -> None:
        # bump a queued preload if a widget now needs it
        waiting = self._waiting.get(key)
        if waiting is None or priority < waiting:
            self._waiting[key] = priority
            self._load_queue.put((priority, next(self._request_numbers), key))

    def _on_icon_loaded(self) -> None:
        with self._lock:
            self._change_pending = False
        self.icons_changed.emit()

    def _run_icon_thread(self) -> None:
        ensure_com_initialized()
        while (key := self._load_queue.get()[2]) is not None:
            with self._lock:
                if key not in self._waiting:
                    continue  # already loaded at a higher priority
            try:
                icon = _load(key)
            except Exception:
                logger.debug("Failed to load the icon of %s", key.source, exc_info=True)
                icon = None

            with self._lock:
                self._waiting.pop(key, None)
                previous = self._cache.get(key)
                changed = icon is not None and (previous is None or not _images_equal(previous.image, icon.image))
                if icon is None:
                    self._shown.discard(key)
                else:
                    if previous is not None:
                        self._cache_bytes -= _image_bytes(previous)
                        if not changed:
                            icon.pixmaps = previous.pixmaps
                    self._cache[key] = icon
                    self._cache.move_to_end(key)
                    self._cache_bytes += _image_bytes(icon)
                full = self._cache_bytes > CACHE_LIMIT_BYTES
                notify = changed and key in self._shown and not self._change_pending
                if notify:
                    self._change_pending = True

            if full:
                self._enforce_cache_limit()
            if notify:
                self._icon_loaded.emit()

    def _enforce_cache_limit(self) -> None:
        # Dead windows and processes go first, then preloads. Icons on screen stay.
        # Owners are checked without the lock, only this thread adds or removes entries.
        with self._lock:
            owners = [
                (k, icon.owner) for k, icon in self._cache.items() if isinstance(k.source, WindowIcon | ProcessIcon)
            ]
        closed = [key for key, owner in owners if _owner_and_title(key.source)[0] != owner]
        with self._lock:
            for key in closed:
                self._evict(key)
            preloads = [k for k in self._cache if k not in self._shown]
            while self._cache_bytes > CACHE_LIMIT_BYTES and preloads:
                self._evict(preloads.pop(0))

    def _evict(self, key: _Key) -> None:
        # caller holds the lock
        self._cache_bytes -= _image_bytes(self._cache.pop(key))
        self._shown.discard(key)

    def _stop(self) -> None:
        self._load_queue.put((-1, next(self._request_numbers), None))


def _load(key: _Key) -> _Icon | None:
    if isinstance(key.source, WindowIcon) and not IsWindow(key.source.hwnd):
        return None
    owner, title = _owner_and_title(key.source)
    loaded = load_icon(key.source, key.physical)
    return _Icon(_to_qimage(loaded.image, key.physical, key.grayscale), owner, title, loaded.complete)


def _owner_and_title(source: IconSource) -> tuple[object, str | None]:
    match source:
        case WindowIcon(hwnd):
            pid = DWORD(0)
            GetWindowThreadProcessId(hwnd, byref(pid))
            title = InternalGetWindowText(hwnd) if GetClassName(hwnd) == EXPLORER_WINDOW_CLASS else None
            return pid.value, title
        case ProcessIcon(pid):
            return get_process_path(pid), None
        case _:
            return None, None


def _is_empty(source: IconSource) -> bool:
    match source:
        case WindowIcon(0) | ProcessIcon(0) | AppIcon("") | FileIcon(""):
            return True
        case _:
            return False


def _to_qimage(image: Image.Image | None, physical: int, grayscale: bool) -> QImage | None:
    if image is None:
        return None
    image = image.convert("RGBA").resize((physical, physical), Image.Resampling.LANCZOS)
    if grayscale:
        image.paste(image.convert("L"), (0, 0), image)
    data = image.tobytes("raw", "RGBA")  # pyright: ignore[reportUnknownMemberType]
    return QImage(data, physical, physical, QImage.Format.Format_RGBA8888).copy()


def _image_bytes(icon: _Icon) -> int:
    return icon.image.sizeInBytes() if icon.image is not None else 0


def _images_equal(a: QImage | None, b: QImage | None) -> bool:
    if a is None or b is None:
        return a is b
    return a == b
