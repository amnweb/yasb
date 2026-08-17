"""Backup, restore and save-a-copy as objects that own what they create.

Split from the window on purpose: the CLI runs the same three jobs and must not import
QtWidgets to do it. Everything here needs only a Qt event loop, which both a QApplication
and the CLI's QCoreApplication provide.
"""

import logging
from functools import partial
from pathlib import Path

from PyQt6.QtCore import QLockFile, QObject, QThread, pyqtSignal
from PyQt6.QtNetwork import QNetworkReply

from core.cloud.api import ApiClient, ApiError, Call, save_reply
from core.cloud.constants import BUSY_MESSAGE, NOTE_MAX_LENGTH, SHUTDOWN_WAIT_MS
from core.cloud.models import Account, Snapshot
from core.cloud.session import Session
from core.cloud.settings import load as load_settings
from core.cloud.workers import (
    DecryptWorker,
    PrepareWorker,
    config_lock,
    download_blob,
    restore_config,
    unpack_into,
)
from settings import BUILD_VERSION

logger = logging.getLogger(__name__)

_winding_down: set[QThread] = set()
"""Live worker threads. Destroying a running QThread aborts the process."""


def _forget(thread: QThread) -> None:
    _winding_down.discard(thread)
    thread.deleteLater()


class Operation(QObject):
    """One job: a backup, a restore, or saving a copy. Owns the lock, temp files, call and
    worker thread it creates, and releases all of them in `_release`."""

    status = pyqtSignal(str)
    failed = pyqtSignal(str)  # why, in a sentence the user can read
    finished = pyqtSignal(object)  # the result, or None if it failed or was cancelled

    def __init__(self, api: ApiClient, session: Session, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._api = api
        self._session = session
        self._lock: QLockFile | None = None
        self._thread: QThread | None = None
        self._worker = None
        self._call: Call | None = None
        self._reply: QNetworkReply | None = None
        self._temp: list[Path] = []
        self._settled = False

    def start(self) -> None:
        raise NotImplementedError

    def cancel(self) -> None:
        """Stop and let go of everything. Silent, because the user asked for it."""
        self._settle(None)

    def _succeed(self, result: object) -> None:
        self._settle(result)

    def _fail(self, message: str) -> None:
        logger.warning("%s failed: %s", type(self).__name__, message)
        self._settle(None, message=message)

    def _settle(self, result: object, *, message: str = "") -> None:
        if self._settled:
            return
        self._settled = True
        self._release()
        if message:
            self.failed.emit(message)
        self.finished.emit(result)

    def _release(self) -> None:
        """Transfers first, then files: an upload holds its blob open and Windows will not
        delete an open file."""
        call, self._call = self._call, None
        if call is not None:
            call.abort()
        reply, self._reply = self._reply, None
        if reply is not None:
            reply.abort()
            reply.deleteLater()
        self._stop_worker(cancel=True)
        for path in self._temp:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass  # a file we cannot delete must not cost us the lock
        self._temp.clear()
        if self._lock is not None:
            self._lock.unlock()
            self._lock = None

    def _claim(self) -> bool:
        """Take the configuration lock. False when a backup or restore already holds it."""
        lock = config_lock()
        if not lock.tryLock(0):
            return False
        self._lock = lock
        return True

    def _keep(self, path: Path) -> Path:
        """A temporary file this operation is responsible for deleting."""
        self._temp.append(path)
        return path

    def _start_worker(self, worker) -> None:
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        thread.finished.connect(partial(_forget, thread))
        _winding_down.add(thread)
        self._thread, self._worker = thread, worker
        thread.start()

    def _stop_worker(self, *, cancel: bool) -> None:
        """Retire the worker thread. quit() cannot interrupt a running run(), so the worker
        is told to stop first."""
        thread, worker = self._thread, self._worker
        if thread is None:
            return
        self._thread = self._worker = None

        if cancel and worker is not None:
            worker.cancel()
        thread.quit()
        thread.wait(SHUTDOWN_WAIT_MS)

    def _send(self, call: Call, then) -> None:
        """Hold on to an in-flight call so cancelling can abort it."""
        self._call = call
        call.succeeded.connect(then)
        call.failed.connect(lambda error: self._fail(str(error)))

    def _download(self, snapshot_id: str, target: Path, then) -> None:
        """Fetch a snapshot to `target` and then call `then`. Cancelling aborts it."""
        reply = self._api.download(snapshot_id)
        self._reply = reply

        def arrived() -> None:
            if self._settled:
                return
            self._reply = None
            error = save_reply(reply, target)
            if error is None:
                then()
            elif error.code != "cancelled":
                self._fail(str(error))

        reply.finished.connect(arrived)


class BackupOperation(Operation):
    """Archive the configuration, reserve a snapshot, upload it."""

    def __init__(self, api, session, *, note: str, max_total_bytes: int, parent=None) -> None:
        super().__init__(api, session, parent)
        self._note = note
        self._max_total_bytes = max_total_bytes

    def start(self) -> None:
        if not self._claim():
            self._fail(BUSY_MESSAGE)
            return
        self.status.emit("Backing up...")
        # Read here rather than at the call sites, so the window, the CLI and the automatic
        # backup all archive with the same rules without each having to remember to load them.
        worker = PrepareWorker(self._session.master_key, self._note, self._max_total_bytes, load_settings().exclude)
        worker.prepared.connect(self._prepared)
        worker.failed.connect(self._fail)
        self._start_worker(worker)

    def _prepared(self, prepared: dict) -> None:
        if self._settled:
            return
        self._keep(prepared["blob"])
        self._stop_worker(cancel=False)

        self._send(
            self._api.begin_backup(
                size_bytes=prepared["size_bytes"],
                sha256=prepared["sha256"],
                file_count=prepared["file_count"],
                note=prepared["note"],
                device_name=prepared["device_name"],
                app_version=BUILD_VERSION,
            ),
            lambda ticket: self._upload(prepared, ticket),
        )

    def _upload(self, prepared: dict, ticket: dict) -> None:
        if self._settled:
            return
        # Read once and checked, not indexed twice inside slots: a KeyError escaping a Qt slot
        # aborts the process rather than raising.
        backup_id = str(ticket.get("backup_id") or "")
        if not backup_id:
            self._fail("The server did not say where to put this backup.")
            return

        self.status.emit("Uploading...")
        try:
            call = self._api.upload(backup_id, prepared["blob"])
        except OSError as exc:
            self._fail(f"The snapshot could not be read for upload: {exc.strerror or exc}")
            return
        self._send(call, lambda _payload: self._succeed(backup_id))


class RestoreOperation(Operation):
    """Download a snapshot and put it back over the configuration directory."""

    def __init__(self, api, session, snapshot_id: str, parent=None) -> None:
        super().__init__(api, session, parent)
        self._snapshot_id = snapshot_id

    def start(self) -> None:
        if not self._claim():
            self._fail(BUSY_MESSAGE)
            return
        self.status.emit("Downloading...")
        blob = self._keep(download_blob())
        self._download(self._snapshot_id, blob, lambda: self._apply(blob))

    def _apply(self, blob: Path) -> None:
        self.status.emit("Restoring...")
        worker = DecryptWorker(blob, self._session.master_key, restore_config)
        worker.done.connect(self._succeed)
        worker.failed.connect(self._fail)
        self._start_worker(worker)


class SaveCopyOperation(Operation):
    """The same download, unpacked where the user asked. The configuration is untouched, so
    this takes no lock and the bar keeps running."""

    def __init__(self, api, session, snapshot_id: str, target: Path, parent=None) -> None:
        super().__init__(api, session, parent)
        self._snapshot_id = snapshot_id
        self._target = target

    def start(self) -> None:
        self.status.emit("Downloading...")
        blob = self._keep(download_blob())
        self._download(self._snapshot_id, blob, lambda: self._apply(blob))

    def _apply(self, blob: Path) -> None:
        self.status.emit("Saving...")
        worker = DecryptWorker(blob, self._session.master_key, unpack_into(self._target))
        worker.done.connect(self._succeed)
        worker.failed.connect(self._fail)
        self._start_worker(worker)


class Operations(QObject):
    """Runs one Operation at a time, plus the small account calls that own nothing."""

    status = pyqtSignal(str)  # progress text for the backups view
    busy = pyqtSignal(bool)  # a backup, restore or save is running; the only thing the UI locks
    failed = pyqtSignal(str)  # why, in a sentence the user can read
    restored = pyqtSignal(object)  # RestoreOutcome
    saved = pyqtSignal(object)  # folder a copy was written to

    # One row changed, and which one. Reloading the list would throw away the reader's
    # position and rebuild every widget to alter one of them.
    backed_up = pyqtSignal(str)  # id of the snapshot just uploaded
    delete_finished = pyqtSignal(str, bool)  # id, whether the server confirmed it
    note_saved = pyqtSignal(str, str)  # id, the note now stored
    shared = pyqtSignal(str, str)  # id, the public link the server minted
    unshared = pyqtSignal(str)  # id

    def __init__(self, api: ApiClient, session: Session, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._api = api
        self._session = session
        self._account: Account | None = None
        self._active: Operation | None = None

    def set_account(self, account: Account | None) -> None:
        self._account = account

    def cancel_active(self) -> None:
        """Everything in flight, stopped and cleaned up. What closing the window calls."""
        if self._active is not None:
            self._active.cancel()

    def backup(self, note: str) -> None:
        if self._session.master_key is None or self._account is None:
            self.failed.emit("Not ready yet. Wait for your account to finish loading and try again.")
            return
        # No fallback to the device name: the row already falls back to it for display.
        note = note.strip()[:NOTE_MAX_LENGTH]
        self._begin(
            BackupOperation(
                self._api,
                self._session,
                note=note,
                max_total_bytes=self._account.limits.max_snapshot_bytes,
                parent=self,
            ),
            self.backed_up.emit,
        )

    def restore(self, snapshot_id: str) -> None:
        self._begin(RestoreOperation(self._api, self._session, snapshot_id, parent=self), self.restored.emit)

    def save_copy(self, snapshot_id: str, target: Path) -> None:
        self._begin(SaveCopyOperation(self._api, self._session, snapshot_id, target, parent=self), self.saved.emit)

    def _begin(self, operation: Operation, on_result) -> None:
        if self._active is not None:
            self.failed.emit(BUSY_MESSAGE)
            return
        self._active = operation
        operation.status.connect(self.status)
        operation.failed.connect(self.failed)
        operation.finished.connect(lambda result: self._ended(operation, result, on_result))
        self.busy.emit(True)
        try:
            operation.start()
        except Exception as exc:
            operation.cancel()
            self.failed.emit(str(exc))

    def _ended(self, operation: Operation, result: object, on_result) -> None:
        if self._active is operation:
            self._active = None
            self.busy.emit(False)
        operation.deleteLater()
        if result is not None:
            on_result(result)

    def share(self, snapshot_id: str) -> None:
        call = self._api.share_backup(snapshot_id)
        call.succeeded.connect(lambda payload: self.shared.emit(snapshot_id, str(payload.get("url", ""))))
        call.failed.connect(lambda error: self.failed.emit(str(error)))

    def unshare(self, snapshot_id: str) -> None:
        call = self._api.unshare_backup(snapshot_id)
        call.succeeded.connect(lambda _payload: self.unshared.emit(snapshot_id))
        call.failed.connect(lambda error: self.failed.emit(str(error)))

    def save_note(self, snapshot: Snapshot, note: str) -> None:
        note = (note.strip() or snapshot.device_name)[:NOTE_MAX_LENGTH]
        call = self._api.update_note(snapshot.id, note)
        call.succeeded.connect(lambda _payload: self.note_saved.emit(snapshot.id, note))
        call.failed.connect(lambda error: self.failed.emit(str(error)))

    def delete(self, snapshot_id: str) -> None:
        call = self._api.delete_backup(snapshot_id)
        call.succeeded.connect(lambda _payload: self.delete_finished.emit(snapshot_id, True))
        call.failed.connect(lambda error: self._delete_failed(snapshot_id, error))

    def _delete_failed(self, snapshot_id: str, error: ApiError) -> None:
        """The row comes back before the dialog, or it looks deleted behind it."""
        self.delete_finished.emit(snapshot_id, False)
        self.failed.emit(str(error))
