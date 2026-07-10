import datetime
import logging
import os
import re
import subprocess

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget

from core.utils.utilities import ElidedLabel, PopupWidget
from core.validation.widgets.yasb.vscode import VSCodeConfig
from core.widgets.base import BaseWidget
from core.widgets.services.vscode.get_vscode_state_db_path import get_state_db_path
from core.widgets.services.vscode.history import get_history_modified_time, load_recent_workspaces


class VSCodeWidget(BaseWidget):
    validation_schema = VSCodeConfig

    def __init__(self, config: VSCodeConfig):
        super().__init__(class_name="vscode-widget")
        self.config = config
        self._show_alt_label = False

        self._state_file_path = self.config.state_storage_path or get_state_db_path()
        self._menu = None
        self._last_db_modified_time = 0
        self._active_filter = "all"
        self._recent_workspaces = []
        self._item_widgets = []
        self._no_recents_widget = None

        self._init_container()
        self.build_widget_label(self.config.label, self.config.label_alt)

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("toggle_menu", self._toggle_menu)

        self.callback_left = self.config.callbacks.on_left
        self.callback_right = self.config.callbacks.on_right
        self.callback_middle = self.config.callbacks.on_middle

    def _toggle_menu(self):
        self.show_menu()

    def _toggle_label(self):
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

    def _update_label(self):
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self.config.label_alt if self._show_alt_label else self.config.label
        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0

        for part in label_parts:
            part = part.strip()
            if part and widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                if "<span" in part and "</span>" in part:
                    icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                    active_widgets[widget_index].setText(icon)
                else:
                    active_widgets[widget_index].setText(part)
                widget_index += 1

    def _handle_mouse_press_event(self, event, workspace_data):
        path = workspace_data["path"]
        is_folder = workspace_data["type"] == "folder"
        is_remote = workspace_data.get("is_remote", False)

        args = [self.config.cli_command]
        if is_remote:
            uri_arg = "--folder-uri" if is_folder else "--file-uri"
            args.extend([uri_arg, path])
        else:
            args.append(path)

        try:
            subprocess.Popen(
                args,
                shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            logging.error("Failed to open VS Code with path %s: %s", path, e)
        self._menu.hide()

    def _create_container_mouse_press_event(self, workspace_data):
        def mouse_press_event(event):
            self._handle_mouse_press_event(event, workspace_data)

        return mouse_press_event

    def show_menu(self):
        db_mtime = get_history_modified_time(self._state_file_path)

        if not self._menu:
            self._menu = self._create_popup_menu()
            self._init_menu_layout()

        if db_mtime > self._last_db_modified_time:
            self._refresh_menu_items()
            self._last_db_modified_time = db_mtime

        self._position_and_show_menu()

    def _create_popup_menu(self):
        menu = PopupWidget(
            self,
            self.config.menu.blur,
            self.config.menu.round_corners,
            self.config.menu.round_corners_type,
            self.config.menu.border_color,
            persistent=True,
        )
        menu.setProperty("class", "vscode-menu")
        return menu

    def _init_menu_layout(self):
        self._menu_layout = QVBoxLayout(self._menu)
        self._menu_layout.setSpacing(0)
        self._menu_layout.setContentsMargins(0, 0, 0, 0)

        header_widget = QFrame()
        header_widget.setProperty("class", "header")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)

        header_label = QLabel(self.config.menu_title)
        header_label.setProperty("class", "title")
        header_layout.addWidget(header_label)

        header_layout.addStretch()

        self._pill_buttons = {}
        for filter_name in ("all", "folders", "files", "remotes"):
            btn = QPushButton(filter_name.title())
            btn.setProperty("class", "filter-button active" if filter_name == self._active_filter else "filter-button")
            btn.clicked.connect(lambda checked, name=filter_name: self._set_filter(name))
            header_layout.addWidget(btn)
            self._pill_buttons[filter_name] = btn

        self._menu_layout.addWidget(header_widget)

        search_bar = QFrame()
        search_bar.setProperty("class", "search-bar")
        search_bar_layout = QHBoxLayout(search_bar)
        search_bar_layout.setContentsMargins(0, 0, 0, 0)
        search_bar_layout.setSpacing(0)

        self._search_input = QLineEdit()
        self._search_input.setProperty("class", "input")
        self._search_input.setPlaceholderText("Search...")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.textChanged.connect(self._on_search_changed)
        search_bar_layout.addWidget(self._search_input)

        self._menu_layout.addWidget(search_bar)

        self._scroll_area = self._create_scroll_area()
        self._menu_layout.addWidget(self._scroll_area)

        self._scroll_widget = QFrame()
        self._scroll_widget.setProperty("class", "contents")
        self._scroll_layout = QVBoxLayout(self._scroll_widget)
        self._scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._scroll_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_layout.setSpacing(0)

        self._items_layout = QVBoxLayout()
        self._items_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._items_layout.setContentsMargins(0, 0, 0, 0)
        self._items_layout.setSpacing(0)
        self._scroll_layout.addLayout(self._items_layout)

        self._no_recents_widget = self._create_no_recents_label()
        self._no_recents_widget.setVisible(False)
        self._scroll_layout.addWidget(self._no_recents_widget)

        self._scroll_area.setWidget(self._scroll_widget)

    def _set_filter(self, filter_name):
        self._active_filter = filter_name

        for name, btn in self._pill_buttons.items():
            btn.setProperty("class", "filter-button active" if name == filter_name else "filter-button")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        self._refresh_menu_items(reload_db=False)

    def _on_search_changed(self, text):
        self._search_query = text.strip().lower()
        self._refresh_menu_items(reload_db=False)

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
        container = QFrame()
        container.setProperty("class", "item")
        container.setContentsMargins(0, 0, 8, 0)

        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        is_folder = workspace_data["type"] == "folder"
        is_remote = workspace_data.get("is_remote", False)

        icon_char = ""
        icon_class = ""

        if is_remote and self.config.icons.remote:
            icon_char = self.config.icons.remote
            icon_class = "remote-icon"
        elif is_folder:
            icon_char = self.config.icons.folder
            icon_class = "folder-icon"
        else:
            icon_char = self.config.icons.file
            icon_class = "file-icon"

        if icon_char:
            icon_label = QLabel(icon_char)
            icon_label.setProperty("class", icon_class)
            container_layout.addWidget(icon_label)

        path = workspace_data["path"]
        display_path = workspace_data["display_path"]
        if self.config.truncate_to_root_dir:
            if is_remote:
                import urllib.parse

                parsed = urllib.parse.urlparse(path)
                remote_path = urllib.parse.unquote(parsed.path).replace("\\", "/").rstrip("/")
                display_path = remote_path.split("/")[-1] if remote_path else "/"
            else:
                local_path = path.replace("\\", "/").rstrip("/")
                if not local_path or local_path.endswith(":"):
                    display_path = path
                else:
                    display_path = local_path.split("/")[-1]

        title_label = ElidedLabel(display_path)
        title_label.setProperty("class", "title")

        if is_remote:
            authority = workspace_data.get("remote_authority", "")
            if authority:
                auth_lower = authority.lower()
                if auth_lower.startswith("wsl+"):
                    distro = authority[4:]
                    date_str = f"WSL ({distro})" if distro else "WSL Connection"
                elif auth_lower.startswith("ssh-remote+"):
                    host = authority[11:]
                    date_str = f"SSH ({host})" if host else "SSH Connection"
                elif auth_lower.startswith("dev-container+"):
                    date_str = "Dev Container"
                else:
                    date_str = f"Remote: {authority}"
            else:
                date_str = "Remote Connection"
        else:
            try:
                mod_time = os.path.getmtime(path)
                mod_date = datetime.datetime.fromtimestamp(mod_time)
                date_str = mod_date.strftime(self.config.modified_date_format)
            except OSError:
                date_str = "Unknown"

        date_label = ElidedLabel(date_str)
        date_label.setProperty("class", "modified-date")

        text_content = QWidget()
        text_content_layout = QVBoxLayout(text_content)
        text_content_layout.addWidget(title_label)
        text_content_layout.addWidget(date_label)
        text_content_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        text_content_layout.setContentsMargins(0, 0, 0, 0)
        text_content_layout.setSpacing(0)

        container_layout.addWidget(text_content, 1)
        container.mousePressEvent = self._create_container_mouse_press_event(workspace_data)

        return container

    def _refresh_menu_items(self, reload_db=True):
        if reload_db:
            for widget in self._item_widgets:
                widget.deleteLater()
            self._item_widgets.clear()

            recent_workspaces = load_recent_workspaces(self._state_file_path)
            if recent_workspaces:
                folders = [ws for ws in recent_workspaces if ws["type"] == "folder"][
                    : self.config.max_number_of_folders
                ]
                files = [ws for ws in recent_workspaces if ws["type"] == "file"][: self.config.max_number_of_files]
                self._recent_workspaces = folders + files
            else:
                self._recent_workspaces = []

            for workspace in self._recent_workspaces:
                item_widget = self._create_workspace_item(workspace)
                item_widget.setProperty("workspace_type", workspace["type"])
                item_widget.setProperty("is_remote", workspace.get("is_remote", False))
                item_widget.setProperty("display_path", workspace.get("display_path", ""))
                item_widget.setProperty("path", workspace.get("path", ""))
                self._items_layout.addWidget(item_widget)
                self._item_widgets.append(item_widget)

        search_query = getattr(self, "_search_query", "").lower()

        has_visible_items = False
        for item_widget in self._item_widgets:
            w_type = item_widget.property("workspace_type")
            w_remote = item_widget.property("is_remote")
            display_path = item_widget.property("display_path") or ""
            path = item_widget.property("path") or ""

            visible = True
            if self._active_filter == "folders" and w_type != "folder":
                visible = False
            elif self._active_filter == "files" and w_type != "file":
                visible = False
            elif self._active_filter == "remotes" and not w_remote:
                visible = False

            if visible and search_query:
                haystack = (display_path + path).lower()
                if search_query not in haystack:
                    visible = False

            item_widget.setVisible(visible)
            if visible:
                has_visible_items = True

        show_empty = (not self._recent_workspaces) or (not has_visible_items)
        self._no_recents_widget.setVisible(show_empty)

        self._menu.adjustSize()

    def _position_and_show_menu(self):
        self._menu.adjustSize()
        self._menu.setPosition(
            alignment=self.config.menu.alignment,
            direction=self.config.menu.direction,
            offset_left=self.config.menu.offset_left,
            offset_top=self.config.menu.offset_top,
        )
        self._menu.show()
