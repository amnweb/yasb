from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from typing import TYPE_CHECKING

from .kanji_data import KANJI_READINGS

if TYPE_CHECKING:
    from .models import Lyrics


# Script Detection


def has_japanese(text: str) -> bool:
    return bool(re.search(r"[\u3040-\u30ff]", text))


def has_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff\u3400-\u4dbf]", text))


def has_hangul(text: str) -> bool:
    return bool(re.search(r"[\uac00-\ud7af\u1100-\u11ff\u3130-\u318f]", text))


def has_cyrillic(text: str) -> bool:
    return bool(re.search(r"[\u0400-\u052f\u2de0-\u2dff\ua640-\ua69f]", text))


def has_devanagari(text: str) -> bool:
    return bool(re.search(r"[\u0900-\u097f]", text))


def has_sinhala(text: str) -> bool:
    return bool(re.search(r"[\u0d80-\u0dff]", text))


def has_indic(text: str) -> bool:
    return bool(re.search(r"[\u0900-\u0d7f]", text))


# 1. Korean Hangul (Revised Romanization of Korean) - Pure Python, 0 dependencies

_HANGUL_CHOSEONG: tuple[str, ...] = (
    "g",
    "kk",
    "n",
    "d",
    "tt",
    "r",
    "m",
    "b",
    "pp",
    "s",
    "ss",
    "",
    "j",
    "jj",
    "ch",
    "k",
    "t",
    "p",
    "h",
)
_HANGUL_JUNGSEONG: tuple[str, ...] = (
    "a",
    "ae",
    "ya",
    "yae",
    "eo",
    "e",
    "yeo",
    "ye",
    "o",
    "wa",
    "wae",
    "oe",
    "yo",
    "u",
    "wo",
    "we",
    "wi",
    "yu",
    "eu",
    "ui",
    "i",
)
_HANGUL_JONGSEONG: tuple[str, ...] = (
    "",
    "k",
    "k",
    "ks",
    "n",
    "nj",
    "nh",
    "t",
    "l",
    "lg",
    "lm",
    "lb",
    "ls",
    "lt",
    "lp",
    "lh",
    "m",
    "p",
    "ps",
    "t",
    "t",
    "ng",
    "t",
    "t",
    "k",
    "t",
    "p",
    "h",
)


_LIAISON_MAP: dict[int, tuple[str, str]] = {
    1: ("", "g"),
    2: ("", "kk"),
    3: ("k", "s"),
    4: ("", "n"),
    5: ("n", "j"),
    6: ("n", ""),
    7: ("", "d"),
    8: ("", "r"),
    9: ("l", "g"),
    10: ("l", "m"),
    11: ("l", "b"),
    12: ("l", "s"),
    13: ("l", "t"),
    14: ("l", "p"),
    15: ("l", ""),
    16: ("", "m"),
    17: ("", "b"),
    18: ("p", "s"),
    19: ("", "s"),
    20: ("", "ss"),
    21: ("ng", ""),
    22: ("", "j"),
    23: ("", "ch"),
    24: ("", "k"),
    25: ("", "t"),
    26: ("", "p"),
    27: ("", "h"),
}


class _HangulBlock:
    __slots__ = ("char", "cho", "is_hangul", "jong", "jung")

    def __init__(
        self,
        is_hangul: bool,
        cho: int | str = 0,
        jung: int = 0,
        jong: int | str = 0,
        char: str = "",
    ) -> None:
        self.is_hangul = is_hangul
        self.cho = cho
        self.jung = jung
        self.jong = jong
        self.char = char


def romanize_korean(text: str) -> str | None:
    """Romanize Korean Hangul into syllable-spaced Revised Romanization with liaison rules."""
    blocks: list[_HangulBlock] = []
    has_hangul = False
    for ch in text:
        code = ord(ch)
        if 0xAC00 <= code <= 0xD7A3:
            s_idx = code - 0xAC00
            cho = s_idx // 588
            jung = (s_idx % 588) // 28
            jong = s_idx % 28
            blocks.append(_HangulBlock(True, cho=cho, jung=jung, jong=jong))
            has_hangul = True
        else:
            blocks.append(_HangulBlock(False, char=ch))

    if not has_hangul:
        return None

    n = len(blocks)
    for i in range(n - 1):
        curr = blocks[i]
        nxt = blocks[i + 1]
        if curr.is_hangul and nxt.is_hangul:
            jong_i = curr.jong
            cho_next = nxt.cho
            if cho_next == 11 and isinstance(jong_i, int) and jong_i in _LIAISON_MAP:
                rem_jong, carry_cho = _LIAISON_MAP[jong_i]
                curr.jong = rem_jong
                nxt.cho = carry_cho

    out: list[str] = []
    for i, b in enumerate(blocks):
        if b.is_hangul:
            cho_str = b.cho if isinstance(b.cho, str) else _HANGUL_CHOSEONG[b.cho]
            jung_str = _HANGUL_JUNGSEONG[b.jung]
            jong_str = b.jong if isinstance(b.jong, str) else _HANGUL_JONGSEONG[b.jong]
            syllable_rom = cho_str + jung_str + jong_str
            if out and out[-1] != " " and blocks[i - 1].is_hangul:
                out.append(" ")
            out.append(syllable_rom)
        else:
            out.append(b.char)

    trans = "".join(out).strip()
    return trans if trans and trans.lower() != text.strip().lower() else None


# 2. Hindi / Devanagari - Pure Python, 0 dependencies

_DEVANAGARI_VOWELS: dict[str, str] = {
    "\u0905": "a",
    "\u0906": "aa",
    "\u0907": "i",
    "\u0908": "ee",
    "\u0909": "u",
    "\u090a": "oo",
    "\u090b": "ri",
    "\u090f": "e",
    "\u0910": "ai",
    "\u0913": "o",
    "\u0914": "au",
}
_DEVANAGARI_MATRAS: dict[str, str] = {
    "\u093e": "aa",
    "\u093f": "i",
    "\u0940": "ee",
    "\u0941": "u",
    "\u0942": "oo",
    "\u0943": "ri",
    "\u0947": "e",
    "\u0948": "ai",
    "\u094b": "o",
    "\u094c": "au",
}
_DEVANAGARI_CONSONANTS: dict[str, str] = {
    "\u0915": "k",
    "\u0916": "kh",
    "\u0917": "g",
    "\u0918": "gh",
    "\u0919": "ng",
    "\u091a": "ch",
    "\u091b": "chh",
    "\u091c": "j",
    "\u091d": "jh",
    "\u091e": "ny",
    "\u091f": "t",
    "\u0920": "th",
    "\u0921": "d",
    "\u0922": "dh",
    "\u0923": "n",
    "\u0924": "t",
    "\u0925": "th",
    "\u0926": "d",
    "\u0927": "dh",
    "\u0928": "n",
    "\u092a": "p",
    "\u092b": "ph",
    "\u092c": "b",
    "\u092d": "bh",
    "\u092e": "m",
    "\u092f": "y",
    "\u0930": "r",
    "\u0932": "l",
    "\u0935": "v",
    "\u0936": "sh",
    "\u0937": "sh",
    "\u0938": "s",
    "\u0939": "h",
    "\u0958": "q",
    "\u0959": "kh",
    "\u095a": "gh",
    "\u095b": "z",
    "\u095c": "r",
    "\u095d": "rh",
    "\u095e": "f",
}
_DEVANAGARI_VIRAMA = "\u094d"
_DEVANAGARI_ANUSVARA = "\u0902"
_DEVANAGARI_CHANDRABINDU = "\u0901"
_DEVANAGARI_VISARGA = "\u0903"


def romanize_devanagari(text: str) -> str | None:
    """Romanize Hindi/Devanagari text in pure Python."""
    # Common Hindi name/title convention: सिंह is standardly Anglicized as 'singh'
    processed = text.replace("सिंह", "singh").replace("सिँह", "singh")
    res: list[str] = []
    n = len(processed)
    i = 0
    has_dev = False

    while i < n:
        ch = processed[i]
        if ch in _DEVANAGARI_CONSONANTS:
            has_dev = True
            base = _DEVANAGARI_CONSONANTS[ch]
            i += 1
            if i < n and text[i] == _DEVANAGARI_VIRAMA:
                res.append(base)
                i += 1
            elif i < n and text[i] in _DEVANAGARI_MATRAS:
                res.append(base + _DEVANAGARI_MATRAS[text[i]])
                i += 1
            elif i < n and text[i] in (_DEVANAGARI_ANUSVARA, _DEVANAGARI_CHANDRABINDU):
                res.append(base + "an")
                i += 1
            else:
                is_word_end = i == n or text[i] in " \t\r\n.,!?;:'\"-()[]"
                res.append(base if is_word_end else base + "a")
        elif ch in _DEVANAGARI_VOWELS:
            has_dev = True
            res.append(_DEVANAGARI_VOWELS[ch])
            i += 1
        elif ch in (_DEVANAGARI_ANUSVARA, _DEVANAGARI_CHANDRABINDU):
            has_dev = True
            res.append("n")
            i += 1
        elif ch == _DEVANAGARI_VISARGA:
            has_dev = True
            res.append("h")
            i += 1
        else:
            res.append(ch)
            i += 1

    if not has_dev:
        return None
    trans = "".join(res).strip()
    return trans if trans and trans.lower() != text.strip().lower() else None


# 3. Sinhala - Pure Python, 0 dependencies

_SINHALA_VOWELS: dict[str, str] = {
    "\u0d85": "a",
    "\u0d86": "aa",
    "\u0d87": "ae",
    "\u0d88": "aae",
    "\u0d89": "i",
    "\u0d8a": "ii",
    "\u0d8b": "u",
    "\u0d8c": "uu",
    "\u0d8d": "ri",
    "\u0d8e": "rii",
    "\u0d8f": "e",
    "\u0d90": "ee",
    "\u0d91": "e",
    "\u0d92": "ee",
    "\u0d93": "ai",
    "\u0d94": "o",
    "\u0d95": "oo",
    "\u0d96": "au",
}
_SINHALA_PILLAM: dict[str, str] = {
    "\u0dcf": "aa",
    "\u0dd0": "ae",
    "\u0dd1": "aae",
    "\u0dd2": "i",
    "\u0dd3": "ii",
    "\u0dd4": "u",
    "\u0dd6": "uu",
    "\u0dd8": "ri",
    "\u0dd9": "e",
    "\u0dda": "ee",
    "\u0ddb": "ai",
    "\u0ddc": "o",
    "\u0ddd": "oo",
    "\u0dde": "au",
    "\u0ddf": "au",
}
_SINHALA_CONSONANTS: dict[str, str] = {
    "\u0d9a": "k",
    "\u0d9b": "kh",
    "\u0d9c": "g",
    "\u0d9d": "gh",
    "\u0d9e": "ng",
    "\u0d9f": "ng",
    "\u0da0": "ch",
    "\u0da1": "chh",
    "\u0da2": "j",
    "\u0da3": "jh",
    "\u0da4": "ny",
    "\u0da5": "gn",
    "\u0da6": "ndj",
    "\u0da7": "t",
    "\u0da8": "th",
    "\u0da9": "d",
    "\u0daa": "dh",
    "\u0dab": "n",
    "\u0dac": "nd",
    "\u0dad": "th",
    "\u0dae": "thh",
    "\u0daf": "d",
    "\u0db0": "dh",
    "\u0db1": "n",
    "\u0db3": "nd",
    "\u0db4": "p",
    "\u0db5": "ph",
    "\u0db6": "b",
    "\u0db7": "bh",
    "\u0db8": "m",
    "\u0db9": "mb",
    "\u0dba": "y",
    "\u0dbb": "r",
    "\u0dbd": "l",
    "\u0dc0": "v",
    "\u0dc1": "sh",
    "\u0dc2": "sh",
    "\u0dc3": "s",
    "\u0dc4": "h",
    "\u0dc5": "l",
    "\u0dc6": "f",
}
_SINHALA_HAL = "\u0dca"
_SINHALA_ANUSVARA = "\u0d82"
_SINHALA_VISARGA = "\u0d83"


def romanize_sinhala(text: str) -> str | None:
    """Romanize Sinhala script into Singlish/English transliteration in pure Python."""
    res: list[str] = []
    n = len(text)
    i = 0
    has_sin = False

    while i < n:
        ch = text[i]
        if ch in _SINHALA_CONSONANTS:
            has_sin = True
            base = _SINHALA_CONSONANTS[ch]
            i += 1
            if i < n and text[i] == _SINHALA_HAL:
                res.append(base)
                i += 1
            elif i < n and text[i] in _SINHALA_PILLAM:
                res.append(base + _SINHALA_PILLAM[text[i]])
                i += 1
            elif i < n and text[i] == _SINHALA_ANUSVARA:
                res.append(base + "an")
                i += 1
            else:
                res.append(base + "a")
        elif ch in _SINHALA_VOWELS:
            has_sin = True
            res.append(_SINHALA_VOWELS[ch])
            i += 1
        elif ch == _SINHALA_ANUSVARA:
            has_sin = True
            res.append("n")
            i += 1
        elif ch == _SINHALA_VISARGA:
            has_sin = True
            res.append("h")
            i += 1
        else:
            res.append(ch)
            i += 1

    if not has_sin:
        return None
    trans = "".join(res).strip()
    return trans if trans and trans.lower() != text.strip().lower() else None


# 4. Japanese (Kana & Kanji) - Pure Python, 0 dependencies

_KANA_TO_ROMAJI: dict[str, str] = {
    # Digraphs
    "きゃ": "kya",
    "きゅ": "kyu",
    "きょ": "kyo",
    "しゃ": "sha",
    "しゅ": "shu",
    "しょ": "sho",
    "ちゃ": "cha",
    "ちゅ": "chu",
    "ちょ": "cho",
    "にゃ": "nya",
    "にゅ": "nyu",
    "にょ": "nyo",
    "ひゃ": "hya",
    "ひゅ": "hyu",
    "ひょ": "hyo",
    "みゃ": "mya",
    "みゅ": "myu",
    "みょ": "myo",
    "りゃ": "rya",
    "りゅ": "ryu",
    "りょ": "ryo",
    "ぎゃ": "gya",
    "ぎゅ": "gyu",
    "ぎょ": "gyo",
    "じゃ": "ja",
    "じゅ": "ju",
    "じょ": "jo",
    "びゃ": "bya",
    "びゅ": "byu",
    "びょ": "byo",
    "ぴゃ": "pya",
    "ぴゅ": "pyu",
    "ぴょ": "pyo",
    "キャ": "kya",
    "キュ": "kyu",
    "キョ": "kyo",
    "シャ": "sha",
    "シュ": "shu",
    "ショ": "sho",
    "チャ": "cha",
    "チュ": "chu",
    "チョ": "cho",
    "ニャ": "nya",
    "ニュ": "nyu",
    "ニョ": "nyo",
    "ヒャ": "hya",
    "ヒュ": "hyu",
    "ヒョ": "hyo",
    "ミャ": "mya",
    "ミュ": "myu",
    "ミョ": "myo",
    "リャ": "rya",
    "リュ": "ryu",
    "リョ": "ryo",
    "ギャ": "gya",
    "ギュ": "gyu",
    "ギョ": "gyo",
    "ジャ": "ja",
    "ジュ": "ju",
    "ジョ": "jo",
    "ビャ": "bya",
    "ビュ": "byu",
    "ビョ": "byo",
    "ピャ": "pya",
    "ピュ": "pyu",
    "ピョ": "pyo",
    "ティ": "ti",
    "ディ": "di",
    "ファ": "fa",
    "フィ": "fi",
    "フェ": "fe",
    "フォ": "fo",
    # Single Hiragana
    "あ": "a",
    "い": "i",
    "う": "u",
    "え": "e",
    "お": "o",
    "か": "ka",
    "き": "ki",
    "く": "ku",
    "け": "ke",
    "こ": "ko",
    "さ": "sa",
    "し": "shi",
    "す": "su",
    "せ": "se",
    "そ": "so",
    "た": "ta",
    "ち": "chi",
    "つ": "tsu",
    "て": "te",
    "と": "to",
    "な": "na",
    "に": "ni",
    "ぬ": "nu",
    "ね": "ne",
    "の": "no",
    "は": "ha",
    "ひ": "hi",
    "ふ": "fu",
    "へ": "he",
    "ほ": "ho",
    "ま": "ma",
    "み": "mi",
    "む": "mu",
    "め": "me",
    "も": "mo",
    "や": "ya",
    "ゆ": "yu",
    "よ": "yo",
    "ら": "ra",
    "り": "ri",
    "る": "ru",
    "れ": "re",
    "ろ": "ro",
    "わ": "wa",
    "を": "wo",
    "ん": "n",
    "が": "ga",
    "ぎ": "gi",
    "ぐ": "gu",
    "げ": "ge",
    "ご": "go",
    "ざ": "za",
    "じ": "ji",
    "ず": "zu",
    "ぜ": "ze",
    "ぞ": "zo",
    "だ": "da",
    "ぢ": "ji",
    "づ": "zu",
    "で": "de",
    "ど": "do",
    "ば": "ba",
    "び": "bi",
    "ぶ": "bu",
    "べ": "be",
    "ぼ": "bo",
    "ぱ": "pa",
    "ぴ": "pi",
    "ぷ": "pu",
    "ぺ": "pe",
    "ぽ": "po",
    # Single Katakana
    "ア": "a",
    "イ": "i",
    "ウ": "u",
    "エ": "e",
    "オ": "o",
    "カ": "ka",
    "キ": "ki",
    "ク": "ku",
    "ケ": "ke",
    "コ": "ko",
    "サ": "sa",
    "シ": "shi",
    "ス": "su",
    "セ": "se",
    "ソ": "so",
    "タ": "ta",
    "チ": "chi",
    "ツ": "tsu",
    "テ": "te",
    "ト": "to",
    "ナ": "na",
    "ニ": "ni",
    "ヌ": "nu",
    "ネ": "ne",
    "ノ": "no",
    "ハ": "ha",
    "ヒ": "hi",
    "フ": "fu",
    "ヘ": "he",
    "ホ": "ho",
    "マ": "ma",
    "ミ": "mi",
    "ム": "mu",
    "メ": "me",
    "モ": "mo",
    "ヤ": "ya",
    "ユ": "yu",
    "ヨ": "yo",
    "ラ": "ra",
    "リ": "ri",
    "ル": "ru",
    "レ": "re",
    "ロ": "ro",
    "ワ": "wa",
    "ヲ": "wo",
    "ン": "n",
    "ガ": "ga",
    "ギ": "gi",
    "グ": "gu",
    "ゲ": "ge",
    "ゴ": "go",
    "ザ": "za",
    "ジ": "ji",
    "ズ": "zu",
    "ゼ": "ze",
    "ゾ": "zo",
    "ダ": "da",
    "ヂ": "ji",
    "ヅ": "zu",
    "デ": "de",
    "ド": "do",
    "バ": "ba",
    "ビ": "bi",
    "ブ": "bu",
    "ベ": "be",
    "ボ": "bo",
    "パ": "pa",
    "ピ": "pi",
    "プ": "pu",
    "ペ": "pe",
    "ポ": "po",
    "ー": "-",
}


def _kana_to_romaji(text: str) -> str:
    res: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        if i + 1 < n and text[i : i + 2] in _KANA_TO_ROMAJI:
            res.append(_KANA_TO_ROMAJI[text[i : i + 2]])
            i += 2
        elif text[i] in _KANA_TO_ROMAJI:
            res.append(_KANA_TO_ROMAJI[text[i]])
            i += 1
        elif text[i] in ("っ", "ッ"):
            if i + 1 < n:
                nxt = _kana_to_romaji(text[i + 1 :])
                if nxt:
                    res.append(nxt[0])
            i += 1
        else:
            res.append(text[i])
            i += 1
    return "".join(res)


_JAPANESE_PHRASE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("瞬いて", " またたいて "),
    ("瞬く", " またたく "),
    ("瞬き", " またたき "),
    ("燃え尽き", " 燃えつき "),
    ("尽きた", " つきた "),
    ("尽きて", " つきて "),
    ("尽きる", " つきる "),
    ("尽き", " つき "),
    ("燻った", " くすぶった "),
    ("燻って", " くすぶって "),
    ("燻る", " くすぶる "),
    ("燻り", " くすぶり "),
    ("燻っ", " くすぶっ "),
    ("蹴飛ばされ", " けとばされ "),
    ("蹴飛ばす", " けとばす "),
    ("蹴飛ば", " けとば "),
    ("塞がって", " ふさがって "),
    ("塞がっ", " ふさがっ "),
    ("成り下がっ", " なりさがっ "),
    ("成り下がり", " なりさがり "),
    ("成り下がる", " なりさがる "),
    ("成り損ね", " なりそこね "),
    ("石ころ", " いしころ "),
    ("何にも", " なんにも "),
    ("這いつくばっ", " はいつくばっ "),
    ("立ち上がれ", " たちあがれ "),
    ("見捨てられ", " みすてられ "),
    ("どこへ", " どこ へ "),
    ("残った", " のこった "),
    ("残って", " のこって "),
    ("間違った", " まちがった "),
    ("間違って", " まちがって "),
    ("光った", " ひかった "),
    ("光って", " ひかって "),
    ("積もった", " つもった "),
    ("積もって", " つもって "),
    ("パッと", " ぱっと "),
    ("散った", " ちった "),
    ("散って", " ちって "),
    ("出会った", " であった "),
    ("出会って", " であって "),
    ("誓った", " ちかった "),
    ("誓って", " ちかって "),
    ("笑った", " わらった "),
    ("笑って", " わらって "),
    ("終わった", " おわった "),
    ("終わって", " おわって "),
    ("失った", " うしなった "),
    ("失って", " うしなって "),
    ("奪った", " うばった "),
    ("奪って", " うばって "),
    ("願った", " ねがった "),
    ("願って", " ねがって "),
    ("祈った", " いのった "),
    ("祈って", " いのって "),
    ("迷った", " まよった "),
    ("迷って", " まよって "),
    ("止まった", " とまった "),
    ("止まって", " とまって "),
    ("始まった", " はじまった "),
    ("始まって", " はじまって "),
    ("変わった", " かわった "),
    ("変わって", " かわって "),
    ("戻った", " もどった "),
    ("戻って", " もどって "),
    ("向かった", " むかった "),
    ("向かって", " むかって "),
    ("刺さった", " ささった "),
    ("刺さって", " ささって "),
    ("触った", " さわった "),
    ("触って", " さわって "),
    ("鳴った", " なった "),
    ("鳴って", " なって "),
    ("黙った", " だまった "),
    ("黙って", " だまって "),
    ("寄り添った", " よりそった "),
    ("寄り添って", " よりそって "),
    ("巡り会った", " めぐりあった "),
    ("巡り会って", " めぐりあって "),
)


def romanize_japanese(text: str) -> str | None:
    """Romanize Japanese (Kana and Kanji) using the built-in pure-Python engine."""
    trimmed = unicodedata.normalize("NFKC", text).strip()
    if not trimmed:
        return None

    # Pre-normalization of known compound verbs, irregular okurigana, and lyric phrases
    t = trimmed
    for src, dst in _JAPANESE_PHRASE_REPLACEMENTS:
        t = t.replace(src, dst)
    t = re.sub(r" +", " ", t).strip()

    # Built-in pure-Python Kana + Kanji engine
    res: list[str] = []
    i = 0
    n = len(t)
    has_jp = False

    while i < n:
        ch = t[i]
        if i + 1 < n and t[i : i + 2] in _KANA_TO_ROMAJI:
            res.append(_KANA_TO_ROMAJI[t[i : i + 2]])
            has_jp = True
            i += 2
        elif ch in _KANA_TO_ROMAJI:
            res.append(_KANA_TO_ROMAJI[ch])
            has_jp = True
            i += 1
        elif ch in ("っ", "ッ"):
            has_jp = True
            if i + 1 < n:
                nxt = _kana_to_romaji(t[i + 1 :])
                if nxt:
                    res.append(nxt[0])
            i += 1
        elif ch in KANJI_READINGS:
            has_jp = True
            res.append(KANJI_READINGS[ch])
            i += 1
        else:
            res.append(ch)
            i += 1

    if not has_jp:
        return None
    trans = "".join(res).strip()
    return trans if trans and trans.lower() != text.strip().lower() else None


# System Detection and Main Dispatcher


def detect_writing_system(texts: Sequence[str]) -> str | None:
    """Return the dominant non-Latin writing system, if any."""
    full_text = unicodedata.normalize("NFKC", "\n".join(t for t in texts if t))
    if not full_text:
        return None

    if has_japanese(full_text):
        return "japanese"

    if has_devanagari(full_text):
        return "hindi"

    if has_sinhala(full_text):
        return "sinhala"

    if has_hangul(full_text):
        return "korean"

    if has_cjk(full_text):
        return "chinese"

    if has_cyrillic(full_text):
        return "cyrillic"

    if has_indic(full_text):
        return "indic"

    for ch in full_text:
        if ch.isalpha() and ord(ch) > 0x024F:
            return "other"

    return None


def romanize_text(text: str, system: str | None = None) -> str | None:
    """Romanize text when it uses a supported non-Latin script."""
    trimmed = unicodedata.normalize("NFKC", text).strip()
    if not trimmed:
        return None

    if system == "korean" or (system is None and has_hangul(trimmed)):
        trans = romanize_korean(trimmed)
        if trans and trans.lower() != trimmed.lower():
            return trans

    if system == "japanese" or (system is None and has_japanese(trimmed)):
        trans = romanize_japanese(trimmed)
        if trans and trans.lower() != trimmed.lower():
            return trans

    if system in ("hindi", "devanagari") or (system is None and has_devanagari(trimmed)):
        trans = romanize_devanagari(trimmed)
        if trans and trans.lower() != trimmed.lower():
            return trans

    if system == "sinhala" or (system is None and has_sinhala(trimmed)):
        trans = romanize_sinhala(trimmed)
        if trans and trans.lower() != trimmed.lower():
            return trans

    if system == "chinese" or (system is None and has_cjk(trimmed)):
        # Fallback to Kanji reading if CJK character is in KANJI_READINGS
        trans_jp = romanize_japanese(trimmed)
        if trans_jp and trans_jp.lower() != trimmed.lower():
            return trans_jp

    return None


def romanize_lyrics(
    lyrics: Lyrics,
    force: bool = False,
    target_scripts: Sequence[str] | None = None,
) -> Lyrics:
    """Romanize the lines and secondary lanes in a lyrics object."""
    if not lyrics.lines:
        return lyrics

    all_texts: list[str] = []
    for line in lyrics.lines:
        all_texts.append(line.text)
        for lane in line.secondary:
            all_texts.append(lane.text)

    system = detect_writing_system(all_texts)
    if not system:
        return lyrics

    if target_scripts is not None and len(target_scripts) > 0:
        targets = [s.lower().strip() for s in target_scripts]
        is_targeted = (
            system in targets
            or "all" in targets
            or (system == "hindi" and "devanagari" in targets)
            or (system == "devanagari" and "hindi" in targets)
            or (system in ("hindi", "devanagari") and "indic" in targets)
            or (system == "sinhala" and "sinhalese" in targets)
        )
        if not is_targeted:
            return lyrics

    for line in lyrics.lines:
        if force or not line.romanized or has_cjk(line.romanized) or has_japanese(line.romanized):
            line.romanized = romanize_text(line.text, system=system)
        for lane in line.secondary:
            if force or not lane.romanized or has_cjk(lane.romanized) or has_japanese(lane.romanized):
                lane.romanized = romanize_text(lane.text, system=system)

    return lyrics
