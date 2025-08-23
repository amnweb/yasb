import ctypes
import logging
import os
import re
import winreg

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout
from win32con import WM_INPUTLANGCHANGEREQUEST

from core.utils.utilities import PopupWidget, add_shadow, build_widget_label
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.win32.bindings import (
    kernel32,
    user32,
)
from core.utils.win32.constants import (
    LOCALE_NAME_MAX_LENGTH,
    LOCALE_SCOUNTRY,
    LOCALE_SISO639LANGNAME,
    LOCALE_SISO639LANGNAME2,
    LOCALE_SISO3166CTRYNAME,
    LOCALE_SLANGUAGE,
    LOCALE_SNAME,
    LOCALE_SNATIVECTRYNAME,
    LOCALE_SNATIVELANGNAME,
)
from core.validation.widgets.yasb.language import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget


class LanguageWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
        self,
        label: str,
        label_alt: str,
        update_interval: int,
        class_name: str,
        animation: dict[str, str],
        container_padding: dict[str, int],
        callbacks: dict[str, str],
        language_menu: dict[str, str] = None,
        label_shadow: dict = None,
        container_shadow: dict = None,
    ):
        super().__init__(int(update_interval * 1000), class_name=f"language-widget {class_name}")

        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt
        self._animation = animation
        self._padding = container_padding
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow
        self._menu_config = language_menu

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

        build_widget_label(self, self._label_content, self._label_alt_content, self._label_shadow)

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("update_label", self._update_label)
        self.register_callback("toggle_menu", self._toggle_menu)

        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]
        self.callback_timer = "update_label"

        # Cache for available languages
        self._available_languages = None

        # Focused window info for activating the layout from the menu
        self._focused_window_hwnd: int | None = None

        self.start_timer()

    def _toggle_label(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

    def _toggle_menu(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self._show_language_menu()

    def _update_label(self):
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content
        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0
        try:
            lang = self._get_current_keyboard_language()
        except:
            lang = None

        for part in label_parts:
            part = part.strip()
            if part and widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                if "<span" in part and "</span>" in part:
                    # Ensure the icon is correctly set
                    icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                    active_widgets[widget_index].setText(icon)
                else:
                    # Update label with formatted content
                    formatted_text = part.format(lang=lang) if lang else part
                    active_widgets[widget_index].setText(formatted_text)
                widget_index += 1

    def _on_settings_click(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._open_language_settings()
            self._menu.hide()

    def _open_language_settings(self):
        """Open Windows language settings"""
        try:
            os.startfile("ms-settings:regionlanguage")
        except Exception:
            # Fallback to the old Control Panel if Settings app fails
            os.startfile(os.path.join(os.environ["SystemRoot"], "System32", "control.exe"), "intl.cpl")

    def _show_language_menu(self):
        """Show popup menu with available languages"""
        self._menu = PopupWidget(
            self,
            self._menu_config["blur"],
            self._menu_config["round_corners"],
            self._menu_config["round_corners_type"],
            self._menu_config["border_color"],
        )
        self._menu.setProperty("class", "language-menu")

        main_layout = QVBoxLayout(self._menu)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Header
        header_label = QLabel("Keyboard Layouts")
        header_label.setProperty("class", "header")
        main_layout.addWidget(header_label)

        # Get available languages
        available_languages = self._get_available_languages()
        current_lang_id = self._get_current_language_id()

        # Create language items
        for lang_info in available_languages:
            self._create_language_item(main_layout, lang_info, lang_info["id"] == current_lang_id)

        footer_label = QLabel("More keyboard settings")
        footer_label.setProperty("class", "footer")
        footer_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        footer_label.mousePressEvent = self._on_settings_click
        main_layout.addWidget(footer_label)

        self._menu.adjustSize()
        self._menu.setPosition(
            alignment=self._menu_config["alignment"],
            direction=self._menu_config["direction"],
            offset_left=self._menu_config["offset_left"],
            offset_top=self._menu_config["offset_top"],
        )

        # Focused widnow handle
        self._focused_window_hwnd = user32.GetForegroundWindow()

        self._menu.show()

    def _create_language_item(self, layout, lang_info, is_current=False):
        """Create a language menu item"""
        container = QFrame()
        container.setProperty("class", f"language-item{' active' if is_current else ''}")
        container.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        container.setContentsMargins(0, 0, 0, 0)

        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Left: language code or icon
        lang_code_label = QLabel(lang_info["code"])
        lang_code_label.setProperty("class", "icon" if self._menu_config["show_layout_icon"] else "code")
        lang_code_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        container_layout.addWidget(lang_code_label)

        # Right: stack name above layout name
        name_layout = QVBoxLayout()
        name_layout.setContentsMargins(0, 0, 0, 0)
        name_layout.setSpacing(2)

        # Top: language name
        lang_name_label = QLabel(lang_info["name"])
        lang_name_label.setProperty("class", "name")
        name_layout.addWidget(lang_name_label)

        # Bottom: layout name
        layout_name_label = QLabel(lang_info["layouts"])
        layout_name_label.setProperty("class", "layout")
        layout_name_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        name_layout.addWidget(layout_name_label)

        container_layout.addLayout(name_layout)

        def mouse_press_handler(event):
            if event.button() == Qt.MouseButton.LeftButton:
                success = self._switch_to_language(lang_info["id"])
                if not success:
                    logging.error(f"Failed to switch to {lang_info['name']}")
                self._menu.hide()

        container.mousePressEvent = mouse_press_handler

        layout.addWidget(container)

    def _get_available_languages(self):
        """Get list of all installed input languages"""
        if self._available_languages is not None:
            return self._available_languages

        languages = []

        # Get number of keyboard layouts
        num_layouts = user32.GetKeyboardLayoutList(0, None)
        if num_layouts == 0:
            return languages

        # Get all keyboard layouts
        layout_array = (ctypes.c_void_p * num_layouts)()
        user32.GetKeyboardLayoutList(num_layouts, layout_array)

        # Save current layout to restore later
        current_layout = user32.ActivateKeyboardLayout(0, 0)
        seen_handles = set()

        for i in range(num_layouts):
            layout_handle = layout_array[i]
            lang_id = layout_handle & 0xFFFF

            # Skip duplicates
            if layout_handle in seen_handles:
                continue
            seen_handles.add(layout_handle)

            try:
                lang_name_buf = ctypes.create_unicode_buffer(LOCALE_NAME_MAX_LENGTH)
                lang_code_buf = ctypes.create_unicode_buffer(LOCALE_NAME_MAX_LENGTH)

                kernel32.GetLocaleInfoW(lang_id, LOCALE_SLANGUAGE, lang_name_buf, LOCALE_NAME_MAX_LENGTH)
                # get the ISO-639-2 three-letter code (e.g. "ENG")
                if not kernel32.GetLocaleInfoW(lang_id, LOCALE_SISO639LANGNAME2, lang_code_buf, LOCALE_NAME_MAX_LENGTH):
                    kernel32.GetLocaleInfoW(lang_id, LOCALE_SISO639LANGNAME, lang_code_buf, LOCALE_NAME_MAX_LENGTH)

                lang_name = lang_name_buf.value
                lang_code = (
                    self._menu_config["layout_icon"] if self._menu_config["show_layout_icon"] else lang_code_buf.value
                )
                k_layouts = None

                try:
                    # Temporarily activate this layout
                    user32.ActivateKeyboardLayout(ctypes.c_void_p(layout_handle), 0)

                    # Get the KLID string for the now-active layout
                    klid_buf = ctypes.create_unicode_buffer(9)
                    if user32.GetKeyboardLayoutNameW(klid_buf):
                        klid = klid_buf.value.upper()

                        # Look up in registry
                        reg_path = rf"SYSTEM\CurrentControlSet\Control\Keyboard Layouts\{klid}"
                        try:
                            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path) as key:
                                # Try Layout Text first
                                try:
                                    k_layouts, _ = winreg.QueryValueEx(key, "Layout Text")
                                except FileNotFoundError:
                                    # Try Layout Display Name
                                    try:
                                        k_layouts, _ = winreg.QueryValueEx(key, "Layout Display Name")
                                    except FileNotFoundError:
                                        pass
                        except WindowsError:
                            pass
                except:
                    pass

                if lang_name and lang_code:
                    languages.append(
                        {
                            "id": lang_id,
                            "handle": layout_handle,
                            "name": lang_name,
                            "code": lang_code,
                            "layouts": k_layouts or lang_name,  # fallback to lang_name
                        }
                    )
            except:
                continue

        # Restore original layout
        try:
            user32.ActivateKeyboardLayout(ctypes.c_void_p(current_layout), 0)
        except:
            pass

        # Sort by language name
        languages.sort(key=lambda x: x["name"])
        self._available_languages = languages
        return languages

    def _get_current_language_id(self):
        """Get the current language ID"""
        try:
            hwnd = user32.GetForegroundWindow()
            thread_id = user32.GetWindowThreadProcessId(hwnd, None)
            input_locale_id = user32.GetKeyboardLayout(thread_id)
            return input_locale_id & 0xFFFF
        except:
            return 0

    def _get_current_layout_handle(self):
        """Get the current keyboard layout handle"""
        try:
            hwnd = user32.GetForegroundWindow()
            thread_id = user32.GetWindowThreadProcessId(hwnd, None)
            return user32.GetKeyboardLayout(thread_id)
        except:
            return 0

    def _activate_layout(self, focus_window: int | None, target_layout: int):
        """Activate the specified keyboard layout returning focus to the specified window"""
        if focus_window:
            user32.SetFocus(focus_window)
            user32.SetActiveWindow(focus_window)
            user32.SetForegroundWindow(focus_window)
            result = user32.ActivateKeyboardLayout(ctypes.c_void_p(target_layout), 0)
            # Post the message to the focus window to activate the layout
            user32.PostMessageW(focus_window, WM_INPUTLANGCHANGEREQUEST, 0, target_layout)
        else:
            # No focus window, just activate the layout
            result = user32.ActivateKeyboardLayout(ctypes.c_void_p(target_layout), 0)
        return result

    def _switch_to_language(self, target_lang_id):
        """Switch to the specified language"""
        try:
            # Get all available layouts
            available_languages = self._get_available_languages()
            target_layout = None

            for lang_info in available_languages:
                if lang_info["id"] == target_lang_id:
                    target_layout = lang_info["handle"]
                    break

            if target_layout is None:
                return False

            result = self._activate_layout(self._focused_window_hwnd, target_layout)

            if result == 0:
                # If activation failed, try loading the layout by string
                layout_str = f"{target_layout & 0xFFFFFFFF:08X}"

                loaded_layout = user32.LoadKeyboardLayoutW(
                    ctypes.c_wchar_p(layout_str),
                    0x00000001,  # KLF_ACTIVATE
                )
                if loaded_layout:
                    self._activate_layout(self._focused_window_hwnd, loaded_layout)

            # Clear the language cache to force refresh
            self._available_languages = None

            # Update the widget label immediately
            self._update_label()

            return True
        except Exception as e:
            logging.error(f"Error switching language: {e}")
            return False

    # Get the current keyboard layout
    def _get_current_keyboard_language(self):
        # Get the foreground window (the active window)
        hwnd = user32.GetForegroundWindow()
        # Get the thread id of the foreground window
        thread_id = user32.GetWindowThreadProcessId(hwnd, None)
        # Get the active input locale identifier for the thread
        input_locale_id = user32.GetKeyboardLayout(thread_id)
        # Extract the low word (language identifier) and high word (keyboard layout identifier) from the active input locale identifier
        lang_id = input_locale_id & 0xFFFF
        layout_id = (input_locale_id >> 16) & 0xFFFF

        # Buffers for the language and country names
        lang_name = ctypes.create_unicode_buffer(LOCALE_NAME_MAX_LENGTH)
        country_name = ctypes.create_unicode_buffer(LOCALE_NAME_MAX_LENGTH)
        full_lang_name = ctypes.create_unicode_buffer(LOCALE_NAME_MAX_LENGTH)
        full_country_name = ctypes.create_unicode_buffer(LOCALE_NAME_MAX_LENGTH)
        native_country_name = ctypes.create_unicode_buffer(LOCALE_NAME_MAX_LENGTH)
        native_lang_name = ctypes.create_unicode_buffer(LOCALE_NAME_MAX_LENGTH)
        layout_locale_name = ctypes.create_unicode_buffer(LOCALE_NAME_MAX_LENGTH)
        full_layout_locale_name = ctypes.create_unicode_buffer(LOCALE_NAME_MAX_LENGTH)
        layout_country_name = ctypes.create_unicode_buffer(LOCALE_NAME_MAX_LENGTH)
        ico_code_name = ctypes.create_unicode_buffer(LOCALE_NAME_MAX_LENGTH)

        # Get the ISO language name
        kernel32.GetLocaleInfoW(lang_id, LOCALE_SISO639LANGNAME, lang_name, LOCALE_NAME_MAX_LENGTH)
        # Get the ISO country name
        kernel32.GetLocaleInfoW(lang_id, LOCALE_SISO3166CTRYNAME, country_name, LOCALE_NAME_MAX_LENGTH)
        # Get the full language name
        kernel32.GetLocaleInfoW(lang_id, LOCALE_SLANGUAGE, full_lang_name, LOCALE_NAME_MAX_LENGTH)
        # Get the full country name
        kernel32.GetLocaleInfoW(lang_id, LOCALE_SCOUNTRY, full_country_name, LOCALE_NAME_MAX_LENGTH)
        # Get the native country name
        kernel32.GetLocaleInfoW(lang_id, LOCALE_SNATIVECTRYNAME, native_country_name, LOCALE_NAME_MAX_LENGTH)
        # Get the native language name
        kernel32.GetLocaleInfoW(lang_id, LOCALE_SNATIVELANGNAME, native_lang_name, LOCALE_NAME_MAX_LENGTH)
        # Get the full name of the keyboard layout
        kernel32.GetLocaleInfoW(layout_id, LOCALE_SNAME, layout_locale_name, LOCALE_NAME_MAX_LENGTH)
        # Get the full language name of the keyboard layout
        kernel32.GetLocaleInfoW(layout_id, LOCALE_SLANGUAGE, full_layout_locale_name, LOCALE_NAME_MAX_LENGTH)
        # Get the full country name of the keyboard layout
        kernel32.GetLocaleInfoW(layout_id, LOCALE_SCOUNTRY, layout_country_name, LOCALE_NAME_MAX_LENGTH)
        # Get the ISO 639-2 three-letter language code (e.g. "ENG")
        kernel32.GetLocaleInfoW(lang_id, LOCALE_SISO639LANGNAME2, ico_code_name, LOCALE_NAME_MAX_LENGTH)

        language_code = lang_name.value
        iso_language_code = ico_code_name.value if ico_code_name.value else language_code
        country_code = country_name.value
        full_name = f"{full_lang_name.value}"
        return {
            "language_code": language_code,
            "iso_language_code": iso_language_code,
            "country_code": country_code,
            "full_name": full_name,
            "native_country_name": native_country_name.value,
            "native_lang_name": native_lang_name.value,
            "layout_name": layout_locale_name.value,
            "full_layout_name": full_layout_locale_name.value,
            "layout_country_name": layout_country_name.value,
        }
