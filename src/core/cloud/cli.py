"""YASB Cloud commands for yasbc.

Reached through `yasbc cloud <command>`. The API client is asynchronous and signal-based, so
every call here runs on a short-lived event loop and returns when it finishes.
"""

import argparse
import re
import signal
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QCoreApplication, QTimer

from core.cloud import logs
from core.cloud.api import ApiClient, ApiError, approve_uri
from core.cloud.constants import (
    BAD_SIGN_IN,
    CALL_TIMEOUT_MS,
    CLI_LOG_FILE,
    DEVICE_CODE_TTL_S,
    DEVICE_POLL_INTERVAL_S,
    EXPIRED_CODE_CLI,
    NOTE_MAX_LENGTH,
    TRANSFER_TIMEOUT_MS,
    UNLIMITED,
)
from core.cloud.models import Account, Snapshot, format_size
from core.cloud.operations import BackupOperation, Operation, RestoreOperation, SaveCopyOperation
from core.cloud.session import Session
from core.cloud.workers import (
    device_name,
)
from core.utils.shell_utils import shell_open

SIGN_IN_HINT = "Not signed in. Run `yasbc cloud auth` first."


class _Failed(Exception):
    """Anything that should print a message and exit non-zero."""


_APP: QCoreApplication | None = None
_INTERRUPTED = False
_TICKER: QTimer | None = None
_OPERATION: Any = None
"""The operation running on this thread, so the interrupt handler can cancel it."""


def _app() -> QCoreApplication:
    """The process-wide event loop owner.

    A module global on purpose: a QCoreApplication with no Python reference is collected the
    moment it is created.
    """
    global _APP
    if _APP is None:
        _APP = QCoreApplication.instance() or QCoreApplication(sys.argv[:1])
    return _APP


def _watch_for_interrupt() -> None:
    """Make Ctrl-C reach Python while a Qt loop is running.

    exec() sits in C++ and only delivers a signal when it returns to the interpreter.
    """
    global _TICKER
    if _TICKER is not None:
        return

    app = _app()

    def interrupted(*_args) -> None:
        global _INTERRUPTED
        _INTERRUPTED = True
        # Cancel here, not on the flag: a running zip or decrypt never checks it.
        if _OPERATION is not None:
            _OPERATION.cancel()
        app.quit()

    signal.signal(signal.SIGINT, interrupted)
    # Ctrl-Break kills the process outright on Windows without this.
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, interrupted)
    _TICKER = QTimer()
    _TICKER.timeout.connect(lambda: None)
    _TICKER.start(200)


def _sleep(seconds: float) -> None:
    """Wait, but give up the moment Ctrl-C arrives.

    The handler sets a flag rather than raising, so a plain sleep runs to the end and sends
    one more request nobody is waiting for.
    """
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if _INTERRUPTED:
            raise KeyboardInterrupt
        time.sleep(0.05)
    if _INTERRUPTED:
        raise KeyboardInterrupt


def _run_operation(operation: Operation):
    """Run one Operation to completion and return its result. Ctrl-C cancels it."""
    global _OPERATION
    app = _app()
    outcome: list = []
    problem: list[str] = []

    operation.status.connect(lambda text: print(text, flush=True))
    operation.failed.connect(problem.append)
    operation.finished.connect(lambda result: (outcome.append(result), app.quit()))

    _OPERATION = operation
    try:
        operation.start()
        if not outcome:  # start() settles on the spot when it is refused
            ceiling = _ceiling(app, TRANSFER_TIMEOUT_MS)
            app.exec()
            ceiling.stop()
    finally:
        _OPERATION = None
        operation.cancel()

    if _INTERRUPTED:
        raise KeyboardInterrupt
    if problem:
        raise _Failed(problem[0])
    if not outcome:
        raise _Failed("YASB Cloud did not respond. Check your connection and try again.")
    return outcome[0]


def _ceiling(app: QCoreApplication, timeout_ms: int) -> QTimer:
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(app.quit)
    timer.start(timeout_ms)
    return timer


def _run_call(call, timeout_ms: int = CALL_TIMEOUT_MS) -> tuple[dict | None, ApiError | None]:
    """Run one API call to completion on a short-lived event loop.

    Both halves come back so the sign-in poll can tell "still waiting" from "denied".
    """
    app = _app()
    outcome: dict = {}

    def succeeded(payload) -> None:
        outcome["payload"] = payload if isinstance(payload, dict) else {}
        app.quit()

    def failed(error) -> None:
        outcome["error"] = error
        app.quit()

    call.succeeded.connect(succeeded)
    call.failed.connect(failed)
    # Stopped afterwards, or a leftover armed timer quits the next exec().
    ceiling = _ceiling(app, timeout_ms)
    app.exec()
    ceiling.stop()

    if _INTERRUPTED:
        call.abort()
        raise KeyboardInterrupt

    return outcome.get("payload"), outcome.get("error")


def _wait(call, timeout_ms: int = CALL_TIMEOUT_MS) -> dict:
    payload, error = _run_call(call, timeout_ms)
    if error is not None:
        raise _Failed(str(error))
    if payload is None:
        raise _Failed("YASB Cloud did not respond. Check your connection and try again.")
    return payload


def _confirm(question: str) -> bool:
    """Default no. This replaces the configuration directory."""
    return input(f"{question} [y/N] ").strip().lower() in ("y", "yes")


def _session() -> Session:
    session = Session()
    if not session.load():
        raise _Failed(SIGN_IN_HINT)
    return session


BACKUP_ID = re.compile(r"^[0-9a-f]{12,32}$")
"""What `_find` will send. Twelve characters is what `list` prints and the floor the server
enforces; anything up to the full thirty-two is passed through untouched."""

SHORT_ID = 12
"""Characters of the id shown by `list`. The full one made a row 98 columns wide, which wraps
on an 80-column console and leaves the table unreadable. At 16**12 two snapshots on one
account will not collide, and the server refuses rather than guessing if they somehow do."""

PAGE_SIZE = 50
"""Rows in one `list` page. The server clamps any larger request down to its own maximum, so
asking for more here would silently return fewer than the offsets below assume."""


def _page(client: ApiClient, offset: int = 0, search: str = "") -> tuple[list[Snapshot], int]:
    """One page and the total, straight from the server."""
    payload = _wait(client.list_backups(offset, search))
    rows = [Snapshot.from_json(entry) for entry in payload.get("backups", [])]
    return rows, int(payload.get("total", 0) or 0)


def _find(client: ApiClient, wanted: str) -> Snapshot:
    """Resolve `latest` or a full id. One request either way.

    A short id is resolved by the server, not here: proving a prefix is unique would mean
    paging the whole list to answer one lookup.
    """
    if wanted == "latest":
        # Offset 0 and newest first, so the first row is the latest.
        rows, _ = _page(client)
        if not rows:
            raise _Failed("You have no backups yet.")
        return rows[0]

    if not BACKUP_ID.match(wanted):
        raise _Failed(f"{wanted!r} is not a backup id. Run `yasbc cloud list` and copy one, or use `latest`.")

    return Snapshot.from_json(_wait(client.get_backup(wanted)))


def _pages(total: int) -> int:
    """How many pages `total` rows fill. At least one, so an empty account is page 1 of 1."""
    return max(1, -(-total // PAGE_SIZE))


def _when(created_at: str) -> str:
    return created_at[:16].replace("T", " ")


def _columns(text: str) -> int:
    """How wide `text` prints, not how many characters it has. A CJK ideograph or emoji
    occupies two terminal cells while counting as one character."""
    return sum(2 if unicodedata.east_asian_width(char) in "WF" else 1 for char in text)


def _clip(text: str, columns: int) -> str:
    """The longest prefix of `text` that fits in `columns`."""
    used = 0
    for index, char in enumerate(text):
        used += 2 if unicodedata.east_asian_width(char) in "WF" else 1
        if used > columns:
            return text[:index]
    return text


NOTE_TEXT = 24
"""Cells a note may use before the three dots. A fixed number rather than one measured from
the window: notes run to a hundred characters, and letting a wide terminal print all of them
gives a row long enough to lose the columns that matter at the start of it."""


def _note_cell(snapshot: Snapshot) -> str:
    """The label, clipped but not padded. It is last on the row, so nothing follows it to
    line up. Clipped by display width, since one CJK ideograph fills two cells."""
    text = snapshot.note
    return _clip(text, NOTE_TEXT) + "..." if _columns(text) > NOTE_TEXT else text


def cmd_auth() -> int:
    session = Session()
    if session.load():
        print(f"Already signed in as {session.tokens.email}. Use `yasbc cloud logout` to switch.")
        return 0

    client = ApiClient(session)
    code = _wait(client.request_device_code(device_name()))

    # The checked address, not the raw field: this decides what gets opened.
    approve = approve_uri(code)
    if not approve:
        raise _Failed(BAD_SIGN_IN)

    print(f"\n  Your code: {code.get('user_code', '')}")
    print(f"  Approve it at: {approve}\n")
    shell_open(approve)
    print("Waiting for you to approve in the browser. Ctrl-C to cancel.")

    deadline = time.monotonic() + DEVICE_CODE_TTL_S
    while True:
        if time.monotonic() >= deadline:
            raise _Failed(EXPIRED_CODE_CLI)

        payload, error = _run_call(client.poll_device_token(code.get("device_code", "")))
        if payload is not None:
            if not session.apply_login(payload):
                raise _Failed(BAD_SIGN_IN)
            print(f"Signed in as {session.tokens.email}.")
            return 0

        if error is not None and error.code == "expired_token":
            raise _Failed(EXPIRED_CODE_CLI)
        if error is not None and error.code not in ("authorization_pending", "slow_down"):
            if error.code == "access_denied":
                raise _Failed("The request was denied in the browser.")
            raise _Failed(str(error))

        _sleep(DEVICE_POLL_INTERVAL_S)


def cmd_logout() -> int:
    """Revoke the session on the server, then forget it here.

    Both halves, like the window's Sign out. Clearing only the local files left the session
    live on the server for its full 180 days. The request is best effort: an unreachable
    server must not leave the credentials sitting on disk.
    """
    session = Session()
    failed_to_revoke = False
    if session.load():
        _, error = _run_call(ApiClient(session).logout())
        failed_to_revoke = error is not None

    session.sign_out()
    print("Signed out.")
    if failed_to_revoke:
        print("Could not reach YASB Cloud, so this device may still be listed. Remove it on the website.")
    return 0


def cmd_status() -> int:
    session = _session()
    account = Account.from_json(_wait(ApiClient(session).me()))

    print(f"Signed in as  {account.email}")
    subscription = account.subscription
    plan = "none" if subscription is None else f"{subscription.plan_id} ({subscription.status})"
    print(f"Plan          {plan}")

    allowance = (
        "unlimited" if account.limits.max_storage_bytes == UNLIMITED else format_size(account.limits.max_storage_bytes)
    )
    print(f"Storage       {format_size(account.usage.bytes)} of {allowance}")
    print(f"Backups       {account.usage.snapshots}")
    return 0


def cmd_list(search: str = "", page: int = 1) -> int:
    """One page of backups, newest first. Pro has no snapshot limit, so printing the lot
    scrolled the useful rows off the top of the console."""
    session = _session()
    page = max(1, page)
    offset = (page - 1) * PAGE_SIZE
    rows, total = _page(ApiClient(session), offset, search)

    if not rows:
        if search:
            print(f"No backup matches {search!r}.")
        elif total:
            # Asked for a page past the end. Saying so beats printing nothing, which reads
            # like the account is empty.
            print(
                f"Page {page} does not exist. There {'is' if total == 1 else 'are'} {total}, "
                f"ending at page {_pages(total)}."
            )
        else:
            print("You have no backups yet. Run `yasbc cloud backup`.")
        return 0

    # Id first so it is in the same column on every row, note last because its width varies.
    print(f"{'ID':<{SHORT_ID}}  {'WHEN':<16}  {'SIZE':>8}  {'PUBLIC':<6}  NOTE")
    for snapshot in rows:
        print(
            f"{snapshot.id[:SHORT_ID]:<{SHORT_ID}}  {_when(snapshot.created_at):<16}  "
            f"{format_size(snapshot.size_bytes):>8}  {'*' if snapshot.share_url else '':<6}  "
            f"{_note_cell(snapshot)}"
        )

    # Only when there is more than one. On a short list it says nothing the rows do not.
    if _pages(total) > 1:
        print(f"\nPage {page} of {_pages(total)}  -  {offset + 1}-{offset + len(rows)} of {total}")
    return 0


def cmd_share(wanted: str) -> int:
    session = _session()
    client = ApiClient(session)
    snapshot = _find(client, wanted)

    if snapshot.share_url:
        print(snapshot.share_url)
        return 0

    print("Anyone with this link can download this backup, including any")
    print("API keys or tokens your configuration contains.")
    # .get, like every other reply is read: a missing key here would be a KeyError, which the
    # handler in run() does not catch, so the user would get a traceback rather than a line.
    url = _wait(client.share_backup(snapshot.id)).get("url", "")
    if not url:
        raise _Failed("The backup was shared, but the server did not return its link.")
    print(url)
    return 0


def cmd_delete(wanted: str, assume_yes: bool) -> int:
    session = _session()
    client = ApiClient(session)
    snapshot = _find(client, wanted)

    print(f"Delete {_when(snapshot.created_at)} {snapshot.note!r}?")
    print("This removes it from YASB Cloud for good. Your configuration is not touched.")
    if snapshot.share_url:
        print("Its public link stops working too.")
    if not assume_yes and not _confirm("Continue?"):
        print("Nothing was deleted.")
        return 1

    _wait(client.delete_backup(snapshot.id))
    print("Deleted.")
    return 0


def cmd_unshare(wanted: str) -> int:
    session = _session()
    client = ApiClient(session)
    snapshot = _find(client, wanted)

    if not snapshot.share_url:
        print("That backup is not shared.")
        return 0

    _wait(client.unshare_backup(snapshot.id))
    print("Stopped sharing. That link no longer works.")
    return 0


def cmd_backup(note: str) -> int:
    session = _session()
    client = ApiClient(session)
    account = Account.from_json(_wait(client.me()))
    if not account.access.can_write:
        raise _Failed("An active subscription is required to create backups.")

    _run_operation(
        BackupOperation(
            client,
            session,
            note=note.strip()[:NOTE_MAX_LENGTH],
            max_total_bytes=account.limits.max_snapshot_bytes,
        )
    )

    print("Backed up.")
    return 0


def cmd_restore(wanted: str, assume_yes: bool) -> int:
    session = _session()
    client = ApiClient(session)
    snapshot = _find(client, wanted)

    print(f"Restore {_when(snapshot.created_at)} {snapshot.note!r}?")
    print("YASB will stop and your configuration folder will be replaced by this backup.")
    print("Anything added since is removed. A copy of the current one is saved first.")
    if not assume_yes and not _confirm("Continue?"):
        print("Nothing was changed.")
        return 1

    # After the prompt, so waiting on stdin does not hold the lock.
    result = _run_operation(RestoreOperation(client, session, snapshot.id))

    print(f"Restored {len(result.restore.restored)} files.")
    if result.bar_was_running and not result.bar_restarted:
        print("YASB did not restart. Start it with `yasbc start`.")
    return 0


def cmd_save(wanted: str, folder: str) -> int:
    session = _session()
    client = ApiClient(session)
    snapshot = _find(client, wanted)

    stamp = snapshot.created_at[:19].replace(":", "-").replace("T", "-")
    target = Path(folder).expanduser().resolve() / f"yasb-backup-{stamp}"

    print(f"Saved to {_run_operation(SaveCopyOperation(client, session, snapshot.id, target))}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="yasbc cloud", description="Back up and restore your YASB configuration.")
    # `metavar` and `title`, or argparse prints the whole brace-delimited command list twice
    # and sizes every description column to its width.
    commands = parser.add_subparsers(dest="action", metavar="<command>", title="commands")

    commands.add_parser("auth", help="Sign in through your browser")
    commands.add_parser("logout", help="Sign out on this machine")
    commands.add_parser("status", help="Show the signed-in account, plan and usage")
    listing = commands.add_parser("list", help="List your backups")
    listing.add_argument("-s", "--search", default="", help="Only backups whose note or PC name contains this")
    listing.add_argument("-p", "--page", type=int, default=1, help=f"Which page to show, {PAGE_SIZE} per page")

    backup = commands.add_parser("backup", help="Back up the configuration directory now")
    backup.add_argument("-n", "--note", default="", help="Label for this backup")

    restore = commands.add_parser("restore", help="Replace the configuration with a backup")
    restore.add_argument("backup", help="Backup id from `yasbc cloud list`, or `latest`")
    restore.add_argument("-y", "--yes", action="store_true", help="Skip the confirmation")

    save = commands.add_parser("save", help="Save a backup to a folder without restoring it")
    save.add_argument("backup", help="Backup id from `yasbc cloud list`, or `latest`")
    save.add_argument("folder", help="Where to write it")

    delete = commands.add_parser("delete", help="Delete a backup from YASB Cloud")
    delete.add_argument("backup", help="Backup id from `yasbc cloud list`, or `latest`")
    delete.add_argument("-y", "--yes", action="store_true", help="Skip the confirmation")

    share = commands.add_parser("share", help="Publish a backup and print its link")
    share.add_argument("backup", help="Backup id from `yasbc cloud list`, or `latest`")

    unshare = commands.add_parser("unshare", help="Stop sharing a backup")
    unshare.add_argument("backup", help="Backup id from `yasbc cloud list`, or `latest`")
    return parser


def run(argv: list[str]) -> int:
    # A Windows console is cp1252, so an emoji in a note would abort the command mid-table.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")

    parser = _parser()
    args = parser.parse_args(argv)
    if args.action is None:
        parser.print_help()
        return 0

    # Each entry reads its own arguments off the namespace, so adding a command is one line
    # here and one in _parser rather than a branch in the middle of the error handling.
    actions = {
        "auth": lambda a: cmd_auth(),
        "logout": lambda a: cmd_logout(),
        "status": lambda a: cmd_status(),
        "list": lambda a: cmd_list(a.search, a.page),
        "backup": lambda a: cmd_backup(a.note),
        "restore": lambda a: cmd_restore(a.backup, a.yes),
        "save": lambda a: cmd_save(a.backup, a.folder),
        "delete": lambda a: cmd_delete(a.backup, a.yes),
        "share": lambda a: cmd_share(a.backup),
        "unshare": lambda a: cmd_unshare(a.backup),
    }

    logs.setup(CLI_LOG_FILE)
    _app()  # before any ApiClient, which builds a QNetworkAccessManager
    _watch_for_interrupt()
    try:
        # argparse has already refused anything not in this table, so the fallback is
        # unreachable rather than a silent success for a name nobody handled.
        action = actions.get(args.action)
        return action(args) if action else 0
    except _Failed as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 1
