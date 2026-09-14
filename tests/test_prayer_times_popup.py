"""Widget-level tests for the prayer times popup: section structure, hero block, refresh and flash classes.

The popup body is filled into a plain host frame, so no popup window is ever shown.
"""

import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from PyQt6.QtWidgets import QApplication, QFrame, QProgressBar, QVBoxLayout, QWidget  # noqa: E402

APP = QApplication.instance() or QApplication([])

from core.validation.widgets.yasb.prayer_times import PrayerTimesConfig  # noqa: E402
from core.widgets.yasb.prayer_times import PrayerTimesWidget  # noqa: E402

JAKARTA = ZoneInfo("Asia/Jakarta")

TIMINGS = {
    "Fajr": "04:44",
    "Sunrise": "06:06",
    "Dhuhr": "12:00",
    "Asr": "15:22",
    "Sunset": "17:54",
    "Maghrib": "17:54",
    "Isha": "19:08",
    "Imsak": "04:34",
    "Midnight": "00:00",
    "Firstthird": "21:58",
    "Lastthird": "02:02",
}


def payload(gregorian: str, hijri_day: str) -> dict:
    """Build an Aladhan-shaped response for the given gregorian date."""
    return {
        "code": 200,
        "data": {
            "timings": dict(TIMINGS),
            "date": {
                "gregorian": {"date": gregorian},
                "hijri": {"day": hijri_day, "month": {"en": "Safar"}, "year": "1448"},
            },
            "meta": {"timezone": "Asia/Jakarta", "method": {"name": "Kementerian Agama Republik Indonesia"}},
        },
    }


def find_class(root: QWidget, cls: str) -> QWidget | None:
    """Return the first descendant whose class list contains *cls*."""
    for child in root.findChildren(QWidget):
        if cls in (child.property("class") or "").split():
            return child
    return None


def by_class(root: QWidget, cls: str) -> QWidget:
    child = find_class(root, cls)
    if child is None:
        raise AssertionError(f"no descendant with class {cls!r}")
    return child


class PopupTestCase(unittest.TestCase):
    def setUp(self) -> None:
        config = PrayerTimesConfig(
            label="<span>{icon}</span> {next_prayer} {next_prayer_time}",
            flash={"enabled": False},
        )
        self.widget = PrayerTimesWidget(config)
        self.widget._fetcher._timer.stop()
        self.set_now(datetime(2026, 7, 21, 10, 6, tzinfo=JAKARTA))
        self.host = QFrame()
        self.layout = QVBoxLayout(self.host)

    def tearDown(self) -> None:
        self.widget._minute_timer.stop()
        self.host.deleteLater()
        self.widget.deleteLater()

    def set_now(self, moment: datetime) -> None:
        self.widget._now = lambda: moment

    def load_today(self) -> None:
        self.widget._on_data_received(payload("21-07-2026", "6"))


class PopupStructureTest(PopupTestCase):
    def test_sections_are_frames_so_css_padding_and_borders_apply(self) -> None:
        """Qt ignores padding and borders on a plain QWidget, which clipped the footer and let the date touch the edge."""
        self.load_today()
        self.widget._fill_popup(self.layout)

        for cls in ("header", "hero", "rows-container", "footer"):
            with self.subTest(section=cls):
                self.assertIsInstance(by_class(self.host, cls), QFrame)

    def test_loading_popup_shows_placeholder_without_hero(self) -> None:
        self.widget._fill_popup(self.layout)

        self.assertIsNotNone(find_class(self.host, "loading-placeholder"))
        self.assertIsNone(find_class(self.host, "hero"))


class HeroTest(PopupTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.load_today()
        self.widget._fill_popup(self.layout)
        self.hero = by_class(self.host, "hero")

    def test_hero_carries_the_next_prayer(self) -> None:
        self.assertIn("dhuhr", self.hero.property("class").split())
        self.assertEqual(by_class(self.hero, "hero-name").text(), "Dhuhr")

    def test_hero_counts_down_and_fills_from_the_previous_prayer(self) -> None:
        self.assertEqual(by_class(self.hero, "hero-countdown").text(), "in 1h 54m")
        self.assertEqual(by_class(self.hero, "hero-from").text(), "Fajr 04:44")
        self.assertEqual(by_class(self.hero, "hero-to").text(), "12:00")

        bar = by_class(self.hero, "hero-progress")
        self.assertIsInstance(bar, QProgressBar)
        # 04:44 -> 12:00 spans 436 minutes, 322 of which have elapsed at 10:06.
        self.assertEqual(bar.value(), round(322 / 436 * bar.maximum()))

    def test_refresh_updates_the_countdown_in_place(self) -> None:
        self.set_now(datetime(2026, 7, 21, 11, 6, tzinfo=JAKARTA))

        self.widget._refresh_popup()

        self.assertIs(by_class(self.host, "hero"), self.hero)
        self.assertEqual(by_class(self.hero, "hero-countdown").text(), "in 54m")


class HeaderAndFooterTest(PopupTestCase):
    def test_header_shows_hijri_and_gregorian_dates(self) -> None:
        self.load_today()
        self.widget._fill_popup(self.layout)

        header = by_class(self.host, "header")
        self.assertEqual(by_class(header, "hijri-date").text(), "6 Safar 1448 AH")
        self.assertEqual(by_class(header, "gregorian-date").text(), "Today, Tuesday 21 July")

    def test_footer_shows_method_and_timezone(self) -> None:
        self.load_today()
        self.widget._fill_popup(self.layout)

        footer = by_class(self.host, "footer")
        self.assertEqual(by_class(footer, "method-name").text(), "Kementerian Agama Republik Indonesia")
        self.assertEqual(by_class(footer, "timezone").text(), "Asia/Jakarta")

    def test_switching_to_tomorrow_rebuilds_the_header(self) -> None:
        self.load_today()
        self.widget._fill_popup(self.layout)

        self.set_now(datetime(2026, 7, 21, 22, 0, tzinfo=JAKARTA))
        self.load_today()  # every prayer has passed, so the widget moves on to tomorrow
        self.widget._on_data_received(payload("22-07-2026", "7"))
        self.widget._refresh_popup()

        header = by_class(self.host, "header")
        self.assertEqual(by_class(header, "gregorian-date").text(), "Tomorrow, Wednesday 22 July")
        self.assertEqual(by_class(header, "hijri-date").text(), "7 Safar 1448 AH")


class FlashTest(PopupTestCase):
    def test_flash_keeps_each_label_class(self) -> None:
        """The flash used to overwrite every label with 'label flash', turning icon spans into text labels."""
        self.load_today()
        icon, text = self.widget._widgets[0], self.widget._widgets[1]

        self.widget._start_flash()
        try:
            icon_classes = icon.property("class").split()
            text_classes = text.property("class").split()
            self.assertIn("icon", icon_classes)
            self.assertNotIn("label", icon_classes)
            self.assertIn("flash", icon_classes)
            self.assertIn("label", text_classes)
            self.assertIn("flash", text_classes)
        finally:
            self.widget._stop_flash()

    def test_flash_keeps_the_prayer_class(self) -> None:
        """Per-prayer rules such as `.icon.dhuhr` used to stop matching for the whole flash."""
        self.load_today()
        icon, text = self.widget._widgets[0], self.widget._widgets[1]

        self.widget._start_flash()
        try:
            self.assertEqual(set(icon.property("class").split()), {"icon", "dhuhr", "flash"})
            self.assertEqual(set(text.property("class").split()), {"label", "dhuhr", "flash"})
        finally:
            self.widget._stop_flash()

    def test_flash_class_survives_a_minute_tick(self) -> None:
        """The minute tick re-rendered the label and dropped `flash` while the glow was still animating."""
        self.load_today()
        icon, text = self.widget._widgets[0], self.widget._widgets[1]

        self.widget._start_flash()
        try:
            self.widget._on_minute_tick()
            self.assertIn("flash", icon.property("class").split())
            self.assertIn("flash", text.property("class").split())
        finally:
            self.widget._stop_flash()

        self.assertEqual(set(icon.property("class").split()), {"icon", "dhuhr"})
        self.assertEqual(set(text.property("class").split()), {"label", "dhuhr"})

    def test_flash_before_the_first_response_keeps_the_loading_class(self) -> None:
        """A debug flash fires before the API answers; it replaced `label loading` with `label flash`."""
        icon, text = self.widget._widgets[0], self.widget._widgets[1]

        self.widget._start_flash()
        try:
            self.assertEqual(set(text.property("class").split()), {"label", "loading", "flash"})
            self.assertEqual(set(icon.property("class").split()), {"icon", "flash"})
        finally:
            self.widget._stop_flash()

    def test_flash_class_follows_a_label_toggle(self) -> None:
        """Toggling to the alt label mid-flash showed it without the `flash` class."""
        self.load_today()

        self.widget._start_flash()
        try:
            self.widget._toggle_label()
            alt = self.widget._widgets_alt[0]
            self.assertEqual(set(alt.property("class").split()), {"label", "alt", "dhuhr", "flash"})
        finally:
            self.widget._stop_flash()


if __name__ == "__main__":
    unittest.main()
