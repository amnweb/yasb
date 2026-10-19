from pathlib import Path

from core.config import plugin_stylesheets
from core.utils.css_processor import CSSProcessor
from core.validation.config import YasbConfig
from tests.plugins.helpers import WIDGET_TYPE, plugin_modules


def _config(*widget_types: str) -> YasbConfig:
    return YasbConfig.model_validate({"widgets": {f"w{i}": {"type": t} for i, t in enumerate(widget_types)}})


def test_plugin_css_comes_first_and_uses_user_variables(tmp_path: Path):
    plugin = tmp_path / "plugin"
    plugin.mkdir()
    (plugin / "icon.png").write_bytes(b"")
    (plugin / "styles.css").write_text(
        ".hello-widget .label { color: var(--accent); image: url(icon.png); }", encoding="utf-8"
    )
    user = tmp_path / "styles.css"
    user.write_text(":root { --accent: #ff0000; }\n.hello-widget .label { color: blue; }", encoding="utf-8")

    css = CSSProcessor(str(user), [str(plugin / "styles.css")]).process()

    assert css.index("color: #ff0000") < css.index("color: blue")
    assert f"url({(plugin / 'icon.png').as_posix()})" in css
    assert "var(--accent)" not in css


def test_without_plugin_css_the_user_css_is_unchanged(tmp_path: Path):
    user = tmp_path / "styles.css"
    user.write_text(".bar { color: red; }", encoding="utf-8")

    assert CSSProcessor(str(user)).process() == CSSProcessor(str(user), []).process()


def test_only_plugins_in_the_config_add_css(plugins_root: Path):
    assert plugin_stylesheets(_config(WIDGET_TYPE, "yasb.clock.ClockWidget")) == [
        str(plugins_root / "hello" / "styles.css")
    ]
    assert plugin_stylesheets(_config("yasb.clock.ClockWidget")) == []
    assert plugin_stylesheets(None) == []


def test_missing_plugin_css_is_skipped(plugin_dir: Path):
    (plugin_dir / "styles.css").unlink()

    assert plugin_stylesheets(_config(WIDGET_TYPE)) == []


def test_plugin_css_does_not_import_the_plugin(plugins_root: Path):
    plugin_stylesheets(_config(WIDGET_TYPE))

    assert plugin_modules() == []
