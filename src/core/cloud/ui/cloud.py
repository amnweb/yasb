import logging
import time
from collections.abc import Callable
from dataclasses import replace
from functools import partial
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, QRect, QSettings, QTimer, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QGuiApplication

from core.cloud.api import ApiClient, ApiError
from core.cloud.autobackup import mark_in_sync
from core.cloud.constants import (
    APP_LOG_FILE,
    BACKUPS_UNAVAILABLE,
    BAD_SIGN_IN,
    BASE_URL,
    EMPTY_BACKUPS,
    MAX_EXCLUDE_RULES,
    MIN_SPINNER_MS,
    NOTE_MAX_LENGTH,
    PRIVACY_URL,
    TERMS_URL,
)
from core.cloud.errors import SnapshotError
from core.cloud.logs import set_level
from core.cloud.models import Access, Account, Snapshot, format_size, parse_timestamp
from core.cloud.operations import Operations
from core.cloud.schedule import create as create_task
from core.cloud.schedule import remove as remove_task
from core.cloud.session import Session, cloud_dir
from core.cloud.settings import Settings as CloudSettings
from core.cloud.settings import clean_rules
from core.cloud.settings import load as load_settings
from core.cloud.settings import save as save_settings
from core.cloud.snapshot import ALWAYS_INCLUDE, collect_files
from core.cloud.ui.backups import BackupModel
from core.cloud.ui.sign_in import SignInFlow
from core.utils.qml import qml_property
from core.utils.shell_utils import shell_open
from settings import DEFAULT_CONFIG_DIRECTORY, SCRIPT_PATH, WEBSITE_DOCS_URL

logger = logging.getLogger(__name__)

STORAGE_WARN_RATIO = 0.8
"""Fraction of the storage limit that turns the footer amber."""


def _reason(access: Access) -> str:
    # What is actually restricted, not why. A past_due subscription carries one reason code
    # for three different states - writes fine, writes stopped, everything stopped - so
    # keying off the code alone reported a stopped subscription while backups still ran.
    if access.reason == "no_subscription":
        return "No active subscription"
    if not access.can_read:
        return "Subscription expired"
    if not access.can_write:
        # Paired with the deletion date, so this half names the cause and that half the cost.
        return "Subscription ended"
    if access.reason == "payment_past_due":
        # Still writable, so this states the problem without claiming anything is blocked.
        return "Payment failed"
    return ""


def _read_deadline(access: Access) -> str:
    if access.can_write or not access.can_read or not access.read_until:
        return ""
    moment = parse_timestamp(access.read_until)
    return f"Backups deleted {moment.astimezone():%d %b}" if moment else ""


def _footer_state(account: Account) -> str:
    limits, usage = account.limits, account.usage
    if not account.access.can_write:
        return "critical"
    if limits.max_storage_bytes > 0 and usage.bytes >= limits.max_storage_bytes * STORAGE_WARN_RATIO:
        return "caution"
    if account.subscription is not None and not account.subscription.is_active:
        return "caution"
    return "normal"


def _footer_details(account: Account) -> str:
    subscription = account.subscription
    limits, usage = account.limits, account.usage
    reason = _reason(account.access)
    if not reason:
        reason = subscription.plan_id.title() if subscription else "No subscription"
    parts = [reason]
    if deadline := _read_deadline(account.access):
        parts.append(deadline)
    if account.access.can_write and limits.max_storage_bytes > 0:
        parts.append(f"{format_size(usage.bytes)} of {format_size(limits.max_storage_bytes)}")
    return " · ".join(parts)


class Cloud(QObject):
    """Owns the session and decides which of the four pages shows: loading, sign-in, backups, settings."""

    pageChanged = pyqtSignal()
    signInChanged = pyqtSignal()
    accountChanged = pyqtSignal()
    busyChanged = pyqtSignal()
    listChanged = pyqtSignal()
    settingsChanged = pyqtSignal()
    infoChanged = pyqtSignal()
    # title, message
    messageRequested = pyqtSignal(str, str)
    shareLinkReady = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._page = "loading"
        self._sign_in_state = "idle"
        self._user_code = ""
        self._account: Account | None = None
        self._busy = False
        self._busy_text = ""
        self._empty_message = ""
        self._total = 0
        self._loading_more = False
        self._info = ("", "", "")
        self._settings = load_settings()
        self._spinner_since: float | None = None
        self._backups = BackupModel(self)

        self._session = Session()
        self._api = ApiClient(self._session, self)
        self._api.signed_out.connect(self._on_signed_out)

        self._ops = Operations(self._api, self._session, self)
        self._ops.status.connect(self._on_op_status)
        self._ops.busy.connect(self._on_busy)
        self._ops.failed.connect(self._on_op_failed)
        self._ops.backed_up.connect(self._on_backed_up)
        self._ops.delete_finished.connect(self._on_delete_finished)
        self._ops.note_saved.connect(self._on_note_saved)
        self._ops.shared.connect(self._on_shared)
        self._ops.unshared.connect(self._on_unshared)
        self._ops.restored.connect(self._on_restored)
        self._ops.saved.connect(self._on_saved)

        self._sign_in = SignInFlow(self._api, self)
        self._sign_in.code_ready.connect(self._on_code_ready)
        self._sign_in.signed_in.connect(self._on_signed_in)
        self._sign_in.failed.connect(self._on_sign_in_failed)

    @qml_property(str, constant=True)
    def iconUrl(self) -> str:
        return QUrl.fromLocalFile(f"{SCRIPT_PATH}/assets/images/app_icon.png").toString()

    @qml_property(str, constant=True)
    def termsUrl(self) -> str:
        return TERMS_URL

    @qml_property(str, constant=True)
    def privacyUrl(self) -> str:
        return PRIVACY_URL

    @qml_property(int, constant=True)
    def noteMaxLength(self) -> int:
        return NOTE_MAX_LENGTH

    # loading, connect, backups or settings
    @qml_property(str, notify=pageChanged)
    def page(self) -> str:
        return self._page

    # idle, connecting or waiting
    @qml_property(str, notify=signInChanged)
    def signInState(self) -> str:
        return self._sign_in_state

    @qml_property(str, notify=signInChanged)
    def userCode(self) -> str:
        return self._user_code

    @qml_property(str, notify=accountChanged)
    def accountEmail(self) -> str:
        return self._account.email if self._account else ""

    @qml_property(str, notify=accountChanged)
    def accountDetails(self) -> str:
        return _footer_details(self._account) if self._account else ""

    # normal, caution or critical
    @qml_property(str, notify=accountChanged)
    def accountState(self) -> str:
        return _footer_state(self._account) if self._account else "normal"

    @qml_property(bool, notify=accountChanged)
    def canWrite(self) -> bool:
        return self._account is not None and self._account.access.can_write

    # A backup, restore or save is under way
    @qml_property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._busy

    @qml_property(str, notify=busyChanged)
    def busyText(self) -> str:
        return self._busy_text

    @qml_property(QObject, constant=True)
    def backups(self) -> BackupModel:
        return self._backups

    # Empty until the first page of backups has arrived
    @qml_property(str, notify=listChanged)
    def emptyMessage(self) -> str:
        return self._empty_message

    @qml_property(list, notify=settingsChanged)
    def excludeRules(self) -> list[str]:
        return list(self._settings.exclude)

    @qml_property(bool, notify=settingsChanged)
    def autoBackup(self) -> bool:
        return self._settings.auto_backup

    @qml_property(bool, notify=settingsChanged)
    def debugLogging(self) -> bool:
        return self._settings.debug_logging

    @qml_property(str, constant=True)
    def logFile(self) -> str:
        return str(Path(cloud_dir()) / APP_LOG_FILE)

    @qml_property(str, constant=True)
    def alwaysKept(self) -> str:
        return " and ".join(sorted(ALWAYS_INCLUDE))

    @qml_property(str, notify=infoChanged)
    def infoTitle(self) -> str:
        return self._info[0]

    @qml_property(str, notify=infoChanged)
    def infoMessage(self) -> str:
        return self._info[1]

    # Empty while hidden, otherwise informational or warning
    @qml_property(str, notify=infoChanged)
    def infoSeverity(self) -> str:
        return self._info[2]

    def _set_page(self, page: str) -> None:
        if page != self._page:
            self._page = page
            self.pageChanged.emit()

    def _set_sign_in(self, state: str, user_code: str = "") -> None:
        self._sign_in_state, self._user_code = state, user_code
        self.signInChanged.emit()

    def _set_info(self, title: str, message: str, severity: str) -> None:
        self._info = (title, message, severity)
        self.infoChanged.emit()

    def _message(self, title: str, message: str) -> None:
        self.messageRequested.emit(title, message)

    @pyqtSlot()
    def start(self) -> None:
        if self._session.load():
            self._spinner_since = time.monotonic()
            self._load_account()
        else:
            self._settle(self._show_connect)

    @pyqtSlot()
    def shutdown(self) -> None:
        self._sign_in.cancel()
        self._ops.cancel_active()
        self._api.abort_all()

    @pyqtSlot(result="QRect")
    def savedGeometry(self) -> QRect:
        """The window's last place, or an empty rect when it was on a screen that is gone."""
        saved = QSettings("YASB", "Cloud").value("window/rect")
        if isinstance(saved, QRect) and any(s.availableGeometry().intersects(saved) for s in QGuiApplication.screens()):
            return saved
        return QRect()

    @pyqtSlot(int, int, int, int)
    def saveGeometry(self, x: int, y: int, width: int, height: int) -> None:
        QSettings("YASB", "Cloud").setValue("window/rect", QRect(x, y, width, height))

    def _on_signed_out(self) -> None:
        self._stop_work()
        self._show_connect()

    def _show_connect(self) -> None:
        self._sign_in.cancel()
        self._set_sign_in("idle")
        self._set_list([], 0, "")
        self._set_page("connect")

    @pyqtSlot()
    def signIn(self) -> None:
        if self._session.load():
            self._load_account()
            return
        self._set_sign_in("connecting")
        self._sign_in.start()

    def _on_code_ready(self, user_code: str) -> None:
        self._set_sign_in("waiting", user_code)

    @pyqtSlot()
    def cancelSignIn(self) -> None:
        self._sign_in.cancel()
        self._show_connect()

    @pyqtSlot()
    def reopenBrowser(self) -> None:
        self._sign_in.open_browser()

    def _on_signed_in(self, payload: dict[str, Any]) -> None:
        if not self._session.apply_login(payload):
            self._on_sign_in_failed(BAD_SIGN_IN, "Could Not Sign In")
            return
        self._load_account()

    def _on_sign_in_failed(self, message: str, title: str) -> None:
        self._set_sign_in("idle")
        self._message(title, message)

    @pyqtSlot()
    def signOut(self) -> None:
        """Order matters: `_stop_work` aborts every tracked call, and the logout request is
        one, so firing it first meant aborting it a line later."""
        self._stop_work()
        self._api.logout()
        self._session.sign_out()
        self._show_connect()

    @pyqtSlot()
    def manageAccount(self) -> None:
        shell_open(BASE_URL)

    @pyqtSlot(str)
    def openUrl(self, url: str) -> None:
        shell_open(url)

    def _stop_work(self) -> None:
        # A run left going holds the config lock, so every later one is refused until the
        # app restarts. The server can end a session too, so this is not only the button's job.
        self._ops.cancel_active()
        self._api.abort_all()

    def _load_account(self, *, refresh_list: bool = True) -> None:
        call = self._api.me()
        call.succeeded.connect(partial(self._on_account, refresh_list=refresh_list))
        call.failed.connect(self._on_account_failed)

    def _settle(self, action: Callable[[], object]) -> None:
        """Run *action* once the startup spinner has been up long enough to be seen. Only
        startup sets the clock; every other path runs immediately."""
        if self._spinner_since is None:
            action()
            return
        waited_ms = int((time.monotonic() - self._spinner_since) * 1000)
        self._spinner_since = None
        QTimer.singleShot(max(0, MIN_SPINNER_MS - waited_ms), action)

    def _on_account(self, payload: dict[str, Any], refresh_list: bool = True) -> None:
        self._account = Account.from_json(payload)
        self._ops.set_account(self._account)
        self.accountChanged.emit()
        self._settle(lambda: self._show_backups(refresh_list))

    def _show_backups(self, refresh_list: bool = True) -> None:
        if self._account is None:
            return
        if self._page != "settings":
            self._set_page("backups")
        if refresh_list:
            self._fetch_backups()

    def _on_account_failed(self, error: ApiError) -> None:
        if error.is_auth_failure:
            self._session.sign_out()
            self._settle(self._show_connect)
            return
        self._settle(lambda: self._fail_to_connect(error))

    def _fail_to_connect(self, error: ApiError) -> None:
        self._show_connect()
        self._message("Could Not Connect", str(error))

    def _fetch_backups(self, offset: int = 0) -> None:
        if self._account is not None and not self._account.access.can_read:
            self._set_list([], 0, BACKUPS_UNAVAILABLE)
            return
        call = self._api.list_backups(offset)
        call.succeeded.connect(self._on_backups)
        call.failed.connect(self._on_backups_failed)

    def _on_backups_failed(self, error: ApiError) -> None:
        self._loading_more = False
        self._message("Could Not Load Backups", str(error))

    def _on_backups(self, payload: dict[str, Any]) -> None:
        """The first page replaces, every page after it appends. Which one comes from the
        response, so replies arriving out of order cannot make page two overwrite the list."""
        page = [Snapshot.from_json(entry) for entry in payload.get("backups", [])]
        total = int(payload.get("total", 0) or 0)
        self._loading_more = False
        if payload.get("offset"):
            self._total = total
            self._backups.append(page)
        else:
            self._set_list(page, total, EMPTY_BACKUPS)

    def _set_list(self, snapshots: list[Snapshot], total: int, empty_message: str) -> None:
        self._total = max(total, len(snapshots))
        self._empty_message = empty_message
        self._loading_more = False
        self._backups.reset(snapshots)
        self.listChanged.emit()

    @pyqtSlot()
    def loadMore(self) -> None:
        """Asked for as the list nears its end. Holds until the page arrives or fails, or one
        flick to the bottom asks for the same page dozens of times."""
        loaded = self._backups.rowCount()
        if self._loading_more or loaded >= self._total:
            return
        self._loading_more = True
        self._fetch_backups(loaded)

    @pyqtSlot()
    def openSettings(self) -> None:
        self._set_info("", "", "")
        self.settingsChanged.emit()
        self._set_page("settings")

    @pyqtSlot()
    def closeSettings(self) -> None:
        self._set_page("backups")

    @pyqtSlot(bool)
    def setDebugLogging(self, enabled: bool) -> None:
        if not self._store(replace(self._settings, debug_logging=enabled)):
            self.settingsChanged.emit()
            return
        set_level(enabled)

    @pyqtSlot(bool)
    def setAutoBackup(self, enabled: bool) -> None:
        """The toggle is the scheduled task: on creates it, off deletes it."""
        if not self.canWrite:
            self.settingsChanged.emit()
            return
        if not self._store(replace(self._settings, auto_backup=enabled)) and enabled:
            self.settingsChanged.emit()
            return

        if not enabled:
            # State kept on purpose: it stays true while off, so re-enabling only backs up
            # if something actually changed.
            ok, detail = remove_task()
            if not ok:
                logger.warning("scheduled task could not be removed: %s", detail)
                self._message(
                    "Could Not Remove The Task",
                    f"Automatic backup was turned off, but its scheduled task could not be removed. {detail}",
                )
            return

        ok, detail = create_task()
        if not ok:
            logger.warning("scheduled task could not be created: %s", detail)
            # The setting is saved but nothing will run it, so this has to be said out loud
            # rather than left to the log.
            self._store(replace(self._settings, auto_backup=False))
            self.settingsChanged.emit()
            self._message("Could Not Schedule Backups", f"Automatic backup could not be scheduled. {detail}")

    def _store(self, settings: CloudSettings) -> bool:
        """Keep the change even when the file will not write. Reports whether it stuck.

        The return value matters for the auto backup toggle: scheduling a task whose setting
        never reached disk gives you a task that reads off and does nothing, for ever.
        """
        self._settings = settings
        self.settingsChanged.emit()
        if save_settings(settings):
            return True
        self._message(
            "Could Not Save Settings",
            "Your settings could not be saved, so they will be forgotten when YASB Cloud closes.",
        )
        return False

    @pyqtSlot(str)
    def addRule(self, rule: str) -> None:
        rule = rule.strip()
        rules = list(self._settings.exclude)
        if not rule or rule in rules:
            return
        if len(rules) >= MAX_EXCLUDE_RULES:
            self._set_info("Too many rules", f"The limit is {MAX_EXCLUDE_RULES}.", "warning")
            return
        self._store(replace(self._settings, exclude=clean_rules([*rules, rule])))

    @pyqtSlot(str)
    def removeRule(self, rule: str) -> None:
        self._store(replace(self._settings, exclude=clean_rules([r for r in self._settings.exclude if r != rule])))

    @pyqtSlot()
    def previewExcluded(self) -> None:
        """Collect twice, with and without the rules, and report the difference."""
        try:
            root = Path(DEFAULT_CONFIG_DIRECTORY)
            everything = collect_files(root)
            kept = collect_files(root, self._settings.exclude)
        except SnapshotError as exc:
            self._message("Could Not Read Your Configuration", str(exc))
            return

        removed = len(everything) - len(kept)
        if removed:
            saved = format_size(sum(c.size for c in everything) - sum(c.size for c in kept))
            message = f"{removed} of {len(everything)} files would be left out, saving {saved}."
        else:
            message = "Your rules do not match anything in the configuration folder."
        self._set_info("Preview", message, "informational")

    @pyqtSlot()
    def openDocs(self) -> None:
        shell_open(WEBSITE_DOCS_URL)

    @pyqtSlot()
    def openLogFolder(self) -> None:
        shell_open(str(cloud_dir()))

    @pyqtSlot(str)
    def backup(self, note: str) -> None:
        self._ops.backup(note)

    @pyqtSlot(str)
    def restore(self, snapshot_id: str) -> None:
        if self._backups.find(snapshot_id) is not None:
            self._ops.restore(snapshot_id)

    @pyqtSlot(str, QUrl)
    def saveCopy(self, snapshot_id: str, folder: QUrl) -> None:
        snapshot = self._backups.find(snapshot_id)
        if snapshot is None or not folder.isLocalFile():
            return
        # Its own folder, so a snapshot cannot overwrite files already in there.
        stamp = snapshot.created_at[:19].replace(":", "-").replace("T", "-")
        self._ops.save_copy(snapshot_id, Path(folder.toLocalFile()) / f"yasb-backup-{stamp}")

    @pyqtSlot(str, str)
    def rename(self, snapshot_id: str, note: str) -> None:
        snapshot = self._backups.find(snapshot_id)
        if snapshot is not None:
            self._ops.save_note(snapshot, note)

    @pyqtSlot(str)
    def share(self, snapshot_id: str) -> None:
        self._ops.share(snapshot_id)

    @pyqtSlot(str)
    def unshare(self, snapshot_id: str) -> None:
        self._ops.unshare(snapshot_id)

    @pyqtSlot(str)
    def delete(self, snapshot_id: str) -> None:
        """Takes this row's actions out until the server answers. Nothing else is affected."""
        if self._backups.find(snapshot_id) is None:
            return
        self._backups.set_pending(snapshot_id, True)
        self._ops.delete(snapshot_id)

    @pyqtSlot(str)
    def copyText(self, text: str) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)

    def _on_note_saved(self, snapshot_id: str, note: str) -> None:
        snapshot = self._backups.find(snapshot_id)
        if snapshot is not None:
            self._backups.replace(replace(snapshot, note=note))

    def _on_shared(self, snapshot_id: str, url: str) -> None:
        snapshot = self._backups.find(snapshot_id)
        if snapshot is not None:
            self._backups.replace(replace(snapshot, share_url=url))
        if url:
            self.shareLinkReady.emit(url)

    def _on_unshared(self, snapshot_id: str) -> None:
        snapshot = self._backups.find(snapshot_id)
        if snapshot is not None:
            self._backups.replace(replace(snapshot, share_url=""))

    def _mark_in_sync(self) -> None:
        """Tell the automatic backup that the cloud now matches the disk, or a manual backup
        is followed a minute later by an automatic one uploading the same thing."""
        mark_in_sync(self._settings.exclude)

    def _on_backed_up(self, snapshot_id: str) -> None:
        """Fetch the one row that was just created rather than reloading the list."""
        self._mark_in_sync()
        call = self._api.get_backup(snapshot_id)
        call.succeeded.connect(self._on_new_backup)

        # The upload succeeded, so a failure here is only a missing row. Saying nothing would
        # read as the backup having been lost.
        def row_failed(_error: ApiError) -> None:
            self._message(
                "Backup Complete",
                "The backup was saved, but this list could not be updated. Reopen the window to see it.",
            )

        call.failed.connect(row_failed)
        # Storage used changed, so the footer is refetched either way.
        self._load_account(refresh_list=False)

    def _on_new_backup(self, payload: dict[str, Any]) -> None:
        snapshot = Snapshot.from_json(payload)
        if snapshot.id and self._backups.find(snapshot.id) is None:
            self._total += 1
            self._backups.prepend(snapshot)

    def _on_busy(self, running: bool) -> None:
        """Only the button that starts one is disabled. Backup against restore is refused by
        config_lock, which is a real lock rather than a greyed-out control."""
        self._busy = running
        if not running:
            self._busy_text = ""
        self.busyChanged.emit()

    def _on_op_status(self, message: str) -> None:
        self._busy, self._busy_text = True, message
        self.busyChanged.emit()

    def _on_op_failed(self, message: str) -> None:
        self._message("Something Went Wrong", message)

    def _on_delete_finished(self, snapshot_id: str, ok: bool) -> None:
        if not ok:
            self._backups.set_pending(snapshot_id, False)
            return
        self._backups.remove(snapshot_id)
        self._total = max(0, self._total - 1)
        self._load_account(refresh_list=False)

    def _on_saved(self, folder: object) -> None:
        shell_open(str(folder))

    def _on_restored(self, result: object) -> None:
        self._mark_in_sync()
        if getattr(result, "bar_was_running", False) and not getattr(result, "bar_restarted", False):
            self._message(
                "Restore Complete", "Your configuration was restored, but YASB did not restart. Start it manually."
            )
