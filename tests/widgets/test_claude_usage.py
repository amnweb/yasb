import copy
import json
import time
from collections.abc import Callable, Iterator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from PyQt6.QtCore import QMetaObject, QObject, QTimer, QUrl
from PyQt6.QtQml import QQmlComponent, QQmlEngine, QQmlError, QQmlProperty
from PyQt6.QtQuick import QQuickItem
from PyQt6.QtWidgets import QApplication

from core.qml_types import register_qml_types
from core.services.claude_usage import history as history_module
from core.services.claude_usage import usage as usage_module
from core.services.claude_usage.api import STATUS_URL, USAGE_URL, parse_usage, read_credentials
from core.services.claude_usage.history import HISTORY_FILE, compact, model_name, scan, summarize
from core.services.claude_usage.usage import (
    USAGE_FILE,
    ClaudeUsageMonitor,
    HistoryFeed,
    StatusFeed,
    UsageFeed,
)
from core.utils.system import app_data_path
from core.widget_files import BUILTIN_WIDGETS_DIR
from settings import QML_IMPORT_PATH
from tests.support.qt import find_item, wait

TOKEN = "sk-ant-oat01-secret"


def iso(hours: float) -> str:
    """A time this many hours from now, as Anthropic writes it."""
    return (datetime.now().astimezone() + timedelta(hours=hours)).isoformat()


def usage_answer() -> dict[str, Any]:
    return {
        "five_hour": {"utilization": 42.4, "resets_at": iso(4.5)},
        "seven_day": {"utilization": 13.0, "resets_at": iso(80)},
        "seven_day_opus": None,
        "limits": [
            {
                "kind": "weekly_scoped",
                "percent": 81.6,
                "resets_at": iso(80),
                "scope": {"model": {"display_name": "Fable"}},
            },
            {"kind": "weekly_scoped", "percent": 5, "scope": {}},
            {"kind": "something_else", "percent": 5},
        ],
    }


def until(condition: Callable[[], Any]) -> None:
    for _ in range(300):
        if condition():
            return
        wait(10)
    assert condition()


class ClaudeApi:
    """Stands in for Anthropic and the status page, so the tests never reach the network."""

    def __init__(self) -> None:
        self.usage = usage_answer()
        self.status: Any = {"status": {"indicator": "minor", "description": "Partially Degraded Service"}}
        self.error = ""
        self.status_error = ""
        self.asked: list[tuple[str, str]] = []

    def get_json(self, _network: Any, url: str, done: Callable[[Any, str], None], token: str = "") -> None:
        self.asked.append((url, token))
        if url == STATUS_URL:
            answer = (None, self.status_error) if self.status_error else (copy.deepcopy(self.status), "")
        else:
            answer = (None, self.error) if self.error else (copy.deepcopy(self.usage), "")
        QTimer.singleShot(0, lambda: done(*answer))

    def usage_requests(self) -> list[str]:
        return [token for url, token in self.asked if url == USAGE_URL]


def sign_in(folder: Path, expires_in_hours: float = 8) -> None:
    expires = int((time.time() + expires_in_hours * 3600) * 1000)
    (folder / ".credentials.json").write_text(
        json.dumps({"claudeAiOauth": {"accessToken": TOKEN, "expiresAt": expires}}), encoding="utf-8"
    )


def write_log(folder: Path, name: str, entries: list[tuple[datetime, str, list[int], str]]) -> Path:
    """A session log with an answer per (time, model, [input, output, cache write, cache read], session id)."""
    project = folder / "projects" / "project"
    project.mkdir(parents=True, exist_ok=True)
    log = project / f"{name}.jsonl"
    lines = [json.dumps({"type": "user", "message": {"content": "never read"}})]
    for at, model, counts, session in entries:
        speed = "fast" if model.endswith("!") else "standard"
        usage = dict(
            zip(
                ["input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"],
                counts,
                strict=True,
            ),
            speed=speed,
        )
        lines.append(
            json.dumps(
                {
                    "timestamp": at.astimezone().isoformat(),
                    "sessionId": session,
                    "message": {"model": model.rstrip("!"), "usage": usage, "content": "never read"},
                }
            )
        )
    lines.append("not json")
    log.write_text("\n".join(lines), encoding="utf-8")
    return log


@pytest.fixture
def claude_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    folder = tmp_path / ".claude"
    folder.mkdir()
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(folder))
    return folder


@pytest.fixture
def api(qapp: QApplication, claude_dir: Path, monkeypatch: pytest.MonkeyPatch) -> ClaudeApi:
    api = ClaudeApi()
    monkeypatch.setattr(usage_module, "get_json", api.get_json)
    for feed in (UsageFeed, StatusFeed, HistoryFeed):
        monkeypatch.setattr(feed, "_feeds", {})
    for name in (USAGE_FILE, HISTORY_FILE):
        app_data_path(name).unlink(missing_ok=True)
    return api


def monitor(**settings: Any) -> ClaudeUsageMonitor:
    """A monitor with the settings given; the token history stays off unless a test turns it on."""
    usage = ClaudeUsageMonitor()
    for name, value in {"tokenHistory": False, **settings}.items():
        usage.setProperty(name, value)
    return usage


def test_the_usage_endpoint_answer_is_read():
    usage = parse_usage(usage_answer())
    assert usage["fiveHour"] is not None and usage["fiveHour"]["name"] == "5-hour"
    assert usage["fiveHour"]["percent"] == 42.4 and usage["fiveHour"]["resetsAt"] > time.time() * 1000
    assert [(model["name"], model["percent"]) for model in usage["models"]] == [("Fable", 81.6)]
    assert parse_usage({"five_hour": None}) == {"fiveHour": None, "sevenDay": None, "models": []}
    assert parse_usage("nonsense")["models"] == []


def test_the_sign_in_is_read_from_claude_code(claude_dir: Path):
    assert read_credentials() == ("", 0)
    (claude_dir / ".credentials.json").write_text("{broken", encoding="utf-8")
    assert read_credentials() == ("", 0)
    sign_in(claude_dir)
    token, expires = read_credentials()
    assert token == TOKEN and expires > time.time() * 1000


def test_model_ids_read_as_people_say_them():
    assert model_name("claude-opus-4-1-20250805") == "Opus 4.1"
    assert model_name("claude-3-5-haiku-20241022") == "Haiku 3.5"
    assert model_name("claude-sonnet-4-5-20250929[fast]") == "Sonnet 4.5 (fast)"
    assert model_name("claude-fable-5-1") == "Fable 5.1"
    assert model_name("gpt") == "Gpt"


def test_token_counts_are_written_short():
    assert [compact(n) for n in (950, 12345, 4_500_000, 1_000_000, 1_200_000_000)] == [
        "950",
        "12.3K",
        "4.5M",
        "1M",
        "1.2B",
    ]


def test_the_logs_add_up_by_period_model_and_kind(claude_dir: Path, qapp: QApplication):
    app_data_path(HISTORY_FILE).unlink(missing_ok=True)
    now = datetime(2026, 11, 4, 15, 30).astimezone()  # A Wednesday
    write_log(
        claude_dir,
        "first",
        [
            (now - timedelta(hours=1), "claude-opus-4-1-20250805", [10, 20, 30, 40], "old"),
            (now - timedelta(days=2), "claude-sonnet-4-5-20250929!", [1, 2, 3, 4], "old"),
            (now - timedelta(days=40), "claude-opus-4-1-20250805", [100, 0, 0, 0], "old"),
            (now - timedelta(hours=2), "<synthetic>", [5, 0, 0, 0], "old"),
        ],
    )
    write_log(claude_dir, "second", [(now - timedelta(minutes=30), "claude-opus-4-1-20250805", [1, 1, 1, 1], "latest")])
    summary = summarize(scan(), count_cache_read=True, week_starts_on="monday", now=now)
    periods = summary["periods"]
    assert summary["sessionId"] == "latest" and periods["session"]["total"] == 4
    assert periods["today"]["total"] == 100 + 4 + 5
    assert periods["today"]["kinds"] == {"input": 16, "output": 21, "cacheCreation": 31, "cacheRead": 41}
    assert [model["name"] for model in periods["today"]["models"]] == ["Opus 4.1"]
    assert (
        periods["week"]["total"] == 109 + 10
        and periods["week"]["step"] == "day"
        and len(periods["week"]["series"]) == 3
    )
    assert [model["name"] for model in periods["week"]["models"]] == ["Opus 4.1", "Sonnet 4.5 (fast)"]
    assert periods["year"]["total"] == 219 and periods["year"]["step"] == "month"
    assert len(periods["today"]["series"]) == 16 and sum(periods["today"]["series"]) == 109
    new_work = summarize(scan(), count_cache_read=False, week_starts_on="monday", now=now)["periods"]
    assert new_work["today"]["total"] == 109 - 41
    sunday = summarize(scan(), count_cache_read=True, week_starts_on="sunday", now=now)["periods"]
    assert len(sunday["week"]["series"]) == 4


def test_a_scan_reads_only_logs_that_changed(claude_dir: Path, qapp: QApplication, monkeypatch: pytest.MonkeyPatch):
    app_data_path(HISTORY_FILE).unlink(missing_ok=True)
    now = datetime.now().astimezone()
    write_log(claude_dir, "a", [(now, "claude-opus-4-1-20250805", [1, 0, 0, 0], "s")])
    write_log(claude_dir, "b", [(now, "claude-opus-4-1-20250805", [2, 0, 0, 0], "s")])
    read: list[str] = []
    parse_log = history_module.parse_log

    def counting(path: Path) -> dict[str, Any]:
        read.append(path.name)
        return parse_log(path)

    monkeypatch.setattr(history_module, "parse_log", counting)
    scan()
    assert sorted(read) == ["a.jsonl", "b.jsonl"]
    read.clear()
    write_log(claude_dir, "b", [(now, "claude-opus-4-1-20250805", [5, 0, 0, 0], "s")])
    history = scan()
    assert read == ["b.jsonl"]
    assert summarize(history, True, "monday", now)["periods"]["today"]["total"] == 6


def test_the_usage_is_fetched_with_claude_codes_sign_in(api: ClaudeApi, claude_dir: Path):
    sign_in(claude_dir)
    usage = monitor(checkStatus=False)
    until(lambda: usage.property("ready"))
    assert api.usage_requests() == [TOKEN]
    five, seven = usage.property("fiveHour"), usage.property("sevenDay")
    assert (five["value"], five["level"], seven["value"]) == (42, "low", 13)
    assert five["resetIn"] in ("4h 29m", "4h 30m") and seven["resetIn"].startswith("3d ")
    assert [(limit["name"], limit["level"]) for limit in usage.property("limits")] == [
        ("5-hour", "low"),
        ("7-day", "low"),
        ("Fable", "high"),
    ]
    values = usage.property("values")
    assert (values["five_hour"], values["seven_day"], values["five_hour_reset"]) == ("42", "13", five["resetIn"])
    assert values["seven_day_reset"] == seven["resetOn"] and values["today_tokens"] == "--"
    assert usage.property("signedIn") and not usage.property("tokenExpired") and usage.property("updated").isValid()
    # The token reaches the request only, never what QML sees
    assert TOKEN not in json.dumps([values, [str(v) for limit in usage.property("limits") for v in limit.values()]])
    assert TOKEN not in app_data_path(USAGE_FILE).read_text(encoding="utf-8")


def test_without_claude_code_nothing_is_asked(api: ClaudeApi):
    usage = monitor(checkStatus=False)
    until(lambda: "Claude Code CLI" in usage.property("error"))
    assert not usage.property("signedIn") and not usage.property("ready") and api.usage_requests() == []
    assert usage.property("values")["five_hour"] == "--"


def test_a_failed_fetch_keeps_the_last_usage(api: ClaudeApi, claude_dir: Path):
    sign_in(claude_dir)
    usage = monitor(checkStatus=False)
    until(lambda: usage.property("ready"))
    api.error = "Anthropic is limiting requests; the last usage stays until it answers again."
    usage.refresh()
    until(lambda: usage.property("error") == api.error)
    assert usage.property("ready") and usage.property("fiveHour")["value"] == 42


def test_an_expired_sign_in_is_reported(api: ClaudeApi, claude_dir: Path):
    sign_in(claude_dir, expires_in_hours=-1)
    usage = monitor(checkStatus=False)
    until(lambda: usage.property("ready"))
    assert usage.property("tokenExpired")


def test_fresh_usage_on_disk_is_not_fetched_again(api: ClaudeApi, claude_dir: Path):
    sign_in(claude_dir)
    first = monitor(checkStatus=False)
    until(lambda: first.property("ready"))
    first.deleteLater()
    until(lambda: not UsageFeed._feeds)  # pyright: ignore[reportPrivateUsage]
    second = monitor(checkStatus=False)
    until(lambda: second.property("ready"))
    wait(50)
    assert api.usage_requests() == [TOKEN]


def test_widgets_on_the_same_interval_share_one_fetch(api: ClaudeApi, claude_dir: Path):
    sign_in(claude_dir)
    first, second = monitor(checkStatus=False), monitor(checkStatus=False)
    until(lambda: first.property("ready") and second.property("ready"))
    assert api.usage_requests() == [TOKEN]


def test_the_status_keeps_the_last_known_while_the_page_fails(api: ClaudeApi, claude_dir: Path):
    sign_in(claude_dir)
    usage = monitor()
    until(lambda: usage.property("status")["indicator"] == "minor")
    assert usage.property("values")["status_text"] == "Partially Degraded Service"
    api.status_error = "Could not connect to the Claude status page."
    usage.refresh()
    until(lambda: usage.property("status")["error"] != "")
    assert usage.property("status")["indicator"] == "minor"


def test_the_token_history_is_scanned_when_on(api: ClaudeApi, claude_dir: Path):
    sign_in(claude_dir)
    write_log(claude_dir, "a", [(datetime.now().astimezone(), "claude-opus-4-1-20250805", [1000, 500, 0, 0], "s")])
    usage = monitor(checkStatus=False)
    until(lambda: usage.property("ready"))
    assert usage.property("history") == {}
    usage.setProperty("tokenHistory", True)
    until(lambda: usage.property("history") != {})
    assert usage.property("history")["periods"]["today"]["total"] == 1500
    assert usage.property("values")["today_tokens"] == "1.5K" and usage.property("scanned").isValid()


def load_widget(claude_dir: Path) -> Iterator[tuple[QQuickItem, list[str]]]:
    write_log(claude_dir, "a", [(datetime.now().astimezone(), "claude-opus-4-1-20250805", [1000, 500, 0, 0], "s")])
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    warnings: list[str] = []

    def collect_warnings(errors: list[QQmlError]) -> None:
        warnings.extend(error.toString() for error in errors)

    engine.warnings.connect(collect_warnings)
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(BUILTIN_WIDGETS_DIR / "ClaudeUsage" / "ClaudeUsage.qml")))
    item = component.create()
    assert isinstance(item, QQuickItem), [error.toString() for error in component.errors()]
    yield item, warnings
    popup = item.findChild(QObject, "popup")
    if popup is not None:
        QMetaObject.invokeMethod(popup, "hide")
    item.deleteLater()
    wait(20)


@pytest.fixture
def widget(api: ClaudeApi, claude_dir: Path) -> Iterator[tuple[QQuickItem, list[str]]]:
    sign_in(claude_dir)
    yield from load_widget(claude_dir)


@pytest.fixture
def signed_out_widget(api: ClaudeApi, claude_dir: Path) -> Iterator[tuple[QQuickItem, list[str]]]:
    yield from load_widget(claude_dir)


def test_the_bar_label_and_popup_show_the_usage(widget: tuple[QQuickItem, list[str]]):
    item, warnings = widget
    # As a widget file sets it, replacing the default that follows the sign-in
    QQmlProperty.write(item, "tokenHistory", True)
    usage = item.findChild(ClaudeUsageMonitor)
    assert usage is not None
    label = find_item(item, "label")
    assert label is not None
    until(lambda: label.property("text") == "Claude 42%")
    QMetaObject.invokeMethod(item, "togglePopup")
    popup = item.findChild(QObject, "popup")
    assert popup is not None
    window = QQmlProperty.read(popup, "window")
    until(lambda: window.isVisible())
    content = window.contentItem()
    limits = find_item(content, "limits")
    assert limits is not None and limits.isVisible()
    until(lambda: (tokens := find_item(content, "tokens")) is not None and tokens.isVisible())
    total = find_item(content, "tokenTotal")
    assert total is not None and total.property("text").replace(",", "").replace(".", "") == "1500"
    status = find_item(content, "status")
    until(lambda: status is not None and status.isVisible())
    assert not warnings, warnings


def test_without_a_sign_in_the_widget_shows_the_tokens(signed_out_widget: tuple[QQuickItem, list[str]]):
    item, warnings = signed_out_widget
    usage = item.findChild(ClaudeUsageMonitor)
    assert usage is not None
    label = find_item(item, "label")
    assert label is not None
    until(lambda: label.property("text") == "Claude 1.5K")
    assert usage.property("tokenHistory") and not usage.property("signedIn")
    QMetaObject.invokeMethod(item, "togglePopup")
    popup = item.findChild(QObject, "popup")
    assert popup is not None
    window = QQmlProperty.read(popup, "window")
    until(lambda: window.isVisible())
    content = window.contentItem()
    notice = find_item(content, "notice")
    assert notice is not None and notice.isVisible() and "claude, then /login" in notice.property("text")
    limits, tokens = find_item(content, "limits"), find_item(content, "tokens")
    assert limits is not None and not limits.isVisible() and tokens is not None and tokens.isVisible()
    assert not warnings, warnings


def test_the_token_history_is_on_by_default(widget: tuple[QQuickItem, list[str]]):
    item, _ = widget
    usage = item.findChild(ClaudeUsageMonitor)
    assert usage is not None
    until(lambda: usage.property("ready") and usage.property("history") != {})
    assert usage.property("tokenHistory") and usage.property("signedIn")


def test_windows_anthropic_leaves_out_are_skipped(api: ClaudeApi, claude_dir: Path):
    sign_in(claude_dir)
    api.usage = {"five_hour": None, "seven_day": {"utilization": 13.0, "resets_at": iso(80)}, "limits": None}
    usage = monitor(checkStatus=False)
    until(lambda: usage.property("ready"))
    assert usage.property("fiveHour") == {} and [lim["name"] for lim in usage.property("limits")] == ["7-day"]
    assert (usage.property("values")["five_hour"], usage.property("values")["five_hour_reset"]) == ("--", "--")


def test_an_answer_without_limits_says_so(api: ClaudeApi, widget: tuple[QQuickItem, list[str]]):
    api.usage = {"five_hour": None, "seven_day": None}
    item, warnings = widget
    usage = item.findChild(ClaudeUsageMonitor)
    assert usage is not None
    until(lambda: usage.property("ready"))
    assert usage.property("limits") == [] and usage.property("error") == ""
    QMetaObject.invokeMethod(item, "togglePopup")
    popup = item.findChild(QObject, "popup")
    assert popup is not None
    window = QQmlProperty.read(popup, "window")
    until(lambda: window.isVisible())
    content = window.contentItem()
    no_limits, placeholder = find_item(content, "noLimits"), find_item(content, "placeholder")
    assert no_limits is not None and no_limits.isVisible()
    assert placeholder is not None and not placeholder.isVisible()
    assert not warnings, warnings
