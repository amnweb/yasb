from collections.abc import Iterator
from typing import Any, cast

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtQml import QJSValue
from PyQt6.QtQuick import QQuickItem

from core.bar.window import BarWindow
from core.events.service import EventService
from core.utils.hotkey import Hotkey
from core.utils.win32.hotkeys import HotkeyBinding, HotkeyDispatcher, HotkeyListener, parse_hotkey


def _plain(value: Any) -> Any:
    return value.toVariant() if isinstance(value, QJSValue) else value


def widget_items(root: QQuickItem) -> Iterator[tuple[str, QObject]]:
    """Name and item of every widget the bar has loaded, found through the slot Loaders' model data.
    Repeater delegates are visual children only, so the item tree is walked rather than findChildren."""
    for child in root.childItems():
        model: Any = _plain(child.property("modelData"))
        item = child.property("item")
        if isinstance(model, dict) and isinstance(item, QObject):
            yield str(cast(dict[str, Any], model).get("name", "")), item
        else:
            yield from widget_items(child)


def widget_hotkeys(root: QQuickItem) -> Iterator[Hotkey]:
    for _, item in widget_items(root):
        yield from item.findChildren(Hotkey)


class WidgetHotkeys(QObject):
    """Registers the Hotkey elements widgets declare and activates those in the bar of the targeted screen."""

    _hotkey = pyqtSignal(str, str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._bars: list[BarWindow] = []
        self._dispatcher = HotkeyDispatcher()
        self._listener: HotkeyListener | None = None
        self._hotkey.connect(self._run)
        EventService().register_event("handle_widget_hotkey", self._hotkey)

    def bindings(self, bars: list[BarWindow]) -> list[HotkeyBinding]:
        bindings: dict[tuple[int, int], HotkeyBinding] = {}
        for bar in bars:
            if bar.item is None:
                continue
            for hotkey in widget_hotkeys(bar.item):
                keys = str(hotkey.property("keys"))
                parsed = parse_hotkey(keys)
                if parsed is not None and parsed not in bindings:
                    modifiers, vk = parsed
                    bindings[parsed] = HotkeyBinding(keys, vk, modifiers, str(hotkey.property("screen")))
        return list(bindings.values())

    def restart(self, bars: list[BarWindow]) -> None:
        self.stop()
        self._bars = bars
        if bindings := self.bindings(bars):
            self._listener = HotkeyListener(bindings, self._dispatcher, {bar.target_screen.name() for bar in bars})
            self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener.wait(1000)
            self._listener = None

    def _run(self, keys: str, screen_name: str) -> None:
        pressed = parse_hotkey(keys)
        for bar in self._bars:
            if bar.item is None or bar.target_screen.name() != screen_name:
                continue
            for hotkey in widget_hotkeys(bar.item):
                if parse_hotkey(str(hotkey.property("keys"))) == pressed:
                    hotkey.activated.emit()
