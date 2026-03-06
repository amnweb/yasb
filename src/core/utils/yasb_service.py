"""
YASB Launcher — Windows Service

A lightweight Windows service that launches YASB when a user logs in.
When a WTS_SESSION_LOGON event arrives the service launches yasb.exe
with the --service flag directly into the user's session.  The --service
flag tells yasb.exe to register user-installed fonts via GDI before the
GUI starts.  The service waits for explorer.exe to appear in the target
session before launching, ensuring the desktop and network are ready.

Usage (elevated prompt via yasbc.exe):

    yasbc install   # install and set to auto-start
    yasbc start     # start immediately without rebooting
    yasbc stop      # stop the service
    yasbc remove    # stop and remove the service

"""

import ctypes
import ctypes.wintypes
import sys
import threading
import time

import servicemanager
import win32event
import win32service
import win32serviceutil
import win32ts

SERVICE_NAME = "YasbReborn"
SERVICE_DISPLAY = "YASB Reborn Launcher Service"
SERVICE_DESC = "This service is responsible for launching YASB Reborn at user login."

WTS_SESSION_LOGON = 5
TOKEN_ALL_ACCESS = 0xF01FF
SECURITY_IMPERSONATION = 2
TOKEN_PRIMARY = 1
STARTF_USESHOWWINDOW = 0x0001
SW_SHOW = 5
CREATE_UNICODE_ENVIRONMENT = 0x00000400
CREATE_NEW_CONSOLE = 0x00000010
EXPLORER_WAIT_TIMEOUT = 30
EXPLORER_POLL_INTERVAL = 0.25


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


def _log_error(msg: str) -> None:
    servicemanager.LogErrorMsg(f"[YasbLauncher] {msg}")


def _log_warning(msg: str) -> None:
    servicemanager.LogWarningMsg(f"[YasbLauncher] {msg}")


def _wait_for_explorer(session_id: int) -> bool:
    """Wait until explorer.exe is running in the target session.

    WTSEnumerateProcesses returns tuples: (SessionId, ProcessId, ProcessName, UserSid)
    """
    deadline = time.monotonic() + EXPLORER_WAIT_TIMEOUT
    while time.monotonic() < deadline:
        try:
            for sid, _pid, name, _usersid in win32ts.WTSEnumerateProcesses(win32ts.WTS_CURRENT_SERVER_HANDLE):
                if sid == session_id and name.lower() == "explorer.exe":
                    return True
        except Exception:
            pass
        time.sleep(EXPLORER_POLL_INTERVAL)
    _log_warning(f"Session {session_id}: explorer.exe not found after {EXPLORER_WAIT_TIMEOUT}s")
    return False


def _launch_in_session(session_id: int) -> bool:
    """Launch yasb.exe --service into the given user session."""
    kernel32 = ctypes.windll.kernel32
    advapi32 = ctypes.windll.advapi32
    userenv = ctypes.windll.userenv
    wtsapi32 = ctypes.windll.wtsapi32

    h_token = ctypes.wintypes.HANDLE()
    if not wtsapi32.WTSQueryUserToken(session_id, ctypes.byref(h_token)):
        _log_error(f"Session {session_id}: WTSQueryUserToken failed ({ctypes.GetLastError()})")
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
        _log_error(f"Session {session_id}: DuplicateTokenEx failed ({ctypes.GetLastError()})")
        return False

    lp_env = ctypes.c_void_p()
    has_env = bool(userenv.CreateEnvironmentBlock(ctypes.byref(lp_env), h_primary, False))

    si = STARTUPINFOW()
    si.cb = ctypes.sizeof(si)
    si.lpDesktop = "winsta0\\default"
    si.dwFlags = STARTF_USESHOWWINDOW
    si.wShowWindow = SW_SHOW

    pi = PROCESS_INFORMATION()
    flags = CREATE_NEW_CONSOLE | (CREATE_UNICODE_ENVIRONMENT if has_env else 0)

    ok = advapi32.CreateProcessAsUserW(
        h_primary,
        None,
        "yasb.exe --service",
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
        _log_error(f"Session {session_id}: CreateProcessAsUserW failed ({ctypes.GetLastError()})")
        return False

    kernel32.CloseHandle(pi.hProcess)
    kernel32.CloseHandle(pi.hThread)
    return True


class YasbRebornService(win32serviceutil.ServiceFramework):
    _svc_name_ = SERVICE_NAME
    _svc_display_name_ = SERVICE_DISPLAY
    _svc_description_ = SERVICE_DESC

    def __init__(self, args):
        super().__init__(args)
        self._stop_event = win32event.CreateEvent(None, 0, 0, None)
        self._launched: set[int] = set()
        self._lock = threading.Lock()

    def GetAcceptedControls(self):
        return super().GetAcceptedControls() | win32service.SERVICE_ACCEPT_SESSIONCHANGE

    def SvcOtherEx(self, control, event_type, data):
        if control == win32service.SERVICE_CONTROL_SESSIONCHANGE and event_type == WTS_SESSION_LOGON:
            session_id: int = data[0] if isinstance(data, tuple) else data
            with self._lock:
                if session_id in self._launched:
                    return
                self._launched.add(session_id)
            threading.Thread(target=self._launch_yasb, args=(session_id,), daemon=True).start()

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self._stop_event)

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, ""),
        )
        self._launch_active_sessions()
        win32event.WaitForSingleObject(self._stop_event, win32event.INFINITE)
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STOPPED,
            (self._svc_name_, ""),
        )

    def _launch_active_sessions(self):
        """Launch YASB for any user sessions already active at service start."""
        try:
            sessions = win32ts.WTSEnumerateSessions(win32ts.WTS_CURRENT_SERVER_HANDLE)
        except Exception as exc:
            _log_error(f"WTSEnumerateSessions failed: {exc}")
            return
        for sess in sessions:
            sid = sess["SessionId"]
            if sid == 0 or sess["State"] != win32ts.WTSActive:
                continue
            with self._lock:
                if sid in self._launched:
                    continue
                self._launched.add(sid)
            threading.Thread(target=self._launch_yasb, args=(sid,), daemon=True).start()

    def _launch_yasb(self, session_id: int):
        _wait_for_explorer(session_id)
        if not _launch_in_session(session_id):
            _log_error(f"Failed to launch YASB in session {session_id}")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(YasbRebornService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(YasbRebornService)
