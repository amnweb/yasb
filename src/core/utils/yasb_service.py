"""
YASB Launcher — Windows Service

A lightweight Windows service that launches YASB immediately when a user
logs in, before the normal startup delay kicks in. It waits for the desktop
shell to be fully ready, then starts yasb.exe directly into the user's session.


To set it up, run it from an elevated prompt using the yasbc.exe:

    yasbc install   # install and set to auto-start
    yasbc start     # start immediately without rebooting
    yasbc stop      # stop the service
    yasbc remove    # stop and remove the service

"""

import ctypes
import ctypes.wintypes
import sys
import time

import servicemanager
import win32event
import win32service
import win32serviceutil
import win32ts

# Service metadata

SERVICE_NAME = "YasbReborn"
SERVICE_DISPLAY = "YASB Reborn Launcher Service"
SERVICE_DESC = "This service is responsible for launching YASB Reborn at user login."

EXPLORER_IDLE_TIMEOUT_SECONDS = 60
POLL_INTERVAL_MS = 100

TOKEN_ALL_ACCESS = 0xF01FF
SECURITY_IMPERSONATION = 2
TOKEN_PRIMARY = 1
STARTF_USESHOWWINDOW = 0x0001
SW_SHOW = 5
CREATE_UNICODE_ENVIRONMENT = 0x00000400
CREATE_NEW_CONSOLE = 0x00000010
TH32CS_SNAPPROCESS = 0x00000002
PROCESS_QUERY_LIMITED = 0x1000
PROCESS_SYNCHRONIZE = 0x00100000


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.wintypes.DWORD),
        ("lpReserved", ctypes.wintypes.LPWSTR),
        ("lpDesktop", ctypes.wintypes.LPWSTR),
        ("lpTitle", ctypes.wintypes.LPWSTR),
        ("dwX", ctypes.wintypes.DWORD),
        ("dwY", ctypes.wintypes.DWORD),
        ("dwXSize", ctypes.wintypes.DWORD),
        ("dwYSize", ctypes.wintypes.DWORD),
        ("dwXCountChars", ctypes.wintypes.DWORD),
        ("dwYCountChars", ctypes.wintypes.DWORD),
        ("dwFillAttribute", ctypes.wintypes.DWORD),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("wShowWindow", ctypes.wintypes.WORD),
        ("cbReserved2", ctypes.wintypes.WORD),
        ("lpReserved2", ctypes.wintypes.LPBYTE),
        ("hStdInput", ctypes.wintypes.HANDLE),
        ("hStdOutput", ctypes.wintypes.HANDLE),
        ("hStdError", ctypes.wintypes.HANDLE),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", ctypes.wintypes.HANDLE),
        ("hThread", ctypes.wintypes.HANDLE),
        ("dwProcessId", ctypes.wintypes.DWORD),
        ("dwThreadId", ctypes.wintypes.DWORD),
    ]


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.wintypes.DWORD),
        ("cntUsage", ctypes.wintypes.DWORD),
        ("th32ProcessID", ctypes.wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", ctypes.wintypes.DWORD),
        ("cntThreads", ctypes.wintypes.DWORD),
        ("th32ParentProcessID", ctypes.wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


def _log_error(msg: str) -> None:
    servicemanager.LogErrorMsg(f"[YasbLauncher] {msg}")


def _launch_in_session(session_id: int) -> bool:
    """Launch yasb.exe into the session identified by session_id."""
    kernel32 = ctypes.windll.kernel32
    advapi32 = ctypes.windll.advapi32
    userenv = ctypes.windll.userenv
    wtsapi32 = ctypes.windll.wtsapi32

    h_token = ctypes.wintypes.HANDLE()
    if not wtsapi32.WTSQueryUserToken(session_id, ctypes.byref(h_token)):
        _log_error(f"WTSQueryUserToken(session={session_id}) failed: {ctypes.GetLastError()}")
        return False

    h_primary = ctypes.wintypes.HANDLE()
    ok = advapi32.DuplicateTokenEx(
        h_token,
        TOKEN_ALL_ACCESS,
        None,
        SECURITY_IMPERSONATION,
        TOKEN_PRIMARY,
        ctypes.byref(h_primary),
    )
    kernel32.CloseHandle(h_token)
    if not ok:
        _log_error(f"DuplicateTokenEx failed: {ctypes.GetLastError()}")
        return False

    lp_env = ctypes.c_void_p()
    has_env = bool(userenv.CreateEnvironmentBlock(ctypes.byref(lp_env), h_primary, False))
    if not has_env:
        _log_error(f"CreateEnvironmentBlock failed: {ctypes.GetLastError()} — using NULL env")

    si = STARTUPINFOW()
    si.cb = ctypes.sizeof(si)
    si.lpDesktop = "winsta0\\default"
    si.dwFlags = STARTF_USESHOWWINDOW
    si.wShowWindow = SW_SHOW

    pi = PROCESS_INFORMATION()
    flags = CREATE_NEW_CONSOLE | (CREATE_UNICODE_ENVIRONMENT if has_env else 0)

    ok = advapi32.CreateProcessAsUserW(
        h_primary,
        None,  # lpApplicationName — resolved via PATH
        "yasb.exe",  # lpCommandLine
        None,
        None,
        False,
        flags,
        lp_env if has_env else None,
        None,
        ctypes.byref(si),
        ctypes.byref(pi),
    )

    if has_env:
        userenv.DestroyEnvironmentBlock(lp_env)
    kernel32.CloseHandle(h_primary)

    if not ok:
        _log_error(f"CreateProcessAsUserW failed: {ctypes.GetLastError()}")
        return False

    kernel32.CloseHandle(pi.hProcess)
    kernel32.CloseHandle(pi.hThread)
    return True


def _wait_for_explorer_idle(session_id: int) -> bool:
    """Wait until explorer.exe in the given session is fully idle (shell ready, fonts loaded)."""
    kernel32 = ctypes.windll.kernel32
    deadline = time.time() + EXPLORER_IDLE_TIMEOUT_SECONDS

    while time.time() < deadline:
        snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snap == ctypes.wintypes.HANDLE(-1).value:
            time.sleep(0.1)
            continue

        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        explorer_pid = None

        try:
            if kernel32.Process32FirstW(snap, ctypes.byref(entry)):
                while True:
                    if entry.szExeFile.lower() == "explorer.exe":
                        sid_out = ctypes.wintypes.DWORD()
                        if kernel32.ProcessIdToSessionId(entry.th32ProcessID, ctypes.byref(sid_out)):
                            if sid_out.value == session_id:
                                explorer_pid = entry.th32ProcessID
                                break
                    if not kernel32.Process32NextW(snap, ctypes.byref(entry)):
                        break
        finally:
            kernel32.CloseHandle(snap)

        if explorer_pid:
            h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED | PROCESS_SYNCHRONIZE, False, explorer_pid)
            if h:
                try:
                    remaining_ms = max(1, int((deadline - time.time()) * 1000))
                    ctypes.windll.user32.WaitForInputIdle(h, remaining_ms)
                finally:
                    kernel32.CloseHandle(h)
                return True

        time.sleep(0.1)

    return False


class YasbRebornService(win32serviceutil.ServiceFramework):
    _svc_name_ = SERVICE_NAME
    _svc_display_name_ = SERVICE_DISPLAY
    _svc_description_ = SERVICE_DESC

    def __init__(self, args):
        super().__init__(args)
        self._stop_event = win32event.CreateEvent(None, 0, 0, None)
        self._launched: set[int] = set()

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self._stop_event)

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, ""),
        )
        self._main_loop()
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STOPPED,
            (self._svc_name_, ""),
        )

    def _main_loop(self):
        while True:
            rc = win32event.WaitForSingleObject(self._stop_event, POLL_INTERVAL_MS)
            if rc == win32event.WAIT_OBJECT_0:
                break
            self._check_sessions()

    def _check_sessions(self):
        try:
            sessions = win32ts.WTSEnumerateSessions(win32ts.WTS_CURRENT_SERVER_HANDLE)
        except Exception as exc:
            _log_error(f"WTSEnumerateSessions failed: {exc}")
            return

        for sess in sessions:
            sid: int = sess["SessionId"]
            state: int = sess["State"]

            if sid == 0 or sid in self._launched:
                continue
            if state != win32ts.WTSActive:
                continue

            self._launched.add(sid)
            _wait_for_explorer_idle(sid)
            _launch_in_session(sid)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(YasbRebornService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(YasbRebornService)
