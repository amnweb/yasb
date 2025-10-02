import functools
import logging
from threading import RLock
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

from core.event_enums import Event
from settings import DEBUG


@functools.lru_cache()
class EventService(QObject):
    def __init__(self) -> None:
        super().__init__()
        self._registered_event_signals: dict[Event, list[pyqtSignal]] = {}
        self._mutex = RLock()
        self._is_shutdown: bool = False

    def register_event(self, event_type: Event, event_signal: pyqtSignal):
        with self._mutex:
            if event_type not in self._registered_event_signals:
                self._registered_event_signals[event_type] = [event_signal]
            else:
                self._registered_event_signals[event_type].append(event_signal)

    def unregister_event(self, event_type: Event, event_signal: pyqtSignal):
        """
        Remove a previously registered signal for an event type.
        Safe to call multiple times; ignores missing entries.
        """
        with self._mutex:
            signals = self._registered_event_signals.get(event_type)
            if not signals:
                return
            try:
                while event_signal in signals:
                    signals.remove(event_signal)
            except ValueError:
                pass
            # Clean up empty lists to avoid growing the dict
            if not signals:
                self._registered_event_signals.pop(event_type, None)

    def emit_event(self, event_type: Event, *args: Any):
        if self._is_shutdown:
            return
        with self._mutex:
            event_signals = self._registered_event_signals.get(event_type, [])
            # Iterate over a shallow copy so we can modify the original list safely
            for event_signal in list(event_signals):
                try:
                    event_signal.emit(*args)
                except Exception:
                    if DEBUG:
                        logging.debug(f"Failed to emit signal {event_signal.__str__()}. Removing link to {event_type}.")
                    with self._mutex:
                        if event_signal in event_signals:
                            event_signals.remove(event_signal)

    def clear(self):
        with self._mutex:
            self._registered_event_signals.clear()

    def shutdown(self):
        """Suppress future emits and clear registry during application shutdown."""
        with self._mutex:
            self._is_shutdown = True
            self._registered_event_signals.clear()
