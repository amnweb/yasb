import asyncio
import logging

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from winrt.windows.applicationmodel.datatransfer import Clipboard, DataPackage, StandardDataFormats

from core.utils.utilities import PopupWidget, add_shadow, build_widget_label
from core.utils.widgets.animation_manager import AnimationManager
from core.validation.widgets.yasb.clipboard import ClipboardConfig
from core.widgets.base import BaseWidget


class ClipboardWidget(BaseWidget):
    """A clipboard manager widget that integrates with Windows Clipboard History."""

    validation_schema = ClipboardConfig

    def __init__(self, config: ClipboardConfig):
        super().__init__(class_name=f"clipboard-widget {config.class_name}")
        self.config = config
        self._show_alt = False
        self._menu = None

        # Set up widget container layout
        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(
            self.config.container_padding.left,
            self.config.container_padding.top,
            self.config.container_padding.right,
            self.config.container_padding.bottom,
        )

        # Initialize container
        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self.config.container_shadow.model_dump())

        # Add the container to the main widget layout
        self.widget_layout.addWidget(self._widget_container)

        # Build widget labels
        build_widget_label(
            self,
            self.config.label.format(clipboard=""),
            self.config.label_alt.format(clipboard=""),
            self.config.label_shadow.model_dump(),
        )

        # Register callbacks
        self.register_callback("toggle_menu", self.toggle_menu)
        self.register_callback("toggle_label", self.toggle_label)

        self.callback_left = self.config.callbacks.on_left
        self.callback_right = self.config.callbacks.on_right
        self.callback_middle = self.config.callbacks.on_middle

    async def _fetch_and_show(self):
        """Fetch clipboard history from Windows and show the popup menu."""
        try:
            history = await Clipboard.get_history_items_async()
            items = []
            if history.status.value == 0:
                for item in list(history.items)[: self.config.max_history]:
                    content = item.content
                    entry = {"id": item.id, "type": "text", "data": None, "raw_item": item}

                    if content.contains(StandardDataFormats.text):
                        entry["data"] = await content.get_text_async()
                        items.append(entry)
                    elif content.contains(StandardDataFormats.bitmap):
                        try:
                            stream_ref = await content.get_bitmap_async()
                            stream = await stream_ref.open_read_async()
                            buffer = bytearray(stream.size)
                            await stream.read_async(buffer, stream.size, 0)

                            pixmap = QPixmap()
                            pixmap.loadFromData(buffer)
                            if not pixmap.isNull():
                                entry["data"] = pixmap
                                entry["raw"] = stream_ref
                                entry["type"] = "image"
                                items.append(entry)
                        except Exception:
                            continue

            self._menu = ClipboardPopup(self, items, self.config)
            self._menu.show_menu()
        except Exception as e:
            logging.error(f"Async Clipboard Error: {e}")

    def toggle_menu(self):
        """Toggle the clipboard history popup menu."""
        try:
            if self._menu and self._menu.isVisible():
                self._menu.hide()
                return
        except RuntimeError:
            self._menu = None

        asyncio.create_task(self._fetch_and_show())

    def toggle_label(self):
        """Toggle between primary and alternate labels with animation."""
        if self.config.animation.enabled:
            AnimationManager.animate(self, self.config.animation.type, self.config.animation.duration)

        self._show_alt = not self._show_alt
        for widget in self._widgets:
            widget.setVisible(not self._show_alt)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt)

    def set_system_clipboard(self, item):
        """Set an item to the system clipboard."""
        dp = DataPackage()
        if item["type"] == "text":
            dp.set_text(item["data"])
        elif item["type"] == "image":
            dp.set_bitmap(item["raw"])

        Clipboard.set_content(dp)
        Clipboard.flush()

        # Provide visual feedback
        self._flash_copied_message()

        if self._menu:
            self._menu.hide()

    def _find_label_widget(self):
        """Helper to find the QLabel created by build_widget_label."""
        active_widgets = self._widgets_alt if self._show_alt else self._widgets
        for widget in active_widgets:
            if isinstance(widget, QLabel):
                return widget
        return None

    def _flash_copied_message(self):
        """Briefly show a 'Copied!' message on the widget label."""
        label = self._find_label_widget()
        if label:
            icon = self.config.icons.clipboard
            flash_text = f"<b><font color='#a6e3a1'>{icon} Copied!</font></b>"
            label.setText(flash_text)
            QTimer.singleShot(1500, self._revert_label)

    def _revert_label(self):
        """Revert the label to its original state."""
        label = self._find_label_widget()
        if label:
            lbl = self.config.label_alt if self._show_alt else self.config.label
            label.setText(lbl.format(clipboard=""))


class ClipboardPopup(PopupWidget):
    """Popup widget for displaying clipboard history."""

    def __init__(self, parent_widget: ClipboardWidget, items: list, config: ClipboardConfig):
        super().__init__(
            parent_widget,
            blur=config.menu.blur,
            round_corners=config.menu.round_corners,
            round_corners_type=config.menu.round_corners_type,
            border_color=config.menu.border_color,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._parent_widget = parent_widget
        self._all_items = items
        self._icons = config.icons
        self._menu_config = config.menu
        self._init_ui()

    def _init_ui(self):
        """Initialize the popup UI."""
        self.main_layout = QVBoxLayout(self)
        self.setMinimumWidth(320)
        self.setProperty("class", "clipboard-menu")

        # Search bar
        self.search_bar = QLineEdit()
        self.search_bar.setProperty("class", "search-input")
        self.search_bar.setPlaceholderText("Search history...")
        self.search_bar.textChanged.connect(self._filter_items)
        self.main_layout.addWidget(self.search_bar)

        # Clear all button
        clear_btn = QPushButton(f"{self._icons.clear} Clear All History")
        clear_btn.setProperty("class", "clear-button")
        clear_btn.clicked.connect(lambda: [Clipboard.clear_history(), self.close()])
        self.main_layout.addWidget(clear_btn)

        # Scroll area for items
        self.scroll = QScrollArea()
        self.scroll.setProperty("class", "scroll-area")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.container)
        self.main_layout.addWidget(self.scroll)
        self._render_items(self._all_items)

    def _render_items(self, items):
        """Render the clipboard items in the popup."""
        # Clear existing items
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            else:
                sub_layout = item.layout()
                if sub_layout:
                    while sub_layout.count():
                        sub_item = sub_layout.takeAt(0)
                        if sub_item.widget():
                            sub_item.widget().deleteLater()
                    sub_layout.deleteLater()

        if not items:
            self.container_layout.addWidget(QLabel("No items match your search."))
            return

        max_item_len = self._menu_config.max_item_length

        for item in items:
            row = QHBoxLayout()

            btn = QPushButton()
            btn.setProperty("class", "clipboard-item")
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

            if item["type"] == "text":
                clean = item["data"].replace("\n", " ").strip()
                display = (clean[:max_item_len] + "..") if len(clean) > max_item_len else clean
                btn.setText(display)
                btn.setToolTip(item["data"])
            else:
                btn.setIcon(QIcon(item["data"]))
                btn.setIconSize(item["data"].size().scaled(200, 80, Qt.AspectRatioMode.KeepAspectRatio))
                btn.setText(" [Image]")

            btn.clicked.connect(lambda _, i=item: self._parent_widget.set_system_clipboard(i))

            del_btn = QPushButton(self._icons.search_clear)
            del_btn.setFixedWidth(35)
            del_btn.setStyleSheet("color: #e74c3c; font-weight: bold;")
            del_btn.clicked.connect(lambda _, i=item: self._delete_item(i))

            row.addWidget(btn)
            row.addWidget(del_btn)
            self.container_layout.addLayout(row)

    def _delete_item(self, item_data):
        """Remove a single item from Windows Clipboard History."""
        try:
            success = Clipboard.delete_item_from_history(item_data["raw_item"])
            if not success:
                logging.warning("Windows refused to delete the item.")
        except AttributeError:
            logging.error("Single item deletion is not supported by this WinRT package.")

        # Refresh the UI
        self.close()
        asyncio.create_task(self._parent_widget._fetch_and_show())

    def _filter_items(self, query):
        """Filter clipboard items based on search query."""
        filtered = []
        for i in self._all_items:
            if i["type"] == "image":
                filtered.append(i)
            elif query.lower() in i["data"].lower():
                filtered.append(i)
        self._render_items(filtered)

    def show_menu(self):
        """Show the popup menu positioned relative to the parent widget."""
        self.show()
        self.setPosition(
            alignment=self._menu_config.alignment,
            direction=self._menu_config.direction,
            offset_left=self._menu_config.offset_left,
            offset_top=self._menu_config.offset_top,
        )
