import logging

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QFileDialog, QHBoxLayout, QInputDialog, QLabel, QPushButton, QVBoxLayout, QWidget
from pyvda import VirtualDesktop, get_virtual_desktops, set_wallpaper_for_all_desktops

from core.event_service import EventService
from core.utils.utilities import PopupWidget, add_shadow, is_windows_10
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
        self.workspace_animation = self.parent_widget._switch_workspace_animation
        self.animation = self.parent_widget._animation
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def update_visible_buttons(self):
        visible_buttons = [btn for btn in self.parent_widget._workspace_buttons if btn.isVisible()]
        for index, button in enumerate(visible_buttons):
            current_class = button.property("class")
            new_class = " ".join([cls for cls in current_class.split() if not cls.startswith("button-")])
            new_class = f"{new_class} button-{index + 1}"
            button.setProperty("class", new_class)
            button.setStyleSheet("")
        if self.animation:
            self.animate_buttons()

    def activate_workspace(self):
        try:
            # VirtualDesktop(self.workspace_index).go(self.workspace_animation)
            VirtualDesktop(self.workspace_index).go()
            if isinstance(self.parent_widget, WorkspaceWidget):
                # Emit event to update desktops on all monitors
                self.parent_widget._event_service.emit_event("virtual_desktop_changed", {"index": self.workspace_index})
        except Exception:
            logging.exception(f"Failed to focus desktop at index {self.workspace_index}")

    def animate_buttons(self, duration=200, step=120):
        # Store the initial width if not already stored
        # we need this to animate the width back to the initial width
        if not hasattr(self, "_initial_width"):
            self._initial_width = self.width()

        self._current_width = self.width()
        target_width = self.sizeHint().width()

        step_duration = int(duration / step)
        width_increment = (target_width - self._current_width) / step

        self._current_step = 0

        def update_width():
            if self._current_step < step:
                self._current_width += width_increment
                self.setFixedWidth(int(self._current_width))
                self._current_step += 1
            else:
                self._animation_timer.stop()
                self.setFixedWidth(target_width)

        # Stop any existing timer before starting a new one to prevent conflicts
        if hasattr(self, "_animation_timer") and self._animation_timer.isActive():
            self._animation_timer.stop()

        self._animation_timer = QTimer()
        self._animation_timer.timeout.connect(update_width)
        self._animation_timer.start(step_duration)

    def contextMenuEvent(self, event):
        # Create the popup menu
        self._popup_menu = PopupWidget(self)
        self._popup_menu.setProperty("class", "context-menu")

        layout = QVBoxLayout(self._popup_menu)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        def add_menu_item(text, handler):
            label = QLabel(text, self._popup_menu)
            label.setProperty("class", "menu-item")
            label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            # Mouse press event handler

            def mousePressEvent(event):
                handler()
                self._popup_menu.hide()

            label.mousePressEvent = mousePressEvent
            layout.addWidget(label)

        add_menu_item("Rename", self.rename_desktop)
        add_menu_item("Delete", self.delete_desktop)

        self._popup_menu._add_separator(layout)

        add_menu_item("Create New Desktop", self.create_new_desktop)

        if not is_windows_10():
            # Separator
            self._popup_menu._add_separator(layout)

            add_menu_item("Set Wallpaper On This Desktop", self.set_wallpaper)
            add_menu_item("Set Wallpaper On All Desktops", self.set_wallpaper_all)

        self._popup_menu.adjustSize()
        self._popup_menu.move(self.mapToGlobal(event.pos()))
        self._popup_menu.show()

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
        # Set the initial text value to the current desktop name or fallback to its index
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
        self._workspace_container_layout: QHBoxLayout = QHBoxLayout()
        self._workspace_container_layout.setSpacing(0)
        self._workspace_container_layout.setContentsMargins(
            self._padding["left"], self._padding["top"], self._padding["right"], self._padding["bottom"]
        )
        self._workspace_container: QWidget = QWidget()
        self._workspace_container.setLayout(self._workspace_container_layout)
        self._workspace_container.setProperty("class", "widget-container")
        add_shadow(self._workspace_container, self._container_shadow)
        self.widget_layout.addWidget(self._workspace_container)

        self.timer_interval = 500  # milliseconds
        self.callback_timer = "update_desktops"
        self.register_callback(self.callback_timer, self.on_update_desktops)
        self.start_timer()

    def _on_desktop_changed(self, event_data: dict):
        self._curr_workspace_index = event_data["index"]
        for button in self._workspace_buttons:
            self._update_button(button)

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
        ):
            self._virtual_desktops = self._virtual_desktops_check
            self._curr_workspace_index = self._curr_workspace_index_check
            self._add_or_remove_buttons()
            self.refresh_workspace_button_labels()
        if update_buttons:
            self.refresh_workspace_button_labels()

    def refresh_workspace_button_labels(self):
        for button in self._workspace_buttons:
            ws_label, ws_active_label = self._get_workspace_label(button.workspace_index)
            button.default_label = ws_label
            button.active_label = ws_active_label
            button.workspace_name = VirtualDesktop(button.workspace_index).name
            self._update_button(button)

    def _clear_container_layout(self):
        for i in reversed(range(self._workspace_container_layout.count())):
            old_workspace_widget = self._workspace_container_layout.itemAt(i).widget()
            self._workspace_container_layout.removeWidget(old_workspace_widget)
            old_workspace_widget.setParent(None)

    def _update_button(self, workspace_btn: WorkspaceButton) -> None:
        if workspace_btn.workspace_index == self._curr_workspace_index:
            workspace_btn.setProperty("class", "ws-btn active")
            workspace_btn.setStyleSheet("")
            workspace_btn.setText(workspace_btn.active_label)
        else:
            workspace_btn.setProperty("class", "ws-btn")
            workspace_btn.setStyleSheet("")
            workspace_btn.setText(workspace_btn.default_label)
        QTimer.singleShot(0, workspace_btn.update_visible_buttons)

    def _add_or_remove_buttons(self) -> None:
        changes_made = False
        current_indices = set(self._virtual_desktops)
        existing_indices = set(btn.workspace_index for btn in self._workspace_buttons)
        # Handle removals
        indices_to_remove = existing_indices - current_indices
        if indices_to_remove:
            self._workspace_buttons = [
                btn for btn in self._workspace_buttons if btn.workspace_index not in indices_to_remove
            ]
            changes_made = True

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
                changes_made = True
        # Rebuild layout only if changes occurred
        if changes_made:
            self._workspace_buttons.sort(key=lambda btn: btn.workspace_index)
            self._clear_container_layout()
            for workspace_btn in self._workspace_buttons:
                self._workspace_container_layout.addWidget(workspace_btn)
                add_shadow(workspace_btn, self._btn_shadow)

    def _get_workspace_label(self, workspace_index):
        ws_name = VirtualDesktop(workspace_index).name
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
