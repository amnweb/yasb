"""Scoop's upgradable apps.

scoop update refreshes the buckets, then scoop status prints a table of apps with newer versions. The table is read
by its dashed line under the titles, as a title can be more than one word.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from core.services.updates.terminal import open_terminal, quote

NAME = "Scoop"
TIMEOUT_S = 120

_COLOURS = re.compile(r"\x1b\[[0-9;]*m")


def executable() -> str | None:
    """Scoop's command: on the PATH, or in Scoop's own folder when it was installed after YASB started."""
    if found := shutil.which("scoop"):
        return found
    shim = Path(os.environ.get("SCOOP") or Path.home() / "scoop") / "shims" / "scoop.cmd"
    return str(shim) if shim.is_file() else None


def installed() -> bool:
    return executable() is not None


def _run(*arguments: str) -> str:
    # scoop is a PowerShell script behind a .cmd shim, so it runs through the shell
    return subprocess.run(
        [executable() or "scoop", *arguments],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        shell=True,
        timeout=TIMEOUT_S,
        creationflags=subprocess.CREATE_NO_WINDOW,
    ).stdout


def parse_table(output: str) -> list[dict[str, str]]:
    """The apps in scoop status's table, each {id, name, installedVersion, availableVersion, info}, without held ones."""
    lines = [line.rstrip("\r") for line in _COLOURS.sub("", output).split("\n")]
    separator = next((index for index, line in enumerate(lines) if line.startswith("----")), -1)
    if separator < 0:
        return []
    dashes = lines[separator]
    starts = [index for index, char in enumerate(dashes) if char == "-" and (index == 0 or dashes[index - 1] != "-")]
    fields = ("name", "installedVersion", "availableVersion", "missingDependencies", "info")[: len(starts)]

    apps: list[dict[str, str]] = []
    for line in lines[separator + 1 :]:
        if not line.strip() or line.strip().startswith("-") or len(line) <= starts[0]:
            continue
        row = {
            field: line[starts[index] : starts[index + 1] if index + 1 < len(fields) else None].strip()
            for index, field in enumerate(fields)
        }
        if row["name"] and "held" not in row.get("info", "").lower():
            apps.append(
                {
                    "id": row["name"],
                    "name": row["name"],
                    "installedVersion": row.get("installedVersion", ""),
                    "availableVersion": row.get("availableVersion", ""),
                    "info": row.get("info", ""),
                }
            )
    return apps


def check() -> dict[str, Any]:
    """The apps Scoop can update, as {updates}; raises RuntimeError with what went wrong."""
    try:
        _run("update")
        return {"updates": parse_table(_run("status"))}
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"Scoop took longer than {TIMEOUT_S // 60} minutes to answer.") from error
    except OSError as error:
        raise RuntimeError("Could not run Scoop.") from error


def install(ids: list[str]) -> subprocess.Popen[bytes]:
    """Updates these apps, by name, in a terminal of their own."""
    commands: list[str] = []
    for app in ids:
        commands.append(f"Write-Host {quote('>> Updating ' + app)} -ForegroundColor Cyan")
        commands.append(f"& {quote(executable() or 'scoop')} update {quote(app)}")
    return open_terminal("YASB: Scoop updates", commands)
