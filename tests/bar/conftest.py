from typing import Any

import pytest

from core.bar.appbar import AppBarManager
from core.bar.window import BarWindow
from core.utils.win32 import app_bar


class FakeAppBar:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def create_appbar(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append("create")

    def remove_appbar(self) -> None:
        self.calls.append("remove")


@pytest.fixture
def registered_bars(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    registered: list[int] = []

    def register_bar(self: AppBarManager, hwnd: int, bar: BarWindow) -> None:
        registered.append(hwnd)

    def unregister_bar(self: AppBarManager, hwnd: int) -> None:
        pass

    monkeypatch.setattr(AppBarManager, "register_bar", register_bar)
    monkeypatch.setattr(AppBarManager, "unregister_bar", unregister_bar)
    return registered


@pytest.fixture
def fake_app_bar(monkeypatch: pytest.MonkeyPatch, registered_bars: list[int]) -> None:
    monkeypatch.setattr(app_bar, "Win32AppBar", FakeAppBar)
