from threading import Lock
from typing import Any

import shiboken6
from PySide6.QtCore import QObject


class Singleton(type):
    """Singleton metaclass for regular python classes"""

    _instances: dict[Any, Any] = {}
    _lock = Lock()

    def __call__(cls, *args: Any, **kwargs: Any):
        with cls._lock:
            if cls not in cls._instances:
                cls._instances[cls] = super().__call__(*args, **kwargs)
            return cls._instances[cls]


class QSingleton(type(QObject)):
    """Singleton metaclass for Qt classes"""

    _instances: dict[Any, Any] = {}
    _lock = Lock()

    def __call__(cls, *args: Any, **kwargs: Any):
        with cls._lock:
            if cls not in cls._instances or not shiboken6.isValid(cls._instances[cls]):
                cls._instances[cls] = super().__call__(*args, **kwargs)
            return cls._instances[cls]
