"""winget's upgradable packages.

winget prints only a table, and cuts long names and ids to fit its console. Captured through a pipe it has no
console and cuts them short, so it runs in a wide pseudo-console (ConPTY) instead. The table is read by where each
column starts, not by its titles, which Windows translates.
"""

import ctypes
import ctypes.wintypes
import re
import shutil
import subprocess
import threading
from typing import Any

from core.services.updates.terminal import open_terminal, quote
from core.utils.win32.bindings.kernel32 import kernel32
from core.utils.win32.constants import (
    EXTENDED_STARTUPINFO_PRESENT,
    PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE,
    STARTF_USESTDHANDLES,
)
from core.utils.win32.structs import COORD, PROCESS_INFORMATION, STARTUPINFOEXW

NAME = "winget"
CHECK_COMMAND = "winget upgrade --include-unknown --accept-source-agreements --disable-interactivity"
TIMEOUT_S = 120

# The VT escape sequences the pseudo-console writes
_ESCAPES = re.compile(
    r"\x1b\[[?>=!]?[0-9;]*[A-Za-z]"  # CSI, private modes too
    r"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"  # OSC
    r"|\x1b[()][A-Za-z0-9]"  # charset select
)


def installed() -> bool:
    return shutil.which("winget") is not None


def _capture(command: str, timeout_s: int = TIMEOUT_S, columns: int = 500) -> str | None:
    """What the command writes in a pseudo-console this many columns wide, or None when it cannot run."""
    handle = ctypes.wintypes.HANDLE
    in_read, in_write, out_read, out_write = handle(), handle(), handle(), handle()
    if not kernel32.CreatePipe(ctypes.byref(in_read), ctypes.byref(in_write), None, 0):
        return None
    if not kernel32.CreatePipe(ctypes.byref(out_read), ctypes.byref(out_write), None, 0):
        kernel32.CloseHandle(in_read)
        kernel32.CloseHandle(in_write)
        return None

    console = handle()
    if kernel32.CreatePseudoConsole(COORD(columns, 30), in_read, out_write, 0, ctypes.byref(console)) != 0:
        for pipe in (in_read, in_write, out_read, out_write):
            kernel32.CloseHandle(pipe)
        return None
    kernel32.CloseHandle(out_write)
    kernel32.CloseHandle(in_read)

    size = ctypes.c_size_t()
    kernel32.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
    attributes = (ctypes.c_byte * size.value)()
    kernel32.InitializeProcThreadAttributeList(ctypes.byref(attributes), 1, 0, ctypes.byref(size))
    kernel32.UpdateProcThreadAttribute(
        ctypes.byref(attributes), 0, PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE, console, ctypes.sizeof(handle), None, None
    )
    startup = STARTUPINFOEXW(lpAttributeList=ctypes.addressof(attributes))
    startup.StartupInfo.cb = ctypes.sizeof(STARTUPINFOEXW)
    # No standard handles of YASB's own, or winget writes to them instead of the pseudo-console when YASB's are
    # redirected
    startup.StartupInfo.dwFlags = STARTF_USESTDHANDLES

    process = PROCESS_INFORMATION()
    if not kernel32.CreateProcessW(
        None, command, None, None, False, EXTENDED_STARTUPINFO_PRESENT, None, None, ctypes.byref(startup),
        ctypes.byref(process),
    ):  # fmt: skip
        kernel32.ClosePseudoConsole(console)
        kernel32.CloseHandle(out_read)
        kernel32.CloseHandle(in_write)
        kernel32.DeleteProcThreadAttributeList(ctypes.byref(attributes))
        return None

    chunks: list[bytes] = []

    def read() -> None:
        buffer = (ctypes.c_char * 4096)()
        count = ctypes.wintypes.DWORD()
        while kernel32.ReadFile(out_read, buffer, 4096, ctypes.byref(count), None) and count.value:
            chunks.append(buffer.raw[: count.value])

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    kernel32.WaitForSingleObject(process.hProcess, timeout_s * 1000)

    kernel32.CloseHandle(process.hProcess)
    kernel32.CloseHandle(process.hThread)
    kernel32.ClosePseudoConsole(console)
    kernel32.CloseHandle(in_write)
    reader.join(timeout=5)
    kernel32.CloseHandle(out_read)
    kernel32.DeleteProcThreadAttributeList(ctypes.byref(attributes))

    text = _ESCAPES.sub("", b"".join(chunks).decode("utf-8", errors="replace"))
    # A carriage return writes over the line from its start, as the progress spinner does
    lines: list[str] = []
    for line in text.split("\n"):
        shown = ""
        for part in line.split("\r"):
            if part:
                shown = part + shown[len(part) :]
        lines.append(shown)
    return "\n".join(lines)


def _column_starts(header: str) -> list[int]:
    """Where each word of the header starts; winget's column titles are single words in every language."""
    return [index for index, char in enumerate(header) if char != " " and (index == 0 or header[index - 1] == " ")]


def _wide_shift(line: str, id_start: int) -> int:
    """How far a name with wide characters, such as CJK ones, pushes the rest of the line to the left."""
    if id_start <= 0 or id_start >= len(line):
        return 0
    shift = 0
    while id_start - shift - 1 >= 0 and shift <= id_start - 5 and line[id_start - shift - 1] != " ":
        shift += 1
    return shift


def parse_table(output: str) -> list[dict[str, str]]:
    """The packages in winget upgrade's table, each {id, name, installedVersion, availableVersion, origin}.

    A package whose installed version winget does not know is kept, as --include-unknown asks for it; lines without
    an available version, such as the summary under the table, are not packages.
    """
    lines = [line.rstrip("\r") for line in output.split("\n")]
    separator = next((index for index, line in enumerate(lines) if "---" in line), -1)
    if separator <= 0:
        return []
    header = lines[separator - 1]
    # The pseudo-console can put the spinner before the header; the columns are at its end
    if len(header) > len(lines[separator]) > 0:
        header = header[len(header) - len(lines[separator]) :]
    starts = _column_starts(header)
    if len(starts) < 4:
        return []
    starts = starts[:5]
    fields = ("name", "id", "installedVersion", "availableVersion", "origin")[: len(starts)]

    packages: list[dict[str, str]] = []
    for line in lines[separator + 1 :]:
        if not line.strip() or line.strip().startswith("-") or len(line) <= starts[1]:
            continue
        shift = _wide_shift(line, starts[1])
        row: dict[str, str] = {}
        for index, field in enumerate(fields):
            start = max(0, starts[index] - shift)
            if index + 1 < len(fields):
                value = line[start : starts[index + 1] - shift].strip()
            else:
                rest = line[start:].strip()
                value = rest.split(" ")[0] if rest else ""
            # winget ends a value it had to cut with an ellipsis
            row[field] = value.removesuffix("…")
        if row["name"] and row["id"] and " " not in row["id"] and any(c.isdigit() for c in row["availableVersion"]):
            row.setdefault("origin", "")
            packages.append(row)
    return packages


def check() -> dict[str, Any]:
    """The packages winget can upgrade, as {updates}; raises RuntimeError with what went wrong."""
    output = _capture(CHECK_COMMAND)
    if output is None:
        raise RuntimeError("Could not run winget.")
    return {"updates": parse_table(output)}


def install(ids: list[str]) -> subprocess.Popen[bytes]:
    """Upgrades these packages, by id, in a terminal of their own."""
    commands: list[str] = []
    for package in ids:
        commands.append(f"Write-Host {quote('>> Upgrading ' + package)} -ForegroundColor Cyan")
        commands.append(
            f"winget upgrade --id {quote(package)} --exact --accept-source-agreements --accept-package-agreements "
            "--disable-interactivity"
        )
    return open_terminal("YASB: winget updates", commands)
