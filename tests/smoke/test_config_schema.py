from typing import Any

import pytest
from pydantic import ValidationError

from core.validation.config import YasbConfig


def test_yasb_config_schema_builds():
    YasbConfig.model_json_schema()


def test_a_bar_fills_its_slots_with_widgets_by_name():
    config = YasbConfig.model_validate(
        {
            "bars": {
                "main": {
                    "file": "bars/main.qml",
                    "widgets": {"left": ["clock", "active_window"], "tray": ["media-lite"]},
                }
            }
        }
    )
    bar = config.bars["main"]
    assert bar.file == "bars/main.qml"
    assert bar.widgets == {"left": ["clock", "active_window"], "tray": ["media-lite"]}


def test_a_bar_without_file_or_widgets_uses_the_defaults():
    bar = YasbConfig.model_validate({"bars": {"main": {}}}).bars["main"]
    assert (bar.file, bar.widgets) == (None, {})


REJECTED: dict[str, dict[str, Any]] = {
    "top_level_widgets": {"widgets": {"clock": {"type": "yasb.clock.ClockWidget"}}},
    "old_alignment": {"bars": {"main": {"alignment": {"position": "top"}}}},
    "old_blur_effect": {"bars": {"main": {"blur_effect": {"enabled": True}}}},
    "old_layouts": {"bars": {"main": {"layouts": {"left": {"stretch": False}}}}},
    "empty_file": {"bars": {"main": {"file": ""}}},
    "path_in_slot_name": {"bars": {"main": {"widgets": {"../left": ["clock"]}}}},
    "path_in_widget_name": {"bars": {"main": {"widgets": {"left": ["../clock"]}}}},
    "widget_name_starts_with_digit": {"bars": {"main": {"widgets": {"left": ["2fa"]}}}},
    "old_backdrop_settings": {"bars": {"main": {"backdrop": {"type": "acrylic"}}}},
    "unknown_length": {"bars": {"main": {"length": "wide"}}},
}


@pytest.mark.parametrize("config", REJECTED.values(), ids=REJECTED.keys())
def test_invalid_config_is_rejected(config: dict[str, Any]):
    with pytest.raises(ValidationError):
        YasbConfig.model_validate(config)
