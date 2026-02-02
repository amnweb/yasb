import logging
import uuid
from contextlib import suppress
from copy import deepcopy

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QScreen
from PyQt6.QtWidgets import QApplication

from core.bar import Bar
from core.config import get_config, get_stylesheet
from core.event_service import EventService
from core.global_state import set_bar_screens
from core.utils.controller import reload_application
from core.utils.utilities import get_screen_by_name
from core.utils.widget_builder import WidgetBuilder
from core.utils.win32.hotkeys import (
    HotkeyBinding,
    HotkeyDispatcher,
    HotkeyListener,
    collect_widget_keybindings,
)


class BarManager(QObject):
    styles_modified = pyqtSignal()
    config_modified = pyqtSignal()

    def __init__(self, config: dict, stylesheet: str):
        super().__init__()
        self.config = config
        self.stylesheet = stylesheet
        self.event_service = EventService()
        self.widget_event_listeners = set()
        self.bars: list[Bar] = []
        self.config["bars"] = {n: bar for n, bar in self.config["bars"].items() if bar["enabled"]}
        self._threads = {}
        self._active_listeners = {}
        self._widget_builder = WidgetBuilder(self.config["widgets"])
        self._prev_listeners = set()
        self._hotkey_listener: HotkeyListener | None = None
        self._hotkey_dispatcher: HotkeyDispatcher | None = None
        self._collected_keybindings: list[HotkeyBinding] = []
        self._bar_id_to_screen: dict[str, str] = {}

        self.styles_modified.connect(self.on_styles_modified)
        self.config_modified.connect(self.on_config_modified)
        app = QApplication.instance()
        app.screenAdded.connect(self.on_screens_update)
        app.screenRemoved.connect(self.on_screens_update)
        app.aboutToQuit.connect(self.stop_listener_threads)

    @pyqtSlot()
    def on_styles_modified(self):
        stylesheet = get_stylesheet(show_error_dialog=True)
        if stylesheet and (stylesheet != self.stylesheet):
            self.stylesheet = stylesheet
            for bar in self.bars:
                bar.setStyleSheet(self.stylesheet)

    @pyqtSlot()
    def on_config_modified(self):
        try:
            config = get_config(show_error_dialog=True)
        except Exception as e:
            logging.error(f"Error loading config: {e}")
            return
        if config and (config != self.config):
            if any(
                config[key] != self.config[key]
                for key in [
                    "bars",
                    "widgets",
                    "komorebi",
                    "glazewm",
                    "show_systray",
                    "debug",
                    "env_file",
                    "update_check",
                ]
            ):
                self.config = config
                reload_application("Reloading Application because of config change.")
            else:
                self.config = config
            logging.info("Successfully loaded updated config and re-initialised all bars.")

    @pyqtSlot(QScreen)
    def on_screens_update(self, _screen: QScreen) -> None:
        logging.info("Screens updated. Re-initialising all bars.")
        reload_application("Reloading Application because of screen update.")

    def run_listeners_in_threads(self):
        for listener in self.widget_event_listeners:
            logging.info(f"Starting {listener.__name__}...")
            thread = listener()
            thread.start()
            self._threads[listener] = thread

    def stop_listener_threads(self):
        # Stop hotkey listener first
        if self._hotkey_listener is not None:
            logging.info("Stopping HotkeyListener...")
            with suppress(Exception):
                self._hotkey_listener.stop()
                self._hotkey_listener.quit()
            self._hotkey_listener = None
            self._hotkey_dispatcher = None

        for listener in self.widget_event_listeners:
            logging.info(f"Stopping {listener.__name__}...")
            with suppress(KeyError):
                thread = self._threads[listener]
                if hasattr(thread, "stop"):
                    try:
                        thread.stop()
                    except Exception as e:
                        logging.debug(f"Thread stop() raised for {listener.__name__}: {e}")
                if hasattr(thread, "quit"):
                    try:
                        thread.quit()
                    except Exception:
                        pass
        self._threads.clear()
        self.widget_event_listeners.clear()

    def initialize_bars(self, init=False) -> None:
        self._widget_builder = WidgetBuilder(self.config["widgets"])
        primary_screen = QApplication.primaryScreen()
        primary_screen_name = primary_screen.name() if primary_screen else None

        available_screens = QApplication.screens()
        available_screen_names = [screen.name() for screen in available_screens]

        # Collect explicitly assigned screens
        assigned_screens = set()
        for bar_config in self.config["bars"].values():
            if bar_config["screens"] != ["*"] and bar_config["screens"] != ["**"]:
                for screen in bar_config["screens"]:
                    resolved_name = primary_screen_name if screen == "primary" else screen
                    if resolved_name not in available_screen_names:
                        logging.warning(f"Screen '{resolved_name}' from config not found among connected screens.")
                        continue
                    assigned_screens.add(resolved_name)

        # Create bars
        initialized_screens = set()
        for bar_name, bar_config in self.config["bars"].items():
            if bar_config["screens"] == ["*"]:
                for screen in available_screens:
                    if screen.name() in assigned_screens:
                        continue
                    self.create_bar(bar_config, bar_name, screen, init)
                    initialized_screens.add(screen.name())
            elif bar_config["screens"] == ["**"]:
                for screen in available_screens:
                    self.create_bar(bar_config, bar_name, screen, init)
                    initialized_screens.add(screen.name())
            else:
                for screen_name in bar_config["screens"]:
                    resolved_name = primary_screen_name if screen_name == "primary" else screen_name
                    if resolved_name not in available_screen_names:
                        logging.warning(f"Screen '{resolved_name}' from config not found among connected screens.")
                        continue
                    screen = get_screen_by_name(resolved_name)
                    if screen:
                        self.create_bar(bar_config, bar_name, screen, init)
                        initialized_screens.add(screen.name())

        set_bar_screens(initialized_screens)
        self._collect_keybindings()
        self._start_hotkey_listener()
        self.run_listeners_in_threads()
        self._widget_builder.raise_alerts_if_errors_present()

    def _collect_keybindings(self) -> None:
        """Collect keybindings from all widget configurations."""
        self._collected_keybindings.clear()
        seen_hotkeys: dict[str, str] = {}

        for widget_name, widget_config in self.config["widgets"].items():
            options = widget_config.get("options", {})
            keybindings = options.get("keybindings", [])

            if not keybindings:
                continue

            bindings = collect_widget_keybindings(widget_name, keybindings)

            for binding in bindings:
                # Check for conflicts
                hotkey_lower = binding.hotkey.lower()
                if hotkey_lower in seen_hotkeys:
                    existing_widget = seen_hotkeys[hotkey_lower]
                    logging.warning(
                        f"Hotkey conflict: '{binding.hotkey}' is already assigned to '{existing_widget}', "
                        f"overriding with '{widget_name}'"
                    )
                seen_hotkeys[hotkey_lower] = widget_name
                self._collected_keybindings.append(binding)

    def _start_hotkey_listener(self) -> None:
        """Start the hotkey listener if keybindings are configured."""
        if not self._collected_keybindings:
            return

        self._hotkey_dispatcher = HotkeyDispatcher()
        self._hotkey_listener = HotkeyListener(
            self._collected_keybindings,
            self._hotkey_dispatcher,
            self._bar_id_to_screen,
        )
        self._hotkey_listener.start()
        logging.info("Starting HotkeyListener...")

    def create_bar(self, config: dict, name: str, screen: QScreen, init=False) -> None:
        screen_name = screen.name().replace("\\", "").replace(".", "")
        bar_id = f"{name}_{screen_name}_{str(uuid.uuid4())[:8]}"
        self._bar_id_to_screen[bar_id] = screen.name()  # Store mapping for hotkey dispatch
        bar_config = deepcopy(config)
        bar_widgets, widget_event_listeners = self._widget_builder.build_widgets(bar_config.get("widgets", {}))
        bar_options = {
            **bar_config,
            "bar_id": bar_id,
            "bar_name": name,
            "bar_screen": screen,
            "stylesheet": self.stylesheet,
            "widgets": bar_widgets,
            "widget_config": bar_config.get("widgets", {}),
            "init": init,
        }

        del bar_options["enabled"]
        del bar_options["screens"]

        self.widget_event_listeners = self.widget_event_listeners.union(widget_event_listeners)
        self.bars.append(Bar(**bar_options))
