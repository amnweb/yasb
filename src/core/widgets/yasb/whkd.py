import logging
import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
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

from core.utils.alert_dialog import raise_info_alert
from core.utils.utilities import add_shadow, build_widget_label, refresh_widget_style
from core.utils.widgets.animation_manager import AnimationManager
from core.validation.widgets.yasb.whkd import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget
from settings import SCRIPT_PATH


class KeybindsDialog(QDialog):
    def __init__(self, content, file_path, animation, special_keys, parent=None):
        super().__init__(parent)

        self.file_path = file_path
        self.original_content = content
        self.animation = animation
        self.special_keys = special_keys or {}
        self.setWindowTitle("WHKD Keybinds")
        self.setProperty("class", "whkd-popup")

        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        icon_path = os.path.join(SCRIPT_PATH, "assets", "images", "app_icon.png")
        icon = QIcon(icon_path)
        self.setWindowIcon(QIcon(icon.pixmap(48, 48)))
        self.setMinimumHeight(800)

        self.main_layout = QVBoxLayout(self)

        # Filter input
        self.filter_input = QLineEdit()
        self.filter_input.setProperty("class", "filter-input")
        self.filter_input.setPlaceholderText("Type to filter keybinds...")
        self.filter_input.textChanged.connect(self.update_display)
        self.main_layout.addWidget(self.filter_input)

        # Scroll area for keybind rows
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("whkd_scroll_area")
        self.scroll_area.setStyleSheet("""
            QScrollArea#whkd_scroll_area {
                border: 0;
                background-color: transparent;
            }
            QScrollBar:vertical {
                width: 4px;
                margin: 0px;
                border: 0;
                background-color: transparent;
            }
            QScrollBar:vertical:hover {
                width: 0px;
                background-color: transparent;
            }
            QScrollBar::handle:vertical {
                background-color: rgba(255,255,255,0.2);
                min-height: 20px;
                border-radius: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: rgba(255,255,255,0.4);
            }
            QScrollBar::add-line:vertical {
                height: 0;
            }
            QScrollBar::sub-line:vertical {
                height: 0;
            }
            QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {
                border: 0;
                width: 0;
                height: 0;
                image: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        self.scroll_area.setWidgetResizable(True)

        self.main_layout.addWidget(self.scroll_area)

        self.container = QWidget()
        self.container.setObjectName("whkd_container_area")
        self.container.setStyleSheet("QWidget#whkd_container_area{background-color: transparent;border:none;}")
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.container)

        # Edit config file button
        self.btn_open = QPushButton("Edit Config File")
        self.btn_open.setProperty("class", "edit-config-button")
        self.btn_open.clicked.connect(lambda: os.startfile(self.file_path))
        self.main_layout.addWidget(self.btn_open)

        self.update_display()

        self.setMinimumWidth(self.calculate_content_width())

        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def calculate_content_width(self):
        min_width = 400
        # Inspect all keybind rows to find the widest one
        for i in range(self.container_layout.count()):
            item = self.container_layout.itemAt(i)
            if item and item.widget():
                # Get the sizeHint width of each row
                row_width = item.widget().sizeHint().width()
                min_width = max(min_width, row_width + 50)

                # If this is a keybind row with buttons and command, check their widths too
                if isinstance(item.widget(), QWidget) and hasattr(item.widget(), "layout"):
                    row_layout = item.widget().layout()
                    if row_layout:
                        width_sum = 0
                        for j in range(row_layout.count()):
                            child_item = row_layout.itemAt(j)
                            if child_item and child_item.widget():
                                width_sum += child_item.widget().sizeHint().width()
                        min_width = max(min_width, width_sum + 70)

        # Add margins to account for the dialog's layout
        margins = self.main_layout.contentsMargins()
        min_width += margins.left() + margins.right()

        # Cap the width at 80% of screen width
        screen_width = QApplication.primaryScreen().geometry().width()
        return min(min_width, int(screen_width * 0.8))

    def update_display(self):
        no_plus_modifiers = {key.lower() for key in self.special_keys.keys()}
        # Clear any existing content
        for i in reversed(range(self.container_layout.count())):
            self.widget = self.container_layout.itemAt(i).widget()
            if self.widget:
                self.widget.deleteLater()

        filter_text = self.filter_input.text().lower()
        for keybind, command in self.original_content:
            if (
                filter_text
                and filter_text not in (keybind.lower() if keybind else "")
                and filter_text not in command.lower()
            ):
                continue

            if keybind is None:
                # Render header
                self.header = QLabel(command)
                self.header.setProperty("class", "keybind-header")

                self.container_layout.addWidget(self.header)
            else:
                # Render keybind row
                self.row = QWidget()
                self.row.setProperty("class", "keybind-row")
                self.row_layout = QHBoxLayout(self.row)

                self.row_layout.setContentsMargins(5, 5, 5, 5)
                self.row_layout.setSpacing(0)
                self.row_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

                # Create a container widget for buttons
                # Create a container widget for buttons
                buttons_container = QWidget(self.row)
                buttons_container.setProperty("class", "keybind-buttons-container")

                buttons_layout = QHBoxLayout(buttons_container)
                buttons_layout.setContentsMargins(0, 0, 0, 0)

                buttons_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

                def create_key_button(key_text):
                    btn = QPushButton(self._friendly_key_text(key_text.lower()))
                    if key_text.lower() in self.special_keys:
                        btn.setProperty("class", "keybind-button special")
                    else:
                        btn.setProperty("class", "keybind-button")
                    btn.setFixedHeight(28)
                    btn.setMinimumWidth(28)
                    btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                    buttons_layout.addWidget(btn)
                    refresh_widget_style(btn)
                    return btn

                if " + " in keybind:
                    groups = keybind.split(" + ")
                    for idx, group in enumerate(groups):
                        keys = group.split()
                        for key in keys:
                            create_key_button(key)

                        # Add plus button between groups if needed
                        if idx < len(groups) - 1:
                            next_keys = groups[idx + 1].split()
                            if not (
                                keys
                                and next_keys
                                and (
                                    keys[-1].lower() in no_plus_modifiers and next_keys[0].lower() in no_plus_modifiers
                                )
                            ):
                                plus_btn = QPushButton("+")
                                plus_btn.setEnabled(False)
                                plus_btn.setProperty("class", "plus-separator")
                                plus_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                                buttons_layout.addWidget(plus_btn)
                else:
                    keys = [k.strip() for k in keybind.split("+")]
                    for key in keys:
                        create_key_button(key)

                # Add the buttons container to the row
                self.row_layout.addWidget(buttons_container)

                # The command label
                self.command_label = QLabel(command)
                self.command_label.setProperty("class", "keybind-command")
                self.row_layout.addWidget(self.command_label)

                self.container_layout.addWidget(self.row)
                refresh_widget_style(self.row)

    def _friendly_key_text(self, k: str) -> str:
        return self.special_keys.get(k.lower(), k)


class WhkdWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
        self,
        label: str,
        animation: dict[str, str],
        special_keys: list = None,
        container_padding: dict = None,
        callbacks: dict = None,
        label_shadow: dict = None,
        container_shadow: dict = None,
    ):
        super().__init__(class_name="whkd-widget")
        self._label_content = label
        self._padding = container_padding
        self._animation = animation
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow
        # Handle the case where special_keys is not provided - initialize as empty
        special_keys = special_keys or []
        self._special_keys = {item["key"]: item["key_replace"] for item in special_keys}
        # Construct container
        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(
            self._padding["left"], self._padding["top"], self._padding["right"], self._padding["bottom"]
        )
        # Initialize container
        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self._container_shadow)

        # Add the container to the main widget layout
        self.widget_layout.addWidget(self._widget_container)

        build_widget_label(self, self._label_content, None, self._label_shadow)

        self.register_callback("open_popup", self._open_popup)
        callbacks = {"on_left": "open_popup"}
        self.callback_left = callbacks["on_left"]

    def _open_popup(self):
        if self._animation.get("enabled"):
            AnimationManager.animate(self, self._animation.get("type"), self._animation.get("duration"))

        # Determine config file location
        whkd_config_home = os.getenv("WHKD_CONFIG_HOME")
        file_path = (
            os.path.join(whkd_config_home, "whkdrc")
            if whkd_config_home
            else os.path.join(os.path.expanduser("~"), ".config", "whkdrc")
        )
        if not os.path.exists(file_path):
            logging.error(f"File not found: {file_path}")
            raise_info_alert(
                title="Error",
                msg=f"The specified file does not exist\n{file_path}",
                informative_msg="Please make sure the file exists and try again.",
                rich_text=True,
            )
            return

        # Read and process the configuration file
        try:
            with open(file_path, "r") as f:
                raw_lines = f.readlines()
        except Exception as e:
            logging.error(f"Error reading file: {e}")
            return

        content = self._process_file(raw_lines)
        dialog = KeybindsDialog(content, file_path, self._animation, self._special_keys, self)
        dialog.exec()

    def _process_file(self, lines):
        # Filter lines: keep headers and non-comment lines
        filtered_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("##"):
                filtered_lines.append(stripped)
            elif not (stripped.startswith("#") or stripped.startswith(".shell")):
                # Remove inline comments; only add non-empty lines
                line_no_comment = line.split("#")[0].strip()
                if line_no_comment:
                    filtered_lines.append(line_no_comment)

        # Format the filtered lines into content tuples
        formatted_lines = []
        for line in filtered_lines:
            # Check if line is a header
            if line.startswith("##"):
                header_text = line.lstrip("#").strip()
                formatted_lines.append((None, header_text))
            elif ":" in line:
                keybind, command = line.split(":", 1)
                formatted_lines.append((keybind.strip(), command.strip()))
        return formatted_lines
