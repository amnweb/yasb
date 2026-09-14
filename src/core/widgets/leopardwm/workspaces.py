"""Native workspace strip backed by LeopardWM's shared event subscription."""

import logging
import ntpath
from dataclasses import dataclass

from PIL import Image, ImageOps
from PyQt6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QImage, QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QStyle, QStyleOptionButton

from core.utils.tooltip import set_tooltip
from core.utils.utilities import refresh_widget_style
from core.utils.win32.app_icons import get_window_icon
from core.utils.win32.utils import get_process_info
from core.validation.widgets.leopardwm.workspaces import LeopardWMWorkspacesConfig
from core.widgets.base import BaseWidget
from core.widgets.services.leopardwm.client import LeopardWMClient
from core.widgets.services.leopardwm.state import Monitor, Workspace, WorkspaceSnapshot

logger = logging.getLogger(__name__)


class _LookupSignals(QObject):
    loaded = pyqtSignal(object)


class _IconLookup(QRunnable):
    """Keep potentially slow Win32 icon extraction off the GUI thread."""

    def __init__(self, requests):
        super().__init__()
        self.requests = requests
        self.signals = _LookupSignals()

    def run(self):
        results = []
        for hwnd, token, need_image in self.requests:
            name, image = "", None
            try:
                process = get_process_info(hwnd)
                name = ntpath.basename(process.get("name") or process.get("path") or "").casefold()
                if need_image:
                    image = get_window_icon(hwnd)
            except Exception:
                logger.debug("Could not resolve LeopardWM window %s", hwnd, exc_info=True)
            results.append((hwnd, token, name, need_image, image))
        self.signals.loaded.emit(results)


@dataclass
class _WindowIcon:
    name: str
    image_loaded: bool = False
    pixmap: QPixmap | None = None


class WorkspaceButton(QPushButton):
    """A keyboard-accessible workspace button with independently styled contents."""

    def __init__(self, device_name, index, activate, parent):
        super().__init__(parent)
        self.device_name = device_name
        self.index = index
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        self.clicked.connect(lambda: activate(device_name, index))
        self.content_layout = QHBoxLayout(self)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        self.text_label = self._label("", "label")
        self.content_layout.addWidget(self.text_label)
        self.icon_labels = []
        self._appearance = None
        self._icon_signature = None

    def _label(self, text, class_name):
        label = QLabel(text, self)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setProperty("class", class_name)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        return label

    def sizeHint(self):
        option = QStyleOptionButton()
        self.initStyleOption(option)
        return self.style().sizeFromContents(
            QStyle.ContentsType.CT_PushButton, option, self.content_layout.sizeHint(), self
        )

    def minimumSizeHint(self):
        return self.sizeHint()

    def update_content(self, text, classes, icons, overflow, config, tooltip):
        signature = tuple(icon.cacheKey() if isinstance(icon, QPixmap) else icon for icon in icons), overflow
        if signature != self._icon_signature:
            self._icon_signature = signature
            for label in self.icon_labels:
                self.content_layout.removeWidget(label)
                label.hide()
                label.deleteLater()
            self.icon_labels = []
            for icon in icons:
                label = self._label("", "icon")
                label.setFixedHeight(config.size)
                label.setMinimumWidth(config.size)
                if isinstance(icon, QPixmap):
                    label.setPixmap(icon)
                else:
                    font = QFont("Segoe Fluent Icons")
                    font.setPixelSize(config.size)
                    label.setFont(font)
                    label.setText(icon)
                self.content_layout.addWidget(label)
                self.icon_labels.append(label)
            if overflow:
                label = self._label(f"+{overflow}", "overflow")
                self.content_layout.addWidget(label)
                self.icon_labels.append(label)
        appearance = text, classes, bool(icons) and config.hide_label, tooltip
        if appearance != self._appearance:
            self._appearance = appearance
            self.text_label.setText(text)
            self.text_label.setHidden(appearance[2])
            self.setAccessibleName(tooltip.replace("\n", ", "))
            set_tooltip(self, tooltip)
            self.setProperty("class", classes)
            refresh_widget_style(self, self.text_label, *self.icon_labels)
        self.updateGeometry()


class WorkspaceWidget(BaseWidget):
    validation_schema = LeopardWMWorkspacesConfig

    def __init__(self, config: LeopardWMWorkspacesConfig):
        super().__init__(class_name="leopardwm-workspaces")
        self.config = config
        self._init_container()
        self._offline_text = QLabel(config.label_offline)
        self._offline_text.setTextFormat(Qt.TextFormat.PlainText)
        self._offline_text.setProperty("class", "offline")
        self.widget_layout.addWidget(self._offline_text)
        self._buttons = {}
        self._snapshot = None
        self._client = None
        self._icon_cache = {}
        self._handle_tokens = {}
        self._next_token = 0
        self._lookup_running = False
        self._lookup = None
        self._requests = {}
        self._glyphs = {ntpath.basename(name).casefold(): glyph for name, glyph in config.app_icons.glyphs.items()}
        self._set_offline()
        # BarManager/Bar assign screen_name and monitor_hwnd after construction;
        # defer rendering shared clients until that monitor identity is available.
        self._connect_timer = QTimer(self)
        self._connect_timer.setSingleShot(True)
        self._connect_timer.timeout.connect(self._connect_client)
        self._connect_timer.start(0)

    def _connect_client(self):
        self._client = LeopardWMClient.acquire(self.config.lwm_path)
        self._client.state_changed.connect(self._on_state)
        self._client.connection_changed.connect(self._on_connection)
        self._client.error_occurred.connect(self._on_error)
        self._on_error(self._client.error_message)
        # A closure independent of self survives QObject teardown; a bound method
        # on the destroyed widget does not reliably receive destroyed().
        client = self._client
        self.destroyed.connect(lambda: client.release())
        if client.connected and client.snapshot is not None:
            self._on_state(client.snapshot)

    def _on_error(self, message):
        set_tooltip(self._offline_text, message or self.config.label_offline)

    def _on_connection(self, connected):
        if not connected:
            self._set_offline()
        elif self._client.snapshot is not None:
            self._on_state(self._client.snapshot)

    def _remove_buttons(self, keys):
        for key in keys:
            button = self._buttons.pop(key)
            self._widget_container_layout.removeWidget(button)
            button.hide()
            button.deleteLater()

    def _set_offline(self):
        self._snapshot = None
        self._remove_buttons(list(self._buttons))
        self._icon_cache.clear()
        self._handle_tokens.clear()
        self._requests.clear()
        self._widget_container.hide()
        self._offline_text.show()
        if self.config.hide_if_offline:
            self.hide()

    def _selected_monitors(self):
        if self._snapshot is None:
            return ()
        monitors = self._snapshot.monitors
        if self.config.monitor:
            return tuple(m for m in monitors if m.device_name.casefold() == self.config.monitor.casefold())
        if not self.config.monitor_exclusive:
            return monitors
        monitor = self._bar_monitor(monitors)
        return (monitor,) if monitor is not None else ()

    def _bar_monitor(self, monitors):
        # Qt 6 screen names can be friendly model names (and can be identical).
        # LeopardWM monitor_id and Bar.monitor_hwnd both identify the HMONITOR.
        monitor = next((m for m in monitors if m.monitor_id == self.monitor_hwnd), None)
        if monitor is not None:
            return monitor
        return next((m for m in monitors if m.device_name.casefold() == (self.screen_name or "").casefold()), None)

    def _on_state(self, snapshot: WorkspaceSnapshot):
        if not isinstance(snapshot, WorkspaceSnapshot):
            self._set_offline()
            return
        if self._snapshot is not None and self._snapshot.session_id != snapshot.session_id:
            self._icon_cache.clear()
            self._handle_tokens.clear()
        self._snapshot = snapshot
        self._offline_text.hide()
        self._widget_container.show()
        self.show()
        self._render()

    def _render(self):
        monitors = self._selected_monitors()
        current = {window.hwnd for m in monitors for ws in m.workspaces for window in ws.windows}
        self._icon_cache = {hwnd: icon for hwnd, icon in self._icon_cache.items() if hwnd in current}
        self._handle_tokens = {hwnd: token for hwnd, token in self._handle_tokens.items() if hwnd in current}
        for hwnd in current - self._handle_tokens.keys():
            self._next_token += 1
            self._handle_tokens[hwnd] = self._next_token
        self._requests = {}
        keys = {(m.device_name, ws.index) for m in monitors for ws in m.workspaces}
        self._remove_buttons(self._buttons.keys() - keys)
        position = 0
        for monitor in monitors:
            for workspace in monitor.workspaces:
                key = monitor.device_name, workspace.index
                if key not in self._buttons:
                    self._buttons[key] = WorkspaceButton(*key, self._activate, self)
                button = self._buttons[key]
                if self._widget_container_layout.indexOf(button) != position:
                    self._widget_container_layout.insertWidget(position, button)
                position += 1
                active = workspace.index == monitor.active_workspace_index
                populated = bool(workspace.windows)
                visible = active or (
                    self.config.show_inactive_workspaces and (populated or not self.config.hide_empty_workspaces)
                )
                button.setVisible(visible)
                if not visible:
                    continue
                classes = ["ws-btn", "populated" if populated else "empty"]
                if active:
                    classes.append("active")
                    if monitor.device_name == self._snapshot.focused_monitor_device_name:
                        classes.append("focused")
                icons, overflow = self._workspace_icons(workspace)
                name = f" ({workspace.name})" if workspace.name else ""
                count = len(workspace.windows)
                tooltip = (
                    f"{monitor.device_name}\nWorkspace {workspace.index + 1}{name}\n"
                    f"{count} window{'s' if count != 1 else ''}"
                )
                button.update_content(
                    self._label(monitor, workspace, active),
                    " ".join(classes),
                    icons,
                    overflow,
                    self.config.app_icons,
                    tooltip,
                )
        self._start_lookup()

    def _label(self, monitor: Monitor, workspace: Workspace, active: bool):
        template = self.config.label_workspace_btn
        if active:
            template = self.config.label_workspace_active_btn
        elif workspace.windows:
            template = self.config.label_workspace_populated_btn
        try:
            return template.format(
                index=workspace.index + 1,
                name=workspace.name or "",
                count=len(workspace.windows),
                monitor=monitor.device_name,
            )
        except KeyError, ValueError, IndexError, AttributeError:
            return str(workspace.index + 1)

    def _workspace_icons(self, workspace):
        config = self.config.app_icons
        if not config.enabled:
            return [], 0
        selected, seen = [], set()
        for window in workspace.windows:
            if config.hide_floating and window.is_floating:
                continue
            cached = self._icon_cache.get(window.hwnd)
            if cached is None:
                self._requests.setdefault(window.hwnd, False)
            # Unknown executables stay distinct rather than being collapsed into
            # a single unknown app; occupancy always uses the unfiltered windows.
            identity = cached.name if cached and cached.name else window.hwnd
            if config.hide_duplicates and identity in seen:
                continue
            seen.add(identity)
            selected.append(window.hwnd)
        overflow = max(0, len(selected) - config.max_icons) if config.max_icons else 0
        if config.max_icons:
            selected = selected[: config.max_icons]
        icons = []
        for hwnd in selected:
            cached = self._icon_cache.get(hwnd)
            if config.mode == "native":
                if cached is None or not cached.image_loaded:
                    self._requests[hwnd] = True
                icons.append(cached.pixmap if cached and cached.pixmap is not None else config.fallback_icon)
            else:
                icons.append(self._glyphs.get(cached.name, config.fallback_icon) if cached else config.fallback_icon)
        return icons, overflow

    def _start_lookup(self):
        if self._lookup_running or not self._requests:
            return
        requests = [(hwnd, self._handle_tokens[hwnd], image) for hwnd, image in list(self._requests.items())[:16]]
        self._lookup_running = True
        self._lookup = _IconLookup(requests)
        self._lookup.signals.loaded.connect(self._icons_loaded)
        QThreadPool.globalInstance().start(self._lookup)

    def _icons_loaded(self, results):
        self._lookup_running = False
        self._lookup = None
        dpi = self.devicePixelRatioF()
        for hwnd, token, name, image_loaded, image in results:
            if self._handle_tokens.get(hwnd) != token:
                continue
            pixmap = None
            if image is not None:
                size = round(self.config.app_icons.size * dpi)
                image = image.resize((size, size), Image.Resampling.LANCZOS).convert("RGBA")
                if self.config.app_icons.monochrome:
                    alpha = image.getchannel("A")
                    image = ImageOps.grayscale(image).convert("RGBA")
                    image.putalpha(alpha)
                qimage = QImage(image.tobytes(), image.width, image.height, QImage.Format.Format_RGBA8888)
                pixmap = QPixmap.fromImage(qimage)
                pixmap.setDevicePixelRatio(dpi)
            self._icon_cache[hwnd] = _WindowIcon(name, image_loaded, pixmap)
        if self._snapshot is not None:
            self._render()

    def _activate(self, device_name, index):
        if self._client is not None and self._snapshot is not None:
            self._client.activate_workspace(device_name, index)

    def showEvent(self, event):
        super().showEvent(event)
        if self._snapshot is not None:
            self._render()

    def wheelEvent(self, event):
        monitors = self._selected_monitors()
        delta = event.angleDelta().y()
        if not self.config.enable_scroll_switching or not monitors or not delta:
            event.ignore()
            return
        # For an all-monitor strip, scroll the monitor under the pointer.
        button = self.childAt(event.position().toPoint())
        while button is not None and not isinstance(button, WorkspaceButton):
            button = button.parentWidget()
        monitor = (
            next((m for m in monitors if m.device_name == button.device_name), None)
            if button
            else self._bar_monitor(monitors)
        ) or monitors[0]
        direction = -1 if (delta > 0) != self.config.reverse_scroll_direction else 1
        self._activate(monitor.device_name, (monitor.active_workspace_index + direction) % len(monitor.workspaces))
        event.accept()
