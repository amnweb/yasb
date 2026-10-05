"""Tests for the stop/restore/start sequence in core.cloud.restore.

A fake controller stands in for yasbc so nothing is spawned.

    python -m pytest tests/cloud/test_restore_runner.py -q
"""

import tempfile
import zipfile
from pathlib import Path

from core.cloud.errors import RestoreError
from core.cloud.restore import BarController, restore_with_restart


class NoYasbcController(BarController):
    """A machine with no yasbc installed: nothing on PATH and nothing bundled."""

    @staticmethod
    def _locate() -> str | None:
        return None


class FakeController(BarController):
    """Records the call order instead of touching a real process."""

    def __init__(self, *, running: bool = True, start_succeeds: bool = True) -> None:
        self.calls: list[str] = []
        self._running = running
        self._start_succeeds = start_succeeds

    @property
    def available(self) -> bool:
        return True

    def is_running(self) -> bool:
        self.calls.append("is_running")
        return self._running

    def stop(self) -> bool:
        self.calls.append("stop")
        self._running = False
        return True

    def start(self) -> bool:
        self.calls.append("start")
        self._running = self._start_succeeds
        return self._start_succeeds


def _archive(path: Path, files: dict[str, str]) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return path


def _tree(root: Path, files: dict[str, bytes]) -> Path:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return root


def test_bar_is_stopped_before_and_started_after():
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        archive = _archive(base / "snap.zip", {"config.yaml": "restored"})
        target = _tree(base / "config", {"config.yaml": b"old"})

        controller = FakeController(running=True)
        result = restore_with_restart(archive, target, controller=controller)

        assert controller.calls == ["is_running", "stop", "start"], f"wrong order: {controller.calls}"
        assert result.bar_was_running and result.bar_restarted
        assert (target / "config.yaml").read_bytes() == b"restored"


def test_bar_is_restarted_even_when_the_restore_fails():
    """A corrupt download must not leave the user with no bar."""
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        broken = base / "broken.zip"
        broken.write_bytes(b"not a zip at all")
        target = _tree(base / "config", {"config.yaml": b"precious"})

        controller = FakeController(running=True)
        try:
            restore_with_restart(broken, target, controller=controller)
            raise AssertionError("a corrupt archive was accepted")
        except RestoreError:
            pass

        assert controller.calls == ["is_running", "stop", "start"], "the bar was not restarted after a failure"
        assert (target / "config.yaml").read_bytes() == b"precious"


def test_a_stopped_bar_is_not_started_by_a_restore():
    """If the user had YASB closed, a restore should not launch it."""
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        archive = _archive(base / "snap.zip", {"config.yaml": "restored"})
        target = _tree(base / "config", {"config.yaml": b"old"})

        controller = FakeController(running=False)
        result = restore_with_restart(archive, target, controller=controller)

        assert controller.calls == ["is_running"], f"a stopped bar was touched: {controller.calls}"
        assert not result.bar_was_running and not result.bar_restarted
        assert (target / "config.yaml").read_bytes() == b"restored"


def test_a_failed_restart_is_reported_rather_than_hidden():
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        archive = _archive(base / "snap.zip", {"config.yaml": "restored"})
        target = _tree(base / "config", {"config.yaml": b"old"})

        controller = FakeController(running=True, start_succeeds=False)
        result = restore_with_restart(archive, target, controller=controller)

        assert result.bar_was_running
        assert not result.bar_restarted, "a failed restart was reported as success"
        assert (target / "config.yaml").read_bytes() == b"restored", "the restore itself still applied"


def test_safety_dir_is_passed_through_to_the_restore():
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        archive = _archive(base / "snap.zip", {"config.yaml": "restored"})
        target = _tree(base / "config", {"config.yaml": b"old", "obsolete.txt": b"remove me"})
        safety = base / "safety"

        result = restore_with_restart(
            archive,
            target,
            safety_dir=safety,
            controller=FakeController(running=True),
        )

        assert result.restore.safety_archive is not None, "safety_dir was not honoured"


def test_missing_yasbc_does_not_break_a_restore():
    """In a dev checkout or a portable install there may be no yasbc on PATH."""
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        archive = _archive(base / "snap.zip", {"config.yaml": "restored"})
        target = _tree(base / "config", {"config.yaml": b"old"})

        controller = NoYasbcController()

        # Nothing is spawned; stop/start report failure and the restore still happens.
        assert controller.stop() is False
        assert controller.start() is False

        result = restore_with_restart(archive, target, controller=controller)
        assert (target / "config.yaml").read_bytes() == b"restored"
        assert result.restore.restored == ("config.yaml",)
