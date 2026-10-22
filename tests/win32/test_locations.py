import ast

import pytest

from tests.win32 import discovery, specs
from tests.win32.probe import ProbeResult

BINDINGS = "core.utils.win32.bindings"
STRUCTS = "core.utils.win32.structs"
DLL_LOADERS = frozenset({"WinDLL", "CDLL", "OleDLL", "PyDLL"})


def _in_bindings(module: str) -> bool:
    return module == BINDINGS or module.startswith(BINDINGS + ".")


def test_only_the_bindings_load_dlls():
    found: list[str] = []
    for module in discovery.source_modules():
        if _in_bindings(module.name) or specs.keeps_own_ctypes(module.name):
            continue
        for node in ast.walk(module.tree()):
            if isinstance(node, ast.Call):
                callee = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", None)
                if callee in DLL_LOADERS:
                    found.append(f"{module.rel}:{node.lineno} loads a DLL with {callee}(...)")
    if found:
        pytest.fail(
            "\n".join(found)
            + "\n\nLoad the DLL in a module under src/core/utils/win32/bindings, declare its functions there "
            "and import them from it.",
            pytrace=False,
        )


def test_structs_and_com_interfaces_live_in_the_bindings():
    found: list[str] = []
    for cls in discovery.ctypes_structs():
        module = cls.__module__
        if module != STRUCTS and not _in_bindings(module) and not specs.keeps_own_ctypes(module):
            found.append(f"struct {discovery.type_id(cls)}: move it to src/core/utils/win32/structs.py")
    for cls in discovery.com_interfaces():
        module = cls.__module__
        if not _in_bindings(module) and not specs.keeps_own_ctypes(module):
            found.append(
                f"COM interface {discovery.type_id(cls)}: move it to a module under src/core/utils/win32/bindings"
            )
    if found:
        pytest.fail("\n".join(found), pytrace=False)


@pytest.mark.sdk
def test_windows_constants_live_in_constants_py(sdk: ProbeResult):
    found: list[str] = []
    for constant in discovery.local_constants():
        c_name = discovery.sdk_constant_name(constant.name.lstrip("_"))
        native = sdk.constants.get(c_name)
        if native is not None and not native.get("skip"):
            found.append(f"{constant.path}:{constant.line} defines {constant.name}, a Windows SDK constant ({c_name})")
    if found:
        pytest.fail(
            "\n".join(found) + "\n\nImport it from core.utils.win32.constants, adding it there if it is missing. "
            "If it is a different value that only shares the name, rename it.",
            pytrace=False,
        )


def test_own_ctypes_modules_exist():
    names = [module.name for module in discovery.source_modules()]
    stale = [p for p in specs.OWN_CTYPES_MODULES if not any(n == p or n.startswith(p + ".") for n in names)]
    assert not stale, f"specs.OWN_CTYPES_MODULES lists modules that no longer exist: {', '.join(stale)}"
