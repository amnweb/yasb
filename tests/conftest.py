"""Shared fixtures: synthetic wallpaper images built with Pillow."""

import pytest
from PIL import Image

HALF = 128


def _write(path, image):
    image.save(path)
    return str(path)


@pytest.fixture
def solid_image(tmp_path):
    """A single-color image: the palette must be exactly that color."""
    return _write(tmp_path / "solid.png", Image.new("RGB", (256, 256), (30, 144, 255)))


@pytest.fixture
def two_tone_image(tmp_path):
    """Two equal halves of very different colors."""
    image = Image.new("RGB", (256, 256), (200, 30, 30))
    for x in range(HALF, 256):
        for y in range(256):
            image.putpixel((x, y), (30, 200, 30))
    return _write(tmp_path / "two_tone.png", image)


@pytest.fixture
def dark_image(tmp_path):
    """Mostly very dark with a small bright patch: text must go light."""
    image = Image.new("RGB", (256, 256), (10, 10, 15))
    for x in range(230, 256):
        for y in range(256):
            image.putpixel((x, y), (240, 240, 240))
    return _write(tmp_path / "dark.png", image)


@pytest.fixture
def light_image(tmp_path):
    """Mostly very light with a small dark patch: text must go dark."""
    image = Image.new("RGB", (256, 256), (245, 245, 245))
    for x in range(230, 256):
        for y in range(256):
            image.putpixel((x, y), (20, 20, 20))
    return _write(tmp_path / "light.png", image)


@pytest.fixture
def saturated_image(tmp_path):
    """Dominant muted gray with a saturated minority: accent must be the hue."""
    image = Image.new("RGB", (256, 256), (128, 128, 128))
    for x in range(0, 64):
        for y in range(256):
            image.putpixel((x, y), (220, 40, 40))
    return _write(tmp_path / "saturated.png", image)
