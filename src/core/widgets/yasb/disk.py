import os
import re

import win32api
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from core.utils.utilities import (
    PopupWidget,
    add_shadow,
    build_progress_widget,
    build_widget_label,
    refresh_widget_style,
)
from core.utils.widgets.animation_manager import AnimationManager
from core.validation.widgets.yasb.disk import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget


class ClickableDiskWidget(QWidget):
    clicked = pyqtSignal()

    def __init__(self, label, parent=None):
        super().__init__(parent)
        self.label = label

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class DiskWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
        self,
        label: str,
        label_alt: str,
        class_name: str,
        volume_label: str,
        decimal_display: int,
        update_interval: int,
        group_label: dict[str, str],
        container_padding: dict[str, int],
        animation: dict[str, str],
        callbacks: dict[str, str],
        disk_thresholds: dict[str, int],
        label_shadow: dict = None,
        container_shadow: dict = None,
        progress_bar: dict = None,
    ):
        super().__init__(int(update_interval * 1000), class_name=f"disk-widget {class_name}")
        self._decimal_display = decimal_display
        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt
        self._volume_label = volume_label.upper()
        self._padding = container_padding
        self._group_label = group_label
        self._animation = animation
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow
        self._disk_thresholds = disk_thresholds
        self._progress_bar = progress_bar

        self.progress_widget = None
        self.progress_widget = build_progress_widget(self, self._progress_bar)

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
        self.register_callback("toggle_group", self._toggle_group)
        self.register_callback("update_label", self._update_label)
        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]
        self.callback_timer = "update_label"
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

    def _toggle_group(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self.show_group_label()

    def _update_label(self):
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content
        label_parts = re.split(r"(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0

        disk_space = self._get_space()
        percent_value = float(disk_space["used"]["percent"].rstrip("%")) if disk_space else 0

        if self._progress_bar["enabled"] and self.progress_widget:
            if self._widget_container_layout.indexOf(self.progress_widget) == -1:
                self._widget_container_layout.insertWidget(
                    0 if self._progress_bar["position"] == "left" else self._widget_container_layout.count(),
                    self.progress_widget,
                )

            self.progress_widget.set_value(percent_value)

        for part in label_parts:
            part = part.strip()
            if part and widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                if "<span" in part and "</span>" in part:
                    # Ensure the icon is correctly set
                    icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                    active_widgets[widget_index].setText(icon)
                else:
                    # Update label with formatted content
                    label_class = "label alt" if self._show_alt_label else "label"
                    formatted_text = (
                        part.format(space=disk_space, volume_label=self._volume_label) if disk_space else part
                    )
                    active_widgets[widget_index].setProperty(
                        "class", f"{label_class} status-{self._get_disk_threshold(percent_value)}"
                    )
                    active_widgets[widget_index].setText(formatted_text)
                    refresh_widget_style(active_widgets[widget_index])
                widget_index += 1

    def _get_volume_label(self, drive_letter):
        if not self._group_label["show_label_name"]:
            return None
        try:
            volume_label = win32api.GetVolumeInformation(f"{drive_letter}:\\")[0]
            return volume_label
        except Exception:
            return None

    def show_group_label(self):
        self.dialog = PopupWidget(
            self,
            self._group_label["blur"],
            self._group_label["round_corners"],
            self._group_label["round_corners_type"],
            self._group_label["border_color"],
        )
        self.dialog.setProperty("class", "disk-group")

        layout = QVBoxLayout()
        for label in self._group_label["volume_labels"]:
            disk_space = self._get_space(label)
            if disk_space is None:
                continue
            row_widget = QWidget()
            row_widget.setProperty("class", "disk-group-row")

            volume_label = self._get_volume_label(label)
            display_label = f"{volume_label} ({label}):" if volume_label else f"{label}:"

            clicable_row = ClickableDiskWidget(label)
            clicable_row.clicked.connect(lambda lbl=label: self.open_explorer(lbl))
            clicable_row.setCursor(Qt.CursorShape.PointingHandCursor)

            v_layout = QVBoxLayout(clicable_row)
            h_layout = QHBoxLayout()

            label_widget = QLabel(display_label)
            label_widget.setProperty("class", "disk-group-label")
            h_layout.addWidget(label_widget)

            label_size = QLabel()
            label_size.setProperty("class", "disk-group-label-size")

            # show size in TB if it's more than 1000GB
            total_gb = float(disk_space["total"]["gb"].strip("GB"))
            free_gb = float(disk_space["free"]["gb"].strip("GB"))
            if total_gb > 1000:
                total_size = disk_space["total"]["tb"]
            else:
                total_size = disk_space["total"]["gb"]

            if free_gb > 1000:
                free_size = disk_space["free"]["tb"]
            else:
                free_size = disk_space["free"]["gb"]
            label_size.setText(f"{free_size} / {total_size}")
            h_layout.addStretch()
            h_layout.addWidget(label_size)

            v_layout.addLayout(h_layout)

            progress_bar = QProgressBar()
            progress_bar.setTextVisible(False)
            progress_bar.setProperty("class", "disk-group-label-bar")
            if disk_space:
                progress_bar.setValue(int(float(disk_space["used"]["percent"].strip("%"))))
            v_layout.addWidget(progress_bar)

            row_widget_layout = QVBoxLayout(row_widget)
            row_widget_layout.setContentsMargins(0, 0, 0, 0)
            row_widget_layout.setSpacing(0)
            row_widget_layout.addWidget(clicable_row)

            layout.addWidget(row_widget)

        self.dialog.setLayout(layout)

        # Position the dialog
        self.dialog.adjustSize()
        self.dialog.setPosition(
            alignment=self._group_label["alignment"],
            direction=self._group_label["direction"],
            offset_left=self._group_label["offset_left"],
            offset_top=self._group_label["offset_top"],
        )
        self.dialog.show()

    def open_explorer(self, label):
        os.startfile(f"{label}:\\")

    def _get_space(self, volume_label=None):
        if volume_label is None:
            volume_label = self._volume_label

        try:
            free_bytes, total_bytes, _ = win32api.GetDiskFreeSpaceEx(f"{volume_label}:\\")
        except Exception:
            return None

        if total_bytes == 0:
            return None

        used_bytes = total_bytes - free_bytes
        percent_used = (used_bytes / total_bytes) * 100
        percent_free = 100 - percent_used
        d = self._decimal_display

        return {
            "total": {
                "mb": f"{total_bytes / 1048576:.{d}f}MB",
                "gb": f"{total_bytes / 1073741824:.{d}f}GB",
                "tb": f"{total_bytes / 1099511627776:.{d}f}TB",
            },
            "free": {
                "mb": f"{free_bytes / 1048576:.{d}f}MB",
                "gb": f"{free_bytes / 1073741824:.{d}f}GB",
                "tb": f"{free_bytes / 1099511627776:.{d}f}TB",
                "percent": f"{percent_free:.{d}f}%",
            },
            "used": {
                "mb": f"{used_bytes / 1048576:.{d}f}MB",
                "gb": f"{used_bytes / 1073741824:.{d}f}GB",
                "tb": f"{used_bytes / 1099511627776:.{d}f}TB",
                "percent": f"{percent_used:.{d}f}%",
            },
        }

    def _get_disk_threshold(self, disk_percent) -> str:
        if disk_percent <= self._disk_thresholds["low"]:
            return "low"
        elif self._disk_thresholds["low"] < disk_percent <= self._disk_thresholds["medium"]:
            return "medium"
        elif self._disk_thresholds["medium"] < disk_percent <= self._disk_thresholds["high"]:
            return "high"
        elif self._disk_thresholds["high"] < disk_percent:
            return "critical"
