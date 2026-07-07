import io
from collections.abc import Callable
from typing import Any

from PIL import Image
from PyQt6.QtCore import QPoint, QSize, Qt
from PyQt6.QtGui import QIcon, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QMenu, QPushButton, QWidget

from core.bar_helper import GlobalState
from core.utils.qobject import is_valid_qobject
from core.utils.shell_utils import shell_open
from core.utils.tooltip import set_tooltip
from core.utils.win32.utils import apply_qmenu_style
from core.widgets.services.power_menu.power_commands import PowerOperations
from core.widgets.services.power_menu.user_info import get_user_avatar_path, get_windows_username


class SystemControlsSectionWidget(QFrame):
    """Section containing system-level controls: user profile, settings, and power menu."""

    def __init__(self, parent: QWidget, config: object, refresh_popup: object, tooltip: bool = False):
        super().__init__(parent)
        self.config = config
        self.refresh_popup = refresh_popup
        self._tooltip = tooltip
        self.setProperty("class", "section system-controls")

        self._power_ops = PowerOperations(main_window=parent)

        self._settings_btn: QPushButton | None = None
        self._settings_menu: QMenu | None = None
        self._power_btn: QPushButton | None = None
        self._power_menu: QMenu | None = None
        self._profile_image_btn: QPushButton | None = None
        self._profile_menu: QMenu | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._build_profile_controls(layout)

        layout.addStretch(1)

        self._settings_btn = QPushButton(config.settings_icon, self)
        self._settings_btn.setProperty("class", "button settings")
        self._settings_btn.clicked.connect(self._show_settings_menu)
        if self._tooltip:
            set_tooltip(self._settings_btn, "Settings", position="top")
        layout.addWidget(self._settings_btn)

        self._power_btn = QPushButton(config.power_icon, self)
        self._power_btn.setProperty("class", "button power")
        self._power_btn.clicked.connect(self._show_power_menu)
        if self._tooltip:
            set_tooltip(self._power_btn, "Shut Down", position="top")
        layout.addWidget(self._power_btn)

    def _build_profile_controls(self, layout: QHBoxLayout):
        self._profile_image_btn = QPushButton(self)
        self._profile_image_btn.setProperty("class", "button profile-image")
        profile_image_size = self.config.profile_image_size
        icon = self._build_profile_image_icon(profile_image_size)
        if icon is not None:
            self._profile_image_btn.setIcon(icon)
            self._profile_image_btn.setIconSize(QSize(profile_image_size, profile_image_size))
        self._profile_image_btn.clicked.connect(self._show_profile_menu)
        if self._tooltip:
            set_tooltip(self._profile_image_btn, get_windows_username(), position="top")
        layout.addWidget(self._profile_image_btn)

    def _build_profile_image_icon(self, size: int) -> QIcon | None:
        profile_image_path = get_user_avatar_path()
        if not profile_image_path:
            return None

        try:
            with Image.open(profile_image_path) as image:
                if image.mode != "RGBA":
                    image = image.convert("RGBA")

                width, height = image.size
                if width > height:
                    left = (width - height) // 2
                    square = image.crop((left, 0, left + height, height))
                elif height > width:
                    top = (height - width) // 2
                    square = image.crop((0, top, width, top + width))
                else:
                    square = image

                resized = square.resize((size, size), Image.LANCZOS)
                buffer = io.BytesIO()
                resized.save(buffer, format="PNG")
                pixmap = QPixmap()
                if not pixmap.loadFromData(buffer.getvalue()):
                    return None
        except Exception:
            return None

        rounded = QPixmap(size, size)
        rounded.fill(Qt.GlobalColor.transparent)
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addEllipse(0, 0, size, size)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, pixmap)
        painter.end()
        return QIcon(rounded)

    def _create_context_menu(self) -> QMenu:
        menu = QMenu(self.window())
        apply_qmenu_style(menu)
        menu.setProperty("class", "context-menu dark" if GlobalState.is_dark() else "context-menu")
        return menu

    @staticmethod
    def _populate_menu(menu: QMenu, items: list[tuple[str, Callable[..., Any]] | None]):
        for item in items:
            if item is None:
                menu.addSeparator()
            else:
                label, callback = item
                action = menu.addAction(label)
                action.triggered.connect(callback)

    def _show_settings_menu(self):
        if self._settings_menu and is_valid_qobject(self._settings_menu) and self._settings_menu.isVisible():
            self._settings_menu.close()
            return

        menu = self._create_context_menu()
        links = [
            ("Windows Update", "ms-settings:windowsupdate"),
            ("Network && Internet", "ms-settings:network"),
            ("Bluetooth && Devices", "ms-settings:bluetooth"),
            ("Sound", "ms-settings:sound"),
            ("Notifications", "ms-settings:notifications"),
            ("Power && Battery", "ms-settings:powersleep"),
            ("Apps", "ms-settings:appsfeatures"),
            ("Accounts", "ms-settings:yourinfo"),
            ("Privacy && Security", "ms-settings:privacy"),
            None,
            ("All Settings", "ms-settings:"),
        ]
        self._populate_menu(
            menu,
            [link if link is None else (link[0], lambda c=False, u=link[1]: shell_open(u)) for link in links],
        )

        self._settings_menu = menu
        btn = self._settings_btn
        pos = btn.mapToGlobal(QPoint(btn.width() - menu.sizeHint().width(), btn.height() + 6))
        btn.setAttribute(Qt.WidgetAttribute.WA_UnderMouse, False)
        btn.update()
        menu.popup(pos)

    def _show_profile_menu(self):
        if self._profile_menu and is_valid_qobject(self._profile_menu) and self._profile_menu.isVisible():
            self._profile_menu.close()
            return

        menu = self._create_context_menu()
        username_action = menu.addAction(get_windows_username())
        username_action.triggered.connect(lambda checked=False: shell_open("ms-settings:yourinfo"))
        menu.addSeparator()
        self._populate_menu(
            menu,
            [
                ("Lock", self._power_ops.lock),
                ("Sign Out", self._power_ops.signout),
            ],
        )

        self._profile_menu = menu
        btn = self._profile_image_btn
        pos = btn.mapToGlobal(QPoint(0, btn.height() + 6))
        btn.setAttribute(Qt.WidgetAttribute.WA_UnderMouse, False)
        btn.update()
        menu.popup(pos)

    def _show_power_menu(self):
        if self._power_menu and is_valid_qobject(self._power_menu) and self._power_menu.isVisible():
            self._power_menu.close()
            return

        menu = self._create_context_menu()
        self._populate_menu(
            menu,
            [
                ("Sleep", self._power_ops.sleep),
                ("Hibernate", self._power_ops.hibernate),
                ("Restart", self._power_ops.restart),
                ("Shut Down", self._power_ops.shutdown),
            ],
        )

        self._power_menu = menu
        btn = self._power_btn
        pos = btn.mapToGlobal(QPoint(btn.width() - menu.sizeHint().width(), btn.height() + 6))
        btn.setAttribute(Qt.WidgetAttribute.WA_UnderMouse, False)
        btn.update()
        menu.popup(pos)

    def refresh_state(self) -> None:
        if self._settings_menu and is_valid_qobject(self._settings_menu):
            self._settings_menu.close()
        if self._profile_menu and is_valid_qobject(self._profile_menu):
            self._profile_menu.close()
        if self._power_menu and is_valid_qobject(self._power_menu):
            self._power_menu.close()
