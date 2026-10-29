import logging
import os
import threading
import urllib.error
from typing import Any

from PyQt6.QtCore import QObject, QTimer, QUrl, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QDesktopServices, QGuiApplication

from core.utils.qml import qml_property
from core.widgets.services.github import auth
from core.widgets.services.github.api import GitHubDataManager

MIN_INTERVAL_MS = 60000
MAX_INTERVAL_MS = 3600000
MAX_NOTIFICATIONS = 100
# Settings that change what GitHub returns, so changing them fetches again
REFETCH_SETTINGS = {"token", "maxNotifications", "showCommentCount"}


def notification_details(item: dict[str, Any]) -> str:
    reason = item.get("reason") or ""
    labels = {
        "review_requested": "Review requested",
        "mention": "Mentioned",
        "team_mention": "Team mention",
        "assign": "Assigned",
        "ci_activity": "CI activity",
    }
    parts = [item.get("repository") or "", labels.get(reason, reason.replace("_", " "))]
    count = item.get("comment_count")
    if type(count) is int and count >= 0:
        parts.append(f"{count} {'comment' if count == 1 else 'comments'}")
    return " · ".join(part for part in parts if part)


def notification_status(item: dict[str, Any]) -> tuple[str, str]:
    match item.get("type"):
        case "Issue":
            if item.get("issue_state") in {"open", "closed"}:
                return f"issue-{item['issue_state']}", f"{item['issue_state'].capitalize()} issue"
        case "PullRequest":
            state = item.get("pull_request_state")
            if item.get("pull_request_is_merged") or state == "merged":
                return "pr-merged", "Merged pull request"
            if state == "closed":
                return "pr-closed", "Closed pull request"
            if item.get("pull_request_is_draft"):
                return "pr-draft", "Draft pull request"
            if state == "open":
                return "pr-open", "Open pull request"
        case "Discussion":
            if isinstance(item.get("discussion_is_answered"), bool):
                return (
                    ("discussion-answered", "Answered discussion")
                    if item["discussion_is_answered"]
                    else ("discussion", "Discussion")
                )
        case "Release":
            return "release", "Release"
        case "CheckSuite":
            return "checks", "Checks · result unavailable"
        case _:
            pass
    return "unknown", f"{item.get('type') or 'Notification'} · status unavailable"


def _is_github(url: QUrl) -> bool:
    return url.scheme() == "https" and url.host() == "github.com"


def _setting(kind: type | str, name: str, notify: pyqtSignal) -> pyqtProperty[Any]:
    def get(service: GitHubNotifications) -> Any:
        return service.setting(name)

    def set_value(service: GitHubNotifications, value: Any) -> None:
        service.change_setting(name, value)

    return pyqtProperty(kind, get, set_value, notify=notify)


class GitHubNotifications(QObject):
    """The GitHub notifications of one account, fetched in the background and filtered for one widget."""

    dataChanged = pyqtSignal()
    stateChanged = pyqtSignal()
    settingsChanged = pyqtSignal()
    authChanged = pyqtSignal()
    _fetched = pyqtSignal(int, object, str, bool)
    _authEvent = pyqtSignal(int, str, object)

    token = _setting(str, "token", settingsChanged)
    updateInterval = _setting(int, "updateInterval", settingsChanged)
    maxNotifications = _setting(int, "maxNotifications", settingsChanged)
    onlyUnread = _setting(bool, "onlyUnread", settingsChanged)
    reasonFilters = _setting("QStringList", "reasonFilters", settingsChanged)
    showCommentCount = _setting(bool, "showCommentCount", settingsChanged)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings: dict[str, Any] = {
            "token": "",
            "updateInterval": 300000,
            "maxNotifications": 50,
            "onlyUnread": False,
            "reasonFilters": [],
            "showCommentCount": True,
        }
        self._token: str = ""
        self._from_sign_in = False
        self._rejected = False
        self._all: list[dict[str, Any]] = []
        self._notifications: list[dict[str, Any]] = []
        self._unread_count = 0
        self._loading = False
        self._error = ""
        self._request = 0
        self._auth_session: int = 0
        self._auth_busy = False
        self._auth_code = ""
        self._auth_url = ""
        self._fetched.connect(self._receive)
        self._authEvent.connect(self._receive_auth)

        # QML sets the settings after creating the object, so the first fetch waits for them
        self._fetch_timer = QTimer(self)
        self._fetch_timer.setSingleShot(True)
        self._fetch_timer.setInterval(0)
        self._fetch_timer.timeout.connect(self.refresh)
        self._fetch_timer.start()
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(self._settings["updateInterval"])
        self._poll_timer.timeout.connect(self.refresh)
        self._poll_timer.start()

    def setting(self, name: str) -> Any:
        return self._settings[name]

    def change_setting(self, name: str, value: Any) -> None:
        if name == "updateInterval":
            value = max(MIN_INTERVAL_MS, min(value, MAX_INTERVAL_MS))
        elif name == "maxNotifications":
            value = max(1, min(value, MAX_NOTIFICATIONS))
        if value == self._settings[name]:
            return
        self._settings[name] = value
        self.settingsChanged.emit()
        if name == "updateInterval":
            self._poll_timer.setInterval(value)
        elif name in REFETCH_SETTINGS:
            self._fetch_timer.start()
        else:
            self._publish()

    @qml_property("QVariantList", notify=dataChanged)
    def notifications(self) -> list[dict[str, Any]]:
        return self._notifications

    @qml_property(int, notify=dataChanged)
    def unreadCount(self) -> int:
        return self._unread_count

    @qml_property(bool, notify=stateChanged)
    def loading(self) -> bool:
        return self._loading

    @qml_property(str, notify=stateChanged)
    def error(self) -> str:
        return self._error

    # No token, or GitHub rejected the one from YASB's own sign-in
    @qml_property(bool, notify=stateChanged)
    def needsSignIn(self) -> bool:
        return not self._token or (self._rejected and self._from_sign_in)

    @qml_property(bool, notify=authChanged)
    def authBusy(self) -> bool:
        return self._auth_busy

    @qml_property(str, notify=authChanged)
    def authCode(self) -> str:
        return self._auth_code

    def _resolve_token(self) -> tuple[str, bool]:
        configured = self._settings["token"].strip()
        if configured and configured != "env":
            return configured, False
        if environment := os.getenv("YASB_GITHUB_TOKEN", "").strip():
            return environment, False
        return auth.get_saved_token(), True

    @pyqtSlot()
    def refresh(self) -> None:
        self._request += 1
        token, from_sign_in = self._resolve_token()
        if token != self._token:
            self._token, self._from_sign_in, self._rejected, self._all = token, from_sign_in, False, []
            self._publish()
        self._loading = bool(token)
        self.stateChanged.emit()
        if not token:
            return
        request, maximum, comments = (
            self._request,
            self._settings["maxNotifications"],
            self._settings["showCommentCount"],
        )

        def fetch() -> None:
            data, error, rejected = None, "", False
            try:
                data = GitHubDataManager.fetch_all_notifications(token, maximum, comments)
            except urllib.error.HTTPError as e:
                error, rejected = f"GitHub returned HTTP {e.code}.", e.code == 401
            except urllib.error.URLError:
                error = "Could not connect to GitHub."
            except Exception:
                error = "Could not fetch GitHub notifications."
                logging.exception(error)
            try:
                self._fetched.emit(request, data, error, rejected)
            except RuntimeError:
                # The widget was destroyed while GitHub answered
                pass

        threading.Thread(target=fetch, daemon=True).start()

    @pyqtSlot(int, object, str, bool)
    def _receive(self, request: int, data: list[dict[str, Any]] | None, error: str, rejected: bool) -> None:
        if request != self._request:
            return
        self._rejected = rejected
        if rejected:
            data = []
            error = (
                "GitHub signed YASB out. Sign in again."
                if self._from_sign_in
                else "GitHub rejected the token. Update or remove it."
            )
        if data is not None:
            self._all = data
            self._publish()
        self._loading, self._error = False, error
        self.stateChanged.emit()

    def _publish(self) -> None:
        reasons = {reason.lower() for reason in self._settings["reasonFilters"] if reason}
        items = [item for item in self._all if not reasons or item.get("reason", "").lower() in reasons]
        unread_count = sum(bool(item.get("unread")) for item in items)
        if self._settings["onlyUnread"]:
            items = [item for item in items if item.get("unread")]
        notifications: list[dict[str, Any]] = []
        for item in items:
            key, label = notification_status(item)
            notifications.append(
                {**item, "statusKey": key, "statusLabel": label, "details": notification_details(item)}
            )
        if notifications != self._notifications or unread_count != self._unread_count:
            self._notifications, self._unread_count = notifications, unread_count
            self.dataChanged.emit()

    def _mark_read(self, ids: set[str]) -> None:
        self._all = [{**item, "unread": False} if item.get("id") in ids else item for item in self._all]
        self._publish()

    @pyqtSlot(str)
    def markRead(self, notification_id: str) -> None:
        if self._token:
            self._mark_read({notification_id})
            GitHubDataManager.mark_as_read(notification_id, token=self._token)

    @pyqtSlot()
    def markAllRead(self) -> None:
        if not self._token:
            return
        if self._settings["reasonFilters"]:
            # GitHub can only mark everything read, which would include notifications this widget hides
            ids = {item["id"] for item in self._notifications if item.get("unread")}
            self._mark_read(ids)
            for notification_id in ids:
                GitHubDataManager.mark_as_read(notification_id, token=self._token)
        else:
            self._mark_read({item["id"] for item in self._all})
            GitHubDataManager.mark_all_as_read(self._token)

    @pyqtSlot(str)
    def openNotification(self, notification_id: str) -> None:
        item = next((item for item in self._all if item.get("id") == notification_id), None)
        if item is None:
            return
        url = QUrl(item.get("url", ""))
        if _is_github(url) and QDesktopServices.openUrl(url) and item.get("unread"):
            self.markRead(notification_id)

    def _set_auth(self, busy: bool, code: str = "", url: str = "") -> None:
        self._auth_busy, self._auth_code, self._auth_url = busy, code, url
        self.authChanged.emit()

    @pyqtSlot()
    def signIn(self) -> None:
        if self._auth_busy:
            return
        self._auth_session += 1
        session = self._auth_session
        self._set_auth(True)

        def send(kind: str, value: object) -> None:
            try:
                self._authEvent.emit(session, kind, value)
            except RuntimeError:
                # The widget was destroyed during sign-in
                pass

        def run() -> None:
            try:
                code = auth.request_device_code()
            except RuntimeError as e:
                send("error", str(e))
                return
            if "device_code" not in code:
                send("error", code.get("error_description") or "Could not start GitHub sign-in.")
                return
            send("code", code)
            auth.poll_for_token(
                code["device_code"],
                int(code.get("interval", 5)),
                lambda token: send("success", token),
                lambda error: send("error", error),
                lambda: session != self._auth_session,
                # Saved on the GUI thread, where a cancelled session can still be told apart
                save_fn=lambda _token: None,
            )

        threading.Thread(target=run, daemon=True).start()

    @pyqtSlot(int, str, object)
    def _receive_auth(self, session: int, kind: str, value: Any) -> None:
        if session != self._auth_session:
            return
        if kind == "code":
            self._set_auth(True, value.get("user_code", ""), value.get("verification_uri", ""))
            return
        self._auth_session += 1
        self._set_auth(False)
        if kind == "success":
            auth.save_token(value)
            self.refresh()
        else:
            self._error = str(value)
            self.stateChanged.emit()

    @pyqtSlot()
    def cancelSignIn(self) -> None:
        self._auth_session += 1
        self._set_auth(False)

    @pyqtSlot()
    def openSignInPage(self) -> None:
        url = QUrl(self._auth_url)
        if _is_github(url):
            QDesktopServices.openUrl(url)

    @pyqtSlot()
    def copyCode(self) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None and self._auth_code:
            clipboard.setText(self._auth_code)
