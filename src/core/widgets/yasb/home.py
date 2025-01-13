import os
import re
import subprocess
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.home import VALIDATION_SCHEMA
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QWidget, QVBoxLayout, QFrame
from PyQt6.QtCore import Qt, QPoint
import os
from core.utils.widgets.power import PowerOperations
from core.utils.utilities import PopupWidget
from core.utils.widgets.animation_manager import AnimationManager

class HomeWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA
    def __init__(
            self,label: str,
            container_padding: dict,
            power_menu: bool,
            system_menu: bool,
            blur: bool,
            round_corners: bool,
            round_corners_type: str,
            border_color: str,
            alignment: str,
            direction: str,
            distance: int,
            menu_labels: dict[str, str],
            animation: dict[str, str],
            callbacks: dict[str, str],
            menu_list: list[str, dict[str]] = None
        ):
        super().__init__(class_name="home-widget")
        self.power_operations = PowerOperations()
        self._label = label
        self._menu_list = menu_list
        self._padding = container_padding
        self._power_menu = power_menu
        self._system_menu = system_menu
        self._blur = blur
        self._round_corners = round_corners
        self._round_corners_type = round_corners_type
        self._border_color = border_color
        self._alignment = alignment
        self._direction = direction
        self._distance = distance
        self._menu_labels = menu_labels
        self._animation = animation
        # Construct container
        self._widget_container_layout: QHBoxLayout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(
                self._padding['left'],
                self._padding['top'],
                self._padding['right'],
                self._padding['bottom']
            )
        # Initialize container
        self._widget_container: QWidget = QWidget()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        # Add the container to the main widget layout
        self.widget_layout.addWidget(self._widget_container)
        self._create_dynamically_label(self._label)        

        self.register_callback("toggle_menu", self._toggle_menu)         
        self.callback_left = callbacks["on_left"]

        
    def _create_dynamically_label(self, content: str):
        def process_content(content):
            label_parts = re.split('(<span.*?>.*?</span>)', content)
            label_parts = [part for part in label_parts if part]
            widgets = []
            for part in label_parts:
                part = part.strip()  # Remove any leading/trailing whitespace
                if not part:
                    continue
                if '<span' in part and '</span>' in part:
                    class_name = re.search(r'class=(["\'])([^"\']+?)\1', part)
                    class_result = class_name.group(2) if class_name else 'icon'
                    icon = re.sub(r'<span.*?>|</span>', '', part).strip()
                    label = QLabel(icon)
                    label.setProperty("class", class_result)
                else:
                    label = QLabel(part)
                    label.setProperty("class", "label")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label.setCursor(Qt.CursorShape.PointingHandCursor)
                self._widget_container_layout.addWidget(label)
                widgets.append(label)
                label.show()
                
            return widgets
        self._widgets = process_content(content)
 
               
    def create_menu_action(self, path):
        expanded_path = os.path.expanduser(path)
        return lambda: os.startfile(expanded_path)
           
    def _create_menu(self):
        self._menu = PopupWidget(self, self._blur, self._round_corners, self._round_corners_type, self._border_color)
        self._menu.setProperty('class', 'home-menu')
        self._menu.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self._menu.setWindowFlag(Qt.WindowType.Popup)
        self._menu.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)

        # Create main vertical layout for the popup
        main_layout = QVBoxLayout(self._menu)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        if self._system_menu:
            # System menu items
            self._add_menu_item(main_layout, self._menu_labels['about'], 
                lambda: subprocess.Popen("winver", shell=True, creationflags=subprocess.CREATE_NO_WINDOW))
            
            self._add_separator(main_layout)
            
            self._add_menu_item(main_layout, self._menu_labels['system'],
                lambda: os.startfile("ms-settings:"))
            self._add_menu_item(main_layout, self._menu_labels['task_manager'],
                lambda: subprocess.Popen("taskmgr", shell=True, creationflags=subprocess.CREATE_NO_WINDOW))
                
            self._add_separator(main_layout)

        # Custom menu items
        if isinstance(self._menu_list, list):
            for menu_item in self._menu_list:
                if 'title' in menu_item and 'path' in menu_item:
                    self._add_menu_item(main_layout, menu_item['title'],
                        self.create_menu_action(menu_item['path']))
        if self._menu_list is not None and len(self._menu_list) > 0 and self._power_menu:
            self._add_separator(main_layout)
       
        if self._power_menu:
            self._add_menu_item(
                main_layout,
                self._menu_labels['sleep'],
                lambda: self.power_operations.sleep()
            )
            self._add_menu_item(
                main_layout,
                self._menu_labels['restart'],
                lambda: self.power_operations.restart()
            )
            self._add_menu_item(
                main_layout,
                self._menu_labels['shutdown'],
                lambda: self.power_operations.shutdown()
            )
            
            self._add_separator(main_layout)
            
            self._add_menu_item(
                main_layout,
                self._menu_labels['lock'],
                lambda: self.power_operations.lock()
            )
            self._add_menu_item(
                main_layout,
                self._menu_labels['logout'],
                lambda: self.power_operations.signout()
            )
            
        self._menu.adjustSize()
        widget_global_pos = self.mapToGlobal(QPoint(0, self.height() + self._distance))
        
        if self._direction == 'up':
            global_y = self.mapToGlobal(QPoint(0, 0)).y() - self._menu.height() - self._distance
            widget_global_pos = QPoint(self.mapToGlobal(QPoint(0, 0)).x(), global_y)
            
        if self._alignment == 'left':
            global_position = widget_global_pos
        elif self._alignment == 'right':
            global_position = QPoint(
                widget_global_pos.x() + self.width() - self._menu.width(),
                widget_global_pos.y()
            )
        elif self._alignment == 'center':
            global_position = QPoint(
                widget_global_pos.x() + (self.width() - self._menu.width()) // 2,
                widget_global_pos.y()
            )
        else:
            global_position = widget_global_pos

        self._menu.move(global_position)
        self._menu.show()


    def _add_menu_item(self, layout, text, triggered_func):
        # Create widget container
        item = QWidget()
        item_layout = QHBoxLayout(item)
        item_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create label
        label = QLabel(text)
        label.setProperty('class', 'menu-item')
        label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        label.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Add label to layout
        item_layout.addWidget(label)
        
        # Add click event
        def mouse_press_handler(event):
            if event.button() == Qt.MouseButton.LeftButton:
                triggered_func()
                self._menu.hide()
        
        item.mousePressEvent = mouse_press_handler
        layout.addWidget(item)
        
        return item

    def _add_separator(self, layout):
        separator = QFrame(self)
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setProperty('class', 'separator')
        separator.setStyleSheet('border:none')
        layout.addWidget(separator)

    def _toggle_menu(self):
        if self._animation['enabled']:
            AnimationManager.animate(self, self._animation['type'], self._animation['duration'])
        self._create_menu()