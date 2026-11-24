import winsound
from pathlib import Path

import pytest
from PyQt6.QtCore import QUrl

from core.utils import notifier
from core.utils.notifier import DEFAULT_SOUND, Notifier

FLAGS = winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT


@pytest.fixture
def played(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str | None, int]]:
    calls: list[tuple[str | None, int]] = []

    def play(sound: str | None, flags: int) -> None:
        calls.append((sound, flags))

    monkeypatch.setattr(notifier.winsound, "PlaySound", play)
    return calls


def test_a_sound_is_played_from_a_path_a_file_url_or_the_default(tmp_path: Path, played: list[tuple[str | None, int]]):
    sound = tmp_path / "ding.wav"
    sound.write_bytes(b"")
    Notifier().playSound(str(sound))
    Notifier().playSound(QUrl.fromLocalFile(str(sound)).toString())
    Notifier().playSound()
    assert played == [
        (str(sound), FLAGS),
        (QUrl.fromLocalFile(str(sound)).toLocalFile(), FLAGS),
        (DEFAULT_SOUND, FLAGS),
    ]


def test_a_missing_sound_is_not_played(tmp_path: Path, played: list[tuple[str | None, int]]):
    Notifier().playSound(str(tmp_path / "missing.wav"))
    assert played == []
