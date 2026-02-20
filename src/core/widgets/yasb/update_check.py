import re

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel

from core.utils.tooltip import set_tooltip
from core.utils.utilities import add_shadow, refresh_widget_style
from core.utils.widgets.update_check.service import UpdateCheckService
from core.validation.widgets.yasb.update_check import UpdateCheckWidgetConfig
from core.widgets.base import BaseWidget

# Sources and their config attribute names
_SOURCES = ("winget", "scoop", "windows")


class UpdateCheckWidget(BaseWidget):
    validation_schema = UpdateCheckWidgetConfig

    def __init__(self, config: UpdateCheckWidgetConfig):
        super().__init__(class_name="update-check-widget")
        self.config = config

        self._containers: dict[str, QFrame | None] = {}
        self._label_widgets: dict[str, list[QLabel]] = {}
        self._counts: dict[str, int] = {}

        for source in _SOURCES:
            cfg = getattr(self.config, f"{source}_update", None)
            if cfg and cfg.enabled:
                container, widgets = self._create_container(source, cfg.label)
                self._containers[source] = container
                self._label_widgets[source] = widgets
            else:
                self._containers[source] = None
                self._label_widgets[source] = []
            self._counts[source] = 0

        # Register with shared service
        self._service = UpdateCheckService()
        self._service.register_widget(self)

        self._update_visibility()

    def on_update(self, source: str, result: dict):
        """Receive update data from the service."""
        count = result.get("count", 0)
        names = result.get("names", [])
        self._counts[source] = count
        self._update_labels(source, count, names)
        self._update_visibility()

    def _create_container(self, source: str, label_text: str) -> tuple[QFrame, list[QLabel]]:
        """Create a container with label widgets for a source."""
        container = QFrame()
        layout = QHBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        container.setLayout(layout)
        container.setProperty("class", f"widget-container {source}")
        add_shadow(container, self.config.container_shadow.model_dump())
        self.widget_layout.addWidget(container)
        container.hide()

        label_parts = re.split(r"(<span.*?>.*?</span>)", label_text)
        label_parts = [p for p in label_parts if p]
        widgets: list[QLabel] = []

        for part in label_parts:
            part = part.strip()
            if not part:
                continue
            if "<span" in part and "</span>" in part:
                class_match = re.search(r'class=(["\'])([^"\']+?)\1', part)
                class_result = class_match.group(2) if class_match else "icon"
                icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                label = QLabel(icon)
                label.setProperty("class", class_result)
            else:
                label = QLabel(part)
                label.setProperty("class", "label")

            add_shadow(label, self.config.label_shadow.model_dump())
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)
            widgets.append(label)
            label.mousePressEvent = self._make_mouse_handler(source)

        return container, widgets

    def _update_labels(self, source: str, count: int, names: list[str]):
        """Update text in label widgets for a source."""
        container = self._containers.get(source)
        if container is None:
            return

        if count == 0:
            container.hide()
            return

        container.show()
        cfg = getattr(self.config, f"{source}_update", None)
        if cfg is None:
            return

        label_parts = re.split(r"(<span.*?>.*?</span>)", cfg.label)
        label_parts = [p for p in label_parts if p]
        widgets = self._label_widgets.get(source, [])
        idx = 0

        for part in label_parts:
            part = part.strip()
            if not part or idx >= len(widgets):
                continue
            w = widgets[idx]
            if not isinstance(w, QLabel):
                idx += 1
                continue

            if "<span" in part and "</span>" in part:
                icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                w.setText(icon)
            else:
                w.setText(part.format(count=count))
            w.setCursor(Qt.CursorShape.PointingHandCursor)
            idx += 1

        if cfg.tooltip:
            title = {"winget": "Winget Update", "scoop": "Scoop Update", "windows": "Windows Update"}.get(
                source, source
            )
            body = "<br>".join(names)
            set_tooltip(container, f"<b>{title}</b><br><br>{body}")

    def _update_visibility(self):
        """Show/hide widget and adjust paired styling."""
        visible_sources = [s for s in _SOURCES if self._counts.get(s, 0) > 0]

        for source in _SOURCES:
            container = self._containers.get(source)
            if container is None:
                continue
            if source in visible_sources:
                idx = visible_sources.index(source)
                has_left = idx > 0
                has_right = idx < len(visible_sources) - 1
                self._set_container_class(container, source, has_left, has_right)
            else:
                self._set_container_class(container, source, False, False)

        if visible_sources:
            self.show()
        else:
            self.hide()

        refresh_widget_style(self)

    def _set_container_class(self, container: QFrame, base_class: str, has_left: bool, has_right: bool):
        """Set the CSS class on a container."""
        class_name = f"widget-container {base_class}"
        if has_left:
            class_name += " paired-left"
        if has_right:
            class_name += " paired-right"
        container.setStyleSheet("")
        container.setProperty("class", class_name)
        container.setStyleSheet(container.styleSheet())
        refresh_widget_style(container)

    def _make_mouse_handler(self, source: str):
        """Create a mouse event handler for a source container."""

        def handler(event):
            if event.button() == Qt.MouseButton.LeftButton:
                self._service.handle_left_click(source)
            elif event.button() == Qt.MouseButton.RightButton:
                self._service.handle_right_click(source)

        return handler
