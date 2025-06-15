import os
import re
import shutil
import subprocess
import sys
import urllib.request
from typing import Dict

from PyQt6.QtCore import QPropertyAnimation, Qt, QThread, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QFont, QFontDatabase, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from settings import SCRIPT_PATH


class ImageLoader(QThread):
    finished = pyqtSignal(str, bytes)

    def __init__(self, theme_id, url):
        super().__init__()
        self.theme_id = theme_id
        self.url = url

    def run(self):
        try:
            with urllib.request.urlopen(self.url) as response:
                data = response.read()
            self.finished.emit(self.theme_id, data)
        except Exception:
            pass


class ThemeLoader(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def run(self):
        try:
            url = "https://raw.githubusercontent.com/amnweb/yasb-themes/refs/heads/main/themes.json"
            with urllib.request.urlopen(url) as response:
                import json

                themes = json.loads(response.read().decode("utf-8"))
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
        name.setFont(QFont("Segoe UI", 18, QFont.Weight.DemiBold))
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
        homepage = (
            self.theme_data["homepage"]
            if self.theme_data["homepage"]
            else f"https://github.com/{self.theme_data['author']}"
        )
        author = QLabel(
            f"author <a style=\"color:#239af5;font-weight:600;text-decoration:none\" href='{homepage}'>{self.theme_data['author']}</a>"
        )
        author.setFont(QFont("Segoe UI", 10))
        author.setOpenExternalLinks(True)
        layout.addWidget(author)

        # Description label
        description = QLabel(self.theme_data["description"])
        description.setWordWrap(True)
        description.setFont(QFont("Segoe UI", 10))
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

        if "image" in self.theme_data:
            self.load_image()

    def load_image(self):
        self.loader = ImageLoader(self.theme_data["id"], self.theme_data["image"])
        self.loader.finished.connect(self.set_image)
        self.loader.start()

    def set_image(self, theme_id, image_data):
        if theme_id == self.theme_data["id"]:
            pixmap = QPixmap()
            if image_data and pixmap.loadFromData(image_data):
                screen = QApplication.primaryScreen()
                dpr = screen.devicePixelRatio()
                target_width = int(screen.geometry().width() * dpr)
                resized_pixmap = pixmap.scaledToWidth(target_width, Qt.TransformationMode.SmoothTransformation)
                resized_pixmap.setDevicePixelRatio(dpr)
                display_size = resized_pixmap.size() / dpr
                self.scroll.setFixedHeight(display_size.height())
                self.image_label.setPixmap(resized_pixmap)
                self.image_label.setFixedSize(display_size)
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
            self.scroll.horizontalScrollBar().setValue(self.scroll.horizontalScrollBar().value() + delta)
            self.last_x = event.pos().x()

    def install_theme(self):
        # Create a custom styled dialog for the confirmation
        self.dialog = QDialog(self)
        self.dialog.setFixedWidth(420)
        self.dialog.setWindowTitle("Install Theme")
        self.dialog.setModal(True)
        icon_path = os.path.join(SCRIPT_PATH, "assets", "images", "app_icon.png")
        icon = QIcon(icon_path)
        self.dialog.setWindowIcon(QIcon(icon.pixmap(48, 48)))

        self.dialog.setWindowFlags(self.dialog.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        # Apply styles to the dialog
        self.dialog.setStyleSheet("""
            QLabel {
                font-size: 12px;
                padding: 10px;
                font-family: 'Segoe UI';
            }
        """)
        layout = QVBoxLayout(self.dialog)

        confirmation_message = QLabel(
            f"Are you sure you want to install the theme <b>{self.theme_data['name']}</b>?<br>This will overwrite your current config and styles files."
        )
        confirmation_message.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(confirmation_message)

        self.compat_label = QLabel("Checking compatibility...")
        layout.addWidget(self.compat_label)
        QTimer.singleShot(1000, lambda: self._check_font_families(self.theme_data["id"]))
        # Add Yes and No buttons
        button_layout = QHBoxLayout()
        self.yes_button = QPushButton("Install")
        self.yes_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.yes_button.clicked.connect(self.dialog.accept)
        self.yes_button.setStyleSheet("""
            QPushButton {
                margin: 10px 0;
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
        no_button.clicked.connect(self.dialog.reject)
        no_button.setStyleSheet("""
            QPushButton {
                margin: 10px 0;
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
        button_layout.addWidget(self.yes_button)
        button_layout.addWidget(no_button)
        button_layout.addStretch()

        layout.addStretch()
        layout.addLayout(button_layout)
        # Show the dialog and check the user's response
        if self.dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                subprocess.run(
                    ["yasbc", "stop"],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                # Define the URLs for the files
                base_url = f"https://raw.githubusercontent.com/amnweb/yasb-themes/main/themes/{self.theme_data['id']}"
                config_url = f"{base_url}/config.yaml"
                styles_url = f"{base_url}/styles.css"

                config_home = (
                    os.getenv("YASB_CONFIG_HOME")
                    if os.getenv("YASB_CONFIG_HOME")
                    else os.path.join(os.path.expanduser("~"), ".config", "yasb")
                )
                config_path = os.path.join(config_home, "config.yaml")
                styles_path = os.path.join(config_home, "styles.css")

                os.makedirs(os.path.dirname(config_path), exist_ok=True)

                # Download and save the styles.css file
                with urllib.request.urlopen(styles_url) as styles_response:
                    styles_data = styles_response.read()
                with open(styles_path, "wb") as styles_file:
                    styles_file.write(styles_data)

                # Download and save the config.yaml file
                with urllib.request.urlopen(config_url) as config_response:
                    config_data = config_response.read()
                with open(config_path, "wb") as config_file:
                    config_file.write(config_data)
                subprocess.run(
                    ["yasbc", "start"],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to install theme: {str(e)}")

    def _check_font_families(self, theme_id):
        try:
            styles_url = f"https://raw.githubusercontent.com/amnweb/yasb-themes/main/themes/{theme_id}/styles.css"
            with urllib.request.urlopen(styles_url, timeout=5) as resp:
                css = resp.read().decode("utf-8")
            css = self._extract_and_replace_variables(css)
            available_fonts = set(QFontDatabase.families())
            font_families = set()
            missing_fonts = set()
            matches = re.findall(r"font-family\s*:\s*([^;}\n]+)\s*[;}]+", css, flags=re.IGNORECASE)
            for match in matches:
                fonts = [f.strip(" '\"\t\r\n") for f in match.split(",")]
                for font in fonts:
                    if font:
                        font_families.add(font)
                        if font not in available_fonts:
                            missing_fonts.add(font)

            if missing_fonts:
                missing_fonts_label = "Some theme fonts are missing from your system"
                self.compat_label.setStyleSheet("""
                    QLabel {
                        font-size: 12px;
                        padding: 10px;
                        margin: 0px 10px;
                        font-family: 'Segoe UI';
                        color: #f1e1c9;
                        background-color: rgba(132, 73, 10, 0.2);
                        border: 1px solid #955816;
                        border-radius: 4px
                    }
                """)
                self.compat_label.setText(f"{missing_fonts_label}<br><b>{'<br>'.join(sorted(missing_fonts))}</b>")
                self.yes_button.setText("Install anyway")
            else:
                self.compat_label.hide()
        except Exception as e:
            self.compat_label.setStyleSheet("""
                QLabel {
                    font-size: 12px;
                    padding: 10px;
                    font-family: 'Segoe UI';
                    color: #fff;
                    background-color: #a00;
                    border: 1px solid #c33;
                    border-radius: 4px
                }
            """)
            self.compat_label.setText(f"Error checking fonts: {str(e)}")
            self.compat_label.setWordWrap(True)
            self.yes_button.setText("Install anyway")
        finally:
            self.dialog.adjustSize()

    def _extract_and_replace_variables(self, css: str) -> str:
        # Extract variables from :root
        root_vars: Dict[str, str] = {}

        def root_replacer(match):
            content = match.group(1)
            for var_match in re.finditer(r"--([\w-]+)\s*:\s*([^;]+);", content):
                var_name = f"--{var_match.group(1).strip()}"
                var_value = var_match.group(2).strip()
                root_vars[var_name] = var_value
            return ""  # Remove :root block

        css = re.sub(r":root\s*{([^}]*)}", root_replacer, css, flags=re.DOTALL)

        # Replace var(--name) with value
        def var_replacer(match):
            var_name = match.group(1).strip()
            return root_vars.get(var_name, match.group(0))

        css = re.sub(r"var\((--[\w-]+)\)", var_replacer, css)
        return css


class ThemeViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YASB Theme Gallery")
        icon_path = os.path.join(SCRIPT_PATH, "assets", "images", "app_icon.png")
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
        self.placeholder_label.setFont(QFont("Segoe UI", 64, QFont.Weight.Normal))
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.placeholder_label)

        # Wrap backup_info and buttons in a row widget
        self.row_widget = QWidget()
        self.row_widget.setObjectName("rowWidget")
        self.row_widget.setStyleSheet("""
            QWidget#rowWidget {
                background-color: rgba(255, 255, 255, 0.05);
            }
        """)
        row_layout = QHBoxLayout(self.row_widget)
        row_layout.setContentsMargins(20, 10, 20, 10)

        # Create backup_info
        self.backup_info = QLabel("Backup your current config files before installing a new theme.")
        self.backup_info.setWordWrap(True)
        self.backup_info.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        row_layout.addWidget(self.backup_info)

        # Horizontal layout for buttons
        self.backup_restore_layout = QHBoxLayout()
        self.backup_button = QPushButton("Backup")
        self.backup_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.backup_button.clicked.connect(self.backup_config)
        self.backup_button.setStyleSheet("""
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
        self.restore_button = QPushButton("Restore")
        self.restore_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.restore_button.clicked.connect(self.restore_config)
        self.restore_button.setStyleSheet("""
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
        self.backup_restore_layout.addWidget(self.backup_button)
        self.backup_restore_layout.addWidget(self.restore_button)
        row_layout.addLayout(self.backup_restore_layout)

        # Add row_widget to main layout, then hide it
        layout.addWidget(self.row_widget)
        self.row_widget.hide()

        # Setup scroll area
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
            if hasattr(self, "load_error_message"):
                self.placeholder_label.setText("Failed to load themes.")
                self.placeholder_label.setFont(QFont("Segoe UI", 14))
                QMessageBox.critical(self, "Error", f"Error loading themes: {self.load_error_message}")
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
        self.row_widget.show()
        self.scroll.show()
        for theme_id, theme in self.themes.items():
            theme["id"] = theme_id
            theme_card = ThemeCard(theme)
            self.container_layout.addWidget(theme_card)

    def backup_config(self):
        original_style = self.backup_button.styleSheet()
        config_home = (
            os.getenv("YASB_CONFIG_HOME")
            if os.getenv("YASB_CONFIG_HOME")
            else os.path.join(os.path.expanduser("~"), ".config", "yasb")
        )
        config_path = os.path.join(config_home, "config.yaml")
        styles_path = os.path.join(config_home, "styles.css")
        backup_config_path = os.path.join(config_home, "config.yaml.backup")
        backup_styles_path = os.path.join(config_home, "styles.css.backup")

        try:
            if os.path.exists(config_path):
                shutil.copy2(config_path, backup_config_path)
            if os.path.exists(styles_path):
                shutil.copy2(styles_path, backup_styles_path)

            # Verify that backup files exist
            backup_ok = True
            if os.path.exists(config_path) and not os.path.exists(backup_config_path):
                backup_ok = False
            if os.path.exists(styles_path) and not os.path.exists(backup_styles_path):
                backup_ok = False

            if backup_ok:
                self.backup_button.setText("Backup complete!")
                self.backup_button.setStyleSheet("""
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
                """)
            else:
                QMessageBox.critical(self, "Error", "Backup failed: Backup file(s) missing.")
                return

            QTimer.singleShot(
                2000, lambda: (self.backup_button.setText("Backup"), self.backup_button.setStyleSheet(original_style))
            )

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Backup failed: {str(e)}")

    def restore_config(self):
        self.restore_button.setText("Restoring...")
        QApplication.processEvents()  # Update the UI immediately

        config_home = (
            os.getenv("YASB_CONFIG_HOME")
            if os.getenv("YASB_CONFIG_HOME")
            else os.path.join(os.path.expanduser("~"), ".config", "yasb")
        )
        config_path = os.path.join(config_home, "config.yaml")
        styles_path = os.path.join(config_home, "styles.css")
        backup_config_path = os.path.join(config_home, "config.yaml.backup")
        backup_styles_path = os.path.join(config_home, "styles.css.backup")
        try:
            if not os.path.exists(backup_config_path) or not os.path.exists(backup_styles_path):
                self.restore_button.setText("Restore")
                QMessageBox.warning(self, "Error", "Restore failed: Backup file(s) missing.")
                return

            subprocess.run(
                ["yasbc", "stop"],
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            shutil.copy2(backup_config_path, config_path)
            shutil.copy2(backup_styles_path, styles_path)

            # Verify that the restored files exist
            restore_ok = True
            if not os.path.exists(config_path):
                restore_ok = False
            if not os.path.exists(styles_path):
                restore_ok = False

            if restore_ok:
                self.restore_button.setText("Restore complete!")
            else:
                QMessageBox.warning(self, "Error", "Restore failed: Backup file(s) missing.")
                return

            subprocess.run(
                ["yasbc", "start"],
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            QTimer.singleShot(2000, lambda: self.restore_button.setText("Restore"))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Restore failed: {str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = ThemeViewer()

    viewer.show()
    sys.exit(app.exec())
