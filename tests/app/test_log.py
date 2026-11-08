# pyright: reportPrivateUsage=false

import logging
from pathlib import Path
from typing import IO, Any

import pytest

from core.app import log


def test_the_colored_level_name_stays_out_of_the_record_the_next_handler_gets():
    record = logging.LogRecord("yasb", logging.INFO, "file.py", 1, "hello", None, None)
    colored = log.ColoredFormatter("%(levelname)s: %(message)s")
    assert colored.format(record) == colored.format(record) == f"{log.Format.green}    INFO{log.Format.reset}: hello"
    assert record.levelname == "INFO"


def test_crash_tracebacks_follow_the_log_file_when_it_rotates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    enabled: list[IO[str]] = []

    def enable(file: IO[str], **_options: Any) -> None:
        enabled.append(file)

    monkeypatch.setattr(log.faulthandler, "enable", enable)
    handler = log._LogFile(tmp_path / "yasb.log", maxBytes=10, backupCount=1, encoding="utf-8")
    handler.doRollover()
    assert enabled == [handler.stream]
    handler.close()
