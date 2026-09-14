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

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtWidgets import QApplication, QFrame, QLabel, QProgressBar, QVBoxLayout, QWidget  # noqa: E402

APP = QApplication.instance() or QApplication([])

from core.utils.widgets.prayer_times.ribbon import DayRibbon  # noqa: E402
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


class DayRibbonTest(PopupTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.load_today()
        self.widget._fill_popup(self.layout)

    def test_the_ribbon_sits_between_the_dates_and_the_countdown(self) -> None:
        sections = [
            cls
            for cls in ("header", "day", "hero", "rows-container", "footer")
            if find_class(self.host, cls) is not None
        ]

        self.assertEqual(sections, ["header", "day", "hero", "rows-container", "footer"])

    def test_the_band_is_painted_not_composed_of_widgets(self) -> None:
        self.assertIsInstance(by_class(self.host, "day-ribbon"), DayRibbon)

    def test_captions_name_the_real_sunrise_sunset_and_daylight(self) -> None:
        day = by_class(self.host, "day")

        self.assertEqual(by_class(day, "day-sunrise").text(), "06:06")
        self.assertEqual(by_class(day, "day-sunset").text(), "17:54")
        self.assertEqual(by_class(day, "day-length").text(), "11h 48m of daylight")

    def test_one_tick_per_prayer_on_show(self) -> None:
        ribbon: DayRibbon = by_class(self.host, "day-ribbon")

        self.assertEqual(len(ribbon._marks), len(self.widget._schedule))

    def test_ticks_carry_which_prayers_the_day_has_gone_past(self) -> None:
        """At 10:06 Fajr is behind and Dhuhr is still ahead."""
        ribbon: DayRibbon = by_class(self.host, "day-ribbon")
        passed = {entry.name: mark.passed for entry, mark in zip(self.widget._schedule, ribbon._marks)}

        self.assertTrue(passed["Fajr"])
        self.assertFalse(passed["Dhuhr"])

    def test_the_stem_tracks_the_clock(self) -> None:
        ribbon: DayRibbon = by_class(self.host, "day-ribbon")
        at_ten = ribbon._now

        self.set_now(datetime(2026, 7, 21, 16, 0, tzinfo=JAKARTA))
        self.widget._refresh_popup()

        self.assertIsNotNone(at_ten)
        self.assertGreater(ribbon._now, at_ten)

    def test_the_stem_is_dropped_when_the_band_is_not_the_day_the_clock_is_in(self) -> None:
        """Late evening the popup has already moved on to tomorrow; today's clock is not on that band."""
        self.widget._on_data_received(payload("22-07-2026", "7"))
        self.widget._fill_popup(self.layout)

        self.assertIsNone(by_class(self.host, "day-ribbon")._now)

    def test_no_ribbon_without_the_moments_that_light_it(self) -> None:
        """A response with no sunrise or sunset would only buy a flat band that says nothing."""
        stripped = payload("21-07-2026", "6")
        for name in ("Sunrise", "Sunset", "Maghrib"):
            stripped["data"]["timings"].pop(name)
        self.widget._on_data_received(stripped)

        self.widget._fill_popup(self.layout)

        self.assertIsNone(find_class(self.host, "day"))
        self.assertIsNotNone(find_class(self.host, "hero"))


class PassedPrayerTest(PopupTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.load_today()
        self.widget._fill_popup(self.layout)

    def remaining(self, prayer: str) -> QLabel:
        return self.widget._popup_row_widgets[prayer]["remaining"]

    def test_a_prayer_the_day_has_gone_past_is_marked_not_labelled(self) -> None:
        """Four rows all reading the word 'passed' filled the column with what you already knew."""
        label = self.remaining("Fajr")

        self.assertEqual(label.text(), self.widget.config.icons.done)
        self.assertIn("done", label.property("class").split())

    def test_upcoming_prayers_keep_their_countdown(self) -> None:
        label = self.remaining("Asr")

        self.assertEqual(label.text(), "in 5h 16m")
        self.assertNotIn("done", label.property("class").split())

    def test_the_mark_is_centred_so_the_glyph_cannot_be_sliced(self) -> None:
        """Right-aligned, Qt lays the glyph out on a fallback advance narrower than the ink it paints."""
        self.assertEqual(self.remaining("Fajr").alignment(), Qt.AlignmentFlag.AlignCenter)

    def test_a_countdown_becoming_a_mark_takes_the_alignment_with_it(self) -> None:
        self.set_now(datetime(2026, 7, 21, 16, 0, tzinfo=JAKARTA))

        self.widget._refresh_popup()

        label = self.remaining("Dhuhr")
        self.assertEqual(label.text(), self.widget.config.icons.done)
        self.assertEqual(label.alignment(), Qt.AlignmentFlag.AlignCenter)


class CalledPrayerTest(PopupTestCase):
    """The minutes a prayer has just been called and is still inside its grace period."""

    def test_the_hero_and_its_row_both_say_now(self) -> None:
        self.load_today()
        self.set_now(datetime(2026, 7, 21, 15, 23, tzinfo=JAKARTA))
        self.widget._fill_popup(self.layout)

        self.assertIn("now", by_class(self.host, "hero").property("class").split())
        self.assertIn("now", self.widget._popup_row_widgets["Asr"]["row"].property("class").split())

    def test_the_state_clears_once_the_grace_period_is_over(self) -> None:
        self.load_today()
        self.set_now(datetime(2026, 7, 21, 15, 23, tzinfo=JAKARTA))
        self.widget._fill_popup(self.layout)

        self.set_now(datetime(2026, 7, 21, 15, 40, tzinfo=JAKARTA))
        self.widget._refresh_popup()

        self.assertNotIn("now", by_class(self.host, "hero").property("class").split())


class EveryPrayerPassedTest(PopupTestCase):
    """Late evening, before tomorrow's schedule has landed."""

    def setUp(self) -> None:
        super().setUp()
        self.load_today()
        self.set_now(datetime(2026, 7, 21, 22, 30, tzinfo=JAKARTA))
        self.widget._fill_popup(self.layout)

    def test_counts_down_to_tomorrow_rather_than_back_to_this_morning(self) -> None:
        """The first prayer was returned unrolled, so the hero announced one 'started 1076m ago'."""
        self.assertEqual(by_class(self.host, "hero-countdown").text(), "in 6h 14m")

    def test_the_span_runs_from_tonight_s_last_prayer(self) -> None:
        hero = by_class(self.host, "hero")

        self.assertEqual(by_class(hero, "hero-from").text(), "Isha 19:08")
        self.assertEqual(by_class(hero, "hero-to").text(), "04:44")

    def test_the_progress_bar_stays_inside_its_range(self) -> None:
        bar = by_class(self.host, "hero-progress")

        self.assertGreater(bar.value(), 0)
        self.assertLess(bar.value(), bar.maximum())

    def test_the_next_row_counts_down_instead_of_being_marked_done(self) -> None:
        """The row was both highlighted as next and marked as gone by, reading its own moment."""
        remaining = self.widget._popup_row_widgets["Fajr"]["remaining"]

        self.assertEqual(remaining.text(), by_class(self.host, "hero-countdown").text())
        self.assertNotIn("done", remaining.property("class").split())

    def test_every_other_row_is_still_marked_done(self) -> None:
        for prayer in ("Dhuhr", "Asr", "Maghrib", "Isha"):
            with self.subTest(prayer=prayer):
                label = self.widget._popup_row_widgets[prayer]["remaining"]
                self.assertIn("done", label.property("class").split())


if __name__ == "__main__":
    unittest.main()
