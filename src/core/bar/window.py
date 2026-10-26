import logging
import math
import os
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import override

from PyQt6.QtCore import QObject, QRect, QSizeF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QCloseEvent, QColor, QGuiApplication, QRegion, QScreen
from PyQt6.QtQml import QQmlComponent, QQmlEngine
from PyQt6.QtQuick import QQuickItem, QQuickWindow

from core.bar.animation import BarAnimationManager
from core.bar.appbar import AppBarManager
from core.bar.autohide import AutoHideManager, MaximizedWindowWatcher
from core.bar.geometry import bar_geometry, bar_length
from core.bar.revisions import Revisions, path_key
from core.events.service import EventService
from core.utils.alert_dialog import raise_info_alert
from core.utils.qml import qml_property
from core.utils.win32 import app_bar, backdrop
from core.utils.win32.bindings.user32 import MonitorFromWindow
from core.validation.bar import BarConfig
from core.widget_files import bar_widget_files
from settings import APP_BAR_TITLE, DEFAULT_CONFIG_DIRECTORY, SCRIPT_PATH

BAR_QML = Path(SCRIPT_PATH) / "core" / "qml" / "Yasb" / "Bar" / "Bar.qml"

APP_BAR_EDGES = {
    "top": app_bar.AppBarEdge.Top,
    "bottom": app_bar.AppBarEdge.Bottom,
    "left": app_bar.AppBarEdge.Left,
    "right": app_bar.AppBarEdge.Right,
}

# QRect.adjust() deltas, per unit of overhang, that grow the window away from its screen edge
OVERHANG_SIDES = {"top": (0, 0, 0, 1), "bottom": (0, -1, 0, 0), "left": (0, 0, 1, 0), "right": (-1, 0, 0, 0)}


@contextmanager
def _without_redirection_surface() -> Generator[None]:
    # Qt reads this when it creates a native window. Without the GDI redirection surface some systems no
    # longer paint an opaque layer over the backdrop, but QWidget windows created meanwhile would draw nothing.
    os.environ["QT_QPA_DISABLE_REDIRECTION_SURFACE"] = "1"
    try:
        yield
    finally:
        del os.environ["QT_QPA_DISABLE_REDIRECTION_SURFACE"]


def is_dark_scheme() -> bool:
    hints = QGuiApplication.styleHints()
    return hints is not None and hints.colorScheme() == Qt.ColorScheme.Dark


class BarContext(QObject):
    def __init__(self, window: BarWindow):
        super().__init__(window)
        self._window = window
        files = bar_widget_files(window.config)
        self.widget_keys = {path_key(file.path) for slot_files in files.values() for file in slot_files}
        self._widgets = {
            slot: [{"name": file.name, "url": window.revisions.url(file.path).toString()} for file in slot_files]
            for slot, slot_files in files.items()
        }

    @qml_property(str, constant=True)
    def name(self) -> str:
        return self._window.name

    @qml_property(str, constant=True)
    def screenName(self) -> str:
        return self._window.target_screen.name()

    @qml_property(str, constant=True)
    def edge(self) -> str:
        return self._window.config.edge

    @qml_property("QVariantMap", constant=True)
    def widgets(self) -> dict[str, list[dict[str, str]]]:
        return self._widgets


class BarWindow(QQuickWindow):
    cli_requested = pyqtSignal(str, str)

    def __init__(
        self,
        engine: QQmlEngine,
        name: str,
        screen: QScreen,
        config: BarConfig,
        revisions: Revisions | None = None,
    ):
        super().__init__()
        self._engine = engine
        self.revisions = revisions or Revisions()
        self.name = name
        self.config = config
        self.target_screen = screen
        self.bar_id = f"{name}_{screen.name().replace('\\', '').replace('.', '')}_{str(uuid.uuid4())[:8]}"
        self.hide_on_fullscreen = config.hide_on_fullscreen and config.always_on_top
        self.autohide_manager: AutoHideManager | None = None
        self._maximized_watcher: MaximizedWindowWatcher | None = None
        self._app_bar = app_bar.Win32AppBar()
        self._event_service = EventService()
        self.item: QQuickItem | None = None
        self.context: BarContext | None = None
        self.shown_file: Path | None = None
        self.load_errors: list[str] = []
        self.overhang = 0
        self.bar_file = self._resolve_bar_file()

        flags = Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
        if config.always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setFlags(flags)
        self.setTitle(APP_BAR_TITLE)
        self.setScreen(screen)
        self.setColor(QColor(Qt.GlobalColor.transparent))
        self.widthChanged.connect(self._fit_item)
        self.heightChanged.connect(self._fit_item)
        self._load_bar()

        with _without_redirection_surface():
            self.create()
        self.hwnd = int(self.winId())
        self.monitor_hwnd = MonitorFromWindow(self.hwnd)

        self.reposition()
        self.apply_backdrop(is_dark_scheme())
        self._animation = BarAnimationManager(self, self)

        if self.hide_on_fullscreen or config.reserve_space:
            AppBarManager().register_bar(self.hwnd, self)
        self.update_app_bar()

        if config.auto_hide == "always":
            self.enable_autohide()
        elif config.auto_hide == "maximized" and not config.reserve_space:
            self._maximized_watcher = MaximizedWindowWatcher(self, self)

        screen.geometryChanged.connect(self._on_screen_changed, Qt.ConnectionType.QueuedConnection)
        self.cli_requested.connect(self.handle_cli)
        self._event_service.register_event("handle_bar_cli", self.cli_requested)

        self._animation.show_bar(initial=True)

    def _resolve_bar_file(self) -> Path:
        if self.config.file is None:
            return BAR_QML
        path = Path(self.config.file)
        return path if path.is_absolute() else Path(DEFAULT_CONFIG_DIRECTORY) / path

    def _create(self, path: Path) -> tuple[QQuickItem | None, BarContext | None, list[str]]:
        if not path.is_file():
            return None, None, [f"{path} does not exist"]
        context = BarContext(self)
        component = QQmlComponent(self._engine, self.revisions.url(path))
        created = None if component.isError() else component.createWithInitialProperties({"context": context})
        errors = [error.toString() for error in component.errors()]
        item = created if isinstance(created, QQuickItem) else None
        if not errors and (item is None or item.property("slotNames") is None):
            errors.append(f"{path} is not a bar, its root must be Bar or BarBase from 'import Yasb.Bar'")
        if item is None or errors:
            if created is not None:
                created.deleteLater()
            context.deleteLater()
            return None, None, errors
        return item, context, []

    def _show(self, item: QQuickItem, context: BarContext, path: Path) -> None:
        old_item, old_context = self.item, self.context
        self.item, self.context, self.shown_file = item, context, path
        item.setParentItem(self.contentItem())
        self._fit_item()
        if self.config.length == "auto":
            (item.implicitHeightChanged if self.config.vertical else item.implicitWidthChanged).connect(self.reposition)
        if item.property("edgeRadius") is not None:
            getattr(item, "edgeRadiusChanged").connect(self.reposition)
        if old_item is not None:
            old_item.setParentItem(None)
            old_item.deleteLater()
        if old_context is not None:
            old_context.deleteLater()
        QTimer.singleShot(0, self._engine.trimComponentCache)
        self._warn_about_missing_slots(path)

    def _fit_item(self) -> None:
        if self.item is None:
            return
        edge, overhang = self.config.edge, self.overhang
        self.item.setX(overhang if edge == "right" else 0)
        self.item.setY(overhang if edge == "bottom" else 0)
        if self.config.vertical:
            self.item.setSize(QSizeF(self.width() - overhang, self.height()))
        else:
            self.item.setSize(QSizeF(self.width(), self.height() - overhang))

    def _load_bar(self) -> None:
        path = self.bar_file
        item, context, errors = self._create(path)
        if item is None and path != BAR_QML:
            details = "\n".join(errors)
            logging.error("Bar %s could not load %s, using the built-in bar:\n%s", self.name, path, details)
            raise_info_alert(
                title=f"Failed to load the bar file of bar '{self.name}'",
                msg="YASB is showing its built-in bar instead.",
                informative_msg="Please click 'Show Details' to find out more.",
                additional_details=details,
            )
            path = BAR_QML
            item, context, errors = self._create(path)
        self.load_errors = errors
        for error in errors:
            logging.error("Bar %s: %s", self.name, error)
        if item is not None and context is not None:
            self._show(item, context, path)

    def reload_qml(self) -> None:
        path = self.bar_file
        item, context, errors = self._create(path)
        if item is None and self.shown_file == BAR_QML and path != BAR_QML:
            path = BAR_QML
            item, context, _ = self._create(path)
        if item is None or context is None:
            details = "\n".join(errors)
            logging.error(
                "Bar %s kept its current content, %s could not be loaded:\n%s", self.name, self.bar_file, details
            )
            return
        self._show(item, context, path)
        self.reposition()
        logging.info("Bar %s reloaded %s", self.name, path)

    def uses(self, keys: set[str]) -> bool:
        if path_key(self.bar_file) in keys:
            return True
        return self.context is not None and bool(self.context.widget_keys & keys)

    def widget_files_changed(self) -> bool:
        files = bar_widget_files(self.config)
        current = {path_key(file.path) for slot_files in files.values() for file in slot_files}
        return self.context is not None and current != self.context.widget_keys

    def _warn_about_missing_slots(self, path: Path) -> None:
        slots: set[str] = set(self.item.property("slotNames") or []) if self.item is not None else set()
        for slot in sorted(self.config.widgets.keys() - slots):
            logging.warning(
                "Bar %s has no slot '%s' in %s, so its widgets are not shown: %s",
                self.name,
                slot,
                path,
                ", ".join(self.config.widgets[slot]),
            )

    @property
    def autohide_enabled(self) -> bool:
        return self.autohide_manager is not None and self.autohide_manager.is_enabled()

    def _content_length(self) -> int:
        if self.item is None:
            return 0
        return math.ceil(self.item.implicitHeight() if self.config.vertical else self.item.implicitWidth())

    def _edge_overhang(self, bar: QRect, screen: QRect) -> int:
        radius = self.item.property("edgeRadius") if self.item is not None else None
        if self.config.vertical:
            spans = bar.top() == screen.top() and bar.height() == screen.height()
        else:
            spans = bar.left() == screen.left() and bar.width() == screen.width()
        return math.ceil(radius) if radius and spans else 0

    def reposition(self) -> None:
        screen = self.target_screen.geometry()
        geometry = bar_geometry(self.config, screen, bar_length(self.config, screen, self._content_length()))
        self.overhang = self._edge_overhang(geometry, screen)
        geometry.adjust(*(side * self.overhang for side in OVERHANG_SIDES[self.config.edge]))
        self.setGeometry(geometry)
        self._fit_item()
        self._update_mask()

    def _update_mask(self) -> None:
        if not self.overhang:
            self.setMask(QRegion())
            return
        # Transparent pixels of this window still take clicks, so of the strip the edge curves hang in,
        # only the two corners holding the curves keep them
        size, width, height, edge = self.overhang, self.width(), self.height(), self.config.edge
        if self.config.vertical:
            mask = QRegion(size if edge == "right" else 0, 0, width - size, height)
            strip = 0 if edge == "right" else width - size
            corners = [QRegion(strip, 0, size, size), QRegion(strip, height - size, size, size)]
        else:
            mask = QRegion(0, size if edge == "bottom" else 0, width, height - size)
            strip = 0 if edge == "bottom" else height - size
            corners = [QRegion(0, strip, size, size), QRegion(width - size, strip, size, size)]
        for corner in corners:
            mask = mask.united(corner)
        self.setMask(mask)

    def _on_screen_changed(self) -> None:
        logging.info(
            "Screen geometry changed. Updating position for bar %s on %s", self.name, self.target_screen.name()
        )
        self.reposition()
        self.update_app_bar()
        if self.autohide_manager is not None and self.autohide_manager.is_enabled():
            self.autohide_manager.setup_detection_zone()

    def apply_backdrop(self, dark: bool) -> None:
        settings = self.config.backdrop
        backdrop.apply_backdrop(self.hwnd, settings.type, settings.corners, settings.border, dark)

    def update_app_bar(self) -> None:
        margin = self.config.margin
        across = margin.left + margin.right if self.config.vertical else margin.top + margin.bottom
        self._app_bar.create_appbar(
            self.hwnd,
            APP_BAR_EDGES[self.config.edge],
            self.config.thickness + across,
            self.target_screen,
            self.target_screen.devicePixelRatio() > 1.0,
            self.name,
            self.config.reserve_space,
            self.config.always_on_top,
        )

    def remove_app_bar(self) -> None:
        self._app_bar.remove_appbar()

    def show_bar(self) -> None:
        self._animation.show_bar()

    def hide_bar(self) -> None:
        self._animation.hide_bar()

    def enable_autohide(self) -> None:
        if self.autohide_manager is None:
            self.autohide_manager = AutoHideManager(self, self)
        if not self.autohide_manager.is_enabled():
            self.autohide_manager.setup_autohide()

    def disable_autohide(self) -> None:
        if self.autohide_manager is not None:
            self.autohide_manager.cleanup()
            self.autohide_manager = None
        if not self.isVisible():
            self.show()

    def handle_cli(self, action: str, screen_name: str) -> None:
        if screen_name and self.target_screen.name() != screen_name:
            return
        manages_app_bar = self.config.reserve_space and not self.autohide_enabled
        if action == "show" or (action == "toggle" and not self.isVisible()):
            self.show_bar()
            if manages_app_bar:
                self.update_app_bar()
        elif action in ("hide", "toggle"):
            if manages_app_bar:
                self.remove_app_bar()
            self.hide_bar()

    def cleanup(self) -> None:
        self._event_service.unregister_event("handle_bar_cli", self.cli_requested)
        AppBarManager().unregister_bar(self.hwnd)
        if self._maximized_watcher is not None:
            self._maximized_watcher.cleanup()
        if self.autohide_manager is not None:
            self.autohide_manager.cleanup()
        self._animation.cleanup()
        self.remove_app_bar()

    @override
    def closeEvent(self, a0: QCloseEvent | None) -> None:
        self.cleanup()
        super().closeEvent(a0)
