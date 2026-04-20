"""Scoop package manager module.

Provides synchronous functions for interacting with the Scoop CLI:
- check_updates(): Refresh buckets then list packages with available upgrades
- upgrade_packages(): Upgrade multiple packages in a visible terminal
"""

import logging
import re
import shutil
import subprocess

# Regex to strip ANSI escape sequences from scoop output.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# Subprocess creation flag to hide the console window on Windows.
_CREATE_NO_WINDOW = 0x08000000


def _run_scoop(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    """Execute a scoop command and return the result.

    Uses UTF-8 encoding and hides the console window.
    """
    cmd = ["scoop", *args]
    return subprocess.run(
        cmd,
        capture_output=True,
        encoding="utf-8",
        text=True,
        shell=True,
        timeout=timeout,
        creationflags=_CREATE_NO_WINDOW,
    )


def _detect_column_starts(separator_line: str) -> list[int]:
    """Return the character offset where each column begins.

    Uses the ``----`` separator line rather than the header, because scoop
    headers can contain multi-word names (e.g. "Installed Version").
    """
    starts: list[int] = []
    in_dash = False
    for i, ch in enumerate(separator_line):
        if ch == "-" and not in_dash:
            starts.append(i)
            in_dash = True
        elif ch != "-":
            in_dash = False
    return starts


def _parse_table(
    stdout: str,
    column_names: list[str],
) -> list[dict[str, str]]:
    """Parse scoop fixed-width table output into a list of dicts."""
    stdout = _ANSI_RE.sub("", stdout)
    results: list[dict[str, str]] = []
    lines = stdout.split("\n")

    data_start = -1
    col_starts: list[int] = []

    for i, raw_line in enumerate(lines):
        line = raw_line.rstrip("\r")
        if line.startswith("----"):
            col_starts = _detect_column_starts(line)
            data_start = i + 1
            break

    if data_start < 0 or not col_starts:
        return results

    n_cols = min(len(col_starts), len(column_names))
    if n_cols < 1:
        return results

    for raw_line in lines[data_start:]:
        line = raw_line.rstrip("\r")

        stripped = line.strip()
        if not stripped or stripped.startswith("-"):
            continue

        if len(line) <= col_starts[0]:
            continue

        try:
            row: dict[str, str] = {}
            for c in range(n_cols):
                start = col_starts[c]

                if start >= len(line):
                    row[column_names[c]] = ""
                    continue

                if c + 1 < n_cols:
                    end = col_starts[c + 1]
                    value = line[start:end].strip()
                else:
                    value = line[start:].strip()

                row[column_names[c]] = value

        except IndexError, ValueError:
            continue

        name = row.get("name", "")
        if not name:
            continue

        results.append(row)

    return results


def check_updates() -> list[dict[str, str]]:
    """Check for available package upgrades via scoop.

    Runs ``scoop update`` to refresh buckets, then ``scoop status``
    to detect outdated packages.

    Returns:
        List of dicts with standardized keys:
        ``name``, ``id``, ``version``, ``available``, ``source``,
        plus extras: ``missing_deps``, ``info``.
        Returns an empty list on error.
    """
    try:
        _run_scoop(["update"], timeout=120)

        result = _run_scoop(["status"], timeout=120)
        if not result.stdout:
            return []
        raw = _parse_table(
            result.stdout,
            ["name", "version", "available", "missing_deps", "info"],
        )
        for row in raw:
            row["id"] = row["name"]
            row["source"] = "scoop"
        return raw
    except subprocess.TimeoutExpired:
        logging.warning("scoop status timed out")
        return []
    except FileNotFoundError:
        logging.error("scoop executable not found")
        return []
    except Exception:
        logging.exception("Error checking scoop updates")
        return []


def upgrade_packages(package_names: list[str]) -> None:
    """Upgrade packages by opening a visible PowerShell window.

    If *package_names* is empty, falls back to ``scoop update *``.
    Returns immediately after launching the terminal.
    """
    powershell = shutil.which("pwsh") or shutil.which("powershell") or "powershell.exe"
    if package_names:
        count = len(package_names)
        package_label = "package" if count == 1 else "packages"
        lines: list[str] = [
            "Write-Host '========================================='",
            f"Write-Host 'YASB found {count} scoop {package_label} ready to update'",
            "Write-Host '========================================='",
        ]
        for name in package_names:
            lines.append(f"Write-Host ' - {name}'")
        lines.append("Write-Host ''")
        for name in package_names:
            safe = name.replace("'", "''")
            lines.append(f"Write-Host '>> Updating {safe} ...' -ForegroundColor Cyan")
            lines.append(f"scoop update '{safe}'")
        script = "; ".join(lines)
        command = f'start "Scoop Update" "{powershell}" -NoExit -Command "{script}"'
    else:
        command = f'start "Scoop Update" "{powershell}" -NoExit -Command "scoop update *"'
    subprocess.Popen(command, shell=True, creationflags=_CREATE_NO_WINDOW)
