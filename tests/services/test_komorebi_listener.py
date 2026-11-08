# pyright: reportPrivateUsage=false

import json
import logging
import subprocess
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication

from core.services.komorebi import event_listener
from core.services.komorebi.client import KomorebiClient
from core.services.komorebi.event_listener import KOMOREBI_PIPE_BUFF_SIZE, KomorebiEventListener
from core.utils.win32.bindings.kernel32 import CloseHandle, CreateFile, WriteFile
from core.utils.win32.constants import GENERIC_WRITE, INVALID_HANDLE_VALUE, OPEN_EXISTING

FIRST_STATE: dict[str, Any] = {"monitors": {"elements": [], "focused": 0}}


class Komorebi:
    """Plays komorebi's side of the pipe: komorebic subscribe has it open the pipe, and each notification is written
    as komorebi writes it, the JSON and then its line break."""

    def __init__(self) -> None:
        self.connects = True
        self.subscribed = threading.Event()
        self._pipe = 0

    def subscribe(self, pipe_name: str) -> tuple[bytes, subprocess.CompletedProcess[bytes]]:
        if self.connects:
            self._pipe = CreateFile(rf"\\.\pipe\{pipe_name}", GENERIC_WRITE, 0, None, OPEN_EXISTING, 0, None)
            assert self._pipe != INVALID_HANDLE_VALUE
        self.subscribed.set()
        return b"", subprocess.CompletedProcess([], 0, b"", b"")

    def notify(self, state: dict[str, Any]) -> None:
        WriteFile(self._pipe, json.dumps({"event": {"type": "FocusChange", "content": []}, "state": state}).encode())
        WriteFile(self._pipe, b"\n")

    def quit(self) -> None:
        CloseHandle(self._pipe)
        self._pipe = 0


@pytest.fixture
def komorebi(monkeypatch: pytest.MonkeyPatch) -> Iterator[Komorebi]:
    fake = Komorebi()

    def running(_name: str) -> bool:
        return True

    def query_state(_client: KomorebiClient) -> dict[str, Any]:
        return FIRST_STATE

    monkeypatch.setattr(event_listener, "is_process_running", running)
    monkeypatch.setattr(KomorebiClient, "wait_until_subscribed_to_pipe", fake.subscribe)
    monkeypatch.setattr(KomorebiClient, "query_state", query_state)
    yield fake
    if fake._pipe:
        fake.quit()


type Listen = Callable[..., tuple[KomorebiEventListener, list[Any]]]


@pytest.fixture
def listen(qapp: QGuiApplication) -> Iterator[Listen]:
    made: list[KomorebiEventListener] = []

    def start(buffer_size: int = KOMOREBI_PIPE_BUFF_SIZE) -> tuple[KomorebiEventListener, list[Any]]:
        listener = KomorebiEventListener(buffer_size=buffer_size)
        received: list[Any] = []
        listener.state_changed.connect(received.append, Qt.ConnectionType.DirectConnection)
        made.append(listener)
        listener.start()
        return listener, received

    yield start
    for listener in made:
        listener.stop()
        listener.wait(2000)


def until(condition: Callable[[], bool], timeout: float = 2) -> bool:
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            return False
        time.sleep(0.005)
    return True


def test_each_notification_is_read_whole_even_when_longer_than_the_buffer(komorebi: Komorebi, listen: Listen):
    _, received = listen(buffer_size=1024)
    assert until(lambda: received == [FIRST_STATE])

    long_state = {"monitors": {"elements": [{"name": "x" * 5000}], "focused": 0}}
    komorebi.notify({"monitors": {"elements": [], "focused": 1}})
    komorebi.notify(long_state)

    assert until(lambda: len(received) == 3)
    assert received[1:] == [{"monitors": {"elements": [], "focused": 1}}, long_state]


def test_komorebi_quitting_is_reported_without_a_warning(
    komorebi: Komorebi, listen: Listen, caplog: pytest.LogCaptureFixture
):
    listener, received = listen()
    assert until(lambda: received == [FIRST_STATE])

    komorebi.quit()

    assert until(lambda: received == [FIRST_STATE, None])
    listener.stop()
    assert listener.wait(1000)
    assert not [record.message for record in caplog.records if record.levelno >= logging.WARNING]


def test_stop_ends_the_wait_for_the_next_notification(komorebi: Komorebi, listen: Listen):
    listener, received = listen()
    assert until(lambda: received == [FIRST_STATE])

    listener.stop()

    assert listener.wait(1000)
    assert received == [FIRST_STATE, None]


def test_stop_ends_the_wait_for_komorebi_to_open_the_pipe(komorebi: Komorebi, listen: Listen):
    komorebi.connects = False
    listener, received = listen()
    assert until(komorebi.subscribed.is_set)
    time.sleep(0.05)

    listener.stop()

    assert listener.wait(1000)
    assert received == [None]
