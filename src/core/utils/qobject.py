"""Lightweight QObject validity check - no heavy dependencies."""

from typing import TypeGuard

import shiboken6
from PySide6.QtCore import QObject


def is_valid_qobject[T](obj: T | None) -> TypeGuard[T]:
    """Check if the object is a valid QObject with specific type."""
    return obj is not None and isinstance(obj, QObject) and shiboken6.isValid(obj)
