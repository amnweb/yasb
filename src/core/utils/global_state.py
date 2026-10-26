from typing import Any


class GlobalState:
    """Centralized global state for detached widgets and application-wide configurations."""

    _is_dark = False
    _stylesheet: str | None = None
    _tooltip_options: Any = None

    @classmethod
    def is_dark(cls) -> bool:
        return cls._is_dark

    @classmethod
    def set_dark(cls, value: bool):
        cls._is_dark = value

    @classmethod
    def stylesheet(cls) -> str:
        return cls._stylesheet or ""

    @classmethod
    def set_stylesheet(cls, value: str):
        cls._stylesheet = value

    @classmethod
    def tooltip_options(cls) -> Any:
        return cls._tooltip_options

    @classmethod
    def set_tooltip_options(cls, value: Any):
        cls._tooltip_options = value
