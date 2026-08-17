import logging
import time
from dataclasses import replace
from pathlib import Path

from PyQt6.QtCore import QObject, QSettings, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from core.cloud.api import ApiClient, ApiError, approve_uri
from core.cloud.autobackup import mark_in_sync
from core.cloud.constants import (
    BACKUPS_UNAVAILABLE,
    BAD_SIGN_IN,
    BASE_URL,
    DEVICE_CODE_TTL_S,
    DEVICE_POLL_INTERVAL_S,
    EXPIRED_CODE_APP,
    MIN_SPINNER_MS,
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
from core.cloud.snapshot import collect_files
from core.cloud.ui.backups_view import BackupsView
from core.cloud.ui.connect_view import ConnectView
from core.cloud.ui.settings_view import SettingsView
from core.cloud.workers import device_name
from core.ui.components.button import Button
from core.ui.components.input_dialog import InputDialog
from core.ui.components.loader import Spinner
from core.ui.theme import FONT_FAMILIES, get_tokens, theme_key
from core.ui.views.view_base import ViewBase
from core.utils.shell_utils import shell_open
from settings import DEFAULT_CONFIG_DIRECTORY, WEBSITE_DOCS_URL

logger = logging.getLogger(__name__)

DEFAULT_SIZE = (1000, 700)
MIN_SIZE = (820, 480)

POLL_INTERVAL_MS = DEVICE_POLL_INTERVAL_S * 1000
POLL_TIMEOUT_MS = DEVICE_CODE_TTL_S * 1000
STORAGE_WARN_RATIO = 0.8
"""Fraction of the storage limit that turns the footer amber."""


class CloudWindow(ViewBase, QMainWindow):
    """Owns the session and swaps between the three pages: loading, sign-in, backups."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("YASB Cloud")
        self.setMinimumSize(*MIN_SIZE)
        self._restore_geometry()

        self._session = Session()
        self._api = ApiClient(self._session, self)
        self._api.signed_out.connect(self._on_signed_out)

        self._account: Account | None = None
        self._settings = load_settings()
        self._snapshots: list[Snapshot] = []
        self._dialog = None
        self._spinner_since: float | None = None

        self._ops = Operations(self._api, self._session, self)
        self._ops.status.connect(self._on_op_status)
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

        self.build_app_icon()
        self.build_view()
        self._init_ui()

        QTimer.singleShot(0, self._startup)

    def _restore_geometry(self) -> None:
        """Reopen at the size the user left, or fall back to a default that fits the screen."""
        saved = QSettings("YASB", "Cloud").value("window/geometry")
        if saved is not None and self.restoreGeometry(saved) and self._is_on_screen():
            return
        screen = self.screen() or QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        width, height = DEFAULT_SIZE
        if available is not None:
            width = min(width, available.width())
            height = min(height, available.height())
        self.resize(width, height)

    def _is_on_screen(self) -> bool:
        """A geometry saved on a monitor that is no longer connected must not be restored."""
        return any(s.availableGeometry().intersects(self.frameGeometry()) for s in QApplication.screens())

    def _init_ui(self) -> None:
        app_font = QFont()
        app_font.setFamilies(list(FONT_FAMILIES))
        self.setFont(app_font)

        central = QWidget(self)
        central.setFont(app_font)
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        pages = QWidget(central)
        self.stack = QStackedLayout(pages)
        root.addWidget(pages, stretch=1)

        loading = QWidget(central)
        spinner_box = QVBoxLayout(loading)
        spinner_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spinner_box.addWidget(Spinner(size=48, color=get_tokens()["text_primary"], parent=loading, pen_width=2))
        self.stack.addWidget(loading)

        self.connect_view = ConnectView()
        self.connect_view.connect_requested.connect(self._start_sign_in)
        self.connect_view.cancel_requested.connect(self._cancel_sign_in)
        self.connect_view.reopen_requested.connect(self._sign_in.open_browser)
        self.stack.addWidget(self.connect_view)

        self.backups_view = BackupsView()
        self.backups_view.backup_now_requested.connect(self._handle_backup_now)
        self.backups_view.restore_requested.connect(self._handle_restore)
        self.backups_view.download_requested.connect(self._handle_download)
        self.backups_view.delete_requested.connect(self._ops.delete)
        self.backups_view.rename_requested.connect(self._handle_rename)
        self.backups_view.share_requested.connect(self._handle_share)
        self.backups_view.unshare_requested.connect(self._ops.unshare)
        self.backups_view.copy_link_requested.connect(self._handle_copy_link)
        self.backups_view.load_more_requested.connect(self._fetch_backups)
        self.backups_view.settings_requested.connect(self._show_settings)
        self._ops.busy.connect(self.backups_view.set_busy)
        self.stack.addWidget(self.backups_view)

        self.settings_view = SettingsView()
        self.settings_view.back_requested.connect(lambda: self.stack.setCurrentWidget(self.backups_view))
        self.settings_view.rules_changed.connect(self._save_rules)
        self.settings_view.auto_backup_changed.connect(self._save_auto_backup)
        self.settings_view.debug_logging_changed.connect(self._save_debug_logging)
        self.settings_view.preview_requested.connect(self._preview_excluded)
        self.settings_view.add_rule_requested.connect(self._handle_add_rule)
        self.settings_view.docs_requested.connect(lambda: shell_open(WEBSITE_DOCS_URL))
        self.settings_view.open_log_requested.connect(lambda: shell_open(str(cloud_dir())))
        self.stack.addWidget(self.settings_view)

        self.footer = Footer(central)
        self.footer.manage_requested.connect(lambda: shell_open(BASE_URL))
        self.footer.sign_out_requested.connect(self._sign_out)
        root.addWidget(self.footer)
        self.footer.hide()

    def _startup(self) -> None:
        if self._session.load():
            self._spinner_since = time.monotonic()
            self._load_account()
        else:
            self._settle(self._show_connect)

    def _on_signed_out(self) -> None:
        self._stop_work()
        self._show_connect()

    def _show_connect(self) -> None:
        self._sign_in.cancel()
        self.footer.hide()
        self.connect_view.show_idle()
        self.stack.setCurrentWidget(self.connect_view)

    def _start_sign_in(self) -> None:
        if self._session.load():
            self._load_account()
            return

        self.connect_view.show_connecting()
        self._sign_in.start()

    def _on_code_ready(self, user_code: str) -> None:
        self.connect_view.show_waiting(user_code)

    def _cancel_sign_in(self) -> None:
        self._sign_in.cancel()
        self._show_connect()

    def _on_signed_in(self, payload: dict) -> None:
        if not self._session.apply_login(payload):
            self._on_sign_in_failed(BAD_SIGN_IN, "Could Not Sign In")
            return
        self._load_account()

    def _on_sign_in_failed(self, message: str, title: str) -> None:
        self.connect_view.show_error(message, title=title)

    def _sign_out(self) -> None:
        """Order matters: `_stop_work` aborts every tracked call, and the logout request is
        one, so firing it first meant aborting it a line later."""
        self._stop_work()
        self._api.logout()
        self._session.sign_out()
        self._show_connect()

    def _stop_work(self) -> None:
        # A run left going holds the config lock, so every later one is refused until the
        # app restarts. The server can end a session too, so this is not only the button's job.
        self._ops.cancel_active()
        self._api.abort_all()

    def _load_account(self, *, refresh_list: bool = True) -> None:
        call = self._api.me()
        call.succeeded.connect(lambda payload: self._on_account(payload, refresh_list))
        call.failed.connect(self._on_account_failed)

    def _settle(self, action) -> None:
        """Run *action* once the startup spinner has been up long enough to be seen. Only
        startup sets the clock; every other path runs immediately."""
        if self._spinner_since is None:
            action()
            return
        waited_ms = int((time.monotonic() - self._spinner_since) * 1000)
        self._spinner_since = None
        QTimer.singleShot(max(0, MIN_SPINNER_MS - waited_ms), action)

    def _on_account(self, payload: dict, refresh_list: bool = True) -> None:
        self._account = Account.from_json(payload)
        self._ops.set_account(self._account)
        self.settings_view.set_can_write(self._account.access.can_write)
        self._settle(lambda: self._show_backups(refresh_list))

    def _show_backups(self, refresh_list: bool = True) -> None:
        if self._account is None:
            return
        self.footer.set_account(self._account)
        self.footer.show()
        self.backups_view.set_can_write(self._account.access.can_write)
        self.stack.setCurrentWidget(self.backups_view)
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
        self.connect_view.show_error(str(error), title="Could Not Connect")

    def _fetch_backups(self, offset: int = 0) -> None:
        if self._account is not None and not self._account.access.can_read:
            self.backups_view.set_snapshots([], empty_message=BACKUPS_UNAVAILABLE)
            return
        call = self._api.list_backups(offset)
        call.succeeded.connect(self._on_backups)
        call.failed.connect(self._on_backups_failed)

    def _on_backups_failed(self, error: ApiError) -> None:
        self.backups_view.loading_failed()
        self.backups_view.show_error(str(error), title="Could Not Load Backups")

    def _on_backups(self, payload: dict) -> None:
        """The first page replaces, every page after it appends. Which one comes from the
        response, so replies arriving out of order cannot make page two overwrite the list."""
        page = [Snapshot.from_json(entry) for entry in payload.get("backups", [])]
        total = int(payload.get("total", 0) or 0)

        if payload.get("offset"):
            self._snapshots.extend(page)
            self.backups_view.append_snapshots(page, total=total)
        else:
            self._snapshots = page
            self.backups_view.set_snapshots(page, total=total)

    def _show_settings(self) -> None:
        self.settings_view.set_settings(self._settings)
        self.settings_view.set_can_write(self._account is not None and self._account.access.can_write)
        self.stack.setCurrentWidget(self.settings_view)

    def _save_debug_logging(self, enabled: bool) -> None:
        if not self._store(replace(self._settings, debug_logging=enabled)):
            self.settings_view.set_settings(self._settings)
            return
        set_level(enabled)

    def _save_rules(self, rules: list) -> None:
        self._store(replace(self._settings, exclude=clean_rules(rules)))

    def _save_auto_backup(self, enabled: bool) -> None:
        """The toggle is the scheduled task: on creates it, off deletes it."""
        if not self._store(replace(self._settings, auto_backup=enabled)) and enabled:
            self.settings_view.set_settings(self._settings)
            return

        if not enabled:
            # State kept on purpose: it stays true while off, so re-enabling only backs up
            # if something actually changed.
            ok, detail = remove_task()
            if not ok:
                logger.warning("scheduled task could not be removed: %s", detail)
                self.backups_view.show_error(
                    f"Automatic backup was turned off, but its scheduled task could not be removed. {detail}",
                    title="Could Not Remove The Task",
                )
            return

        ok, detail = create_task()
        if not ok:
            logger.warning("scheduled task could not be created: %s", detail)
            # The setting is saved but nothing will run it, so this has to be said out loud
            # rather than left to the log.
            self.settings_view.set_settings(replace(self._settings, auto_backup=False))
            self._store(replace(self._settings, auto_backup=False))
            self.backups_view.show_error(
                f"Automatic backup could not be scheduled. {detail}",
                title="Could Not Schedule Backups",
            )
            return

    def _store(self, settings: CloudSettings) -> bool:
        """Keep the change even when the file will not write. Reports whether it stuck.

        The return value matters for the auto backup toggle: scheduling a task whose setting
        never reached disk gives you a task that reads off and does nothing, for ever.
        """
        self._settings = settings
        if save_settings(settings):
            return True

        self.backups_view.show_error(
            "Your settings could not be saved, so they will be forgotten when YASB Cloud closes.",
            title="Could Not Save Settings",
        )
        return False

    def _handle_add_rule(self) -> None:
        """One rule per dialog. The same InputDialog the note and rename use."""
        self._dialog = InputDialog(
            parent=self,
            title="Add Rule",
            content="Files matching this pattern are left out of every backup:",
            placeholder="e.g., *.env  or  secrets/*",
            primary_button_text="Add",
            close_button_text="Cancel",
        )
        self._dialog.accepted.connect(self.settings_view.add_rule)
        self._dialog.show_dialog()

    def _preview_excluded(self) -> None:
        """Collect twice, with and without the rules, and report the difference."""
        try:
            root = Path(DEFAULT_CONFIG_DIRECTORY)
            everything = collect_files(root)
            kept = collect_files(root, self._settings.exclude)
        except SnapshotError as exc:
            self.backups_view.show_error(str(exc), title="Could Not Read Your Configuration")
            return

        removed = len(everything) - len(kept)
        saved = sum(c.size for c in everything) - sum(c.size for c in kept)
        self.settings_view.show_preview(removed, len(everything), format_size(saved))

    def _snapshot(self, snapshot_id: str) -> Snapshot | None:
        return next((s for s in self._snapshots if s.id == snapshot_id), None)

    def _handle_backup_now(self) -> None:
        self._dialog = InputDialog(
            parent=self,
            title="Backup Note",
            content="Enter an optional label or note for this snapshot (max 100 chars):",
            placeholder="e.g., My Custom Dark Theme Setup",
            primary_button_text="Backup",
            close_button_text="Cancel",
        )
        self._dialog.accepted.connect(self._ops.backup)
        self._dialog.show_dialog()

    def _handle_restore(self, snapshot_id: str) -> None:
        snapshot = self._snapshot(snapshot_id)
        if snapshot is None:
            return
        self.backups_view.confirm(
            "Restore this backup?",
            "YASB will stop, your files will be replaced, and it will start again. "
            "A copy of your current configuration is saved first.",
            "Restore",
            lambda: self._ops.restore(snapshot_id),
        )

    def _handle_download(self, snapshot_id: str) -> None:
        snapshot = self._snapshot(snapshot_id)
        if snapshot is None:
            return
        chosen = QFileDialog.getExistingDirectory(self, "Choose where to save this backup")
        if not chosen:
            return

        # Its own folder, so a snapshot cannot overwrite files already in there.
        stamp = snapshot.created_at[:19].replace(":", "-").replace("T", "-")
        target = Path(chosen) / f"yasb-backup-{stamp}"
        self._ops.save_copy(snapshot_id, target)

    def _handle_rename(self, snapshot_id: str) -> None:
        snapshot = self._snapshot(snapshot_id)
        if snapshot is None:
            return
        self._dialog = InputDialog(
            parent=self,
            title="Edit Note",
            content="Rename this snapshot so you can recognise it later",
            text=snapshot.note,
            placeholder="e.g., My Custom Dark Theme Setup",
            primary_button_text="Save",
            close_button_text="Cancel",
        )
        self._dialog.accepted.connect(lambda note: self._ops.save_note(snapshot, note))
        self._dialog.show_dialog()

    def _handle_share(self, snapshot_id: str) -> None:
        self.backups_view.confirm(
            "Share publicly?",
            "Anyone with the link can download this backup. Your configuration is published "
            "as it is, including any API keys or tokens it contains.\n\n"
            "You can stop sharing at any time, which makes the link stop working.",
            "Share",
            lambda: self._ops.share(snapshot_id),
            accent_action=True,
        )

    def _handle_copy_link(self, snapshot_id: str) -> None:
        snapshot = self._snapshot(snapshot_id)
        if snapshot is not None and snapshot.share_url:
            self.backups_view.show_share_link(snapshot.share_url)

    def _replace(self, snapshot: Snapshot) -> None:
        """Swap one snapshot in the local list and rebuild only its card."""
        self._snapshots = [snapshot if s.id == snapshot.id else s for s in self._snapshots]
        self.backups_view.replace_row(snapshot)

    def _on_note_saved(self, snapshot_id: str, note: str) -> None:
        snapshot = self._snapshot(snapshot_id)
        if snapshot is not None:
            self._replace(replace(snapshot, note=note))

    def _on_shared(self, snapshot_id: str, url: str) -> None:
        snapshot = self._snapshot(snapshot_id)
        if snapshot is not None:
            self._replace(replace(snapshot, share_url=url))
        if url:
            self.backups_view.show_share_link(url)

    def _on_unshared(self, snapshot_id: str) -> None:
        snapshot = self._snapshot(snapshot_id)
        if snapshot is not None:
            self._replace(replace(snapshot, share_url=""))

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
        call.failed.connect(
            lambda _error: self.backups_view.show_error(
                "The backup was saved, but this list could not be updated. Reopen the window to see it.",
                title="Backup Complete",
            )
        )
        # Storage used changed, so the footer is refetched either way.
        self._load_account(refresh_list=False)

    def _on_new_backup(self, payload: dict) -> None:
        snapshot = Snapshot.from_json(payload)
        if snapshot.id and self._snapshot(snapshot.id) is None:
            self._snapshots.insert(0, snapshot)
            self.backups_view.insert_row(snapshot)

    def _on_op_status(self, message: str) -> None:
        self.backups_view.set_busy(True, message)

    def _on_op_failed(self, message: str) -> None:
        self.backups_view.show_error(message, title="Something Went Wrong")

    def _on_delete_finished(self, snapshot_id: str, ok: bool) -> None:
        self.backups_view.finish_delete(snapshot_id, ok)
        if ok:
            self._snapshots = [s for s in self._snapshots if s.id != snapshot_id]
            self._load_account(refresh_list=False)

    def _on_saved(self, folder) -> None:
        shell_open(str(folder))

    def _on_restored(self, result) -> None:
        self._mark_in_sync()
        if getattr(result, "bar_was_running", False) and not getattr(result, "bar_restarted", False):
            self.backups_view.show_error(
                "Your configuration was restored, but YASB did not restart. Start it manually.",
                title="Restore Complete",
            )

    def closeEvent(self, event) -> None:
        QSettings("YASB", "Cloud").setValue("window/geometry", self.saveGeometry())
        self._sign_in.cancel()
        self._ops.cancel_active()
        self._api.abort_all()
        super().closeEvent(event)


def _reason(access: Access) -> str:
    # What is actually restricted, not why. A past_due subscription carries one reason code
    # for three different states - writes fine, writes stopped, everything stopped - so
    # keying off the code alone said "Backups are paused" while backups were still running.
    if access.reason == "no_subscription":
        return "No active subscription"
    if not access.can_read:
        return "Subscription expired"
    if not access.can_write:
        return "Backups are paused"
    return ""


def _read_deadline(access: Access) -> str:
    # Only while writes are stopped but the backups can still be fetched.
    if access.can_write or not access.can_read or not access.read_until:
        return ""
    moment = parse_timestamp(access.read_until)
    return f"Downloads until {moment.astimezone():%d %b}" if moment else ""


def _footer_state(account: Account) -> str:
    limits, usage = account.limits, account.usage
    if not account.access.can_write:
        return "critical"
    if limits.max_storage_bytes > 0 and usage.bytes >= limits.max_storage_bytes * STORAGE_WARN_RATIO:
        return "caution"
    if account.subscription is not None and not account.subscription.is_active:
        return "caution"
    return "normal"


class Footer(QFrame):
    """Who is signed in, what the plan allows, and how much of it is used."""

    manage_requested = pyqtSignal()
    sign_out_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("CloudFooter")
        self.setFixedHeight(48)
        self._theme_key = theme_key()
        self._state = "normal"

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 16, 0)
        layout.setSpacing(10)

        self._details = QLabel("")
        layout.addWidget(self._details, alignment=Qt.AlignmentFlag.AlignVCenter)

        layout.addStretch()

        self._email = QLabel("")
        layout.addWidget(self._email, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._manage = Button("Manage account", variant="default", font_size=13)
        self._manage.setFixedHeight(28)
        self._manage.clicked.connect(self.manage_requested.emit)
        layout.addWidget(self._manage)

        self._sign_out = Button("Sign out", variant="default", font_size=13)
        self._sign_out.setFixedHeight(28)
        self._sign_out.clicked.connect(self.sign_out_requested.emit)
        layout.addWidget(self._sign_out)

        self.apply_styles()
        QApplication.instance().paletteChanged.connect(self._on_palette_changed)

    def set_account(self, account: Account) -> None:
        subscription = account.subscription
        limits, usage = account.limits, account.usage

        reason = _reason(account.access)
        if not reason:
            reason = subscription.plan_id.title() if subscription else "No subscription"

        self._email.setText(account.email)

        parts = [reason]
        if deadline := _read_deadline(account.access):
            parts.append(deadline)
        if account.access.can_write and limits.max_storage_bytes > 0:
            parts.append(f"{format_size(usage.bytes)} of {format_size(limits.max_storage_bytes)}")

        self._details.setText(" · ".join(parts))
        self._state = _footer_state(account)
        self.apply_styles()

    def _on_palette_changed(self) -> None:
        key = theme_key()
        if key == self._theme_key:
            return
        self._theme_key = key
        self.apply_styles()

    def apply_styles(self) -> None:
        t = get_tokens()
        base = QLabel().font()
        base.setFamilies(list(FONT_FAMILIES))
        base.setPixelSize(13)
        for label in (self._details, self._email):
            label.setFont(base)
            label.setStyleSheet(f"color: {t['text_secondary']}; background: transparent;")

        background = {
            "critical": t["system_critical_bg"],
            "caution": t["system_caution_bg"],
        }.get(self._state, t["layer_alt"])

        self.setStyleSheet(f"""
            QFrame#CloudFooter {{
                background-color: {background};
                border-top: 1px solid {t["divider_stroke_default"]};
            }}
        """)


class SignInFlow(QObject):
    """Emits exactly one of `signed_in` or `failed` per attempt."""

    code_ready = pyqtSignal(str)  # user_code, for the waiting screen
    signed_in = pyqtSignal(dict)  # the token payload
    failed = pyqtSignal(str, str)  # message, dialog title

    def __init__(self, api: ApiClient, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._api = api
        self._device_code = ""
        self._verification_uri = ""
        self._elapsed_ms = 0

        self._poll = QTimer(self)
        self._poll.setInterval(POLL_INTERVAL_MS)
        self._poll.timeout.connect(self._tick)

    def start(self) -> None:
        call = self._api.request_device_code(device_name())
        call.succeeded.connect(self._on_code)
        call.failed.connect(lambda error: self.failed.emit(str(error), "Could Not Sign In"))

    def cancel(self) -> None:
        self._poll.stop()
        self._device_code = ""

    def open_browser(self) -> None:
        if self._verification_uri:
            shell_open(self._verification_uri)

    def _on_code(self, payload: dict) -> None:
        self._device_code = str(payload.get("device_code") or "")
        if not self._device_code:
            # Without it there is nothing to poll for. Starting anyway put a blank code on
            # screen and waited forever, which is the one outcome this class promises not to
            # have: exactly one of signed_in or failed, per attempt.
            self.failed.emit(BAD_SIGN_IN, "Could Not Sign In")
            return

        # Refused rather than opened when it is not on our own site - see approve_uri. Treated
        # as a failed attempt rather than carrying on: there would be no browser to approve in
        # and no address to reach it at, so polling would only spin until the code expired -
        # the same dead wait the missing device_code above exists to prevent.
        self._verification_uri = approve_uri(payload)
        if not self._verification_uri:
            self.failed.emit(BAD_SIGN_IN, "Could Not Sign In")
            return

        self._elapsed_ms = 0
        self.code_ready.emit(payload.get("user_code", ""))
        self.open_browser()
        self._poll.start()

    def _tick(self) -> None:
        if not self._device_code:
            self._poll.stop()
            return

        self._elapsed_ms += POLL_INTERVAL_MS
        if self._elapsed_ms >= POLL_TIMEOUT_MS:
            self.cancel()
            self.failed.emit(EXPIRED_CODE_APP, "Request Expired")
            return

        call = self._api.poll_device_token(self._device_code)
        call.succeeded.connect(self._on_token)
        call.failed.connect(self._on_poll_failed)

    def _on_token(self, payload: dict) -> None:
        # A poll still in flight when cancel() ran lands here. The cleared code says the
        # attempt is over, so do not sign anyone in on the way out.
        if not self._device_code:
            return
        self.cancel()
        self.signed_in.emit(payload)

    def _on_poll_failed(self, error: ApiError) -> None:
        if not self._device_code:
            return
        # Still waiting, not a failure.
        if error.code in ("authorization_pending", "slow_down"):
            return
        self.cancel()
        message = {
            "access_denied": "The request was denied in the browser.",
            "expired_token": EXPIRED_CODE_APP,
        }.get(error.code, str(error))
        self.failed.emit(message, "Could Not Sign In")
