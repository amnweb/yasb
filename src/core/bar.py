import logging

from PyQt6.QtCore import QEvent, QRect, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QScreen
from PyQt6.QtWidgets import QBoxLayout, QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from core.bar_helper import (
    AppBarManager,
    AutoHideManager,
    AutoWidthManager,
    BarAnimationManager,
    BarCliManager,
    BarContextMenu,
    MaximizedWindowWatcher,
    OsThemeManager,
)
from core.events.service import EventService
from core.utils.utilities import is_valid_percentage_str, percent_to_float
from core.utils.win32.backdrop import enable_blur
from core.utils.win32.utils import get_monitor_hwnd
from core.validation.bar import BarConfig
from settings import APP_BAR_TITLE

try:
    from core.utils.win32 import app_bar

    IMPORT_APP_BAR_MANAGER_SUCCESSFUL = True
except ImportError:
    IMPORT_APP_BAR_MANAGER_SUCCESSFUL = False


class Bar(QWidget):
    handle_bar_management = pyqtSignal(str, str)

    def __init__(
        self,
        bar_id: str,
        bar_name: str,
        bar_screen: QScreen,
        stylesheet: str,
        widgets: dict[str, list[QWidget]],
        config: BarConfig,
        init: bool = False,
    ):
        super().__init__()
        self.config = config
        self._event_service = EventService()
        self.hide()
        self.setScreen(bar_screen)
        self._bar_id = bar_id
        self._bar_name = bar_name
        self._alignment = self.config.alignment.model_dump()
        self._align = self._alignment["align"]
        self._window_flags = self.config.window_flags.model_dump()
        self._dimensions = self.config.dimensions.model_dump()
        self._padding = self.config.padding.model_dump()
        self._animation = self.config.animation.model_dump()
        self._context_menu = self.config.context_menu
        self._layouts = self.config.layouts
        self._autohide_bar = self._window_flags["auto_hide"]
        self._widgets = widgets  # Store widgets reference for context menu
        self._widget_config_map = self.config.widgets.model_dump() or {}
        self._is_auto_width = str(self.config.dimensions.width).lower() == "auto"
        self._os_theme_manager = None
        self._autohide_manager = None
        self._maximized_watcher = None
        self._animation_manager = None
        self._auto_width_manager = None
        self._cli_manager = None
        self._target_screen = bar_screen
        self._fullscreen_app_bar_suspended = False
        self._is_vertical = self._alignment["position"] in ("left", "right")

        self.screen_name = self._target_screen.name()
        self.app_bar_edge = {
            "top": app_bar.AppBarEdge.Top,
            "bottom": app_bar.AppBarEdge.Bottom,
            "left": app_bar.AppBarEdge.Left,
            "right": app_bar.AppBarEdge.Right,
        }[self._alignment["position"]]

        self.setWindowTitle(APP_BAR_TITLE)
        self.setStyleSheet(stylesheet)
        self.setWindowFlag(Qt.WindowType.Tool)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self._bar_frame = QFrame(self)
        self._bar_frame.setProperty(
            "class",
            " ".join(
                [
                    "bar",
                    self.config.class_name,
                    "bar-vertical" if self._is_vertical else "bar-horizontal",
                    f"bar-{self._alignment['position']}",
                ]
            ),
        )
        self._bar_frame.setProperty("orientation", "vertical" if self._is_vertical else "horizontal")
        self._bar_frame.setProperty("edge", self._alignment["position"])

        if IMPORT_APP_BAR_MANAGER_SUCCESSFUL:
            self.app_bar_manager = app_bar.Win32AppBar()
        else:
            self.app_bar_manager = None

        if self._window_flags["always_on_top"]:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)

        try:
            self._os_theme_manager = OsThemeManager(self._bar_frame, self)
            self._os_theme_manager.update_theme_class()
        except Exception as e:
            logging.error("Failed to initialize theme manager: %s", e)
            self._os_theme_manager = None

        self._hide_on_fullscreen = self._window_flags["hide_on_fullscreen"] and self._window_flags["always_on_top"]

        self.position_bar(init)
        self.monitor_hwnd = get_monitor_hwnd(int(self.winId()))

        self._add_widgets(widgets)

        if self._is_auto_width:
            self._auto_width_manager = AutoWidthManager(self, self)
            self._bar_frame.installEventFilter(self)
            QTimer.singleShot(0, self._auto_width_manager.sync)

        self._target_screen.geometryChanged.connect(self.on_geometry_changed, Qt.ConnectionType.QueuedConnection)

        self._cli_manager = BarCliManager(self, self)
        self.handle_bar_management.connect(self._cli_manager.handle)
        self._event_service.register_event("handle_bar_cli", self.handle_bar_management)

        # Initialize animation manager
        self._animation_manager = BarAnimationManager(self, self)
        # If animation is enabled, initial show uses fade effect because of DWM issues
        self._initial_show = True

        if (self._hide_on_fullscreen or self._window_flags["windows_app_bar"]) and self.app_bar_manager:
            AppBarManager().register_bar(int(self.winId()), self)

        self.update_app_bar()

        if self._window_flags["auto_hide"]:
            self._autohide_manager = AutoHideManager(self, self)
            self._autohide_manager.setup_autohide()

        if self._window_flags["hide_on_maximized"] and not self._window_flags["windows_app_bar"]:
            self._maximized_watcher = MaximizedWindowWatcher(self, self)

        if self.config.blur_effect.enabled:
            enable_blur(
                self.winId(),
                DarkMode=self.config.blur_effect.dark_mode,
                RoundCorners=self.config.blur_effect.round_corners,
                RoundCornersType=self.config.blur_effect.round_corners_type,
                BorderColor=self.config.blur_effect.border_color,
            )

        self.show()

    @property
    def bar_id(self) -> str:
        return self._bar_id

    def on_geometry_changed(self, geo: QRect) -> None:
        logging.info(
            "Screen geometry changed. Updating position for bar %s on screen %s",
            self._bar_name,
            self._target_screen.name(),
        )
        self.position_bar()
        # Re-register AppBar when screen config changes (resolution/monitor added/removed)
        self.update_app_bar()

        if self._autohide_manager and self._autohide_manager.is_enabled():
            self._autohide_manager.setup_detection_zone()

        if self._is_auto_width and self._auto_width_manager:
            QTimer.singleShot(0, self._auto_width_manager.sync)

    def update_app_bar(self, reserve_space_override: bool | None = None) -> None:
        if self.app_bar_manager:
            # Always register AppBar for notifications, but only reserve space when windows_app_bar is true
            reserve_space = (
                self._window_flags["windows_app_bar"] if reserve_space_override is None else reserve_space_override
            )
            scale_screen_height = self._target_screen.devicePixelRatio() > 1.0
            self.app_bar_manager.create_appbar(
                self.winId().__int__(),
                self.app_bar_edge,
                (
                    self._resolve_dimension(self._dimensions["width"], self._target_screen.geometry().width())
                    + self._padding["left"]
                    + self._padding["right"]
                )
                if self._is_vertical
                else (
                    self._resolve_dimension(self._dimensions["height"], self._target_screen.geometry().height())
                    + self._padding["top"]
                    + self._padding["bottom"]
                ),
                self._target_screen,
                scale_screen_height,
                self._bar_name,
                reserve_space,
                self._window_flags["always_on_top"],
            )

    def try_remove_app_bar(self) -> None:
        if self.app_bar_manager:
            self.app_bar_manager.remove_appbar()

    def bar_pos(self, bar_w: int, bar_h: int, screen_w: int, screen_h: int) -> tuple[int, int]:
        screen_x = self._target_screen.geometry().x()
        screen_y = self._target_screen.geometry().y()

        if self._is_vertical:
            if self._alignment["position"] == "right":
                x = int(screen_x + screen_w - bar_w - self._padding["right"])
            else:
                x = int(screen_x + self._padding["left"])

            if self._align == "center" or self._alignment.get("center", False):
                available_y = screen_y + self._padding["top"]
                available_height = screen_h - self._padding["top"] - self._padding["bottom"]
                if bar_h >= available_height:
                    y = available_y
                else:
                    y = int(available_y + (available_height - bar_h) / 2)
            elif self._align == "right":
                y = int(screen_y + screen_h - bar_h - self._padding["bottom"])
                min_y = screen_y + self._padding["top"]
                if y < min_y:
                    y = min_y
            else:
                y = int(screen_y + self._padding["top"])
                max_y = screen_y + screen_h - bar_h - self._padding["bottom"]
                if y > max_y:
                    y = max_y
        else:
            if self._align == "center" or self._alignment.get("center", False):
                available_x = screen_x + self._padding["left"]
                available_width = screen_w - self._padding["left"] - self._padding["right"]
                if bar_w >= available_width:
                    x = available_x
                else:
                    x = int(available_x + (available_width - bar_w) / 2)
            elif self._align == "right":
                x = int(screen_x + screen_w - bar_w - self._padding["right"])
                min_x = screen_x + self._padding["left"]
                if x < min_x:
                    x = min_x
            else:
                x = int(screen_x + self._padding["left"])
                max_x = screen_x + screen_w - bar_w - self._padding["right"]
                if x > max_x:
                    x = max_x

            if self._alignment["position"] == "bottom":
                y = int(screen_y + screen_h - bar_h - self._padding["bottom"])
            else:
                y = int(screen_y + self._padding["top"])

        return x, y

    def position_bar(self, init=False) -> None:
        screen_width = self._target_screen.geometry().width()
        screen_height = self._target_screen.geometry().height()

        if self._is_auto_width:
            if self._bar_frame.layout() is not None:
                bar_width = self._auto_width_manager.update() if self._auto_width_manager else 0
            else:
                bar_width = 0
        else:
            bar_width = self._resolve_dimension(self._dimensions["width"], screen_width)

        bar_height = self._resolve_dimension(self._dimensions["height"], screen_height)

        available_width = screen_width - self._padding["left"] - self._padding["right"]
        available_height = screen_height - self._padding["top"] - self._padding["bottom"]
        bar_width = min(bar_width, available_width)
        bar_height = min(bar_height, available_height)

        bar_x, bar_y = self.bar_pos(bar_width, bar_height, screen_width, screen_height)

        self.setGeometry(bar_x, bar_y, bar_width, bar_height)
        self._bar_frame.setGeometry(0, 0, bar_width, bar_height)

    def _resolve_dimension(self, value: str | int, available: int) -> int:
        if isinstance(value, int):
            return value
        if value == "auto":
            return 0
        if is_valid_percentage_str(str(value)):
            return int(available * percent_to_float(value))
        return 0

    def _format_label_text_for_orientation(self, text: str, label: QLabel) -> str:
        if not self._is_vertical:
            return text.replace("\n", "")

        class_name = str(label.property("class") or "")
        if "icon" in class_name:
            return text

        parts = [part.strip() for part in text.splitlines()]
        parts = [part for part in parts if part]
        if not parts:
            return text

        vertical_parts = []
        for part in parts:
            vertical_parts.append("\n".join(ch for ch in part if ch != " "))
        return "\n\n".join(vertical_parts)

    def _set_box_layout_direction(self, layout: QBoxLayout | None) -> None:
        if layout is None:
            return

        direction = QBoxLayout.Direction.TopToBottom if self._is_vertical else QBoxLayout.Direction.LeftToRight
        if layout.direction() != direction:
            layout.setDirection(direction)

    def _configure_widget_orientation(self, widget: QWidget) -> None:
        max_label_width = max(
            12,
            self._resolve_dimension(self._dimensions["width"], self._target_screen.geometry().width())
            - self._padding["left"]
            - self._padding["right"]
            - 10,
        )
        self._set_box_layout_direction(getattr(widget, "_widget_container_layout", None))
        self._set_box_layout_direction(getattr(widget, "workspace_container_layout", None))

        for child in widget.findChildren(QWidget):
            self._set_box_layout_direction(getattr(child, "_widget_container_layout", None))
            self._set_box_layout_direction(getattr(child, "button_layout", None))

        for label in widget.findChildren(QLabel):
            class_name = str(label.property("class") or "")
            if "label" not in class_name or "icon" in class_name:
                continue

            if not hasattr(label, "_yasb_original_set_text"):
                label._yasb_original_set_text = label.setText

                def orientation_set_text(text: str, _label=label, _bar=self):
                    _label._yasb_original_set_text(_bar._format_label_text_for_orientation(text, _label))

                label.setText = orientation_set_text

            label.setWordWrap(self._is_vertical)
            if self._is_vertical:
                label.setMaximumWidth(max_label_width)
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            else:
                label.setMaximumWidth(16777215)

            current_text = label.text()
            label._yasb_original_set_text(self._format_label_text_for_orientation(current_text, label))

    def _add_widgets(self, widgets: dict[str, list] = None):
        bar_layout = QGridLayout()
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(0)
        if self._is_vertical:
            bar_layout.setRowStretch(1, 1)
        else:
            bar_layout.setColumnStretch(1, 1)

        for index, layout_type in enumerate(["left", "center", "right"]):
            config = self.config.layouts.model_dump()[layout_type]
            layout = QVBoxLayout() if self._is_vertical else QHBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            layout_container = QFrame()
            layout_container.setProperty("class", f"container container-{layout_type}")

            # Add widgets
            if layout_type in widgets:
                for widget in widgets[layout_type]:
                    widget.parent_layout_type = layout_type
                    widget.bar_id = self.bar_id
                    widget.monitor_hwnd = self.monitor_hwnd
                    self._configure_widget_orientation(widget)
                    layout.addWidget(widget, 0)

            if config["alignment"] == "left" and config["stretch"]:
                layout.addStretch(1)

            elif config["alignment"] == "right" and config["stretch"]:
                layout.insertStretch(0, 1)

            elif config["alignment"] == "center" and config["stretch"]:
                layout.insertStretch(0, 1)
                layout.addStretch(1)

            layout_container.setLayout(layout)
            if self._is_vertical:
                bar_layout.addWidget(layout_container, index, 0)
            else:
                bar_layout.addWidget(layout_container, 0, index)

        self._bar_frame.setLayout(bar_layout)

    def show_bar(self):
        if self._animation_manager:
            self._animation_manager.show_bar()

    def hide_bar(self):
        if self._animation_manager:
            self._animation_manager.hide_bar()

    def showEvent(self, event):
        super().showEvent(event)
        if self._animation.get("enabled", False) and self._animation_manager:
            # Use fade on initial show to avoid DWM blur/shadow flash with slide
            if getattr(self, "_initial_show", False):
                self._initial_show = False
                self._animation_manager._start_fade(True)
            else:
                self.show_bar()

    def closeEvent(self, event):
        if self._hide_on_fullscreen and self.app_bar_manager:
            AppBarManager().unregister_bar(int(self.winId()))

        if self._maximized_watcher:
            self._maximized_watcher.cleanup()
        if self._autohide_manager:
            self._autohide_manager.cleanup()
        if self._animation_manager:
            self._animation_manager.cleanup()
        self.try_remove_app_bar()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.PaletteChange:
            if self._os_theme_manager:
                self._os_theme_manager.update_theme_class()
        super().changeEvent(event)

    def eventFilter(self, obj, event):
        if (
            self._is_auto_width
            and self._auto_width_manager
            and obj == self._bar_frame
            and event.type() == QEvent.Type.LayoutRequest
        ):
            previous_width = self._auto_width_manager._current_auto_width
            new_width = self._auto_width_manager.update()
            if new_width != previous_width:
                self._auto_width_manager.apply(new_width)

        return super().eventFilter(obj, event)

    def hide(self):
        if getattr(self, "_skip_animation", False):
            super().hide()
        elif self.isVisible() and self._animation.get("enabled") and self._animation_manager:
            self._animation_manager.hide_bar()
        else:
            super().hide()

    def contextMenuEvent(self, event):
        """Handle right-click context menu"""
        if not self._context_menu:
            return

        widget_at_pos = self.childAt(event.pos())
        # If the click is on a widget, ignore the context menu
        if widget_at_pos and widget_at_pos != self._bar_frame and widget_at_pos != self:
            parent_widget = widget_at_pos
            while parent_widget and parent_widget != self:
                if hasattr(parent_widget, "parent_layout_type"):
                    event.ignore()
                    return
                parent_widget = parent_widget.parent()

        BarContextMenu(
            parent=self,
            bar_name=self._bar_name,
            widgets=self._widgets,
            widget_config_map=self._widget_config_map,
            autohide_bar=self._autohide_bar,
        ).show(event.pos())
