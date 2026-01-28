"""
Terminal Menu Widget
Provides a dropdown menu to launch configured terminal applications with admin support.
"""

import logging
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget
from core.utils.utilities import PopupWidget, add_shadow
from core.utils.widgets.animation_manager import AnimationManager
from core.validation.widgets.yasb.terminal_menu import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget

# Windows-specific imports for admin launch
try:
    import ctypes
    WINDOWS_AVAILABLE = True
except ImportError:
    WINDOWS_AVAILABLE = False
    logging.warning("Windows-specific modules not available. Admin launch will not work.")


class ClickableTerminalRow(QWidget):
    """Clickable row widget for terminal menu items."""
    
    def __init__(self, terminal_info, shield_icon, parent_widget, parent=None):
        super().__init__(parent)
        self.terminal_info = terminal_info
        self.shield_icon = shield_icon
        self.parent_widget = parent_widget
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Create inner widget with menu-item class (like disk widget structure)
        inner_widget = QWidget(self)
        inner_widget.setProperty("class", "menu-item")
        inner_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        
        # Create layout for inner widget  
        h_layout = QHBoxLayout(inner_widget)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(8)

        # Terminal name
        name_label = QLabel(terminal_info.get("name", "Terminal"))
        name_label.setProperty("class", "terminal-name")
        name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        name_label.setIndent(8)  # Add left indent to the label text
        h_layout.addWidget(name_label, 1)

        # Admin shield icon (button)
        self.shield_label = QLabel(shield_icon)
        self.shield_label.setProperty("class", "admin-button")
        self.shield_label.setToolTip("Launch as Administrator")
        self.shield_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        h_layout.addWidget(self.shield_label, 0)
        
        # Main layout for outer widget
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(inner_widget, 1)  # Stretch factor 1
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if click is on admin shield area (right side)
            shield_rect = self.shield_label.geometry()
            if shield_rect.contains(event.pos()):
                self.parent_widget._launch_terminal_admin(self.terminal_info)
            else:
                self.parent_widget._launch_terminal(self.terminal_info)
        super().mousePressEvent(event)


class TerminalMenuWidget(BaseWidget):
    """
    Terminal Menu Widget - Dropdown launcher for terminal applications.
    
    Features:
    - Configurable list of terminal applications
    - Normal and administrator launch support
    - Customizable icons and labels
    - Dropdown menu on click
    """
    
    validation_schema = VALIDATION_SCHEMA

    def __init__(
        self,
        label: str,
        terminal_list: list[dict],
        container_padding: dict[str, int],
        blur: bool,
        round_corners: bool,
        round_corners_type: str,
        border_color: str,
        alignment: str,
        direction: str,
        offset_top: int,
        offset_left: int,
        shield_icon: str,
        animation: dict,
        callbacks: dict[str, str],
        label_shadow: dict = None,
        container_shadow: dict = None,
    ):
        super().__init__(0, class_name="terminal-menu-widget")
        
        self._label_content = label
        self._terminal_list = terminal_list
        self._padding = container_padding
        self._blur = blur
        self._round_corners = round_corners
        self._round_corners_type = round_corners_type
        self._border_color = border_color
        self._alignment = alignment
        self._direction = direction
        self._offset_top = offset_top
        self._offset_left = offset_left
        self._shield_icon = shield_icon
        self._animation = animation
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow

        # Construct container
        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(
            self._padding["left"], 
            self._padding["top"], 
            self._padding["right"], 
            self._padding["bottom"]
        )
        
        # Initialize container
        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self._container_shadow)
        
        # Add the container to the main widget layout
        self.widget_layout.addWidget(self._widget_container)
        
        # Create label (icon)
        self._label = QLabel(self._label_content)
        self._label.setProperty("class", "icon")
        self._label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        add_shadow(self._label, self._label_shadow)
        self._widget_container_layout.addWidget(self._label)

        # Register callbacks
        self.register_callback("toggle_menu", self._toggle_menu)
        
        self.callback_left = callbacks.get("on_left", "toggle_menu")
        
        self.menu_dialog = None

    def _toggle_menu(self):
        """Toggle the terminal menu dropdown."""
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
            
        if hasattr(self, "menu_dialog") and self.menu_dialog:
            self.menu_dialog.hide()
        
        self._show_menu()

    def _show_menu(self):
        """Display the terminal menu dropdown."""
        self.menu_dialog = PopupWidget(
            self,
            self._blur,
            self._round_corners,
            self._round_corners_type,
            self._border_color,
        )
        self.menu_dialog.setProperty("class", "terminal-menu")

        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        for terminal in self._terminal_list:
            row = ClickableTerminalRow(terminal, self._shield_icon, self)
            layout.addWidget(row)

        self.menu_dialog.setLayout(layout)
        self.menu_dialog.adjustSize()
        
        # Position the dialog
        self.menu_dialog.setPosition(
            alignment=self._alignment,
            direction=self._direction,
            offset_left=self._offset_left,
            offset_top=self._offset_top,
        )
        
        self.menu_dialog.show()

    def _launch_terminal(self, terminal):
        """Launch terminal normally using ShellExecuteW for consistency."""
        if not WINDOWS_AVAILABLE:
            logging.error("Windows-specific modules not available. Cannot launch terminal.")
            return

        path = terminal.get("path", "")
        if not path:
            logging.error(f"Terminal path not specified for {terminal.get('name', 'Unknown')}")
            return

        try:
            # Use ShellExecuteW with "open" verb for normal launch
            # This provides consistent behavior with admin launch and better path handling
            shell32 = ctypes.windll.shell32
            
            # ShellExecuteW parameters
            hwnd = None
            operation = "open"  # Normal launch (not elevated)
            file = path
            parameters = None
            directory = None
            show_cmd = 1  # SW_SHOWNORMAL

            result = shell32.ShellExecuteW(
                hwnd,
                operation,
                file,
                parameters,
                directory,
                show_cmd
            )

            # ShellExecuteW returns a value > 32 on success
            if result > 32:
                logging.info(f"Launched terminal: {terminal.get('name', path)}")
                if self.menu_dialog:
                    self.menu_dialog.hide()
                    self.menu_dialog = None
            else:
                logging.error(f"Failed to launch terminal. Error code: {result}")
                
        except Exception as e:
            logging.error(f"Failed to launch terminal {terminal.get('name', path)}: {e}")

    def _launch_terminal_admin(self, terminal):
        """Launch terminal as administrator using Windows ShellExecute."""
        if not WINDOWS_AVAILABLE:
            logging.error("Windows-specific modules not available. Cannot launch as admin.")
            return

        path = terminal.get("path", "")
        if not path:
            logging.error(f"Terminal path not specified for {terminal.get('name', 'Unknown')}")
            return

        try:
            # Use ShellExecuteW with "runas" verb for admin elevation
            shell32 = ctypes.windll.shell32
            
            # ShellExecuteW parameters
            hwnd = None
            operation = "runas"
            file = path
            parameters = None
            directory = None
            show_cmd = 1  # SW_SHOWNORMAL

            result = shell32.ShellExecuteW(
                hwnd,
                operation,
                file,
                parameters,
                directory,
                show_cmd
            )

            # ShellExecuteW returns a value > 32 on success
            if result > 32:
                logging.info(f"Launched terminal as admin: {terminal.get('name', path)}")
                if self.menu_dialog:
                    self.menu_dialog.hide()
                    self.menu_dialog = None
            else:
                logging.error(f"Failed to launch terminal as admin. Error code: {result}")
                
        except Exception as e:
            logging.error(f"Failed to launch terminal as admin {terminal.get('name', path)}: {e}")
