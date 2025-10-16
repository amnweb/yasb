import logging
import re
from contextlib import suppress
from typing import Literal

import win32gui
from PIL import Image
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QCursor, QImage, QMouseEvent, QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from core.event_enums import KomorebiEvent
from core.event_service import EventService
from core.utils.utilities import add_shadow, refresh_widget_style
from core.utils.widgets.komorebi.client import KomorebiClient
from core.utils.win32.app_icons import get_window_icon
from core.utils.win32.utilities import get_monitor_hwnd
from core.utils.win32.window_actions import close_application
from core.validation.widgets.komorebi.stack import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget
from settings import DEBUG

try:
    from core.utils.widgets.komorebi.event_listener import KomorebiEventListener
except ImportError:
    KomorebiEventListener = None
    logging.warning("Failed to load Komorebi Event Listener")

WindowStatus = Literal["INACTIVE", "ACTIVE"]
WINDOW_STATUS_INACTIVE: WindowStatus = "INACTIVE"
WINDOW_STATUS_ACTIVE: WindowStatus = "ACTIVE"


class WindowButton(QFrame):
    def __init__(
        self,
        window_index: int,
        parent_widget: "StackWidget",
        label: str = None,
        active_label: str = None,
        animation: bool = False,
    ):
        super().__init__()
        self._animation_initialized = False
        self.komorebic = KomorebiClient()
        self.window_index = window_index
        self.parent_widget = parent_widget
        self.status = WINDOW_STATUS_INACTIVE
        self.setProperty("class", "window")
        self.default_label = label
        self.active_label = active_label if active_label else self.default_label
        self._animation = animation
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.button_layout = QHBoxLayout(self)
        self.button_layout.setContentsMargins(0, 0, 0, 0)
        self.button_layout.setSpacing(0)
        add_shadow(self, self.parent_widget._btn_shadow)

        self.icon = None
        self.icon_label = QLabel()
        self.icon_label.setProperty("class", "icon")
        self.button_layout.addWidget(self.icon_label)
        add_shadow(self.icon_label, self.parent_widget._label_shadow)
        if self.parent_widget._show_icons == "never" or (
            self.parent_widget._show_icons == "focused" and self.status == WINDOW_STATUS_INACTIVE
        ):
            self.icon_label.hide()

        self.text_label = QLabel(self.default_label)
        self.text_label.setProperty("class", "label")
        self.button_layout.addWidget(self.text_label)
        add_shadow(self.text_label, self.parent_widget._label_shadow)

        self.hide()
        self.update_icon()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.focus_stack_window()
        elif event.button() == Qt.MouseButton.MiddleButton:
            self.close_stack_window()

    def update_visible_buttons(self):
        visible_buttons = [btn for btn in self.parent_widget._window_buttons if btn.isVisible()]
        for index, button in enumerate(visible_buttons):
            current_class = button.property("class")
            new_class = " ".join([cls for cls in current_class.split() if not cls.startswith("button-")])
            new_class = f"{new_class} button-{index + 1}"
            button.setProperty("class", new_class)
            refresh_widget_style(button)

    def update_and_redraw(self, status: WindowStatus):
        self.status = status
        self.setProperty("class", f"window {status.lower()}")
        if status == WINDOW_STATUS_ACTIVE:
            self.text_label.setText(self.active_label)
        else:
            self.text_label.setText(self.default_label)
        refresh_widget_style(self)

        if self.parent_widget._show_icons == "focused":
            if self.status == WINDOW_STATUS_ACTIVE:
                self.icon_label.show()
            else:
                self.icon_label.hide()

    def update_icon(self, pixmap: QPixmap = None, ignore_cache: bool = False):
        if self.parent_widget._show_icons != "never":
            self.icon = pixmap if pixmap else self.parent_widget._get_app_icon(self.window_index, ignore_cache)
            if self.icon:
                self.icon_label.setPixmap(self.icon)

    def focus_stack_window(self):
        try:
            self.komorebic.focus_stack_window(self.window_index)
            if self._animation:
                pass
                # self.animate_buttons()
        except Exception:
            logging.exception(f"Failed to focus stack window at index {self.window_index}")

    def close_stack_window(self):
        hwnd = self.parent_widget._komorebi_windows[self.window_index]["hwnd"]
        close_application(hwnd)

    def animate_buttons(self, duration=200, step=30):
        # Store the initial width if not already stored (to enable reverse animations)
        if not hasattr(self, "_initial_width"):
            self._initial_width = self.width()

        self._current_width = self.width()
        target_width = self.sizeHint().width()

        step_duration = int(duration / step)
        width_increment = (target_width - self._current_width) / step
        self._current_step = 0

        def update_width():
            if self._current_step < step:
                self._current_width += width_increment
                self.setFixedWidth(int(self._current_width))
                self._current_step += 1
            else:
                # Animation done: stop timer and set to target exactly
                self._animation_timer.stop()
                self.setFixedWidth(target_width)

        # Stop any existing timer before starting a new one to prevent conflicts
        if hasattr(self, "_animation_timer") and self._animation_timer.isActive():
            self._animation_timer.stop()

        # Parent the timer to the widget to avoid potential memory leaks
        self._animation_timer = QTimer(self)
        self._animation_timer.timeout.connect(update_width)
        self._animation_timer.start(step_duration)


class StackWidget(BaseWidget):
    k_signal_connect = pyqtSignal(dict)
    k_signal_update = pyqtSignal(dict, dict)
    k_signal_disconnect = pyqtSignal()
    validation_schema = VALIDATION_SCHEMA
    event_listener = KomorebiEventListener

    def __init__(
        self,
        label_offline: str,
        label_window: str,
        label_window_active: str,
        label_no_window: str,
        label_zero_index: bool,
        show_icons: str,
        icon_size: int,
        max_length: int,
        max_length_active: int,
        max_length_overall: int,
        max_length_ellipsis: str,
        hide_if_offline: bool,
        show_only_stack: bool,
        container_padding: dict,
        animation: bool,
        enable_scroll_switching: bool,
        reverse_scroll_direction: bool,
        rewrite: list[dict] = None,
        btn_shadow: dict = None,
        label_shadow: dict = None,
        container_shadow: dict = None,
    ):
        super().__init__(class_name="komorebi-stack")
        self._event_service = EventService()
        self._komorebic = KomorebiClient()
        self._label_window = label_window
        self._label_window_active = label_window_active
        self._label_zero_index = label_zero_index
        self._show_icons = show_icons
        self._icon_size = icon_size
        self._max_length = max_length
        self._max_length_active = max_length_active
        self._max_length_overall = max_length_overall
        self._max_length_ellipsis = max_length_ellipsis
        self._hide_if_offline = hide_if_offline
        self._show_only_stack = show_only_stack
        self._padding = container_padding
        self._animation = animation
        self._rewrite_rules = rewrite
        self._btn_shadow = btn_shadow
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow
        self._komorebi_screen = None
        self._curr_focus_container = None
        self._prev_focus_container = None
        self._komorebi_windows = []
        self._prev_workspace_index = None
        self._curr_workspace_index = None
        self._prev_window_index = None
        self._curr_window_index = None
        self._prev_num_windows = None
        self._curr_num_windows = None
        self._prev_workspace_layer = None
        self._curr_workspace_layer = None
        self._window_buttons: list[WindowButton] = []
        self._window_focus_events = [
            KomorebiEvent.CycleStack.value,
            KomorebiEvent.FocusStackWindow.value,
        ]
        self._reset_buttons_events = [
            KomorebiEvent.ReloadConfiguration.value,
            KomorebiEvent.WatchConfiguration.value,
            KomorebiEvent.StackWindow.value,
            KomorebiEvent.UnstackWindow.value,
        ]
        # Disable default mouse event handling inherited from BaseWidget
        self.mousePressEvent = None
        if self._hide_if_offline:
            self.hide()
        # Status text shown when komorebi state can't be retrieved
        self._offline_text = QLabel()
        self._offline_text.setText(label_offline)
        add_shadow(self._offline_text, self._label_shadow)
        self._offline_text.setProperty("class", "offline-status")
        # Status text shown when there is no active window
        self._no_window_text = QLabel()
        self._no_window_text.setText(label_no_window)
        add_shadow(self._no_window_text, self._label_shadow)
        self._no_window_text.setProperty("class", "no-window")
        self._rewrite_rules = rewrite
        # Construct container which holds windows buttons
        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(
            self._padding["left"], self._padding["top"], self._padding["right"], self._padding["bottom"]
        )
        self._widget_container_layout.addWidget(self._offline_text)
        self._widget_container_layout.addWidget(self._no_window_text)
        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self._container_shadow)
        self._widget_container.hide()
        self.widget_layout.addWidget(self._offline_text)
        self.widget_layout.addWidget(self._no_window_text)
        self.widget_layout.addWidget(self._widget_container)
        self._enable_scroll_switching = enable_scroll_switching
        self._reverse_scroll_direction = reverse_scroll_direction
        self._icon_cache = dict()
        self.dpi = None

        self._hide_no_window_text()
        self._register_signals_and_events()

    def _register_signals_and_events(self):
        self.k_signal_connect.connect(self._on_komorebi_connect_event)
        self.k_signal_update.connect(self._on_komorebi_update_event)
        self.k_signal_disconnect.connect(self._on_komorebi_disconnect_event)
        self._event_service.register_event(KomorebiEvent.KomorebiConnect, self.k_signal_connect)
        self._event_service.register_event(KomorebiEvent.KomorebiDisconnect, self.k_signal_disconnect)
        self._event_service.register_event(KomorebiEvent.KomorebiUpdate, self.k_signal_update)
        # Unregister on widget destruction to prevent late emits
        try:
            self.destroyed.connect(self._on_destroyed)  # type: ignore[attr-defined]
        except Exception:
            pass

    def _on_destroyed(self, *args):
        try:
            self._event_service.unregister_event(KomorebiEvent.KomorebiConnect, self.k_signal_connect)
            self._event_service.unregister_event(KomorebiEvent.KomorebiDisconnect, self.k_signal_disconnect)
            self._event_service.unregister_event(KomorebiEvent.KomorebiUpdate, self.k_signal_update)
        except Exception:
            pass

    def _rewrite_filter(self, text: str) -> str:
        """Applies rewrite rules to the given text."""
        if not text or not self._rewrite_rules:
            return text

        result = text
        for rule in self._rewrite_rules:
            pattern, replacement, case = (rule.get(k, "") for k in ("pattern", "replacement", "case"))

            if not pattern or not replacement:
                continue

            try:
                result, count = re.subn(pattern, replacement, result)
                if count > 0:
                    transform = getattr(result, case, None)
                    if callable(transform):
                        result = transform()
            except re.error as e:
                logging.warning(f"Invalid regex pattern '{pattern}': {e}")
                continue

        return result

    def _reset(self):
        self._komorebi_state = None
        self._komorebi_screen = None
        self._curr_focus_container = None
        self._prev_focus_container = None
        self._komorebi_windows = []
        self._prev_workspace_index = None
        self._curr_workspace_index = None
        self._prev_window_index = None
        self._curr_window_index = None
        self._prev_num_windows = None
        self._curr_num_windows = None
        self._prev_workspace_layer = None
        self._curr_workspace_layer = None
        self._window_buttons = []
        self._clear_container_layout()

    def _on_komorebi_connect_event(self, state: dict) -> None:
        self._reset()
        self._hide_offline_status()
        if self._update_komorebi_state(state):
            self._add_or_update_buttons()
        if self._hide_if_offline:
            self.show()

    def _on_komorebi_disconnect_event(self) -> None:
        self._show_offline_status()
        if self._hide_if_offline:
            self.hide()

    def _on_komorebi_update_event(self, event: dict, state: dict) -> None:
        if self._update_komorebi_state(state):
            self._hide_no_window_text()

            if event["type"] in self._window_focus_events or self._has_active_window_index_changed():
                try:
                    prev_window_button = self._window_buttons[self._prev_window_index]
                    self._update_button_status(prev_window_button)
                    new_window_button = self._window_buttons[self._curr_window_index]
                    self._update_button_status(new_window_button)
                    if (
                        self._komorebi_windows[self._curr_window_index]["exe"] == "ApplicationFrameHost.exe"
                        and not new_window_button.icon
                    ):
                        new_window_button.update_icon(ignore_cache=True)
                except (IndexError, TypeError):
                    pass

            elif (
                event["type"] in self._reset_buttons_events
                or self._has_active_container_changed()
                or self._has_active_workspace_index_changed()
                or self._prev_num_windows != self._curr_num_windows
                or self._prev_workspace_layer != self._curr_workspace_layer
            ):
                while len(self._window_buttons) > len(self._komorebi_windows):
                    self._try_remove_window_button(self._window_buttons[-1].window_index)
                self._add_or_update_buttons()

            elif self._curr_workspace_layer == "Floating" and event["type"] == KomorebiEvent.FocusChange.value:
                for window_btn in self._window_buttons:
                    self._update_button_label(window_btn)
                    window_btn.update_icon()

            elif event["type"] == KomorebiEvent.TitleUpdate.value:
                hwnd = event["content"][1]["hwnd"]
                for window_btn in self._window_buttons:
                    window_btn_hwnd = self._komorebi_windows[window_btn.window_index]["hwnd"]
                    if window_btn_hwnd == hwnd:
                        self._update_button_label(window_btn)
                        window_btn.update_icon(ignore_cache=True)

            if self._show_only_stack and len(self._window_buttons) <= 1:
                self.hide()
            else:
                self.show()

        else:
            self._show_no_window_text()

    def _clear_container_layout(self):
        for i in reversed(range(self._widget_container_layout.count())):
            old_widget = self._widget_container_layout.itemAt(i).widget()
            self._widget_container_layout.removeWidget(old_widget)
            old_widget.setParent(None)

    def _update_komorebi_state(self, komorebi_state: dict) -> bool:
        try:
            self._screen_hwnd = get_monitor_hwnd(int(QWidget.winId(self)))
            self._komorebi_state = komorebi_state
            if self._komorebi_state:
                self._komorebi_screen = self._komorebic.get_screen_by_hwnd(self._komorebi_state, self._screen_hwnd)
                focused_workspace = self._komorebic.get_focused_workspace(self._komorebi_screen)
                focused_container = self._komorebic.get_focused_container(focused_workspace, get_monocle=True)
                self._komorebi_windows = []

                if focused_workspace:
                    self._prev_workspace_index = self._curr_workspace_index
                    self._curr_workspace_index = focused_workspace["index"]
                if focused_container:
                    self._prev_focus_container = self._curr_focus_container
                    self._curr_focus_container = focused_container
                    self._komorebi_windows = self._komorebic.get_windows(focused_container)
                    focused_window = self._komorebic.get_focused_window(focused_container)
                    if focused_window:
                        self._prev_window_index = self._curr_window_index
                        self._curr_window_index = focused_window["index"]

                self._prev_workspace_layer = self._curr_workspace_layer
                self._curr_workspace_layer = focused_workspace["layer"]
                if focused_workspace["layer"] == "Floating":
                    floating_windows = self._komorebic.get_floating_windows(focused_workspace)
                    for window in floating_windows:
                        if window["hwnd"] == win32gui.GetForegroundWindow():
                            self._komorebi_windows = [window]
                self._prev_num_windows = self._curr_num_windows
                self._curr_num_windows = len(self._komorebi_windows)

                if len(self._komorebi_windows) == 0:
                    return False
                else:
                    return True
        except TypeError:
            return False

    def _has_active_window_index_changed(self):
        return (
            self._prev_window_index != self._curr_window_index
            and not self._has_active_container_changed()
            and not self._has_active_workspace_index_changed()
        )

    def _has_active_container_changed(self):
        return (
            self._prev_focus_container != self._curr_focus_container and not self._has_active_workspace_index_changed()
        )

    def _has_active_workspace_index_changed(self):
        return self._prev_workspace_index != self._curr_workspace_index

    def _get_window_new_status(self, window) -> WindowStatus:
        if len(self._window_buttons) == 1:
            return WINDOW_STATUS_ACTIVE
        if self._curr_window_index == window["index"]:
            return WINDOW_STATUS_ACTIVE
        else:
            return WINDOW_STATUS_INACTIVE

    def _update_button_status(self, window_btn: WindowButton) -> None:
        window_index = window_btn.window_index
        window = self._komorebi_windows[window_index]
        window_status = self._get_window_new_status(window)
        window_btn.show()
        if window_btn.status != window_status:
            window_btn.update_and_redraw(window_status)
            if self._animation and window_btn._animation_initialized:
                window_btn.animate_buttons()
        window_btn.update_visible_buttons()
        window_btn._animation_initialized = True

    def _update_button_label(self, window_btn: WindowButton) -> None:
        window_index = window_btn.window_index
        default_label, active_label = self._get_window_label(window_index)
        if window_btn.default_label != default_label or window_btn.active_label != active_label:
            window_btn.default_label = default_label
            window_btn.active_label = active_label if active_label else default_label
            window_btn.update_and_redraw(window_btn.status)
            if self._animation and window_btn._animation_initialized:
                window_btn.animate_buttons()
        window_btn._animation_initialized = True

    def _add_or_update_buttons(self) -> None:
        buttons_added = False
        for window_index, _ in enumerate(self._komorebi_windows):
            try:
                button = self._window_buttons[window_index]
                self._update_button_status(button)
                self._update_button_label(button)
                button.update_icon()
            except IndexError:
                button = self._try_add_window_button(window_index)
                buttons_added = True
        if buttons_added:
            self._window_buttons.sort(key=lambda btn: btn.window_index)
            self._clear_container_layout()
            for window_btn in self._window_buttons:
                self._widget_container_layout.addWidget(window_btn)
                self._update_button_status(window_btn)

    def _get_window_label(self, window_index):
        window = self._komorebi_windows[window_index]
        w_index = window_index if self._label_zero_index else window_index + 1

        # Apply rewrite filter to title and process name
        title = self._rewrite_filter(window["title"])
        process_name = self._rewrite_filter(window["exe"])

        default_label = self._label_window.format(index=w_index, title=title, process=process_name, hwnd=window["hwnd"])
        active_label = self._label_window_active.format(
            index=w_index, title=title, process=process_name, hwnd=window["hwnd"]
        )
        if self._max_length_overall:
            calculated_max_length = self._max_length_overall // max(1, len(self._komorebi_windows) - 1)
            if len(default_label) > calculated_max_length:
                default_label = default_label[:calculated_max_length] + self._max_length_ellipsis
        elif self._max_length and len(default_label) > self._max_length:
            default_label = default_label[: self._max_length] + self._max_length_ellipsis
        if self._max_length_active and len(active_label) > self._max_length_active:
            active_label = active_label[: self._max_length_active] + self._max_length_ellipsis
        return default_label, active_label

    def _try_add_window_button(self, window_index: int) -> WindowButton:
        window_button_indexes = [ws_btn.window_index for ws_btn in self._window_buttons]
        if window_index not in window_button_indexes:
            default_label, active_label = self._get_window_label(window_index)
            window_btn = WindowButton(window_index, self, default_label, active_label, self._animation)
            self._window_buttons.append(window_btn)
            return window_btn

    def _try_remove_window_button(self, window_index: int) -> None:
        with suppress(IndexError):
            self._window_buttons[window_index].setParent(None)
            self._widget_container_layout.removeWidget(self._window_buttons[window_index])
            self._window_buttons.pop(window_index)

    def _show_offline_status(self):
        self._offline_text.show()
        self._widget_container.hide()

    def _hide_offline_status(self):
        self._offline_text.hide()
        self._widget_container.show()

    def _show_no_window_text(self):
        if self._no_window_text.text():
            self._no_window_text.show()
            self._widget_container.hide()
        else:
            self.hide()

    def _hide_no_window_text(self):
        self._no_window_text.hide()
        self._widget_container.show()

    def wheelEvent(self, event):
        """Handle mouse wheel events to switch windows."""
        if not self._enable_scroll_switching or not self._komorebi_screen:
            return

        delta = event.angleDelta().y()
        # Determine direction (consider reverse_scroll_direction setting)
        direction = -1 if (delta > 0) != self._reverse_scroll_direction else 1

        windows = self._komorebic.get_windows(self._curr_focus_container)
        if not windows:
            return

        current_idx = self._curr_window_index
        num_windows = len(windows)
        next_idx = (current_idx + direction) % num_windows
        try:
            self._komorebic.focus_stack_window(next_idx)
        except Exception:
            logging.exception(f"Failed to switch to stack window at index {next_idx}")

    def _get_app_icon(self, window_index: int, ignore_cache: bool) -> QPixmap | None:
        try:
            hwnd = None
            hwnd = self._komorebi_windows[window_index]["hwnd"]
            self.dpi = self.screen().devicePixelRatio()
            cache_key = (hwnd, self.dpi)

            if cache_key in self._icon_cache and not ignore_cache:
                icon_img = self._icon_cache[cache_key]
            else:
                icon_img = get_window_icon(hwnd)
                if icon_img:
                    icon_img = icon_img.resize(
                        (int(self._icon_size * self.dpi), int(self._icon_size * self.dpi)), Image.LANCZOS
                    ).convert("RGBA")
                    self._icon_cache[cache_key] = icon_img
            if not icon_img:
                return None
            if icon_img:
                qimage = QImage(icon_img.tobytes(), icon_img.width, icon_img.height, QImage.Format.Format_RGBA8888)
                pixmap = QPixmap.fromImage(qimage)
                pixmap.setDevicePixelRatio(self.dpi)
                try:
                    self._window_buttons[window_index].update_icon(pixmap=pixmap)
                except IndexError:
                    return pixmap

        except Exception:
            if DEBUG:
                logging.exception(f"Failed to get icons for window with HWND {hwnd if hwnd is not None else 'unknown'}")
            return None
