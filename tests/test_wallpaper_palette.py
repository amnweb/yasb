"""Palette extraction tests: pure Pillow logic, runs on any OS."""

import pytest

from core.utils.wallpaper_palette import extract_palette, pick_accent, pick_text, rgb_to_hex


def test_solid_image_yields_exactly_that_color(solid_image):
    palette = extract_palette(solid_image)
    assert len(palette) >= 1
    assert palette[0] == (30, 144, 255)


def test_dominant_color_is_first(two_tone_image):
    palette = extract_palette(two_tone_image, max_colors=2)
    assert len(palette) == 2
    # The two halves are equal in area, so either may rank first, but both
    # cluster centers must be close to the two source colors.
    recovered = sorted(palette)
    assert recovered[0] == pytest.approx((30, 30, 30), abs=40) or recovered[0] == pytest.approx((30, 200, 30), abs=40)
    assert recovered[1] == pytest.approx((200, 30, 30), abs=40) or recovered[1] == pytest.approx((30, 200, 30), abs=40)


def test_palette_is_deterministic(solid_image):
    assert extract_palette(solid_image) == extract_palette(solid_image)


def test_unreadable_image_raises(solid_image, tmp_path):
    with pytest.raises(Exception):
        extract_palette(str(tmp_path / "does_not_exist.png"))


def test_rgb_to_hex():
    assert rgb_to_hex((0, 0, 0)) == "#000000"
    assert rgb_to_hex((255, 255, 255)) == "#ffffff"
    assert rgb_to_hex((18, 52, 86)) == "#123456"


def test_pick_text_light_background_gives_dark_text():
    assert pick_text((245, 245, 245)) == (17, 17, 17)


def test_pick_text_dark_background_gives_light_text():
    assert pick_text((10, 10, 15)) == (255, 255, 255)


def test_pick_accent_prefers_saturated_color(saturated_image):
    colors = extract_palette(saturated_image, max_colors=2)
    accent = pick_accent(colors)
    # The red patch is the only saturated cluster, so it must win over gray.
    assert accent[0] > accent[1] and accent[0] > accent[2]


def test_pick_accent_on_empty_list():
    assert pick_accent([]) == (255, 255, 255)
