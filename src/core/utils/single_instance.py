import contextlib
import logging
import sys
import time

from core.utils.win32.bindings.kernel32 import CloseHandle, CreateMutex, GetLastError, OpenMutex
from core.utils.win32.constants import ERROR_ALREADY_EXISTS, SYNCHRONIZE

BAR_MUTEX_NAME = "yasb_reborn"


@contextlib.contextmanager
def single_instance_lock(name: str = BAR_MUTEX_NAME):
    """Hold a named mutex so only one YASB instance runs at a time."""

    deadline = time.monotonic() + (10.0 if "--restart-wait" in sys.argv else 0.0)
    waiting = False

    while True:
        mutex = CreateMutex(None, False, name)
        if not mutex:
            logging.error("Failed to create mutex.")
            sys.exit(1)
        if GetLastError() != ERROR_ALREADY_EXISTS:
            break

        CloseHandle(mutex)
        if time.monotonic() >= deadline:
            logging.error(
                "Timeout waiting for previous instance. Aborting start."
                if waiting
                else "Another instance of the YASB is already running."
            )
            sys.exit(1)
        if not waiting:
            logging.info("Waiting for previous YASB instance to exit...")
            waiting = True
        time.sleep(0.25)

    if waiting:
        logging.info("Previous instance exited, continuing startup.")

    # Windows closes the handle once this process has exited; closing it earlier would let a waiting
    # instance start while this one is still shutting down.
    yield mutex


def wait_for_bar_exit(timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while True:
        handle = OpenMutex(SYNCHRONIZE, False, BAR_MUTEX_NAME)
        if not handle:
            return True
        CloseHandle(handle)
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.1)
