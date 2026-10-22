"""Tests for core.cloud.autobackup.

    python -m pytest tests/cloud/test_autobackup.py -q

The settle rule is the point of this file. A folder being edited must not produce a backup on
every check, and a folder that has gone quiet must produce exactly one. Nothing here needs a
network, an account or a lock, because `decide()` is separated from the upload for that reason.
"""

import os
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.cloud import autobackup, state
from core.cloud import run_auto_backup as runner
from core.cloud.settings import Settings


def _point_at(monkeypatch: pytest.MonkeyPatch, tmp: Path) -> None:
    """Run the checker against a scratch config folder and scratch state."""
    monkeypatch.setattr(autobackup, "DEFAULT_CONFIG_DIRECTORY", str(tmp / "config"))
    monkeypatch.setattr(state, "state_path", lambda: tmp / "autobackup.json")


def _write(root: Path, name: str, content: bytes) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    # Windows mtime resolution is coarse enough that two writes in the same tick can share a
    # timestamp, which would make a real change look like none.
    os.utime(path, (time.time(), time.time() + 1))


def test_a_folder_being_edited_never_says_back_up(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        config = tmp / "config"
        _write(config, "config.yaml", b"one")
        _point_at(monkeypatch, tmp)

        decisions: list[bool] = []
        for step in range(4):
            decisions.append(autobackup.decide(autobackup.entries())[0])
            _write(config, "styles.css", f"edit {step}".encode())

        assert decisions == [False, False, False, False], "a backup was called for mid-edit"


def test_one_backup_once_the_folder_goes_quiet(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        config = tmp / "config"
        _write(config, "config.yaml", b"one")
        _point_at(monkeypatch, tmp)

        assert autobackup.decide(autobackup.entries())[0] is False, "first sight has nothing to compare against"
        _write(config, "styles.css", b"edited")
        assert autobackup.decide(autobackup.entries())[0] is False, "changed, so not settled"

        should, expected = autobackup.decide(autobackup.entries())
        assert should is True, "no backup after the folder settled"

        autobackup.mark_backed_up(expected)
        for _ in range(3):
            assert autobackup.decide(autobackup.entries())[0] is False, "a quiet folder was backed up more than once"


def test_a_failed_backup_is_retried(monkeypatch: pytest.MonkeyPatch):
    """`mark_backed_up` is the record of success, so not calling it must mean try again."""
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        _write(tmp / "config", "config.yaml", b"one")
        _point_at(monkeypatch, tmp)

        autobackup.decide(autobackup.entries())
        assert autobackup.decide(autobackup.entries())[0] is True
        # upload failed, so nothing is recorded
        assert autobackup.decide(autobackup.entries())[0] is True, "a failed backup was not retried"


class _FakeSchedule:
    """Stands in for the Task Scheduler. Records rather than calling COM."""

    def __init__(self, ok: bool = True) -> None:
        self.ok = ok
        self.removals = 0

    def remove(self) -> tuple[bool, str]:
        self.removals += 1
        return (self.ok, "" if self.ok else "scheduler unreachable")


class _FakeSession:
    master_key = b"k"

    def load(self) -> bool:
        return True


class _FakeApp:
    def __init__(self, argv: list[str]) -> None:
        pass

    def exec(self) -> int:
        return 0

    def quit(self) -> None:
        pass


def test_nothing_happens_while_the_toggle_is_off(monkeypatch: pytest.MonkeyPatch):
    """The toggle gates the run, not `decide`, which only judges the folder.

    So this has to exercise the entry point: with the setting off it must return without
    walking anything or touching the state file.
    """
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        _write(tmp / "config", "config.yaml", b"one")
        _point_at(monkeypatch, tmp)

        walked: list[int] = []

        def walk(exclude: tuple[str, ...] = ()) -> dict[str, str]:
            walked.append(1)
            return {}

        monkeypatch.setattr(runner, "load_settings", lambda: Settings(auto_backup=False))
        monkeypatch.setattr(runner, "entries", walk)
        monkeypatch.setattr(runner, "schedule", _FakeSchedule())

        assert runner.run_auto_backup() == 0
        assert walked == [], "the folder was walked despite the toggle being off"
        assert not (tmp / "autobackup.json").exists(), "state was written despite the toggle being off"


def test_an_off_toggle_removes_the_task_that_woke_it(monkeypatch: pytest.MonkeyPatch):
    """Self-healing, and the reason the removal is not only done at the moment of disabling.

    This process runs because Task Scheduler started it, so reading `auto_backup: false` means
    a task exists that should not - a first removal that failed, or a settings file edited by
    hand. Without this, Windows wakes a process every minute forever to read one line and exit.
    """
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        _write(tmp / "config", "config.yaml", b"one")
        _point_at(monkeypatch, tmp)

        monkeypatch.setattr(runner, "load_settings", lambda: Settings(auto_backup=False))
        fake = _FakeSchedule()
        monkeypatch.setattr(runner, "schedule", fake)

        assert runner.run_auto_backup() == 0
        assert fake.removals == 1, "the task that started this run was left registered"


def test_an_edit_made_while_nothing_was_running_is_caught(monkeypatch: pytest.MonkeyPatch):
    """Both signatures are persisted, so a gap between checks loses nothing."""
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        config = tmp / "config"
        _write(config, "config.yaml", b"one")
        _point_at(monkeypatch, tmp)

        autobackup.decide(autobackup.entries())
        should, expected = autobackup.decide(autobackup.entries())
        assert should is True
        autobackup.mark_backed_up(expected)

        _write(config, "config.yaml", b"edited while nothing ran")

        assert autobackup.decide(autobackup.entries())[0] is False, "backed up before confirming the folder was quiet"
        assert autobackup.decide(autobackup.entries())[0] is True, "an edit made between checks was never backed up"


def test_excluded_files_do_not_trigger_a_backup(monkeypatch: pytest.MonkeyPatch):
    """The rotating yasb.log changes constantly and is not in the archive, so it must not
    keep the folder looking busy or trigger uploads of identical content."""
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        config = tmp / "config"
        _write(config, "config.yaml", b"one")
        _point_at(monkeypatch, tmp)

        autobackup.decide(autobackup.entries())
        should, expected = autobackup.decide(autobackup.entries())
        assert should is True
        autobackup.mark_backed_up(expected)

        for step in range(3):
            _write(config, "yasb.log", f"line {step}".encode())
            assert autobackup.decide(autobackup.entries())[0] is False, "a log write triggered a backup"


def test_mark_in_sync_stops_the_next_check_re_uploading(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        _write(tmp / "config", "config.yaml", b"restored content")
        _point_at(monkeypatch, tmp)

        autobackup.mark_in_sync()

        assert autobackup.decide(autobackup.entries())[0] is False
        assert autobackup.decide(autobackup.entries())[0] is False, "the state restored a moment ago was uploaded back"


def test_user_rules_are_honoured_by_the_signature(monkeypatch: pytest.MonkeyPatch):
    """A file the rules exclude is not in the archive, so changing it is not a change."""
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        config = tmp / "config"
        _write(config, "config.yaml", b"one")
        _point_at(monkeypatch, tmp)

        rules = ("*.env",)
        autobackup.decide(autobackup.entries(rules))
        should, expected = autobackup.decide(autobackup.entries(rules))
        assert should is True
        autobackup.mark_backed_up(expected)

        _write(config, "secret.env", b"KEY=1")
        for _ in range(2):
            assert autobackup.decide(autobackup.entries(rules))[0] is False, "an excluded file triggered a backup"


def test_the_file_map_survives_a_backup(monkeypatch: pytest.MonkeyPatch):
    """After a backup, the stored map must still describe the folder.

    Blanking it made every later check compare against nothing and log the whole folder as
    newly added, run after run, while the backup logic itself was behaving correctly.
    """
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        config = tmp / "config"
        _write(config, "config.yaml", b"one")
        _point_at(monkeypatch, tmp)

        autobackup.decide(autobackup.entries())
        should, expected = autobackup.decide(autobackup.entries())
        assert should is True
        autobackup.mark_backed_up(expected)

        stored = state.read_state()
        assert stored.files, "the file map was wiped by the backup"
        assert stored.files == autobackup.entries(), "the map no longer matches the folder"

        # and the next check must report nothing, not a folder full of additions
        assert autobackup.differences(state.read_state().files, autobackup.entries()) == []


def test_a_state_file_without_a_map_heals_itself(monkeypatch: pytest.MonkeyPatch):
    """Upgrading from a version that stored only signatures must not log the whole folder."""
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        config = tmp / "config"
        _write(config, "config.yaml", b"one")
        _point_at(monkeypatch, tmp)

        current = autobackup.signature(autobackup.entries())
        state.write_state(last_seen=current, last_backed_up=current, files={})

        autobackup.decide(autobackup.entries())
        assert state.read_state().files == autobackup.entries(), "the stale map was not refreshed"


def test_a_new_file_is_a_change(monkeypatch: pytest.MonkeyPatch):
    """An editor dropping a dotfile in the config folder is what a real surprise looks like."""
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        config = tmp / "config"
        _write(config, "config.yaml", b"one")
        _point_at(monkeypatch, tmp)

        autobackup.decide(autobackup.entries())
        _, expected = autobackup.decide(autobackup.entries())
        autobackup.mark_backed_up(expected)

        before = state.read_state().files
        _write(config, ".vscode/settings.json", b"{}")
        assert autobackup.differences(before, autobackup.entries()) == ["added .vscode/settings.json"]
        assert autobackup.decide(autobackup.entries())[0] is False, "backed up before it settled"
        assert autobackup.decide(autobackup.entries())[0] is True, "never backed up after it settled"


# --- turning itself off ----------------------------------------------------------------
#
# The actions are easy; the condition is the dangerous part. Disabling on anything other than
# a real answer from the server would mean one outage switching automatic backup off for every
# user at once, so "no answer" and "answered no" are tested apart.


def _disable_harness(
    monkeypatch: pytest.MonkeyPatch, can_write: bool | None
) -> tuple[list[Settings], list[int], _FakeSchedule]:
    """Drive run_auto_backup to the point of asking the server, then answer for it.

    `can_write=None` stands for no answer at all - offline, dropped, or a 503 in maintenance.
    """
    saved: list[Settings] = []
    notified: list[int] = []
    fake = _FakeSchedule()

    def save(settings: Settings) -> bool:
        saved.append(settings)
        return True

    def walk(exclude: tuple[str, ...] = ()) -> dict[str, str]:
        return {"config.yaml": "1:1"}

    def decide(now: dict[str, str]) -> tuple[bool, str]:
        return True, "sig"

    def client(session: object) -> None:
        return None

    def account(client: object, app: object) -> SimpleNamespace | None:
        if can_write is None:
            return None
        return SimpleNamespace(access=SimpleNamespace(can_write=can_write))

    monkeypatch.setattr(runner, "load_settings", lambda: Settings(auto_backup=True))
    monkeypatch.setattr(runner, "save_settings", save)
    monkeypatch.setattr(runner, "schedule", fake)
    monkeypatch.setattr(runner, "_notify", lambda: notified.append(1))
    # Past the folder walk and the sign-in check, which have their own tests above.
    monkeypatch.setattr(runner, "entries", walk)
    monkeypatch.setattr(runner, "decide", decide)
    monkeypatch.setattr(runner, "read_state", lambda: state.State(last_seen="sig", last_backed_up="", files={}))
    monkeypatch.setattr(runner, "Session", _FakeSession)
    monkeypatch.setattr(runner, "QCoreApplication", _FakeApp)
    monkeypatch.setattr(runner, "ApiClient", client)
    monkeypatch.setattr(runner, "_account", account)

    return saved, notified, fake


def test_a_refusal_turns_automatic_backup_off(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as raw:
        _point_at(monkeypatch, Path(raw))
        saved, notified, fake = _disable_harness(monkeypatch, can_write=False)

        assert runner.run_auto_backup() == 0
        assert [s.auto_backup for s in saved] == [False], "the setting was not turned off"
        assert fake.removals == 1, "the scheduled task was left behind"
        assert notified == [1], "the user was not told"


def test_no_answer_from_the_server_changes_nothing(monkeypatch: pytest.MonkeyPatch):
    """Offline, a dropped connection and maintenance all arrive as no account at all.

    None of them mean the subscription ended, and acting on them would take the feature away
    from every user for the length of an outage - then leave it off after the outage passed.
    """
    with tempfile.TemporaryDirectory() as raw:
        _point_at(monkeypatch, Path(raw))
        saved, notified, fake = _disable_harness(monkeypatch, can_write=None)

        assert runner.run_auto_backup() == 1
        assert saved == [], "an unanswered check turned the feature off"
        assert fake.removals == 0, "an unanswered check removed the scheduled task"
        assert notified == [], "an unanswered check notified the user"


def test_nothing_is_touched_when_the_setting_cannot_be_written(monkeypatch: pytest.MonkeyPatch):
    """The setting is written first, so a failure there must stop the rest.

    Removing the task after a failed write would leave the toggle reading "on" with nothing
    behind it - the window would show the feature enabled and it would never run again.
    """
    with tempfile.TemporaryDirectory() as raw:
        _point_at(monkeypatch, Path(raw))
        _, notified, fake = _disable_harness(monkeypatch, can_write=False)

        def save(settings: Settings) -> bool:
            return False

        monkeypatch.setattr(runner, "save_settings", save)

        assert runner.run_auto_backup() == 0
        assert fake.removals == 0, "the task was removed even though the setting was not saved"
        assert notified == [], "the user was told about a change that did not happen"
