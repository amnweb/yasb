"""WallpaperColorsService lifecycle tests.

These exercise the Qt plumbing (debounce, event registration, stop cleanup) and
therefore need a QApplication plus the Windows registry, so they only run on
Windows; elsewhere they skip with a visible reason.
"""

import os
import sys

import pytest

pytest.importorskip("PyQt6.QtWidgets", reason="service is Qt-based")

if sys.platform != "win32":
    pytest.skip("Wallpaper registry and native messages only exist on Windows", allow_module_level=True)

from PyQt6.QtWidgets import QApplication  # noqa: E402

import core.utils.wallpaper_colors as wc  # noqa: E402
from core.utils.wallpaper_colors import WallpaperColorsService  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def service_home(tmp_path, monkeypatch):
    monkeypatch.setattr(wc, "DEFAULT_CONFIG_DIRECTORY", str(tmp_path))
    return tmp_path


@pytest.fixture
def no_registry(monkeypatch):
    """No wallpaper set: the poll reads None and extraction is skipped."""
    monkeypatch.setattr(wc, "_read_registry_wallpaper", lambda: None)


def test_singleton_start_and_stop(qapp, service_home, no_registry):
    service = WallpaperColorsService.start_service()
    try:
        assert WallpaperColorsService.start_service() is service
    finally:
        WallpaperColorsService.stop_service()
    assert WallpaperColorsService._instance is None


def test_stop_removes_generated_file(qapp, service_home, no_registry):
    generated = service_home / "yasb_wallpaper_colors.css"
    generated.write_text(":root {}\n", encoding="utf-8")

    service = WallpaperColorsService.start_service()
    emitted = []
    service.stylesheet_changed.connect(lambda: emitted.append(1))
    WallpaperColorsService.stop_service()

    assert not generated.exists()
    assert emitted == [1]


def test_debounce_coalesces_bursts(qapp, service_home, no_registry):
    service = WallpaperColorsService(auto_apply=True)
    try:
        service.schedule_update()
        service.schedule_update()
        service.schedule_update()
        assert service._debounce_timer.isActive()
    finally:
        service.stop()


def test_regenerate_skips_without_wallpaper(qapp, service_home, no_registry):
    service = WallpaperColorsService()
    emitted = []
    service.stylesheet_changed.connect(lambda: emitted.append(1))

    service._regenerate()

    assert emitted == []
    assert not (service_home / "yasb_wallpaper_colors.css").exists()


def test_regenerate_extracts_publishes_and_writes(qapp, service_home, monkeypatch):
    image = service_home / "wall.png"
    image.write_bytes(b"not really a png")
    monkeypatch.setattr(wc, "_read_registry_wallpaper", lambda: str(image))
    monkeypatch.setattr(wc, "extract_palette", lambda path: [(26, 43, 60), (200, 100, 50), (10, 200, 120)])

    service = WallpaperColorsService(auto_apply=True)
    emitted = []
    service.stylesheet_changed.connect(lambda: emitted.append(1))
    service._regenerate()

    generated = service_home / "yasb_wallpaper_colors.css"
    assert generated.exists()
    assert "background-color: #1a2b3c;" in generated.read_text(encoding="utf-8")
    assert emitted == [1]

    # A second run over the same wallpaper is a no-op.
    service._regenerate()
    assert emitted == [1]
    service.stop()


def test_fingerprint_tracks_content_change(tmp_path):
    image = tmp_path / "wall.png"
    image.write_bytes(b"png")
    first = wc._wallpaper_fingerprint(str(image))

    os.utime(image, ns=(1_000_000_000, 1_000_000_000))
    second = wc._wallpaper_fingerprint(str(image))

    assert first != second
    assert wc._wallpaper_fingerprint(None) is None
    assert wc._wallpaper_fingerprint(str(tmp_path / "missing.png")) == (str(tmp_path / "missing.png"),)
