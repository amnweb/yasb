"""Salah Times widget for YASB.

Shows the next salah and countdown in the bar; hover reveals the full day's
times. Clicking opens an in-bar popup that is both a **location chooser** and a
full editor — add a location by searching for a city, edit its calculation
method / Asr school / per-salah offsets, delete it, and pick the time format.

Salah times are computed with the ``adhanpy`` library and the Hijri date with
``hijridate`` (Umm al-Qura). The only network use is the free Open-Meteo
geocoding API for city search (no API key required).
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import UTC, datetime, timedelta
from functools import partial
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from adhanpy.PrayerTimes import PrayerTimes
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QComboBox,
    QCompleter,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.utils.system import app_data_path
from core.utils.tooltip import set_tooltip
from core.utils.utilities import PopupWidget
from core.validation.widgets.yasb.salah_times import SalahTimesWidgetConfig
from core.widgets.base import BaseWidget
from core.widgets.services.salah_times import geo, methods
from core.widgets.services.salah_times.api import GeocodingFetcher

logger = logging.getLogger("salah_times")

LIST_SALAH = ["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"]
NEXT_SALAH = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]


def _round_minute(dt: datetime) -> datetime:
    """Round a datetime to the nearest minute (for computed Sunnah times)."""
    return (dt + timedelta(seconds=30)).replace(second=0, microsecond=0)


OFFSET_KEYS = ["fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"]


def _searchable_combo(items: list[str], current: str, placeholder: str = "") -> QComboBox:
    """An editable combo box with a type-to-filter (contains) completer."""
    combo = QComboBox()
    combo.setEditable(True)
    combo.addItems(items)
    combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    completer = combo.completer()
    completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
    completer.setFilterMode(Qt.MatchFlag.MatchContains)
    completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    if placeholder:
        combo.lineEdit().setPlaceholderText(placeholder)
    combo.setCurrentText(current)
    return combo


ICON_EDIT = ""  # nf-fa-edit (pencil)
ICON_DELETE = ""  # nf-fa-trash_o


class SalahTimesWidget(BaseWidget):
    validation_schema = SalahTimesWidgetConfig
    _instances: list[SalahTimesWidget] = []

    def __init__(self, config: SalahTimesWidgetConfig):
        super().__init__(int(config.update_interval * 1000), class_name=config.class_name)
        SalahTimesWidget._instances.append(self)
        self.config = config

        self._show_alt_label = False
        self._menu: PopupWidget | None = None
        self._body: QWidget | None = None
        self._data: dict = {}
        self._values: dict = {}

        self._init_container()
        self.build_widget_label(config.label, config.label_alt, config.label_placeholder)

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("toggle_menu", self._toggle_menu)
        self.register_callback("update_label", self._update_label)
        self.callback_left = config.callbacks.on_left
        self.callback_middle = config.callbacks.on_middle
        self.callback_right = config.callbacks.on_right
        self.callback_timer = "update_label"

        self._load_data()
        self.start_timer()

    # ------------------------------------------------------------------ data

    @classmethod
    def update_all(cls) -> None:
        for inst in cls._instances:
            inst._load_data()
            inst._update_label()

    def _data_file(self) -> str:
        if self.config.data_file and self.config.data_file.strip():
            return os.path.expanduser(self.config.data_file)
        return str(app_data_path("salah_times.json"))

    def _load_data(self) -> None:
        path = self._data_file()
        try:
            with open(path, encoding="utf-8") as f:
                self._data = json.load(f)
        except FileNotFoundError:
            self._data = {}
        except Exception as e:
            logger.error("Failed to read salah_times data: %s", e)
            self._data = {}

        self._data.setdefault("locations", {})
        self._data.setdefault("time_format", self.config.time_format)

    def _save_data(self) -> None:
        try:
            with open(self._data_file(), "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("Failed to write salah_times data: %s", e)

    def _locations(self) -> dict:
        return self._data.get("locations", {})

    def _selected_key(self) -> str | None:
        locs = self._locations()
        sel = self._data.get("selected_location")
        if sel in locs:
            return sel
        return next(iter(locs), None)

    def _time_format(self) -> str:
        return self._data.get("time_format", "12h")

    # -------------------------------------------------------------- compute

    def _resolve_zone(self, tz_name: str | None):
        if tz_name:
            try:
                return ZoneInfo(tz_name)
            except ZoneInfoNotFoundError, Exception:
                logger.warning("Unknown timezone '%s', using local time", tz_name)
        return datetime.now().astimezone().tzinfo

    def _fmt(self, dt: datetime, zone) -> str:
        local = dt.astimezone(zone)
        if self._time_format() == "24h":
            return local.strftime("%H:%M")
        return local.strftime("%I:%M %p").lstrip("0")

    def _compute(self) -> dict:
        """Return a dict of label placeholders plus a structured payload used by
        the popup (`_times`, `_next`, `_empty`)."""
        key = self._selected_key()
        if not key:
            return self._empty_state()

        loc = self._locations()[key]
        lat = float(loc["latitude"])
        lon = float(loc["longitude"])
        country = (loc.get("country_code") or "").upper()
        city = loc.get("city") or key
        zone = self._resolve_zone(loc.get("timezone"))

        method_opt = methods.parse_method_option(loc.get("method") or "auto")
        method_key = methods.resolve_auto_method(country) if method_opt == "auto" else method_opt
        asr_school = loc.get("asr_school", "standard")
        offsets = loc.get("offsets") or {}

        params = methods.build_parameters(method_key, asr_school)

        now = datetime.now(UTC)
        today = now.astimezone(zone).date()
        tomorrow = today + timedelta(days=1)

        try:
            pt = PrayerTimes((lat, lon), datetime(today.year, today.month, today.day), calculation_parameters=params)
            pt_next = PrayerTimes(
                (lat, lon), datetime(tomorrow.year, tomorrow.month, tomorrow.day), calculation_parameters=params
            )
        except Exception as e:
            logger.warning("Salah time calculation failed: %s", e)
            return self._empty_state("Salah times unavailable for this location")

        def adj(dt: datetime, k: str) -> datetime:
            return dt + timedelta(minutes=offsets.get(k, 0) or 0)

        times = {
            "Fajr": adj(pt.fajr, "fajr"),
            "Sunrise": adj(pt.sunrise, "sunrise"),
            "Dhuhr": adj(pt.dhuhr, "dhuhr"),
            "Asr": adj(pt.asr, "asr"),
            "Maghrib": adj(pt.maghrib, "maghrib"),
            "Isha": adj(pt.isha, "isha"),
        }

        next_name, next_dt = None, None
        for name in NEXT_SALAH:
            if times[name] > now:
                next_name, next_dt = name, times[name]
                break
        if next_dt is None:
            next_name, next_dt = "Fajr", adj(pt_next.fajr, "fajr")

        total_min = max(0, int((next_dt - now).total_seconds() + 59) // 60)
        hours, mins = divmod(total_min, 60)
        time_left = f"{hours}h {mins:02d}m"
        next_time = self._fmt(next_dt, zone)

        display = [(n, self._fmt(times[n], zone)) for n in LIST_SALAH]
        if self.config.show_sunnah_times:
            # Sunnah night times: split the night from Maghrib to next Fajr.
            night = pt_next.fajr - pt.maghrib
            display.append(("Midnight", self._fmt(_round_minute(pt.maghrib + night / 2), zone)))
            display.append(("Last third", self._fmt(_round_minute(pt.maghrib + night * 2 / 3), zone)))

        line_items = [f"{n}: {t}" for n, t in display]
        location_text = f"{city}, {country}" if city and country else (city or country or "Unknown")

        return {
            "compact": f"{next_name} | {next_time}  ({time_left})",
            "next_salah": next_name,
            "next_time": next_time,
            "time_left": time_left,
            "list_inline": " | ".join(line_items),
            "list_multiline": "\n".join(line_items),
            "hijri_date": methods.hijri_date(today),
            "location": location_text,
            "location_source": f"manual:{key}",
            "method": methods.method_label(method_key),
            "asr": "Hanafi" if asr_school == "hanafi" else "Standard",
            # structured extras for the popup
            "_empty": False,
            "_times": display,
            "_next": next_name,
        }

    def _empty_state(self, msg: str = "No location — click to add one") -> dict:
        return {
            "compact": msg,
            "next_salah": "--",
            "next_time": "--",
            "time_left": "--",
            "list_inline": msg,
            "list_multiline": msg,
            "hijri_date": "--",
            "location": "No location",
            "location_source": "none",
            "method": "--",
            "asr": "--",
            "_empty": True,
            "_times": [],
            "_next": None,
        }

    # --------------------------------------------------------------- labels

    def _toggle_label(self) -> None:
        self._show_alt_label = not self._show_alt_label
        for w in self._widgets:
            w.setVisible(not self._show_alt_label)
        for w in self._widgets_alt:
            w.setVisible(self._show_alt_label)
        self._update_label()

    def _update_label(self) -> None:
        self._values = self._compute()
        active = self._widgets_alt if self._show_alt_label else self._widgets
        content = self.config.label_alt if self._show_alt_label else self.config.label

        parts = [p for p in re.split(r"(<span.*?>.*?</span>)", content) if p]
        idx = 0
        for part in parts:
            if idx >= len(active):
                break
            widget = active[idx]
            if "<span" in part and "</span>" in part:
                idx += 1
                continue
            text = part
            for k, v in self._values.items():
                if isinstance(v, str):
                    text = text.replace(f"{{{k}}}", v)
            widget.setText(text.strip())
            idx += 1

        if self.config.tooltip:
            set_tooltip(self, self._tooltip_html(self._values))

    @staticmethod
    def _tooltip_html(v: dict) -> str:
        """A styled hover card (Qt rich text): next-salah hero, location + Hijri
        date, then the day's times with the next one emphasised."""
        accent = "#cba6f7"
        dim = "#9399b2"
        if v.get("_empty"):
            return f"<div style=\"font-family:'Segoe UI'\">{v['compact']}</div>"
        rows = []
        for name, t in v["_times"]:
            if name == v["_next"]:
                rows.append(
                    f"<tr><td style='padding:2px 0;color:{accent};font-weight:700'>{name}</td>"
                    f"<td align='right' style='padding:2px 0 2px 22px;color:{accent};font-weight:700'>{t}</td></tr>"
                )
            else:
                rows.append(
                    f"<tr><td style='padding:2px 0'>{name}</td>"
                    f"<td align='right' style='padding:2px 0 2px 22px'>{t}</td></tr>"
                )
        return (
            "<div style=\"font-family:'Segoe UI'\">"
            f"<span style='font-size:19px;font-weight:700'>{v['next_salah']}</span><br>"
            f"<span style='font-size:12px;color:{accent};font-weight:600'>in {v['time_left']}</span>"
            f"<span style='font-size:12px;color:{dim}'> &#183; {v['next_time']}</span><br>"
            f"<span style='font-size:11px;color:{dim}'>{v['location']} &#183; {v['hijri_date']} "
            f"&#183; {v['method']} &#183; {v['asr']}</span>"
            f"<table cellspacing='0' style='margin-top:6px;font-size:12px'>{''.join(rows)}</table>"
            "</div>"
        )

    # ---------------------------------------------------------------- popup

    def _toggle_menu(self) -> None:
        self._show_menu()

    def _show_menu(self) -> None:
        self._menu = PopupWidget(
            self,
            self.config.menu.blur,
            self.config.menu.round_corners,
            self.config.menu.round_corners_type,
            self.config.menu.border_color,
        )
        self._menu.setProperty("class", "salah-times-menu")

        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self._body = QWidget()
        self._body.setProperty("class", "menu-body")
        body_layout = QVBoxLayout(self._body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        outer.addWidget(self._body)
        self._menu.setLayout(outer)

        self._populate_body()

        self._menu.adjustSize()
        self._menu.setPosition(
            alignment=self.config.menu.alignment,
            direction=self.config.menu.direction,
            offset_left=self.config.menu.offset_left,
            offset_top=self.config.menu.offset_top,
        )
        self._menu.show()

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
            else:
                sub = item.layout()
                if sub is not None:
                    SalahTimesWidget._clear_layout(sub)

    def _refresh_body(self) -> None:
        """Rebuild popup contents in place (no hide/show flicker)."""
        if self._menu is None or self._body is None:
            return
        try:
            self._populate_body()
            self._menu.adjustSize()
            self._menu.setPosition(
                alignment=self.config.menu.alignment,
                direction=self.config.menu.direction,
                offset_left=self.config.menu.offset_left,
                offset_top=self.config.menu.offset_top,
            )
        except RuntimeError:
            pass

    def _populate_body(self) -> None:
        layout = self._body.layout()
        self._clear_layout(layout)

        v = self._compute()

        # --- Header: title + time-format toggle ---------------------------
        header = QFrame()
        header.setProperty("class", "header")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(0)
        title = QLabel("Salah Times")
        title.setProperty("class", "title")
        hl.addWidget(title, 1)
        tf = self._time_format()
        for value in ("12h", "24h"):
            b = QPushButton(value)
            b.setProperty("class", f"toggle-button {'active' if tf == value else ''}".strip())
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(partial(self._set_time_format, value))
            hl.addWidget(b)
        layout.addWidget(header)

        if v["_empty"]:
            self._populate_empty(layout, v)
        else:
            self._populate_summary(layout, v)
            self._populate_times(layout, v)
            self._populate_locations(layout)

        # --- Add location -------------------------------------------------
        add = QPushButton("  Add location")  # nf-fa-plus
        add.setProperty("class", "add-location")
        add.setCursor(Qt.CursorShape.PointingHandCursor)
        add.clicked.connect(self._show_search_dialog)
        layout.addWidget(add)

    def _populate_empty(self, layout, v) -> None:
        box = QFrame()
        box.setProperty("class", "empty-state")
        bl = QVBoxLayout(box)
        icon = QLabel("")  # mosque glyph
        icon.setProperty("class", "empty-icon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg = QLabel("No location set.\nAdd one to see salah times.")
        msg.setProperty("class", "empty-text")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bl.addWidget(icon)
        bl.addWidget(msg)
        layout.addWidget(box)

    def _populate_summary(self, layout, v) -> None:
        box = QFrame()
        box.setProperty("class", "summary")
        bl = QVBoxLayout(box)
        bl.setSpacing(0)
        loc = QLabel(v["location"])
        loc.setProperty("class", "summary-location")
        nxt = QLabel(f"{v['next_salah']} in {v['time_left']} · {v['next_time']}")
        nxt.setProperty("class", "summary-next")
        hij = QLabel(f"{v['hijri_date']}  ·  {v['method']} · {v['asr']}")
        hij.setProperty("class", "summary-meta")
        bl.addWidget(loc)
        bl.addWidget(nxt)
        bl.addWidget(hij)
        layout.addWidget(box)

    def _populate_times(self, layout, v) -> None:
        box = QFrame()
        box.setProperty("class", "times")
        bl = QVBoxLayout(box)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(0)
        for name, t in v["_times"]:
            row = QFrame()
            is_next = name == v["_next"]
            row.setProperty("class", "time-row next" if is_next else "time-row")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            nlab = QLabel(name)
            nlab.setProperty("class", "time-name")
            tlab = QLabel(t)
            tlab.setProperty("class", "time-value")
            rl.addWidget(nlab, 1)
            rl.addWidget(tlab)
            bl.addWidget(row)
        layout.addWidget(box)

    def _populate_locations(self, layout) -> None:
        section = QLabel("LOCATIONS")
        section.setProperty("class", "section-label")
        layout.addWidget(section)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setProperty("class", "locations-scroll")
        container = QWidget()
        container.setProperty("class", "locations-container")
        cl = QVBoxLayout(container)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        selected = self._selected_key()
        for key in self._locations():
            cl.addWidget(self._build_location_row(key, key == selected))
        cl.addStretch(1)
        scroll.setWidget(container)
        # cap the height so long lists scroll instead of growing forever
        scroll.setMaximumHeight(190)
        layout.addWidget(scroll)

    def _build_location_row(self, key: str, active: bool) -> QFrame:
        loc = self._locations()[key]
        row = QFrame()
        row.setProperty("class", "location-item active" if active else "location-item")
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)

        info = QWidget()
        info.setCursor(Qt.CursorShape.PointingHandCursor)
        il = QVBoxLayout(info)
        il.setContentsMargins(0, 0, 0, 0)
        il.setSpacing(0)
        country = (loc.get("country_code") or "").upper()
        name = QLabel(f"{loc.get('city', key)}{(', ' + country) if country else ''}")
        name.setProperty("class", "name")
        method_opt = methods.parse_method_option(loc.get("method") or "auto")
        method_key = methods.resolve_auto_method(country) if method_opt == "auto" else method_opt
        asr = "Hanafi" if loc.get("asr_school") == "hanafi" else "Standard"
        sub = QLabel(f"{methods.method_label(method_key)} · {asr}")
        sub.setProperty("class", "detail")
        il.addWidget(name)
        il.addWidget(sub)
        info.mousePressEvent = lambda e, k=key: self._select_location(k)
        rl.addWidget(info, 1)

        edit = QPushButton(ICON_EDIT)
        edit.setProperty("class", "icon-button edit-button")
        edit.setCursor(Qt.CursorShape.PointingHandCursor)
        edit.clicked.connect(partial(self._show_edit_dialog, key))
        rl.addWidget(edit)

        delete = QPushButton(ICON_DELETE)
        delete.setProperty("class", "icon-button delete-button")
        delete.setCursor(Qt.CursorShape.PointingHandCursor)
        delete.clicked.connect(partial(self._delete_location, key))
        rl.addWidget(delete)

        return row

    # --------------------------------------------------------- mutations

    def _select_location(self, key: str) -> None:
        self._data["selected_location"] = key
        self._save_data()
        SalahTimesWidget.update_all()
        self._refresh_body()

    def _delete_location(self, key: str) -> None:
        locs = self._locations()
        if key in locs:
            del locs[key]
            if self._data.get("selected_location") == key:
                self._data["selected_location"] = next(iter(locs), None)
            self._save_data()
            SalahTimesWidget.update_all()
        self._refresh_body()

    def _set_time_format(self, value: str) -> None:
        self._data["time_format"] = value
        self._save_data()
        SalahTimesWidget.update_all()
        self._refresh_body()

    # ----------------------------------------------------------- dialogs

    def _show_search_dialog(self) -> None:
        # Qt.Popup grabs input, so the menu must be hidden while a modal dialog
        # is open (same pattern as the todo widget).
        if self._menu is not None:
            self._menu.hide()
        dialog = QDialog()
        dialog.setWindowTitle("Add location")
        dialog.setMinimumSize(380, 340)
        dialog.setProperty("class", "salah-times-dialog")
        dialog.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.CustomizeWindowHint
        )
        dl = QVBoxLayout(dialog)

        desc = QLabel("Search for a city. Timezone and calculation method are set automatically.")
        desc.setWordWrap(True)
        desc.setProperty("class", "search-description")
        dl.addWidget(desc)

        search = QLineEdit()
        search.setPlaceholderText("Search a city…  (e.g. London, GB)")
        search.setProperty("class", "search-input")
        dl.addWidget(search)

        status = QLabel("")
        status.setProperty("class", "search-status")
        dl.addWidget(status)

        results = QListWidget()
        results.setProperty("class", "search-results")
        dl.addWidget(results, 1)

        manual_btn = QPushButton("Enter coordinates manually instead")
        manual_btn.setProperty("class", "link-button")
        manual_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        manual_btn.clicked.connect(lambda: (dialog.accept(), self._show_edit_dialog(None)))
        dl.addWidget(manual_btn)

        fetcher = GeocodingFetcher(dialog)
        debounce = QTimer(dialog)
        debounce.setSingleShot(True)
        debounce.setInterval(350)

        def run_search():
            q = search.text().strip()
            if len(q) >= 2:
                status.setText("Searching…")
                fetcher.search(q)
            else:
                results.clear()
                status.setText("")

        debounce.timeout.connect(run_search)
        search.textChanged.connect(lambda: debounce.start())

        def on_results(items: list):
            results.clear()
            status.setText("" if items else "No matches")
            for r in items:
                label = ", ".join(x for x in (r.get("name", ""), r.get("admin1", ""), r.get("country", "")) if x)
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, r)
                results.addItem(item)

        fetcher.results_ready.connect(on_results)
        results.itemClicked.connect(
            lambda item: (self._add_from_geocoding(item.data(Qt.ItemDataRole.UserRole)), dialog.accept())
        )

        search.setFocus()
        dialog.exec()
        self._show_menu()

    def _add_from_geocoding(self, r: dict) -> None:
        name = r.get("name", "Location")
        key = name
        locs = self._locations()
        i = 2
        while key in locs:
            key = f"{name} ({i})"
            i += 1
        locs[key] = {
            "latitude": r.get("latitude"),
            "longitude": r.get("longitude"),
            "city": name,
            "country_code": (r.get("country_code") or "").upper(),
            "timezone": r.get("timezone"),
            "method": "auto",
            "asr_school": "standard",
        }
        self._data["locations"] = locs
        self._data["selected_location"] = key
        self._save_data()
        SalahTimesWidget.update_all()

    def _show_edit_dialog(self, key: str | None) -> None:
        loc = dict(self._locations().get(key, {})) if key else {}
        if self._menu is not None:
            self._menu.hide()
        dialog = QDialog()
        dialog.setWindowTitle("Edit location" if key else "Add location")
        dialog.setMinimumWidth(380)
        dialog.setProperty("class", "salah-times-dialog")
        dialog.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.CustomizeWindowHint
        )
        dl = QVBoxLayout(dialog)

        def field(text, widget):
            lab = QLabel(text)
            lab.setProperty("class", "field-label")
            dl.addWidget(lab)
            dl.addWidget(widget)

        name_in = QLineEdit(str(key or loc.get("city", "")))
        name_in.setProperty("class", "text-field")
        field("Name", name_in)

        coords_row = QHBoxLayout()
        lat_in = QDoubleSpinBox()
        lat_in.setDecimals(6)
        lat_in.setRange(-90.0, 90.0)
        lat_in.setValue(float(loc.get("latitude", 0.0) or 0.0))
        lon_in = QDoubleSpinBox()
        lon_in.setDecimals(6)
        lon_in.setRange(-180.0, 180.0)
        lon_in.setValue(float(loc.get("longitude", 0.0) or 0.0))
        lat_col = QVBoxLayout()
        lat_lab = QLabel("Latitude")
        lat_lab.setProperty("class", "field-label")
        lat_col.addWidget(lat_lab)
        lat_col.addWidget(lat_in)
        lon_col = QVBoxLayout()
        lon_lab = QLabel("Longitude")
        lon_lab.setProperty("class", "field-label")
        lon_col.addWidget(lon_lab)
        lon_col.addWidget(lon_in)
        coords_row.addLayout(lat_col)
        coords_row.addLayout(lon_col)
        dl.addLayout(coords_row)

        country_in = _searchable_combo(
            [""] + geo.country_names(),
            geo.code_to_name(loc.get("country_code") or ""),
            "Type to search…",
        )
        field("Country (used by auto method)", country_in)

        tz_in = _searchable_combo(
            [""] + geo.timezones(),
            loc.get("timezone") or "",
            "Type to search… (blank = system local)",
        )
        field("Timezone", tz_in)

        method_in = QComboBox()
        method_in.addItems(methods.METHOD_OPTIONS)
        raw_method = loc.get("method") or "auto"
        method_in.setCurrentText("auto" if raw_method == "auto" else methods.parse_method_option(raw_method))
        field("Calculation method", method_in)

        asr_in = QComboBox()
        asr_in.addItems(["standard", "hanafi"])
        asr_in.setCurrentText(loc.get("asr_school", "standard"))
        field("Asr school", asr_in)

        offsets = loc.get("offsets") or {}
        offset_spins: dict[str, QSpinBox] = {}
        off_label = QLabel("Per-salah offsets (minutes)")
        off_label.setProperty("class", "field-label")
        dl.addWidget(off_label)
        for k in OFFSET_KEYS:
            row = QHBoxLayout()
            tag = QLabel(k.capitalize())
            tag.setProperty("class", "offset-name")
            spin = QSpinBox()
            spin.setRange(-120, 120)
            spin.setValue(int(offsets.get(k, 0) or 0))
            spin.setProperty("class", "offset-spin")
            row.addWidget(tag, 1)
            row.addWidget(spin)
            dl.addLayout(row)
            offset_spins[k] = spin

        buttons = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.setProperty("class", "button cancel")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(dialog.reject)
        save = QPushButton("Save")
        save.setProperty("class", "button save")
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        dl.addLayout(buttons)

        def do_save():
            new_name = name_in.text().strip() or "Location"
            new_offsets = {k: s.value() for k, s in offset_spins.items() if s.value() != 0}
            entry = {
                "latitude": lat_in.value(),
                "longitude": lon_in.value(),
                "city": new_name,
                "country_code": geo.name_to_code(country_in.currentText()),
                "timezone": tz_in.currentText().strip(),
                "method": method_in.currentText(),
                "asr_school": asr_in.currentText(),
            }
            if new_offsets:
                entry["offsets"] = new_offsets
            locs = self._locations()
            if key and key != new_name:
                locs.pop(key, None)
            locs[new_name] = entry
            self._data["locations"] = locs
            self._data["selected_location"] = new_name
            self._save_data()
            SalahTimesWidget.update_all()
            dialog.accept()

        save.clicked.connect(do_save)
        name_in.setFocus()
        dialog.exec()
        self._show_menu()
