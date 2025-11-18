import logging

from PyQt6.QtCore import (
    QEasingCurve,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import QAction, QCursor
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QMenu,
    QPushButton,
)
from pyvda import VirtualDesktop, get_virtual_desktops, set_wallpaper_for_all_desktops

from core.event_service import EventService
from core.utils.utilities import add_shadow, is_windows_10, refresh_widget_style
from core.utils.widgets.komorebi.animation import KomorebiAnimation
from core.utils.win32.utilities import apply_qmenu_style
from core.validation.widgets.yasb.windows_desktops import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget


class WorkspaceButton(QPushButton):
    def __init__(self, workspace_index: int, label: str = None, active_label: str = None, parent=None):
        super().__init__(parent)

        self.workspace_index = workspace_index
        self.setProperty("class", "ws-btn")
        self.default_label = label if label else str(workspace_index)
        self.active_label = active_label if active_label else self.default_label
        self.setText(self.default_label)
        self.clicked.connect(self.activate_workspace)
        self.parent_widget = parent
        self.workspace_animation = getattr(self.parent_widget, "_switch_workspace_animation", False)
        self.animation = getattr(self.parent_widget, "_animation", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def update_text(self, text: str):
        """Update button text and capture width before change for animation"""
        if self.animation:
            self._pre_change_width = self.sizeHint().width()
        self.setText(text)

    def update_visible_buttons(self):
        visible_buttons = self.parent_widget._workspace_buttons
        for index, button in enumerate(visible_buttons):
            current_class = button.property("class")
            new_class = " ".join([cls for cls in current_class.split() if not cls.startswith("button-")])
            new_class = f"{new_class} button-{index + 1}"
            button.setProperty("class", new_class)
            refresh_widget_style(button)
        if self.animation:
            try:
                parent = self.parent_widget
                prev_idx = getattr(parent, "_prev_workspace_index", None)
                curr_idx = getattr(parent, "_curr_workspace_index", None)
                if self.workspace_index in (prev_idx, curr_idx):
                    self.animate_buttons()
            except Exception:
                self.animate_buttons()

    def activate_workspace(self):
        try:
            VirtualDesktop(self.workspace_index).go()
            if isinstance(self.parent_widget, WorkspaceWidget):
                self.parent_widget._event_service.emit_event("virtual_desktop_changed", {"index": self.workspace_index})
        except Exception:
            logging.exception(f"Failed to focus desktop at index {self.workspace_index}")

    def animate_buttons(self, duration: int = 120):
        # Use the centralized animation from Komorebi
        start_width = self._pre_change_width
        KomorebiAnimation.animate_width(
            self, duration=duration, easing=QEasingCurve.Type.OutCubic, start_width=start_width
        )

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        # Assign a class for global styling; apply rounded corners via helper
        menu.setProperty("class", "context-menu")
        # Apply Windows rounded corners to the QMenu when it is shown
        apply_qmenu_style(menu)

        act_rename = QAction("Rename", self)
        act_rename.triggered.connect(self.rename_desktop)
        menu.addAction(act_rename)

        act_delete = QAction("Delete", self)
        act_delete.triggered.connect(self.delete_desktop)
        menu.addAction(act_delete)

        menu.addSeparator()

        act_create = QAction("Create New Desktop", self)
        act_create.triggered.connect(self.create_new_desktop)
        menu.addAction(act_create)

        if not is_windows_10():
            menu.addSeparator()
            act_set_wall = QAction("Set Wallpaper On This Desktop", self)
            act_set_wall.triggered.connect(self.set_wallpaper)
            menu.addAction(act_set_wall)

            act_set_wall_all = QAction("Set Wallpaper On All Desktops", self)
            act_set_wall_all.triggered.connect(self.set_wallpaper_all)
            menu.addAction(act_set_wall_all)

        def _on_menu_about_to_hide():
            from core.global_state import get_autohide_owner_for_widget

            try:
                mgr = get_autohide_owner_for_widget(self)._autohide_manager
                if mgr._hide_timer:
                    mgr._hide_timer.start(mgr._autohide_delay)
            except Exception:
                pass

        menu.aboutToHide.connect(_on_menu_about_to_hide)

        menu.popup(self.mapToGlobal(event.pos()))
        try:
            menu.activateWindow()
        except Exception:
            pass

    def set_wallpaper(self):
        image_path, _ = QFileDialog.getOpenFileName(
            self, "Select Wallpaper Image", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if image_path:
            try:
                VirtualDesktop(self.workspace_index).set_wallpaper(image_path)
            except Exception as e:
                logging.exception(f"Failed to set wallpaper: {e}")

    def set_wallpaper_all(self):
        image_path, _ = QFileDialog.getOpenFileName(
            self, "Select Wallpaper Image", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if image_path:
            try:
                set_wallpaper_for_all_desktops(image_path)
            except Exception as e:
                logging.exception(f"Failed to set wallpaper for all desktops: {e}")

    def rename_desktop(self):
        dialog = QInputDialog(self)
        dialog.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)
        dialog.setWindowTitle("Rename This Desktop")
        dialog.setProperty("class", "rename-dialog")
        dialog.setLabelText("Enter name for this desktop")

        current_name = VirtualDesktop(self.workspace_index).name.strip()
        if not current_name:
            current_name = str(self.workspace_index)
        dialog.setTextValue(current_name)
        dialog.move(QCursor.pos())
        ok = dialog.exec()
        new_name = dialog.textValue().strip()
        if ok and new_name:
            try:
                VirtualDesktop(self.workspace_index).rename(new_name)
                if isinstance(self.parent_widget, WorkspaceWidget):
                    self.parent_widget._event_service.emit_event(
                        "virtual_desktop_update", {"index": self.workspace_index}, {"update_buttons": True}
                    )
            except Exception as e:
                logging.exception(f"Failed to rename desktop: {e}")
        else:
            logging.info("No name entered. Rename cancelled.")

    def delete_desktop(self):
        try:
            VirtualDesktop(self.workspace_index).remove()
            if isinstance(self.parent_widget, WorkspaceWidget):
                self.parent_widget.on_update_desktops()
        except Exception as e:
            logging.exception(f"Failed to delete desktop: {e}")

    def create_new_desktop(self):
        try:
            VirtualDesktop.create()
            if isinstance(self.parent_widget, WorkspaceWidget):
                self.parent_widget.on_update_desktops()
        except Exception as e:
            logging.exception("Failed to create new desktop", exc_info=e)


class WorkspaceWidget(BaseWidget):
    d_signal_virtual_desktop_changed = pyqtSignal(dict)
    d_signal_virtual_desktop_update = pyqtSignal(dict, dict)
    validation_schema = VALIDATION_SCHEMA
    _instances: list["WorkspaceWidget"] = []
    _shared_timer: QTimer | None = None

    def __init__(
        self,
        label_workspace_btn: str,
        label_workspace_active_btn: str,
        switch_workspace_animation: bool,
        animation: bool,
        container_padding: dict,
        btn_shadow: dict = None,
        container_shadow: dict = None,
    ):
        super().__init__(class_name="windows-desktops")
        self._event_service = EventService()

        self.d_signal_virtual_desktop_changed.connect(self._on_desktop_changed)
        self._event_service.register_event("virtual_desktop_changed", self.d_signal_virtual_desktop_changed)

        self.d_signal_virtual_desktop_update.connect(self._on_update_desktops)
        self._event_service.register_event("virtual_desktop_update", self.d_signal_virtual_desktop_update)

        self._label_workspace_btn = label_workspace_btn
        self._label_workspace_active_btn = label_workspace_active_btn
        self._padding = container_padding
        self._switch_workspace_animation = switch_workspace_animation
        self._animation = animation
        self._btn_shadow = btn_shadow
        self._container_shadow = container_shadow
        self._virtual_desktops = range(1, len(get_virtual_desktops()) + 1)
        self._prev_workspace_index = None
        self._curr_workspace_index = VirtualDesktop.current().number
        self._workspace_buttons: list[WorkspaceButton] = []

        # Disable default mouse event handling inherited from BaseWidget
        self.mousePressEvent = None

        # Construct container which holds workspace buttons
        self._workspace_container_layout = QHBoxLayout()
        self._workspace_container_layout.setSpacing(0)
        self._workspace_container_layout.setContentsMargins(
            self._padding["left"], self._padding["top"], self._padding["right"], self._padding["bottom"]
        )
        self._workspace_container = QFrame()
        self._workspace_container.setLayout(self._workspace_container_layout)
        self._workspace_container.setProperty("class", "widget-container")
        add_shadow(self._workspace_container, self._container_shadow)
        self.widget_layout.addWidget(self._workspace_container)

        self.register_callback("update_desktops", self.on_update_desktops)

        # Register this instance to the class-wide shared timer (one timer per widget class)
        if self not in WorkspaceWidget._instances:
            WorkspaceWidget._instances.append(self)

        if WorkspaceWidget._shared_timer is None:
            WorkspaceWidget._shared_timer = QTimer(self)
            WorkspaceWidget._shared_timer.setInterval(500)
            WorkspaceWidget._shared_timer.timeout.connect(WorkspaceWidget._notify_instances)
            WorkspaceWidget._shared_timer.start()

        try:
            self.destroyed.connect(
                lambda _=None: WorkspaceWidget._instances.remove(self) if self in WorkspaceWidget._instances else None
            )
        except Exception:
            pass

        # initial update
        try:
            self.on_update_desktops()
        except Exception:
            logging.exception("Initial update_desktops failed on register")

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

        # Start both animations so they run in parallel
        if prev_btn is not None and getattr(prev_btn, "animation", False):
            prev_btn.animate_buttons()
        if curr_btn is not None and getattr(curr_btn, "animation", False):
            curr_btn.animate_buttons()

    def on_update_desktops(self):
        # Emit event to update desktops on all monitors
        self._event_service.emit_event(
            "virtual_desktop_update", {"index": VirtualDesktop.current().number}, {"update_buttons": False}
        )

    def _on_update_desktops(self, event_data=None, options=None):
        self._virtual_desktops_check = list(range(1, len(get_virtual_desktops()) + 1))
        self._curr_workspace_index_check = VirtualDesktop.current().number
        update_buttons = options.get("update_buttons") if options else False
        if (
            self._virtual_desktops != self._virtual_desktops_check
            or self._curr_workspace_index != self._curr_workspace_index_check
            or update_buttons
        ):
            self._virtual_desktops = self._virtual_desktops_check
            self._curr_workspace_index = self._curr_workspace_index_check
            self._add_or_remove_buttons()
            self.refresh_workspace_button_labels(animate=update_buttons)

    def refresh_workspace_button_labels(self, animate: bool = False):
        for button in self._workspace_buttons:
            ws_label, ws_active_label = self._get_workspace_label(button.workspace_index)
            button.default_label = ws_label
            button.active_label = ws_active_label
            button.workspace_name = VirtualDesktop(button.workspace_index).name
            self._update_button(button)
            if animate and getattr(button, "animation", False):
                try:
                    button.animate_buttons()
                except Exception:
                    pass

    def _clear_container_layout(self):
        for i in reversed(range(self._workspace_container_layout.count())):
            old_workspace_widget = self._workspace_container_layout.itemAt(i).widget()
            self._workspace_container_layout.removeWidget(old_workspace_widget)
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
                self._workspace_container_layout.addWidget(workspace_btn)
                add_shadow(workspace_btn, self._btn_shadow)
            try:
                QTimer.singleShot(0, lambda: [btn.update_visible_buttons() for btn in self._workspace_buttons])
                for btn in self._workspace_buttons:
                    if getattr(btn, "animation", False):
                        try:
                            QTimer.singleShot(0, btn.animate_buttons)
                        except Exception:
                            pass
            except Exception:
                pass

    def _get_workspace_label(self, workspace_index):
        try:
            ws_name = VirtualDesktop(workspace_index).name
        except Exception:
            ws_name = ""
        if not ws_name or not ws_name.strip():
            ws_name = f"{workspace_index}"
        label = self._label_workspace_btn.format(index=workspace_index, name=ws_name)
        active_label = self._label_workspace_active_btn.format(index=workspace_index, name=ws_name)
        return label, active_label

    def _try_add_workspace_button(self, workspace_index: int) -> WorkspaceButton:
        workspace_button_indexes = [ws_btn.workspace_index for ws_btn in self._workspace_buttons]
        if workspace_index not in workspace_button_indexes:
            ws_label, ws_active_label = self._get_workspace_label(workspace_index)
            workspace_btn = WorkspaceButton(workspace_index, ws_label, ws_active_label, self)
            self._update_button(workspace_btn)
            self._workspace_buttons.append(workspace_btn)
            return workspace_btn

    @classmethod
    def _notify_instances(cls):
        if not cls._instances:
            return
        for inst in cls._instances[:]:
            try:
                inst.on_update_desktops()
            except Exception:
                try:
                    cls._instances.remove(inst)
                except Exception:
                    pass
        if not cls._instances and cls._shared_timer:
            try:
                cls._shared_timer.stop()
            except Exception:
                pass
            cls._shared_timer = None
