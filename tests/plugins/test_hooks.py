import asyncio
import logging
import threading
from collections.abc import Callable
from pathlib import Path

import pytest

import main
from tests.plugins.helpers import PLUGIN_ID, boom_module


def _fail() -> None:
    raise RuntimeError("core")


def _run_thread(target: Callable[[], object], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(threading, "excepthook", main.thread_exception_hook)
    thread = threading.Thread(target=target, name="worker")
    thread.start()
    thread.join()


def test_thread_exception_in_plugin_names_the_plugin(
    plugin_dir: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    boom = boom_module(plugin_dir)

    with caplog.at_level(logging.ERROR):
        _run_thread(boom.explode, monkeypatch)

    assert f'Unhandled exception in plugin "{PLUGIN_ID}" (thread worker)' in caplog.text


def test_other_thread_exceptions_keep_the_default_hook(
    plugin_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    boom_module(plugin_dir)

    _run_thread(_fail, monkeypatch)

    assert "Exception in thread worker" in capsys.readouterr().err


def _task_failure(error: BaseException) -> dict[str, object]:
    return {"message": "Task exception was never retrieved", "exception": error}


def test_async_exception_in_plugin_names_the_plugin(plugin_dir: Path, caplog: pytest.LogCaptureFixture):
    boom = boom_module(plugin_dir)
    with pytest.raises(RuntimeError) as raised:
        boom.explode()
    loop = asyncio.new_event_loop()

    try:
        with caplog.at_level(logging.ERROR):
            main.asyncio_exception_handler(loop, _task_failure(raised.value))
    finally:
        loop.close()

    assert f'Unhandled exception in plugin "{PLUGIN_ID}": Task exception was never retrieved' in caplog.text


def test_other_async_exceptions_keep_the_default_handler(plugin_dir: Path, caplog: pytest.LogCaptureFixture):
    boom_module(plugin_dir)
    with pytest.raises(RuntimeError) as raised:
        _fail()
    loop = asyncio.new_event_loop()

    try:
        with caplog.at_level(logging.ERROR):
            main.asyncio_exception_handler(loop, _task_failure(raised.value))
    finally:
        loop.close()

    assert "Task exception was never retrieved" in caplog.text
    assert "in plugin" not in caplog.text
