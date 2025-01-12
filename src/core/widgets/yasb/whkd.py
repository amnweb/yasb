import re
import os
import logging
from core.utils.alert_dialog import raise_info_alert
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.whkd import VALIDATION_SCHEMA
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QWidget, QApplication, QSizePolicy, QVBoxLayout, QScrollArea, QPushButton, QLineEdit
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor, QIcon
from core.utils.widgets.animation_manager import AnimationManager

class WhkdWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
            self,
            label: str,
            animation: dict[str, str],
            container_padding: dict
        ):
        super().__init__(class_name="whkd-widget")
        self._label_content = label
        self._padding = container_padding
        self._animation = animation
        # Construct container
        self._widget_container_layout: QHBoxLayout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(self._padding['left'],self._padding['top'],self._padding['right'],self._padding['bottom'])
        # Initialize container
        self._widget_container: QWidget = QWidget()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        # Add the container to the main widget layout
        self.widget_layout.addWidget(self._widget_container)
        self._create_dynamically_label(self._label_content)
        self._popup_window = None  # Initialize the popup window

    def _create_dynamically_label(self, content: str):
        def process_content(content, is_alt=False):
            label_parts = re.split('(<span.*?>.*?</span>)', content)
            label_parts = [part for part in label_parts if part]
            widgets = []
            for part in label_parts:
                part = part.strip()
                if not part:
                    continue
                if '<span' in part and '</span>' in part:
                    class_name = re.search(r'class=(["\'])([^"\']+?)\1', part)
                    class_result = class_name.group(2) if class_name else 'icon'
                    icon = re.sub(r'<span.*?>|</span>', '', part).strip()
                    label = QLabel(icon)
                    label.setProperty("class", class_result)
                    label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                else:
                    label = QLabel(part)
                    label.setProperty("class", "label")
                    label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self._widget_container_layout.addWidget(label)
                widgets.append(label)
                label.show()
                label.mousePressEvent = self.show_popup
            return widgets
        self._widgets = process_content(content)

    def show_popup(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._animation['enabled']:
                AnimationManager.animate(self, self._animation['type'], self._animation['duration'])
                
            if self._popup_window is not None:
                try:
                    self._popup_window.deleteLater()
                except RuntimeError:
                     self._popup_window = None

            # Check if WHKD_CONFIG_HOME exists in the environment variables and use it as the default path
            whkd_config_home = os.getenv('WHKD_CONFIG_HOME')
            if whkd_config_home:
                file_path = os.path.join(whkd_config_home, 'whkdrc')
            else:
                file_path = os.path.join(os.path.expanduser('~'), '.config', 'whkdrc')
                
            if not os.path.exists(file_path):
                logging.error(f"File not found: {file_path}")
                raise_info_alert(
                    title=f"Error",
                    msg=f"The specified file does not exist\n{file_path}",
                    informative_msg=f"Please make sure the file exists and try again.",
                    rich_text=True
                )
                return

            filtered_lines = self.read_and_filter_file(file_path)
            formatted_content = self.format_content(filtered_lines)

            self._popup_window = KeybindsWindow(formatted_content, file_path)
            self._popup_window.show()

    def read_and_filter_file(self, file_path):
        with open(file_path, 'r') as file:
            lines = file.readlines()
        filtered_lines = []
        for line in lines:
            if not (line.strip().startswith('#') or line.strip().startswith('.shell')):
                # Remove inline comments
                line = line.split('#')[0].strip()
                if line:  # Only add non-empty lines
                    filtered_lines.append(line)
        return filtered_lines

    def format_content(self, lines):
        formatted_lines = []
        for line in lines:
            if ':' in line:
                keybind, command = line.split(':', 1)
                keybind = keybind.strip()
                command = command.strip()
                formatted_lines.append((keybind, command))
        return formatted_lines

class KeybindWidget(QWidget):
    def __init__(self, keybind, command):
        super().__init__()
        self.initUI(keybind, command)

    def initUI(self, keybind, command):
        container = QWidget()
        container.setObjectName("keybindContainer")
        layout = QHBoxLayout()
        
        keybind_label = QLabel(keybind)
        keybind_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        keybind_label.setStyleSheet("""
            background-color: #3a3a3a;
            color: white;
            padding: 4px 8px;
            font-size: 15px;
            font-weight: bold;
            border-radius: 4px;
            max-height: 24px;
            font-family: 'Segoe UI', sans-serif;
        """)
        command_label = QLabel(command)
        command_label.setStyleSheet("""
            padding:4px;
            font-size: 14px;
            font-family: 'Segoe UI', sans-serif;
        """)
        layout.addWidget(keybind_label)
        layout.addWidget(command_label)
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)
        container.setLayout(layout)
        
        container.setStyleSheet("""
            QWidget#keybindContainer {
                background-color: transparent;
                border-radius: 4px;
                border:1px solid transparent;
            }
            QWidget#keybindContainer:hover {
                background-color: #3a3a3a;
                border:1px solid #53545a;
            }
        """)
        main_layout = QVBoxLayout()
        main_layout.addWidget(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(main_layout)
        
 
        # Adjust the width of the keybind_label based on its content
        keybind_label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        keybind_label.setMinimumWidth(keybind_label.sizeHint().width())

class KeybindsWindow(QWidget):
    def __init__(self, content, file_path):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.file_path = file_path
        self.original_content = content  # Store the original content
        self.initUI(content)

    def initUI(self, content):
        self.setWindowTitle('WHKD Keybinds')
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), 'assets', 'images', 'app_icon.png')
        icon = QIcon(icon_path)
        self.setWindowIcon(QIcon(icon.pixmap(48, 48)))
        # Get screen size and set window center
        screen = QApplication.primaryScreen()
        screen_size = screen.size()
        window_width = 720
        window_height = 640
        self.setGeometry(
            (screen_size.width() - window_width) // 2,
            (screen_size.height() - window_height) // 2,
            window_width,
            window_height
        )

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)  # Align items to the top
        layout.setSpacing(5)  # Set spacing between items if needed
        # Add input field for filtering
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Type to filter keybinds...")
        self.filter_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                font-size: 16px;
                font-family: 'Segoe UI', sans-serif;
                border: 1px solid transparent;
                border-radius: 4px;
                outline: none; 
            }
            QLineEdit:focus {
            border: 1px solid #0078D4;
            }
        """)
        self.filter_input.setFixedHeight(40)
        self.filter_input.textChanged.connect(self.filter_keybinds)
        layout.addWidget(self.filter_input)

        # Create a scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        # Get the window's background color
        
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                border: 0;
            }}
            QScrollBar:vertical {{
                width: 4px;
                margin: 0px;
                border: 0;
            }}
            QScrollBar::handle:vertical {{
                background-color: #555;
                min-height: 20px;
                border-radius: 2px;
            }}
            QScrollBar::add-line:vertical {{
                height: 0;
            }}
            QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {{
                border: 0;
                width: 0;
                height: 0;
                image: none;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
        """)

        # Create a widget to hold the keybind widgets
        self.container = QWidget()
        self.container_layout = QVBoxLayout()
        self.container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        # Add each formatted line as a KeybindWidget
        self.add_keybind_widgets(content)

        self.container.setLayout(self.container_layout)
        self.scroll_area.setWidget(self.container)

        layout.addWidget(self.scroll_area)

        # Add a button to open the file in the default text editor
        open_button = QPushButton("Edit Config File")
        open_button.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                font-size: 12px;
                font-weight: bold;
                background-color: #3a3a3a;
                color: white;
                border: 0;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0078D4;
            }
        """)
        open_button.clicked.connect(self.open_file)
        layout.addWidget(open_button)
        self.setLayout(layout)

    def add_keybind_widgets(self, content):
        # Clear existing widgets
        for i in reversed(range(self.container_layout.count())):
            widget = self.container_layout.itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)

        # Add each formatted line as a KeybindWidget
        for keybind, command in content:
            keybind_widget = KeybindWidget(keybind, command)
            self.container_layout.addWidget(keybind_widget)

    def filter_keybinds(self, text):
        filtered_content = [
            (keybind, command) for keybind, command in self.original_content
            if text.lower() in keybind.lower() or text.lower() in command.lower()
        ]
        self.add_keybind_widgets(filtered_content)

    def open_file(self):
        os.startfile(self.file_path)

    def closeEvent(self, event):
        if hasattr(self, 'container'):
            for i in reversed(range(self.container_layout.count())):
                widget = self.container_layout.itemAt(i).widget()
                if widget:
                    widget.deleteLater()
        self.container_layout = None
        self.container = None
        self.scroll_area = None
        self.filter_input = None
        super().closeEvent(event)