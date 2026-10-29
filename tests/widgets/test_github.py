# pyright: reportPrivateUsage=false

import threading
import urllib.error
from collections.abc import Callable, Iterator
from email.message import Message
from typing import Any

import pytest
from PyQt6.QtCore import QCoreApplication, QEvent, QMetaObject, QThread, QUrl
from PyQt6.QtQml import QQmlComponent, QQmlEngine, QQmlError
from PyQt6.QtQuick import QQuickItem, QQuickWindow
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication

from core.qml_types import register_qml_types
from core.widget_files import BUILTIN_WIDGETS_DIR
from core.widgets.services.github import auth
from core.widgets.services.github.api import GitHubDataManager
from core.widgets.services.github.notifications import GitHubNotifications, notification_details, notification_status
from settings import QML_IMPORT_PATH
from tests.support.qt import wait

SAMPLE: list[dict[str, Any]] = [
    {
        "id": "1",
        "type": "PullRequest",
        "title": "Fix popup behavior",
        "repository": "owner/repo",
        "url": "https://github.com/owner/repo/pull/1",
        "unread": True,
        "reason": "review_requested",
        "updated_at": "2026-10-29T08:00:00Z",
        "comment_count": None,
        "pull_request_state": "closed",
        "pull_request_is_merged": True,
    },
    {
        "id": "2",
        "type": "Issue",
        "title": "Crash on start",
        "repository": "owner/repo",
        "url": "https://github.com/owner/repo/issues/2",
        "unread": True,
        "reason": "mention",
        "updated_at": "2026-10-29T07:00:00Z",
        "comment_count": 3,
        "issue_state": "open",
    },
]

type Fetch = Callable[[str, int, bool], list[dict[str, Any]]]


def until(condition: Callable[[], Any]) -> None:
    for _ in range(100):
        if condition():
            return
        wait(10)
    assert condition()


def sample(*_args: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in SAMPLE]


def empty(*_args: Any) -> list[dict[str, Any]]:
    return []


def rejected(*_args: Any) -> list[dict[str, Any]]:
    raise urllib.error.HTTPError("https://api.github.com/notifications", 401, "Unauthorized", Message(), None)


class GitHub:
    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.monkeypatch = monkeypatch
        self.tokens: list[str] = []
        self.read: list[tuple[str, str | None]] = []
        self.all_read: list[str] = []
        self.fetch: Fetch = sample
        monkeypatch.setattr(GitHubDataManager, "fetch_all_notifications", staticmethod(self._fetch))
        monkeypatch.setattr(GitHubDataManager, "mark_as_read", staticmethod(self._mark_read))
        monkeypatch.setattr(GitHubDataManager, "mark_all_as_read", staticmethod(self.all_read.append))

    def _fetch(self, token: str, maximum: int, comments: bool) -> list[dict[str, Any]]:
        self.tokens.append(token)
        return self.fetch(token, maximum, comments)

    def _mark_read(self, notification_id: str, token: str | None = None) -> None:
        self.read.append((notification_id, token))


@pytest.fixture
def github(qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> GitHub:
    monkeypatch.setenv("YASB_GITHUB_TOKEN", "env-token")
    monkeypatch.setattr(auth, "get_saved_token", lambda: "")
    return GitHub(monkeypatch)


@pytest.fixture
def service(github: GitHub) -> Iterator[GitHubNotifications]:
    service = GitHubNotifications()
    yield service
    service.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)


def settled(service: GitHubNotifications) -> Callable[[], bool]:
    return lambda: not service.property("loading") and bool(service._request)


@pytest.mark.parametrize(
    ("item", "key"),
    [
        ({"type": "Issue", "issue_state": "open"}, "issue-open"),
        ({"type": "Issue", "issue_state": "closed"}, "issue-closed"),
        ({"type": "PullRequest", "pull_request_state": "open"}, "pr-open"),
        ({"type": "PullRequest", "pull_request_state": "closed"}, "pr-closed"),
        ({"type": "PullRequest", "pull_request_state": "closed", "pull_request_is_merged": True}, "pr-merged"),
        ({"type": "PullRequest", "pull_request_state": "open", "pull_request_is_draft": True}, "pr-draft"),
        ({"type": "Discussion", "discussion_is_answered": True}, "discussion-answered"),
        ({"type": "Discussion", "discussion_is_answered": False}, "discussion"),
        ({"type": "Release"}, "release"),
        ({"type": "CheckSuite"}, "checks"),
        ({"type": "Issue"}, "unknown"),
        ({"type": "PullRequest"}, "unknown"),
        ({"type": "Discussion"}, "unknown"),
    ],
)
def test_notification_status_and_icon(item: dict[str, Any], key: str, qapp: QApplication):
    assert notification_status(item)[0] == key
    assert QSvgRenderer(str(BUILTIN_WIDGETS_DIR / "Github" / "icons" / f"{key}.svg")).isValid()


@pytest.mark.parametrize(
    ("count", "suffix"),
    [
        (None, ""),
        ("undefined", ""),
        (True, ""),
        (-1, ""),
        (0, " · 0 comments"),
        (1, " · 1 comment"),
        (3, " · 3 comments"),
    ],
)
def test_optional_comment_count_is_only_shown_when_valid(count: Any, suffix: str):
    assert notification_details({**SAMPLE[0], "comment_count": count}) == "owner/repo · Review requested" + suffix


def test_notifications_arrive_on_the_gui_thread(github: GitHub, qapp: QApplication):
    threads: list[QThread | None] = []
    service = GitHubNotifications()
    service.dataChanged.connect(lambda: threads.append(QThread.currentThread()))
    until(settled(service))
    assert [item["id"] for item in service.property("notifications")] == ["1", "2"]
    assert service.property("unreadCount") == 2 and service.property("error") == ""
    assert threads and all(thread == qapp.thread() for thread in threads)
    service.deleteLater()


def test_a_failed_refresh_keeps_the_notifications(github: GitHub, service: GitHubNotifications):
    until(settled(service))

    def offline(*_args: Any) -> list[dict[str, Any]]:
        raise urllib.error.URLError("offline")

    github.fetch = offline
    service.refresh()
    until(settled(service))
    assert len(service.property("notifications")) == 2
    assert service.property("error") == "Could not connect to GitHub."
    github.fetch = empty
    service.refresh()
    until(settled(service))
    assert service.property("notifications") == [] and service.property("error") == ""


def test_a_slow_fetch_for_an_old_token_is_dropped(github: GitHub, service: GitHubNotifications):
    started, release = threading.Event(), threading.Event()

    def fetch(token: str, *_args: Any) -> list[dict[str, Any]]:
        if token == "old-token":
            started.set()
            release.wait(2)
        return [{**SAMPLE[0], "id": token}]

    until(settled(service))
    github.fetch = fetch
    service.setProperty("token", "old-token")
    until(started.is_set)
    service.setProperty("token", "new-token")
    until(lambda: github.tokens[-1] == "new-token")
    release.set()
    until(settled(service))
    wait(50)
    assert [item["id"] for item in service.property("notifications")] == ["new-token"]


def test_a_rejected_configured_token_asks_to_update_it(github: GitHub, service: GitHubNotifications):
    github.fetch = rejected
    until(settled(service))
    assert service.property("error") == "GitHub rejected the token. Update or remove it."
    assert not service.property("needsSignIn")


def test_a_rejected_sign_in_asks_to_sign_in_again(github: GitHub, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("YASB_GITHUB_TOKEN")
    monkeypatch.setattr(auth, "get_saved_token", lambda: "saved-token")
    github.fetch = rejected
    service = GitHubNotifications()
    until(settled(service))
    assert service.property("needsSignIn") and service.property("error") == "GitHub signed YASB out. Sign in again."
    service.deleteLater()


def test_no_token_asks_to_sign_in_without_fetching(github: GitHub, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("YASB_GITHUB_TOKEN")
    service = GitHubNotifications()
    until(lambda: service._request)
    assert service.property("needsSignIn") and not service.property("loading") and github.tokens == []
    service.deleteLater()


@pytest.mark.parametrize(
    ("setting", "environment", "expected"),
    [
        ("", "env-token", "env-token"),
        ("env", "env-token", "env-token"),
        ("", "", "saved-token"),
        ("config-token", "env-token", "config-token"),
    ],
)
def test_token_priority(github: GitHub, monkeypatch: pytest.MonkeyPatch, setting: str, environment: str, expected: str):
    monkeypatch.setenv("YASB_GITHUB_TOKEN", environment)
    monkeypatch.setattr(auth, "get_saved_token", lambda: "saved-token")
    service = GitHubNotifications()
    service.setProperty("token", setting)
    until(settled(service))
    assert github.tokens == [expected]
    service.deleteLater()


def test_marking_read_updates_the_filtered_view(github: GitHub, service: GitHubNotifications):
    service.setProperty("onlyUnread", True)
    until(settled(service))
    service.markRead("1")
    assert [item["id"] for item in service.property("notifications")] == ["2"]
    assert service.property("unreadCount") == 1 and github.read == [("1", "env-token")]
    service.setProperty("onlyUnread", False)
    assert [item["unread"] for item in service.property("notifications")] == [False, True]


def test_mark_all_read_marks_everything_without_filters(github: GitHub, service: GitHubNotifications):
    until(settled(service))
    service.markAllRead()
    assert service.property("unreadCount") == 0 and github.all_read == ["env-token"] and github.read == []


def test_mark_all_read_with_reason_filters_leaves_hidden_notifications_unread(
    github: GitHub, service: GitHubNotifications
):
    service.setProperty("reasonFilters", ["mention"])
    until(settled(service))
    service.markAllRead()
    assert github.all_read == [] and github.read == [("2", "env-token")]
    service.setProperty("reasonFilters", [])
    assert [item["unread"] for item in service.property("notifications")] == [True, False]


def device_code(_name: str = "notifications") -> dict[str, Any]:
    return {"device_code": "device", "user_code": "TEST-CODE", "verification_uri": "https://github.com/login/device"}


def test_a_cancelled_sign_in_cannot_save_a_late_token(
    github: GitHub, service: GitHubNotifications, monkeypatch: pytest.MonkeyPatch
):
    started, release = threading.Event(), threading.Event()
    saved: list[str] = []

    def poll(*args: Any, **_kwargs: Any) -> None:
        started.set()
        release.wait(2)
        args[2]("late-token")

    monkeypatch.setattr(auth, "request_device_code", device_code)
    monkeypatch.setattr(auth, "poll_for_token", poll)
    monkeypatch.setattr(auth, "save_token", saved.append)
    service.signIn()
    until(lambda: service.property("authCode") == "TEST-CODE")
    service.cancelSignIn()
    release.set()
    wait(50)
    assert saved == [] and not service.property("authBusy")


def test_a_sign_in_saves_the_token_on_the_gui_thread_and_fetches(
    github: GitHub, monkeypatch: pytest.MonkeyPatch, qapp: QApplication
):
    saved: list[tuple[str, QThread | None]] = []
    monkeypatch.delenv("YASB_GITHUB_TOKEN")
    monkeypatch.setattr(auth, "request_device_code", device_code)

    def poll(*args: Any, **_kwargs: Any) -> None:
        args[2]("new-token")

    def save(token: str) -> None:
        saved.append((token, QThread.currentThread()))

    monkeypatch.setattr(auth, "poll_for_token", poll)
    monkeypatch.setattr(auth, "save_token", save)
    service = GitHubNotifications()
    until(lambda: service._request)
    monkeypatch.setattr(auth, "get_saved_token", lambda: saved[-1][0] if saved else "")
    service.signIn()
    until(lambda: github.tokens == ["new-token"] and settled(service)())
    assert saved == [("new-token", qapp.thread())]
    assert not service.property("authBusy") and not service.property("needsSignIn")
    service.deleteLater()


def test_qml_widget_shows_every_state_without_warnings(github: GitHub, monkeypatch: pytest.MonkeyPatch):
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    warnings: list[str] = []

    def collect_warnings(errors: list[QQmlError]) -> None:
        warnings.extend(error.toString() for error in errors)

    engine.warnings.connect(collect_warnings)
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(BUILTIN_WIDGETS_DIR / "Github" / "Github.qml")))
    widget = component.create()
    assert isinstance(widget, QQuickItem), [error.toString() for error in component.errors()]
    host = QQuickWindow()
    try:
        widget.setParentItem(host.contentItem())
        host.show()
        service = widget.findChild(GitHubNotifications)
        assert service is not None
        until(settled(service))
        QMetaObject.invokeMethod(widget, "togglePopup")
        wait(50)
        github.fetch = empty
        service.refresh()
        until(settled(service))
        github.fetch = rejected
        service.refresh()
        until(settled(service))
        monkeypatch.delenv("YASB_GITHUB_TOKEN")
        service.refresh()
        wait(50)
        assert service.property("needsSignIn")
        assert not warnings
    finally:
        widget.setParentItem(None)
        widget.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
        host.close()
        engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
