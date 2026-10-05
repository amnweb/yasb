"""Tests for core.cloud.settings.

    python -m pytest tests/cloud/test_settings.py -q

The concern here is `save()` under two writers. The window writes settings from a Qt slot and
the scheduled task writes them when a lapsed subscription is refused, so the two really can
overlap on one machine. `save()` reports failure with a bool, and both callers depend on that:
an exception escaping a Qt slot aborts the process, and one escaping `run_auto_backup` kills
the task before it can remove itself.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"


from core.cloud import settings
from core.cloud.settings import Settings

_WRITER = f"""
import os, sys
sys.path.insert(0, r"{SRC}")
os.environ["LOCALAPPDATA"] = sys.argv[1]
from core.cloud.settings import Settings, save
rules = tuple("rule-%d/*.conf" % i for i in range(100))
for _ in range(60):
    save(Settings(exclude=rules, auto_backup=sys.argv[2] == "on"))
"""


def test_an_unusable_staging_file_is_reported_not_raised():
    """The staging file being unwritable must come back as False, never as an exception.

    Blocked with a non-empty directory, which fails the write and then fails the cleanup that
    the write's own error handler attempts. That second failure is the one that used to escape.
    """
    with tempfile.TemporaryDirectory() as raw:
        target = Path(raw) / "settings.json"
        settings.settings_path = lambda: target

        staging = settings.staging_path(target)
        staging.mkdir()
        (staging / "blocker").write_bytes(b"x")

        try:
            result = settings.save(Settings(exclude=("secrets/*",)))
        except Exception as exc:
            raise AssertionError(f"save() raised {type(exc).__name__} instead of returning False") from exc

        assert result is False, "a staging file that could not be written was reported as success"


def test_two_processes_writing_at_once_leave_a_readable_file():
    """Neither writer may crash, and the file they leave must still parse with every rule."""
    with tempfile.TemporaryDirectory() as raw:
        running = [
            subprocess.Popen([sys.executable, "-c", _WRITER, raw, mode], stderr=subprocess.PIPE, text=True)
            for mode in ("on", "off")
        ]
        errors = [process.communicate()[1] for process in running]

        for process, error in zip(running, errors):
            assert process.returncode == 0, f"a writer died with exit code {process.returncode}: {error.strip()}"

        target = Path(raw) / "YASB" / "cloud" / "settings.json"
        try:
            stored = json.loads(target.read_bytes())
        except ValueError as exc:
            raise AssertionError(f"concurrent writes left settings.json unparseable: {exc}") from exc

        assert len(stored.get("exclude", [])) == 100, "concurrent writes lost exclude rules"
        assert list(target.parent.glob("*.partial")) == [], "a staging file was left behind"
