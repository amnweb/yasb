import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication

from core.services.theme import mode as mode_module
from core.services.theme.mode import WindowsTheme


class Windows:
    """Stands in for ThemeService, so the tests never change the real Windows theme."""

    mode = "dark"
    written: list[str] = []
    refuse = False

    @classmethod
    def get_theme_mode(cls) -> str:
        return cls.mode

    @classmethod
    def set_theme_mode(cls, mode: str) -> bool:
        if cls.refuse:
            return False
        cls.written.append(mode)
        cls.mode = mode
        return True


@pytest.fixture
def windows(qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch) -> type[Windows]:
    Windows.mode, Windows.written, Windows.refuse = "dark", [], False
    monkeypatch.setattr(mode_module, "ThemeService", Windows)
    return Windows


def test_the_mode_is_read_and_switched(windows: type[Windows]):
    theme = WindowsTheme()
    assert theme.property("dark")
    theme.toggle()
    assert not theme.property("dark")
    theme.setDark(True)
    assert theme.property("dark") and windows.written == ["light", "dark"]


def test_a_refused_switch_keeps_the_mode(windows: type[Windows]):
    windows.refuse = True
    theme = WindowsTheme()
    theme.toggle()
    assert theme.property("dark") and windows.written == []


def test_the_mode_follows_windows(windows: type[Windows]):
    theme = WindowsTheme()
    windows.mode = "light"
    hints = QGuiApplication.styleHints()
    assert hints is not None
    hints.colorSchemeChanged.emit(Qt.ColorScheme.Light)
    assert not theme.property("dark")
