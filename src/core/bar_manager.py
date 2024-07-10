import logging
import uuid
from contextlib import suppress
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QScreen
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from core.bar import Bar
from core.utils.widget_builder import WidgetBuilder
from core.utils.utilities import get_screen_by_name
from core.event_service import EventService
from core.config import get_stylesheet, get_config
from copy import deepcopy


class BarManager(QObject):
    styles_modified = pyqtSignal()
    config_modified = pyqtSignal()

    def __init__(self, config: dict, stylesheet: str):
        super().__init__()
        self.config = config
        self.stylesheet = stylesheet
        self.event_service = EventService()
        self.widget_event_listeners = set()
        self.bars: list[Bar] = list()
        self.config['bars'] = {n: bar for n, bar in self.config['bars'].items() if bar['enabled']}
        self._threads = {}
        self._active_listeners = {}
        self._widget_builder = WidgetBuilder(self.config['widgets'])
        self._prev_listeners = set()

        self.styles_modified.connect(self.on_styles_modified)
        self.config_modified.connect(self.on_config_modified)
        QApplication.instance().screenAdded.connect(self.on_screens_update)
        QApplication.instance().screenRemoved.connect(self.on_screens_update)

    @pyqtSlot()
    def on_styles_modified(self):
        stylesheet = get_stylesheet(show_error_dialog=True)

        if stylesheet and (stylesheet != self.stylesheet):
            self.stylesheet = stylesheet
            for bar in self.bars:
                bar.setStyleSheet(self.stylesheet)
            logging.info("Successfully loaded updated stylesheet and applied to all bars.")

    @pyqtSlot()
    def on_config_modified(self):
        config = get_config(show_error_dialog=True)

        if config and (config != self.config):

            if config['bars'] != self.config['bars'] or config['widgets'] != self.config['widgets']:
                self.config = config
                self.close_bars()
                self.initialize_bars()
            else:
                self.config = config

            logging.info("Successfully loaded updated config and re-initialised all bars.")

    @pyqtSlot(QScreen)
    def on_screens_update(self, _screen: QScreen) -> None:
        logging.info("Screens updated. Re-initialising all bars.")
        self.close_bars()
        self.initialize_bars()

    def run_listeners_in_threads(self):
        for listener in self.widget_event_listeners:
            logging.info(f"Starting {listener.__name__}...")
            thread = listener()
            thread.start()
            self._threads[listener] = thread

    def stop_listener_threads(self):
        for listener in self.widget_event_listeners:
            logging.info(f"Stopping {listener.__name__}...")
            with suppress(KeyError):
                self._threads[listener].stop()
                self._threads[listener].quit()
                self._threads[listener].wait(500)
        self._threads.clear()
        self.widget_event_listeners.clear()

    def close_bars(self):
        self.stop_listener_threads()

        for bar in self.bars:
            bar.close()

        self.event_service.clear()
        self.bars.clear()

    def initialize_bars(self, init=False) -> None:
        self._widget_builder = WidgetBuilder(self.config['widgets'])

        for bar_name, bar_config in self.config['bars'].items():

            if bar_config['screens'] == ['*']:
                for screen in QApplication.screens():
                    self.create_bar(bar_config, bar_name, screen, init)
                continue

            for screen_name in bar_config['screens']:
                screen = get_screen_by_name(screen_name)
                if screen:
                    self.create_bar(bar_config, bar_name, screen, init)

        self.run_listeners_in_threads()
        self._widget_builder.raise_alerts_if_errors_present()

    def create_bar(self, config: dict, name: str, screen: QScreen, init=False) -> None:
        screen_name = screen.name().replace('\\', '').replace('.', '')
        bar_id = f"{name}_{screen_name}_{str(uuid.uuid4())[:8]}"
        bar_config = deepcopy(config)
        bar_widgets, widget_event_listeners = self._widget_builder.build_widgets(bar_config.get('widgets', {}))
        bar_options = {
            **bar_config,
            'bar_id': bar_id,
            'bar_name': name,
            'bar_screen': screen,
            'stylesheet': self.stylesheet,
            'widgets': bar_widgets,
            'init': init
        }

        del bar_options['enabled']
        del bar_options['screens']

        self.widget_event_listeners = self.widget_event_listeners.union(widget_event_listeners)
        self.bars.append(Bar(**bar_options))
