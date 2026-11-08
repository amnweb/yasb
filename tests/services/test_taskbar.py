from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from unittest.mock import Mock, call

import pytest
from PyQt6.QtCore import Q_ARG, QMetaObject, QObject, QRectF, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QGuiApplication
from PyQt6.QtQml import QQmlComponent, QQmlEngine, QQmlError, QQmlProperty
from PyQt6.QtQuick import QQuickItem, QQuickWindow

from core.events.service import EventService
from core.events.win32 import WinEvent
from core.qml_types import register_qml_types
from core.services.recycle_bin import recycle_bin_monitor
from core.services.recycle_bin.recycle_bin_monitor import RecycleBinMonitor
from core.services.taskbar import apps as apps_module
from core.services.taskbar import window_manager
from core.services.taskbar.apps import OpenWindows, TaskbarApps
from core.services.taskbar.jump_list import jump_list
from core.services.taskbar.pin_manager import PinManager
from core.services.taskbar.window_manager import TaskbarWindowManager
from core.utils.icons.image_provider import ICON_PROVIDER, IconImageProvider
from core.utils.win32 import event_listener
from core.utils.win32.constants import HSHELL_FLASH, HSHELL_WINDOWCREATED
from core.utils.win32.shell_hook import shell_event
from core.widget_files import BUILTIN_WIDGETS_DIR
from settings import QML_IMPORT_PATH
from tests.support.qt import find_item, wait


def window_data(hwnd: int, title: str, app: str, **state: Any) -> dict[str, Any]:
    """A window as the window manager reports it, with the id of its app in app."""
    return {
        "hwnd": hwnd,
        "title": title,
        "app": app,
        "class_name": state.get("class_name", "Window"),
        "is_active": state.get("is_active", False),
        "is_flashing": state.get("is_flashing", False),
        "is_cloaked": state.get("is_cloaked", False),
        "monitor_handle": state.get("monitor_handle", 1),
        "process_name": state.get("process_name", f"{app}.exe"),
        "process_pid": 1,
        "process_path": f"C:\\{app}.exe",
        "can_minimize": state.get("can_minimize", True),
    }


class Manager(QObject):
    """Stands in for the window manager, so the tests never hook the shell."""

    window_added = pyqtSignal(int, dict)
    window_removed = pyqtSignal(int, dict)
    window_updated = pyqtSignal(int, dict)
    window_monitor_changed = pyqtSignal(int, dict)
    window_minimize_changed = pyqtSignal(int, bool)

    def __init__(self) -> None:
        super().__init__()
        self.windows: dict[int, dict[str, Any]] = {}

    def get_windows(self) -> dict[int, Any]:
        return {hwnd: Tracked(data) for hwnd, data in self.windows.items()}

    def open(self, hwnd: int, title: str, app: str, **state: Any) -> None:
        self.windows[hwnd] = window_data(hwnd, title, app, **state)
        self.window_added.emit(hwnd, self.windows[hwnd])

    def update(self, hwnd: int, **state: Any) -> None:
        data = self.windows[hwnd]
        self.windows[hwnd] = window_data(hwnd, state.pop("title", data["title"]), data["app"], **state)
        self.window_updated.emit(hwnd, self.windows[hwnd])

    def close(self, hwnd: int) -> None:
        self.window_removed.emit(hwnd, self.windows.pop(hwnd))


class Tracked:
    """A window the manager tracks."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data

    def as_dict(self) -> dict[str, Any]:
        return self.data


class Pins(PinManager):
    """Pins kept in memory, identifying a window's app by the app in its data."""

    def __init__(self, pinned: dict[str, str]) -> None:
        super().__init__()
        self.initial = pinned
        self.saves = 0
        self.launched: list[tuple[str, str]] = []

    def load_pinned_apps(self) -> None:
        self.pinned_apps = {uid: {"title": title} for uid, title in self.initial.items()}
        self.pinned_order = list(self.initial)

    def save_pinned_apps(self) -> None:
        self.saves += 1

    @staticmethod
    def get_app_unique_id(hwnd: int, window_data: dict[str, Any]) -> str | None:
        return window_data.get("app")

    def icon_source(self, unique_id: str, metadata: dict[str, str] | None = None) -> None:
        return None

    def pin_app(self, hwnd: int, window_data: dict[str, Any], position: int = -1) -> str | None:
        uid = window_data["app"]
        self.pinned_apps[uid] = {"title": window_data["title"]}
        self.pinned_order.insert(position if position >= 0 else len(self.pinned_order), uid)
        self.save_pinned_apps()
        return uid

    def launch_pinned_app(self, unique_id: str, extra_arguments: str = "") -> None:
        self.launched.append((unique_id, extra_arguments))


@pytest.fixture
def manager(qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch) -> Manager:
    fake = Manager()
    fake.windows[11] = window_data(11, "Inbox - Outlook", "outlook")
    pins = Pins({"terminal": "Terminal", "outlook": "Outlook"})
    monkeypatch.setattr(apps_module, "_shared", OpenWindows(fake, pins))

    def screen_monitor(name: str) -> int | None:
        return {"DISPLAY1": 1, "DISPLAY2": 2}.get(name)

    monkeypatch.setattr(apps_module, "screen_monitor", screen_monitor)
    return fake


def pins() -> Pins:
    pinned = apps_module.open_windows().pins
    assert isinstance(pinned, Pins)
    return pinned


def taskbar(**settings: Any) -> TaskbarApps:
    apps = TaskbarApps()
    for name, value in settings.items():
        apps.setProperty(name, value)
    return apps


def shown(apps: TaskbarApps) -> list[tuple[str, bool, list[int]]]:
    return [(app["id"], app["pinned"], [window["hwnd"] for window in app["windows"]]) for app in apps.property("apps")]


def test_pinned_apps_come_first_holding_their_windows(manager: Manager):
    apps = taskbar()
    manager.open(12, "Downloads", "explorer")
    manager.open(13, "Calendar - Outlook", "outlook")
    assert shown(apps) == [("terminal", True, []), ("outlook", True, [11, 13]), ("explorer", False, [12])]
    outlook = apps.property("apps")[1]
    assert outlook["name"] == "Outlook"
    assert outlook["windows"][0]["title"] == "Inbox - Outlook"
    assert outlook["windows"][0]["icon"].startswith("image://icon/window/11/")


def test_a_closed_window_leaves_its_pinned_app_but_not_an_unpinned_one(manager: Manager):
    apps = taskbar()
    manager.open(12, "Downloads", "explorer")
    manager.close(11)
    manager.close(12)
    assert shown(apps) == [("terminal", True, []), ("outlook", True, [])]


def test_windows_are_left_out_by_the_settings(manager: Manager):
    manager.open(12, "Untitled", "notepad", class_name="Notepad")
    manager.open(13, "Properties", "dialog", can_minimize=False)
    manager.open(14, "Mail", "mail", is_cloaked=True)
    manager.open(15, "Other screen", "paint", monitor_handle=2)
    manager.open(16, "   ", "blank")
    assert [window for _id, _pinned, windows in shown(taskbar()) for window in windows] == [11, 12, 14, 15]
    assert [w for _id, _p, ws in shown(taskbar(strictFiltering=False)) for w in ws] == [11, 12, 13, 14, 15]
    assert [w for _id, _p, ws in shown(taskbar(onlyVisible=True)) for w in ws] == [11, 12, 15]
    assert [w for _id, _p, ws in shown(taskbar(screenName="DISPLAY2")) for w in ws] == [15]
    assert [w for _id, _p, ws in shown(taskbar(ignoreClasses=["Notepad"], ignoreTitles=["Mail"])) for w in ws] == [
        11,
        15,
    ]
    assert [w for _id, _p, ws in shown(taskbar(ignoreProcesses=["paint.exe"])) for w in ws] == [11, 12, 14]


def test_window_state_follows_the_window_manager(manager: Manager):
    apps = taskbar()

    def outlook() -> dict[str, Any]:
        return apps.property("apps")[1]["windows"][0]

    manager.update(11, is_flashing=True)
    assert outlook()["flashing"]
    manager.update(11, is_active=True, title="Sent - Outlook")
    assert outlook()["active"] and not outlook()["flashing"] and outlook()["title"] == "Sent - Outlook"
    manager.window_minimize_changed.emit(11, True)
    assert outlook()["minimized"]
    # A tiling manager can activate a window it just minimized; it stays minimized until restored
    manager.update(11, is_active=True)
    assert outlook()["minimized"]
    manager.window_minimize_changed.emit(11, False)
    assert not outlook()["minimized"]


def test_pins_move_and_change(manager: Manager):
    apps = taskbar()
    manager.open(12, "Downloads", "explorer")
    apps.move("outlook", 0)
    assert [app["id"] for app in apps.property("apps")] == ["outlook", "terminal", "explorer"]
    apps.pin("explorer", 1)
    assert shown(apps) == [("outlook", True, [11]), ("explorer", True, [12]), ("terminal", True, [])]
    apps.unpin("terminal")
    assert shown(apps) == [("outlook", True, [11]), ("explorer", True, [12])]
    assert pins().saves == 3


def test_launching_starts_the_app_by_its_id(manager: Manager):
    apps = taskbar()
    apps.launch("terminal")
    apps.launch("outlook", "/c ipm.note")
    apps.launch("window:99")
    assert pins().launched == [("terminal", ""), ("outlook", "/c ipm.note")]


def test_activating_toggles_a_window(manager: Manager, monkeypatch: pytest.MonkeyPatch):
    calls: list[tuple[str, int]] = []
    iconic: set[int] = set()

    def recorder(name: str) -> Callable[[int], None]:
        def record(hwnd: int) -> None:
            calls.append((name, hwnd))

        return record

    def answer(value: bool) -> Callable[[int], bool]:
        return lambda _hwnd: value

    def is_iconic(hwnd: int) -> bool:
        return hwnd in iconic

    def resolve(hwnd: int) -> tuple[int, int]:
        return hwnd, hwnd

    monkeypatch.setattr(apps_module, "IsWindow", answer(True))
    monkeypatch.setattr(apps_module, "IsIconic", is_iconic)
    monkeypatch.setattr(apps_module, "resolve_base_and_focus", resolve)
    monkeypatch.setattr(apps_module, "is_owner_root_active", answer(False))
    monkeypatch.setattr(apps_module, "window_can_minimize", answer(True))
    for name in ("restore_window", "minimize_window", "show_window", "set_foreground"):
        monkeypatch.setattr(apps_module, name, recorder(name))
    apps = taskbar()
    apps.activate(11)
    assert calls == [("show_window", 11), ("set_foreground", 11)]
    calls.clear()
    manager.update(11, is_active=True)
    apps.activate(11)
    assert calls == [("minimize_window", 11)]
    calls.clear()
    iconic.add(11)
    apps.activate(11)
    assert calls[:2] == [("restore_window", 11), ("set_foreground", 11)]


@pytest.fixture
def quiet_bin(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Recycle Bin monitor without its watch thread, so a test sets what the bin holds."""
    monkeypatch.setattr(RecycleBinMonitor, "_feeds", {})
    monkeypatch.setattr(recycle_bin_monitor, "_Watch", Mock())


def watched_bin() -> RecycleBinMonitor | None:
    return RecycleBinMonitor._feeds.get(None)  # pyright: ignore[reportPrivateUsage]


def test_a_pinned_recycle_bin_shows_whether_it_is_full(
    manager: Manager, monkeypatch: pytest.MonkeyPatch, quiet_bin: None
):
    bin_id = "explorer:::{645FF040-5081-101B-9F08-00AA002F954E}"
    monkeypatch.setattr(apps_module, "_shared", OpenWindows(manager, Pins({bin_id: "Recycle Bin"})))
    apps = taskbar()

    def icon() -> str:
        return apps.property("apps")[0]["icon"]

    monitor = watched_bin()
    assert icon().startswith("image://icon/stock/31/") and monitor is not None
    monitor.info = {"size_bytes": 10, "num_items": 1}
    monitor.changed.emit()
    assert icon().startswith("image://icon/stock/32/")
    apps.unpin(bin_id)
    assert watched_bin() is None


def test_exiting_lets_go_of_the_recycle_bin_monitor(manager: Manager, quiet_bin: None):
    windows = OpenWindows(manager, Pins({"explorer:::{645FF040-5081-101B-9F08-00AA002F954E}": "Recycle Bin"}))
    assert watched_bin() is not None
    windows.stop()
    assert watched_bin() is None


def test_browsers_and_editors_offer_new_windows():
    def offered(app_id: str) -> list[tuple[str, str, str]]:
        return [(item["kind"], item["target"], item["arguments"]) for item in jump_list(app_id)]

    edge = r"path:C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    assert offered(edge) == [("window", edge, ""), ("private", edge, "--inprivate")]
    assert offered("aumid:308046B0AF4A39CB") == [
        ("window", "aumid:308046B0AF4A39CB", ""),
        ("private", "aumid:308046B0AF4A39CB;PrivateBrowsingAUMID", ""),
    ]
    assert offered(r"path:C:\Code\Code.exe") == [("window", r"path:C:\Code\Code.exe", "-n")]
    assert offered(r"path:C:\Windows\System32\mspaint.exe") == []


def test_terminal_profiles_use_configured_icons(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    package = "Microsoft.WindowsTerminalPreview_8wekyb3d8bbwe"
    local_state = tmp_path / "Packages" / package / "LocalState"
    local_state.mkdir(parents=True)
    (local_state / "settings.json").write_text(
        """
        {
            // Terminal allows comments and trailing commas.
            "profiles": {
                "defaults": {"icon": "shell.png"},
                "list": [
                    {"guid": "{1}", "name": "PowerShell // Preview"},
                    {"guid": "{2}", "name": "Ubuntu", "icon": "🐧"},
                    {"guid": "{3}", "name": "CMD", "icon": "ms-appx:///ProfileIcons/cmd.png"},
                    {"guid": "{4}", "name": "Git", "icon": "ms-appdata:///Roaming/git.ico"},
                    {"guid": "{5}", "name": "Hidden", "hidden": true}, // Skip
                ],
            },
        }
        """,
        encoding="utf-8",
    )

    app_id = f"aumid:{package}!App"
    items = jump_list(app_id)
    assert [item["text"] for item in items] == ["PowerShell // Preview", "Ubuntu", "CMD", "Git"]
    assert [item["arguments"] for item in items] == ["-p {1}", "-p {2}", "-p {3}", "-p {4}"]
    assert items[0]["icon"] == QUrl.fromLocalFile(str(local_state / "shell.png")).toString()
    assert items[1]["iconText"] == "🐧"
    assert "icon" not in items[2] and "iconText" not in items[2]
    assert items[3]["icon"] == QUrl.fromLocalFile(str(local_state.with_name("RoamingState") / "git.ico")).toString()


def test_a_menu_names_its_pinned_app(manager: Manager):
    assert taskbar().jumpList("outlook") == {"name": "Outlook", "items": []}


@pytest.fixture
def widget(manager: Manager) -> Iterator[tuple[QQuickItem, list[str]]]:
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    engine.addImageProvider(ICON_PROVIDER, IconImageProvider())
    warnings: list[str] = []

    def collect_warnings(errors: list[QQmlError]) -> None:
        warnings.extend(error.toString() for error in errors)

    engine.warnings.connect(collect_warnings)
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(BUILTIN_WIDGETS_DIR / "Taskbar" / "Taskbar.qml")))
    item = component.create()
    assert isinstance(item, QQuickItem), [error.toString() for error in component.errors()]
    # An item counts as visible only in a window, as on a bar
    host = QQuickWindow()
    item.setParentItem(host.contentItem())
    item.setHeight(32)
    # The tests wait for animations, so they take the same time whatever the widget file sets
    QQmlProperty.write(item, "animationDuration", 200)
    host.show()
    yield item, warnings
    item.setParentItem(None)
    item.deleteLater()
    host.close()
    wait(20)


def named(parent: QQuickItem, name: str) -> list[QQuickItem]:
    found: list[QQuickItem] = []
    for child in parent.childItems():
        if child.objectName() == name:
            found.append(child)
        found.extend(named(child, name))
    return found


def test_the_widget_shows_a_button_per_app_or_per_window(widget: tuple[QQuickItem, list[str]], manager: Manager):
    item, warnings = widget
    buttons = find_item(item, "buttons")
    assert buttons is not None
    manager.open(12, "Calendar - Outlook", "outlook")
    manager.open(13, "Downloads", "explorer", is_active=True)
    wait(50)
    assert buttons.property("count") == 3
    assert [count.isVisible() for count in named(item, "count")] == [False, True, False]
    QQmlProperty.write(item, "grouping", False)
    wait(50)
    assert buttons.property("count") == 4
    assert not warnings, warnings


def test_only_the_flashing_windows_preview_uses_the_attention_color(
    widget: tuple[QQuickItem, list[str]], manager: Manager
) -> None:
    item, warnings = widget
    attention = QColor("#27c189")
    assert QQmlProperty.write(item, "attentionColor", attention)
    attention.setAlphaF(0.28)
    manager.open(12, "Calendar - Outlook", "outlook")
    preview = item.findChild(QQuickWindow, "previewWindow")
    assert preview is not None
    preview.setProperty("previewArea", QRectF(0, 0, 800, 600))
    QMetaObject.invokeMethod(preview, "setCards", Q_ARG("QString", "outlook"))
    content = preview.contentItem()
    assert content is not None
    cards = {card.property("hwnd"): card for card in named(content, "preview")}
    assert set(cards) == {11, 12}

    def color(hwnd: int) -> QColor:
        value = cards[hwnd].childItems()[0].property("color")
        assert isinstance(value, QColor)
        return value

    assert color(11).alpha() == color(12).alpha() == 0
    manager.update(12, is_flashing=True)
    assert color(11).alpha() == 0
    assert color(12).getRgb() == attention.getRgb()
    manager.update(12, is_active=True)
    assert color(12).alpha() == 0
    assert not warnings, warnings


@pytest.mark.parametrize("with_backdrop", [False, True])
def test_peek_keeps_the_preview_and_its_backdrop_after_a_context_menu(
    widget: tuple[QQuickItem, list[str]], monkeypatch: pytest.MonkeyPatch, with_backdrop: bool
) -> None:
    item, warnings = widget
    bar = item.window()
    preview = item.findChild(QQuickWindow, "previewWindow")
    assert bar is not None and preview is not None
    bar_hwnd, preview_hwnd = int(bar.winId()), int(preview.winId())
    assert bar_hwnd != preview_hwnd

    class NativeBackdrop(QObject):
        def __init__(self, window: QQuickWindow, hwnd: int, *, closed: bool = False) -> None:
            super().__init__(window)
            self.hwnd = hwnd
            self.closed = closed

    monkeypatch.setattr(apps_module, "BackdropWindow", NativeBackdrop)
    top_window = preview_hwnd
    kept = [call(preview_hwnd), call(bar_hwnd)]
    if with_backdrop:
        NativeBackdrop(preview, 100, closed=True)
        preview_blur = NativeBackdrop(preview, 101)
        bar_blur = NativeBackdrop(bar, 102)
        top_window = preview_blur.hwnd
        kept = [call(preview_hwnd), call(preview_blur.hwnd), call(bar_hwnd), call(bar_blur.hwnd)]

    activate = Mock(return_value=True)
    exclude = Mock(return_value=True)
    monkeypatch.setattr(apps_module, "activate_live_preview", activate)
    monkeypatch.setattr(apps_module, "exclude_from_peek", exclude)
    QMetaObject.invokeMethod(preview, "setPeek", Q_ARG("int", 11))
    QMetaObject.invokeMethod(preview, "stopPeek")

    buttons = find_item(item, "buttons")
    assert buttons is not None
    button = next(child for child in buttons.childItems() if child.property("key") == "outlook")
    existing = QGuiApplication.topLevelWindows()
    QMetaObject.invokeMethod(item, "openMenu", Q_ARG("QQuickItem*", button))
    menu = next(window for window in QGuiApplication.topLevelWindows() if window not in existing)
    menu.close()
    wait(20)

    QMetaObject.invokeMethod(preview, "setPeek", Q_ARG("int", 11))
    QMetaObject.invokeMethod(preview, "stopPeek")
    assert activate.call_args_list == [call(True, 11, top_window), call(False, 0, top_window)] * 2
    assert exclude.call_args_list == kept * 2
    assert not warnings, warnings


@pytest.mark.parametrize("action", ["launch", "emptyBin"])
def test_the_recycle_bin_menu_runs_its_action_after_the_trigger_handler(
    widget: tuple[QQuickItem, list[str]],
    manager: Manager,
    monkeypatch: pytest.MonkeyPatch,
    action: str,
    quiet_bin: None,
) -> None:
    item, warnings = widget
    emptied: list[bool] = []
    monkeypatch.setattr(apps_module, "empty_recycle_bin", lambda: emptied.append(True))
    bin_id = "explorer:::{645FF040-5081-101B-9F08-00AA002F954E}"
    manager.open(12, "Recycle Bin", bin_id)
    apps_module.open_windows().pin(bin_id)
    monitor = watched_bin()
    assert monitor is not None
    monitor.info = {"size_bytes": 10, "num_items": 1}
    manager.close(12)
    wait(50)

    buttons = find_item(item, "buttons")
    assert buttons is not None
    button = next(child for child in buttons.childItems() if child.property("app") and child.property("key") == bin_id)
    existing = QGuiApplication.topLevelWindows()
    QMetaObject.invokeMethod(item, "openMenu", Q_ARG("QQuickItem*", button))
    menu = next(window for window in QGuiApplication.topLevelWindows() if window not in existing)
    assert isinstance(menu, QQuickWindow)

    def menu_items(root: QQuickItem) -> Iterator[QQuickItem]:
        for child in root.childItems():
            if child.property("entry") is not None:
                yield child
            else:
                yield from menu_items(child)

    label = "Empty Recycle Bin" if action == "emptyBin" else "Recycle Bin"
    content = menu.contentItem()
    assert content is not None
    entry = next(child for child in menu_items(content) if child.property("text") == label)
    QMetaObject.invokeMethod(entry, "triggered")
    assert not pins().launched and not emptied

    menu.close()
    wait(20)
    assert pins().launched == ([(bin_id, "")] if action == "launch" else [])
    assert emptied == ([True] if action == "emptyBin" else [])
    assert not warnings, warnings


def test_the_window_manager_hears_the_shell_and_win_events_only_while_it_runs(
    qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    def nothing(_manager: TaskbarWindowManager) -> None:
        pass

    # The shared WinEvent thread and the windows already open stay out of the test
    monkeypatch.setattr(event_listener, "ensure_system_event_listener", lambda: None)
    monkeypatch.setattr(TaskbarWindowManager, "_enumerate_existing_windows", nothing)
    manager = TaskbarWindowManager()
    created: list[int] = []
    flashing: list[int] = []
    cloaked: list[int] = []
    minimized: list[tuple[int, bool]] = []
    monkeypatch.setattr(manager, "_on_window_created", created.append)
    monkeypatch.setattr(manager, "_on_window_flash", flashing.append)
    monkeypatch.setattr(manager, "_on_window_cloaked", cloaked.append)

    def minimize(hwnd: int, state: bool) -> None:
        minimized.append((hwnd, state))

    monkeypatch.setattr(manager, "_on_window_minimized", minimize)

    def win(event: WinEvent, hwnd: int) -> None:
        EventService().emit_event(event, hwnd, event)

    manager.start()
    shell_event(HSHELL_WINDOWCREATED).emit(5)
    shell_event(HSHELL_FLASH).emit(6)
    win(WinEvent.EventObjectCloaked, 7)
    win(WinEvent.EventSystemMinimizeStart, 8)
    wait(100)
    assert (created, flashing, cloaked, minimized) == ([5], [6], [7], [(8, True)])

    # Stopping on quit uses the signals it kept: asking the shared hooks again could start the WinEvent thread
    def no_hooks(_event: object) -> None:
        raise AssertionError("stop asked a shared hook again")

    with monkeypatch.context() as stopping:
        stopping.setattr(window_manager, "win_event", no_hooks)
        stopping.setattr(window_manager, "shell_event", no_hooks)
        manager.stop()
    shell_event(HSHELL_WINDOWCREATED).emit(9)
    win(WinEvent.EventObjectCloaked, 9)
    wait(100)
    assert created == [5] and cloaked == [7] and not manager.is_initialized()
    assert "Error" not in caplog.text


def test_two_taskbars_share_one_window_manager(qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch):
    def nothing(_manager: TaskbarWindowManager) -> None:
        pass

    monkeypatch.setattr(event_listener, "ensure_system_event_listener", lambda: None)
    monkeypatch.setattr(TaskbarWindowManager, "_enumerate_existing_windows", nothing)
    monkeypatch.setattr(window_manager, "_shared_task_manager", None)
    first, second = window_manager.start_shared_task_manager(), window_manager.start_shared_task_manager()
    try:
        assert first is second
        # Connected once: ten shell messages and six WinEvents
        shell, win = first._shell_connections, first._win_signals  # pyright: ignore[reportPrivateUsage]
        assert (len(shell), len(win)) == (10, 6)
    finally:
        first.stop()
