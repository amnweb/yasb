import copy

import pytest
import yaml
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QWidget

from core.ui.views.bar_settings import BarSettingsDialog
from core.utils import settings_editor
from core.utils.settings_editor import SettingsDocument


@pytest.fixture
def config_dir(tmp_path):
    config = {
        "custom_top_level": {"preserve": True},
        "bars": {
            "status": {
                "dimensions": {"height": 26},
                "widgets": {"left": ["ceiling"], "center": [], "right": ["clock", "tray"]},
            }
        },
        "widgets": {
            "ceiling": {"type": "yasb.custom.CustomWidget", "options": {"exec_options": {"run_cmd": "private"}}},
            "clock": {"type": "yasb.clock.ClockWidget", "options": {"label": "{%I:%M:%S %p}", "custom": 123}},
            "tray": {"type": "yasb.systray.SystrayWidget", "options": {"icon_size": 16}},
        },
    }
    config["bars"]["secondary"] = copy.deepcopy(config["bars"]["status"])
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    (tmp_path / "styles.css").write_text(
        "* {font-size: 11px;}\n.yasb-bar {background-color: rgba(20,22,27,0.84);}", encoding="utf-8"
    )
    return tmp_path


def test_preserves_custom_settings_and_backs_up(config_dir):
    doc = SettingsDocument(config_dir)
    original_config, original_style = doc.original_config, doc.original_style
    placements = {"left": ["ceiling"], "center": ["clock"], "right": []}
    appearance = dict(doc.appearance(), font_size=14, opacity=50, tray_icon_size=20)
    config, css = doc.render("status", placements, appearance, ("clock", "{%I:%M:%S %p}", "{%I:%M:%S %p}"))
    doc.save(config, css)
    saved = yaml.safe_load(config)
    assert saved["widgets"]["ceiling"] == yaml.safe_load(original_config)["widgets"]["ceiling"]
    assert saved["custom_top_level"] == {"preserve": True}
    assert saved["bars"]["secondary"] == yaml.safe_load(original_config)["bars"]["secondary"]
    assert saved["widgets"]["clock"]["options"]["custom"] == 123
    assert saved["widgets"]["clock"]["options"]["update_interval"] == 1000
    assert saved["widgets"]["tray"]["options"]["icon_size"] == 20
    assert b"font-size: 14px" in css and b"0.50" in css
    assert (config_dir / "config.settings-backup.yaml").read_bytes() == original_config
    assert (config_dir / "styles.settings-backup.css").read_bytes() == original_style
    config, css = doc.render("status", placements, appearance)
    assert css.count(settings_editor.STYLE_START.encode()) == 1


def test_external_edit_is_not_overwritten(config_dir):
    doc = SettingsDocument(config_dir)
    doc.config_path.write_text("external edit", encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        doc.save(b"replacement", b"replacement")
    assert doc.config_path.read_text() == "external edit"
    assert doc.style_path.read_bytes() == doc.original_style


def test_failed_config_write_rolls_back_css(config_dir, monkeypatch):
    doc = SettingsDocument(config_dir)
    original_write = settings_editor.atomic_write

    def fail_config(path, content):
        if path == doc.config_path:
            raise OSError("simulated failure")
        original_write(path, content)

    monkeypatch.setattr(settings_editor, "atomic_write", fail_config)
    with pytest.raises(OSError):
        doc.save(b"new config", b"new CSS")
    assert doc.style_path.read_bytes() == doc.original_style
    assert doc.config_path.read_bytes() == doc.original_config


def test_dialog_saves_edits_across_bars_and_keeps_fixed_height(config_dir, qapp):
    calls = []
    dialog = BarSettingsDialog(config_dir, lambda: calls.append(True), fixed_height=26)
    dialog.bar.setCurrentText("status")
    assert not dialog.height.isEnabled()
    dialog.widgets.item(0, 0).setCheckState(Qt.CheckState.Unchecked)
    dialog.bar.setCurrentText("secondary")
    dialog.bar.setCurrentText("status")
    assert dialog.widgets.item(0, 1).text() == "clock"
    dialog.font_size.setValue(15)
    dialog.opacity.setValue(65)
    dialog.seconds.setChecked(False)
    dialog.seconds.setChecked(True)
    dialog.save()
    saved = yaml.safe_load((config_dir / "config.yaml").read_bytes())
    assert saved["bars"]["status"]["widgets"]["left"] == []
    assert saved["bars"]["secondary"]["widgets"]["left"] == ["ceiling"]
    assert saved["bars"]["status"]["dimensions"]["height"] == 26
    assert saved["widgets"]["clock"]["options"]["label"] == "{%I:%M:%S %p}"
    assert calls == [True]
    dialog.close()


def test_unchanged_clock_keeps_custom_format(config_dir, qapp):
    dialog = BarSettingsDialog(config_dir)
    original = dialog.document.config["widgets"]["clock"]
    dialog.save()
    assert yaml.safe_load((config_dir / "config.yaml").read_bytes())["widgets"]["clock"] == original
    dialog.close()


def test_dock_tab_applies_only_edited_size(config_dir, qapp, monkeypatch):
    from core.utils import windhawk_dock

    calls = []

    class DockSettings:
        original = (32, 32)

        def save(self, size):
            calls.append(size)
            return True

    monkeypatch.setattr(windhawk_dock, "DockIconSettings", DockSettings)
    dialog = BarSettingsDialog(config_dir, windhawk_dock=True)
    assert dialog.tabs.tabText(3) == "Dock"
    assert dialog.dock_size.value() == 32
    dialog.save()
    assert calls == []
    dialog.dock_size.setValue(36)
    dialog.save()
    dialog.save()
    assert calls == [36]
    dialog.close()


def test_dock_failure_keeps_bar_saved_and_reports_partial_result(config_dir, qapp, monkeypatch):
    from core.utils import windhawk_dock

    class DockSettings:
        original = (32, 32)

        def save(self, size):
            raise OSError("Approval cancelled")

    monkeypatch.setattr(windhawk_dock, "DockIconSettings", DockSettings)
    messages = []
    monkeypatch.setattr("core.ui.views.bar_settings.QMessageBox.warning", lambda *args: messages.append(args[2]))
    dialog = BarSettingsDialog(config_dir, windhawk_dock=True)
    dialog.font_size.setValue(15)
    dialog.dock_size.setValue(36)
    dialog.save()
    assert SettingsDocument(config_dir).appearance()["font_size"] == 15
    assert "Approval cancelled" in messages[0]
    assert "could not be applied" in dialog.status.text()
    assert dialog.dock_size_changed
    dialog.close()


def test_unavailable_dock_does_not_block_bar_settings(config_dir, qapp, monkeypatch):
    from core.utils import windhawk_dock

    def unavailable():
        raise FileNotFoundError("Windhawk mod is not installed")

    monkeypatch.setattr(windhawk_dock, "DockIconSettings", unavailable)
    dialog = BarSettingsDialog(config_dir, windhawk_dock=True)
    assert not dialog.dock_size.isEnabled()
    dialog.font_size.setValue(15)
    dialog.save()
    assert SettingsDocument(config_dir).appearance()["font_size"] == 15
    dialog.close()


def test_appearance_rules_reach_labels_and_round_trip(config_dir, qapp):
    doc = SettingsDocument(config_dir)
    appearance = dict(doc.appearance(), font_size=19, spacing=13, opacity=37)
    config, css = doc.render("status", doc.config["bars"]["status"]["widgets"], appearance)
    root = QWidget()
    root.setProperty("class", "bar yasb-bar")
    widget = QWidget(root)
    widget.setProperty("class", "widget")
    label = QLabel("CPU 10%", widget)
    label.setProperty("class", "label")
    root.setStyleSheet(css.decode())
    root.ensurePolished()
    label.ensurePolished()
    assert label.font().pixelSize() == 19
    doc.save(config, css)
    values = SettingsDocument(config_dir).appearance()
    assert (values["font_size"], values["spacing"], values["opacity"]) == (19, 13, 37)
    root.close()
