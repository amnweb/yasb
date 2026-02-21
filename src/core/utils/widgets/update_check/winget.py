"""Winget package manager module.

Provides synchronous functions for interacting with winget:
- check_updates(): List packages with available upgrades
- upgrade_packages(): Upgrade packages in a visible terminal

Winget truncates its table output based on the console width.  When Python
captures output via pipes there is no console at all, so winget falls back
to a narrow default and cuts long package IDs with like `Microsoft.VisualStudio.2022.Comm…`.

To work around this, we use the Windows ConPTY API
"""

import ctypes
import ctypes.wintypes
import logging
import re
import shutil
import subprocess
import threading

from core.utils.win32.bindings import kernel32

# Subprocess creation flag to hide the console window on Windows.
_CREATE_NO_WINDOW = 0x08000000

# PowerShell executable (prefer pwsh, fall back to powershell)
_PWSH = shutil.which("pwsh") or shutil.which("powershell") or "powershell.exe"


# Regex to strip ANSI/VT escape sequences emitted by the pseudo-terminal
_ANSI_RE = re.compile(
    r"\x1b\[[?>=!]?[0-9;]*[A-Za-z]"  # CSI  (incl. private modes)
    r"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"  # OSC
    r"|\x1b[()][A-Za-z0-9]"  # charset select
)


def _capture_with_conpty(cmd: str, timeout: int = 120, cols: int = 500) -> str | None:
    """Run *cmd* inside a wide pseudo-console and return its output."""
    h = ctypes.wintypes.HANDLE
    in_r, in_w, out_r, out_w = h(), h(), h(), h()
    if not kernel32.CreatePipe(ctypes.byref(in_r), ctypes.byref(in_w), None, 0):
        return None
    if not kernel32.CreatePipe(ctypes.byref(out_r), ctypes.byref(out_w), None, 0):
        kernel32.CloseHandle(in_r)
        kernel32.CloseHandle(in_w)
        return None

    class COORD(ctypes.Structure):
        _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]

    hpc = h()
    if kernel32.CreatePseudoConsole(COORD(cols, 30), in_r, out_w, 0, ctypes.byref(hpc)) != 0:
        for p in (in_r, in_w, out_r, out_w):
            kernel32.CloseHandle(p)
        return None
    kernel32.CloseHandle(out_w)
    kernel32.CloseHandle(in_r)

    SIEX = type(
        "SIEX",
        (ctypes.Structure,),
        {
            "_fields_": [
                ("cb", ctypes.wintypes.DWORD),
                ("_pad", ctypes.c_byte * 100),
                ("lpAttr", ctypes.c_void_p),
            ]
        },
    )
    sz = ctypes.c_size_t()
    kernel32.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(sz))
    attr = (ctypes.c_byte * sz.value)()
    kernel32.InitializeProcThreadAttributeList(ctypes.byref(attr), 1, 0, ctypes.byref(sz))
    kernel32.UpdateProcThreadAttribute(
        ctypes.byref(attr),
        0,
        0x00020016,
        hpc,
        ctypes.sizeof(h),
        None,
        None,
    )
    si = SIEX(cb=112, lpAttr=ctypes.addressof(attr))

    # create process
    PI = type(
        "PI",
        (ctypes.Structure,),
        {
            "_fields_": [
                ("hProcess", h),
                ("hThread", h),
                ("dwPid", ctypes.wintypes.DWORD),
                ("dwTid", ctypes.wintypes.DWORD),
            ]
        },
    )
    pi = PI()
    ok = kernel32.CreateProcessW(
        None,
        cmd,
        None,
        None,
        False,
        0x00080000,
        None,
        None,
        ctypes.byref(si),
        ctypes.byref(pi),
    )
    if not ok:
        kernel32.ClosePseudoConsole(hpc)
        kernel32.CloseHandle(out_r)
        kernel32.CloseHandle(in_w)
        kernel32.DeleteProcThreadAttributeList(ctypes.byref(attr))
        return None

    # Read output in background
    chunks: list[bytes] = []

    def _reader():
        buf = (ctypes.c_char * 4096)()
        n = ctypes.wintypes.DWORD()
        while kernel32.ReadFile(out_r, buf, 4096, ctypes.byref(n), None) and n.value:
            chunks.append(buf[: n.value])

    t = threading.Thread(target=_reader, daemon=True)
    t.start()
    kernel32.WaitForSingleObject(pi.hProcess, timeout * 1000)

    # Cleanup
    kernel32.CloseHandle(pi.hProcess)
    kernel32.CloseHandle(pi.hThread)
    kernel32.ClosePseudoConsole(hpc)
    kernel32.CloseHandle(in_w)
    t.join(timeout=5)
    kernel32.CloseHandle(out_r)
    kernel32.DeleteProcThreadAttributeList(ctypes.byref(attr))

    # Decode & clean
    text = b"".join(chunks).decode("utf-8", errors="replace")
    text = _ANSI_RE.sub("", text)
    # Carriage-returns keep only the last segment
    cleaned: list[str] = []
    for line in text.split("\n"):
        if "\r" in line:
            parts = line.split("\r")
            vis = ""
            for p in parts:
                if p:
                    vis = p + vis[len(p) :]
            cleaned.append(vis)
        else:
            cleaned.append(line)
    return "\n".join(cleaned)


def _detect_column_starts(header_line: str) -> list[int]:
    """Return the character offset where each column header word begins."""
    starts: list[int] = []
    in_word = False
    for i, ch in enumerate(header_line):
        if ch != " " and not in_word:
            starts.append(i)
            in_word = True
        elif ch == " ":
            in_word = False
    return starts


def _compute_offset(line: str, id_index: int) -> int:
    """Compute the character offset caused by wide Unicode characters."""
    if id_index <= 0 or id_index >= len(line):
        return 0
    offset = 0
    while (id_index - offset - 1) >= 0 and offset <= (id_index - 5):
        if line[id_index - offset - 1] == " ":
            break
        offset += 1
    return offset


def _parse_table(
    stdout: str,
    column_names: list[str],
) -> list[dict[str, str]]:
    """Parse winget fixed-width table output into a list of dicts.

    Fully language-agnostic: does not look at header text, only at
    the positions where header words start.
    """
    results: list[dict[str, str]] = []
    lines = stdout.split("\n")

    # Find header & column positions
    prev_line = ""
    data_start = -1
    col_starts: list[int] = []

    for i, raw_line in enumerate(lines):
        line = raw_line.rstrip("\r")
        if "---" in line:
            header = prev_line.rstrip("\r")
            sep_len = len(line)
            # ConPTY may prepend progress-spinner text to the header.
            # Trim the header to the separator length (columns are at the end).
            if len(header) > sep_len > 0:
                header = header[len(header) - sep_len :]
            col_starts = _detect_column_starts(header)
            data_start = i + 1
            break
        prev_line = raw_line

    if data_start < 0 or not col_starts:
        return results

    n_cols = min(len(col_starts), len(column_names))
    if n_cols < 2:
        return results

    id_col_start = col_starts[1] if len(col_starts) > 1 else 0

    for raw_line in lines[data_start:]:
        line = raw_line.rstrip("\r")

        stripped = line.strip()
        if not stripped or stripped.startswith("-"):
            continue

        if len(line) <= id_col_start:
            continue

        offset = _compute_offset(line, id_col_start)

        try:
            row: dict[str, str] = {}
            for c in range(n_cols):
                start = col_starts[c] - offset
                if start < 0:
                    start = 0

                if c + 1 < n_cols:
                    end = col_starts[c + 1] - offset
                    value = line[start:end].strip() if end <= len(line) else line[start:].strip()
                else:
                    remainder = line[start:].strip()
                    value = remainder.split(" ")[0] if remainder else ""

                # Strip winget's truncation ellipsis (U+2026)
                if value.endswith("\u2026"):
                    value = value[:-1]
                row[column_names[c]] = value

        except IndexError, ValueError:
            continue

        name = row.get("name", "")
        pkg_id = row.get("id", "")
        version = row.get("version", "")

        if not name or not pkg_id:
            continue
        if " " in pkg_id:
            continue
        if not any(ch.isdigit() for ch in version):
            continue

        results.append(row)

    return results


def check_updates() -> list[dict[str, str]]:
    """Check for available package upgrades via winget.

    Uses a wide ConPTY so that winget outputs full, untruncated package IDs.

    Returns:
        List of dicts, each with keys:
        ``name``, ``id``, ``version``, ``available``, ``source``.
        Returns an empty list on error.
    """
    try:
        cmd = "winget upgrade --include-unknown --accept-source-agreements --disable-interactivity"
        stdout = _capture_with_conpty(cmd, timeout=120)
        if stdout:
            return _parse_table(
                stdout,
                ["name", "id", "version", "available", "source"],
            )
    except Exception:
        logging.exception("Error checking winget updates")
    return []


def upgrade_packages(package_ids: list[str]) -> None:
    """Upgrade packages by opening a visible PowerShell window.

    If *package_ids* is empty, falls back to ``winget upgrade --all``.
    Returns immediately after launching the terminal.
    """
    powershell = _PWSH
    if package_ids:
        count = len(package_ids)
        package_label = "package" if count == 1 else "packages"
        lines: list[str] = [
            "Write-Host '========================================='",
            f"Write-Host 'YASB found {count} {package_label} ready to update'",
            "Write-Host '========================================='",
        ]
        for pid in package_ids:
            lines.append(f"Write-Host ' - {pid}'")
        lines.append("Write-Host ''")
        for pid in package_ids:
            lines.append(f"Write-Host '>> Upgrading {pid} ...' -ForegroundColor Cyan")
            lines.append(
                f"winget upgrade --id '{pid}'"
                f" --accept-source-agreements --accept-package-agreements"
                f" --disable-interactivity --force"
            )
        script = "; ".join(lines)
        command = f'start "Winget Upgrade" "{powershell}" -NoExit -Command "{script}"'
    else:
        command = f'start "Winget Upgrade" "{powershell}" -NoExit -Command "winget upgrade --all"'
    subprocess.Popen(command, shell=True, creationflags=_CREATE_NO_WINDOW)
