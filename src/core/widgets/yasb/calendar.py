import logging
import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices

from core.utils.tooltip import set_tooltip
from core.utils.utilities import refresh_widget_style
from core.validation.widgets.yasb.calendar import CalendarConfig
from core.widgets.base import BaseWidget

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

ZOOM_RE = re.compile(r"https://[\w.-]+\.zoom\.us/(?:j|my|w)/[^\s<>\"'\)]+")
TEAMS_RE = re.compile(r"https://teams\.microsoft\.com/l/meetup-join/[^\s<>\"'\)]+")
MEET_RE = re.compile(r"https://meet\.google\.com/[a-z]{3}-[a-z]{4}-[a-z]{3}", re.I)


def _classify_url(url: str) -> str:
    if "meet.google.com" in url:
        return "meet"
    if "zoom.us" in url:
        return "zoom"
    if "teams.microsoft.com" in url or "teams.live.com" in url:
        return "teams"
    return "other"


def extract_meeting_url(event: dict[str, Any]) -> tuple[str | None, str]:
    """Pick the best join URL out of a Google Calendar event payload.

    Priority: hangoutLink → conferenceData video entry point → regex over
    location + description. Returns (url, kind) where kind ∈
    {"meet","zoom","teams","other","none"}.
    """
    hangout = event.get("hangoutLink")
    if hangout:
        return hangout, "meet"

    conf = event.get("conferenceData") or {}
    for ep in conf.get("entryPoints") or []:
        if ep.get("entryPointType") == "video":
            uri = ep.get("uri")
            if uri:
                return uri, _classify_url(uri)

    haystack = (event.get("location") or "") + "\n" + (event.get("description") or "")
    for rx, kind in ((MEET_RE, "meet"), (ZOOM_RE, "zoom"), (TEAMS_RE, "teams")):
        m = rx.search(haystack)
        if m:
            return m.group(0), kind

    return None, "none"


def _parse_event_time(slot: dict[str, Any] | None) -> datetime | None:
    if not slot:
        return None
    if "dateTime" in slot:
        # RFC 3339 — fromisoformat handles offsets including 'Z' on Python 3.11+
        return datetime.fromisoformat(slot["dateTime"].replace("Z", "+00:00"))
    if "date" in slot:
        # All-day event: anchor to UTC midnight so comparisons work
        return datetime.fromisoformat(slot["date"]).replace(tzinfo=UTC)
    return None


def _format_countdown(now: datetime, start: datetime, end: datetime) -> tuple[str, str]:
    """Return (countdown_text, status). status ∈ {upcoming, live, ended}."""
    if now >= end:
        return "ended", "ended"
    if now >= start:
        elapsed = int((now - start).total_seconds() // 60)
        if elapsed <= 0:
            return "now", "live"
        return f"started {elapsed}m ago", "live"
    delta = start - now
    secs = int(delta.total_seconds())
    if secs < 60:
        return "in <1m", "upcoming"
    mins = secs // 60
    if mins < 60:
        return f"in {mins}m", "upcoming"
    hours, rem = divmod(mins, 60)
    if rem == 0:
        return f"in {hours}h", "upcoming"
    return f"in {hours}h {rem}m", "upcoming"


class _FetchSignals(QObject):
    events_ready = pyqtSignal(list)
    no_event = pyqtSignal()
    needs_setup = pyqtSignal(str)
    error = pyqtSignal(str)


class _FetchTask(QRunnable):
    def __init__(self, config: CalendarConfig, signals: _FetchSignals):
        super().__init__()
        self._config = config
        self._signals = signals
        self.setAutoDelete(True)

    def run(self) -> None:  # runs on a thread-pool worker
        try:
            try:
                from google.auth.transport.requests import Request
                from google.oauth2.credentials import Credentials
                from google_auth_oauthlib.flow import InstalledAppFlow
                from googleapiclient.discovery import build
            except ImportError as e:
                self._signals.error.emit(f"Missing google API deps: {e}")
                return

            creds_path = Path(os.path.expanduser(self._config.credentials_path))
            token_path = Path(os.path.expanduser(self._config.token_path))

            creds = None
            if token_path.exists():
                try:
                    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
                except Exception as e:
                    logging.warning("CalendarWidget: ignoring unreadable token at %s: %s", token_path, e)
                    creds = None

            if creds and not creds.valid and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    logging.warning("CalendarWidget: token refresh failed: %s", e)
                    creds = None

            if not creds or not creds.valid:
                if not creds_path.exists():
                    self._signals.needs_setup.emit(str(creds_path))
                    return
                flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
                # Blocks this worker thread while the user authorises in browser.
                creds = flow.run_local_server(port=0)
                token_path.parent.mkdir(parents=True, exist_ok=True)
                token_path.write_text(creds.to_json(), encoding="utf-8")

            service = build(
                "calendar",
                "v3",
                credentials=creds,
                cache_discovery=False,
                static_discovery=False,
            )
            now = datetime.now(UTC)
            grace = timedelta(minutes=self._config.grace_period_minutes)
            time_min = (now - grace).isoformat()
            cutoff = None
            if self._config.look_ahead_minutes > 0:
                cutoff = now + timedelta(minutes=self._config.look_ahead_minutes)

            collected: list[tuple[datetime, dict[str, Any]]] = []
            for cid in self._config.calendar_ids:
                list_kwargs: dict[str, Any] = dict(
                    calendarId=cid,
                    timeMin=time_min,
                    maxResults=10,
                    singleEvents=True,
                    orderBy="startTime",
                )
                if cutoff is not None:
                    list_kwargs["timeMax"] = cutoff.isoformat()
                try:
                    events = service.events().list(**list_kwargs).execute()
                except Exception as e:
                    logging.warning("CalendarWidget: list failed for %s: %s", cid, e)
                    continue
                for ev in events.get("items", []):
                    start_slot = ev.get("start") or {}
                    end_slot = ev.get("end") or {}
                    if self._config.skip_all_day and "dateTime" not in start_slot:
                        continue
                    start = _parse_event_time(start_slot)
                    end = _parse_event_time(end_slot)
                    if not start or not end or end <= now:
                        continue
                    url, kind = extract_meeting_url(ev)
                    collected.append(
                        (
                            start,
                            {
                                "title": ev.get("summary", "(no title)"),
                                "start": start.isoformat(),
                                "end": end.isoformat(),
                                "meeting_url": url,
                                "meeting_kind": kind,
                                "html_link": ev.get("htmlLink", ""),
                                "location": ev.get("location", "") or "",
                                "calendar_id": cid,
                            },
                        )
                    )

            collected.sort(key=lambda pair: pair[0])
            top = [ev for _, ev in collected[: self._config.tooltip_event_count]]
            if top:
                self._signals.events_ready.emit(top)
            else:
                self._signals.no_event.emit()
        except Exception as e:
            logging.exception("CalendarWidget: fetch failed")
            self._signals.error.emit(str(e))


class CalendarWidget(BaseWidget):
    validation_schema = CalendarConfig

    def __init__(self, config: CalendarConfig):
        super().__init__(
            timer_interval=config.update_interval * 1000,
            class_name=f"calendar-widget {config.class_name}".strip(),
        )
        self.config = config
        self._label_content = config.label
        self._label_alt_content = config.label_alt
        self._show_alt_label = False
        self._upcoming_events: list[dict[str, Any]] = []
        self._state: str = "loading"
        self._error: str | None = None
        self._fetch_in_flight = False

        self._init_container()
        self.build_widget_label(self._label_content, self._label_alt_content)

        self._signals = _FetchSignals()
        self._signals.events_ready.connect(self._on_events_ready)
        self._signals.no_event.connect(self._on_no_event)
        self._signals.needs_setup.connect(self._on_needs_setup)
        self._signals.error.connect(self._on_error)
        self._pool = QThreadPool.globalInstance()

        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._on_tick)
        self._tick_timer.start(config.tick_interval)

        self.register_callback("join_meeting", self._cb_join_meeting)
        self.register_callback("open_event", self._cb_open_event)
        self.register_callback("toggle_label", self._cb_toggle_label)
        self.register_callback("refresh", self._cb_refresh)
        self.register_callback("open_setup", self._cb_open_setup)
        self.callback_left = config.callbacks.on_left
        self.callback_middle = config.callbacks.on_middle
        self.callback_right = config.callbacks.on_right
        self.callback_timer = "refresh"

        self.start_timer()

    # ---- fetch lifecycle ------------------------------------------------

    def _cb_refresh(self) -> None:
        if self._fetch_in_flight:
            return
        self._fetch_in_flight = True
        self._pool.start(_FetchTask(self.config, self._signals))

    def _on_events_ready(self, events: list[dict[str, Any]]) -> None:
        self._fetch_in_flight = False
        self._upcoming_events = events
        self._state = "ok"
        self._error = None
        self._update_label()

    def _on_no_event(self) -> None:
        self._fetch_in_flight = False
        self._upcoming_events = []
        self._state = "empty"
        self._error = None
        self._update_label()

    def _on_needs_setup(self, creds_path: str) -> None:
        self._fetch_in_flight = False
        self._upcoming_events = []
        self._state = "setup"
        self._error = creds_path
        self._update_label()

    def _on_error(self, msg: str) -> None:
        self._fetch_in_flight = False
        self._error = msg
        if not self._upcoming_events:
            self._state = "error"
        # Keep showing last good events if we have any — just record the error.
        self._update_label()

    def _on_tick(self) -> None:
        if self._state == "ok" and self._upcoming_events:
            self._update_label()

    # ---- rendering ------------------------------------------------------

    def _build_tokens(self) -> dict[str, str]:
        if not self._upcoming_events:
            return {}
        ev = self._upcoming_events[0]
        now = datetime.now(UTC)
        start = datetime.fromisoformat(ev["start"])
        end = datetime.fromisoformat(ev["end"])
        countdown, status = _format_countdown(now, start, end)
        kind = ev["meeting_kind"]
        icons = self.config.icons.model_dump()
        icon = icons.get(kind) or icons.get("calendar") or ""
        title = ev["title"] or "(no title)"
        max_len = self.config.max_title_length
        if len(title) > max_len:
            title = title[: max_len - 1] + "…"
        try:
            start_time = start.astimezone().strftime("%H:%M")
        except Exception:
            start_time = "??:??"
        return {
            "{title}": title,
            "{start_time}": start_time,
            "{countdown}": countdown,
            "{status}": status,
            "{meeting_kind}": kind,
            "{icon}": icon,
        }

    def _frame_classes(self) -> str:
        parts = ["widget", "calendar-widget", self.config.class_name, self._state]
        if self._state == "ok" and self._upcoming_events:
            ev = self._upcoming_events[0]
            parts.append(ev.get("meeting_kind", "none"))
            try:
                now = datetime.now(UTC)
                start = datetime.fromisoformat(ev["start"])
                end = datetime.fromisoformat(ev["end"])
                _, status = _format_countdown(now, start, end)
                parts.append(status)
            except Exception:
                pass
        if self._error and self._state == "ok":
            parts.append("stale")
        return " ".join(p for p in parts if p)

    def _update_label(self) -> None:
        if self._state == "empty" and self.config.hide_when_empty:
            self.hide()
            return
        if not self.isVisible():
            self.show()

        if self._state == "ok":
            tpl = self._label_alt_content if self._show_alt_label else self._label_content
            tokens = self._build_tokens()
        elif self._state == "setup":
            tpl, tokens = self.config.auth_label, {}
        elif self._state == "empty":
            tpl, tokens = self.config.empty_label, {}
        else:  # loading / error
            tpl, tokens = self.config.empty_label, {}

        rendered = tpl
        for k, v in tokens.items():
            rendered = rendered.replace(k, str(v))

        active_widgets = (
            self._widgets_alt if self._show_alt_label and self._widgets_alt and self._state == "ok" else self._widgets
        )
        if active_widgets:
            parts = re.split(r"(<span.*?>.*?</span>)", rendered)
            parts = [p for p in parts if p and p.strip()]
            for i, part in enumerate(parts):
                if i >= len(active_widgets):
                    break
                if "<span" in part and "</span>" in part:
                    inner = re.sub(r"<span.*?>|</span>", "", part).strip()
                    active_widgets[i].setText(inner)
                else:
                    active_widgets[i].setText(part)
            # If there are more widgets than parts, blank the leftovers
            for j in range(len(parts), len(active_widgets)):
                active_widgets[j].setText("")

        self._widget_frame.setProperty("class", self._frame_classes())
        refresh_widget_style(self._widget_frame)

        if self.config.tooltip:
            self._update_tooltip()

    def _update_tooltip(self) -> None:
        if self._state == "setup":
            set_tooltip(
                self,
                f"Google Calendar credentials missing.<br>Drop your OAuth client JSON at:<br>{self._error}",
            )
            return
        if self._state == "error":
            set_tooltip(self, f"Calendar error:<br>{self._error or 'unknown'}")
            return
        if not self._upcoming_events:
            set_tooltip(self, self.config.empty_label)
            return

        blocks: list[str] = []
        for i, ev in enumerate(self._upcoming_events):
            try:
                start = datetime.fromisoformat(ev["start"]).astimezone()
                end = datetime.fromisoformat(ev["end"]).astimezone()
                when = f"{start.strftime('%a %b %d, %H:%M')} – {end.strftime('%H:%M')}"
            except Exception:
                when = ""
            block = [f"<strong>{ev['title']}</strong>", when]
            if ev.get("location"):
                block.append(f"@ {ev['location']}")
            if i == 0:
                if ev.get("meeting_url"):
                    block.append(f"Click to join ({ev['meeting_kind']})")
                elif ev.get("html_link"):
                    block.append("Click to open in Google Calendar")
            blocks.append("<br>".join(line for line in block if line))
        set_tooltip(self, "<br><br>".join(blocks))

    # ---- click handlers -------------------------------------------------

    def _cb_toggle_label(self) -> None:
        self._show_alt_label = not self._show_alt_label
        for w in self._widgets:
            w.setVisible(not self._show_alt_label)
        for w in self._widgets_alt:
            w.setVisible(self._show_alt_label)
        self._update_label()

    def _cb_join_meeting(self) -> None:
        if self._state == "setup":
            self._cb_open_setup()
            return
        if not self._upcoming_events:
            return
        ev = self._upcoming_events[0]
        url = ev.get("meeting_url") or ev.get("html_link")
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def _cb_open_event(self) -> None:
        if not self._upcoming_events:
            return
        ev = self._upcoming_events[0]
        if ev.get("html_link"):
            QDesktopServices.openUrl(QUrl(ev["html_link"]))

    def _cb_open_setup(self) -> None:
        QDesktopServices.openUrl(QUrl(self.config.setup_url))
