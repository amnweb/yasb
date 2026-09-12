import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from PyQt6.QtCore import QObject, QPoint, QRunnable, Qt, QThreadPool, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QPainter, QPaintEvent
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from core.ui.components.loader import LoaderLine
from core.utils.tooltip import set_tooltip
from core.utils.utilities import PopupWidget, refresh_widget_style
from core.validation.widgets.yasb.calendar import CalendarConfig, Corner
from core.widgets.base import BaseWidget
from core.widgets.services.google_calendar import auth as gcal_auth
from core.widgets.services.google_calendar.auth_dialog import GoogleCalendarAuthDialog

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
        return datetime.fromisoformat(slot["dateTime"].replace("Z", "+00:00"))
    if "date" in slot:
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


class _NotificationLabel(QLabel):
    """QLabel that can paint a coloured dot in any corner."""

    def __init__(self, *args: Any, color: str, corner: Corner, margin: list[int], **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._show_dot = False
        self._color = color
        self._corner = corner
        self._margin = margin

    def show_dot(self, enabled: bool) -> None:
        if enabled == self._show_dot:
            return
        self._show_dot = enabled
        self.update()

    def paintEvent(self, a0: QPaintEvent | None) -> None:
        super().paintEvent(a0)
        if not self._show_dot:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(self._color))
        painter.setPen(Qt.PenStyle.NoPen)
        radius = 6
        mx, my = self._margin[0], self._margin[1]
        if self._corner == Corner.TOP_LEFT:
            x, y = mx, my
        elif self._corner == Corner.TOP_RIGHT:
            x, y = self.width() - radius - mx, my
        elif self._corner == Corner.BOTTOM_LEFT:
            x, y = mx, self.height() - radius - my
        else:  # BOTTOM_RIGHT
            x, y = self.width() - radius - mx, self.height() - radius - my
        painter.drawEllipse(QPoint(x + radius // 2, y + radius // 2), radius // 2, radius // 2)


class _FetchSignals(QObject):
    events_ready = pyqtSignal(list)
    no_event = pyqtSignal()
    needs_setup = pyqtSignal()
    error = pyqtSignal(str)


class _FetchTask(QRunnable):
    def __init__(self, config: CalendarConfig, signals: _FetchSignals):
        super().__init__()
        self._config = config
        self._signals = signals
        self.setAutoDelete(True)

    def run(self) -> None:
        try:
            try:
                from googleapiclient.discovery import build
            except ImportError as e:
                self._signals.error.emit(f"Missing google API deps: {e}")
                return

            creds = gcal_auth.get_creds()
            if creds is None:
                self._signals.needs_setup.emit()
                return

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
            top = [ev for _, ev in collected[: self._config.menu.event_count]]
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
        self._auth_dialog: GoogleCalendarAuthDialog | None = None
        self._menu: PopupWidget | None = None
        self._dot_labels: list[_NotificationLabel] = []
        self._dot_labels_alt: list[_NotificationLabel] = []

        self._init_container()
        self._build_labels(self._label_content, self._label_alt_content)

        self._loader_line = LoaderLine(self)
        self._loader_line.attach_to_widget(self._widget_frame)

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
        self.register_callback("toggle_menu", self._cb_toggle_menu)
        self.callback_left = config.callbacks.on_left
        self.callback_middle = config.callbacks.on_middle
        self.callback_right = config.callbacks.on_right
        self.callback_timer = "refresh"

        self.start_timer()

    # ---- label construction --------------------------------------------

    def _build_labels(self, content: str, content_alt: str) -> None:
        self._widgets = self._make_label_row(content, is_alt=False)
        self._widgets_alt = self._make_label_row(content_alt, is_alt=True)

    def _make_label_row(self, content: str, is_alt: bool) -> list[QLabel]:
        widgets: list[QLabel] = []
        for raw in re.split(r"(<span.*?>.*?</span>)", content):
            part = raw.strip()
            if not part:
                continue
            if "<span" in part and "</span>" in part:
                m = re.search(r'class=(["\'])([^"\']+?)\1', part)
                cls = m.group(2) if m else "icon"
                inner = re.sub(r"<span.*?>|</span>", "", part).strip()
                lbl = _NotificationLabel(
                    inner,
                    color=self.config.notification_dot.color,
                    corner=self.config.notification_dot.corner,
                    margin=self.config.notification_dot.margin,
                )
                lbl.setProperty("class", cls)
                if is_alt:
                    self._dot_labels_alt.append(lbl)
                else:
                    self._dot_labels.append(lbl)
            else:
                lbl = QLabel(part)
                lbl.setProperty("class", "label alt" if is_alt else "label")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._widget_container_layout.addWidget(lbl)
            widgets.append(lbl)
            lbl.setVisible(not is_alt)
        return widgets

    # ---- fetch lifecycle ------------------------------------------------

    def _cb_refresh(self) -> None:
        if self._fetch_in_flight:
            return
        self._fetch_in_flight = True
        self._loader_line.start()
        self._pool.start(_FetchTask(self.config, self._signals))

    def _on_events_ready(self, events: list[dict[str, Any]]) -> None:
        self._fetch_in_flight = False
        self._loader_line.stop()
        self._upcoming_events = events
        self._state = "ok"
        self._error = None
        self._update_label()

    def _on_no_event(self) -> None:
        self._fetch_in_flight = False
        self._loader_line.stop()
        self._upcoming_events = []
        self._state = "empty"
        self._error = None
        self._update_label()

    def _on_needs_setup(self) -> None:
        self._fetch_in_flight = False
        self._loader_line.stop()
        self._upcoming_events = []
        self._state = "setup"
        self._error = None
        self._update_label()

    def _on_error(self, msg: str) -> None:
        self._fetch_in_flight = False
        self._loader_line.stop()
        self._error = msg
        if not self._upcoming_events:
            self._state = "error"
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

    def _should_show_dot(self) -> bool:
        if not self.config.notification_dot.enabled:
            return False
        if self._state != "ok" or not self._upcoming_events:
            return False
        ev = self._upcoming_events[0]
        try:
            now = datetime.now(UTC)
            start = datetime.fromisoformat(ev["start"])
            end = datetime.fromisoformat(ev["end"])
        except Exception:
            return False
        if now >= start and now < end:
            return True
        threshold = timedelta(minutes=self.config.notification_dot.threshold_minutes)
        return start - now <= threshold

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
            for j in range(len(parts), len(active_widgets)):
                active_widgets[j].setText("")

        show_dot = self._should_show_dot()
        active_dots = self._dot_labels_alt if self._show_alt_label else self._dot_labels
        for dot in active_dots:
            dot.show_dot(show_dot)

        self._widget_frame.setProperty("class", self._frame_classes())
        refresh_widget_style(self._widget_frame)

        if self.config.tooltip:
            self._update_tooltip()

    def _update_tooltip(self) -> None:
        if self._state == "setup":
            set_tooltip(self, "Google Calendar: click to sign in")
            return
        if self._state == "error":
            set_tooltip(self, f"Calendar error:<br>{self._error or 'unknown'}")
            return
        if not self._upcoming_events:
            set_tooltip(self, self.config.empty_label)
            return
        blocks: list[str] = []
        for ev in self._upcoming_events[: self.config.tooltip_event_count]:
            try:
                start = datetime.fromisoformat(ev["start"]).astimezone()
                end = datetime.fromisoformat(ev["end"]).astimezone()
                when = f"{start.strftime('%a %b %d, %H:%M')} – {end.strftime('%H:%M')}"
            except Exception:
                when = ""
            lines = [f"<strong>{ev['title']}</strong>", when]
            if ev.get("location"):
                lines.append(f"@ {ev['location']}")
            blocks.append("<br>".join(line for line in lines if line))
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
            self._open_auth_dialog()
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

    def _cb_toggle_menu(self) -> None:
        if self._menu is not None and self._menu.isVisible():
            self._menu.hide()
            return
        if self._state == "setup":
            self._open_auth_dialog()
            return
        self._show_menu()

    # ---- auth dialog ----------------------------------------------------

    def _open_auth_dialog(self) -> None:
        if self._auth_dialog is not None:
            self._auth_dialog.raise_()
            self._auth_dialog.activateWindow()
            return
        self._auth_dialog = GoogleCalendarAuthDialog()
        self._auth_dialog.auth_completed.connect(self._on_auth_completed)
        self._auth_dialog.finished.connect(self._on_auth_dialog_closed)
        self._auth_dialog.show()

    def _on_auth_completed(self) -> None:
        self._cb_refresh()

    def _on_auth_dialog_closed(self, *_: Any) -> None:
        self._auth_dialog = None

    # ---- popup menu -----------------------------------------------------

    def _show_menu(self) -> None:
        self._menu = PopupWidget(
            self,
            self.config.menu.blur,
            self.config.menu.round_corners,
            self.config.menu.round_corners_type,
            self.config.menu.border_color,
        )
        self._menu.setProperty("class", "calendar-menu")

        main_layout = QVBoxLayout(self._menu)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel("<span style='font-weight:bold'>Google Calendar</span>")
        header.setProperty("class", "header")
        main_layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            """
            QScrollArea { background: transparent; border: none; border-radius:0; }
            QScrollBar:vertical { border: none; background: transparent; width: 4px; }
            QScrollBar::handle:vertical { background: rgba(255,255,255,0.2); min-height: 10px; border-radius: 2px; }
            QScrollBar::handle:vertical:hover { background: rgba(255,255,255,0.35); }
            QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical { height: 0; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
            """
        )
        main_layout.addWidget(scroll)

        body = QWidget()
        body.setProperty("class", "contents")
        body_layout = QVBoxLayout(body)
        body_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        events = self._upcoming_events
        if events:
            section = QFrame()
            section.setProperty("class", "section")
            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setSpacing(0)
            count = len(events)
            for index, ev in enumerate(events):
                pos: list[str] = []
                if index == 0:
                    pos.append("first")
                if index == count - 1:
                    pos.append("last")
                section_layout.addWidget(self._build_menu_row(ev, pos, parent=section))
            body_layout.addWidget(section)
        else:
            empty = QLabel("No upcoming events")
            empty.setProperty("class", "empty")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            body_layout.addWidget(empty)

        scroll.setWidget(body)

        self._menu.adjustSize()
        self._menu.setPosition(
            alignment=self.config.menu.alignment,
            direction=self.config.menu.direction,
            offset_left=self.config.menu.offset_left,
            offset_top=self.config.menu.offset_top,
        )
        self._menu.show()

    def _build_menu_row(self, ev: dict[str, Any], position_classes: list[str], parent: QWidget) -> QFrame:
        kind = ev.get("meeting_kind", "none")
        icons = self.config.icons.model_dump()
        icon_text = icons.get(kind) or icons.get("calendar") or ""

        try:
            now = datetime.now(UTC)
            start = datetime.fromisoformat(ev["start"])
            end = datetime.fromisoformat(ev["end"])
            when = f"{start.astimezone().strftime('%a %H:%M')} – {end.astimezone().strftime('%H:%M')}"
            countdown, status = _format_countdown(now, start, end)
        except Exception:
            when = ""
            countdown, status = "", "upcoming"

        classes = ["item", kind, status, *position_classes]
        container = QFrame(parent)
        container.setProperty("class", " ".join(dict.fromkeys(c for c in classes if c)))

        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        if icon_text:
            icon_label = QLabel(icon_text)
            icon_label.setProperty("class", f"icon {kind}")
            row.addWidget(icon_label)

        text = QWidget()
        text_layout = QVBoxLayout(text)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(0)
        title_label = QLabel(ev["title"] or "(no title)")
        title_label.setProperty("class", "title")
        text_layout.addWidget(title_label)
        meta_label = QLabel(f"{when}  •  {countdown}".strip(" •"))
        meta_label.setProperty("class", "description")
        text_layout.addWidget(meta_label)
        row.addWidget(text, 1)

        url = ev.get("meeting_url")
        link = ev.get("html_link") or ""
        if url:
            join = QLabel("Join")
            join.setProperty("class", "join")
            join.setCursor(Qt.CursorShape.PointingHandCursor)
            join.mousePressEvent = lambda _e, u=url: self._on_menu_link(u)
            row.addWidget(join)
        elif link:
            open_lbl = QLabel("Open")
            open_lbl.setProperty("class", "open")
            open_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
            open_lbl.mousePressEvent = lambda _e, u=link: self._on_menu_link(u)
            row.addWidget(open_lbl)

        # Click anywhere on the row opens the event in Google Calendar
        if link:
            container.mousePressEvent = lambda _e, u=link: self._on_menu_link(u)

        return container

    def _on_menu_link(self, url: str) -> None:
        QDesktopServices.openUrl(QUrl(url))
        if self._menu is not None:
            self._menu.hide()
