from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtGui import QCursor, QKeySequence, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
)

from core.utils.utilities import PopupWidget, add_shadow, build_widget_label
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.widgets.quick_launch.base_provider import ProviderResult
from core.utils.widgets.quick_launch.service import QuickLaunchService
from core.utils.win32.utilities import get_foreground_hwnd, set_foreground_hwnd
from core.utils.win32.window_actions import force_foreground_focus
from core.validation.widgets.yasb.quick_launch import QuickLaunchConfig
from core.widgets.base import BaseWidget

_ICON_CACHE: dict[str, QPixmap] = {}


def _load_and_scale_icon(icon_path: str, size: int, dpr: float = 1.0) -> QPixmap:
    key = f"{icon_path}_{size}_{dpr}"
    if key in _ICON_CACHE:
        return _ICON_CACHE[key]
    try:
        target = int(size * dpr)
        pixmap = QPixmap(icon_path)
        if pixmap.isNull():
            return QPixmap()
        scaled = pixmap.scaled(
            QSize(target, target),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        scaled.setDevicePixelRatio(dpr)
        _ICON_CACHE[key] = scaled
        return scaled
    except Exception:
        return QPixmap()


class QuickLaunchWidget(BaseWidget):
    validation_schema = QuickLaunchConfig

    def __init__(self, config: QuickLaunchConfig):
        super().__init__(class_name="quick-launch-widget")
        self.config = config

        # Popup state
        self._popup: PopupWidget | None = None
        self._dpr = 1.0
        self._previous_hwnd = 0
        self._launched_app = False

        # Result state
        self._result_items: list[QFrame] = []
        self._result_data: list[ProviderResult] = []
        self._selected_index = -1

        # Async query state
        self._pending_query_id: str | None = None
        self._pending_search_text: str = ""

        # Service
        self._service = QuickLaunchService.instance()
        self._service.request_refresh.connect(self._on_request_refresh)
        self._service.icon_ready.connect(self._on_icon_ready)
        self._service.query_finished.connect(self._on_query_finished)
        self._service.configure_providers(self.config.providers.model_dump())

        # Bar widget
        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(0, 0, 0, 0)
        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self.config.container_shadow.model_dump())
        self.widget_layout.addWidget(self._widget_container)
        build_widget_label(self, self.config.label, None, self.config.label_shadow.model_dump())

        # Callbacks
        self.register_callback("toggle_quick_launch", self._toggle_quick_launch)
        self.callback_left = self.config.callbacks.on_left
        self.callback_right = self.config.callbacks.on_right
        self.callback_middle = self.config.callbacks.on_middle

    def _toggle_quick_launch(self):
        if self.config.animation.enabled:
            AnimationManager.animate(self, self.config.animation.type, self.config.animation.duration)
        if self._popup and self._popup.isVisible():
            self._hide_popup()
        else:
            self._show_popup()

    def _show_popup(self):
        self._dpr = self.screen().devicePixelRatio()
        self._previous_hwnd = get_foreground_hwnd()
        self._launched_app = False
        if not self._popup:
            self._popup = self._create_popup()
        self._center_popup_on_screen()
        self._popup.show()
        self._popup.search_input.blockSignals(True)
        self._popup.search_input.clear()
        self._popup.search_input.blockSignals(False)
        self._update_results("", immediate=True)
        force_foreground_focus(int(self._popup.winId()))
        QTimer.singleShot(0, self._reset_scroll_position)
        self._popup.search_input.setFocus()

    def _hide_popup(self):
        if not self._popup or self._popup._is_closing:
            return
        self._popup.hide_animated()

    def _on_popup_closed(self):
        """Called when the fade-out animation finishes."""
        if not (self._popup and self._popup._is_closing):
            return
        self._popup = None
        self._result_items.clear()
        self._result_data.clear()
        # Don't restore foreground if we just launched an app - let it keep focus
        if self._previous_hwnd and not self._launched_app:
            set_foreground_hwnd(self._previous_hwnd)
        self._previous_hwnd = 0
        self._launched_app = False

    def _center_popup_on_screen(self):
        if not self._popup:
            return
        screen = QApplication.screenAt(self.mapToGlobal(self.rect().center()))
        if screen is None:
            screen = QApplication.primaryScreen()
        geo = screen.geometry()
        popup_rect = self._popup.geometry()
        x = (geo.width() - popup_rect.width()) // 2 + geo.x()
        y = (geo.height() - popup_rect.height()) // 3 + geo.y()
        self._popup.move(x, y)

    def _reset_scroll_position(self):
        if self._popup and self._popup.isVisible():
            self._popup.scroll_area.verticalScrollBar().setValue(0)

    def _create_popup(self) -> PopupWidget:
        cfg = self.config.popup
        popup = PopupWidget(
            self,
            blur=cfg.blur,
            round_corners=cfg.round_corners,
            round_corners_type=cfg.round_corners_type,
            border_color=cfg.border_color,
            dark_mode=cfg.dark_mode,
        )
        popup.setProperty("class", "quick-launch-popup")
        popup._popup_content.setProperty("class", "container")
        popup.setFixedSize(cfg.width, cfg.height)
        popup._fade_animation.setDuration(40)
        popup._fade_animation.finished.connect(self._on_popup_closed)

        main_layout = QVBoxLayout(popup._popup_content)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Search bar
        search_container = QFrame()
        search_container.setProperty("class", "search")
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(0)

        search_icon = QLabel("\ue721")
        search_icon.setProperty("class", "search-icon")
        search_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        search_layout.addWidget(search_icon)

        search_input = QLineEdit()
        search_input.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        search_input.setProperty("class", "search-input")
        search_input.setPlaceholderText(self.config.search_placeholder)
        search_input.textChanged.connect(self._on_text_changed)
        search_layout.addWidget(search_input)

        enter_icon = QLabel("\ue751")
        enter_icon.setProperty("class", "search-submit-icon")
        enter_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        search_layout.addWidget(enter_icon)
        main_layout.addWidget(search_container)

        # Results area
        scroll_area = QScrollArea()
        scroll_area.setObjectName("results_scroll_area")
        scroll_area.setStyleSheet("""
            #results_scroll_area {
                background: transparent; 
                border: none;
                border-radius: 0;
            }
            #results_scroll_area QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 6px;
                margin: 4px 2px 4px 0;
            }
            #results_scroll_area QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.2);
                min-height: 20px;
                border-radius: 3px;
            }
            #results_scroll_area QScrollBar::handle:vertical:hover {
                background: rgba(255, 255, 255, 0.3);
            }
            #results_scroll_area QScrollBar::handle:vertical:pressed {
                background: rgba(255, 255, 255, 0.35);
            }
            #results_scroll_area QScrollBar::add-line:vertical,
            #results_scroll_area QScrollBar::sub-line:vertical {
                height: 0px;
            }
            #results_scroll_area QScrollBar::add-page:vertical,
            #results_scroll_area QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        results_container = QFrame()
        results_container.setProperty("class", "results")
        results_layout = QVBoxLayout(results_container)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.setSpacing(0)
        results_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll_area.setWidget(results_container)
        main_layout.addWidget(scroll_area)

        popup.search_input = search_input
        popup.results_layout = results_layout
        popup.scroll_area = scroll_area
        popup.keyPressEvent = self._handle_key_press

        QShortcut(QKeySequence(Qt.Key.Key_Escape), popup).activated.connect(self._hide_popup)
        return popup

    def _on_text_changed(self, text: str):
        self._pending_search_text = text
        self._update_results(text)

    def _update_results(self, search_text: str, immediate: bool = False):
        if not self._popup:
            return
        if immediate:
            results = self._service.query(search_text, self.config.max_results)
            self._apply_results(results)
        else:
            self._pending_query_id = self._service.async_query(search_text, self.config.max_results)

    def _apply_results(self, results: list):
        self._result_items.clear()
        self._result_data.clear()
        self._selected_index = -1

        # Build new results container
        new_container = QFrame()
        new_container.setProperty("class", "results")
        new_layout = QVBoxLayout(new_container)
        new_layout.setContentsMargins(0, 0, 0, 0)
        new_layout.setSpacing(0)
        new_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        if not results:
            has_text = bool(self._pending_search_text.strip())
            msg = "Type to search..." if not has_text else "No results found"
            hint = QLabel(msg)
            hint.setProperty("class", "results-empty")
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            new_layout.addWidget(hint)
        else:
            for i, result in enumerate(results):
                item = self._create_result_item(result, i)
                new_layout.addWidget(item)
                self._result_items.append(item)
                self._result_data.append(result)

        # Swap container in one shot
        self._popup.scroll_area.setWidget(new_container)
        self._popup.results_layout = new_layout

        if self._result_items:
            self._set_selected(0)

    def _create_result_item(self, result: ProviderResult, index: int) -> QFrame:
        item = QFrame()
        item.setProperty("class", f"item provider-{result.provider}")
        item.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        item_layout = QHBoxLayout(item)
        item_layout.setContentsMargins(0, 0, 0, 0)
        item_layout.setSpacing(12)

        # Icon
        if self.config.show_icons:
            icon_label = QLabel()
            icon_label.setFixedSize(self.config.icon_size, self.config.icon_size)
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            if result.icon_path:
                icon_label.setProperty("class", "item-icon")
                pixmap = _load_and_scale_icon(result.icon_path, self.config.icon_size, self._dpr)
                if not pixmap.isNull():
                    icon_label.setPixmap(pixmap)
            elif result.icon_char:
                icon_label.setProperty("class", "item-icon-char")
                icon_label.setText(result.icon_char)
            else:
                icon_label.setProperty("class", "item-icon")

            # Track result id for late icon updates from the service
            if result.id:
                item._result_id = result.id
                item._icon_label = icon_label

            item_layout.addWidget(icon_label)

        # Text (title + description)
        text_widget = QFrame()
        text_widget.setProperty("class", "item-text")
        text_widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        text_container = QVBoxLayout(text_widget)
        text_container.setContentsMargins(0, 0, 0, 0)
        text_container.setSpacing(2)

        title = QLabel(result.title)
        title.setProperty("class", "item-title")
        text_container.addWidget(title)

        if result.description:
            desc_label = QLabel(result.description)
            desc_label.setProperty("class", "item-description")
            text_container.addWidget(desc_label)

        item_layout.addWidget(text_widget, stretch=1)

        item._index = index
        item.mousePressEvent = lambda e, idx=index: (
            self._execute_result(idx) if e.button() == Qt.MouseButton.LeftButton else None
        )
        return item

    def _set_item_icon(self, item: QFrame, icon_path: str):
        if not hasattr(item, "_icon_label"):
            return
        pixmap = _load_and_scale_icon(icon_path, self.config.icon_size, self._dpr)
        if not pixmap.isNull():
            label = item._icon_label
            label.setText("")
            label.setProperty("class", "item-icon")
            label.style().unpolish(label)
            label.style().polish(label)
            label.setPixmap(pixmap)

    def _set_selected(self, index: int):
        # Deselect old
        if 0 <= self._selected_index < len(self._result_items):
            old = self._result_items[self._selected_index]
            old_class = old.property("class").replace(" selected", "")
            old.setProperty("class", old_class)
            old.style().unpolish(old)
            old.style().polish(old)

        self._selected_index = index

        # Select new
        if 0 <= self._selected_index < len(self._result_items):
            new_item = self._result_items[self._selected_index]
            cur_class = new_item.property("class")
            new_item.setProperty("class", cur_class + " selected")
            new_item.style().unpolish(new_item)
            new_item.style().polish(new_item)
            if self._selected_index > 0:
                self._popup.scroll_area.ensureWidgetVisible(new_item)
            else:
                self._popup.scroll_area.verticalScrollBar().setValue(0)

    def _on_request_refresh(self):
        if self._popup and self._popup.isVisible():
            text = self._popup.search_input.text()
            self._update_results(text, immediate=not text.strip())

    def _on_icon_ready(self, result_id: str, icon_path: str):
        if self._popup and self._popup.isVisible():
            for item in self._result_items:
                if getattr(item, "_result_id", None) == result_id:
                    self._set_item_icon(item, icon_path)
                    break

    def _on_query_finished(self, query_id: str, results: list):
        if query_id != self._pending_query_id:
            return
        if not self._popup or not self._popup.isVisible():
            return
        self._apply_results(results)

    def _handle_key_press(self, event):
        key = event.key()
        if key == Qt.Key.Key_Down and self._result_items:
            self._set_selected(min(self._selected_index + 1, len(self._result_items) - 1))
            return event.accept()
        if key == Qt.Key.Key_Up and self._result_items:
            self._set_selected(max(self._selected_index - 1, 0))
            return event.accept()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if 0 <= self._selected_index < len(self._result_data):
                self._execute_result(self._selected_index)
            return event.accept()
        if self._popup and not self._popup.search_input.hasFocus():
            self._popup.search_input.setFocus()
            self._popup.search_input.keyPressEvent(event)

    def _execute_result(self, index: int):
        if not (0 <= index < len(self._result_data)):
            return
        result = self._result_data[index]
        should_close = self._service.execute_result(result)
        if should_close:
            self._launched_app = True
            QTimer.singleShot(0, self._hide_popup)
        elif self._popup:
            text = self._popup.search_input.text()
            self._update_results(text)
