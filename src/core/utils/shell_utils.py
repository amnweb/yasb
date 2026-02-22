"""
Utilities for launching files, URLs, and shortcuts via the Windows shell.
"""

import threading

from core.utils.win32.bindings.shell32 import shell_execute
from core.utils.win32.constants import SW_SHOWNORMAL


def shell_open(
    file: str,
    verb: str = "open",
    parameters: str | None = None,
    directory: str | None = None,
    show_cmd: int = SW_SHOWNORMAL,
) -> None:
    """Launch a file, URL, or shortcut without blocking the UI thread.

    This is a thin wrapper around :func:`shell_execute` that dispatches the
    call on a daemon thread. ShellExecuteW is synchronous and can block the UI
    if the launched process takes time to start,

    Args:
        file: Path to the file, URL, or shortcut to open.
        verb: Shell verb — ``"open"``, ``"runas"``, ``"edit"``, ``"print"``, etc.
        parameters: Optional command-line arguments.
        directory: Optional working directory.
        show_cmd: Window show state (``SW_SHOWNORMAL=1``, ``SW_HIDE=0``, etc).
    """
    threading.Thread(
        target=shell_execute,
        args=(file, verb, parameters, directory, show_cmd),
        daemon=True,
    ).start()
