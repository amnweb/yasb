import logging
import os
import re
import subprocess
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.home import VALIDATION_SCHEMA
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QWidget, QMenu, QWidgetAction
from PyQt6.QtCore import Qt, QPoint, QTimer
from core.utils.win32.blurWindow import Blur
from core.utils.utilities import is_windows_10
import os
from core.utils.widgets.power import PowerOperations

class HomeWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA
    def __init__(
            self,label: str,
            container_padding: dict,
            power_menu: bool,
            system_menu: bool,
            blur: bool,
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
        
        self._create_menu()
        self.is_menu_visible = False
        
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
                self._widget_container_layout.addWidget(label)
                widgets.append(label)
                label.show()
                label.setCursor(Qt.CursorShape.PointingHandCursor)
            return widgets
        self._widgets = process_content(content)
       
    def add_menu_action(self, menu, text, triggered_func):
        label = QLabel(text)
        label.setProperty('class', 'menu-item')
        label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        label.setCursor(Qt.CursorShape.PointingHandCursor)
       
        widget_action = QWidgetAction(menu)
        widget_action.setDefaultWidget(label)
        widget_action.triggered.connect(triggered_func)
        menu.addAction(widget_action)
       
        return widget_action
               
    def create_menu_action(self, path):
        expanded_path = os.path.expanduser(path)
        return lambda: os.startfile(expanded_path)
           
    def _create_menu(self):
        self._menu = QMenu(self)
        self._update_menu_style()
        self._setup_menu()
        self._menu.aboutToHide.connect(self._on_menu_about_to_hide)
        self._menu.triggered.connect(self.on_menu_triggered)
        
    def _update_menu_style(self):
        self._menu.setProperty('class', 'home-menu')
        
        self._menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        if self._blur:
            Blur(
                self._menu.winId(),
                Acrylic=True if is_windows_10() else False,
                DarkMode=False,
                RoundCorners=True,
                BorderColor="System"
            )
        
    def _setup_menu(self):
        if self._system_menu:
            self.add_menu_action(
                self._menu,
                "About this PC",
                lambda: subprocess.Popen("winver", shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            )
            self._menu.addSeparator()
            self.add_menu_action(
                self._menu,
                "System Settings",
                lambda: os.startfile("ms-settings:")
            )
            self.add_menu_action(
                self._menu,
                "Task Manager",
                lambda: subprocess.Popen("taskmgr", shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            )
            self._menu.addSeparator()
       
        if self._menu_list is not None:
            if isinstance(self._menu_list, list):
                for menu_item in self._menu_list:
                    if 'title' in menu_item and 'path' in menu_item:
                        action = self.create_menu_action(menu_item['path'])
                        self.add_menu_action(
                            self._menu,
                            menu_item['title'],
                            action
                        )
            else:
                logging.error(f"Expected menu_list to be a list but got {type(self._menu_list)}")
                return
            
        if self._menu_list is not None and len(self._menu_list) > 0 and self._power_menu:
            self._menu.addSeparator()
       
        if self._power_menu:
            self.add_menu_action(
                self._menu,
                "Sleep",
                lambda: self.power_operations.sleep()
            )
            self.add_menu_action(
                self._menu,
                "Restart",
                lambda: self.power_operations.restart()
            )
            self.add_menu_action(
                self._menu,
                "Shut Down",
                lambda: self.power_operations.shutdown()
            )
            self._menu.addSeparator()
            self.add_menu_action(
                self._menu,
                "Lock Screen",
                lambda: self.power_operations.lock()
            )
            self.add_menu_action(
                self._menu,
                "Logout",
                lambda: self.power_operations.signout()
            )
        
    def on_menu_triggered(self):
        self._reset_menu_visibility()
        
    def _on_menu_about_to_hide(self):
        QTimer.singleShot(100, self._reset_menu_visibility)      
          
    def _toggle_menu(self):
        if self.is_menu_visible:
            self._reset_menu_visibility()
            return
        global_position = self.mapToGlobal(QPoint(0, self.height() + 6))
        self._menu.move(global_position)
        self._update_menu_style()
        QTimer.singleShot(0, self._menu.show)
        self.is_menu_visible = True

    def _reset_menu_visibility(self):
        self.is_menu_visible = False
        self._menu.hide()