import os
from pathlib import Path

from PyQt6.QtCore import QUrl


def path_key(path: Path | str) -> str:
    return os.path.normcase(os.path.abspath(path))


class Revisions:
    """QML caches compiled files by URL and keeps any file still in use, so every new version of a file
    is loaded under its own revision URL. Bars use the accepted revision, a check uses the next one."""

    def __init__(self) -> None:
        self._accepted: dict[str, int] = {}
        self._latest: dict[str, int] = {}

    @staticmethod
    def _url(path: Path, number: int) -> QUrl:
        url = QUrl.fromLocalFile(str(path))
        if number:
            url.setQuery(f"revision={number}")
        return url

    def url(self, path: Path) -> QUrl:
        return self._url(path, self._accepted.get(path_key(path), 0))

    def next_url(self, path: Path) -> QUrl:
        key = path_key(path)
        self._latest[key] = self._latest.get(key, 0) + 1
        return self._url(path, self._latest[key])

    def accept(self, path: Path) -> None:
        key = path_key(path)
        self._accepted[key] = self._latest.get(key, 0)

    def bump(self, path: Path) -> None:
        self.next_url(path)
        self.accept(path)
