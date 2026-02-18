import ctypes
import logging

from core.utils.widgets.quick_launch.base_provider import BaseProvider, ProviderResult
from core.utils.widgets.quick_launch.providers.resources.icons import ICON_KILL_PROCESS
from core.utils.win32.bindings.kernel32 import kernel32
from core.utils.win32.bindings.psapi import psapi
from core.utils.win32.constants import PROCESS_QUERY_LIMITED_INFORMATION, PROCESS_TERMINATE, TH32CS_SNAPPROCESS
from core.utils.win32.structs import PROCESS_MEMORY_COUNTERS, PROCESSENTRY32

_PROTECTED_PROCESSES = frozenset(
    {
        "system",
        "registry",
        "smss.exe",
        "csrss.exe",
        "wininit.exe",
        "services.exe",
        "lsass.exe",
        "winlogon.exe",
        "dwm.exe",
        "explorer.exe",
        "svchost.exe",
    }
)


def _get_process_memory(pid: int) -> int:
    """Return WorkingSetSize (RSS) in bytes for a process, or 0 on failure."""
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return 0
    try:
        pmc = PROCESS_MEMORY_COUNTERS()
        pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        if psapi.GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb):
            return pmc.WorkingSetSize
        return 0
    finally:
        kernel32.CloseHandle(h)


def _enumerate_processes() -> list[tuple[int, str]]:
    """Return list of (pid, exe_name) for all running processes."""
    results = []
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == ctypes.wintypes.HANDLE(-1).value:
        return results
    try:
        entry = PROCESSENTRY32()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
        if not kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
            return results
        while True:
            results.append((entry.th32ProcessID, entry.szExeFile))
            if not kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                break
    finally:
        kernel32.CloseHandle(snapshot)
    return results


def _terminate_process(pid: int) -> bool:
    """Terminate a process by PID. Returns True on success."""
    h = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
    if not h:
        return False
    try:
        return bool(kernel32.TerminateProcess(h, 1))
    finally:
        kernel32.CloseHandle(h)


class KillProcessProvider(BaseProvider):
    """Search and kill running processes."""

    name = "kill_process"
    display_name = "Process Killer"
    input_placeholder = "Type a process name to kill..."
    icon = ICON_KILL_PROCESS

    def match(self, text: str) -> bool:
        text = text.strip()
        if self.prefix and text.startswith(self.prefix):
            return True
        text_lower = text.lower()
        if text_lower.startswith("kill ") and len(text_lower) > 5:
            return True
        return False

    def get_results(self, text: str, **kwargs) -> list[ProviderResult]:
        if self.prefix and text.strip().startswith(self.prefix):
            query = self.get_query_text(text).lower()
        elif text.strip().lower().startswith("kill "):
            query = text.strip()[5:].strip().lower()
        else:
            query = text.strip().lower()

        if not query:
            return [
                ProviderResult(
                    title="Type a process name to kill",
                    description="e.g. !notepad, !chrome, kill firefox",
                    icon_char=ICON_KILL_PROCESS,
                    provider=self.name,
                )
            ]

        # Gather matching processes, grouped by name
        proc_map: dict[str, dict] = {}
        try:
            for pid, exe_name in _enumerate_processes():
                name_lower = exe_name.lower()
                if name_lower in _PROTECTED_PROCESSES:
                    continue
                if query not in name_lower:
                    continue
                if name_lower not in proc_map:
                    proc_map[name_lower] = {
                        "name": exe_name,
                        "pids": [],
                        "total_mem": 0,
                    }
                proc_map[name_lower]["pids"].append(pid)
                proc_map[name_lower]["total_mem"] += _get_process_memory(pid)
        except Exception as e:
            logging.debug(f"Process enumeration error: {e}")
            return []

        results = []
        for key in sorted(proc_map, key=lambda k: proc_map[k]["total_mem"], reverse=True):
            entry = proc_map[key]
            count = len(entry["pids"])
            mem_mb = entry["total_mem"] / (1024 * 1024)
            count_str = f"{count} process{'es' if count > 1 else ''}"
            results.append(
                ProviderResult(
                    title=f"Kill {entry['name']}",
                    description=f"{count_str}, {mem_mb:.1f} MB",
                    icon_char=ICON_KILL_PROCESS,
                    provider=self.name,
                    action_data={"name": entry["name"], "pids": entry["pids"]},
                )
            )
        return results

    def execute(self, result: ProviderResult) -> bool:
        pids = result.action_data.get("pids", [])
        name = result.action_data.get("name", "")
        killed = 0
        for pid in pids:
            try:
                if _terminate_process(pid):
                    killed += 1
                else:
                    logging.debug(f"Failed to terminate PID {pid} ({name})")
            except Exception as e:
                logging.debug(f"Failed to kill PID {pid} ({name}): {e}")
        if killed:
            logging.info(f"Killed {killed} instance(s) of {name}")
        return killed > 0
