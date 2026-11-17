import re
from pathlib import Path
from typing import Any

import pytest
from PyQt6.QtCore import Q_RETURN_ARG, QMetaObject, Qt, QUrl
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlComponent, QQmlEngine

import core.config as config_module
from core.app.windows import setup as setup_window
from core.app.windows.setup import Setup, register_setup_type
from core.config import read_config
from core.qml_types import register_qml_types
from core.setup import (
    LAYOUT_TEMPLATES,
    THEME_NAME,
    THEME_TEMPLATE,
    SetupChoices,
    Style,
    build_config,
    setup_reason,
    write_setup,
)
from core.theme_files import THEME_QML
from core.validation.config import YasbConfig
from core.widget_files import BUILTIN_WIDGETS_DIR
from settings import QML_IMPORT_PATH
from tests.support.qt import wait

V2_CONFIG = "watch_stylesheet: true\nwatch_config: true\nbars:\n  primary-bar:\n    widgets:\n      left: [clock]\nwidgets:\n  clock:\n    type: yasb.clock.ClockWidget\n"


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A temporary config folder, and no autostart."""
    monkeypatch.setattr(config_module, "HOME_CONFIG_PATH", str(tmp_path / "config.yaml"))
    monkeypatch.setattr(setup_window, "AUTOSTART_FILE", None)
    return tmp_path


def choices(**overrides: Any) -> SetupChoices:
    picked: dict[str, Any] = {
        "edge": "top",
        "style": "bar",
        "thickness": 32,
        "screens": "*",
        "backdrop": True,
        "always_on_top": True,
        "hide_on_fullscreen": True,
        "auto_hide": "never",
        "reserve_space": True,
        "widgets": {"left": ["ActiveWindow"], "center": ["Clock"], "right": ["Volume", "PowerMenu"]},
        "update_check": True,
        "autostart": False,
    }
    return SetupChoices.model_validate({**picked, **overrides})


def qml_choices(**overrides: Any) -> dict[str, Any]:
    """The choices as the window sends them."""
    return choices(**overrides).model_dump(by_alias=True)


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        (None, "new"),
        (V2_CONFIG, "upgrade"),
        # 3.0 configs, valid or not
        ("bars:\n  yasb-bar:\n    widgets:\n      left: [Clock]\n", None),
        ("bars: [unclosed\n", None),
    ],
)
def test_the_setup_opens_for_a_missing_or_2x_config(home: Path, text: str | None, reason: str | None):
    if text is not None:
        (home / "config.yaml").write_text(text, encoding="utf-8")
    assert setup_reason() == reason


def test_the_config_keeps_the_widgets_order_and_a_floating_bar_its_gap():
    picked = choices(style="floating", widgets={"right": ["Volume"], "center": [], "left": ["Clock", "Media"]})
    bar = build_config(picked)["bars"]["yasb-bar"]
    assert list(bar["widgets"].items()) == [("left", ["Clock", "Media"]), ("right", ["Volume"])]
    assert bar["margin"] == {"top": 6, "left": 6, "right": 6}


@pytest.mark.parametrize("style", ["bar", "floating", "islands"])
def test_the_written_config_loads_with_its_layout_and_theme(home: Path, style: Style):
    picked = choices(style=style)
    config = build_config(picked)
    write_setup(config, picked)
    assert read_config() == YasbConfig(**config)
    assert (home / "layouts" / f"{style}.qml").read_bytes() == (LAYOUT_TEMPLATES / f"{style}.qml").read_bytes()
    assert (home / "themes" / f"{THEME_NAME}.qml").read_bytes() == THEME_TEMPLATE.read_bytes()


def test_a_layout_and_theme_the_user_already_has_are_kept(home: Path):
    for folder, name in (("layouts", "islands.qml"), ("themes", f"{THEME_NAME}.qml")):
        (home / folder).mkdir()
        (home / folder / name).write_text("// mine\n", encoding="utf-8")
    picked = choices(style="islands")
    write_setup(build_config(picked), picked)
    assert (home / "layouts" / "islands.qml").read_text(encoding="utf-8") == "// mine\n"
    assert (home / "themes" / f"{THEME_NAME}.qml").read_text(encoding="utf-8") == "// mine\n"


def test_without_a_backdrop_the_bar_and_popups_get_an_opaque_background(home: Path):
    picked = choices(backdrop=False)
    write_setup(build_config(picked), picked)
    written = _theme_file_values((home / "themes" / f"{THEME_NAME}.qml").read_text(encoding="utf-8"))
    template = _theme_file_values(THEME_TEMPLATE.read_text(encoding="utf-8"))
    changed = {name for name, value in template.items() if written[name] != value}
    assert changed == {"bar.background", "popup.background"}
    assert written["bar.background"] == written["popup.background"] == "colors.background"


def test_finish_writes_the_config_and_says_so(qapp: QGuiApplication, home: Path):
    controller = Setup("new")
    finished: list[bool] = []
    controller.finished.connect(lambda: finished.append(True))
    assert controller.finish(qml_choices(style="floating")) == ""
    assert read_config().bars["yasb-bar"].layout == "floating"
    assert finished == [True]


def test_choices_the_setup_cannot_use_write_nothing(qapp: QGuiApplication, home: Path):
    controller = Setup("new")
    assert controller.finish({**qml_choices(), "style": "sideways"}) != ""
    assert list(home.iterdir()) == []


def test_the_setup_window_starts_with_choices_yasb_loads(qapp: QGuiApplication, home: Path):
    register_qml_types()
    register_setup_type()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    component = QQmlComponent(
        engine, QUrl.fromLocalFile(str(Path(QML_IMPORT_PATH, "Yasb", "Setup", "SetupWindow.qml")))
    )
    controller = Setup("new")
    window = component.createWithInitialProperties({"setup": controller})
    assert window is not None, [error.toString() for error in component.errors()]
    defaults = window.property("choices")
    sent = QMetaObject.invokeMethod(defaults, "toSetup", Qt.ConnectionType.DirectConnection, Q_RETURN_ARG("QVariant"))
    assert controller.finish(sent.toVariant()) == ""
    assert read_config().bars["yasb-bar"].widgets["center"] == ["Clock"]
    window.deleteLater()
    wait(0)


def test_every_widget_the_setup_offers_is_built_in():
    text = (Path(QML_IMPORT_PATH) / "Yasb" / "Setup" / "Choices.qml").read_text(encoding="utf-8")
    offered = re.findall(r'^\s*\["(\w+)", qsTr', text, flags=re.MULTILINE)
    assert len(offered) > 20
    assert [name for name in offered if not (BUILTIN_WIDGETS_DIR / name / f"{name}.qml").is_file()] == []


def test_the_theme_the_setup_copies_sets_every_default_as_it_is():
    defaults = _default_theme_values()
    assert len(defaults) > 40
    assert _theme_file_values(THEME_TEMPLATE.read_text(encoding="utf-8")) == defaults


def _theme_file_values(text: str) -> dict[str, str]:
    """Every value a theme file sets, as group.name: expression."""
    return _group_values(re.findall(r"^    (colors|bar|popup|menu) \{\n(.*?)\n    \}", text, re.DOTALL | re.MULTILINE))


def _default_theme_values() -> dict[str, str]:
    """Theme.qml's defaults, as group.name: expression, without the theme. a theme file doesn't need."""
    text = THEME_QML.read_text(encoding="utf-8").replace("theme.", "")
    return _group_values(
        re.findall(r"readonly property \w+ (colors|bar|popup|menu): \w+ \{\n(.*?)\n    \}", text, re.DOTALL)
    )


def _group_values(groups: list[tuple[str, str]]) -> dict[str, str]:
    return {
        f"{group}.{name}": value
        for group, body in groups
        for name, value in re.findall(r"^        ([\w.]+): (.+)$", body, flags=re.MULTILINE)
    }
