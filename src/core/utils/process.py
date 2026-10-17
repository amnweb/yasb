from core.utils.win32.bindings.kernel32 import snapshot_processes


def is_process_running(process_name: str) -> bool:
    target = process_name.lower()
    return any(process.exe.lower() == target for process in snapshot_processes())
