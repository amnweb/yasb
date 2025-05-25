import json
import logging
import sqlite3
import subprocess
from typing import Any, List
import re
import os

import urllib.parse

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget
from PyQt6.QtGui import QCursor

from core.utils.widgets.animation_manager import AnimationManager
from core.utils.utilities import add_shadow, build_widget_label, PopupWidget
from core.validation.widgets.yasb.vscode import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget

class VSCodeWidget(BaseWidget):
    validation_schema: dict[str, Any] = VALIDATION_SCHEMA

    def __init__(
        self,
        label: str,
        label_alt: str,
        file_icon: str,
        folder_icon: str,
        hide_folder_icon: bool,
        hide_file_icon: bool,
        truncate_to_root_dir: bool,
        max_number_of_folders: int,
        max_number_of_files: int,
        max_field_size: int,
        menu: dict[str, str],
        container_padding: dict[str, int],
        animation: dict[str, str],
        callbacks: dict[str, str],
        label_shadow: dict = None,
        container_shadow: dict = None,
    ):
        super().__init__(class_name="vscode-widget")
        self._label_content = label
        self._label_alt_content = label_alt
        self._file_icon = file_icon
        self._folder_icon = folder_icon
        self._hide_folder_icon = hide_folder_icon
        self._hide_file_icon = hide_file_icon
        self._truncate_to_root_dir = truncate_to_root_dir
        self._max_number_of_folders = max_number_of_folders
        self._max_number_of_files = max_number_of_files
        self._max_field_size = max_field_size
        self._menu_popup = menu
        self._show_alt_label = False
        self._padding = container_padding
        self._animation = animation
        self._container_shadow = container_shadow
        self._label_shadow = label_shadow

        self._widget_container_layout: QHBoxLayout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(self._padding['left'],self._padding['top'],self._padding['right'],self._padding['bottom'])
       
        self._widget_container: QWidget = QWidget()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self._container_shadow)

        self.widget_layout.addWidget(self._widget_container)

        build_widget_label(self, self._label_content, self._label_alt_content, self._label_shadow)

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("toggle_menu", self._toggle_menu)

        self.callback_left = callbacks['on_left']
        self.callback_right = callbacks['on_right']
        self.callback_middle = callbacks['on_middle']

    def _uri_to_windows_path(self, uri):
        parsed = urllib.parse.urlparse(uri)
        path = urllib.parse.unquote(parsed.path)
        if path.startswith('/'):
            path = path[1:]
        if ':' in path:
            drive_part, rest = path.split(':', 1)
            drive_part = drive_part.capitalize()
            path = f"{drive_part}:{rest}"
        return path
    
    def _load_recent_workspaces(self) -> List[dict]:
        try:
            file_path = os.path.expandvars(r"%APPDATA%\Code\User\globalStorage\state.vscdb")
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM ItemTable WHERE key = 'history.recentlyOpenedPathsList'")
            result = cursor.fetchone()
            result_list = []
            if result:
                paths_data = json.loads(result[0]).get('entries', [])
                for path in paths_data:
                    if isinstance(path, dict):
                        if path.get('folderUri'):
                            folder_path = self._uri_to_windows_path(path.get('folderUri'))
                            if os.path.exists(folder_path):
                                result_list.append({"folder":  folder_path})
                        if path.get('fileUri'):
                            file_path = self._uri_to_windows_path(path.get('fileUri'))
                            if os.path.exists(file_path):
                                result_list.append({"file": file_path})
                    else:
                        logging.error(f"Unexpected entry type: {type(path)}")
            else:
                logging.error(f"No data found in {file_path}")
            conn.close()
            return result_list
        except Exception as e:
            logging.error(f"Error: {e}")
            return []

    def _toggle_menu(self):
        if self._animation['enabled']:
            AnimationManager.animate(self, self._animation['type'], self._animation['duration'])
        self.show_menu()

    def _toggle_label(self):
        if self._animation['enabled']:
            AnimationManager.animate(self, self._animation['type'], self._animation['duration'])
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

    def _update_label(self):
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content
        label_parts = re.split('(<span.*?>.*?</span>)', active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0

        for part in label_parts:
            part = part.strip()
            if part and widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                if '<span' in part and '</span>' in part:
                    icon = re.sub(r'<span.*?>|</span>', '', part).strip()
                    active_widgets[widget_index].setText(icon)
                else:
                    active_widgets[widget_index].setText(part)
                widget_index += 1

    def _handle_mouse_press_event(self, event, folder):
        try:
            subprocess.Popen(['code', folder], shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to open VS Code with folder {folder}: {e}")
        except FileNotFoundError:
            logging.error("VS Code not found in PATH")
        self._menu.hide()

    def _create_container_mouse_press_event(self, folder):
        def mouse_press_event(event):
            self._handle_mouse_press_event(event, folder)
        return mouse_press_event

    def show_menu(self):
        self._menu = self._create_popup_menu()
        self._populate_menu_content()
        self._position_and_show_menu()

    def _create_popup_menu(self):
        menu = PopupWidget(
            self, 
            self._menu_popup['blur'], 
            self._menu_popup['round_corners'], 
            self._menu_popup['round_corners_type'], 
            self._menu_popup['border_color']
        )
        menu.setProperty('class', 'vscode-menu')
        return menu

    def _create_menu_header(self, layout):
        header_label = QLabel(f"<span style='font-weight:bold'>VSCode</span> recents")
        header_label.setProperty("class", "header")
        layout.addWidget(header_label)

    def _create_scroll_area(self):
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setViewportMargins(0, 0, -4, 0)
        scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; border: none; border-radius:0; }
            QScrollBar:vertical { border: none; background:transparent; width: 4px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
            QScrollBar::handle:vertical { background: rgba(255, 255, 255, 0.2); min-height: 10px; border-radius: 2px; }
            QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 0.35); }
            QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        """)
        return scroll_area

    def _create_no_recents_label(self):
        no_recent_label = QLabel("No recent workspaces found.")
        no_recent_label.setProperty("class", "no-recent")
        no_recent_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        no_recent_label.setContentsMargins(0, 20, 0, 20)
        return no_recent_label

    def _create_workspace_item(self, workspace_data):
        container = QWidget()
        container.setProperty("class", "item")
        container.setContentsMargins(0, 0, 8, 0)
        container.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        container_layout = QHBoxLayout(container)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        
        is_folder = 'folder' in workspace_data
        
        if (is_folder and not self._hide_folder_icon) or (not is_folder and not self._hide_file_icon):
            icon_label = QLabel(self._folder_icon if is_folder else self._file_icon)
            icon_label.setProperty("class", "folder-icon" if is_folder else "file-icon")
            container_layout.addWidget(icon_label)
        
        path = workspace_data.get('folder' if is_folder else 'file')
        display_path = path.split("/")[-1] if self._truncate_to_root_dir else path
        if len(display_path) > self._max_field_size:
            display_path = "..." + display_path[-self._max_field_size + 3:]
        
        title_label = QLabel(display_path)
        title_label.setProperty("class", "title")
        
        text_content = QWidget()
        text_content_layout = QVBoxLayout(text_content)
        text_content_layout.addWidget(title_label)
        text_content_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        text_content_layout.setContentsMargins(0, 0, 0, 0)
        text_content_layout.setSpacing(0)
        
        container_layout.addWidget(text_content, 1)
        container.mousePressEvent = self._create_container_mouse_press_event(path)
        
        return container

    def _populate_menu_content(self):
        main_layout = QVBoxLayout(self._menu)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        self._create_menu_header(main_layout)
        
        scroll_area = self._create_scroll_area()
        main_layout.addWidget(scroll_area)
        
        scroll_widget = QWidget()
        scroll_widget.setProperty("class", "contents")
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(0)
        scroll_area.setWidget(scroll_widget)
        
        recent_workspaces = self._load_recent_workspaces()
        
        if not recent_workspaces:
            scroll_layout.addWidget(self._create_no_recents_label())
        else:
            folders = [ws for ws in recent_workspaces if 'folder' in ws][:self._max_number_of_folders]
            files = [ws for ws in recent_workspaces if 'file' in ws][:self._max_number_of_files]
            workspaces_to_show = folders + files
            
            for workspace in workspaces_to_show:
                item = self._create_workspace_item(workspace)
                scroll_layout.addWidget(item)

    def _position_and_show_menu(self):
        self._menu.adjustSize()
        self._menu.setPosition(
            alignment=self._menu_popup['alignment'],
            direction=self._menu_popup['direction'],
            offset_left=self._menu_popup['offset_left'],
            offset_top=self._menu_popup['offset_top']
        )
        self._menu.show()