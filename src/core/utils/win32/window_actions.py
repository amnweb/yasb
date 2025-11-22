import ctypes
import logging

import win32con
import win32process

from core.utils.win32.bindings import kernel32 as k32
from core.utils.win32.bindings import user32 as u32

# --- Resolution helpers ---


def resolve_base_and_focus(hwnd: int) -> tuple[int, int]:
    """Return (base_owner_root, focus_target). Focus target is the last active visible popup if any."""
    GA_ROOT = 2
    GA_ROOTOWNER = 3
    base = hwnd
    try:
        base = u32.GetAncestor(hwnd, GA_ROOTOWNER) or u32.GetAncestor(hwnd, GA_ROOT) or hwnd
    except Exception:
        base = hwnd

    focus_target = base
    try:
        last = u32.GetLastActivePopup(base)
        if last and u32.IsWindowVisible(last):
            focus_target = last
    except Exception:
        pass
    return int(base), int(focus_target)


def is_owner_root_active(base: int) -> bool:
    """Check if the owner-root of the current foreground window matches base."""
    GA_ROOT = 2
    GA_ROOTOWNER = 3
    fg = u32.GetForegroundWindow()
    if not fg:
        return False
    try:
        fg_top = u32.GetAncestor(fg, GA_ROOTOWNER) or u32.GetAncestor(fg, GA_ROOT) or fg
    except Exception:
        fg_top = fg
    return int(fg_top) == int(base)


def can_minimize(base: int) -> bool:
    try:
        style = u32.GetWindowLong(base, win32con.GWL_STYLE)
        return bool(style & win32con.WS_MINIMIZEBOX) and bool(u32.IsWindowEnabled(base))
    except Exception:
        return True


# --- Window commands ---


def send_sys_command(hwnd: int, cmd: int) -> bool:
    """Send WM_SYSCOMMAND to a window with a short timeout. Returns True on success."""
    try:
        SMTO_ABORTIFHUNG = 0x0002
        result = ctypes.c_ulong()
        ret = u32.SendMessageTimeoutW(
            int(hwnd),
            int(win32con.WM_SYSCOMMAND),
            int(cmd),
            0,
            SMTO_ABORTIFHUNG,
            200,
            ctypes.byref(result),
        )
        return bool(ret)
    except Exception:
        return False


def restore_window(hwnd: int) -> None:
    if not send_sys_command(hwnd, win32con.SC_RESTORE):
        try:
            u32.ShowWindowAsync(int(hwnd), win32con.SW_RESTORE)
        except Exception:
            u32.ShowWindow(hwnd, win32con.SW_RESTORE)


def minimize_window(hwnd: int) -> None:
    if not send_sys_command(hwnd, win32con.SC_MINIMIZE):
        try:
            u32.ShowWindowAsync(int(hwnd), win32con.SW_MINIMIZE)
        except Exception:
            u32.ShowWindow(hwnd, win32con.SW_FORCEMINIMIZE)


def show_window(hwnd: int) -> None:
    try:
        u32.ShowWindowAsync(int(hwnd), win32con.SW_SHOW)
    except Exception:
        u32.ShowWindow(hwnd, win32con.SW_SHOW)


# --- Foreground helper ---


def set_foreground(hwnd: int) -> None:
    """Attempt to set foreground reliably by attaching input to the target thread."""
    try:
        tgt_tid, _ = win32process.GetWindowThreadProcessId(hwnd)
    except Exception:
        tgt_tid = 0
    cur_tid = k32.GetCurrentThreadId()

    attached = False
    if tgt_tid and cur_tid and tgt_tid != cur_tid:
        try:
            attached = bool(u32.AttachThreadInput(cur_tid, tgt_tid, True))
        except Exception:
            attached = False
    try:
        try:
            u32.BringWindowToTop(hwnd)
        except Exception:
            pass
        u32.SetForegroundWindow(int(hwnd))
        try:
            u32.SetActiveWindow(int(hwnd))
        except Exception:
            pass
    finally:
        if attached:
            try:
                u32.AttachThreadInput(cur_tid, tgt_tid, False)
            except Exception:
                pass


def force_foreground_focus(hwnd: int) -> None:
    """
    Force a window to foreground with focus.

    Args:
        hwnd: Window handle to set as foreground
    """
    if not hwnd:
        return

    try:
        # Get the current foreground window
        fg_hwnd = u32.GetForegroundWindow()

        if fg_hwnd:
            fg_tid, _ = win32process.GetWindowThreadProcessId(fg_hwnd)
            my_tid = k32.GetCurrentThreadId()
            if fg_tid and my_tid and fg_tid != my_tid:
                u32.AttachThreadInput(my_tid, fg_tid, True)
                u32.SetForegroundWindow(hwnd)
                u32.SetFocus(hwnd)
                u32.AttachThreadInput(my_tid, fg_tid, False)
            else:
                u32.SetForegroundWindow(hwnd)
                u32.SetFocus(hwnd)
        else:
            u32.SetForegroundWindow(hwnd)
            u32.SetFocus(hwnd)
    except Exception as e:
        logging.debug(f"Failed to force foreground focus: {e}")


# --- Close application helper ---


def close_application(hwnd: int, force: bool = False):
    """
    Close the application associated with the given HWND.

    Args:
        hwnd: The window handle of the application to close
        force: If True, forcefully terminates the process (like Task Manager's End Task)
               If False, tries graceful close methods first

    Graceful close (force=False):
    - SendMessageTimeout(WM_SYSCOMMAND, SC_CLOSE) to the root owner window
    - Fallback to PostMessage(WM_CLOSE)
    - As a last resort, call EndTask (graceful attempt)

    Forced termination (force=True):
    - Tries EndTask with force flag
    - Falls back to direct TerminateProcess
    """
    try:
        if not hwnd or hwnd == 0:
            logging.warning(f"Invalid HWND: {hwnd}")
            return

        # Resolve a better target: prefer GA_ROOTOWNER, then GA_ROOT
        GA_ROOT = 2
        GA_ROOTOWNER = 3
        try:
            root_owner = u32.GetAncestor(int(hwnd), GA_ROOTOWNER)
        except Exception:
            root_owner = 0
        try:
            root = u32.GetAncestor(int(hwnd), GA_ROOT)
        except Exception:
            root = 0
        target_hwnd = int(root_owner or root or hwnd)

        if force:
            # Forced termination path
            # Get process ID for direct termination
            try:
                _, process_id = win32process.GetWindowThreadProcessId(hwnd)
            except Exception as e:
                logging.error(f"Failed to get process ID for HWND {hwnd}: {e}")
                return

            if not process_id:
                logging.warning(f"No process ID found for HWND: {hwnd}")
                return

            # Try forced EndTask first (Windows shell approach)
            try:
                # BOOL EndTask(HWND hWnd, BOOL fShutDown, BOOL fForce)
                # fForce=True makes it more aggressive
                endtask_ok = u32.EndTask(int(target_hwnd), False, True)
                if endtask_ok:
                    logging.info(f"Successfully ended task via forced EndTask for HWND: {hwnd}")
                    return
            except Exception as et_ex:
                logging.warning(f"Forced EndTask failed for HWND {target_hwnd}: {et_ex}")

            # Fallback: Direct process termination
            PROCESS_TERMINATE = 0x0001
            try:
                # Open process handle with terminate rights
                process_handle = k32.OpenProcess(PROCESS_TERMINATE, False, process_id)
                if not process_handle:
                    logging.error(f"Failed to open process {process_id} for termination")
                    return

                # Terminate the process with exit code 1
                terminated = k32.TerminateProcess(process_handle, 1)
                if terminated:
                    logging.info(f"Successfully terminated process {process_id} for HWND: {hwnd}")
                else:
                    logging.warning(f"TerminateProcess returned False for process {process_id}")

                # Close the process handle
                k32.CloseHandle(process_handle)

            except Exception as term_ex:
                logging.error(f"Failed to terminate process {process_id}: {term_ex}")

        else:
            # Graceful close path
            # First try: SC_CLOSE via SendMessageTimeout to avoid hangs
            WM_SYSCOMMAND = 0x0112
            SC_CLOSE = 0xF060
            SMTO_ABORTIFHUNG = 0x0002

            lpdw_result = ctypes.c_ulong()
            sent = u32.SendMessageTimeoutW(
                int(target_hwnd),
                int(WM_SYSCOMMAND),
                int(SC_CLOSE),
                0,
                int(SMTO_ABORTIFHUNG),
                int(2000),
                ctypes.byref(lpdw_result),
            )

            if sent:
                return

            # Fallback: WM_CLOSE via PostMessage
            WM_CLOSE = 0x0010
            posted = u32.PostMessage(int(target_hwnd), int(WM_CLOSE), 0, 0)
            if posted:
                return

            # Last resort: EndTask (graceful attempt, not forced)
            # BOOL EndTask(HWND hWnd, BOOL fShutDown, BOOL fForce)
            try:
                endtask_ok = u32.EndTask(int(target_hwnd), False, False)
                if not endtask_ok:
                    logging.warning(f"EndTask failed for HWND: {target_hwnd}")
            except Exception as et_ex:
                logging.warning(f"EndTask unavailable/failed for HWND {target_hwnd}: {et_ex}")

    except Exception as e:
        logging.error(f"Failed to close window {hwnd}: {e}")
