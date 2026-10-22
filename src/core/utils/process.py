from core.utils.win32.bindings.kernel32 import kernel32, snapshot_processes
from core.utils.win32.constants import PROCESS_TERMINATE


def is_process_running(process_name: str) -> bool:
    target = process_name.lower()
    return any(process.exe.lower() == target for process in snapshot_processes())


def terminate_process(pid: int) -> bool:
    handle = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
    if not handle:
        return False
    try:
        return bool(kernel32.TerminateProcess(handle, 1))
    finally:
        kernel32.CloseHandle(handle)
