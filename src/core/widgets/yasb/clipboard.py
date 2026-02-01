import asyncio
import logging

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget
from winrt.windows.applicationmodel.datatransfer import Clipboard, DataPackage, StandardDataFormats

from core.utils.utilities import PopupWidget, build_widget_label
from core.validation.widgets.yasb.clipboard import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget


class ClipboardWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(self, **kwargs):
        super().__init__(class_name=f"clipboard-widget {kwargs.get('class_name', '')}")
        self._config = kwargs
        self._show_alt = False
        self._widget_container_layout = self.layout()
        self.widget_label = build_widget_label(self, self._config["label"].format(clipboard=""))
        self._menu = None

        self.register_callback("toggle_menu", self.toggle_menu)
        self.register_callback("toggle_label", self.toggle_label)
        self.callback_left = "toggle_menu"
        self.callback_right = "toggle_label"

    async def _fetch_and_show(self):
        try:
            history = await Clipboard.get_history_items_async()
            items = []
            if history.status.value == 0:
                for item in list(history.items)[: self._config["max_history"]]:
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

            self._menu = ClipboardPopup(self, items, self._config)
            self._menu.show_menu()
        except Exception as e:
            logging.error(f"Async Clipboard Error: {e}")

    def toggle_menu(self):
        try:
            if self._menu and self._menu.isVisible():
                self._menu.hide()
                return
        except RuntimeError:
            self._menu = None

        asyncio.create_task(self._fetch_and_show())

    def toggle_label(self):
        self._show_alt = not self._show_alt
        lbl = self._config["label_alt"] if self._show_alt else self._config["label"]
        while self.layout().count():
            child = self.layout().takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.widget_label = build_widget_label(self, lbl.format(clipboard=""))

    def set_system_clipboard(self, item):
        # 1. Update the actual Windows Clipboard
        dp = DataPackage()
        if item["type"] == "text":
            dp.set_text(item["data"])
        elif item["type"] == "image":
            dp.set_bitmap(item["raw"])

        Clipboard.set_content(dp)
        Clipboard.flush()

        # 2. Provide Visual Feedback on the Bar
        self._flash_copied_message()

        if self._menu:
            self._menu.hide()

    def _find_label_widget(self):
        """Helper to find the QLabel created by build_widget_label"""
        for i in range(self.layout().count()):
            widget = self.layout().itemAt(i).widget()
            if isinstance(widget, QLabel):
                return widget
        return None

    def _flash_copied_message(self):
        label = self._find_label_widget()
        if label:
            # Use the hex code directly here.
            # We add <b> for bolding since the CSS selector is gone.
            icon = self._config["icons"]["clipboard"]
            flash_text = f"<b><font color='#a6e3a1'>{icon} Copied!</font></b>"

            label.setText(flash_text)
            QTimer.singleShot(1500, self._revert_label)

    def _revert_label(self):
        """Returns the bar label to its original state by updating text"""
        label = self._find_label_widget()
        if label:
            lbl = self._config["label_alt"] if self._show_alt else self._config["label"]
            label.setText(lbl.format(clipboard=""))


class ClipboardPopup(PopupWidget):
    def __init__(self, parent_widget, items, config):
        super().__init__(parent_widget, config["menu"])
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._parent_widget = parent_widget
        self._all_items = items
        self._icons = config["icons"]
        self._max_item_len = config["menu"].get("max_item_length", 50)
        self._init_ui()

    def _init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.setMinimumWidth(320)

        # FIX: Set property on the instances, not the methods
        self.setProperty("class", "clipboard-menu")

        self.search_bar = QLineEdit()
        self.search_bar.setProperty("class", "search-input")
        self.search_bar.setPlaceholderText("Search history...")
        self.search_bar.textChanged.connect(self._filter_items)
        self.main_layout.addWidget(self.search_bar)

        clear_btn = QPushButton(f"{self._icons['clear']} Clear All History")
        clear_btn.setProperty("class", "clear-button")
        clear_btn.clicked.connect(lambda: [Clipboard.clear_history(), self.close()])
        self.main_layout.addWidget(clear_btn)

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
        # 1. Properly clear EVERYTHING (widgets and layouts)
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            else:
                # If it's a layout (the row), we need to clear its contents too
                sub_layout = item.layout()
                if sub_layout:
                    while sub_layout.count():
                        sub_item = sub_layout.takeAt(0)
                        if sub_item.widget():
                            sub_item.widget().deleteLater()
                    sub_layout.deleteLater()

        # 2. Re-render the items
        if not items:
            self.container_layout.addWidget(QLabel("No items match your search."))
            return

        for item in items:
            row = QHBoxLayout()

            btn = QPushButton()
            btn.setProperty("class", "clipboard-item")
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

            if item["type"] == "text":
                clean = item["data"].replace("\n", " ").strip()
                display = (clean[: self._max_item_len] + "..") if len(clean) > self._max_item_len else clean
                btn.setText(display)
                btn.setToolTip(item["data"])
            else:
                btn.setIcon(QIcon(item["data"]))
                btn.setIconSize(item["data"].size().scaled(200, 80, Qt.AspectRatioMode.KeepAspectRatio))
                btn.setText(" [Image]")

            btn.clicked.connect(lambda _, i=item: self._parent_widget.set_system_clipboard(i))

            del_btn = QPushButton(self._icons["search_clear"])
            del_btn.setFixedWidth(35)
            del_btn.setStyleSheet("color: #e74c3c; font-weight: bold;")
            del_btn.clicked.connect(lambda _, i=item: self._delete_item(i))

            row.addWidget(btn)
            row.addWidget(del_btn)
            self.container_layout.addLayout(row)

    def _delete_item(self, item_data):
        """Removes a single item from Windows History"""
        try:
            # We pass the 'raw_item' stored during _fetch_and_show
            success = Clipboard.delete_item_from_history(item_data["raw_item"])
            if not success:
                logging.warning("Windows refused to delete the item.")
        except AttributeError:
            logging.error("Single item deletion is not supported by this WinRT package.")

        # Refresh the UI
        self.close()
        asyncio.create_task(self._parent_widget._fetch_and_show())

    def _filter_items(self, query):
        filtered = []
        for i in self._all_items:
            if i["type"] == "image":
                filtered.append(i)
            elif query.lower() in i["data"].lower():
                filtered.append(i)
        self._render_items(filtered)

    def show_menu(self):
        self.show()
        parent_geo = self._parent_widget.mapToGlobal(self._parent_widget.rect().bottomLeft())
        screen_geo = self.screen().availableGeometry()
        x, y = parent_geo.x(), parent_geo.y()
        if x + self.width() > screen_geo.right():
            x = screen_geo.right() - self.width()
        if y + self.height() > screen_geo.bottom():
            y = parent_geo.y() - self._parent_widget.height() - self.height()
        self.move(x, y)
