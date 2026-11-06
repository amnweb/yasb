# pyright: reportPrivateUsage=false

import threading
from collections.abc import Callable, Iterator
from ctypes import Array, wintypes
from unittest.mock import Mock, call

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QMetaObject, QObject, QUrl
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlComponent, QQmlEngine

from core.qml_types import register_qml_types
from core.services.recycle_bin import recycle_bin_monitor
from core.services.recycle_bin.recycle_bin_monitor import (
    COOLDOWN_MS,
    BinInfo,
    RecycleBin,
    RecycleBinMonitor,
    empty_recycle_bin,
)
from core.utils.win32.constants import (
    DRIVE_CDROM,
    DRIVE_FIXED,
    DRIVE_REMOTE,
    DRIVE_REMOVABLE,
    FILE_NOTIFY_CHANGE_DIR_NAME,
    FILE_NOTIFY_CHANGE_FILE_NAME,
    INFINITE,
    INVALID_HANDLE_VALUE,
    S_OK,
    SHERB_NOSOUND,
    WAIT_OBJECT_0,
    WAIT_TIMEOUT,
)
from tests.support.qt import wait

type Done = Callable[[object, str], None]


@pytest.fixture
def jobs(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Callable[[], object], Done]]:
    """Background work the service asked for, run only when a test answers it."""
    scheduled: list[tuple[Callable[[], object], Done]] = []

    def schedule(work: Callable[[], object], done: Done, _failure: str) -> None:
        scheduled.append((work, done))

    monkeypatch.setattr(recycle_bin_monitor, "run_in_worker", schedule)
    return scheduled


@pytest.fixture
def no_watch(monkeypatch: pytest.MonkeyPatch) -> Iterator[Mock]:
    """No watch thread; each monitor gets a fresh shared slot."""
    monkeypatch.setattr(RecycleBinMonitor, "_feeds", {})
    watch = Mock()
    monkeypatch.setattr(recycle_bin_monitor, "_Watch", watch)
    yield watch


def test_a_burst_of_changes_reads_the_bin_once_then_once_after_the_cooldown(
    qapp: QGuiApplication, jobs: list[tuple[Callable[[], object], Done]], no_watch: Mock
) -> None:
    user = QObject()
    monitor = RecycleBinMonitor.join(None, user)
    notify = no_watch.call_args.args[0]

    def burst() -> None:
        for _ in range(5_000):
            notify()

    watcher = threading.Thread(target=burst)
    watcher.start()
    watcher.join()
    qapp.processEvents()
    assert len(jobs) == 1

    full: BinInfo = {"num_items": 5_000, "size_bytes": 5_000}
    jobs[0][1](full, "")
    assert monitor.info == full
    # Changes during the first read are read once the cooldown ends
    wait(COOLDOWN_MS + 200)
    assert len(jobs) == 2
    jobs[1][1]({"num_items": 0, "size_bytes": 0}, "")
    assert monitor.info["num_items"] == 0
    wait(COOLDOWN_MS + 200)
    assert len(jobs) == 2
    sip.delete(user)


def test_only_fixed_drive_watches_share_one_wait_and_survive_a_failed_watch(monkeypatch: pytest.MonkeyPatch) -> None:
    win32 = Mock()
    win32.GetLogicalDrives.return_value = 0b11111100  # C through H
    win32.GetDriveTypeW.side_effect = [
        DRIVE_FIXED,
        DRIVE_FIXED,
        DRIVE_FIXED,
        DRIVE_REMOVABLE,
        DRIVE_REMOTE,
        DRIVE_CDROM,
    ]
    win32.WaitForSingleObject.return_value = WAIT_TIMEOUT
    win32.FindFirstChangeNotificationW.side_effect = [10, INVALID_HANDLE_VALUE, 20]
    win32.FindNextChangeNotification.side_effect = [False, True]
    monkeypatch.setattr(recycle_bin_monitor, "kernel32", win32)
    signals = iter([WAIT_OBJECT_0 + 1, WAIT_OBJECT_0 + 1, WAIT_OBJECT_0])
    waits: list[tuple[int | None, ...]] = []

    def wait_for(count: int, handles: Array[wintypes.HANDLE], wait_all: bool, timeout: int) -> int:
        assert count == len(handles) and not wait_all and timeout == INFINITE
        waits.append(tuple(handles))
        return next(signals)

    win32.WaitForMultipleObjects.side_effect = wait_for
    notify = Mock()
    recycle_bin_monitor._watch_bins(99, notify)

    flags = FILE_NOTIFY_CHANGE_DIR_NAME | FILE_NOTIFY_CHANGE_FILE_NAME
    assert win32.FindFirstChangeNotificationW.call_args_list == [
        call(r"C:\$Recycle.Bin", True, flags),
        call(r"D:\$Recycle.Bin", True, flags),
        call(r"E:\$Recycle.Bin", True, flags),
    ]
    assert waits == [(99, 10, 20), (99, 20), (99, 20)]
    assert win32.FindNextChangeNotification.call_args_list == [call(10), call(20)]
    assert win32.FindCloseChangeNotification.call_args_list == [call(10), call(20)]
    assert notify.call_count == 3  # Once the watches are set, and two drive changes


@pytest.mark.parametrize("thread_ends_first", [False, True])
def test_the_stop_event_closes_only_after_the_thread_and_the_release(
    qapp: QGuiApplication,
    monkeypatch: pytest.MonkeyPatch,
    jobs: list[tuple[Callable[[], object], Done]],
    thread_ends_first: bool,
) -> None:
    win32 = Mock()
    win32.CreateEventW.return_value = 99
    monkeypatch.setattr(recycle_bin_monitor, "kernel32", win32)
    watch = recycle_bin_monitor._Watch(Mock())
    [(_work, finished)] = jobs

    if thread_ends_first:
        finished(None, "Could not wait for Recycle Bin changes")
        win32.CloseHandle.assert_not_called()
        watch.release()
    else:
        watch.release()
        win32.CloseHandle.assert_not_called()
        finished(None, "")
    win32.SetEvent.assert_called_once_with(99)
    win32.CloseHandle.assert_called_once_with(99)


def test_qml_recycle_bins_share_one_monitor_while_used(qapp: QGuiApplication, no_watch: Mock) -> None:
    register_qml_types()
    engine = QQmlEngine()
    component = QQmlComponent(engine)
    component.setData(b"import QtQml\nimport Yasb\nQtObject {}", QUrl())
    unused = component.create()
    assert unused is not None, [error.toString() for error in component.errors()]
    assert RecycleBinMonitor._feeds == {}

    component.setData(
        b"""
        import QtQuick
        import Yasb
        Item {
            RecycleBin { id: bin }
            property real count: bin.itemCount
            property real bytes: bin.sizeBytes
        }
        """,
        QUrl(),
    )
    first, second = component.create(), component.create()
    assert first is not None and second is not None, [error.toString() for error in component.errors()]
    no_watch.assert_called_once()
    monitor = RecycleBinMonitor._feeds[None]
    assert first.property("count") == first.property("bytes") == 0

    size = 8 * 1024**3
    monitor.info = {"num_items": 2, "size_bytes": size}
    monitor.changed.emit()
    for instance in (first, second):
        assert instance.property("count") == 2
        assert instance.property("bytes") == size

    first.deleteLater()
    wait(20)
    assert RecycleBinMonitor._feeds == {None: monitor}
    no_watch.return_value.release.assert_not_called()
    second.deleteLater()
    wait(20)
    assert RecycleBinMonitor._feeds == {}
    no_watch.return_value.release.assert_called_once_with()
    sip.delete(unused)


def test_qml_opens_and_empties_the_bin_once_at_a_time(
    qapp: QGuiApplication,
    monkeypatch: pytest.MonkeyPatch,
    jobs: list[tuple[Callable[[], object], Done]],
    no_watch: Mock,
) -> None:
    opened = Mock()
    empty = Mock(return_value=S_OK)
    monkeypatch.setattr(recycle_bin_monitor, "open_recycle_bin", opened)
    monkeypatch.setattr(recycle_bin_monitor.shell32, "SHEmptyRecycleBinW", empty)
    client = RecycleBin()
    QMetaObject.invokeMethod(client, "open")
    # Opened once the click has finished, as Explorer can take focus
    opened.assert_not_called()
    qapp.processEvents()
    opened.assert_called_once_with()

    QMetaObject.invokeMethod(client, "empty")
    empty_recycle_bin()
    [(work, done)] = jobs
    done(work(), "")
    empty.assert_called_once_with(None, None, SHERB_NOSOUND)

    empty_recycle_bin()
    assert len(jobs) == 2
    jobs[1][1](None, "")
    sip.delete(client)
