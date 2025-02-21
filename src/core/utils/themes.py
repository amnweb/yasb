import os
import subprocess
import sys
import requests
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QLabel, QScrollArea, QFrame, QHBoxLayout, QPushButton, QMessageBox, QDialog)
from PyQt6.QtGui import QPixmap, QFont, QDesktopServices, QIcon
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, QTimer, QPropertyAnimation
from PyQt6.QtWidgets import QGraphicsOpacityEffect

class ImageLoader(QThread):
    finished = pyqtSignal(str, bytes)

    def __init__(self, theme_id, url):
        super().__init__()
        self.theme_id = theme_id
        self.url = url

    def run(self):
        try:
            response = requests.get(self.url)
            self.finished.emit(self.theme_id, response.content)
        except:
            pass


class ThemeLoader(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def run(self):
        try:
            url = "https://raw.githubusercontent.com/amnweb/yasb-themes/refs/heads/main/themes.json"
            response = requests.get(url)
            response.raise_for_status()
            themes = response.json()
            self.finished.emit(themes)
        except Exception as e:
            self.error.emit(str(e))


class ThemeCard(QFrame):
    def __init__(self, theme_data):
        super().__init__()

        self.theme_data = theme_data
        self.setObjectName("themeCard")
        self.setStyleSheet("""
            #themeCard {
                background-color:rgba(0, 0, 0, 0.1);
                border:1px solid #333;
                border-radius: 8px;
                margin: 0 5px 10px 5px;
                padding: 5px;
            }
        """)
        self.dragging = False
        self.last_x = 0
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Create horizontal layout for name and buttons
        top_layout = QHBoxLayout()

        # Name label (left-aligned)
        name = QLabel(self.theme_data["name"])
        name.setOpenExternalLinks(True)
        name.setFont(QFont('Segoe UI', 16, QFont.Weight.Bold))
        top_layout.addWidget(name)

        # Download button (right-aligned)
        download_btn = QPushButton("Download")
        download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        download_btn.setFixedWidth(80)
        download_btn.setStyleSheet("""
            QPushButton {
                background-color: #2c323b;
                border: 1px solid #363e49;
                color: white;
                padding: 3px 5px;
                margin-top:10px;
                border-radius: 4px;
                font-family: 'Segoe UI';
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #393f47;
            }
        """)
        top_layout.addWidget(download_btn)
        download_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl(f"https://github.com/amnweb/yasb-themes/tree/main/themes/{self.theme_data['id']}")
            )
        )

        # Install button
        install_btn = QPushButton("Install")
        install_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        install_btn.setFixedWidth(80)
        install_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078D4;
                border: 1px solid #0884e2;
                color: white;
                padding: 3px 5px;
                margin-top:10px;
                border-radius: 4px;
                font-family: 'Segoe UI';
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0884e2;
            }
            QPushButton:pressed {
                background-color: #0f8dee;
            }
        """)
        top_layout.addWidget(install_btn)
        install_btn.clicked.connect(lambda: self.install_theme())

        # Add the horizontal layout to the main layout
        layout.addLayout(top_layout)

        # Author label
        homepage = self.theme_data['homepage'] if self.theme_data['homepage'] else f'https://github.com/{self.theme_data['author']}'
        author = QLabel(f"author <a style=\"color:#0078D4;font-weight:500;text-decoration:none\" href='{homepage}'>{self.theme_data['author']}</a>")
        author.setFont(QFont('Segoe UI', 10))
        author.setOpenExternalLinks(True)
        layout.addWidget(author)

        # Description label
        description = QLabel(self.theme_data['description'])
        description.setWordWrap(True)
        description.setFont(QFont('Segoe UI', 10))
        opacity_effect = QGraphicsOpacityEffect()
        opacity_effect.setOpacity(0.75)
        description.setGraphicsEffect(opacity_effect)

        layout.addWidget(description)

        # Scroll area for image
        self.scroll = QScrollArea()
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidgetResizable(False)
        
        layout.addWidget(self.scroll)

        # Image container
        self.image_label = QLabel()
        self.image_label.setMouseTracking(True)
        self.image_label.setCursor(Qt.CursorShape.OpenHandCursor)
        self.scroll.setWidget(self.image_label)

        if 'image' in self.theme_data:
            self.load_image()

    def load_image(self):
        self.loader = ImageLoader(self.theme_data['id'], self.theme_data['image'])
        self.loader.finished.connect(self.set_image)
        self.loader.start()

    def set_image(self, theme_id, image_data):
        if theme_id == self.theme_data['id']:
            pixmap = QPixmap()
            if image_data and pixmap.loadFromData(image_data):
                # Scale image to 60px height to fit the scroll area
                set_scale = 1.2
                self.scroll.setFixedHeight(int(pixmap.height() * set_scale))  
                resized_pixmap = pixmap.scaled(
                    int(1920 * set_scale),
                    int(pixmap.height() * set_scale),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.image_label.setPixmap(resized_pixmap)
                self.image_label.setFixedSize(resized_pixmap.size())
            else:
                self.image_label.setText("Invalid image")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.last_x = event.pos().x()
            self.image_label.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            self.image_label.setCursor(Qt.CursorShape.OpenHandCursor)

    def mouseMoveEvent(self, event):
        if self.dragging:
            delta = self.last_x - event.pos().x()
            self.scroll.horizontalScrollBar().setValue(
                self.scroll.horizontalScrollBar().value() + delta
            )
            self.last_x = event.pos().x()

    def install_theme(self):
        # Create a custom styled dialog for the confirmation
        dialog = QDialog(self)
        dialog.setWindowTitle("Install Theme")
        dialog.setModal(True)
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets', 'images', 'app_icon.png')
        icon = QIcon(icon_path)
        dialog.setWindowIcon(QIcon(icon.pixmap(48, 48)))

        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        # Apply styles to the dialog
        dialog.setStyleSheet("""
            QLabel {
                font-size: 12px;
                padding: 10px;
                font-family: 'Segoe UI';
            }
        """)
        layout = QVBoxLayout(dialog)

        confirmation_message = QLabel(f"Are you sure you want to install the theme <b>{self.theme_data['name']}</b>?<br/>This will overwrite your current config and styles files.")
        layout.addWidget(confirmation_message, alignment=Qt.AlignmentFlag.AlignCenter)

        # Add Yes and No buttons
        button_layout = QHBoxLayout()

        yes_button = QPushButton("Install")
        yes_button.setCursor(Qt.CursorShape.PointingHandCursor)
        yes_button.clicked.connect(dialog.accept)
        yes_button.setStyleSheet("""
            QPushButton {
                background-color: #0078D4;
                border: 1px solid #0884e2;
                color: white;
                padding: 4px 16px;
                border-radius: 4px;
                font-family: 'Segoe UI';
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #0884e2;
            }
            QPushButton:focus {
                outline: none;
            }
            QPushButton:pressed {
                background-color: #0f8dee;
            }
        """)
        no_button = QPushButton("Cancel")
        no_button.setCursor(Qt.CursorShape.PointingHandCursor)
        no_button.setObjectName("cancelButton")
        no_button.clicked.connect(dialog.reject)
        no_button.setStyleSheet("""
            QPushButton {
                background-color: #2c323b;
                border: 1px solid #363e49;
                color: white;
                padding: 4px 16px;
                border-radius: 4px;
                font-family: 'Segoe UI';
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #393f47;
            }
            QPushButton:focus {
                outline: none;
            }
            QPushButton:pressed {
                background-color: #2c323b;
            }
        """)
        button_layout.addStretch()
        button_layout.addWidget(yes_button)
        button_layout.addWidget(no_button)
        button_layout.addStretch()

        layout.addLayout(button_layout)

        # Show the dialog and check the user's response
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                subprocess.run(["yasbc", "stop"], creationflags=subprocess.CREATE_NO_WINDOW, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                # Define the URLs for the files
                base_url = f"https://raw.githubusercontent.com/amnweb/yasb-themes/main/themes/{self.theme_data['id']}"
                config_url = f"{base_url}/config.yaml"
                styles_url = f"{base_url}/styles.css"

                config_home = os.getenv('YASB_CONFIG_HOME') if os.getenv('YASB_CONFIG_HOME') else os.path.join(os.path.expanduser("~"), ".config", "yasb")
                config_path = os.path.join(config_home, "config.yaml")
                styles_path = os.path.join(config_home, "styles.css")

                # Create the directory if it doesn't exist
                os.makedirs(os.path.dirname(config_path), exist_ok=True)

                # Download and save the styles.css file
                styles_response = requests.get(styles_url)
                styles_response.raise_for_status()
                with open(styles_path, 'wb') as styles_file:
                    styles_file.write(styles_response.content)

                # Download and save the config.yaml file
                config_response = requests.get(config_url)
                config_response.raise_for_status()
                with open(config_path, 'wb') as config_file:
                    config_file.write(config_response.content)
                subprocess.run(["yasbc", "start"], creationflags=subprocess.CREATE_NO_WINDOW, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            except Exception as e:
                QMessageBox.critical(self, 'Error', f"Failed to install theme: {str(e)}")


class ThemeViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YASB Theme Gallery")
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets', 'images', 'app_icon.png')
        icon = QIcon(icon_path)
        self.setWindowIcon(QIcon(icon.pixmap(48, 48)))
        screen = QApplication.primaryScreen().geometry()
        width = 920
        height = 800
 
        # Calculate center position
        x = (screen.width() - width) // 2
        y = (screen.height() - height) // 2
        # Set window geometry
        self.setGeometry(x, y, width, height)
        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Add the placeholder label
        self.placeholder_label = QLabel("<span style='font-weight:700'>YASB</span> Reborn")
        self.placeholder_label.setFont(QFont('Segoe UI', 64, QFont.Weight.Normal))
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.placeholder_label)

        config_home = os.getenv('YASB_CONFIG_HOME') if os.getenv('YASB_CONFIG_HOME') else os.path.join(os.path.expanduser("~"), ".config", "yasb")
        self.backup_info = QLabel(f"Backup your current theme before installing a new one. You can do this by copying the <b>config.yaml</b> and <b>styles.css</b> files from the <b><i>{config_home}</i></b> directory to a safe location.")
        self.backup_info.setWordWrap(True)
        self.backup_info.setStyleSheet("color:#fff; background-color: rgba(166, 16, 48, 0.3);border-radius:6px;border:1px solid rgba(166, 16, 48, 0.5);padding:4px 8px;font-size:11px;font-family:'Segoe UI';margin:14px 20px 0 14px")
        self.backup_info.hide()
        layout.addWidget(self.backup_info)

        # Setup scroll area but hide it initially
        self.scroll = QScrollArea()

        self.scroll.setWidgetResizable(True)
        self.setStyleSheet("""
            QScrollArea {
                background-color:transparent;
                border: none;
            }
            QScrollBar:vertical {
                border: none;
                background:transparent;
                width: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #30363d;
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical {
                height: 0px;
            }
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        layout.addWidget(self.scroll)
        self.scroll.hide()

        container = QWidget()
        self.container_layout = QVBoxLayout(container)
        self.container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(container)

        # Initialize flags for minimum display time
        self.themes_loaded = False
        self.timer_elapsed = False

        # Start loading themes
        self.load_themes()

        # Start a timer for minimum 3 seconds display
        self.minimum_display_timer = QTimer(self)
        self.minimum_display_timer.setSingleShot(True)
        self.minimum_display_timer.timeout.connect(self.on_minimum_time_elapsed)
        self.minimum_display_timer.start(3000)

            
    def load_themes(self):
        self.theme_loader = ThemeLoader()
        self.theme_loader.finished.connect(self.on_themes_loaded)
        self.theme_loader.error.connect(self.on_load_error)
        self.theme_loader.start()

    def on_themes_loaded(self, themes):
        self.themes_loaded = True
        self.themes = themes
        self.check_loading_complete()

    def on_load_error(self, error_message):
        self.themes_loaded = True
        self.load_error_message = error_message
        self.check_loading_complete()

    def on_minimum_time_elapsed(self):
        self.timer_elapsed = True
        self.check_loading_complete()

    def check_loading_complete(self):
        if self.themes_loaded and self.timer_elapsed:
            if hasattr(self, 'load_error_message'):
                self.placeholder_label.setText("Failed to load themes.")
                self.placeholder_label.setFont(QFont('Segoe UI', 14))
                QMessageBox.critical(self, 'Error', f"Error loading themes: {self.load_error_message}")
            else:
                # Fade out placeholder_label
                self.placeholder_opacity = QGraphicsOpacityEffect()
                self.placeholder_label.setGraphicsEffect(self.placeholder_opacity)
                self.fade_out = QPropertyAnimation(self.placeholder_opacity, b"opacity")
                self.fade_out.setDuration(400)
                self.fade_out.setStartValue(1)
                self.fade_out.setEndValue(0)
                self.fade_out.finished.connect(self.on_fade_out_complete)
                self.fade_out.start()

    def on_fade_out_complete(self):
        self.placeholder_label.hide()
        self.backup_info.show()
        self.scroll.show()
        for theme_id, theme in self.themes.items():
            theme['id'] = theme_id
            theme_card = ThemeCard(theme)
            self.container_layout.addWidget(theme_card)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    viewer = ThemeViewer()
 
    viewer.show()
    sys.exit(app.exec())