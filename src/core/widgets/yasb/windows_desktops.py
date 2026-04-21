import logging

from PyQt6.QtCore import (
    Qt,
    QTimer,
)
from PyQt6.QtGui import QAction, QCursor
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QVBoxLayout,
)

from core.utils.system import is_windows_10
from core.utils.utilities import PopupWidget, refresh_widget_style
from core.utils.win32.utils import apply_qmenu_style
from core.validation.widgets.yasb.windows_desktops import WindowsDesktopsConfig
from core.widgets.base import BaseWidget
from core.widgets.services.windows_desktops.service import WindowsDesktopService


class WorkspaceButton(QPushButton):
    def __init__(
        self,
        workspace_index: int,
        label: str | None = None,
        active_label: str | None = None,
        parent: WorkspaceWidget | None = None,
    ):
        super().__init__(parent)

        self.workspace_index = workspace_index
        self.setProperty("class", "ws-btn")
        self.default_label = label if label else str(workspace_index)
        self.active_label = active_label if active_label else self.default_label
        self.setText(self.default_label)
        self.parent_widget = parent
        self.clicked.connect(self._on_clicked)

    def _on_clicked(self):
        if self.parent_widget:
            self.parent_widget._clicked_button = self
            self.parent_widget._run_callback(self.parent_widget.callback_left)

    def contextMenuEvent(self, event):
        if self.parent_widget:
            self.parent_widget._clicked_button = self
            self.parent_widget._run_callback(self.parent_widget.callback_right)

    def update_text(self, text: str):
        self.setText(text)

    def update_visible_buttons(self):
        if not self.parent_widget:
            return

        visible_buttons = self.parent_widget._workspace_buttons
        for index, button in enumerate(visible_buttons):
            current_class = button.property("class")
            new_class = " ".join([cls for cls in current_class.split() if not cls.startswith("button-")])
            new_class = f"{new_class} button-{index + 1}"
            button.setProperty("class", new_class)
            refresh_widget_style(button)

    def activate_workspace(self):
        try:
            WindowsDesktopService.switch_desktop(self.workspace_index)
            WindowsDesktopService().notify_desktop_changed(self.workspace_index)
        except Exception:
            logging.exception("Failed to focus desktop at index %s", self.workspace_index)

    def _show_context_menu(self):
        menu = QMenu(self.window())
        # Assign a class for global styling; apply rounded corners via helper
        menu.setProperty("class", "context-menu")
        # Apply Windows rounded corners to the QMenu when it is shown
        apply_qmenu_style(menu)

        act_rename = QAction("Rename", self)
        act_rename.triggered.connect(self.rename_desktop)
        menu.addAction(act_rename)

        if len(WindowsDesktopService.get_desktops()) > 1:
            act_delete = QAction("Delete", self)
            act_delete.triggered.connect(self.delete_desktop)
            menu.addAction(act_delete)

        menu.addSeparator()

        act_create = QAction("Create New Desktop", self)
        act_create.triggered.connect(self.create_new_desktop)
        menu.addAction(act_create)

        # Get the foreground window before the menu steals focus
        svc = WindowsDesktopService()
        app_view = svc.get_foreground_app_view()

        if app_view:
            active_hwnd = app_view.hwnd
            menu.addSeparator()

            act_move_here = QAction("Move Window Here", self)
            act_move_here.triggered.connect(
                lambda checked=False, n=self.workspace_index, h=active_hwnd: self.move_active_window_to(n, h)
            )
            menu.addAction(act_move_here)

            move_menu = QMenu("Move Window To", self.window())
            move_menu.setProperty("class", "context-menu")
            apply_qmenu_style(move_menu)
            try:
                desktops = svc.get_desktops()
                for desktop in desktops:
                    desk_name = desktop.name.strip() if desktop.name.strip() else f"Desktop {desktop.number}"
                    act = QAction(desk_name, self)
                    target_number = desktop.number
                    act.triggered.connect(
                        lambda checked=False, n=target_number, h=active_hwnd: self.move_active_window_to(n, h)
                    )
                    move_menu.addAction(act)
            except Exception:
                logging.exception("Failed to populate move window submenu")
            menu.addMenu(move_menu)

            try:
                is_win_pinned = app_view.is_pinned()
            except Exception:
                is_win_pinned = False
            act_pin = QAction("Unpin Window From All Desktops" if is_win_pinned else "Pin Window To All Desktops", self)
            act_pin.triggered.connect(lambda checked=False, h=active_hwnd: self.toggle_pin_window(h))
            menu.addAction(act_pin)

            try:
                is_app_pinned = app_view.is_app_pinned()
            except Exception:
                is_app_pinned = False
            act_pin_app = QAction("Unpin App From All Desktops" if is_app_pinned else "Pin App To All Desktops", self)
            act_pin_app.triggered.connect(lambda checked=False, h=active_hwnd: self.toggle_pin_app(h))
            menu.addAction(act_pin_app)

        if not is_windows_10():
            menu.addSeparator()
            act_set_wall = QAction("Set Wallpaper On This Desktop", self)
            act_set_wall.triggered.connect(self.set_wallpaper)
            menu.addAction(act_set_wall)

            act_set_wall_all = QAction("Set Wallpaper On All Desktops", self)
            act_set_wall_all.triggered.connect(self.set_wallpaper_all)
            menu.addAction(act_set_wall_all)

        menu.popup(QCursor.pos())
        menu.activateWindow()

    def set_wallpaper(self):
        image_path, _ = QFileDialog.getOpenFileName(
            self, "Select Wallpaper Image", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if image_path:
            try:
                WindowsDesktopService.set_wallpaper(self.workspace_index, image_path)
            except Exception as e:
                logging.exception("Failed to set wallpaper: %s", e)

    def set_wallpaper_all(self):
        image_path, _ = QFileDialog.getOpenFileName(
            self, "Select Wallpaper Image", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if image_path:
            try:
                WindowsDesktopService.set_wallpaper_all(image_path)
            except Exception as e:
                logging.exception("Failed to set wallpaper for all desktops: %s", e)

    def rename_desktop(self):
        current_name = WindowsDesktopService.get_desktop_name(self.workspace_index)
        if not current_name:
            current_name = str(self.workspace_index)

        workspace_index = self.workspace_index

        popup = PopupWidget(
            self.parent_widget,
            blur=True,
            round_corners=True,
            round_corners_type="normal",
            border_color="System",
            dark_mode=True,
        )
        popup.setProperty("class", "windows-desktops-popup rename")

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        popup.setLayout(layout)

        container_frame = QFrame()
        container_frame.setProperty("class", "windows-desktops-popup-container")
        container_layout = QVBoxLayout(container_frame)
        container_layout.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel("Rename Desktop")
        title_label.setProperty("class", "popup-title")
        container_layout.addWidget(title_label)

        desc_label = QLabel("Enter a new name for this desktop.")
        desc_label.setProperty("class", "popup-description")
        container_layout.addWidget(desc_label)

        name_edit = QLineEdit()
        name_edit.setProperty("class", "rename-input")
        name_edit.setText(current_name)
        name_edit.setPlaceholderText("Desktop name")
        name_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        name_edit.selectAll()
        name_edit.setFocus()
        container_layout.addWidget(name_edit)

        rename_btn = QPushButton("Rename")
        rename_btn.setProperty("class", "button save")
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "button cancel")

        def do_rename():
            new_name = name_edit.text().strip()
            if new_name:
                try:
                    WindowsDesktopService.rename_desktop(workspace_index, new_name)
                    WindowsDesktopService().notify_desktops_updated(update_buttons=True)
                except Exception as e:
                    logging.exception("Failed to rename desktop: %s", e)
            popup.close()

        def update_rename_enabled():
            rename_btn.setEnabled(bool(name_edit.text().strip()))

        update_rename_enabled()
        name_edit.textChanged.connect(lambda _text: update_rename_enabled())
        name_edit.returnPressed.connect(do_rename)
        rename_btn.clicked.connect(do_rename)
        cancel_btn.clicked.connect(lambda: popup.close())

        footer_frame = QFrame()
        footer_frame.setProperty("class", "windows-desktops-popup-footer")
        button_layout = QHBoxLayout(footer_frame)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(0)
        button_layout.addWidget(rename_btn)
        button_layout.addWidget(cancel_btn)

        layout.addWidget(container_frame)
        layout.addWidget(footer_frame)

        popup.adjustSize()
        popup.setPosition(
            alignment="center",
            direction="down",
            offset_left=0,
            offset_top=6,
        )
        popup.show()

    def move_active_window_to(self, desktop_number: int, hwnd: int):
        try:
            WindowsDesktopService.move_window(hwnd, desktop_number)
        except Exception as e:
            logging.exception("Failed to move active window to desktop %s: %s", desktop_number, e)

    def toggle_pin_window(self, hwnd: int):
        try:
            WindowsDesktopService.toggle_pin_window(hwnd)
        except Exception as e:
            logging.exception("Failed to toggle pin window: %s", e)

    def toggle_pin_app(self, hwnd: int):
        try:
            WindowsDesktopService.toggle_pin_app(hwnd)
        except Exception as e:
            logging.exception("Failed to toggle pin app: %s", e)

    def delete_desktop(self):
        try:
            WindowsDesktopService.remove_desktop(self.workspace_index)
            WindowsDesktopService().notify_desktops_updated(update_buttons=False)
        except Exception as e:
            logging.exception("Failed to delete desktop: %s", e)

    def create_new_desktop(self):
        try:
            WindowsDesktopService.create_desktop()
            WindowsDesktopService().notify_desktops_updated(update_buttons=False)
        except Exception as e:
            logging.exception("Failed to create new desktop", exc_info=e)


class WorkspaceWidget(BaseWidget):
    validation_schema = WindowsDesktopsConfig

    def __init__(self, config: WindowsDesktopsConfig):
        super().__init__(class_name="windows-desktops")
        self.config = config
        self._svc = WindowsDesktopService()

        # Connect to service signals
        self._svc.desktop_changed.connect(self._on_desktop_changed)
        self._svc.desktops_updated.connect(self._on_update_desktops)

        self._virtual_desktops = range(1, len(self._svc.get_desktops()) + 1)
        self._prev_workspace_index = None
        self._curr_workspace_index = self._svc.get_current_desktop().number
        self._workspace_buttons: list[WorkspaceButton] = []

        self._clicked_button: WorkspaceButton | None = None

        # Disable default mouse event handling inherited from BaseWidget
        self.mousePressEvent = None

        # Register callbacks
        self.register_callback("activate_workspace", self._cb_activate_workspace)
        self.register_callback("toggle_context_menu", self._cb_toggle_context_menu)
        self.register_callback("move_window_here", self._cb_move_window_here)
        self.register_callback("delete_workspace", self._cb_delete_workspace)
        self.register_callback("create_desktop", self._cb_create_desktop)
        self.register_callback("rename_desktop", self._cb_rename_desktop)

        # Wire config callbacks to mouse buttons
        self.callback_left = config.callbacks.on_left
        self.callback_right = config.callbacks.on_right
        self.callback_middle = config.callbacks.on_middle

        # Construct container which holds workspace buttons
        self._init_container()

        self.register_callback("update_desktops", self._force_update)

        # Register with the service (auto-starts the shared timer)
        self._svc.register_widget(self)

        try:
            self.destroyed.connect(lambda _=None: self._svc.unregister_widget(self))
        except Exception:
            pass

        # initial update
        try:
            self._force_update()
        except Exception:
            logging.exception("Initial update_desktops failed on register")

    def _force_update(self):
        self._svc.notify_desktops_updated(update_buttons=False)

    def _cb_activate_workspace(self):
        if self._clicked_button:
            self._clicked_button.activate_workspace()

    def _cb_toggle_context_menu(self):
        if self._clicked_button:
            self._clicked_button._show_context_menu()

    def _cb_move_window_here(self):
        if self._clicked_button:
            try:
                svc = WindowsDesktopService()
                app_view = svc.get_foreground_app_view()
                if app_view:
                    WindowsDesktopService.move_window(app_view.hwnd, self._clicked_button.workspace_index)
            except Exception as e:
                logging.exception("Failed to move window to desktop %s: %s", self._clicked_button.workspace_index, e)

    def _cb_delete_workspace(self):
        if self._clicked_button:
            self._clicked_button.delete_desktop()

    def _cb_create_desktop(self):
        if self._clicked_button:
            self._clicked_button.create_new_desktop()

    def _cb_rename_desktop(self):
        if self._clicked_button:
            self._clicked_button.rename_desktop()

    def _on_desktop_changed(self, event_data: dict):
        # Keep track of previous index for animation coordination
        new_index = event_data["index"]
        self._prev_workspace_index = self._curr_workspace_index
        self._curr_workspace_index = new_index

        # Update only affected buttons (previous and current) and animate both simultaneously
        prev_btn = next((b for b in self._workspace_buttons if b.workspace_index == self._prev_workspace_index), None)
        curr_btn = next((b for b in self._workspace_buttons if b.workspace_index == self._curr_workspace_index), None)

        # Update labels without scheduling the automatic update/animation, we'll start animations explicitly
        if prev_btn is not None:
            self._update_button(prev_btn, schedule_update=False)
        if curr_btn is not None:
            self._update_button(curr_btn, schedule_update=False)

    def _on_update_desktops(self, event_data=None, options=None):
        self._virtual_desktops_check = list(range(1, len(self._svc.get_desktops()) + 1))
        self._curr_workspace_index_check = self._svc.get_current_desktop().number
        update_buttons = options.get("update_buttons") if options else False
        if (
            self._virtual_desktops != self._virtual_desktops_check
            or self._curr_workspace_index != self._curr_workspace_index_check
            or update_buttons
        ):
            self._virtual_desktops = self._virtual_desktops_check
            self._curr_workspace_index = self._curr_workspace_index_check
            self._add_or_remove_buttons()
            self.refresh_workspace_button_labels()

    def refresh_workspace_button_labels(self):
        for button in self._workspace_buttons:
            ws_label, ws_active_label = self._get_workspace_label(button.workspace_index)
            button.default_label = ws_label
            button.active_label = ws_active_label
            button.workspace_name = self._svc.get_desktop_name(button.workspace_index)
            self._update_button(button)

    def _clear_container_layout(self):
        for i in reversed(range(self._widget_container_layout.count())):
            old_workspace_widget = self._widget_container_layout.itemAt(i).widget()
            self._widget_container_layout.removeWidget(old_workspace_widget)
            old_workspace_widget.setParent(None)

    def _update_button(self, workspace_btn: WorkspaceButton, schedule_update: bool = True) -> None:
        existing_class = workspace_btn.property("class") or ""
        tokens = [t for t in str(existing_class).split() if t.startswith("button-")]

        # Determine base classes explicitly so stale tokens are not preserved
        if workspace_btn.workspace_index == self._curr_workspace_index:
            base = "ws-btn active"
            workspace_btn.update_text(workspace_btn.active_label)
        else:
            base = "ws-btn"
            workspace_btn.update_text(workspace_btn.default_label)
        if tokens:
            base = f"{base} {' '.join(tokens)}"

        workspace_btn.setProperty("class", base)
        refresh_widget_style(workspace_btn)
        if schedule_update:
            QTimer.singleShot(0, workspace_btn.update_visible_buttons)

    def _add_or_remove_buttons(self) -> None:
        current_indices = set(self._virtual_desktops)
        existing_indices = set(btn.workspace_index for btn in self._workspace_buttons)
        # Handle removals
        indices_to_remove = existing_indices - current_indices
        if indices_to_remove:
            self._workspace_buttons = [
                btn for btn in self._workspace_buttons if btn.workspace_index not in indices_to_remove
            ]

        # Handle additions
        for desktop_index in current_indices:
            # Find existing button with matching workspace_index
            existing_button = next(
                (btn for btn in self._workspace_buttons if btn.workspace_index == desktop_index), None
            )
            if existing_button:
                self._update_button(existing_button)
            else:
                new_button = self._try_add_workspace_button(desktop_index)
                self._update_button(new_button)
            self._workspace_buttons.sort(key=lambda btn: btn.workspace_index)
            self._clear_container_layout()
            for workspace_btn in self._workspace_buttons:
                self._widget_container_layout.addWidget(workspace_btn)
            try:
                QTimer.singleShot(0, lambda: [btn.update_visible_buttons() for btn in self._workspace_buttons])
            except Exception:
                pass

    def _get_workspace_label(self, workspace_index):
        ws_name = self._svc.get_desktop_name(workspace_index)
        if not ws_name:
            ws_name = f"{workspace_index}"
        label = self.config.label_workspace_btn.format(index=workspace_index, name=ws_name)
        active_label = self.config.label_workspace_active_btn.format(index=workspace_index, name=ws_name)
        return label, active_label

    def _try_add_workspace_button(self, workspace_index: int) -> WorkspaceButton:
        workspace_button_indexes = [ws_btn.workspace_index for ws_btn in self._workspace_buttons]
        if workspace_index not in workspace_button_indexes:
            ws_label, ws_active_label = self._get_workspace_label(workspace_index)
            workspace_btn = WorkspaceButton(workspace_index, ws_label, ws_active_label, self)
            self._update_button(workspace_btn)
            self._workspace_buttons.append(workspace_btn)
            return workspace_btn
