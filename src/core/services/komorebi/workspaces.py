import logging
from typing import Any

from PyQt6.QtCore import QCoreApplication, QObject, QTimer, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QGuiApplication

from core.services.komorebi.client import KomorebiClient, KomorebiNode, as_list, as_node
from core.services.komorebi.event_listener import KomorebiEventListener
from core.utils.icons.image_provider import window_icon_url
from core.utils.icons.service import IconService
from core.utils.qml import qml_property
from core.utils.win32.bindings.user32 import get_window_thread_process_id
from core.utils.win32.utils import screen_monitor
from core.utils.worker import run_in_worker

logger = logging.getLogger("komorebi_workspaces")


class _WorkspaceFeed(QObject):
    """The one komorebi subscription every workspace widget shares, running while at least one exists."""

    changed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.client = KomorebiClient()
        self.state: KomorebiNode | None = None
        self._listener: KomorebiEventListener | None = None
        self._users = 0
        self._stopping = False
        self._closed = False
        self._focus_pending: tuple[int, int] | None = None
        self._focusing = False
        # A burst of events is published once
        self._publish = QTimer(self)
        self._publish.setSingleShot(True)
        self._publish.setInterval(0)
        self._publish.timeout.connect(self.changed.emit)

    def acquire(self) -> None:
        self._users += 1
        self._start()

    @pyqtSlot()
    def release(self) -> None:
        self._users -= 1
        if self._users == 0:
            self._stop()

    def _start(self) -> None:
        # A listener that is still stopping starts again from _finished
        if self._listener is not None or not self._users or self._closed:
            return
        listener = KomorebiEventListener()
        listener.state_changed.connect(self._receive)
        listener.finished.connect(self._finished)
        self._listener = listener
        self._stopping = False
        listener.start()

    @pyqtSlot(object)
    def _receive(self, state: object) -> None:
        if self._stopping:
            return
        snapshot = as_node(state)
        monitors = as_node(snapshot.get("monitors")) if snapshot is not None else None
        elements = as_list(monitors.get("elements")) if monitors is not None else None
        if state is not None and elements is None:
            return
        self.state = snapshot
        if snapshot is None:
            self._focus_pending = None
        if not self._publish.isActive():
            self._publish.start()

    def _stop(self) -> None:
        self.state = None
        self._focus_pending = None
        self._publish.stop()
        if self._listener is not None and not self._stopping:
            self._stopping = True
            self._listener.stop()

    @pyqtSlot()
    def _finished(self) -> None:
        listener, self._listener = self._listener, None
        if listener is not None:
            listener.deleteLater()
        self._start()

    @pyqtSlot()
    def close(self) -> None:
        self._closed = True
        self._stop()
        if self._listener is not None:
            # stop() ends the listener's wait on the pipe, and every komorebic call it makes has a timeout
            self._listener.wait(2000)

    def focus(self, monitor: int, workspace: int) -> None:
        # One komorebic runs at a time and only the last workspace asked for waits its turn, so fast scrolling
        # doesn't pile up processes
        self._focus_pending = (monitor, workspace)
        self._send_focus()

    def _send_focus(self) -> None:
        if self._focusing or self._focus_pending is None:
            return
        monitor, workspace = self._focus_pending
        self._focus_pending = None
        self._focusing = True
        run_in_worker(
            lambda: self.client.activate_workspace(monitor, workspace, wait=True),
            self._focus_finished,
            "Could not switch komorebi workspaces.",
        )

    def _focus_finished(self, _result: object, _error: str) -> None:
        self._focusing = False
        self._send_focus()


_feed: _WorkspaceFeed | None = None


def workspace_feed() -> _WorkspaceFeed:
    global _feed
    if _feed is None:
        _feed = _WorkspaceFeed()
        if (app := QCoreApplication.instance()) is not None:
            app.aboutToQuit.connect(_feed.close)
    return _feed


def _layout(workspace: KomorebiNode) -> str:
    layout = as_node(workspace.get("layout"))
    if layout is None:
        return ""
    default = layout.get("Default")
    return default if isinstance(default, str) else next(iter(layout), "")


def _setting(kind: type | str, name: str, notify: pyqtSignal) -> pyqtProperty[Any]:
    def get(model: KomorebiWorkspacesModel) -> Any:
        return model.setting(name)

    def set_value(model: KomorebiWorkspacesModel, value: Any) -> None:
        model.change_setting(name, value)

    return pyqtProperty(kind, get, set_value, notify=notify)


class KomorebiWorkspacesModel(QObject):
    """The workspaces komorebi has on one bar's monitor, in komorebi's order, and switching between them.

    Every widget shares one subscription to komorebi, which runs while at least one widget exists.
    """

    dataChanged = pyqtSignal()
    settingsChanged = pyqtSignal()

    # The bar's screen, by its name; the primary screen when empty
    screenName = _setting(str, "screenName", settingsChanged)
    # Which workspaces list the icons of their windows:
    # {enabledPopulated, enabledActive, maxIcons, hideDuplicates, hideFloating}
    appIcons = _setting("QVariantMap", "appIcons", settingsChanged)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings: dict[str, Any] = {"screenName": "", "appIcons": {}}
        self._connected: bool = False
        self._monitor_index: int = -1
        self._float_override: bool = False
        self._paused: bool = False
        self._workspaces: list[dict[str, Any]] = []
        self._feed = workspace_feed()
        self._feed.changed.connect(self._publish)
        self.destroyed.connect(self._feed.release)
        IconService.instance().icons_changed.connect(self._on_icons_changed)
        self._feed.acquire()
        self._publish()

    def setting(self, name: str) -> Any:
        return self._settings[name]

    def change_setting(self, name: str, value: Any) -> None:
        if self._settings[name] == value:
            return
        self._settings[name] = value
        self.settingsChanged.emit()
        self._publish()

    # Whether komorebi is running and YASB gets its events
    @qml_property(bool, notify=dataChanged)
    def connected(self) -> bool:
        return self._connected

    # Komorebi's index of this bar's monitor, from 0, or -1 when komorebi doesn't manage it
    @qml_property(int, notify=dataChanged)
    def monitorIndex(self) -> int:
        return self._monitor_index

    # Whether new windows float while komorebi's float override is on
    @qml_property(bool, notify=dataChanged)
    def floatOverride(self) -> bool:
        return self._float_override

    # Whether komorebi is paused and leaves windows alone
    @qml_property(bool, notify=dataChanged)
    def paused(self) -> bool:
        return self._paused

    # Each workspace on the monitor in komorebi's order: {index, name, active, focused, populated, windowCount,
    # layout, layer, tile, monocle, maximized, icons}. index counts from 0 and name is empty when komorebi has none.
    # active is the workspace the monitor shows, and focused also needs the monitor to have komorebi's focus.
    # layout is komorebi's name for it, such as BSP or VerticalStack, or Custom; layer is Tiling or Floating,
    # tile is false while the workspace doesn't tile, and monocle and maximized say whether it has a monocle
    # container or a maximized window. icons is [{hwnd, title, source}] as appIcons chooses, source an image URL
    @qml_property("QVariantList", notify=dataChanged)
    def workspaces(self) -> list[dict[str, Any]]:
        return self._workspaces

    @pyqtSlot()
    def _publish(self) -> None:
        state = self._feed.state
        monitor = self._monitor(state) if state is not None else None
        workspaces: list[dict[str, Any]] = []
        if state is not None and monitor is not None:
            try:
                workspaces = self._read_workspaces(state, monitor)
            except KeyError, TypeError, AttributeError:
                logger.debug("Komorebi sent a state YASB could not read", exc_info=True)

        current = (
            state is not None,
            monitor["index"] if monitor is not None else -1,
            bool(state and state.get("float_override")),
            bool(state and state.get("is_paused")),
            workspaces,
        )
        if current != (self._connected, self._monitor_index, self._float_override, self._paused, self._workspaces):
            self._connected, self._monitor_index, self._float_override, self._paused, self._workspaces = current
            self.dataChanged.emit()

    def _monitor(self, state: KomorebiNode) -> KomorebiNode | None:
        name = self.setting("screenName")
        if not name and (screen := QGuiApplication.primaryScreen()) is not None:
            name = screen.name()
        handle = screen_monitor(name)
        return self._feed.client.get_screen_by_hwnd(state, handle) if handle is not None else None

    def _read_workspaces(self, state: KomorebiNode, monitor: KomorebiNode) -> list[dict[str, Any]]:
        client = self._feed.client
        active = client.get_focused_workspace(monitor)
        active_index = active["index"] if active is not None else -1
        focused_monitor = (as_node(state.get("monitors")) or {}).get("focused")
        workspaces: list[dict[str, Any]] = []
        for workspace in client.get_workspaces(monitor):
            windows = self._windows(workspace)
            is_active = workspace["index"] == active_index
            workspaces.append(
                {
                    "index": workspace["index"],
                    "name": workspace.get("name") or "",
                    "active": is_active,
                    "focused": is_active and focused_monitor == monitor["index"],
                    "populated": bool(windows),
                    "windowCount": len(windows),
                    "layout": _layout(workspace),
                    "layer": workspace.get("layer") or "",
                    "tile": bool(workspace.get("tile", True)),
                    "monocle": as_node(workspace.get("monocle_container")) is not None,
                    "maximized": as_node(workspace.get("maximized_window")) is not None,
                    "icons": self._icons(windows, is_active),
                }
            )
        return workspaces

    def _windows(self, workspace: KomorebiNode) -> list[tuple[KomorebiNode, bool]]:
        """Each window on the workspace with whether it floats: tiled, monocle, maximized and floating ones."""
        client = self._feed.client
        windows = [
            (window, False)
            for container in client.get_containers(workspace)
            for window in client.get_windows(container)
        ]
        if (maximized := as_node(workspace.get("maximized_window"))) is not None:
            windows.append((maximized, False))
        windows.extend((window, True) for window in client.get_floating_windows(workspace))
        unique: list[tuple[KomorebiNode, bool]] = []
        handles: set[int] = set()
        for window, floating in windows:
            hwnd = window.get("hwnd")
            if isinstance(hwnd, int) and hwnd and hwnd not in handles:
                handles.add(hwnd)
                unique.append((window, floating))
        return unique

    def _icons(self, windows: list[tuple[KomorebiNode, bool]], active: bool) -> list[dict[str, Any]]:
        options = self.setting("appIcons")
        if not options.get("enabledActive" if active else "enabledPopulated", False):
            return []
        icons: list[dict[str, Any]] = []
        pids: set[int] = set()
        maximum = max(0, options.get("maxIcons", 0))
        # IconService's revision, not one of the model's own: QML keeps an image by its URL, so a model made later
        # starting again from 0 would be handed the blank image shown while the icon was still loading
        revision = IconService.instance().revision
        for window, floating in windows:
            if floating and options.get("hideFloating"):
                continue
            hwnd: int = window["hwnd"]
            if options.get("hideDuplicates"):
                _, pid = get_window_thread_process_id(hwnd)
                if pid and pid in pids:
                    continue
                if pid:
                    pids.add(pid)
            icons.append(
                {
                    "hwnd": hwnd,
                    "title": window.get("title") or window.get("exe") or "",
                    "source": window_icon_url(hwnd, revision),
                }
            )
            if maximum and len(icons) >= maximum:
                break
        return icons

    @pyqtSlot()
    def _on_icons_changed(self) -> None:
        options = self.setting("appIcons")
        if options.get("enabledActive") or options.get("enabledPopulated"):
            self._publish()

    @pyqtSlot(int)
    def activateWorkspace(self, index: int) -> None:
        if self._monitor_index >= 0 and 0 <= index < len(self._workspaces):
            self._feed.focus(self._monitor_index, index)

    # Scrolling up, a positive delta, goes to the previous workspace, and down to the next; both wrap around
    @pyqtSlot(int)
    def switchWorkspace(self, delta: int) -> None:
        active = next((workspace["index"] for workspace in self._workspaces if workspace["active"]), -1)
        if delta and active >= 0:
            self.activateWorkspace((active + (-1 if delta > 0 else 1)) % len(self._workspaces))
