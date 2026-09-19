"""Config model tests for the wallpaper_colors option: pydantic only, any OS."""

import pytest
from pydantic import ValidationError

from core.validation.config import WallpaperColorsConfig, YasbConfig


def test_defaults_are_opt_in():
    config = WallpaperColorsConfig()
    assert config.enabled is False
    assert config.auto_apply is True


def test_unknown_keys_rejected():
    with pytest.raises(ValidationError):
        WallpaperColorsConfig(nonexistent=1)


def test_roundtrip_inside_yasb_config():
    config = YasbConfig(wallpaper_colors={"enabled": True, "auto_apply": False})
    assert config.wallpaper_colors.enabled is True
    assert config.wallpaper_colors.auto_apply is False


def test_default_yasb_config_has_feature_disabled():
    config = YasbConfig()
    assert config.wallpaper_colors.enabled is False


def test_top_level_unknown_key_still_rejected():
    with pytest.raises(ValidationError):
        YasbConfig(wallpaper_colors_typo=1)
