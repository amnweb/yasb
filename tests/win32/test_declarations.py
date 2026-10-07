import ctypes
from collections import defaultdict
from functools import cache

import pytest

from tests.win32 import abi, foreign, known_issues, specs
from tests.win32.probe import MISSING_HEADER_HINT, ProbeResult, function_key

_C_INT_SIZE = ctypes.sizeof(ctypes.c_int)
_HINT = (
    "Without restype ctypes reads every result as a 4-byte C int: an 8-byte handle, pointer or LONG_PTR "
    "loses its upper half, and a 1-byte BOOLEAN picks up whatever is in the rest of the register. Declare "
    "restype and argtypes, the way the modules in src/core/utils/win32/bindings do."
)


def _modules_with_calls() -> list[str]:
    return sorted({call.site.module for call in foreign.analyse().calls} | set(known_issues.UNDECLARED))


def _read_correctly_as_c_int(native: abi.Abi) -> bool:
    return native.kind == "v" or (native.is_integer and native.size == _C_INT_SIZE)


@pytest.mark.sdk
@pytest.mark.parametrize("module", _modules_with_calls())
def test_results_without_restype_fit_a_c_int(module: str, sdk: ProbeResult):
    code = foreign.analyse()
    returns: dict[str, abi.Abi] = {}
    lines: dict[str, list[int]] = defaultdict(list)
    for call in code.calls:
        function = call.function
        if call.site.module != module or not call.result_used or "restype" in code.declared(function):
            continue
        if function.ordinal or specs.not_in_sdk(function.name):
            continue
        key = function_key(function.name)
        if key in sdk.errors:
            pytest.fail(
                f"{function.name} (line {call.site.line}) is not declared by the SDK headers: {sdk.errors[key]}\n"
                f"Check the spelling. {MISSING_HEADER_HINT} "
                "Only an undocumented function goes in tests/win32/specs.py:NOT_IN_SDK.",
                pytrace=False,
            )
        native = abi.Abi.from_json(sdk.functions[function.name]["ret"])
        if not _read_correctly_as_c_int(native):
            returns[function.name] = native
            lines[function.name].append(call.site.line)

    found = {
        name: f"{name} returns {native} but has no restype, so ctypes reads it as a 4-byte int "
        f"(line {', '.join(map(str, lines[name]))})"
        for name, native in returns.items()
    }
    known = known_issues.UNDECLARED.get(module, ())
    known_issues.assert_matches_baseline(found, known, "UNDECLARED", module, hint=_HINT)


@cache
def _load(library: str) -> ctypes.CDLL | None:
    try:
        return ctypes.WinDLL(library)
    except OSError:
        return None


@cache
def _referenced_by_library() -> dict[str, dict[str, set[str]]]:
    code = foreign.analyse()
    found: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for item in (*code.declarations, *code.calls):
        function = item.function
        if function.dll.known and function.dll.library:
            found[function.dll.library][function.name].add(str(item.site))
    return found


def _exported(dll: ctypes.CDLL, name: str) -> bool:
    try:
        if name.startswith("#"):
            dll[int(name[1:])]  # pyright: ignore[reportArgumentType]
        else:
            getattr(dll, name)
    except AttributeError:
        return False
    return True


@pytest.mark.parametrize("library", sorted(_referenced_by_library()))
def test_referenced_functions_are_exported(library: str):
    dll = _load(library)
    if dll is None:
        pytest.skip(f"{library}.dll does not load on this machine")

    found: dict[str, str] = {}
    for name, sites in _referenced_by_library()[library].items():
        if not _exported(dll, name):
            macro = f" ({name}W is; {name} is only a macro in the SDK headers)" if _exported(dll, f"{name}W") else ""
            found[name] = f"{library}.dll does not export {name}{macro}, used at {', '.join(sorted(sites))}"
    known_issues.assert_matches_baseline(found, known_issues.EXPORTS.get(library, {}), "EXPORTS", library)
