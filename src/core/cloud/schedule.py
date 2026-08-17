"""The Windows scheduled task that drives automatic backup."""

import datetime
from pathlib import Path

from core.cloud.constants import TASK_INTERVAL_MINUTES, TASK_NAME
from settings import SCRIPT_PATH

_TRIGGER_TIME = 1
"""TASK_TRIGGER_TIME. A one-off start, made recurring by its Repetition below."""

_ACTION_EXEC = 0
_CREATE_OR_UPDATE = 6
_LOGON_INTERACTIVE_TOKEN = 3
_IGNORE_NEW = 2
"""TASK_INSTANCES_IGNORE_NEW: a check firing mid-upload is dropped, not killed."""


def _scheduler():
    import win32com.client

    scheduler = win32com.client.Dispatch("Schedule.Service")
    scheduler.Connect()
    return scheduler


def _executable() -> Path:
    return Path(SCRIPT_PATH) / "yasb_cloud.exe"


def exists() -> bool:
    """Whether the task is registered. False also when the scheduler cannot be reached, so
    this is only safe for display. Anything acting on the answer must use `remove`.
    """
    try:
        _scheduler().GetFolder("\\").GetTask(TASK_NAME)
        return True
    except Exception:
        return False


def create() -> tuple[bool, str]:
    """Register the task, replacing any existing one. Returns success and any failure text."""
    executable = _executable()
    if not executable.exists():
        # Running from source. A task pointing at a missing exe fails silently every interval.
        return False, f"{executable.name} was not found next to the app"

    try:
        scheduler = _scheduler()
        task = scheduler.NewTask(0)

        task.RegistrationInfo.Description = "Backs up the YASB configuration when it changes."
        task.RegistrationInfo.Author = "YASB Cloud"
        task.Settings.Compatibility = 6

        trigger = task.Triggers.Create(_TRIGGER_TIME)
        trigger.Enabled = True
        trigger.StartBoundary = datetime.datetime.now().isoformat()
        trigger.Repetition.Interval = f"PT{TASK_INTERVAL_MINUTES}M"
        trigger.Repetition.Duration = ""  # empty means forever

        task.Principal.LogonType = _LOGON_INTERACTIVE_TOKEN
        task.Principal.RunLevel = 0

        settings = task.Settings
        settings.Enabled = True
        settings.StartWhenAvailable = True
        settings.MultipleInstances = _IGNORE_NEW
        settings.ExecutionTimeLimit = "PT1H"
        settings.Hidden = False
        settings.RunOnlyIfIdle = False
        settings.WakeToRun = False
        settings.DisallowStartIfOnBatteries = False
        settings.StopIfGoingOnBatteries = False

        action = task.Actions.Create(_ACTION_EXEC)
        action.Path = str(executable)
        action.Arguments = "--auto-backup"
        action.WorkingDirectory = SCRIPT_PATH

        scheduler.GetFolder("\\").RegisterTaskDefinition(
            TASK_NAME, task, _CREATE_OR_UPDATE, None, None, _LOGON_INTERACTIVE_TOKEN, None
        )
    except Exception as exc:
        return False, str(exc)
    return True, ""


def remove() -> tuple[bool, str]:
    """Delete the task. Reports success when there was none, failure when it cannot tell.

    The lookup is separate from the connection on purpose. Guarding this with `exists()`
    reported success whenever the scheduler was unreachable, so the toggle looked off while
    the task stayed registered.
    """
    try:
        folder = _scheduler().GetFolder("\\")
    except Exception as exc:
        return False, str(exc)

    try:
        folder.GetTask(TASK_NAME)
    except Exception:
        return True, ""  # nothing registered, which is what was wanted

    try:
        folder.DeleteTask(TASK_NAME, 0)
    except Exception as exc:
        return False, str(exc)
    return True, ""
