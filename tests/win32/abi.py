# pyright: reportPrivateUsage=false

import ctypes
from _ctypes import CFuncPtr
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeGuard

POINTER_SIZE = ctypes.sizeof(ctypes.c_void_p)

_KIND_NAMES = {
    "v": "void",
    "i": "signed int",
    "u": "unsigned int",
    "f": "float",
    "p": "pointer",
    "s": "struct",
    "a": "array",
    "fn": "function",
    "?": "incomplete type",
}
_SIGNED_CODES = set("cbhilqv")
_FLOAT_CODES = set("fdg")
_POINTER_CODES = {"z": ("i", 1), "Z": ("u", 2), "X": ("u", 2), "P": None, "O": None}


@dataclass(frozen=True)
class Abi:
    kind: str
    size: int
    pointee: Abi | None = None

    @classmethod
    def from_json(cls, value: list[Any]) -> Abi:
        kind, size, *rest = value
        return cls(kind, size, cls.from_json(rest[0]) if rest else None)

    @property
    def is_integer(self) -> bool:
        return self.kind in ("i", "u")

    def __str__(self) -> str:
        text = f"{_KIND_NAMES.get(self.kind, self.kind)}({self.size})"
        if self.pointee is not None and self.kind in ("p", "a"):
            text += f" -> {self.pointee}"
        return text


def _simple(code: str, size: int) -> Abi:
    if code in _POINTER_CODES:
        target = _POINTER_CODES[code]
        return Abi("p", POINTER_SIZE, Abi(*target) if target else Abi("v", 0))
    if code in _FLOAT_CODES:
        return Abi("f", size)
    return Abi("i" if code in _SIGNED_CODES else "u", size)


def _is_pointer(ctype: type) -> TypeGuard[type[ctypes._Pointer[Any]]]:
    return issubclass(ctype, ctypes._Pointer)


def _is_array(ctype: type) -> TypeGuard[type[ctypes.Array[Any]]]:
    return issubclass(ctype, ctypes.Array)


def _is_simple(ctype: type) -> TypeGuard[type[ctypes._SimpleCData[Any]]]:
    return issubclass(ctype, ctypes._SimpleCData)


def _type_attr(ctype: type) -> Any:
    # typeshed declares _type_ per instance (and not at all on _SimpleCData); ctypes sets it on the class.
    return getattr(ctype, "_type_")


def of(ctype: object, *, argument: bool = False, opaque: Callable[[type], bool] | None = None) -> Abi:
    if ctype is None:
        return Abi("v", 0)
    if not isinstance(ctype, type):
        if callable(ctype):
            # ctypes reads the native return value as c_int when restype is a plain callable.
            return Abi("i", ctypes.sizeof(ctypes.c_int))
        raise TypeError(f"not a ctypes type: {ctype!r}")
    if _is_pointer(ctype):
        if opaque is not None and opaque(_type_attr(ctype)):
            return Abi("p", POINTER_SIZE, Abi("v", 0))
        return Abi("p", POINTER_SIZE, of(_type_attr(ctype)))
    if _is_array(ctype):
        element = of(_type_attr(ctype))
        return Abi("p", POINTER_SIZE, element) if argument else Abi("a", ctypes.sizeof(ctype), element)
    if _is_simple(ctype):
        return _simple(_type_attr(ctype), ctypes.sizeof(ctype))
    if issubclass(ctype, CFuncPtr):
        return Abi("p", POINTER_SIZE, Abi("fn", 0))
    if issubclass(ctype, (ctypes.Structure, ctypes.Union)):
        return Abi("s", ctypes.sizeof(ctype))
    raise TypeError(f"unsupported ctypes type: {ctype!r}")


def describe(ctype: object) -> str:
    if ctype is None:
        return "None"
    if isinstance(ctype, type):
        return ctype.__qualname__
    return getattr(ctype, "__qualname__", repr(ctype))


def mismatch(python: Abi, native: Abi, *, check_sign: bool) -> str | None:
    if native.kind == "?":
        return None
    if python.size != native.size:
        return f"size {python.size} != {native.size}"
    pair = {python.kind, native.kind}
    if python.kind == native.kind:
        if python.kind == "p":
            return _pointee_mismatch(python.pointee, native.pointee)
        if python.kind == "a" and python.pointee and native.pointee:
            if python.pointee.size != native.pointee.size and native.pointee.kind != "?":
                return f"array element size {python.pointee.size} != {native.pointee.size}"
        return None
    if pair <= {"i", "u"}:
        return "signedness differs" if check_sign else None
    if "f" in pair:
        return f"{_KIND_NAMES[python.kind]} vs {_KIND_NAMES[native.kind]}"
    if "p" in pair:
        other = native if python.kind == "p" else python
        if other.is_integer and other.size == POINTER_SIZE:
            return None
        return f"{_KIND_NAMES[python.kind]} vs {_KIND_NAMES[native.kind]}"
    if "v" in pair:
        return f"{_KIND_NAMES[python.kind]} vs {_KIND_NAMES[native.kind]}"
    # Opaque stand-ins: an integer or byte array in place of a same-sized struct or union (LUID, IN_ADDR, ...).
    return None


def _pointee_mismatch(python: Abi | None, native: Abi | None) -> str | None:
    if python is None or native is None or "v" in (python.kind, native.kind):
        return None
    if native.kind in ("?", "fn") or python.kind == "fn":
        return None
    if python.size != native.size:
        return f"points to {python} but the API expects a pointer to {native}"
    return None
