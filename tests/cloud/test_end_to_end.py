"""End-to-end: configuration directory → archive → encrypt → decrypt → restore.

This is the seam between the crypto layer and the file layer, and the acceptance test for
the offline half of YASB Cloud: a config directory must survive a full round trip
byte-for-byte, including on a machine that has never seen it before.

    python -m pytest tests/cloud/test_end_to_end.py -q
"""

import os
import secrets
import tempfile
import zipfile
from pathlib import Path

from core.cloud.encryption.stream import decrypt_snapshot, encrypt_snapshot
from core.cloud.restore import restore_archive
from core.cloud.snapshot import collect_files, create_archive

CONFIG_TREE = {
    "config.yaml": b"watch_stylesheet: true\nbars:\n  status-bar:\n    enabled: true\n",
    "styles.css": b".yasb-bar { background-color: rgba(0,0,0,0.5); }\n",
    "assets/wallpaper.png": os.urandom(64 * 1024),
    "assets/fonts/custom.ttf": os.urandom(32 * 1024),
    "scripts/on-start.ps1": b"Write-Host 'hello'\n",
    "unicode-éàü.yaml": "note: café\n".encode(),
    "empty.txt": b"",
}

NOISE = {
    "yasb.log": b"log line\n" * 100,
    "yasb.log.3": b"older log\n" * 100,
    "editor.tmp": b"scratch",
    "__pycache__/cached.pyc": b"\x00\x01",
}


def _build(root: Path, files: dict[str, bytes]) -> Path:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return root


def test_full_round_trip_onto_a_fresh_machine():
    """Back up on one PC, wipe it, restore onto an empty directory elsewhere."""
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        master_key = secrets.token_bytes(32)

        # --- Device A: create the backup ---
        config = _build(base / "device-a" / "yasb", CONFIG_TREE | NOISE)
        work = base / "work"
        work.mkdir()

        archive = work / "snapshot.zip"
        result = create_archive(config, archive)
        with zipfile.ZipFile(archive) as built:
            assert set(built.namelist()) == set(CONFIG_TREE), "wrong file set collected"
        assert result.file_count == len(CONFIG_TREE), "log and scratch files were not skipped"

        blob = work / "snapshot.ysb"
        info = encrypt_snapshot(archive, blob, master_key)
        assert len(info.sha256) == 64

        # The snapshot is what must be opaque. The note and the device name are ordinary
        # columns on the server now, and deliberately readable there.
        payload = blob.read_bytes()
        assert b"watch_stylesheet" not in payload
        assert b"yasb-bar" not in payload

        # --- Device B: nothing but the master key and the blob ---
        incoming = base / "device-b" / "download"
        incoming.mkdir(parents=True)
        restored_archive = incoming / "snapshot.zip"
        decrypt_snapshot(blob, restored_archive, master_key)

        target = base / "device-b" / "yasb"
        restore_archive(restored_archive, target)

        for relative, content in CONFIG_TREE.items():
            assert (target / relative).read_bytes() == content, f"{relative} did not survive the round trip"

        # Logs were never backed up, so they must not appear on the new machine.
        for relative in NOISE:
            assert not (target / relative).exists(), f"{relative} should not have been restored"


def test_round_trip_over_an_existing_configuration():
    """The common case: restoring onto a machine that already has a config."""
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        master_key = secrets.token_bytes(32)

        source = _build(base / "source", CONFIG_TREE)
        work = base / "work"
        work.mkdir()
        archive = work / "snap.zip"
        create_archive(source, archive)
        blob = work / "snap.ysb"
        encrypt_snapshot(archive, blob, master_key)

        target = _build(base / "target", {"config.yaml": b"local edits\n", "my-own-notes.md": b"keep me\n"})
        safety = base / "safety"

        decrypt_snapshot(blob, work / "restored.zip", master_key)
        result = restore_archive(work / "restored.zip", target, safety_dir=safety)

        assert (target / "config.yaml").read_bytes() == CONFIG_TREE["config.yaml"], "snapshot did not win"
        assert not (target / "my-own-notes.md").exists(), "a file added since the backup survived"
        assert result.safety_archive is not None and result.safety_archive.is_file()

        # The removed file is still recoverable from the safety archive.
        with zipfile.ZipFile(result.safety_archive) as saved:
            assert saved.read("my-own-notes.md") == b"keep me\n"


def test_a_tampered_blob_never_reaches_the_configuration():
    """The integrity check must fire before any file is touched."""
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        master_key = secrets.token_bytes(32)

        source = _build(base / "source", CONFIG_TREE)
        work = base / "work"
        work.mkdir()
        archive = work / "snap.zip"
        create_archive(source, archive)
        blob = work / "snap.ysb"
        encrypt_snapshot(archive, blob, master_key)

        corrupted = bytearray(blob.read_bytes())
        corrupted[len(corrupted) // 2] ^= 0x01
        (work / "bad.ysb").write_bytes(bytes(corrupted))

        target = _build(base / "target", {"config.yaml": b"precious\n"})
        restored_archive = work / "restored.zip"

        try:
            decrypt_snapshot(work / "bad.ysb", restored_archive, master_key)
            raise AssertionError("a tampered blob was accepted")
        except Exception as exc:
            assert type(exc).__name__ == "IntegrityError", f"unexpected error type: {type(exc).__name__}"

        assert not restored_archive.exists(), "a partial archive was written"
        assert (target / "config.yaml").read_bytes() == b"precious\n", "the configuration was touched"


def test_symlinks_in_the_config_directory_are_not_followed():
    """A link inside the config directory must not pull in outside files.

    Creating symlinks on Windows needs Developer Mode or elevation, so this reports rather
    than fails when the environment cannot make one.
    """
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        secret = base / "outside-secret.txt"
        secret.write_bytes(b"should never be backed up")

        config = _build(base / "yasb", {"config.yaml": b"real\n"})
        link = config / "link.txt"
        try:
            link.symlink_to(secret)
        except OSError, NotImplementedError:
            print("      (skipped: this environment cannot create symlinks)")
            return

        assert [c.relative for c in collect_files(config)] == ["config.yaml"], "a symlink was followed"

        archive = base / "snap.zip"
        create_archive(config, archive)

        with zipfile.ZipFile(archive) as zf:
            assert b"should never be backed up" not in b"".join(zf.read(n) for n in zf.namelist())
