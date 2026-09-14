"""The `--auto-backup` run: one automatic backup check, headless, then exit."""

import logging
import sys
from dataclasses import replace

from PyQt6.QtCore import QCoreApplication

from core.cloud import schedule
from core.cloud.api import ApiClient
from core.cloud.autobackup import decide, differences, entries, mark_backed_up
from core.cloud.constants import BASE_URL
from core.cloud.models import Account
from core.cloud.operations import BackupOperation
from core.cloud.session import Session
from core.cloud.settings import Settings
from core.cloud.settings import load as load_settings
from core.cloud.settings import save as save_settings
from core.cloud.state import read_state
from core.cloud.workers import device_name

logger = logging.getLogger(__name__)


def _account(client: ApiClient, app: QCoreApplication) -> Account | None:
    """Fetch the account, or None. Needed for the plan limits before archiving."""
    result: dict = {}
    call = client.me()
    call.succeeded.connect(lambda payload: (result.update(payload=payload), app.quit()))
    call.failed.connect(lambda error: (result.update(error=error), app.quit()))
    # A cancelled reply emits only `finished`, and without this the loop never returns.
    call.finished.connect(app.quit)
    app.exec()

    if "payload" not in result:
        logger.warning("check: could not read the account: %s", result.get("error", "no reply"))
        return None
    return Account.from_json(result["payload"])


def _notify() -> None:
    """Tell the user automatic backup has stopped, and where to fix it."""
    try:
        import os

        from core.utils.utilities import ToastNotifier
        from settings import SCRIPT_PATH

        ToastNotifier().show(
            os.path.join(SCRIPT_PATH, "assets", "images", "app_transparent.png"),
            "Automatic backup turned off",
            "Your subscription is not active, so YASB Cloud has stopped backing up automatically.",
            launch_url=f"{BASE_URL}/account",
            launch_label="Manage subscription",
        )
    except Exception as exc:
        logger.warning("could not show the notification: %s", exc)


def _disable(settings: Settings) -> None:
    """Turn automatic backup off after the server refused.

    Only ever called with a real answer from the server, never a timeout or a 503. The setting
    is written before the task is removed: the other way round, a failure in between leaves no
    task behind a toggle still reading on.
    """
    if not save_settings(replace(settings, auto_backup=False)):
        logger.error("check: refused by the server, but the setting could not be written")
        return

    removed, error = schedule.remove()
    if not removed:
        logger.warning("scheduled task could not be removed: %s", error)

    logger.debug("check: subscription is not active - automatic backup turned off")
    _notify()


def run_auto_backup() -> int:
    """One check. Returns a process exit code, which nobody reads but the log does."""
    settings = load_settings()
    if not settings.auto_backup:
        # The task fired, so a toggle reading off means a task that should not be registered.
        removed, error = schedule.remove()
        logger.debug("check: off%s", "" if removed else f" - task still registered: {error}")
        return 0

    try:
        before = read_state()
        now = entries(settings.exclude)
        should_backup, expected = decide(now)
    except Exception as exc:
        logger.exception("check failed: %s", exc)
        return 1

    if not should_backup:
        changes = differences(before.files, now)
        if changes:
            logger.debug("check: changed, waiting for it to settle - %s", "; ".join(changes))
        else:
            logger.debug("check: no change (%s files)", len(now))
        return 0

    session = Session()
    if not session.load():
        # Signed out since the task was created. Left registered: signing back in resumes it.
        logger.debug("check: settled, but signed out - skipping")
        return 0

    app = QCoreApplication(sys.argv)
    client = ApiClient(session)

    account = _account(client, app)
    if account is None:
        # No answer, not a refusal. Offline or in maintenance must not disable the feature.
        return 1
    if not account.access.can_write:
        _disable(settings)
        return 0

    logger.debug("check: settled and not uploaded, backing up (%s files)", len(now))

    outcome: list = []
    problem: list[str] = []

    operation = BackupOperation(
        client,
        session,
        note=f"{device_name()} (auto)",
        max_total_bytes=account.limits.max_snapshot_bytes,
    )
    operation.failed.connect(problem.append)
    operation.finished.connect(lambda result: (outcome.append(result), app.quit()))
    operation.start()
    if not outcome:  # start() settles on the spot when the lock is held
        app.exec()

    if problem or not outcome or outcome[0] is None:
        # Left unrecorded so the next quiet run tries again.
        logger.warning("backup failed: %s", problem[0] if problem else "no result")
        return 1

    mark_backed_up(expected)
    logger.debug("backed up")
    return 0
