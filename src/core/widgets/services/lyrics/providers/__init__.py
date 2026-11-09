from .base import LyricsProvider
from .binimum import BinimumProvider
from .kugou import KugouProvider
from .lrclib import LrcLibProvider
from .lrcred import LrcRedProvider
from .netease import NetEaseProvider

__all__ = [
    "LyricsProvider",
    "LrcLibProvider",
    "LrcRedProvider",
    "NetEaseProvider",
    "BinimumProvider",
    "KugouProvider",
]
