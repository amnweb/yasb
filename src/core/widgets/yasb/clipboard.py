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

try:
    from winrt.windows.applicationmodel.datatransfer import Clipboard, DataPackage, StandardDataFormats

    HAS_WINRT = True
except ImportError:
    HAS_WINRT = False
    Clipboard = None
    DataPackage = None
    StandardDataFormats = None

from core.utils.utilities import PopupWidget, add_shadow, build_widget_label, is_valid_qobject
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
        self._fetching = False
        self._missing_dependencies = not HAS_WINRT

        # Set up widget container layout
        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(0, 0, 0, 0)

        # Initialize container
        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self.config.container_shadow.model_dump())

        # Add the container to the main widget layout
        self.widget_layout.addWidget(self._widget_container)

        if self._missing_dependencies:
            # Show error label if dependencies are missing
            build_widget_label(
                self,
                "<span>\uf071</span> Missing dependencies",
                "Start with 'pip install winrt-Windows.ApplicationModel.DataTransfer'",
                self.config.label_shadow.model_dump(),
            )
        else:
            # Build widget labels
            build_widget_label(
                self,
                self.config.label.format(clipboard=""),
                self.config.label_alt.format(clipboard=""),
                self.config.label_shadow.model_dump(),
            )
            # Ensure all sub-labels (including icons) are catchable by .label CSS
            for label in getattr(self, "_widgets", []) + getattr(self, "_widgets_alt", []):
                if isinstance(label, QLabel):
                    current_class = label.property("class") or ""
                    if "label" not in current_class:
                        label.setProperty("class", f"{current_class} label".strip())

        # Register callbacks
        self.register_callback("toggle_menu", self.toggle_menu)
        self.register_callback("toggle_label", self.toggle_label)

        self.callback_left = self.config.callbacks.on_left
        self.callback_right = self.config.callbacks.on_right
        self.callback_middle = self.config.callbacks.on_middle

    async def _fetch_and_show(self):
        """Fetch clipboard history from Windows and show the popup menu."""
        if self._fetching:
            return

        self._fetching = True
        try:
            # Clean up existing menu immediately to prevent visual stacking
            if self._menu and is_valid_qobject(self._menu):
                try:
                    # Set closing flag to ensure event filters are removed in hideEvent
                    self._menu._is_closing = True
                    # Stop any animations and hide immediately
                    if hasattr(self._menu, "_fade_animation"):
                        self._menu._fade_animation.stop()
                    self._menu.hide()
                    self._menu.deleteLater()
                except Exception:
                    pass
                self._menu = None

            if not Clipboard.is_history_enabled():
                self._menu = ClipboardPopup(
                    self,
                    [],
                    self.config,
                    status_message="Clipboard History is disabled.<br>Enable it in Windows Settings (Win+V).",
                )
                self._menu.show_menu()
                return

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

            # Persistent Singleton Popup: Reuse the existing instance or create it once.
            if not self._menu or not is_valid_qobject(self._menu):
                self._menu = ClipboardPopup(self, items, self.config)
            else:
                self._menu._is_closing = False
                self._menu.update_items(items)

            self._menu.show_menu()
        except Exception as e:
            logging.error(f"Async Clipboard Error: {e}")
        finally:
            self._fetching = False

    def toggle_menu(self):
        """Toggle the clipboard history popup menu."""
        try:
            if (
                self._menu
                and is_valid_qobject(self._menu)
                and self._menu.isVisible()
                and not getattr(self._menu, "_is_closing", False)
            ):
                self._menu.hide_animated()
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
            # User can include icons in the string if they want
            flash_text = self.config.copied_feedback
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

    def __init__(
        self, parent_widget: ClipboardWidget, items: list, config: ClipboardConfig, status_message: str = None
    ):
        super().__init__(
            parent_widget,
            blur=config.menu.blur,
            round_corners=config.menu.round_corners,
            round_corners_type=config.menu.round_corners_type,
            border_color=config.menu.border_color,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._parent_widget = parent_widget
        self._all_items = items
        self._status_message = status_message
        self._icons = config.icons
        self._menu_config = config.menu
        self._ui_initialized = False

        self._add_scrollbar_style()
        self._init_ui()

    def _add_scrollbar_style(self):
        """Inject generic QScrollBar styles into the scroll area."""
        self._scrollbar_style = """
            QScrollBar:vertical { border: none; background: transparent; width: 4px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
            QScrollBar::handle:vertical { background: rgba(255, 255, 255, 0.2); min-height: 10px; border-radius: 2px; }
            QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 0.35); }
            QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical { height: 0px; }
        """

    def _init_ui(self):
        """Initialize the popup UI. Guarded to run only once."""
        if self._ui_initialized:
            return
        self._ui_initialized = True

        # 1. Root Layout on self (Window)
        # We use this ONLY to hold the _popup_content frame.
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.addWidget(self._popup_content)

        # 2. Main Layout on _popup_content (The Styled Frame)
        self.main_layout = QVBoxLayout(self._popup_content)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)
        self.setMinimumWidth(320)

        # Ensure the frame is opaque and has the styling class
        self._popup_content.setAutoFillBackground(False)
        self._popup_content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self._popup_content.setProperty("class", "clipboard-menu")

        # Force styling refresh on the frame
        from core.utils.utilities import refresh_widget_style

        refresh_widget_style(self._popup_content)

        # Search bar
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(lambda: self._filter_items(self.search_bar.text()))

        self.search_bar = QLineEdit()
        self.search_bar.setProperty("class", "search-input")
        self.search_bar.setPlaceholderText("Search history...")
        self.search_bar.textChanged.connect(lambda _: self._search_timer.start(150))
        self.main_layout.addWidget(self.search_bar)

        # Clear all
        clear_btn = QPushButton(f"{self._icons.clear_icon} Clear History")
        clear_btn.setProperty("class", "clear-button")
        clear_btn.clicked.connect(lambda: [Clipboard.clear_history(), self.close()])
        self.main_layout.addWidget(clear_btn)

        # Scroll area
        self.scroll = QScrollArea()
        self.scroll.setProperty("class", "scroll-area")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setViewportMargins(0, 0, -4, 0)
        self.scroll.verticalScrollBar().setStyleSheet(self._scrollbar_style)
        self.scroll.viewport().setAutoFillBackground(False)
        self.main_layout.addWidget(self.scroll)

        # Initial render
        self._render_items(self._all_items)

    def update_items(self, items, status_message=None):
        """Update items in the existing popup instance."""
        self._all_items = items
        if status_message:
            self._status_message = status_message

        self.search_bar.blockSignals(True)
        self.search_bar.clear()
        self.search_bar.blockSignals(False)

        self._render_items(items)

    def _render_items(self, items):
        """Render the clipboard items in the popup using the 'Nuclear Swap' method."""
        # Create a brand new container instead of clearing the old one.
        # This is the most robust way to ensure no "stacking" occurs.
        new_container = QWidget()
        new_container.setObjectName("clipboardScrollContent")
        new_container.setStyleSheet("#clipboardScrollContent { background: transparent; }")
        new_container.setAutoFillBackground(False)
        container_layout = QVBoxLayout(new_container)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        # Increase right margin (15) to give scrollbar breathing room
        container_layout.setContentsMargins(5, 5, 15, 5)
        container_layout.setSpacing(6)
        container_layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinimumSize)

        if not items:
            msg = self._status_message if self._status_message else "No items match your search."
            lbl = QLabel(msg)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color: #e74c3c;" if self._status_message else "color: gray;")
            container_layout.addWidget(lbl)
        else:
            max_item_len = self._menu_config.max_item_length
            for item in items:
                row_widget = QWidget()
                row_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                row = QHBoxLayout(row_widget)
                row.setContentsMargins(0, 0, 0, 0)
                row.setSpacing(8)

                btn = QPushButton()
                btn.setProperty("class", "clipboard-item")
                btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

                if item["type"] == "text":
                    clean = item["data"].replace("\n", " ").strip()
                    display = (clean[:max_item_len] + "..") if len(clean) > max_item_len else clean
                    btn.setText(display)
                    btn.setToolTip(item["data"])
                else:
                    # 1. Scale the image for the icon
                    pixmap = item["data"]
                    btn.setIcon(QIcon(pixmap))
                    btn.setIconSize(pixmap.size().scaled(200, 80, Qt.AspectRatioMode.KeepAspectRatio))
                    btn.setText(" [Image]")
                    btn.setProperty("class", "clipboard-item image-item")

                    # 2. Convert Pixmap to Base64 for the ToolTip
                    from PyQt6.QtCore import QBuffer, QByteArray, QIODevice

                    byte_array = QByteArray()
                    buffer = QBuffer(byte_array)
                    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
                    # Use JPG or PNG format for the preview
                    pixmap.save(buffer, "PNG")
                    base64_data = byte_array.toBase64().data().decode()

                    # 3. Set Rich Text HTML ToolTip
                    # You can adjust 'width' here to control the popup size
                    btn.setToolTip(f'<img src="data:image/png;base64,{base64_data}" width="300">')

                btn.clicked.connect(lambda _, i=item: self._parent_widget.set_system_clipboard(i))

                del_btn = QPushButton(self._icons.delete_icon)
                del_btn.setFixedWidth(35)
                del_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                del_btn.setProperty("class", "delete-button")
                del_btn.clicked.connect(lambda _, i=item: self._delete_item(i))
                del_btn.setStyleSheet("""
                    QPushButton {
                        padding: 0px;
                        margin: 0px;
                    }
                """)

                row.addWidget(btn)
                row.addWidget(del_btn)
                del_btn.setFixedHeight(btn.sizeHint().height())
                container_layout.addWidget(row_widget)

        # NUCLEAR SWAP: Swap the old container for the new one
        old_container = self.scroll.takeWidget()
        if old_container:
            old_container.deleteLater()

        self.scroll.setWidget(new_container)
        # Force a resize update to ensure scrollarea knows about the new content
        self.scroll.updateGeometry()

    def _delete_item(self, item_data):
        """Remove a single item from Windows Clipboard History."""
        try:
            success = Clipboard.delete_item_from_history(item_data["raw_item"])
            if not success:
                logging.warning("Windows refused to delete the item.")
        except AttributeError:
            logging.error("Single item deletion is not supported by this WinRT package.")

        # Refresh the UI
        asyncio.create_task(self._parent_widget._fetch_and_show())

    def _filter_items(self, query):
        """Filter clipboard items based on search query."""
        filtered = []
        for i in self._all_items:
            if i["type"] == "text" and query.lower() in i["data"].lower():
                filtered.append(i)
            elif i["type"] == "image" and (not query or query.lower() in "image"):
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
