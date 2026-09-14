"""Archive/encrypt and decrypt/restore on a QThread."""

import secrets
import socket
from collections.abc import Callable
from pathlib import Path
from threading import Event

from PyQt6.QtCore import QLockFile, QObject, pyqtSignal

from core.cloud.constants import DOWNLOAD_DIR, LOCK_FILE, SAFETY_DIR, UPLOAD_DIR
from core.cloud.encryption.stream import decrypt_snapshot, encrypt_snapshot
from core.cloud.errors import Cancelled
from core.cloud.restore import RestoreOutcome, extract_archive, restore_with_restart
from core.cloud.session import cloud_dir
from core.cloud.snapshot import create_archive
from settings import DEFAULT_CONFIG_DIRECTORY


def upload_dir() -> Path:
    path = cloud_dir() / UPLOAD_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def download_dir() -> Path:
    path = cloud_dir() / DOWNLOAD_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def download_blob() -> Path:
    return download_dir() / f"{secrets.token_hex(6)}.ysb"


def clear_upload_dir() -> None:
    """Drop what a dead run left behind. Only safe to call while holding config_lock."""
    for stale in upload_dir().glob("*"):
        try:
            stale.unlink()
        except OSError:
            continue


def config_lock() -> QLockFile:
    """One operation on the configuration directory at a time, across the window and the CLI.

    Backup and restore share it: overlapping them archives a half-swapped folder. Qt clears
    the file if the owning process is gone, so a crashed run does not lock the next one out.
    """
    return QLockFile(str(cloud_dir() / LOCK_FILE))


def device_name() -> str:
    try:
        return socket.gethostname()
    except OSError:
        return "Windows PC"


class PrepareWorker(QObject):
    """Config directory to archive to encrypted .ysb, ready to upload."""

    prepared = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, master_key: bytes, note: str, max_total_bytes: int, exclude: tuple[str, ...] = ()) -> None:
        super().__init__()
        self._master_key = master_key
        self._note = note
        self._max_total_bytes = max_total_bytes
        self._exclude = exclude
        self._stop = Event()

    def cancel(self) -> None:
        """Stop at the next file or frame. Called from the UI thread, hence the Event."""
        self._stop.set()

    def run(self) -> None:
        archive = blob = None
        try:
            clear_upload_dir()
            stem = secrets.token_hex(6)
            archive = upload_dir() / f"{stem}.zip"
            blob = upload_dir() / f"{stem}.ysb"

            snapshot = create_archive(
                Path(DEFAULT_CONFIG_DIRECTORY),
                archive,
                max_total_bytes=self._max_total_bytes,
                exclude=self._exclude,
                should_stop=self._stop.is_set,
            )
            info = encrypt_snapshot(archive, blob, self._master_key, should_stop=self._stop.is_set)

            name = device_name()
            self.prepared.emit(
                {
                    "blob": blob,
                    "sha256": info.sha256,
                    "size_bytes": info.ciphertext_size,
                    "file_count": snapshot.file_count,
                    "note": self._note or name,
                    "device_name": name,
                }
            )
        except Cancelled:
            if blob is not None:
                blob.unlink(missing_ok=True)
        except Exception as exc:
            self.failed.emit(str(exc))
            if blob is not None:
                blob.unlink(missing_ok=True)
        finally:
            if archive is not None:
                archive.unlink(missing_ok=True)


Apply = Callable[[Path, Callable[[], bool]], object]
"""What DecryptWorker does with the decrypted zip. Takes the stop check as well as the path,
so the loop inside it can be cut short the same way the decrypt above it is."""


def restore_config(archive: Path, should_stop: Callable[[], bool]) -> RestoreOutcome:
    """Replace the configuration directory, with the bar stopped around it."""
    return restore_with_restart(
        archive, Path(DEFAULT_CONFIG_DIRECTORY), safety_dir=cloud_dir() / SAFETY_DIR, should_stop=should_stop
    )


def unpack_into(target: Path) -> Apply:
    """Write the snapshot to a folder the user picked, leaving the configuration alone."""

    def apply(archive: Path, should_stop: Callable[[], bool]) -> Path:
        extract_archive(archive, target, should_stop=should_stop)
        return target

    return apply


class DecryptWorker(QObject):
    """Decrypts a downloaded .ysb here and hands the zip to `apply`."""

    done = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, blob: Path, master_key: bytes, apply: Apply) -> None:
        super().__init__()
        self._blob = blob
        self._master_key = master_key
        self._apply = apply
        self._stop = Event()

    def cancel(self) -> None:
        self._stop.set()

    def run(self) -> None:
        archive = None
        try:
            archive = self._blob.with_suffix(".zip")
            decrypt_snapshot(self._blob, archive, self._master_key, should_stop=self._stop.is_set)
            self.done.emit(self._apply(archive, self._stop.is_set))
        except Cancelled:
            pass
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            if archive is not None:
                archive.unlink(missing_ok=True)
            self._blob.unlink(missing_ok=True)
