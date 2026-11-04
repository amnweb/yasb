from collections.abc import Hashable
from typing import Any, ClassVar, Self, cast

from PyQt6.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot


class Feed[K: Hashable](QObject):
    """Something fetched in the background and shared by every widget asking for it with the same key.

    A subclass keeps its own _feeds, fetches in fetch() and emits changed; the feed goes away with its last user. K is
    the key's type, such as an interval in ms.
    """

    changed = pyqtSignal()

    _feeds: ClassVar[dict[Any, Any]] = {}

    def __init__(self, key: K) -> None:
        super().__init__()
        self.key = key
        self.loading = False
        self.error = ""
        self._users = 0
        # Answers to an earlier request are dropped
        self._request: int = 0
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.fetch)

    @classmethod
    def join(cls, key: K, user: QObject) -> Self:
        feed = cls._feeds.get(key)
        if feed is None:
            feed = cls._feeds[key] = cls(key)
        feed = cast(Self, feed)
        feed._users += 1
        user.destroyed.connect(feed._user_destroyed)
        return feed

    def leave(self, user: QObject) -> None:
        user.destroyed.disconnect(self._user_destroyed)
        self._user_destroyed()

    def _user_destroyed(self) -> None:
        self._users -= 1
        if self._users > 0:
            return
        if type(self)._feeds.get(self.key) is self:
            del type(self)._feeds[self.key]
        self._request += 1
        self._timer.stop()
        self.deleteLater()

    @pyqtSlot()
    def fetch(self) -> None:
        raise NotImplementedError
