import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from functools import lru_cache
from typing import Any, Dict, List

from PyQt6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QEvent,
    QMimeData,
    QPropertyAnimation,
    QSize,
    QStringListModel,
    Qt,
    QThread,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import QAction, QColor, QCursor, QDrag, QIcon, QKeySequence, QPainter, QPixmap, QShortcut, QWheelEvent
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QApplication,
    QCompleter,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.config import HOME_CONFIGURATION_DIR
from core.utils.shell_utils import shell_open
from core.utils.utilities import add_shadow, build_widget_label, refresh_widget_style
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.widgets.launchpad.app_loader import AppListLoader, ShortcutResolver
from core.utils.widgets.launchpad.icon_extractor import IconExtractorUtil, UrlExtractorUtil
from core.utils.win32.utilities import apply_qmenu_style, get_foreground_hwnd, set_foreground_hwnd
from core.utils.win32.win32_accent import Blur
from core.utils.win32.window_actions import force_foreground_focus
from core.validation.widgets.yasb.launchpad import LaunchpadConfig
from core.widgets.base import BaseWidget

_ICON_CACHE = {}


@lru_cache(maxsize=256)
def load_and_scale_icon(icon_path: str, size: int, dpr=1.0) -> QPixmap:
    """Load and scale icon with caching, supports SVG"""
    try:
        ext = os.path.splitext(icon_path)[1].lower()
        target_size = int(size * dpr)
        if ext == ".svg":
            renderer = QSvgRenderer(icon_path)
            pixmap = QPixmap(target_size, target_size)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            pixmap.setDevicePixelRatio(dpr)
            return pixmap
        else:
            pixmap = QPixmap(icon_path)
            if pixmap.isNull():
                return QPixmap()
            scaled_pixmap = pixmap.scaled(
                QSize(target_size, target_size),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            scaled_pixmap.setDevicePixelRatio(dpr)
            return scaled_pixmap
    except Exception as e:
        logging.error(f"Failed to load icon {icon_path}: {e}")
        return QPixmap()


class IconLoadWorker(QThread):
    """Background thread for loading icons"""

    icon_loaded = pyqtSignal(str, QPixmap)

    def __init__(self, icon_requests):
        super().__init__()
        self.icon_requests = icon_requests
        self._should_stop = False

    def stop(self):
        self._should_stop = True

    def run(self):
        for icon_path, size, dpr in self.icon_requests:
            if self._should_stop:
                break
            if os.path.isfile(icon_path):
                try:
                    pixmap = load_and_scale_icon(icon_path, size, dpr)
                    if not pixmap.isNull() and not self._should_stop:
                        self.icon_loaded.emit(icon_path, pixmap)
                except Exception as e:
                    logging.error(f"Failed to load icon in worker: {e}")


class UrlFetchWorker(QThread):
    finished = pyqtSignal(object, object)  # icon_path, title

    def __init__(self, url, icons_dir):
        super().__init__()
        self.url = url
        self.icons_dir = icons_dir

    def run(self):
        try:
            icon, title = UrlExtractorUtil.extract_from_url(self.url, self.icons_dir)
            self.finished.emit(icon, title)
        except Exception:
            self.finished.emit(None, None)


class AppDialog(QDialog):
    """Dialog for adding or editing an application in the launchpad"""

    def __init__(
        self,
        parent=None,
        app_data=None,
        icons_dir=None,
        all_groups=None,
        title=None,
        message=None,
        show_only_group=False,
        default_group=None,
    ):
        super().__init__(parent)
        self.app_data = app_data or {}
        self.is_edit_mode = app_data is not None
        self.icons_dir = icons_dir
        self.all_groups = all_groups or []
        self.show_only_group = show_only_group
        self.default_group = default_group

        self.setWindowTitle(title or ("Edit App" if self.is_edit_mode else "Add New App"))
        self.setMinimumSize(460, 200)
        self.setProperty("class", "app-dialog")
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.MSWindowsFixedSizeDialogHint
        )

        # Main layout setup
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(20, 0, 20, 0)
        content_layout.setSpacing(0)

        self._warning_label = QLabel("")
        self._warning_label.setProperty("class", "warning-message")
        self._warning_label.hide()
        content_layout.addWidget(self._warning_label)

        # Optional message label
        if message:
            message_label = QLabel(message)
            message_label.setProperty("class", "message")
            content_layout.addWidget(message_label)

        # Title field
        self.title_edit = QLineEdit()
        self.lineedit_context_menu(self.title_edit)
        self.title_edit.setPlaceholderText("Enter application title...")
        self.title_edit.setText(self.app_data.get("title", ""))
        self.title_edit.setProperty("class", "title-field")
        self.title_edit.returnPressed.connect(self._on_title_edit_return)
        title_edit_palette = self.title_edit.palette()
        self.title_edit.setPalette(title_edit_palette)
        if not show_only_group:
            content_layout.addWidget(self.title_edit)

        # App Path field
        if not show_only_group:
            h1 = QHBoxLayout()
            self.path_edit = QLineEdit()
            self.lineedit_context_menu(self.path_edit)
            self.path_edit.setPlaceholderText("Application executable, command or url...")
            self.path_edit.setText(self.app_data.get("path", ""))
            self.path_edit.setProperty("class", "path-field")
            self.path_edit.returnPressed.connect(self.accept)
            self.path_edit_palette = self.path_edit.palette()
            self.path_edit.setPalette(self.path_edit_palette)
            self.path_edit.editingFinished.connect(self._fetch_url_info)
            h1.addWidget(self.path_edit)

            browse_btn = QPushButton("Browse")
            browse_btn.setProperty("class", "button")
            browse_btn.clicked.connect(self.browse_path)
            h1.addWidget(browse_btn)
            content_layout.addLayout(h1)

        # Icon field
        if not show_only_group:
            h2 = QHBoxLayout()
            self.icon_edit = QLineEdit()
            self.lineedit_context_menu(self.icon_edit)
            self.icon_edit.setPlaceholderText("Icon file path...")
            self.icon_edit.setText(self.app_data.get("icon", ""))
            self.icon_edit.setProperty("class", "icon-field")
            self.icon_edit.returnPressed.connect(self.accept)
            self.icon_edit_palette = self.icon_edit.palette()
            self.icon_edit.setPalette(self.icon_edit_palette)
            h2.addWidget(self.icon_edit)

            browse_icon_btn = QPushButton("Browse Icon")
            browse_icon_btn.setProperty("class", "button")
            browse_icon_btn.clicked.connect(self.browse_icon)
            h2.addWidget(browse_icon_btn)
            content_layout.addLayout(h2)

        # Group field
        self.group_edit = QLineEdit()
        self.lineedit_context_menu(self.group_edit)
        self.group_edit.setPlaceholderText("Group name..." if show_only_group else "Group (optional)...")
        # Set group from app_data, or use default_group if provided
        group_value = self.app_data.get("group", "") or self.default_group or ""
        self.group_edit.setText(group_value)
        self.group_edit.setProperty("class", "group-field")
        self.group_edit.returnPressed.connect(self.accept)
        self.group_edit_palette = self.group_edit.palette()
        self.group_edit.setPalette(self.group_edit_palette)
        content_layout.addWidget(self.group_edit)

        # Setup group autocomplete
        self._group_completer = QCompleter(self.all_groups)
        self._group_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._group_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._group_completer.setMaxVisibleItems(5)
        self.group_edit.setCompleter(self._group_completer)
        group_popup = self._group_completer.popup()
        group_popup.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        group_popup.setStyleSheet("""
            QListView::item {
                padding: 8px;
            }
            QListView::item:selected,
            QListView::item:focus,
            QListView::item:selected:focus {
                background-color: rgba(0, 120, 212, 0.521);
            }
            QListView:focus {
                outline: none;
                border: none;
            }
        """)

        layout.addWidget(content_container)

        # Button container
        button_container = QFrame()
        button_container.setProperty("class", "buttons-container")
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.cancel_btn.setProperty("class", "button")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        self.add_btn = QPushButton("Save" if self.is_edit_mode else "Add")
        self.add_btn.setProperty("class", f"button {'save' if self.is_edit_mode else 'add'}")
        self.add_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.add_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.add_btn)
        layout.addWidget(button_container)
        self.setLayout(layout)

        self._installed_apps = []
        self._completer = QCompleter([])
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._completer.setMaxVisibleItems(5)
        self.title_edit.setCompleter(self._completer)
        popup = self._completer.popup()
        popup.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        popup.setStyleSheet("""
            QListView::item {
                padding: 8px;
            }
            QListView::item:selected,
            QListView::item:focus,
            QListView::item:selected:focus {
                background-color: rgba(0, 120, 212, 0.521);
            }
            QListView:focus {
                outline: none;
                border: none;
            }
        """)

        def on_title_selected(text):
            for name, path, _ in self._installed_apps:
                if name.lower() == text.lower():
                    if path.startswith("UWP::"):
                        appid = path.replace("UWP::", "")
                        self.path_edit.setText(f"explorer.exe shell:AppsFolder\\{appid}")
                        install_location = None
                        try:
                            ps_get_location = (
                                f"Get-AppxPackage | Where-Object {{$_.PackageFamilyName -eq '{appid.split('!')[0]}'}} | "
                                f"Select-Object -ExpandProperty InstallLocation"
                            )
                            result = subprocess.run(
                                [
                                    "powershell",
                                    "-NoProfile",
                                    "-NonInteractive",
                                    "-NoLogo",
                                    "-ExecutionPolicy",
                                    "Bypass",
                                    "-Command",
                                    ps_get_location,
                                ],
                                capture_output=True,
                                text=True,
                                encoding="utf-8",
                                errors="replace",
                                timeout=5,
                                creationflags=subprocess.CREATE_NO_WINDOW,
                            )
                            if result.returncode == 0:
                                install_location = result.stdout.strip()
                        except Exception:
                            install_location = None

                        uwp_icon = None
                        if install_location:
                            uwp_icon = IconExtractorUtil.extract_uwp_icon(appid, install_location=install_location)
                        if uwp_icon and os.path.isfile(uwp_icon):
                            ext = os.path.splitext(uwp_icon)[1].lower()
                            if ext == ".png":
                                self.icon_edit.setText(uwp_icon)
                            else:
                                self._show_warning("Failed to extract icon from UWP package.")
                                self.icon_edit.setText("")
                        else:
                            self.icon_edit.setText("")
                            self._show_warning("Could not locate icon for this UWP app.")

                    else:
                        self.path_edit.setText(path)
                        temp_dir = tempfile.gettempdir()
                        # If .lnk, resolve to target for icon extraction
                        ext = os.path.splitext(path)[1].lower()
                        icon_source = path
                        if ext == ".lnk":
                            _, icon_source, _ = ShortcutResolver.resolve_lnk_target(path, self._show_warning)
                        if icon_source and isinstance(icon_source, str) and os.path.isfile(icon_source):
                            icon_path = IconExtractorUtil.extract_icon_from_path(icon_source, temp_dir)
                            if icon_path:
                                self.icon_edit.setText(icon_path)
                            else:
                                self._show_warning("Failed to extract icon for the selected application.")
                        else:
                            self._show_warning("No valid icon source found for the selected application.")
                    break

        self._completer.activated.connect(on_title_selected)

        def on_apps_loaded(apps):
            self._installed_apps = apps
            self._completer.setModel(QStringListModel([name for name, _, _ in apps]))

        self._app_loader = AppListLoader()
        self._app_loader.apps_loaded.connect(on_apps_loaded)
        self._app_loader.start()

    def _fetch_url_info(self):
        path = self.path_edit.text().strip()
        if path.startswith("http://") or path.startswith("https://"):
            dialog_title = self.windowTitle()
            icon_path = self.icon_edit.text().strip()
            if not icon_path or not os.path.isfile(icon_path):
                self.setWindowTitle("Fetching website info...")

                def on_icon_fetched(icon, title):
                    self.setWindowTitle(dialog_title)
                    if icon and os.path.isfile(icon):
                        self.icon_edit.setText(icon)
                        if title and not self.title_edit.text().strip():
                            self.title_edit.setText(title)
                    else:
                        self._show_warning("Could not find an icon for this website.")

                self._url_fetch_worker = UrlFetchWorker(path, self.icons_dir)
                self._url_fetch_worker.finished.connect(on_icon_fetched)
                self._url_fetch_worker.start()

    def _on_title_edit_return(self):
        # Accept save or add only if completer is not visible
        if not self._completer.popup().isVisible():
            self.accept()

    def lineedit_context_menu(self, lineedit: QLineEdit):
        def show_custom_menu(point):
            menu = lineedit.createStandardContextMenu()
            apply_qmenu_style(menu)
            menu.setProperty("class", "context-menu")
            for action in menu.actions():
                action.setIconVisibleInMenu(False)
                action.setIcon(QIcon())
            menu.exec(lineedit.mapToGlobal(point))

        lineedit.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        lineedit.customContextMenuRequested.connect(show_custom_menu)

    def _show_warning(self, message):
        """Show warning message with animation"""
        self._warning_label.setText(message)
        self._warning_label.show()

        self.adjustSize()
        QTimer.singleShot(4000, self._hide_warning)

    def _hide_warning(self):
        """Hide warning message"""
        self._warning_label.hide()
        QTimer.singleShot(0, self.adjustSize)

    def browse_path(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Application", "", "Executable or Shortcut (*.exe *.lnk);;All Files (*)"
        )
        if file_path:
            self.path_edit.setText(file_path)

    def browse_icon(self):
        icon_path, _ = QFileDialog.getOpenFileName(
            self, "Select Icon", "", "Image Files (*.png *.jpg *.jpeg *.gif *.bmp *.ico *.svg);;All Files (*)"
        )
        if icon_path:
            self.icon_edit.setText(icon_path)

    def get_app_data(self):
        # If only group field is shown (rename mode)
        if self.show_only_group:
            group = self.group_edit.text().strip()
            return {
                "group": group if group else None,
            }

        icon_path = self.icon_edit.text().strip()
        original_icon = self.app_data.get("icon", "") if self.is_edit_mode else ""
        icon_changed = icon_path != original_icon

        if icon_changed and icon_path and self.icons_dir and os.path.isfile(icon_path):
            try:
                title = self.title_edit.text().strip().lower()
                safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).rstrip().replace(" ", "_")
                _, ext = os.path.splitext(icon_path)
                if not ext:
                    ext = ".png"
                timestamp = int(time.time() * 1000)
                new_filename = f"{safe_title}_{timestamp}{ext}"
                new_icon_path = os.path.join(self.icons_dir, new_filename)
                shutil.copy2(icon_path, new_icon_path)
                icon_path = new_icon_path
            except Exception as e:
                logging.error(f"Failed to copy icon: {e}")

        path = self.path_edit.text().strip()

        if path.startswith("http://") or path.startswith("https://"):
            entry_type = "url"
        else:
            entry_type = "app"

        group = self.group_edit.text().strip()
        return {
            "title": self.title_edit.text().strip(),
            "path": self.path_edit.text().strip(),
            "icon": icon_path,
            "type": entry_type,
            "group": group if group else None,
        }

    def accept(self):
        # If only showing group field (rename mode), skip validation
        if self.show_only_group:
            group = self.group_edit.text().strip()
            if not group:
                self._show_warning("Please enter a group name.")
                self.group_edit.setFocus()
                return
            super().accept()
            return

        title = self.title_edit.text().strip()
        path = self.path_edit.text().strip()
        icon = self.icon_edit.text().strip()

        if not title:
            self._show_warning("Please enter a title.")
            self.title_edit.setFocus()
            return

        if not path:
            self._show_warning("The specified path does not exist.")
            self.path_edit.setFocus()
            return

        if not os.path.isfile(icon):
            self._show_warning("The specified icon file does not exist.")
            self.icon_edit.setFocus()
            return

        super().accept()

    def done(self, result):
        for btn in (self.add_btn, self.cancel_btn):
            btn.unsetCursor()
        super().done(result)


class SmoothScrollArea(QScrollArea):
    """Custom scroll area with smooth scrolling capabilities"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scroll_animation = None
        self.scroll_speed = 300
        self.animation_duration = 400

    def keyPressEvent(self, event):
        if event.key() in [Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down]:
            event.ignore()
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        scroll_amount = -delta // 8 * self.scroll_speed // 15
        scrollbar = self.verticalScrollBar()
        current_value = scrollbar.value()
        target_value = current_value + scroll_amount
        target_value = max(scrollbar.minimum(), min(scrollbar.maximum(), target_value))
        if self.scroll_animation and self.scroll_animation.state() == QAbstractAnimation.State.Running:
            self.scroll_animation.stop()
        self.scroll_animation = QPropertyAnimation(scrollbar, b"value")
        self.scroll_animation.setDuration(self.animation_duration)
        self.scroll_animation.setStartValue(current_value)
        self.scroll_animation.setEndValue(target_value)
        self.scroll_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.scroll_animation.start()
        event.accept()


class TransparentOverlay(QWidget):
    """
    Transparent overlay window that captures clicks to hide the launchpad
    """

    overlay_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.BypassWindowManagerHint
        )
        self.setWindowOpacity(0.01)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def update_geometry(self, screen_geometry):
        # We use 1 pixel less in height to avoid windows to activate the Do Not Disturb mode
        width = screen_geometry.width()
        height = screen_geometry.height() - 1
        x = screen_geometry.x()
        y = screen_geometry.y()
        self.setFixedSize(width, height)
        self.move(x, y)

    def mousePressEvent(self, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            self.overlay_clicked.emit()
        event.accept()


class LaunchpadWidget(BaseWidget):
    validation_schema = LaunchpadConfig

    def __init__(self, config: LaunchpadConfig):
        super().__init__(class_name="launchpad-widget")
        self.config = config
        self._label = config.label
        self._search_placeholder = config.search_placeholder
        self._app_icon_size = config.app_icon_size
        self._window = config.window.model_dump()
        self._window_style = config.window_style.model_dump()
        self._window_animation = config.window_animation.model_dump()
        self._animation = config.animation.model_dump()
        self._shortcuts = config.shortcuts.model_dump()
        self._padding = config.container_padding.model_dump()
        self._group_apps = config.group_apps
        self._label_shadow = config.label_shadow.model_dump()
        self._container_shadow = config.container_shadow.model_dump()
        self._app_title_shadow = config.app_title_shadow.model_dump()
        self._app_icon_shadow = config.app_icon_shadow.model_dump()
        self._dpr = 1.0
        # Setup directories and files
        self._launchpad_dir = os.path.join(HOME_CONFIGURATION_DIR, "launchpad")
        self._icons_dir = os.path.join(self._launchpad_dir, "icons")
        self._data_file = os.path.join(self._launchpad_dir, "apps.json")
        if not os.path.isfile(self._data_file):
            os.makedirs(self._launchpad_dir, exist_ok=True)
            os.makedirs(self._icons_dir, exist_ok=True)

        # Initialize properties
        self._launchpad_popup = None
        self._overlay = None
        self._drop_overlay = None
        self._is_closing = False
        self._app_icons = []
        self._all_apps = []
        self._icon_worker = None
        self._grid_columns = 0
        self._num_drag_items = 0
        self._previous_hwnd = 0

        # Create a container widget for layout
        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(0, 0, 0, 0)
        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self._container_shadow)
        self.widget_layout.addWidget(self._widget_container)
        build_widget_label(self, self._label, None, self._label_shadow)

        # Register callbacks
        self.register_callback("toggle_launchpad", self._toggle_launchpad)
        self.callback_left = self.config.callbacks.on_left
        self.callback_right = self.config.callbacks.on_right
        self.callback_middle = self.config.callbacks.on_middle

    def _toggle_launchpad(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        if self._launchpad_popup and self._launchpad_popup.isVisible():
            self._hide_launchpad()
        else:
            self._show_launchpad()

    def _show_launchpad(self):
        self._dpr = self.screen().devicePixelRatio()

        # Save current foreground window before showing popup
        self._previous_hwnd = get_foreground_hwnd()

        if not self._launchpad_popup:
            self._launchpad_popup = self._create_launchpad_popup()
        if not self._overlay and not self._window["fullscreen"] and self._window["overlay_block"]:
            self._overlay = self._create_overlay()

        self._center_popup_on_screen()
        if self._overlay:
            self._overlay.show()
        self._launchpad_popup.show()
        self._populate_grid()

        # Force focus using Win32 API
        force_foreground_focus(int(self._launchpad_popup.winId()))

    def _hide_launchpad(self):
        if self._launchpad_popup and not self._is_closing:
            self._fade_out_popup()

    def _create_app_icon_widget(self, app_data: Dict[str, Any]) -> QFrame:
        """Create an app icon widget"""
        app_icon = QFrame()
        if app_data.get("type") == "url":
            app_icon.setProperty("class", "app-icon url")
        else:
            app_icon.setProperty("class", "app-icon")
        app_icon.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        app_icon.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        app_icon.setAcceptDrops(True)
        app_icon.app_data = app_data
        app_icon._icon_loaded = False
        app_icon._drag_start_position = None
        app_icon._drop_highlight = False

        container_layout = QVBoxLayout(app_icon)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        icon_label = QLabel()
        icon_label.setFixedSize(self._app_icon_size, self._app_icon_size)
        icon_label.setProperty("class", "icon")
        add_shadow(icon_label, self._app_icon_shadow)

        title_label = QLabel(app_data.get("title", "Unknown"))
        title_label.setProperty("class", "title")
        title_label.setWordWrap(True)
        title_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        add_shadow(title_label, self._app_title_shadow)

        container_layout.addWidget(
            icon_label, stretch=1, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )
        container_layout.addWidget(title_label, stretch=2, alignment=Qt.AlignmentFlag.AlignHCenter)

        app_icon.icon_label = icon_label
        app_icon.title_label = title_label

        def paintEvent(event):
            QFrame.paintEvent(app_icon, event)
            if getattr(app_icon, "_drop_highlight", False):
                painter = QPainter(app_icon)
                rect = app_icon.rect()
                radius = 6
                pen = painter.pen()
                pen.setWidth(1)
                pen.setColor(QColor(0, 153, 255, 150))
                pen.setStyle(Qt.PenStyle.CustomDashLine)
                pen.setDashPattern([8, 4])
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius, radius)

                painter.setBrush(QColor(0, 153, 255, 40))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(rect, radius, radius)

        app_icon.paintEvent = paintEvent

        def mousePressEvent(event):
            if event.button() == Qt.MouseButton.LeftButton:
                app_icon._drag_start_position = event.pos()
            elif event.button() == Qt.MouseButton.RightButton:
                self._show_context_menu(event.pos(), app_data=app_icon.app_data, parent_widget=app_icon, event=event)

        app_icon.mousePressEvent = mousePressEvent

        def mouseMoveEvent(event):
            if event.buttons() & Qt.MouseButton.LeftButton:
                if (event.pos() - app_icon._drag_start_position).manhattanLength() >= QApplication.startDragDistance():
                    drag = QDrag(app_icon)
                    mime_data = QMimeData()
                    app_id = str(app_icon.app_data.get("id", ""))
                    mime_data.setText(app_id)
                    drag.setMimeData(mime_data)
                    pixmap = app_icon.grab()
                    drag.setPixmap(pixmap)
                    drag.setHotSpot(event.pos())
                    drag.exec(Qt.DropAction.MoveAction)

        app_icon.mouseMoveEvent = mouseMoveEvent

        def mouseReleaseEvent(event):
            if event.button() == Qt.MouseButton.LeftButton:
                if (event.pos() - app_icon._drag_start_position).manhattanLength() < QApplication.startDragDistance():
                    self._launch_app(app_icon.app_data)

        app_icon.mouseReleaseEvent = mouseReleaseEvent

        def dragEnterEvent(event):
            if event.mimeData().hasUrls():
                self._show_drop_overlay()
                event.acceptProposedAction()

            elif event.mimeData().hasText():
                event.acceptProposedAction()
                app_icon._drop_highlight = True
                app_icon.setProperty("isDropTarget", True)
                app_icon.setStyleSheet("""
                    QFrame[isDropTarget="true"] {
                        background: transparent;
                        border-color: transparent;
                    }
                """)
                app_icon.update()
            else:
                event.ignore()

        app_icon.dragEnterEvent = dragEnterEvent

        def dragLeaveEvent(event):
            if self._overlay and self._overlay.isVisible():
                self._hide_drop_overlay()
            app_icon._drop_highlight = False
            app_icon.setProperty("isDropTarget", False)
            refresh_widget_style(app_icon)
            app_icon.update()

        app_icon.dragLeaveEvent = dragLeaveEvent

        def dropEvent(event):
            app_icon._drop_highlight = False
            app_icon.setProperty("isDropTarget", False)
            refresh_widget_style(app_icon)
            app_icon.update()
            source_id = event.mimeData().text()
            target_id = str(app_icon.app_data.get("id", ""))
            if source_id != target_id:
                self._reorder_apps(source_id, target_id)
            event.acceptProposedAction()

        app_icon.dropEvent = dropEvent

        self._load_app_icon(app_icon)
        return app_icon

    def _load_app_icon(self, app_icon):
        """Load icon for an app icon widget"""
        icon_path = app_icon.app_data.get("icon", "")
        if not icon_path or not os.path.isfile(icon_path):
            app_icon.icon_label.setText("")
            app_icon._icon_loaded = True
            return
        cache_key = f"{icon_path}_{self._app_icon_size}_{self._dpr}"
        if cache_key in _ICON_CACHE:
            app_icon.icon_label.setPixmap(_ICON_CACHE[cache_key])
            refresh_widget_style(app_icon.icon_label)
            app_icon._icon_loaded = True
            return
        try:
            pixmap = load_and_scale_icon(icon_path, self._app_icon_size, self._dpr)
            if not pixmap.isNull():
                _ICON_CACHE[cache_key] = pixmap
                app_icon.icon_label.setPixmap(pixmap)
                refresh_widget_style(app_icon.icon_label)
                app_icon._icon_loaded = True
            else:
                app_icon.icon_label.setText("")
                app_icon._icon_loaded = True
        except Exception as e:
            logging.error(f"Failed to load icon {icon_path}: {e}")
            app_icon.icon_label.setText("")
            app_icon._icon_loaded = True

    def _reorder_apps(self, source_app_id: str, target_app_id: str):
        try:
            apps = self._load_apps()
            source_index = -1
            target_index = -1
            for i, app in enumerate(apps):
                if str(app.get("id", "")) == source_app_id:
                    source_index = i
                elif str(app.get("id", "")) == target_app_id:
                    target_index = i
            if source_index != -1 and target_index != -1 and source_index != target_index:
                source_app = apps.pop(source_index)
                apps.insert(target_index, source_app)
                self._save_apps(apps)
                if self._launchpad_popup:
                    # If we're in a group, refresh the group view
                    if hasattr(self, "_current_group"):
                        updated_apps = self._load_apps()
                        group_apps_list = [app for app in updated_apps if app.get("group") == self._current_group]
                        self._open_group(self._current_group, group_apps_list)
                    else:
                        current_search = self._launchpad_popup.search_input.text()
                        self._populate_grid(current_search)

        except Exception as e:
            logging.error(f"Failed to reorder apps: {e}")

    _SHELL_APPS_FOLDER = "explorer.exe shell:AppsFolder\\"

    def _launch_app(self, app_data: Dict[str, Any]):
        path = app_data.get("path", "")
        if path:
            try:
                if path.startswith("http://") or path.startswith("https://"):
                    shell_open(path)
                elif path.startswith(self._SHELL_APPS_FOLDER):
                    shell_open(path[len("explorer.exe ") :])
                elif os.path.isfile(path):
                    shell_open(path)
                else:
                    parts = path.split(None, 1)
                    shell_open(parts[0], parameters=parts[1] if len(parts) > 1 else None)
                self._hide_launchpad()
            except Exception as e:
                logging.error(f"Failed to launch app {app_data.get('title', 'Unknown')}: {e}")

    def _launch_app_elevated(self, app_data: Dict[str, Any]):
        """Launch an app with administrator privileges (UAC prompt)."""
        path = app_data.get("path", "")
        if path:
            try:
                if path.startswith("http://") or path.startswith("https://"):
                    shell_open(path)
                elif path.startswith(self._SHELL_APPS_FOLDER):
                    shell_open(path[len("explorer.exe ") :], verb="runas")
                elif os.path.isfile(path):
                    shell_open(path, verb="runas")
                else:
                    parts = path.split(None, 1)
                    shell_open(parts[0], verb="runas", parameters=parts[1] if len(parts) > 1 else None)
                self._hide_launchpad()
            except Exception as e:
                logging.error(f"Failed to launch app elevated {app_data.get('title', 'Unknown')}: {e}")

    def _show_context_menu(self, pos, app_data=None, parent_widget=None, event=None):
        """
        Show context menu for the launchpad or an app icon
        """
        menu_parent = parent_widget if parent_widget else self._launchpad_popup
        menu = QMenu(menu_parent.window())
        menu.setProperty("class", "context-menu")
        apply_qmenu_style(menu)

        if app_data:
            edit_action = QAction("Edit", menu_parent)
            edit_action.triggered.connect(lambda: self._edit_app(app_data))
            menu.addAction(edit_action)

            path = app_data.get("path", "")
            if path and not path.startswith("http://") and not path.startswith("https://"):
                admin_action = QAction("Run as Administrator", menu_parent)
                admin_action.triggered.connect(lambda: self._launch_app_elevated(app_data))
                menu.addAction(admin_action)

        add_action = QAction("Add New App", menu_parent)
        add_action.triggered.connect(self._add_new_app)
        menu.addAction(add_action)

        if app_data:
            # Context-aware group menu
            all_groups = self._get_all_groups()
            inside_group = hasattr(self, "_current_group")

            if inside_group:
                # Inside a group view: show "Remove from [GroupName]" + "Move to Group" with other groups
                menu.addSeparator()

                # Direct "Remove from [GroupName]" action
                remove_action = QAction(f"Remove from {self._current_group}", menu_parent)
                remove_action.triggered.connect(lambda: self._set_app_group(app_data, None))
                menu.addAction(remove_action)

                # "Move to Group" submenu with other groups (exclude current)
                other_groups = [g for g in all_groups if g != self._current_group]
                if other_groups:
                    move_menu = QMenu("Move to Group", menu)
                    move_menu.setProperty("class", "context-menu")
                    apply_qmenu_style(move_menu)

                    for group in other_groups:
                        move_action = QAction(group, menu_parent)
                        move_action.triggered.connect(lambda checked, c=group, a=app_data: self._set_app_group(a, c))
                        move_menu.addAction(move_action)

                    menu.addMenu(move_menu)
            else:
                # Main view (not inside group): show "Add to Group" with all groups
                if all_groups:
                    menu.addSeparator()

                    group_menu = QMenu("Add to Group", menu)
                    group_menu.setProperty("class", "context-menu")
                    apply_qmenu_style(group_menu)

                    for group in all_groups:
                        group_action = QAction(group, menu_parent)
                        group_action.triggered.connect(lambda checked, c=group, a=app_data: self._set_app_group(a, c))
                        group_menu.addAction(group_action)

                    menu.addMenu(group_menu)

        menu.addSeparator()

        order_action_az = QAction("Order A-Z", menu_parent)
        order_action_az.triggered.connect(lambda: self._order_apps("az"))
        menu.addAction(order_action_az)
        order_action_za = QAction("Order Z-A", menu_parent)
        order_action_za.triggered.connect(lambda: self._order_apps("za"))
        menu.addAction(order_action_za)
        order_action_recent = QAction("Order by Recent", menu_parent)
        order_action_recent.triggered.connect(lambda: self._order_apps("recent"))
        menu.addAction(order_action_recent)
        order_action_oldest = QAction("Order by Oldest", menu_parent)
        order_action_oldest.triggered.connect(lambda: self._order_apps("oldest"))
        menu.addAction(order_action_oldest)

        menu.addSeparator()

        if app_data:
            delete_action = QAction("Delete", menu_parent)
            delete_action.triggered.connect(lambda: self._delete_app(app_data))
            menu.addAction(delete_action)
            menu.addSeparator()

        exit_action = QAction("Exit Launchpad", menu_parent)
        exit_action.triggered.connect(self._hide_launchpad)
        menu.addAction(exit_action)

        if event:
            menu.exec(parent_widget.mapToGlobal(event.pos()))
        else:
            menu.exec(self._launchpad_popup.mapToGlobal(pos))

    def _show_drop_overlay(self):
        """Show the drop overlay when dragging items over the launchpad"""
        if self._num_drag_items > 1:
            overlay_label = f"Drop {self._num_drag_items} Apps Here"
        else:
            overlay_label = "Drop App Here"

        if self._drop_overlay:
            # Update label text if overlay already exists
            label = self._drop_overlay.findChild(QLabel)
            if label:
                label.setText(overlay_label)
            self._drop_overlay.show()
            return

        overlay = QWidget(self._launchpad_popup)
        overlay.setProperty("class", "drop-overlay")
        overlay.setGeometry(self._launchpad_popup.rect())
        label = QLabel(overlay_label, overlay)
        label.setProperty("class", "text")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setGeometry(0, 0, overlay.width(), overlay.height())
        overlay.show()
        self._drop_overlay = overlay

    def _hide_drop_overlay(self):
        if self._drop_overlay:
            self._drop_overlay.hide()

    def _create_launchpad_popup(self):
        """Create the launchpad popup window"""
        self.popup = QWidget(self)
        self.popup.setProperty("class", "launchpad")
        self.popup.setContentsMargins(0, 0, 0, 0)
        self.popup.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint
        )
        self.popup.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        def focusNextPrevChild(block):
            return False

        self.popup.focusNextPrevChild = focusNextPrevChild

        target_screen = self._get_target_screen()
        screen_geometry = target_screen.geometry()

        if self._window["fullscreen"]:
            self.popup.setGeometry(screen_geometry)
        else:
            self.popup.setFixedSize(self._window["width"], self._window["height"])
        self.popup.setWindowOpacity(0.0)
        self.popup._target_screen = target_screen
        self.popup._screen_geometry = screen_geometry

        self.popup.fade_in_animation = QPropertyAnimation(self.popup, b"windowOpacity")
        self.popup.fade_in_animation.setDuration(self._window_animation["fade_in_duration"])
        self.popup.fade_in_animation.setStartValue(0.0)
        self.popup.fade_in_animation.setEndValue(1.0)

        self.popup.fade_out_animation = QPropertyAnimation(self.popup, b"windowOpacity")
        self.popup.fade_out_animation.setDuration(self._window_animation["fade_out_duration"])
        self.popup.fade_out_animation.setStartValue(1.0)
        self.popup.fade_out_animation.setEndValue(0.0)

        self.popup.fade_out_animation.finished.connect(self._on_fade_out_finished)
        self.popup.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.popup.customContextMenuRequested.connect(lambda pos: self._show_context_menu(pos))

        window_layout = QVBoxLayout(self.popup)
        window_layout.setContentsMargins(0, 0, 0, 0)
        window_layout.setSpacing(0)

        container = QFrame(self)
        container.setProperty("class", "launchpad-container")
        window_layout.addWidget(container)

        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        search_outer_layout = QHBoxLayout()
        search_outer_layout.setContentsMargins(0, 0, 0, 0)
        search_outer_layout.setSpacing(0)
        search_container = QWidget()
        search_container.setProperty("class", "search-container")
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(0)

        search_input = QLineEdit()
        search_input.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        search_input.setProperty("class", "search-input")
        search_input.setPlaceholderText(self._search_placeholder)
        search_input.textChanged.connect(lambda text: self._update_search_results(text))

        search_layout.addWidget(search_input)
        search_outer_layout.addWidget(search_container)
        search_wrapper = QWidget()
        search_wrapper.setLayout(search_outer_layout)
        main_layout.addWidget(search_wrapper)

        scroll_area = SmoothScrollArea()
        scroll_area.setProperty("class", "launchpad-scroll-area")
        scroll_area.setViewportMargins(0, 0, 0, 0)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        scroll_area.setStyleSheet("""
            QScrollBar:vertical { border: none; background:transparent; width: 4px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
            QScrollBar::handle:vertical { background: rgba(255, 255, 255, 0.2); min-height: 10px; border-radius: 2px; }
            QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 0.35); }
            QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        """)

        grid_container = QFrame()
        grid_container.setObjectName("grid-container")
        grid_container.setStyleSheet("#grid-container { background: transparent; }")
        grid_container.setContentsMargins(0, 0, 0, 0)

        grid_layout = QGridLayout(grid_container)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(0)
        grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignCenter)
        scroll_area.setWidget(grid_container)
        main_layout.addWidget(scroll_area)

        self.popup.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.popup.container = container
        self.popup.search_container = search_container
        self.popup.search_input = search_input
        self.popup.scroll_area = scroll_area
        self.popup.grid_container = grid_container
        self.popup.grid_layout = grid_layout

        self.popup.setAcceptDrops(True)
        self.popup.mousePressEvent = lambda event: self._handle_popup_mouse_press(self.popup, event)
        self.popup.keyPressEvent = lambda event: self._handle_popup_key_press(event)
        self.popup.showEvent = self._popup_show_event
        self.popup.closeEvent = self._popup_close_event
        self.popup.dropEvent = self._popup_drop_event
        self.popup.dragEnterEvent = self._popup_drag_enter_event
        self.popup.dragLeaveEvent = self._popup_drag_leave_event
        self.popup.enterEvent = self._popup_enter_event
        self.popup.leaveEvent = self._popup_leave_event

        shortcut_add = QShortcut(QKeySequence(self._shortcuts["add_app"]), self.popup)
        shortcut_add.activated.connect(self._add_new_app)

        shortcut_edit = QShortcut(QKeySequence(self._shortcuts["edit_app"]), self.popup)
        shortcut_edit.activated.connect(self._edit_selected_app)

        shortcut_menu = QShortcut(QKeySequence(self._shortcuts["show_context_menu"]), self.popup)
        shortcut_menu.activated.connect(lambda: self._show_context_menu(self.popup.rect().center()))

        shortcut_delete = QShortcut(QKeySequence(self._shortcuts["delete_app"]), self.popup)
        shortcut_delete.activated.connect(self._delete_selected_app)

        return self.popup

    def _edit_selected_app(self):
        focused_icon = next((icon for icon in self._app_icons if icon.hasFocus()), None)
        if focused_icon:
            self._edit_app(focused_icon.app_data)

    def _delete_selected_app(self):
        focused_icon = next((icon for icon in self._app_icons if icon.hasFocus()), None)
        if focused_icon:
            self._delete_app(focused_icon.app_data)

    def _center_popup_on_screen(self):
        if not self._launchpad_popup:
            return
        target_screen = self._get_target_screen()
        screen_geometry = target_screen.geometry()
        if not self._window["fullscreen"]:
            window_geometry = self._launchpad_popup.geometry()
            x = (screen_geometry.width() - window_geometry.width()) // 2 + screen_geometry.x()
            y = (screen_geometry.height() - window_geometry.height()) // 2 + screen_geometry.y()
            self._launchpad_popup.move(x, y)
        if self._overlay:
            self._overlay.update_geometry(screen_geometry)

    def _create_overlay(self):
        if self._overlay:
            return self._overlay
        self._overlay = TransparentOverlay()
        self._overlay.overlay_clicked.connect(self._hide_launchpad)
        return self._overlay

    def _get_file_description(self, path):
        """Get the file description from Windows file properties."""
        import win32api

        try:
            language, codepage = win32api.GetFileVersionInfo(path, "\\VarFileInfo\\Translation")[0]
            stringFileInfo = "\\StringFileInfo\\%04X%04X\\%s" % (language, codepage, "FileDescription")
            description = win32api.GetFileVersionInfo(path, stringFileInfo)
        except:
            description = "unknown"

        return description

    def _handle_file_drop(self, file_path, refresh_grid=True):
        ext = os.path.splitext(file_path)[1].lower()
        app_data = None

        if ext == ".lnk":
            target_path, icon_path, app_name = ShortcutResolver.resolve_lnk_target(file_path, self._warning_dialog)
            if not app_name or not target_path:
                self._warning_dialog(f"Failed to resolve shortcut: {file_path}")
                return
            if not icon_path:
                icon_path = target_path
            icon_png = IconExtractorUtil.extract_icon_from_path(icon_path, self._icons_dir)
            if not icon_png:
                self._warning_dialog(
                    f"Failed to extract icon for application<br><b>{file_path}</b><br>Please select an icon manually."
                )

            app_data = (app_name, target_path, icon_png or "")

        elif ext == ".exe":
            title = self._get_file_description(file_path)
            if not title:
                self._warning_dialog(f"Failed to get description for executable: {file_path}")
                return
            icon_png = IconExtractorUtil.extract_icon_from_path(file_path, self._icons_dir)

            if not icon_png:
                self._warning_dialog(
                    f"Failed to extract icon for application<br><b>{file_path}</b><br>Please select an icon manually."
                )

            app_data = (title, file_path, icon_png or "")

        if app_data:
            app_dict = {
                "title": app_data[0],
                "path": app_data[1],
                "icon": app_data[2],
                "id": int(time.time() * 1000),
            }
            # If we're in a group, automatically set the group
            if hasattr(self, "_current_group"):
                app_dict["group"] = self._current_group

            apps = self._load_apps()
            apps.append(app_dict)
            self._save_apps(apps)
            if self._launchpad_popup and refresh_grid:
                # If in group, refresh the group view
                if hasattr(self, "_current_group"):
                    # Reload apps to get the fresh list
                    updated_apps = self._load_apps()
                    group_apps_list = [app for app in updated_apps if app.get("group") == self._current_group]
                    self._open_group(self._current_group, group_apps_list)
                else:
                    self._populate_grid()

    def _popup_drag_enter_event(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            self._num_drag_items = len(urls)
            self._show_drop_overlay()
            event.acceptProposedAction()
        else:
            event.ignore()

    def _popup_drag_leave_event(self, event):
        self._hide_drop_overlay()
        event.accept()

    def _popup_drop_event(self, event):
        self._hide_drop_overlay()
        if event.mimeData().hasUrls():
            file_paths = [url.toLocalFile() for url in event.mimeData().urls()]
            for file_path in file_paths:
                self._handle_file_drop(file_path, refresh_grid=False)

            # Refresh only once after all files are added
            if hasattr(self, "_current_group"):
                # If in group, refresh the group view
                updated_apps = self._load_apps()
                group_apps_list = [app for app in updated_apps if app.get("group") == self._current_group]
                self._open_group(self._current_group, group_apps_list)
            else:
                self._populate_grid()

            event.acceptProposedAction()
        else:
            event.ignore()

    def _handle_popup_mouse_press(self, popup, event):
        if event.button() == Qt.MouseButton.LeftButton:
            widget_at_pos = popup.childAt(event.pos())
            if widget_at_pos == popup or widget_at_pos == popup.container:
                self._fade_out_popup()
                event.accept()
                return

    def _handle_popup_key_press(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._fade_out_popup()
            event.accept()

        elif event.key() in [Qt.Key.Key_Return, Qt.Key.Key_Enter]:
            focused_icon = next((icon for icon in self._app_icons if icon.hasFocus()), None)
            if focused_icon:
                # Check if it's a group or an app
                if hasattr(focused_icon, "is_group") and focused_icon.is_group:
                    self._open_group(focused_icon.group_name, focused_icon.apps_in_group)
                else:
                    self._launch_app(focused_icon.app_data)
            event.accept()

        elif event.key() == Qt.Key.Key_Backspace:
            # If we're in a group, go back to main grid
            if hasattr(self, "_current_group"):
                self._close_group()
                event.accept()
            else:
                event.ignore()

        elif event.key() == Qt.Key.Key_Tab:
            if self._launchpad_popup.search_input.hasFocus():
                if self._app_icons:
                    self._app_icons[0].setFocus()
            else:
                self._launchpad_popup.search_input.setFocus()
            event.accept()

        elif event.key() in [Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down]:
            self._handle_arrow_navigation(event.key())
            event.accept()
        else:
            event.ignore()

    def _handle_arrow_navigation(self, key):
        if not self._app_icons:
            return
        current_index = next((i for i, icon in enumerate(self._app_icons) if icon.hasFocus()), -1)
        if current_index == -1:
            self._focus_icon(0)
            return
        new_index = current_index
        if key == Qt.Key.Key_Left:
            new_index = max(0, current_index - 1)
        elif key == Qt.Key.Key_Right:
            new_index = min(len(self._app_icons) - 1, current_index + 1)
        elif key == Qt.Key.Key_Up:
            new_index = max(0, current_index - self._grid_columns)
        elif key == Qt.Key.Key_Down:
            new_index = min(len(self._app_icons) - 1, current_index + self._grid_columns)
        self._focus_icon(new_index)

    def _popup_enter_event(self, event):
        self.popup.setCursor(Qt.CursorShape.ArrowCursor)
        QWidget.enterEvent(self.popup, event)

    def _popup_leave_event(self, event):
        self.popup.setCursor(Qt.CursorShape.ArrowCursor)
        QWidget.leaveEvent(self.popup, event)

    def _scroll_to_icon(self, icon):
        """
        If the icon is above or below the visible area
        adjusts the scrollbar so the icon comes into view.
        """
        if not self._launchpad_popup:
            return
        scroll_area = self._launchpad_popup.scroll_area
        icon_rect = icon.geometry()
        scroll_rect = scroll_area.viewport().rect()
        scrollbar = scroll_area.verticalScrollBar()
        current_scroll = scrollbar.value()
        icon_top = icon_rect.top()
        icon_bottom = icon_rect.bottom()
        visible_top = current_scroll
        visible_bottom = current_scroll + scroll_rect.height()
        if icon_top < visible_top:
            scrollbar.setValue(icon_top)
        elif icon_bottom > visible_bottom:
            scrollbar.setValue(icon_bottom - scroll_rect.height())

    def _popup_show_event(self, event):
        if self._window_style["enable_blur"]:
            try:
                self._apply_blur()
            except Exception as e:
                logging.warning(f"Failed to apply blur effect: {e}")
        self._fade_in_popup()
        QTimer.singleShot(0, self._focus_first_icon)

    def _popup_close_event(self, event):
        if self._icon_worker and self._icon_worker.isRunning():
            self._icon_worker.terminate()
            self._icon_worker.wait()

    def _update_search_results(self, text: str):
        self._populate_grid(text)

    def _populate_grid(self, search_text: str = ""):
        if not self._launchpad_popup:
            return
        grid_layout = self._launchpad_popup.grid_layout
        for i in reversed(range(grid_layout.count())):
            child = grid_layout.itemAt(i).widget()
            if child:
                child.setParent(None)
        self._app_icons.clear()
        self._all_apps = self._load_apps()

        # Filter apps based on search text
        filtered_apps = []
        if search_text:
            # Support group:name syntax for filtering by group
            if search_text.startswith("group:"):
                group_filter = search_text[6:].strip().lower()
                for app_data in self._all_apps:
                    app_group = (app_data.get("group") or "").lower()
                    if group_filter in app_group:
                        filtered_apps.append(app_data)
            else:
                for app_data in self._all_apps:
                    if search_text.lower() in app_data.get("title", "").lower():
                        filtered_apps.append(app_data)
        else:
            filtered_apps = self._all_apps

        if not filtered_apps:
            no_apps_label = QLabel(
                f"No applications found<div style='font-size:14pt;margin-top:12px;font-weight:400'>press <b>{self._shortcuts['add_app']}</b> to add new apps</div>"
            )
            no_apps_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_apps_label.setTextFormat(Qt.TextFormat.RichText)
            no_apps_label.setStyleSheet("font-size: 24pt;font-family: 'Segoe UI';padding: 40px")
            grid_layout.addWidget(no_apps_label, 0, 0, 1, 1)
            return

        # Create group-style grid or flat grid based on grouping and search
        if self._group_apps and not search_text and not hasattr(self, "_current_group"):
            self._populate_grouped_grid(filtered_apps)
        else:
            self._populate_flat_grid(filtered_apps)

    def _populate_flat_grid(self, filtered_apps: List[Dict[str, Any]]):
        """Populate grid without grouping (original behavior)"""
        grid_layout = self._launchpad_popup.grid_layout

        for app_data in filtered_apps:
            app_icon = self._create_app_icon_widget(app_data)
            self._app_icons.append(app_icon)

        if self._app_icons:
            first_icon = self._app_icons[0]
            first_icon.setParent(self._launchpad_popup.grid_container)
            first_icon.updateGeometry()

            self._recalculate_grid_columns()

            # Safety check: ensure _grid_columns is never 0
            if self._grid_columns <= 0:
                self._grid_columns = 1

            rows = (len(self._app_icons) + self._grid_columns - 1) // self._grid_columns
            icon_height = self._app_icons[0].height()
            total_height = rows * icon_height

            # Set the grid container to the exact height needed
            self._launchpad_popup.grid_container.setFixedHeight(total_height)

        for index, app_icon in enumerate(self._app_icons):
            # Ensure _grid_columns is not 0 before using modulo
            if self._grid_columns <= 0:
                self._grid_columns = 1
            row = index // self._grid_columns
            col = index % self._grid_columns
            grid_layout.addWidget(app_icon, row, col)

        icon_requests = []
        for app_data in filtered_apps:
            icon_path = app_data.get("icon", "")
            if icon_path and os.path.isfile(icon_path):
                cache_key = f"{icon_path}_{self._app_icon_size}_{self._dpr}"
                if cache_key not in _ICON_CACHE:
                    icon_requests.append((icon_path, self._app_icon_size, self._dpr))
        if icon_requests:
            self._start_background_loading(icon_requests)

    def _populate_grouped_grid(self, filtered_apps: List[Dict[str, Any]]):
        """Populate grid with icons for group"""
        grid_layout = self._launchpad_popup.grid_layout

        # Group apps by group field
        grouped_apps = {}
        uncategorized_apps = []

        for app_data in filtered_apps:
            group = app_data.get("group")
            if group:
                if group not in grouped_apps:
                    grouped_apps[group] = []
                grouped_apps[group].append(app_data)
            else:
                uncategorized_apps.append(app_data)

        # Create list of items to display: group + uncategorized apps
        display_items = []

        for group_name in sorted(grouped_apps.keys()):
            display_items.append({"type": "group", "group": group_name, "apps": grouped_apps[group_name]})

        # Add uncategorized apps
        for app_data in uncategorized_apps:
            display_items.append({"type": "app", "data": app_data})

        # Create widgets for all items
        for item in display_items:
            if item["type"] == "group":
                group_widget = self._create_group_widget(item["group"], item["apps"])
                self._app_icons.append(group_widget)
            else:
                app_icon = self._create_app_icon_widget(item["data"])
                self._app_icons.append(app_icon)

        if self._app_icons:
            first_icon = self._app_icons[0]
            first_icon.setParent(self._launchpad_popup.grid_container)
            first_icon.updateGeometry()

            self._recalculate_grid_columns()

            if self._grid_columns <= 0:
                self._grid_columns = 1

            rows = (len(self._app_icons) + self._grid_columns - 1) // self._grid_columns
            icon_height = self._app_icons[0].height()
            total_height = rows * icon_height
            self._launchpad_popup.grid_container.setFixedHeight(total_height)

        for index, widget in enumerate(self._app_icons):
            if self._grid_columns <= 0:
                self._grid_columns = 1
            row = index // self._grid_columns
            col = index % self._grid_columns
            grid_layout.addWidget(widget, row, col)

        # Load icons in background for uncategorized apps only
        icon_requests = []
        for app_data in uncategorized_apps:
            icon_path = app_data.get("icon", "")
            if icon_path and os.path.isfile(icon_path):
                cache_key = f"{icon_path}_{self._app_icon_size}_{self._dpr}"
                if cache_key not in _ICON_CACHE:
                    icon_requests.append((icon_path, self._app_icon_size, self._dpr))
        if icon_requests:
            self._start_background_loading(icon_requests)

    def _create_group_widget(self, group_name: str, apps: List[Dict[str, Any]]):
        group_widget = QFrame()
        group_widget.setProperty("class", "group-icon")
        group_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        group_widget.setCursor(Qt.CursorShape.PointingHandCursor)
        group_widget.is_group = True
        group_widget.group_name = group_name
        group_widget.apps_in_group = apps

        # Use same layout structure as regular app icons
        container_layout = QVBoxLayout(group_widget)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        icon_container = QFrame()

        group_class = group_name.lower().replace(" ", "-")
        icon_container.setProperty("class", f"group-icon-container {group_class}")
        icon_container.setFixedSize(self._app_icon_size, self._app_icon_size)

        mini_layout = QGridLayout(icon_container)
        margin = 6
        spacing = 6
        mini_layout.setContentsMargins(margin, margin, margin, margin)
        mini_layout.setSpacing(spacing)

        # Available space = container_size - (2 * margin)
        # For 2x2 grid: 2 icons + 1 spacing = available_space
        # So: icon_size = (available_space - spacing) / 2
        available_space = self._app_icon_size - (2 * margin)
        mini_icon_size = (available_space - spacing) // 2
        for i, app in enumerate(apps[:4]):
            if i >= 4:
                break
            row = i // 2
            col = i % 2
            mini_icon_label = QLabel()
            mini_icon_label.setFixedSize(mini_icon_size, mini_icon_size)
            mini_icon_label.setScaledContents(True)

            # Load mini icon
            icon_path = app.get("icon", "")
            if icon_path and os.path.isfile(icon_path):
                try:
                    pixmap = load_and_scale_icon(icon_path, mini_icon_size, self._dpr)
                    if not pixmap.isNull():
                        mini_icon_label.setPixmap(pixmap)
                except:
                    pass

            mini_layout.addWidget(mini_icon_label, row, col)

        # Add icon container with same alignment as regular apps
        container_layout.addWidget(
            icon_container, stretch=1, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )

        title_label = QLabel(group_name)
        title_label.setProperty("class", "title")
        title_label.setWordWrap(True)
        title_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        add_shadow(title_label, self._app_title_shadow)

        # Add title with same alignment as regular apps
        container_layout.addWidget(title_label, stretch=2, alignment=Qt.AlignmentFlag.AlignHCenter)

        def mouseReleaseEvent(event):
            if event.button() == Qt.MouseButton.LeftButton:
                self._open_group(group_name, apps)

        group_widget.mouseReleaseEvent = mouseReleaseEvent

        # Add right-click context menu
        def mousePressEvent(event):
            if event.button() == Qt.MouseButton.RightButton:
                self._show_group_context_menu(event.pos(), group_name, group_widget, event)

        group_widget.mousePressEvent = mousePressEvent

        return group_widget

    def _open_group(self, group_name: str, apps: List[Dict[str, Any]]):
        self._current_group = group_name

        # Hide search input and show back button
        if self._launchpad_popup.search_input:
            self._launchpad_popup.search_input.hide()

        # Create back button once if needed
        if not hasattr(self._launchpad_popup, "back_button"):
            back_button = QPushButton()
            back_button.setProperty("class", "group-back-button")
            back_button.setCursor(Qt.CursorShape.PointingHandCursor)
            back_button.setFixedHeight(40)
            back_button.clicked.connect(self._close_group)
            self._launchpad_popup.search_container.layout().insertWidget(0, back_button)
            self._launchpad_popup.back_button = back_button
            back_button.hide()

        self._launchpad_popup.back_button.setText(f"\U0001f860 {group_name}")
        self._launchpad_popup.back_button.show()

        # Clear grid and app icons
        grid_layout = self._launchpad_popup.grid_layout
        for i in reversed(range(grid_layout.count())):
            child = grid_layout.itemAt(i).widget()
            if child:
                child.setParent(None)
        self._app_icons.clear()

        self._populate_flat_grid(apps)

    def _close_group(self):
        if hasattr(self, "_current_group"):
            delattr(self, "_current_group")

        # Toggle back button and search
        if hasattr(self._launchpad_popup, "back_button"):
            self._launchpad_popup.back_button.hide()
        if self._launchpad_popup.search_input:
            self._launchpad_popup.search_input.show()
            self._launchpad_popup.search_input.clear()

        self._populate_grid()

    def _show_group_context_menu(self, pos, group_name, parent_widget, event):
        """Show context menu for group"""
        menu_parent = parent_widget
        menu = QMenu(menu_parent.window())
        menu.setProperty("class", "context-menu")
        apply_qmenu_style(menu)

        open_action = QAction(f"Open {group_name}", menu_parent)
        open_action.triggered.connect(lambda: self._open_group(group_name, parent_widget.apps_in_group))
        menu.addAction(open_action)

        menu.addSeparator()

        rename_action = QAction("Rename Group", menu_parent)
        rename_action.triggered.connect(lambda: self._rename_group(group_name))
        menu.addAction(rename_action)

        menu.addSeparator()

        exit_action = QAction("Exit Launchpad", menu_parent)
        exit_action.triggered.connect(self._hide_launchpad)
        menu.addAction(exit_action)

        menu.exec(parent_widget.mapToGlobal(event.pos()))

    def _rename_group(self, old_group: str):
        """Rename a group"""
        # Create a minimal app data with just the group field
        dialog = AppDialog(
            parent=self._launchpad_popup,
            app_data={"group": old_group},
            title="Rename Group",
            all_groups=self._get_all_groups(),
            show_only_group=True,
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_name = dialog.get_app_data().get("group", "").strip()
            if new_name and new_name != old_group:
                # Update all apps with this group
                apps = self._load_apps()
                for app in apps:
                    if app.get("group") == old_group:
                        app["group"] = new_name
                self._save_apps(apps)

                # Refresh grid
                if hasattr(self, "_current_group") and self._current_group == old_group:
                    self._close_group()
                else:
                    self._populate_grid()

    def _set_app_group(self, app_data: Dict[str, Any], group: str):
        """Set group for an app"""
        apps = self._load_apps()
        for app in apps:
            if app.get("id") == app_data.get("id"):
                app["group"] = group
                break
        self._save_apps(apps)

        # Refresh grid
        if hasattr(self, "_current_group"):
            updated_apps = self._load_apps()
            group_apps_list = [app for app in updated_apps if app.get("group") == self._current_group]
            if group_apps_list:
                self._open_group(self._current_group, group_apps_list)
            else:
                self._close_group()
        else:
            self._populate_grid()

    def _fade_in_popup(self):
        if self._window_animation["fade_in_duration"] > 0 and self._launchpad_popup:
            self._launchpad_popup.fade_in_animation.start()
        elif self._launchpad_popup:
            self._launchpad_popup.setWindowOpacity(1.0)

    def _fade_out_popup(self):
        if self._is_closing or not self._launchpad_popup:
            return
        self._is_closing = True
        self._cleanup_overlay()
        if self._window_animation["fade_in_duration"] > 0:
            self._launchpad_popup.fade_out_animation.start()
        else:
            self._on_fade_out_finished()

    def _on_fade_out_finished(self):
        if self._is_closing:
            self._cleanup_popup()

    def _apply_blur(self):
        if self._launchpad_popup:
            try:
                Blur(
                    self._launchpad_popup.winId(),
                    Acrylic=False,
                    DarkMode=True if not self._window["fullscreen"] else False,
                    RoundCorners=self._window_style["round_corners"] if not self._window["fullscreen"] else False,
                    RoundCornersType=self._window_style["round_corners_type"],
                    BorderColor=self._window_style["border_color"] if not self._window["fullscreen"] else None,
                )
            except Exception as e:
                logging.warning(f"Failed to apply blur effect: {e}")

    def _cleanup_popup(self):
        if self._launchpad_popup:
            self._cleanup_drop_overlay()
            self._launchpad_popup.hide()
            self._launchpad_popup.deleteLater()
            self._launchpad_popup = None
            self._app_icons.clear()
            self._all_apps.clear()
            self._is_closing = False
            AppListLoader.clear_cache()

            # Clear group state when closing launchpad
            if hasattr(self, "_current_group"):
                delattr(self, "_current_group")

            # Restore focus to previous window
            if self._previous_hwnd:
                set_foreground_hwnd(self._previous_hwnd)
                self._previous_hwnd = 0

    def _cleanup_overlay(self):
        if self._overlay:
            self._overlay.hide()
            self._overlay.deleteLater()
            self._overlay = None

    def _cleanup_drop_overlay(self):
        if self._drop_overlay:
            try:
                self._drop_overlay.hide()
                self._drop_overlay.deleteLater()
            except Exception:
                pass
            self._drop_overlay = None

    def _focus_icon(self, index: int = 0):
        if self._app_icons and 0 <= index < len(self._app_icons):
            icon = self._app_icons[index]
            icon.setFocus()
            icon.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self._scroll_to_icon(icon)
        elif self._launchpad_popup:
            self._launchpad_popup.search_input.setFocus()

    def _focus_first_icon(self):
        self._focus_icon(0)

    def _start_background_loading(self, icon_requests):
        if self._icon_worker and self._icon_worker.isRunning():
            self._icon_worker.terminate()
            self._icon_worker.wait()
        self._icon_worker = IconLoadWorker(icon_requests)
        self._icon_worker.icon_loaded.connect(self._on_background_icon_loaded)
        self._icon_worker.start()

    def _on_background_icon_loaded(self, icon_path: str, pixmap: QPixmap):
        cache_key = f"{icon_path}_{self._app_icon_size}_{self._dpr}"
        _ICON_CACHE[cache_key] = pixmap
        for app_icon in self._app_icons:
            if hasattr(app_icon, "app_data") and app_icon.app_data.get("icon", "") == icon_path:
                if hasattr(app_icon, "_icon_loaded") and not app_icon._icon_loaded:
                    app_icon.icon_label.setPixmap(pixmap)
                    refresh_widget_style(app_icon.icon_label)
                    app_icon._icon_loaded = True

    def _recalculate_grid_columns(self):
        """Recalculate the number of columns based on available width and icon size"""
        scrollbar_width = 0
        scroll_area = self._launchpad_popup.scroll_area
        if scroll_area.verticalScrollBar().isVisible():
            scrollbar_width = 4
        if not self._app_icons:
            self._grid_columns = 1
            return

        grid_container_width = self.popup.grid_container.width() + scrollbar_width

        first_icon = self._app_icons[0]
        first_icon.adjustSize()
        actual_cell_width = first_icon.width()

        max_columns = grid_container_width // actual_cell_width if actual_cell_width > 0 else 1

        calculated_columns = max(1, int(max_columns))
        self._grid_columns = calculated_columns

    def _get_target_screen(self):
        screen = QApplication.screenAt(self.mapToGlobal(self.rect().center()))
        if screen is None:
            screen = QApplication.primaryScreen()
        return screen

    def _add_new_app(self):
        all_groups = self._get_all_groups()
        default_group = self._current_group if hasattr(self, "_current_group") else None
        dialog = AppDialog(
            self._launchpad_popup if self._launchpad_popup else None,
            None,
            self._icons_dir,
            all_groups,
            default_group=default_group,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            app_data = dialog.get_app_data()
            app_data["id"] = int(time.time() * 1000)
            apps = self._load_apps()
            apps.append(app_data)
            self._save_apps(apps)
            if self._launchpad_popup:
                # If we're in a group, refresh the group view
                if hasattr(self, "_current_group"):
                    updated_apps = self._load_apps()
                    group_apps_list = [app for app in updated_apps if app.get("group") == self._current_group]
                    self._open_group(self._current_group, group_apps_list)
                else:
                    self._populate_grid()

    def _edit_app(self, app_data: Dict[str, Any]):
        all_groups = self._get_all_groups()
        dialog = AppDialog(
            self._launchpad_popup if self._launchpad_popup else None, app_data, self._icons_dir, all_groups
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated_data = dialog.get_app_data()
            updated_data["id"] = app_data.get("id", int(time.time() * 1000))
            old_icon = app_data.get("icon", "")
            new_icon = updated_data.get("icon", "")
            icon_changed = old_icon != new_icon
            apps = self._load_apps()
            for i, app in enumerate(apps):
                if app.get("id") == app_data.get("id"):
                    apps[i] = updated_data
                    break
            self._save_apps(apps)
            if icon_changed:
                self._cleanup_unused_icons()
            if self._launchpad_popup:
                self._populate_grid()

    def _warning_dialog(self, message: str):
        """Show a warning dialog with a message"""
        dialog = QDialog(self._launchpad_popup if self._launchpad_popup else None)
        dialog.setWindowTitle("Warning")
        dialog.setMinimumSize(400, 150)
        dialog.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.MSWindowsFixedSizeDialogHint
        )
        dialog.setProperty("class", "app-dialog")

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(20, 20, 20, 0)
        content_layout.setSpacing(0)

        message_label = QLabel(message)
        message_label.setWordWrap(True)
        message_label.setProperty("class", "message")
        message_label.setTextFormat(Qt.TextFormat.RichText)
        content_layout.addWidget(message_label)
        layout.addWidget(content_container)

        button_container = QFrame()
        button_container.setProperty("class", "buttons-container")
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)

        ok_btn = QPushButton("OK")
        ok_btn.setProperty("class", "button")
        ok_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(ok_btn)

        layout.addWidget(button_container)
        dialog.setLayout(layout)

        dialog.exec()

    def _delete_app(self, app_data: Dict[str, Any]):
        """Delete an app with modern styled confirmation dialog"""
        dialog = QDialog(self._launchpad_popup if self._launchpad_popup else None)
        dialog.setWindowTitle("Delete App")
        dialog.setMinimumSize(400, 150)
        dialog.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.MSWindowsFixedSizeDialogHint
        )
        dialog.setProperty("class", "app-dialog")

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(20, 20, 20, 0)
        content_layout.setSpacing(0)

        message_label = QLabel(f"Are you sure you want to delete '{app_data.get('title', 'Unknown')}'?")
        message_label.setWordWrap(True)
        message_label.setProperty("class", "message")
        content_layout.addWidget(message_label)
        layout.addWidget(content_container)

        button_container = QFrame()
        button_container.setProperty("class", "buttons-container")
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "button")
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_btn)

        delete_btn = QPushButton("Delete")
        delete_btn.setProperty("class", "button delete")
        delete_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(delete_btn)

        layout.addWidget(button_container)
        dialog.setLayout(layout)
        delete_btn.setAutoDefault(True)
        delete_btn.setDefault(True)
        delete_btn.setFocus()
        result = dialog.exec()
        if result == QDialog.DialogCode.Accepted:
            apps = self._load_apps()
            app_id = app_data.get("id")
            prev_focus_index = None
            for i, app in enumerate(apps):
                if app.get("id") == app_id:
                    prev_focus_index = i - 1 if i > 0 else 0
                    break
            if app_id is not None:
                apps = [app for app in apps if app.get("id") != app_id]
            else:
                apps = [app for app in apps if app != app_data]
            self._save_apps(apps)
            self._cleanup_unused_icons()
            if self._launchpad_popup:
                # If we're in a group, check if there are apps left in the group
                if hasattr(self, "_current_group"):
                    group_apps = [app for app in apps if app.get("group") == self._current_group]
                    if group_apps:
                        # Still apps in group, refresh the group view
                        self._open_group(self._current_group, group_apps)
                    else:
                        # No apps left in group, go back to main window
                        self._close_group()
                else:
                    # Not in a group, just refresh the grid
                    self._populate_grid()

                if self._app_icons:
                    if prev_focus_index is not None and 0 <= prev_focus_index < len(self._app_icons):
                        self._app_icons[prev_focus_index].setFocus()
                    else:
                        self._app_icons[0].setFocus()

    def _cleanup_unused_icons(self):
        try:
            if not os.path.exists(self._icons_dir):
                return
            apps = self._load_apps()
            used_icons = set()
            for app in apps:
                icon_path = app.get("icon", "")
                if icon_path and os.path.isfile(icon_path):
                    used_icons.add(os.path.basename(icon_path))
            for filename in os.listdir(self._icons_dir):
                if filename not in used_icons:
                    unused_icon_path = os.path.join(self._icons_dir, filename)
                    try:
                        os.remove(unused_icon_path)
                    except Exception as e:
                        logging.warning(f"Failed to remove unused icon {filename}: {e}")

                    for cache_key in list(_ICON_CACHE.keys()):
                        if filename in cache_key:
                            del _ICON_CACHE[cache_key]

        except Exception as e:
            logging.error(f"Failed to cleanup unused icons: {e}")

    def _load_apps(self) -> List[Dict[str, Any]]:
        try:
            if os.path.exists(self._data_file):
                with open(self._data_file, "r", encoding="utf-8") as f:
                    apps = json.load(f)
                return apps
        except Exception as e:
            logging.error(f"Failed to load apps from {self._data_file}: {e}")
        return []

    def _get_all_groups(self) -> List[str]:
        """Get all unique groups from apps"""
        apps = self._load_apps()
        groups = set()
        for app in apps:
            group = app.get("group")
            if group:
                groups.add(group)
        return sorted(list(groups))

    def _order_apps(self, order_type: str):
        """Order apps based on the specified type"""
        try:
            apps = self._load_apps()
            if not apps:
                return

            if order_type == "az":
                apps.sort(key=lambda app: app.get("title", "").lower())
            elif order_type == "za":
                apps.sort(key=lambda app: app.get("title", "").lower(), reverse=True)
            elif order_type == "recent":
                apps.sort(key=lambda app: app.get("id", 0), reverse=True)
            elif order_type == "oldest":
                apps.sort(key=lambda app: app.get("id", 0))

            self._save_apps(apps)

            if self._launchpad_popup:
                current_search = self._launchpad_popup.search_input.text()
                self._populate_grid(current_search)

        except Exception as e:
            logging.error(f"Failed to order apps by {order_type}: {e}")

    def _save_apps(self, apps: List[Dict[str, Any]]):
        try:
            with open(self._data_file, "w", encoding="utf-8") as f:
                json.dump(apps, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Failed to save apps to {self._data_file}: {e}")
