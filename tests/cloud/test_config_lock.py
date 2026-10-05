"""One operation on the configuration directory at a time.

Backup and restore share a single lock, so any of them excludes the others - in this process
and in another one, which is what stops a CLI restore running under the window's.

    python -m pytest tests/cloud/test_config_lock.py -q
"""

import pytest
from PyQt6.QtGui import QCloseEvent

from core.cloud.api import ApiClient
from core.cloud.constants import BUSY_MESSAGE
from core.cloud.session import Session
from core.cloud.ui.window import CloudWindow, Operations
from core.cloud.workers import config_lock


@pytest.fixture
def cloud_home(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    return tmp_path


@pytest.fixture
def ops(qapp, cloud_home):
    session = _signed_in()
    return Operations(ApiClient(session), session)


def _refusals(operations: Operations) -> list[str]:
    seen: list[str] = []
    operations.failed.connect(seen.append)
    return seen


def test_a_second_holder_cannot_take_the_lock(cloud_home):
    """The cross-process case. A separate instance is what another yasbc run would hold."""
    held = config_lock()
    assert held.tryLock(0)
    try:
        assert not config_lock().tryLock(0)
    finally:
        held.unlock()
    assert config_lock().tryLock(0)


def test_restore_is_refused_while_something_else_holds_the_lock(ops):
    other = config_lock()
    assert other.tryLock(0)
    try:
        refused = _refusals(ops)
        ops.restore("any-snapshot-id")
    finally:
        other.unlock()

    assert refused == [BUSY_MESSAGE]


def test_backup_is_refused_while_a_restore_holds_the_lock(ops, monkeypatch):
    """The pairing that used to be unguarded: a restore replacing the directory a backup
    is reading would archive it half-swapped."""
    monkeypatch.setattr(ops, "_session", _signed_in())
    ops.set_account(_account())

    other = config_lock()
    assert other.tryLock(0)
    try:
        refused = _refusals(ops)
        ops.backup("note")
    finally:
        other.unlock()

    assert refused == [BUSY_MESSAGE]


def test_cancelling_a_restore_gives_back_its_lock_and_its_temp_file(ops, cloud_home):
    """The reason operations own their resources: one release path, reached by every exit.
    Cancelling used to leave the lock held and the blob on disk, because only the success
    callback cleaned up."""
    ops.restore("any-snapshot-id")
    assert not config_lock().tryLock(0), "the restore should be holding the lock"

    blobs = list((cloud_home / "YASB" / "cloud" / "tmp" / "download").glob("*.ysb"))

    ops.cancel_active()

    assert config_lock().tryLock(0), "cancelling must give the lock back"
    assert not any(blob.exists() for blob in blobs), "and must take its temporary file with it"


def test_a_second_operation_is_refused_while_one_is_active(ops):
    refused = _refusals(ops)
    ops.restore("first")
    ops.restore("second")

    assert refused == [BUSY_MESSAGE]
    ops.cancel_active()


def test_closing_the_window_cancels_rather_than_refusing(qapp, cloud_home):
    """Closing always closes. Whatever is running is cancelled and released; the user is
    never asked to wait and never shown a dialog about it."""
    window = CloudWindow()
    window._session.master_key = bytes(32)
    warned: list[str] = []
    window.backups_view.show_error = lambda message, title="Error": warned.append(title)

    window._ops.restore("any-snapshot-id")
    assert window._ops._active is not None

    event = QCloseEvent()
    event.accept()
    window.closeEvent(event)

    assert event.isAccepted(), "the close must never be refused"
    assert warned == [], "and must never explain itself"
    assert window._ops._active is None, "and must leave nothing running"
    assert config_lock().tryLock(0), "with the lock handed back"


def _signed_in() -> Session:
    session = Session()
    session.master_key = bytes(32)
    return session


def _account():
    from core.cloud.models import Account

    return Account.from_json({"user": {"id": "u", "email": "e@example.com"}})
