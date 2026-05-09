import ctypes
import datetime
import os

from PyQt6 import QtCore
from PyQt6.QtCore import QPropertyAnimation, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStyle,
    QStyleOption,
    QVBoxLayout,
)

from core.utils.utilities import PopupWidget, refresh_widget_style
from core.utils.win32.backdrop import enable_blur
from core.utils.win32.window_actions import force_foreground_focus
from core.validation.widgets.yasb.power_menu import PowerMenuConfig
from core.widgets.base import BaseWidget
from core.widgets.services.power_menu.power_commands import PowerOperations
from core.widgets.services.power_menu.user_info import (
    get_account_type,
    get_user_avatar_path,
    get_user_email,
    get_windows_username,
)


class AnimatedWidget(QFrame):
    def __init__(self, animation_duration, parent=None):
        super().__init__(parent)
        self.animation_duration = animation_duration
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.finished.connect(self._on_animation_finished)
        self._closing = False

    def fade_in(self):
        self._closing = False
        self.animation.stop()
        self.animation.setDuration(self.animation_duration)
        self.animation.setStartValue(0)
        self.animation.setEndValue(1)
        self.animation.start()

    def fade_out(self):
        self._closing = True
        self.animation.stop()
        self.animation.setDuration(self.animation_duration)
        self.animation.setStartValue(1)
        self.animation.setEndValue(0)
        self.animation.start()

    def _on_animation_finished(self):
        if self._closing:
            self._closing = False
            self.hide()


class OverlayWidget(AnimatedWidget):
    def __init__(self, parent, animation_duration, uptime, blur_background):
        super().__init__(animation_duration, parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setProperty("class", "power-menu-overlay")
        self._blur_background_enabled = blur_background

        if uptime:
            self.boot_time()

    def update_geometry(self, screen_geometry):
        self.setGeometry(screen_geometry)

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 1))
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, painter, self)

    def showEvent(self, event):
        super().showEvent(event)
        if self._blur_background_enabled:
            enable_blur(
                self.winId(),
                DarkMode=False,
                RoundCorners=False,
                BorderColor="None",
            )

    def boot_time(self):
        uptime_seconds = int(ctypes.windll.kernel32.GetTickCount64() / 1000)
        delta = datetime.timedelta(seconds=uptime_seconds)
        days, hours = delta.days, delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        parts = []
        if days > 0:
            parts.append(f"{days} day{'s' if days > 1 else ''}")
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours > 1 else ''}")
        if minutes > 0:
            parts.append(f"{minutes} min")

        label = QLabel(f"Uptime {' '.join(parts)}", self)
        label.setProperty("class", "uptime")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch()
        layout.addWidget(label)


class PowerMenuWidget(BaseWidget):
    validation_schema = PowerMenuConfig

    def __init__(self, config: PowerMenuConfig):
        super().__init__(0, class_name="power-menu-widget")
        self.config = config

        # Construct container and label
        self._init_container()
        self.build_widget_label(self.config.label, None)

        self.register_callback("toggle_power_menu", self._show_main_window)

        self.callback_left = self.config.callbacks.on_left
        self.callback_right = self.config.callbacks.on_right
        self.callback_middle = self.config.callbacks.on_middle

        self.main_window = None
        self._popup = None

    def _cleanup_main_window(self):
        if self.main_window:
            self.main_window.overlay.deleteLater()
            self.main_window.deleteLater()
            self.main_window = None

    def _show_main_window(self):
        if self.config.menu_style == "popup":
            self._show_popup_menu()
            return
        if self.main_window and self.main_window.isVisible():
            self.main_window.fade_out()
            self.main_window.overlay.fade_out()
        else:
            self._cleanup_main_window()
            self.main_window = MainWindow(
                self,
                self.config.uptime,
                self.config.blur,
                self.config.blur_background,
                self.config.animation_duration,
                self.config.button_row,
                self.config.buttons.model_dump(exclude_none=True),
                self.config.show_user,
                self.config.profile_image_size,
            )
            self.main_window.overlay.fade_in()
            self.main_window.overlay.show()
            self.main_window.show()
            force_foreground_focus(int(self.main_window.winId()))

    def _show_popup_menu(self):
        popup_cfg = self.config.popup
        self._popup = PopupWidget(
            self,
            popup_cfg.blur,
            popup_cfg.round_corners,
            popup_cfg.round_corners_type,
            popup_cfg.border_color,
        )
        self._popup.setProperty("class", "power-menu-compact")

        main_layout = QVBoxLayout(self._popup)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        if self.config.show_user:
            profile_frame = QFrame()
            profile_frame.setProperty("class", "profile-info")
            profile_layout = QVBoxLayout(profile_frame)
            profile_layout.setSpacing(0)
            profile_layout.setContentsMargins(0, 0, 0, 0)

            avatar_label = QLabel()
            avatar_label.setProperty("class", "profile-avatar")
            avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            avatar_size = self.config.profile_image_size
            avatar_label.setFixedSize(avatar_size, avatar_size)
            avatar_path = get_user_avatar_path()
            if avatar_path:
                pixmap = QPixmap(avatar_path)
                if not pixmap.isNull():
                    size = avatar_size
                    pixmap = pixmap.scaled(
                        size,
                        size,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    if pixmap.width() > size or pixmap.height() > size:
                        pixmap = pixmap.copy((pixmap.width() - size) // 2, (pixmap.height() - size) // 2, size, size)
                    rounded = QPixmap(size, size)
                    rounded.fill(Qt.GlobalColor.transparent)
                    painter = QPainter(rounded)
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    path = QPainterPath()
                    path.addEllipse(0, 0, size, size)
                    painter.setClipPath(path)
                    painter.drawPixmap(0, 0, pixmap)
                    painter.end()
                    avatar_label.setPixmap(rounded)
            profile_layout.addWidget(avatar_label, alignment=Qt.AlignmentFlag.AlignCenter)

            username_label = QLabel(get_windows_username())
            username_label.setProperty("class", "profile-username")
            username_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            profile_layout.addWidget(username_label, alignment=Qt.AlignmentFlag.AlignCenter)

            account_type_label = QLabel(get_account_type())
            account_type_label.setProperty("class", "profile-account-type")
            account_type_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            profile_layout.addWidget(account_type_label, alignment=Qt.AlignmentFlag.AlignCenter)

            user_email = get_user_email()
            if user_email:
                email_label = QLabel(user_email)
                email_label.setProperty("class", "profile-email")
                email_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                profile_layout.addWidget(email_label, alignment=Qt.AlignmentFlag.AlignCenter)

            manage_btn = QPushButton("Manage accounts")
            manage_btn.setProperty("class", "manage-accounts")
            manage_btn.clicked.connect(lambda: (self._popup.hide(), os.startfile("ms-settings:accounts")))
            profile_layout.addWidget(manage_btn, alignment=Qt.AlignmentFlag.AlignCenter)

            main_layout.addWidget(profile_frame)

        buttons_frame = QFrame()
        buttons_frame.setProperty("class", "buttons")
        buttons_layout = QVBoxLayout(buttons_frame)
        buttons_layout.setSpacing(0)
        buttons_layout.setContentsMargins(0, 0, 0, 0)

        power_operations = PowerOperations(self._popup)
        buttons = self.config.buttons.model_dump(exclude_none=True)
        for button_name, button_info in buttons.items():
            if button_name == "cancel":
                continue
            icon_text, label_text = button_info
            action = getattr(power_operations, button_name, None)
            if action is None:
                continue

            btn_frame = QFrame()
            btn_frame.setProperty("class", f"button {button_name.replace('_', '-')}")
            btn_layout = QHBoxLayout(btn_frame)
            btn_layout.setSpacing(0)
            btn_layout.setContentsMargins(0, 0, 0, 0)

            if icon_text:
                icon_label = QLabel(icon_text)
                icon_label.setProperty("class", "icon")
                icon_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                icon_label.setTextFormat(Qt.TextFormat.RichText)
                btn_layout.addWidget(icon_label)

            text_label = QLabel(label_text)
            text_label.setProperty("class", "label")
            text_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            btn_layout.addWidget(text_label)
            btn_layout.addStretch()

            btn_frame._action = action
            btn_frame.mousePressEvent = lambda _, a=action: a()
            btn_frame.installEventFilter(self)
            buttons_layout.addWidget(btn_frame)

        main_layout.addWidget(buttons_frame)

        self._popup.adjustSize()
        self._popup.setPosition(
            alignment=popup_cfg.alignment,
            direction=popup_cfg.direction,
            offset_left=popup_cfg.offset_left,
            offset_top=popup_cfg.offset_top,
        )
        self._popup.show()

    def eventFilter(self, source, event):
        if isinstance(source, QFrame) and hasattr(source, "_action"):
            if event.type() == QtCore.QEvent.Type.Enter:
                base = source.property("class")
                if "hover" not in base:
                    source.setProperty("class", f"{base} hover")
                    refresh_widget_style(source)
                    for child in source.findChildren(QLabel):
                        child_base = child.property("class")
                        if "hover" not in child_base:
                            child.setProperty("class", f"{child_base} hover")
                        refresh_widget_style(child)
            elif event.type() == QtCore.QEvent.Type.Leave:
                base = source.property("class")
                source.setProperty("class", base.replace(" hover", ""))
                refresh_widget_style(source)
                for child in source.findChildren(QLabel):
                    child_base = child.property("class")
                    child.setProperty("class", child_base.replace(" hover", ""))
                    refresh_widget_style(child)
        return super().eventFilter(source, event)


class MainWindow(AnimatedWidget):
    def __init__(
        self,
        parent,
        uptime,
        blur,
        blur_background,
        animation_duration,
        button_row,
        buttons,
        show_user,
        profile_size,
    ):
        super().__init__(animation_duration, parent)

        self.overlay = OverlayWidget(parent, animation_duration, uptime, blur_background)
        self.button_row = button_row
        self.buttons_list = []
        self.current_focus_index = -1

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setProperty("class", "power-menu-popup")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        self.power_operations = PowerOperations(self, self.overlay)

        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        if show_user:
            profile_frame = QFrame(self)
            profile_frame.setProperty("class", "profile-info")
            profile_layout = QVBoxLayout(profile_frame)
            profile_layout.setSpacing(0)
            profile_layout.setContentsMargins(0, 0, 0, 0)

            avatar_label = QLabel(self)
            avatar_label.setProperty("class", "profile-avatar")
            avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            avatar_label.setFixedSize(profile_size, profile_size)
            avatar_path = get_user_avatar_path()
            if avatar_path:
                pixmap = QPixmap(avatar_path)
                if not pixmap.isNull():
                    size = profile_size
                    pixmap = pixmap.scaled(
                        size,
                        size,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    if pixmap.width() > size or pixmap.height() > size:
                        pixmap = pixmap.copy((pixmap.width() - size) // 2, (pixmap.height() - size) // 2, size, size)
                    rounded = QPixmap(size, size)
                    rounded.fill(Qt.GlobalColor.transparent)
                    painter = QPainter(rounded)
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    path = QPainterPath()
                    path.addEllipse(0, 0, size, size)
                    painter.setClipPath(path)
                    painter.drawPixmap(0, 0, pixmap)
                    painter.end()
                    avatar_label.setPixmap(rounded)
            profile_layout.addWidget(avatar_label, alignment=Qt.AlignmentFlag.AlignCenter)

            username_label = QLabel(get_windows_username(), self)
            username_label.setProperty("class", "profile-username")
            username_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            profile_layout.addWidget(username_label, alignment=Qt.AlignmentFlag.AlignCenter)

            account_type_label = QLabel(get_account_type(), self)
            account_type_label.setProperty("class", "profile-account-type")
            account_type_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            profile_layout.addWidget(account_type_label, alignment=Qt.AlignmentFlag.AlignCenter)

            user_email = get_user_email()
            if user_email:
                email_label = QLabel(user_email, self)
                email_label.setProperty("class", "profile-email")
                email_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                profile_layout.addWidget(email_label, alignment=Qt.AlignmentFlag.AlignCenter)

            main_layout.addWidget(profile_frame)

        buttons_frame = QFrame(self)
        buttons_frame.setProperty("class", "buttons")
        buttons_layout = QVBoxLayout(buttons_frame)
        buttons_layout.setSpacing(0)
        buttons_layout.setContentsMargins(0, 0, 0, 0)

        action_buttons = [(name, info) for name, info in buttons.items() if name != "cancel"]
        cancel_button = buttons.get("cancel")
        self.primary_button_count = len(action_buttons)
        self.cancel_button_index = -1

        def build_button(button_name, button_info):
            icon, label = button_info
            action = getattr(self.power_operations, button_name, self.power_operations.cancel)

            button = QPushButton(self)
            button.setProperty("class", f"button {button_name.replace('_', '-')}")
            btn_layout = QVBoxLayout(button)
            btn_layout.setSpacing(0)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.buttons_list.append(button)

            if icon:
                icon_label = QLabel(icon, button)
                icon_label.setProperty("class", "icon")
                icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                icon_label.setTextFormat(Qt.TextFormat.RichText)
                btn_layout.addWidget(icon_label)

            text_label = QLabel(label, button)
            text_label.setProperty("class", "label")
            text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            btn_layout.addWidget(text_label)

            button.clicked.connect(action)
            button.installEventFilter(self)
            return button

        row_layouts = []
        for i, (button_name, button_info) in enumerate(action_buttons):
            if i % button_row == 0:
                row = QHBoxLayout()
                row.setSpacing(0)
                row.setContentsMargins(0, 0, 0, 0)
                row_layouts.append(row)
                buttons_layout.addLayout(row)

            row_layouts[-1].addWidget(build_button(button_name, button_info))

        if cancel_button:
            cancel_row = QHBoxLayout()
            cancel_row.setSpacing(0)
            cancel_row.setContentsMargins(0, 22, 0, 0)
            cancel_row.addStretch(1)
            cancel_row.addWidget(build_button("cancel", cancel_button))
            cancel_row.addStretch(1)
            buttons_layout.addLayout(cancel_row)
            self.cancel_button_index = len(self.buttons_list) - 1

        main_layout.addWidget(buttons_frame)
        self.setLayout(main_layout)
        self.adjustSize()
        self.center_on_screen()

        if blur:
            enable_blur(
                self.winId(),
                DarkMode=False,
                RoundCorners=True,
                BorderColor="None",
            )

        self.fade_in()

    def center_on_screen(self):
        screen = QApplication.screenAt(self.parent().mapToGlobal(QtCore.QPoint(0, 0)))
        if screen is None:
            screen = QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        window_geometry = self.geometry()
        x = (screen_geometry.width() - window_geometry.width()) // 2 + screen_geometry.x()
        y = (screen_geometry.height() - window_geometry.height()) // 2 + screen_geometry.y()
        self.move(x, y)
        self.overlay.update_geometry(screen_geometry)

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, painter, self)

    def _get_base_class(self, source):
        """Get button class without hover state."""
        parts = source.property("class").split()
        return " ".join(p for p in parts if p != "hover")

    def _apply_hover(self, button, hover):
        """Apply or remove hover class and refresh styles."""
        base = self._get_base_class(button)
        button.setProperty("class", f"{base} hover" if hover else base)
        refresh_widget_style(button)
        for child in button.findChildren(QLabel):
            refresh_widget_style(child)

    def eventFilter(self, source, event):
        if isinstance(source, QPushButton):
            if event.type() == QtCore.QEvent.Type.Enter:
                self._apply_hover(source, True)
            elif event.type() == QtCore.QEvent.Type.Leave:
                self._apply_hover(source, False)
        return super().eventFilter(source, event)

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.cancel_action()
        elif key == Qt.Key.Key_Right:
            self.navigate_focus(1)
        elif key == Qt.Key.Key_Left:
            self.navigate_focus(-1)
        elif key == Qt.Key.Key_Down:
            self.navigate_focus(self.button_row)
        elif key == Qt.Key.Key_Up:
            self.navigate_focus(-self.button_row)
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            if 0 <= self.current_focus_index < len(self.buttons_list):
                self.buttons_list[self.current_focus_index].click()
        else:
            super().keyPressEvent(event)
            return
        event.accept()

    def navigate_focus(self, step):
        """Navigate button focus by step."""
        if not self.buttons_list:
            return

        total_buttons = len(self.buttons_list)

        # If no button is currently focused, start with the appropriate first button
        if self.current_focus_index < 0 or self.current_focus_index >= total_buttons:
            if step > 0:
                # When pressing right or down arrow with no selection, select the first button
                new_index = 0
            elif step < 0:
                # When pressing left or up arrow with no selection, select the last button
                new_index = total_buttons - 1
            else:
                # Default to first button
                new_index = 0
        else:
            # Normal navigation with existing selection
            current = self.current_focus_index

            if step == 1:  # Right
                new_index = (current + 1) % total_buttons
            elif step == -1:  # Left
                new_index = (current - 1) % total_buttons
            elif self.cancel_button_index != -1 and step in (self.button_row, -self.button_row):
                if current == self.cancel_button_index:
                    if step == -self.button_row and self.primary_button_count > 0:
                        new_index = min(self.primary_button_count // 2, self.primary_button_count - 1)
                    else:
                        new_index = 0
                else:
                    new_index = self.cancel_button_index
            elif step == self.button_row or step == -self.button_row:  # Up/Down - vertical movement
                # Calculate the current row and column
                current_row = current // self.button_row
                current_col = current % self.button_row

                # Determine total rows
                total_rows = (total_buttons + self.button_row - 1) // self.button_row

                if step == self.button_row:  # Down
                    # Move to next row, same column
                    new_row = (current_row + 1) % total_rows
                else:  # Up
                    # Move to previous row, same column
                    new_row = (current_row - 1) % total_rows

                # Calculate new index
                new_index = new_row * self.button_row + current_col

                # If we've moved to a partial row and the column is beyond its bounds
                if new_index >= total_buttons:
                    if step == self.button_row:
                        # When moving down to an out-of-bounds position, wrap to first row
                        new_index = current_col
                    else:
                        # When moving up to an out-of-bounds position, use last valid button
                        new_index = total_buttons - 1
            else:
                new_index = current  # No change

        new_index = max(0, min(new_index, total_buttons - 1))
        self.set_focused_button(new_index)

    def set_focused_button(self, index):
        """Set focus to the button at the given index."""
        if not self.buttons_list or not (0 <= index < len(self.buttons_list)):
            return

        prev_index = self.current_focus_index
        self.current_focus_index = index

        if 0 <= prev_index < len(self.buttons_list):
            self._apply_hover(self.buttons_list[prev_index], False)

        self._apply_hover(self.buttons_list[index], True)
        self.setFocus()

    def showEvent(self, event):
        super().showEvent(event)
        self.setFocus()
        self.current_focus_index = -1

    def cancel_action(self):
        self.power_operations.cancel()
