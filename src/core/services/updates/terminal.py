import shutil
import subprocess


def quote(value: str) -> str:
    """A PowerShell single-quoted string, which takes nothing in it as code."""
    return "'" + value.replace("'", "''") + "'"


def open_terminal(title: str, commands: list[str]) -> subprocess.Popen[bytes]:
    """Runs the PowerShell commands in a terminal of their own, which waits for Enter before it closes.

    The terminal shows the progress and any prompts, such as one for administrator rights; the process ends when it
    closes, so the caller knows when to check again.
    """
    powershell = shutil.which("pwsh") or shutil.which("powershell") or "powershell.exe"
    script = "; ".join(
        [
            f"$Host.UI.RawUI.WindowTitle = {quote(title)}",
            *commands,
            "Write-Host ''",
            "Read-Host 'Done. Press Enter to close'",
        ]
    )
    return subprocess.Popen(
        [powershell, "-NoLogo", "-NoProfile", "-Command", script], creationflags=subprocess.CREATE_NEW_CONSOLE
    )
