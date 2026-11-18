from collections.abc import Callable
from pathlib import Path

import pytest
from PyQt6.QtGui import QGuiApplication

from core.services.apps import watcher as watcher_module
from core.services.apps.watcher import AppChanges
from tests.support.qt import wait


def until(condition: Callable[[], bool]) -> bool:
    for _ in range(300):
        if condition():
            return True
        wait(10)
    return condition()


def test_one_change_comes_after_an_install_and_its_new_folder_is_watched(
    qapp: QGuiApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    programs = tmp_path / "Programs"
    (programs / "Tools").mkdir(parents=True)
    monkeypatch.setattr(watcher_module, "START_MENU_FOLDERS", (str(programs),))
    monkeypatch.setattr(watcher_module, "SETTLE_MS", 100)
    watch = AppChanges()
    changes: list[None] = []
    watch.changed.connect(lambda: changes.append(None))
    watcher = watch._watcher  # pyright: ignore[reportPrivateUsage]
    assert until(lambda: len(watcher.directories()) == 2)

    # An install adds its shortcuts and a folder of its own, in a burst
    (programs / "App.lnk").write_text("")
    (programs / "App").mkdir()
    (programs / "App" / "Help.lnk").write_text("")
    (programs / "Tools" / "App Tool.lnk").write_text("")
    assert until(lambda: len(changes) == 1)
    wait(300)
    assert len(changes) == 1

    # The folder it made is watched from then on
    assert until(lambda: len(watcher.directories()) == 3)
    (programs / "App" / "Help.lnk").unlink()
    assert until(lambda: len(changes) == 2)
    watch.stop()
