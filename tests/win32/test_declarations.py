import ast
import ctypes
from collections import defaultdict
from functools import cache

import pytest

from tests.support.source import SRC_ROOT, SourceModule, core_modules
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


_DECLARE_HINT = (
    "Declare argtypes and restype next to the function's WinDLL in src/core/utils/win32/bindings. Without "
    "argtypes ctypes passes every Python int as a 4-byte C int, so an 8-byte handle or pointer fails with "
    "OverflowError; without restype it reads the result as a C int."
)


def _modules_with_foreign_calls() -> list[str]:
    return sorted({call.site.module for call in foreign.analyse().calls} | set(known_issues.MISSING_DECLARATIONS))


@pytest.mark.parametrize("module", _modules_with_foreign_calls())
def test_every_foreign_call_is_declared(module: str):
    code = foreign.analyse()
    lines: dict[str, set[int]] = defaultdict(set)
    missing: dict[str, set[str]] = defaultdict(set)
    for call in code.calls:
        absent = {"argtypes", "restype"} - code.declared(call.function)
        if call.site.module == module and absent:
            lines[call.function.name].add(call.site.line)
            missing[call.function.name] |= absent
    found = {
        name: f"{name} is called without {' or '.join(sorted(missing[name]))} (line {', '.join(map(str, sorted(lines[name])))})"
        for name in lines
    }
    known = known_issues.MISSING_DECLARATIONS.get(module, ())
    known_issues.assert_matches_baseline(found, known, "MISSING_DECLARATIONS", module, hint=_DECLARE_HINT)


_SHARED_HINT = (
    "Every library in the process shares the function objects of ctypes.windll, oledll and cdll: argtypes "
    "set on them change the calls other libraries make, and calls made through them use whatever argtypes "
    "another library set. Declare the function in a module under src/core/utils/win32/bindings, which loads "
    "its own WinDLL."
)


def _source_modules() -> dict[str, SourceModule]:
    top_level = [SourceModule(path.stem, path) for path in sorted(SRC_ROOT.glob("*.py"))]
    return {module.name: module for module in (*top_level, *core_modules())}


def _attribute_chain(node: ast.Attribute) -> list[str]:
    parts: list[str] = []
    current: ast.expr = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return parts[::-1]


@cache
def _shared_loader_references() -> dict[str, dict[str, set[int]]]:
    found: dict[str, dict[str, set[int]]] = defaultdict(lambda: defaultdict(set))
    for name, module in _source_modules().items():
        chains: dict[int, set[str]] = defaultdict(set)
        for node in ast.walk(module.tree()):
            if isinstance(node, ast.Attribute):
                parts = _attribute_chain(node)
                loader = next((i for i, part in enumerate(parts) if part in foreign.LOADERS), None)
                if loader is not None:
                    chains[node.lineno].add(".".join(parts[loader:]))
        for line, names in chains.items():
            for chain in names:
                if not any(other.startswith(chain + ".") for other in names):
                    found[name][chain].add(line)
    return found


@pytest.mark.parametrize("module", sorted(_source_modules()))
def test_nothing_uses_the_shared_ctypes_loaders(module: str):
    references = _shared_loader_references().get(module, {})
    found = {chain: f"{chain} (line {', '.join(map(str, sorted(lines)))})" for chain, lines in references.items()}
    known = known_issues.SHARED_LOADERS.get(module, ())
    known_issues.assert_matches_baseline(found, known, "SHARED_LOADERS", module, hint=_SHARED_HINT)


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


_LAST_ERROR_HINT = (
    "Every bindings handle loads with use_last_error=True, so ctypes keeps the error of a bindings call in its "
    "per-thread copy and the thread's own last error belongs to whatever ran after it. Read the error with "
    "GetLastError() from core.utils.win32.bindings.kernel32 and raise ctypes.WinError(GetLastError())."
)


def _thread_error_reads(tree: ast.Module) -> dict[str, set[int]]:
    found: dict[str, set[int]] = defaultdict(set)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "ctypes":
            if any(alias.name == "GetLastError" for alias in node.names):
                found["from ctypes import GetLastError"].add(node.lineno)
        elif isinstance(node, ast.Attribute) and node.attr == "GetLastError":
            if isinstance(node.value, ast.Name) and node.value.id == "ctypes":
                found["ctypes.GetLastError"].add(node.lineno)
        elif isinstance(node, ast.Call) and not node.args and not node.keywords:
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else None
            if name == "WinError":
                found["WinError()"].add(node.lineno)
    return found


@pytest.mark.parametrize("module", sorted(_source_modules()))
def test_last_error_comes_from_the_bindings(module: str):
    reads = _thread_error_reads(_source_modules()[module].tree())
    if reads:
        lines = [f"{name} (line {', '.join(map(str, sorted(found)))})" for name, found in sorted(reads.items())]
        pytest.fail("\n".join([*lines, "", _LAST_ERROR_HINT]), pytrace=False)
