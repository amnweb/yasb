# pyright: reportPrivateUsage=false

import ctypes
from collections.abc import Iterator
from queue import Queue
from threading import Event, Thread
from typing import Literal
from uuid import uuid4

import pytest
from PyQt6.QtWidgets import QApplication

from core.utils.win32.bindings.kernel32 import CloseHandle, CreateFile, WaitForSingleObject, WaitNamedPipe, WriteFile
from core.utils.win32.constants import (
    ERROR_BROKEN_PIPE,
    FILE_ATTRIBUTE_NORMAL,
    GENERIC_WRITE,
    INVALID_HANDLE_VALUE,
    OPEN_EXISTING,
)
from core.widgets.services.systray import systray_hook


@pytest.fixture
def hook(monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> Iterator[systray_hook.SystrayHook]:
    def is_dll_loaded(pid: int, dll_name: str) -> bool:
        return True

    suffix = uuid4().hex
    monkeypatch.setattr(systray_hook, "MESSAGE_PIPE_NAME", rf"\\.\pipe\yasb-test-{suffix}")
    monkeypatch.setattr(systray_hook, "WATCHDOG_MUTEX_NAME", rf"Local\YASBTrayHookTest-{suffix}")
    monkeypatch.setattr(systray_hook, "get_explorer_pid", lambda: 1)
    monkeypatch.setattr(systray_hook, "get_dll_path", lambda: "test-hook.dll")
    monkeypatch.setattr(systray_hook, "is_dll_loaded", is_dll_loaded)
    instance = systray_hook.SystrayHook()
    yield instance
    instance.destroy()


def _open_client() -> int:
    client = CreateFile(systray_hook.MESSAGE_PIPE_NAME, GENERIC_WRITE, 0, None, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL)
    if not client or client == INVALID_HANDLE_VALUE:
        raise ctypes.WinError(systray_hook.GetLastError())
    return client


def _dll_not_loaded(pid: int, dll_name: str) -> bool:
    return False


@pytest.mark.parametrize("size", [17, systray_hook.PIPE_BUFFER_SIZE, 2 * systray_hook.PIPE_BUFFER_SIZE + 17])
def test_reads_complete_binary_messages(
    hook: systray_hook.SystrayHook, monkeypatch: pytest.MonkeyPatch, size: int
) -> None:
    received = Queue[bytes]()
    monkeypatch.setattr(hook, "_process_message", received.put)
    # Connecting before run() also exercises ERROR_PIPE_CONNECTED.
    client = _open_client()
    worker = Thread(target=hook.run, daemon=True)
    worker.start()
    try:
        payload = (bytes(range(256)) * (size // 256 + 1))[:size]
        assert WriteFile(client, payload)
        assert received.get(timeout=5) == payload
        assert WriteFile(client, b"next message")
        assert received.get(timeout=5) == b"next message"
    finally:
        hook.destroy()
        worker.join(timeout=5)
        CloseHandle(client)
    assert not worker.is_alive()


@pytest.mark.parametrize("phase", ["connect", "read"])
def test_shutdown_drains_pending_io_and_closes_handles(
    hook: systray_hook.SystrayHook, monkeypatch: pytest.MonkeyPatch, phase: Literal["connect", "read"]
) -> None:
    waiting = Event()
    closed: list[int] = []

    def wait_for_io(handle: int, milliseconds: int) -> int:
        waiting.set()
        return WaitForSingleObject(handle, milliseconds)

    def close_handle(handle: int) -> bool:
        closed.append(handle)
        return bool(CloseHandle(handle))

    monkeypatch.setattr(systray_hook, "WaitForSingleObject", wait_for_io)
    monkeypatch.setattr(systray_hook, "CloseHandle", close_handle)
    worker = Thread(target=hook.run, daemon=True)
    # A connected client with no data makes the first wait a pending read.
    client = _open_client() if phase == "read" else None
    worker.start()
    try:
        assert waiting.wait(timeout=5)
        hook.destroy()
        worker.join(timeout=5)
    finally:
        hook.destroy()
        worker.join(timeout=5)
        if client is not None:
            CloseHandle(client)
    assert not worker.is_alive()
    # Pipe, watchdog mutex, and the worker's completion event.
    assert len(closed) == 3
    assert len(set(closed)) == 3


def test_reconnects_after_client_disconnects(hook: systray_hook.SystrayHook, monkeypatch: pytest.MonkeyPatch) -> None:
    received = Queue[bytes]()
    disconnected = Event()
    disconnect_pipe = systray_hook.DisconnectNamedPipe

    def disconnect(handle: int) -> bool:
        result = disconnect_pipe(handle)
        disconnected.set()
        return result

    monkeypatch.setattr(hook, "_process_message", received.put)
    monkeypatch.setattr(systray_hook, "DisconnectNamedPipe", disconnect)
    client = _open_client()
    worker = Thread(target=hook.run, daemon=True)
    worker.start()
    try:
        assert WriteFile(client, b"first connection")
        assert received.get(timeout=5) == b"first connection"
        CloseHandle(client)
        client = None
        assert disconnected.wait(timeout=5)
        assert WaitNamedPipe(systray_hook.MESSAGE_PIPE_NAME, 5000)
        client = _open_client()
        assert WriteFile(client, b"second connection")
        assert received.get(timeout=5) == b"second connection"
    finally:
        hook.destroy()
        worker.join(timeout=5)
        if client is not None:
            CloseHandle(client)
    assert not worker.is_alive()


def test_mutex_creation_failure_leaves_no_handles(monkeypatch: pytest.MonkeyPatch) -> None:
    def create_mutex(attributes: int | None, initial_owner: bool, name: str) -> int:
        return 0

    closed: list[int] = []
    monkeypatch.setattr(systray_hook, "CreateMutex", create_mutex)
    monkeypatch.setattr(systray_hook, "CloseHandle", closed.append)
    hook = systray_hook.SystrayHook()
    hook.run()
    hook.destroy()
    assert closed == []


def test_pipe_creation_failure_closes_watchdog_mutex(monkeypatch: pytest.MonkeyPatch) -> None:
    def create_mutex(attributes: int | None, initial_owner: bool, name: str) -> int:
        return 123

    def create_named_pipe(
        name: str,
        open_mode: int,
        pipe_mode: int,
        max_instances: int,
        out_buffer_size: int,
        in_buffer_size: int,
        default_timeout: int,
        security_attributes: int | None,
    ) -> int | None:
        return INVALID_HANDLE_VALUE

    closed: list[int] = []
    monkeypatch.setattr(systray_hook, "CreateMutex", create_mutex)
    monkeypatch.setattr(systray_hook, "CreateNamedPipe", create_named_pipe)
    monkeypatch.setattr(systray_hook, "CloseHandle", closed.append)
    hook = systray_hook.SystrayHook()
    hook.run()
    hook.destroy()
    assert closed == [123]


def test_event_creation_failure_closes_pipe(hook: systray_hook.SystrayHook, monkeypatch: pytest.MonkeyPatch) -> None:
    def create_event(attributes: int | None, manual_reset: bool, initial_state: bool, name: str | None) -> int:
        return 0

    closed: list[int] = []

    def close_handle(handle: int) -> bool:
        closed.append(handle)
        return bool(CloseHandle(handle))

    monkeypatch.setattr(systray_hook, "CreateEvent", create_event)
    monkeypatch.setattr(systray_hook, "CloseHandle", close_handle)
    hook.run()
    assert len(closed) == 1
    # run() cannot restart after its pipe has been released.
    hook.run()
    assert len(closed) == 1
    hook.destroy()
    assert len(closed) == 2
    assert len(set(closed)) == 2


@pytest.mark.parametrize(("phase", "delay"), [("explorer", 1), ("injection", 5), ("disconnect", 3)])
def test_shutdown_interrupts_retry_delay(
    hook: systray_hook.SystrayHook,
    monkeypatch: pytest.MonkeyPatch,
    phase: Literal["explorer", "injection", "disconnect"],
    delay: int,
) -> None:
    retrying = Event()
    delays: list[float | None] = []
    stop_wait = hook._stop_event.wait

    def wait_for_retry(timeout: float | None = None) -> bool:
        delays.append(timeout)
        retrying.set()
        return stop_wait(timeout)

    def broken_connection(pipe: int, h_event: int) -> bool:
        raise ctypes.WinError(ERROR_BROKEN_PIPE)

    def failed_injection(dll_path: str, pid: int) -> int:
        return 0

    monkeypatch.setattr(hook._stop_event, "wait", wait_for_retry)
    if phase == "explorer":
        monkeypatch.setattr(systray_hook, "get_explorer_pid", lambda: None)
    elif phase == "injection":
        monkeypatch.setattr(systray_hook, "is_dll_loaded", _dll_not_loaded)
        monkeypatch.setattr(systray_hook, "_inject_via_hook", failed_injection)
    else:
        monkeypatch.setattr(hook, "_connect_pipe", broken_connection)

    worker = Thread(target=hook.run, daemon=True)
    worker.start()
    try:
        assert retrying.wait(timeout=5)
        hook.destroy()
        worker.join(timeout=0.5)
        assert not worker.is_alive()
        assert delays == [delay]
    finally:
        hook.destroy()
        worker.join(timeout=5)


def test_failed_connection_releases_hook_before_reinjecting(
    hook: systray_hook.SystrayHook, monkeypatch: pytest.MonkeyPatch
) -> None:
    injected: list[int] = []
    unhooked: list[int] = []

    def inject(dll_path: str, pid: int) -> int:
        assert unhooked == injected
        h_hook = 100 + len(injected)
        injected.append(h_hook)
        return h_hook

    def connect(pipe: int, h_event: int) -> bool:
        if len(injected) == 1:
            raise ctypes.WinError(ERROR_BROKEN_PIPE)
        hook.destroy()
        return False

    def skip_retry_delay(timeout: float | None = None) -> bool:
        return False

    monkeypatch.setattr(systray_hook, "is_dll_loaded", _dll_not_loaded)
    monkeypatch.setattr(systray_hook, "_inject_via_hook", inject)
    monkeypatch.setattr(systray_hook, "UnhookWindowsHookEx", unhooked.append)
    monkeypatch.setattr(hook, "_connect_pipe", connect)
    monkeypatch.setattr(hook._stop_event, "wait", skip_retry_delay)
    hook.run()
    assert injected == [100, 101]
    assert unhooked == injected


def test_shutdown_during_injection_releases_new_hook(
    hook: systray_hook.SystrayHook, monkeypatch: pytest.MonkeyPatch
) -> None:
    injecting = Event()
    finish_injection = Event()
    unhooked: list[int] = []
    connections: list[int] = []

    def inject(dll_path: str, pid: int) -> int:
        injecting.set()
        assert finish_injection.wait(timeout=5)
        return 123

    def connect(pipe: int, h_event: int) -> bool:
        connections.append(pipe)
        return False

    monkeypatch.setattr(systray_hook, "is_dll_loaded", _dll_not_loaded)
    monkeypatch.setattr(systray_hook, "_inject_via_hook", inject)
    monkeypatch.setattr(systray_hook, "UnhookWindowsHookEx", unhooked.append)
    monkeypatch.setattr(hook, "_connect_pipe", connect)
    worker = Thread(target=hook.run, daemon=True)
    worker.start()
    try:
        assert injecting.wait(timeout=5)
        hook.destroy()
    finally:
        finish_injection.set()
        hook.destroy()
        worker.join(timeout=5)
    assert not worker.is_alive()
    assert unhooked == [123]
    assert connections == []
