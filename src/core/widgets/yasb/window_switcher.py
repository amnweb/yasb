import logging
from ctypes import byref, wintypes
from typing import override

from PyQt6.QtCore import QEvent, QObject, QPoint, QRect, Qt, QTimer
from PyQt6.QtGui import QKeyEvent, QMouseEvent, QPixmap, QScreen, QShowEvent, QWheelEvent
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.utils.icons.service import IconService, WindowIcon
from core.utils.qobject import is_valid_qobject
from core.utils.utilities import ElidedLabel, PopupWidget, refresh_widget_style
from core.utils.win32.bindings.dwmapi import (
    DwmQueryThumbnailSourceSize,
    DwmRegisterThumbnail,
    DwmUnregisterThumbnail,
    DwmUpdateThumbnailProperties,
)
from core.utils.win32.bindings.user32 import GetWindowText, IsIconic, IsWindow, enum_windows
from core.utils.win32.constants import DWM_TNP_RECTDESTINATION, DWM_TNP_VISIBLE
from core.utils.win32.structs import DWM_THUMBNAIL_PROPERTIES, RECT, SIZE
from core.utils.win32.utils import find_focused_screen
from core.utils.win32.window_actions import (
    close_application,
    is_owner_root_active,
    resolve_base_and_focus,
    restore_window,
    set_foreground,
    show_window,
)
from core.validation.widgets.yasb.window_switcher import WindowSwitcherConfig
from core.widgets.base import BaseWidget
from core.widgets.services.taskbar.application_window import ApplicationWindow
from core.widgets.services.taskbar.window_manager import TaskbarWindowManager, connect_taskbar

logger = logging.getLogger("window_switcher")


class _SwitcherItem(QFrame):
    def __init__(self, parent: QWidget, hwnd: int, title: str) -> None:
        super().__init__(parent)
        self.hwnd = hwnd
        self.title = title
        self.icon_label: QLabel | None = None
        self.thumbnail: QFrame | None = None
        self.thumb = wintypes.HANDLE(0)

    def release_thumbnail(self):
        if self.thumb.value:
            DwmUnregisterThumbnail(self.thumb)
            self.thumb = wintypes.HANDLE(0)


class WindowSwitcherWidget(BaseWidget):
    validation_schema = WindowSwitcherConfig
    PREVIEW_ICON_SIZE = 16

    def __init__(self, config: WindowSwitcherConfig):
        super().__init__(class_name="window-switcher-widget")
        self.config = config

        self._init_container()
        self.build_widget_label(self.config.label, self.config.label_alt)
        self.register_callback("toggle_window_switcher", self._toggle_window_switcher)

        self.callback_left = self.config.callbacks.on_left
        self.callback_right = self.config.callbacks.on_right
        self.callback_middle = self.config.callbacks.on_middle

        self._popup: PopupWidget | None = None
        self._scroll_area: QScrollArea | None = None
        self._btn_w = 0
        self._btn_h = 0
        self._popup_height = 0
        self._popup_extra_w = 0
        self._icons = IconService.instance()
        self._icons.icons_changed.connect(self._refresh_icons)
        self.buttons_list: list[_SwitcherItem] = []
        self.active_title_label: QLabel | None = None
        self.current_focus_index = -1
        self._icon_size = self.PREVIEW_ICON_SIZE if self.config.preview.enabled else self.config.icon_size
        self._hold_modifiers = Qt.KeyboardModifier.NoModifier

        # Tell TaskbarWindowManager to track cloaked apps globally so we can see them
        self._show_only_visible = False

        self._task_manager: TaskbarWindowManager | None = None

    @override
    def showEvent(self, a0: QShowEvent | None) -> None:
        super().showEvent(a0)
        # connect_taskbar() calls winId() on self.window(). Before the widget is in the bar,
        # that is the widget itself, and Qt would make it and its siblings native windows.
        if self._task_manager is None:
            try:
                self._task_manager = connect_taskbar(self)
            except Exception as e:
                logger.error("Failed to connect to the task manager: %s", e)

    def _toggle_window_switcher(self):
        if self._popup and is_valid_qobject(self._popup) and self._popup.isVisible():
            if self._hold_modifiers and self.buttons_list:
                self.set_focused_button((self.current_focus_index + 1) % len(self.buttons_list))
            else:
                self._popup.hide_animated()
            return

        self._hold_modifiers = QApplication.queryKeyboardModifiers()
        if self._show_popup() and self._hold_modifiers:
            # A quick tap can release the modifiers before the popup takes focus and sees the key release
            QTimer.singleShot(0, self._switch_if_released)

    def _switch_if_released(self):
        if not self._hold_modifiers or QApplication.queryKeyboardModifiers() & self._hold_modifiers:
            return
        if 0 <= self.current_focus_index < len(self.buttons_list):
            self._switch_to_window(self.buttons_list[self.current_focus_index].hwnd)

    def _show_popup(self) -> bool:
        taskbar_windows = self._get_sorted_windows()
        if not taskbar_windows:
            return False

        if self._popup and is_valid_qobject(self._popup):
            self._popup.deleteLater()

        popup_cfg = self.config.popup
        self._popup = PopupWidget(
            self,
            popup_cfg.blur,
            popup_cfg.round_corners,
            popup_cfg.round_corners_type,
            popup_cfg.border_color,
            popup_cfg.dark_mode,
            animation=0,
        )
        self._popup.installEventFilter(self)
        self._popup.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._current_screen = self._get_target_screen()
        self._current_dpr = self._current_screen.devicePixelRatio()

        self._build_overlay_popup(taskbar_windows)

        # Start on the window behind the active one. Checked before show() takes the foreground.
        index = 1 if len(self.buttons_list) > 1 and is_owner_root_active(self.buttons_list[0].hwnd) else 0

        self._popup.show()
        self._popup.setFocus()
        self.current_focus_index = -1
        self.set_focused_button(index)
        self._update_thumbnails()
        return True

    def _get_target_screen(self) -> QScreen:
        screen_mode = "active"
        for kb in self.config.keybindings:
            if kb.action == "toggle_window_switcher":
                screen_mode = kb.screen
                break
        if screen_mode == "cursor":
            screen_name = find_focused_screen(follow_mouse=True, follow_window=False)
        elif screen_mode == "active":
            screen_name = find_focused_screen(follow_mouse=False, follow_window=True)
        elif screen_mode == "primary":
            return QApplication.primaryScreen() or QApplication.screens()[0]
        else:
            return self.screen() or QApplication.primaryScreen() or QApplication.screens()[0]
        if screen_name:
            for s in QApplication.screens():
                if s.name() == screen_name:
                    return s
        return self.screen() or QApplication.primaryScreen() or QApplication.screens()[0]

    def _get_sorted_windows(self) -> list[ApplicationWindow]:
        if self._task_manager is None:
            return []
        windows = list(self._task_manager.get_windows().values())
        taskbar_windows = [w for w in windows if w.is_taskbar_window()]
        z_order = enum_windows()
        z_order_map = {hwnd: i for i, hwnd in enumerate(z_order)}
        taskbar_windows.sort(key=lambda w: z_order_map.get(w.hwnd, 99999))
        return taskbar_windows

    def _build_overlay_popup(self, taskbar_windows: list[ApplicationWindow]):
        icon_size = self._icon_size

        main_layout = QVBoxLayout(self._popup)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        wrapper = QFrame()
        wrapper.setProperty("class", "window-switcher-popup")
        main_layout.addWidget(wrapper)

        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setSpacing(0)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(False)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setObjectName("ws_scroll")
        viewport = self._scroll_area.viewport()
        if viewport is not None:
            viewport.setObjectName("ws_viewport")
        scroll_bar = self._scroll_area.horizontalScrollBar()
        if self.config.preview.enabled and scroll_bar is not None:
            scroll_bar.valueChanged.connect(self._update_thumbnails)

        container = QWidget()
        container.setObjectName("ws_container")
        container_layout = QHBoxLayout(container)
        container_layout.setSpacing(0)
        container_layout.setContentsMargins(0, 0, 0, 0)

        self.buttons_list = []
        for win in taskbar_windows:
            btn = _SwitcherItem(container, win.hwnd, GetWindowText(win.hwnd) or win.title or "")
            btn.setProperty("class", "item")
            btn_layout = QVBoxLayout(btn)
            btn_layout.setSpacing(0)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            icon_label = QLabel(btn)
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_label.setFixedSize(icon_size, icon_size)
            icon_pixmap = self._get_app_icon(win.hwnd)
            if icon_pixmap:
                icon_label.setPixmap(icon_pixmap)
            btn.icon_label = icon_label

            if self.config.preview.enabled:
                title_label = ElidedLabel(btn.title, btn)
                title_label.setProperty("class", "item-title")
                header = QHBoxLayout()
                header.setSpacing(6)
                header.setContentsMargins(0, 0, 0, 6)
                header.addWidget(icon_label)
                header.addWidget(title_label, 1)
                btn_layout.addLayout(header)

                btn.thumbnail = QFrame(btn)
                btn.thumbnail.setFixedSize(self.config.preview.width, self.config.preview.width * 9 // 16)
                btn_layout.addWidget(btn.thumbnail)
            else:
                btn_layout.addWidget(icon_label)

            btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            btn.installEventFilter(self)
            self.buttons_list.append(btn)
            container_layout.addWidget(btn)

        self._scroll_area.setWidget(container)
        self._scroll_area.setStyleSheet(
            "#ws_scroll, #ws_viewport, #ws_container { background: transparent; border: none; }"
        )

        wrapper_layout.addWidget(self._scroll_area)

        self.active_title_label = None
        if self.config.show_title:
            self.active_title_label = QLabel()
            self.active_title_label.setProperty("class", "title")
            self.active_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.active_title_label.setText(" ")
            wrapper_layout.addWidget(self.active_title_label)

        if self.buttons_list:
            self.buttons_list[0].ensurePolished()
            if (btn_layout := self.buttons_list[0].layout()) is not None:
                btn_layout.activate()
            hint = self.buttons_list[0].sizeHint()
            self._btn_w = max(hint.width(), icon_size)
            self._btn_h = max(hint.height(), icon_size)
        else:
            self._btn_w = self._btn_h = icon_size

        self._update_popup_geometry(initial=True)

    def _get_app_icon(self, hwnd: int) -> QPixmap | None:
        if self._icon_size <= 0:
            return None
        return self._icons.get_icon(WindowIcon(hwnd), self._icon_size, self._current_dpr)

    def _refresh_icons(self) -> None:
        for btn in self.buttons_list:
            if btn.icon_label is None or not is_valid_qobject(btn.icon_label):
                continue
            pixmap = self._get_app_icon(btn.hwnd)
            if pixmap:
                btn.icon_label.setPixmap(pixmap)

    def _update_thumbnails(self):
        popup = self._popup
        if not self.config.preview.enabled or not popup or not is_valid_qobject(popup) or not popup.isVisible():
            return
        viewport = self._scroll_area.viewport() if self._scroll_area else None
        if viewport is None:
            return
        visible_area = QRect(viewport.mapTo(popup, QPoint(0, 0)), viewport.size())
        # DWM takes physical pixels relative to the popup window
        dpr = popup.devicePixelRatioF()
        for btn in self.buttons_list:
            if btn.thumbnail is None:
                continue
            if not btn.thumb.value and DwmRegisterThumbnail(int(popup.winId()), btn.hwnd, byref(btn.thumb)) != 0:
                continue
            area = QRect(btn.thumbnail.mapTo(popup, QPoint(0, 0)), btn.thumbnail.size())
            box_w, box_h = round(area.width() * dpr), round(area.height() * dpr)
            width, height = box_w, box_h
            source = SIZE(0, 0)
            if DwmQueryThumbnailSourceSize(btn.thumb, byref(source)) == 0 and source.cx > 0 and source.cy > 0:
                scale = min(box_w / source.cx, box_h / source.cy)
                width, height = round(source.cx * scale), round(source.cy * scale)
            left = round(area.x() * dpr) + (box_w - width) // 2
            top = round(area.y() * dpr) + (box_h - height) // 2

            props = DWM_THUMBNAIL_PROPERTIES()
            props.dwFlags = DWM_TNP_RECTDESTINATION | DWM_TNP_VISIBLE
            props.rcDestination = RECT(left, top, left + width, top + height)
            props.fVisible = visible_area.contains(area)
            DwmUpdateThumbnailProperties(btn.thumb, byref(props))

    def _switch_to_window(self, hwnd: int):
        self._hold_modifiers = Qt.KeyboardModifier.NoModifier
        if self._popup:
            self._popup.hide_animated()
        if not IsWindow(hwnd):
            return

        def _do_focus():
            try:
                base, focus_target = resolve_base_and_focus(hwnd)

                if IsIconic(base) or IsIconic(hwnd):
                    restore_window(base)
                    if base != hwnd:
                        restore_window(hwnd)
                else:
                    show_window(base)
                    if base != hwnd:
                        show_window(hwnd)

                set_foreground(base)
                target = focus_target or base
                QTimer.singleShot(0, lambda: set_foreground(target))

            except Exception:
                try:
                    if IsIconic(hwnd):
                        restore_window(hwnd)
                    else:
                        show_window(hwnd)
                except Exception as final_e:
                    logger.error("Failed to switch to window %s: %s", hwnd, final_e)

        QTimer.singleShot(0, _do_focus)

    def _close_window(self, hwnd: int):
        if not IsWindow(hwnd):
            return

        try:
            close_application(hwnd)
        except Exception as e:
            logger.error("Failed to close window %s: %s", hwnd, e)

        button = next((b for b in self.buttons_list if b.hwnd == hwnd), None)
        if button:
            index = self.buttons_list.index(button)
            self.buttons_list.remove(button)
            button.release_thumbnail()
            button.setParent(None)
            button.deleteLater()

            if not self.buttons_list:
                if self._popup is not None:
                    self._popup.hide_animated()
                return

            self.current_focus_index = -1
            self._update_popup_geometry()
            QTimer.singleShot(0, lambda: self.set_focused_button(min(index, len(self.buttons_list) - 1)))
            QTimer.singleShot(0, self._update_thumbnails)

    def _update_popup_geometry(self, initial: bool = False):
        if self._popup and self._scroll_area:
            screen_geometry = self._current_screen.geometry()
            # We will use max 90% of screen size
            max_allowed_width = screen_geometry.width() * 0.9

            if container := self._scroll_area.widget():
                container.setFixedSize(self._btn_w * len(self.buttons_list), self._btn_h)

            if initial:
                self._scroll_area.setFixedSize(self._btn_w, self._btn_h)
                size_hint = self._popup.sizeHint()
                self._popup_height = size_hint.height()
                self._popup_extra_w = size_hint.width() - self._btn_w

            available_w = max_allowed_width - self._popup_extra_w
            max_screen_apps = max(1, int(available_w // self._btn_w)) if self._btn_w > 0 else 1

            visible_apps = min(len(self.buttons_list), self.config.max_visible_apps, max_screen_apps)
            self._scroll_area.setFixedSize(self._btn_w * visible_apps, self._btn_h)

            popup_width = self._btn_w * visible_apps + self._popup_extra_w
            self._popup.setFixedSize(int(popup_width), self._popup_height)
            self._popup.move(
                int((screen_geometry.width() - popup_width) // 2 + screen_geometry.x()),
                int((screen_geometry.height() - self._popup_height) // 2 + screen_geometry.y()),
            )

    @override
    def eventFilter(self, a0: QObject | None, a1: QEvent | None) -> bool:
        if a1 is None:
            return super().eventFilter(a0, a1)
        if self.config.preview.enabled and a0 is self._popup and a1.type() == QEvent.Type.Hide:
            # DWM keeps a thumbnail registered even after its popup window is destroyed
            for btn in self.buttons_list:
                btn.release_thumbnail()
        if isinstance(a1, QWheelEvent):
            if self._scroll_area and self.buttons_list:
                step = self._btn_w * (-1 if a1.angleDelta().y() < 0 else 1)
                bar = self._scroll_area.horizontalScrollBar()
                if bar is not None:
                    bar.setValue(bar.value() - step)
            return True

        if isinstance(a0, _SwitcherItem) and a0 in self.buttons_list:
            if a1.type() == QEvent.Type.Enter:
                self.set_focused_button(self.buttons_list.index(a0), by_mouse=True)
            elif a1.type() == QEvent.Type.MouseButtonRelease and isinstance(a1, QMouseEvent):
                if a1.button() == Qt.MouseButton.LeftButton:
                    self._switch_to_window(a0.hwnd)
                elif a1.button() == Qt.MouseButton.RightButton:
                    self._close_window(a0.hwnd)
                return True

        if isinstance(a1, QKeyEvent) and a1.type() == QEvent.Type.KeyRelease:
            self._switch_if_released()

        if isinstance(a1, QKeyEvent) and a1.type() == QEvent.Type.KeyPress:
            key = a1.key()
            if key == Qt.Key.Key_Escape:
                self._hold_modifiers = Qt.KeyboardModifier.NoModifier
                if self._popup is not None:
                    self._popup.hide_animated()
                return True
            if key == Qt.Key.Key_Right:
                new_idx = min(self.current_focus_index + 1, len(self.buttons_list) - 1)
                if new_idx != self.current_focus_index:
                    self.set_focused_button(new_idx)
                return True
            if key == Qt.Key.Key_Left:
                new_idx = max(self.current_focus_index - 1, 0)
                if new_idx != self.current_focus_index:
                    self.set_focused_button(new_idx)
                return True
            if key == Qt.Key.Key_Delete:
                if 0 <= self.current_focus_index < len(self.buttons_list):
                    self._close_window(self.buttons_list[self.current_focus_index].hwnd)
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
                if 0 <= self.current_focus_index < len(self.buttons_list):
                    self._switch_to_window(self.buttons_list[self.current_focus_index].hwnd)
                return True

        return super().eventFilter(a0, a1)

    def set_focused_button(self, index: int, by_mouse: bool = False):
        if not self.buttons_list or not (0 <= index < len(self.buttons_list)):
            return

        prev = self.current_focus_index
        self.current_focus_index = index

        if 0 <= prev < len(self.buttons_list):
            prev_btn = self.buttons_list[prev]
            prev_btn.clearFocus()
            prev_btn.setProperty("class", "item")
            refresh_widget_style(prev_btn)

        btn = self.buttons_list[index]
        btn.setProperty("class", "item active")
        refresh_widget_style(btn)

        if self.active_title_label:
            title = btn.title
            available_w = self.active_title_label.contentsRect().width()
            if available_w > 0:
                title = self.active_title_label.fontMetrics().elidedText(
                    title, Qt.TextElideMode.ElideRight, available_w
                )
            self.active_title_label.setText(title)

        if not by_mouse:
            btn.setFocus()
            bar = self._scroll_area.horizontalScrollBar() if self._scroll_area else None
            if self._scroll_area and bar is not None and self._btn_w > 0:
                first_visible = bar.value() // self._btn_w
                actual_visible_apps = self._scroll_area.width() // self._btn_w

                if actual_visible_apps > 0:
                    last_visible = first_visible + actual_visible_apps - 1
                    if index > last_visible:
                        bar.setValue((index - actual_visible_apps + 1) * self._btn_w)
                    elif index < first_visible:
                        bar.setValue(index * self._btn_w)
