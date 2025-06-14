import logging
from collections import deque

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QPainter
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.event_enums import KomorebiEvent
from core.event_service import EventService
from core.utils.komorebi.client import KomorebiClient
from core.utils.utilities import PopupWidget, add_shadow
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.win32.utilities import get_monitor_hwnd
from core.validation.widgets.komorebi.active_layout import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget

try:
    from core.utils.komorebi.event_listener import KomorebiEventListener
except ImportError:
    KomorebiEventListener = None
    logging.warning("Failed to load Komorebi Event Listener")

layout_cmds = {
    "BSP": "bsp",
    "Columns": "columns",
    "Rows": "rows",
    "Grid": "grid",
    "Scrolling": "scrolling",
    "VerticalStack": "vertical-stack",
    "HorizontalStack": "horizontal-stack",
    "UltrawideVerticalStack": "ultrawide-vertical-stack",
    "RightMainVerticalStack": "right-main-vertical-stack",
}
layout_snake_case = {
    "BSP": "bsp",
    "Columns": "columns",
    "Rows": "rows",
    "Grid": "grid",
    "Scrolling": "scrolling",
    "VerticalStack": "vertical_stack",
    "HorizontalStack": "horizontal_stack",
    "UltrawideVerticalStack": "ultrawide_vertical_stack",
    "RightMainVerticalStack": "right_main_vertical_stack",
    "Floating": "floating",
    "Monocle": "monocle",
    "Maximised": "maximised",
    "Paused": "paused",
}


class LayoutIconWidget(QWidget):
    def __init__(
        self,
        layout_name: str = "bsp",
    ):
        super().__init__()
        self.layout_name = layout_name

    def sizeHint(self):
        size = self.font().pixelSize()
        return QSize(size, size)

    def setAlignment(self, a0):
        pass

    def paintEvent(self, a0):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        size = self.font().pixelSize()
        stroke_width = max(1.0, size * 0.08)

        pen = painter.pen()
        pen.setWidthF(stroke_width)
        painter.setPen(pen)

        rect = self.rect()
        x = (rect.width() - size) / 2
        y = (rect.height() - size) / 2
        icon_rect = QRectF(x, y, size, size)

        r = (icon_rect.width() / 2) - stroke_width
        c = icon_rect.center()
        
        adjusted_width = stroke_width * 0.8
        icon_rect = icon_rect.adjusted(adjusted_width, adjusted_width, -adjusted_width, -adjusted_width)
        
        corner_radius = icon_rect.width() * 0.1
        painter.drawRoundedRect(icon_rect, corner_radius, corner_radius)
        
        self._draw_icon(painter, icon_rect, r, c)
        painter.end()

    def _draw_icon(
        self,
        painter: QPainter,
        icon_rect: QRectF,
        r: float,
        c: QPointF,
    ):
        # helper functions to draw lines and vectors
        def vec(dx, dy):
            return QPointF(dx, dy)

        def line(start, end):
            painter.drawLine(start, end)

        # draw layout icons
        if self.layout_name == "bsp":
            line(c - vec(0, r), c + vec(0, r))
            line(c, c + vec(r, 0))
            line(c + vec(r / 2 + 0.2, 0.2), c + vec(r / 2 + 0.2, r))
        elif self.layout_name == "columns":
            line(c - vec(r / 2, r), c + vec(-r / 2, r))
            line(c - vec(0, r), c + vec(0, r))
            line(c - vec(-r / 2, r), c + vec(r / 2, r))
        elif self.layout_name == "rows":
            line(c - vec(r, r / 2), c + vec(r, -r / 2))
            line(c - vec(r, 0), c + vec(r, 0))
            line(c - vec(r, -r / 2), c + vec(r, r / 2))
        elif self.layout_name == "vertical_stack":
            line(c - vec(0, r), c + vec(0, r))
            line(c, c + vec(r, 0))
        elif self.layout_name == "right_main_vertical_stack":
            line(c - vec(0, r), c + vec(0, r))
            line(c - vec(r, 0), c)
        elif self.layout_name == "horizontal_stack":
            line(c - vec(r, 0), c + vec(r, 0))
            line(c, c + vec(0, r))
        elif self.layout_name == "ultrawide_vertical_stack":
            line(c - vec(r / 2, r), c + vec(-r / 2, r))
            line(c + vec(r / 2, 0), c + vec(r, 0))
            line(c - vec(-r / 2, r), c + vec(r / 2, r))
        elif self.layout_name == "grid":
            line(c - vec(r, 0), c + vec(r, 0))
            line(c - vec(0, r), c + vec(0, r))
        elif self.layout_name == "scrolling":
            line(c - vec(r / 2, r), c + vec(-r / 2, r))
            line(c - vec(0, r), c + vec(0, r))
            line(c - vec(-r / 2, r), c + vec(r / 2, r))
        elif self.layout_name == "monocle" or self.layout_name == "maximised":
            pass
        elif self.layout_name == "tiling" or self.layout_name == "floating":
            rect_left = QRectF(icon_rect)
            rect_left.setWidth(icon_rect.width() * 0.5)
            rect_left.setHeight(icon_rect.height() * 0.5)
            rect_right = QRectF(rect_left)

            rect_left.moveTopLeft(
                icon_rect.topLeft() + vec(icon_rect.width() * 0.15, icon_rect.height() * 0.15)
            )
            rect_right.moveTopLeft(
                icon_rect.topLeft() + vec(icon_rect.width() * 0.3, icon_rect.height() * 0.3)
            )
    
            corner_radius = icon_rect.width() * 0.1

            painter.setBrush(self.palette().brush(self.foregroundRole()))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect_left, corner_radius, corner_radius)
            
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(self.palette().color(self.foregroundRole()))
            painter.drawRoundedRect(rect_right, corner_radius, corner_radius)
        elif self.layout_name == "paused":
            rect_left = QRectF(icon_rect)
            rect_right = QRectF(rect_left)

            rect_left.setWidth(icon_rect.width() * 0.25)
            rect_left.setHeight(icon_rect.height() * 0.7)
            rect_right.setWidth(rect_left.width())
            rect_right.setHeight(rect_left.height())

            rect_left.moveTopLeft(
                icon_rect.topLeft() + vec(icon_rect.width() * 0.2, icon_rect.width() * 0.15)
            )
            rect_right.moveTopLeft(
                icon_rect.topLeft() + vec(icon_rect.width() * 0.55, icon_rect.width() * 0.15)
            )

            painter.setBrush(self.palette().brush(self.foregroundRole()))
            painter.setPen(Qt.PenStyle.NoPen)

            corner_radius = icon_rect.width() * 0.1
            painter.drawRoundedRect(rect_left, corner_radius, corner_radius)
            painter.drawRoundedRect(rect_right, corner_radius, corner_radius)
        else:
            line(c - vec(0, r), c + vec(0, r))
            line(c + vec(0, r / 2), c + vec(r, r / 2))
            line(c - vec(0, r / 3), c - vec(r, r / 3))


class ActiveLayoutWidget(BaseWidget):
    k_signal_connect = pyqtSignal(dict)
    k_signal_disconnect = pyqtSignal()
    k_signal_layout_change = pyqtSignal(dict, dict)
    k_signal_update = pyqtSignal(dict, dict)

    validation_schema = VALIDATION_SCHEMA
    event_listener = KomorebiEventListener

    def __init__(
            self,
            label: str,
            layouts: list[str],
            layout_icons: dict[str, str],
            layout_menu: dict[str, str],
            generate_layout_icons: bool,
            hide_if_offline: bool,
            container_padding: dict,
            animation: dict[str, str],
            callbacks: dict[str, str],
            label_shadow: dict = None,
            container_shadow: dict = None,
        ):
        super().__init__(class_name="komorebi-active-layout")
        self._label = label
        self._layout_icons = layout_icons
        self._layout_menu = layout_menu
        self._layouts_config = layouts
        self._generate_layout_icons = generate_layout_icons
        self._padding = container_padding
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow
        self._reset_layouts()
        self._hide_if_offline = hide_if_offline
        self._event_service = EventService()
        self._komorebic = KomorebiClient()
        self._komorebi_screen = None
        self._komorebi_workspaces = []
        self._focused_workspace = {}
        # Set the cursor to be a pointer when hovering over the button
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._active_layout_icon = LayoutIconWidget()
        self._active_layout_icon.setProperty("class", "icon")
        self._active_layout_text = QLabel()
        self._active_layout_text.setProperty("class", "label")
        self._active_layout_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        add_shadow(self._active_layout_text, self._label_shadow)
        self._animation = animation
        # Construct container
        self._widget_container_layout: QHBoxLayout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(self._padding['left'],self._padding['top'],self._padding['right'],self._padding['bottom'])
        # Initialize container
        self._widget_container: QWidget = QWidget()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self._container_shadow)
        # Add the container to the main widget layout
        self.widget_layout.addWidget(self._widget_container)

        if self._generate_layout_icons:
            self._widget_container_layout.addWidget(self._active_layout_icon)
        self._widget_container_layout.addWidget(self._active_layout_text)
  
        self.callback_left = callbacks['on_left']
        self.callback_right = callbacks['on_right']
        self.callback_middle = callbacks['on_middle']

        self.register_callback("next_layout", self._next_layout)
        self.register_callback("prev_layout", self._prev_layout)
        self.register_callback("flip_layout", self._komorebic.flip_layout_horizontal)
        self.register_callback("flip_layout_horizontal", self._komorebic.flip_layout_horizontal)
        self.register_callback("flip_layout_vertical", self._komorebic.flip_layout_vertical)
        self.register_callback("flip_layout_horizontal_and_vertical", self._komorebic.flip_layout_horizontal_and_vertical)
        self.register_callback("first_layout", self._first_layout)
        self.register_callback("toggle_tiling", lambda: self._komorebic.toggle("tiling"))
        self.register_callback("toggle_float", lambda: self._komorebic.toggle("float"))
        self.register_callback("toggle_monocle", lambda: self._komorebic.toggle("monocle"))
        self.register_callback("toggle_maximise", lambda: self._komorebic.toggle("maximise"))
        self.register_callback("toggle_pause", lambda: self._komorebic.toggle("pause"))
        self.register_callback("toggle_layout_menu", self._toggle_layout_menu)

        self._register_signals_and_events()
        self.hide()

    def _toggle_layout_menu(self):
        if self._animation['enabled']:
            AnimationManager.animate(self, self._animation['type'], self._animation['duration'])
        self._show_layout_menu()

    def _show_layout_menu(self):
        self._menu = PopupWidget(
            self,
            self._layout_menu['blur'],
            self._layout_menu['round_corners'],
            self._layout_menu['round_corners_type'],
            self._layout_menu['border_color']
        )
        self._menu.setProperty('class', 'komorebi-layout-menu')

        main_layout = QVBoxLayout(self._menu)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        def create_menu_item(icon, text, click_handler):
            item = QFrame()
            item.setProperty("class", "menu-item")
            item_layout = QHBoxLayout(item)
            item_layout.setContentsMargins(0, 0, 0, 0)

            if self._layout_menu['show_layout_icons']:
                icon_label = QLabel(icon) if isinstance(icon, str) else icon

                icon_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                icon_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

                icon_label.setProperty("class", "menu-item-icon")
                item_layout.addWidget(icon_label)

            text_label = QLabel(text)
            text_label.setProperty("class", "menu-item-text")
            text_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            text_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            item_layout.addWidget(text_label)

            item.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            item.mousePressEvent = click_handler
            return item

        for layout in self._layouts_config:
            if self._generate_layout_icons:
                icon = LayoutIconWidget(layout)
            else:
                icon = self._layout_icons[layout]
            text = layout.replace('_', ' ').title()

            def handler(event, l=layout):
                self._on_layout_menu_selected(l)

            main_layout.addWidget(create_menu_item(icon, text, handler))

        self._menu._add_separator(main_layout)

        def make_toggle_handler(func):
            def handler(event):
                func()
                self._menu.hide()

            return handler

        if self._generate_layout_icons:
            toggle_icons = {
                "Toggle Tiling": LayoutIconWidget("tiling"),
                "Toggle Monocle": LayoutIconWidget("monocle"),
                "Toggle Pause": LayoutIconWidget("paused"),
            }
        else:
            toggle_icons = {
                "Toggle Tiling": self._layout_icons["tiling"],
                "Toggle Monocle": self._layout_icons["monocle"],
                "Toggle Pause": self._layout_icons["paused"],
            }
        toggle_actions = [
            ("Toggle Tiling", lambda: self._komorebic.toggle("tiling")),
            ("Toggle Monocle", lambda: self._komorebic.toggle("monocle")),
            ("Toggle Pause", lambda: self._komorebic.toggle("pause")),
        ]
        for label, func in toggle_actions:
            main_layout.addWidget(
                create_menu_item(
                    toggle_icons.get(label, ""), 
                    label, 
                    make_toggle_handler(func)
                )
            )

        self._menu.adjustSize()
        self._menu.setPosition(
            alignment=self._layout_menu['alignment'],
            direction=self._layout_menu['direction'],
            offset_left=self._layout_menu['offset_left'],
            offset_top=self._layout_menu['offset_top']
        )
        self._menu.show()

    def _on_layout_menu_selected(self, layout):
        layout_cmd = layout.replace('_', '-')
        self.change_layout(layout_cmd)
        self._menu.hide()
        if self._animation['enabled']:
            AnimationManager.animate(self, self._animation['type'], self._animation['duration'])

    def _reset_layouts(self):
        self._layouts = deque([x.replace('_', '-') for x in self._layouts_config])

    def change_layout(self, layout: str):
        self._komorebic.change_layout(self._komorebi_screen['index'], self._focused_workspace['index'], layout)

    def _first_layout(self):
        if self._is_shift_layout_allowed():
            self._reset_layouts()
            self.change_layout(self._layouts[0])

    def _next_layout(self):
        if self._is_shift_layout_allowed():
            self._layouts.rotate(1)
            self.change_layout(self._layouts[0])
            if self._animation['enabled']:
                AnimationManager.animate(self, self._animation['type'], self._animation['duration'])

    def _prev_layout(self):
        if self._is_shift_layout_allowed():
            self._layouts.rotate(-1)
            self.change_layout(self._layouts[0])
            if self._animation['enabled']:
                AnimationManager.animate(self, self._animation['type'], self._animation['duration'])

    def _is_shift_layout_allowed(self):
        return not bool(
            not self._focused_workspace.get('tile', False) or
            self._focused_workspace.get('monocle_container', None) or
            self._focused_workspace.get('maximized_window', None) or
            self._komorebi_state.get('is_paused', False)
        )

    def _register_signals_and_events(self):
        active_layout_change_event_watchlist = [
            KomorebiEvent.ChangeLayout,
            KomorebiEvent.FocusWorkspaceNumber,
            KomorebiEvent.FocusMonitorWorkspaceNumber,
            KomorebiEvent.TogglePause,
            KomorebiEvent.ToggleTiling,
            KomorebiEvent.ToggleMonocle,
            KomorebiEvent.ToggleMaximise,
        ]

        self.k_signal_connect.connect(self._on_komorebi_connect_event)
        self.k_signal_disconnect.connect(self._on_komorebi_disconnect_event)
        self.k_signal_layout_change.connect(self._on_komorebi_layout_change_event)
        self.k_signal_update.connect(self._on_komorebi_layout_change_event)

        self._event_service.register_event(KomorebiEvent.KomorebiConnect, self.k_signal_connect)
        self._event_service.register_event(KomorebiEvent.KomorebiDisconnect, self.k_signal_disconnect)
        self._event_service.register_event(KomorebiEvent.KomorebiUpdate, self.k_signal_update)

        for event_type in active_layout_change_event_watchlist:
            self._event_service.register_event(event_type, self.k_signal_layout_change)

    def _on_komorebi_connect_event(self, state: dict) -> None:
        self._update_active_layout(state, is_connect_event=True)
        if self.isHidden():
            self.show()

    def _on_komorebi_layout_change_event(self, _event: dict, state: dict) -> None:
        self._update_active_layout(state)

    def _on_komorebi_disconnect_event(self) -> None:
        if self._hide_if_offline:
            self.hide()

    def _update_active_layout(self, state: dict, is_connect_event=False):
        try:
            if self._update_komorebi_state(state):
                self._focused_workspace = self._komorebic.get_focused_workspace(self._komorebi_screen)

                if not self._focused_workspace:
                    return

                layout_name, layout_icon = self._get_layout_label_info()

                if is_connect_event:
                    conn_layout_name = self._focused_workspace['layout']['Default']
                    conn_layout_cmd = layout_cmds.get(conn_layout_name, 'bsp')

                    while self._layouts[0] != conn_layout_cmd:
                        self._layouts.rotate(1)

                if self._generate_layout_icons:
                    self._active_layout_icon.layout_name = layout_snake_case.get(layout_name, "unknown layout")
                    self._active_layout_icon.update()

                self._active_layout_text.setText(self._label.replace("{icon}", layout_icon).replace("{layout_name}", layout_name))

                if self._active_layout_text.isHidden():
                    self.show()
        except Exception:
            logging.exception("Failed to update komorebi status and widget button state")

    def _get_layout_label_info(self):
        if self._komorebi_state.get('is_paused', False):
            layout_name = 'Paused'
            layout_icon = self._layout_icons['paused']
        elif not self._focused_workspace.get('tile', False):
            layout_name = 'Floating'
            layout_icon = self._layout_icons['floating']
        elif self._focused_workspace.get('maximized_window', None):
            layout_name = 'Maximised'
            layout_icon = self._layout_icons['maximised']
        elif self._focused_workspace.get('monocle_container', None):
            layout_name = 'Monocle'
            layout_icon = self._layout_icons['monocle']
        else:
            layout_name = self._focused_workspace['layout']['Default']
            layout_icon = self._layout_icons.get(layout_snake_case[layout_name], 'unknown layout')

        return layout_name, layout_icon

    def _update_komorebi_state(self, komorebi_state: dict):
        try:
            self._screen_hwnd = get_monitor_hwnd(int(QWidget.winId(self)))
            self._komorebi_state = komorebi_state

            if self._komorebi_state:
                self._komorebi_screen = self._komorebic.get_screen_by_hwnd(self._komorebi_state, self._screen_hwnd)
                self._komorebi_workspaces = self._komorebic.get_workspaces(self._komorebi_screen)
                return True
        except TypeError:
            return False
