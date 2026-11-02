from contextlib import nullcontext

import pytest

from core.utils import windhawk_dock as dock


@pytest.fixture
def registry(monkeypatch):
    values = {
        "mod": {"Disabled": 0, "SettingsChangeTime": 100},
        "settings": {"IconSize": 32, "IconSizeSmall": 32, "TaskbarHeight": 48, "TaskbarButtonWidth": 44},
    }
    monkeypatch.setattr(
        dock.winreg, "OpenKey", lambda root, path, *args: nullcontext("settings" if path == "Settings" else "mod")
    )
    monkeypatch.setattr(dock.winreg, "QueryValueEx", lambda key, name: (values[key][name], dock.winreg.REG_DWORD))
    monkeypatch.setattr(
        dock.winreg, "SetValueEx", lambda key, name, unused, kind, value: values[key].update({name: value})
    )
    return values


def test_elevated_write_changes_only_icon_sizes_and_notifies_windhawk(registry):
    dock.write_sizes(36, (32, 32))
    assert registry["settings"] == {"IconSize": 36, "IconSizeSmall": 36, "TaskbarHeight": 48, "TaskbarButtonWidth": 44}
    assert registry["mod"]["SettingsChangeTime"] > 100


def test_write_failure_restores_previous_sizes(registry, monkeypatch):
    original = dock.winreg.SetValueEx

    def fail_small(key, name, unused, kind, value):
        if name == "IconSizeSmall" and value == 36:
            raise OSError("simulated failure")
        original(key, name, unused, kind, value)

    monkeypatch.setattr(dock.winreg, "SetValueEx", fail_small)
    with pytest.raises(OSError, match="simulated"):
        dock.write_sizes(36, (32, 32))
    assert dock.read_sizes() == (32, 32)
    assert registry["mod"]["SettingsChangeTime"] == 100


def test_external_edit_rejected_in_elevated_helper(registry):
    registry["settings"]["IconSize"] = 28
    with pytest.raises(ValueError, match="elsewhere"):
        dock.write_sizes(36, (32, 32))
    assert dock.read_sizes() == (28, 32)


def test_save_skips_unchanged_and_preserves_state_after_cancel(registry, monkeypatch):
    settings = dock.DockIconSettings()
    calls = []

    def cancelled(size, expected):
        calls.append((size, expected))
        raise OSError("approval cancelled")

    monkeypatch.setattr(dock, "_run_elevated", cancelled)
    assert settings.save(32) is False
    with pytest.raises(OSError, match="cancelled"):
        settings.save(36)
    assert calls == [(36, (32, 32))]
    assert settings.original == dock.read_sizes() == (32, 32)


@pytest.mark.parametrize("size", [0, 15, 41, 1000])
def test_size_range_checked_before_write(registry, size):
    with pytest.raises(ValueError, match="between"):
        dock.write_sizes(size, (32, 32))
    assert dock.read_sizes() == (32, 32)
