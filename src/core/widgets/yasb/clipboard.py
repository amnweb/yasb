import asyncio
import logging
import textwrap

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
)

try:
    from winrt.windows.applicationmodel.datatransfer import Clipboard, DataPackage, StandardDataFormats

    HAS_WINRT = True
except ImportError:
    HAS_WINRT = False
    Clipboard = None
    DataPackage = None
    StandardDataFormats = None

from core.utils.tooltip import set_tooltip
from core.utils.utilities import PopupWidget, add_shadow, build_widget_label, is_valid_qobject, refresh_widget_style
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
                                entry["size"] = len(buffer)
                                entry["timestamp"] = item.timestamp
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

        try:
            asyncio.create_task(self._fetch_and_show())
        except Exception as e:
            logging.error(f"Error toggling clipboard menu: {e}")

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

    @staticmethod
    def _hide_tooltips():
        """Hide any active custom tooltips."""
        from core.utils.tooltip import CustomToolTip

        if CustomToolTip._active_tooltip:
            CustomToolTip._active_tooltip.hide()
            CustomToolTip._active_tooltip = None

    def hide_animated(self):
        """Hide the popup and also hide any active tooltips."""
        self._hide_tooltips()
        super().hide_animated()

    def hide(self):
        """Hide the popup and also hide any active tooltips."""
        self._hide_tooltips()
        super().hide()

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

        # Ensure the frame is opaque and has the styling class
        self._popup_content.setAutoFillBackground(False)
        self._popup_content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self._popup_content.setProperty("class", "clipboard-menu")

        # Force styling refresh on the frame
        refresh_widget_style(self._popup_content)

        # Search bar
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(lambda: self._filter_items(self.search_bar.text()))

        self.search_bar = QLineEdit()
        self.search_bar.setProperty("class", "search-input")
        self.search_bar.setPlaceholderText("Search history...")
        self.search_bar.textChanged.connect(lambda _: (self._hide_tooltips(), self._search_timer.start(150)))
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
        new_container = QFrame()
        new_container.setProperty("class", "clipboard-scroll-content")
        container_layout = QVBoxLayout(new_container)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        container_layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinimumSize)

        if not items:
            msg = self._status_message if self._status_message else "No items match your search."
            lbl = QLabel(msg)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setWordWrap(True)
            lbl.setProperty("class", "status-message error" if self._status_message else "status-message empty")
            container_layout.addWidget(lbl)
        else:
            max_item_len = self._menu_config.max_item_length
            for item in items:
                # Create item container with horizontal layout
                item_container = QFrame()
                item_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                item_container.setProperty("class", "clipboard-item")
                item_layout = QHBoxLayout(item_container)
                item_layout.setContentsMargins(0, 0, 0, 0)
                item_layout.setSpacing(0)

                # Content area (button + optional info)
                content_area = QFrame()
                content_area.setProperty("class", "clipboard-item-content")
                content_layout = QHBoxLayout(content_area)
                content_layout.setContentsMargins(0, 0, 0, 0)
                content_layout.setSpacing(0)

                btn = QPushButton()

                if item["type"] == "text":
                    clean = item["data"].replace("\n", " ").strip()
                    display = (clean[:max_item_len] + "..") if len(clean) > max_item_len else clean
                    btn.setText(display)
                    btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                    btn.setProperty("class", "clipboard-item-btn text-item")
                    if self._menu_config.tooltip_enabled:
                        # Wrap long text to prevent tooltip from spanning screens, limit to 750 chars
                        max_chars = 750
                        display_text = item["data"][:max_chars] + ("..." if len(item["data"]) > max_chars else "")
                        wrapped_text = "<br>".join(textwrap.wrap(display_text, width=50))
                        set_tooltip(
                            item_container,
                            wrapped_text,
                            delay=self._menu_config.tooltip_delay,
                            position=self._menu_config.tooltip_position,
                        )
                else:
                    # Show thumbnail OR replacement text based on config
                    pixmap = item["data"]
                    btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                    btn.setProperty("class", "clipboard-item-btn image-item")
                    if self._menu_config.show_image_thumbnail:
                        btn.setIcon(QIcon(pixmap))
                        btn.setIconSize(pixmap.size().scaled(200, 80, Qt.AspectRatioMode.KeepAspectRatio))
                        btn.setText("")
                    else:
                        btn.setText(f" {self._menu_config.image_replacement_text}")

                btn.clicked.connect(lambda _, i=item: self._parent_widget.set_system_clipboard(i))

                # Make entire content_area clickable to copy the item
                def copy_on_click(event, itm=item):
                    self._parent_widget.set_system_clipboard(itm)

                content_area.mousePressEvent = copy_on_click

                # Add image info stacked vertically
                if item["type"] == "image" and self._menu_config.show_image_list_info:
                    pixmap = item["data"]
                    dims = f"{pixmap.width()} x {pixmap.height()}"
                    size_kb = item.get("size", 0) / 1024
                    timestamp = item.get("timestamp")

                    # Create a vertical layout for the info (stacked)
                    info_container = QFrame()
                    info_container.setProperty("class", "clipboard-item-info")
                    info_layout = QVBoxLayout(info_container)

                    dims_label = QLabel(dims)
                    dims_label.setProperty("class", "image-list-info")
                    info_layout.addWidget(dims_label)

                    size_label = QLabel(f"{size_kb:.1f} KB")
                    size_label.setProperty("class", "image-list-info")
                    info_layout.addWidget(size_label)

                    if timestamp:
                        try:
                            date_str = timestamp.astimezone().strftime("%Y-%m-%d %H:%M")
                            date_label = QLabel(date_str)
                            date_label.setProperty("class", "image-list-info")
                            info_layout.addWidget(date_label)
                        except Exception:
                            pass

                    # Add widgets in order based on config
                    if self._menu_config.image_info_position == "left":
                        content_layout.addWidget(info_container)
                        content_layout.addWidget(btn)
                    else:
                        content_layout.addWidget(btn)
                        content_layout.addWidget(info_container)
                else:
                    # Text items or image without info
                    content_layout.addWidget(btn)

                del_btn = QPushButton(self._icons.delete_icon)
                del_btn.setProperty("class", "delete-button")
                del_btn.clicked.connect(lambda _, i=item: self._delete_item(i))

                item_layout.addWidget(content_area)
                item_layout.addWidget(del_btn)
                item_layout.setAlignment(del_btn, Qt.AlignmentFlag.AlignVCenter)

                container_layout.addWidget(item_container)

        # Refresh styles on all newly created widgets
        refresh_widget_style(new_container)

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
        try:
            asyncio.create_task(self._parent_widget._fetch_and_show())
        except Exception as e:
            logging.error(f"Error refreshing clipboard after delete: {e}")

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
