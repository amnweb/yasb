import ast
import ctypes
import importlib
import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache
from types import ModuleType
from typing import TypedDict

import comtypes  # pyright: ignore[reportMissingTypeStubs]

from tests.support.source import all_subclasses, core_modules, defined_in_core, import_core_modules
from tests.win32 import foreign, specs
from tests.win32.probe import StructRequest, VtableRequest

CONSTANT_MODULES = re.compile(r"^core\.utils\.win32\.(constants|bindings(\..+)?)$")
_CONSTANT_NAME = re.compile(r"^[A-Z][A-Z0-9_]+$")


def type_id(cls: type) -> str:
    return f"{cls.__module__}.{cls.__qualname__}"


@cache
def ctypes_structs() -> tuple[type[ctypes.Structure | ctypes.Union], ...]:
    import_core_modules()
    found = [
        cls
        for base in (ctypes.Structure, ctypes.Union)
        for cls in all_subclasses(base)
        if defined_in_core(cls) and "_fields_" in cls.__dict__
    ]
    return tuple(sorted(found, key=type_id))


def is_prefix_struct(cls: type) -> bool:
    spec = specs.STRUCTS.get(type_id(cls))
    return isinstance(spec, specs.Sdk) and spec.prefix


def struct_fields(cls: type[ctypes.Structure | ctypes.Union]) -> list[tuple[str, type]]:
    return [(entry[0], entry[1]) for entry in cls._fields_ if len(entry) == 2]


def struct_requests() -> list[StructRequest]:
    requests: list[StructRequest] = []
    for cls in ctypes_structs():
        key = type_id(cls)
        spec = specs.struct_spec(key, cls.__name__)
        c_type = f"vendored::{spec.c_type}" if isinstance(spec, specs.Vendored) else spec.c_type
        assert c_type is not None
        members: list[tuple[str, str]] = []
        for name, _ in struct_fields(cls):
            target = spec.fields.get(name, name)
            if isinstance(target, specs.Offset):
                target = target.member
            if target is not None:
                members.append((name, target))
        requests.append(StructRequest(key, c_type, tuple(members)))
    return requests


@dataclass(frozen=True)
class ComMethod:
    index: int
    name: str
    c_name: str
    restype: object
    argtypes: tuple[object, ...]


@cache
def com_interfaces() -> tuple[type, ...]:
    import_core_modules()
    found = [cls for cls in all_subclasses(comtypes.IUnknown) if defined_in_core(cls) and "_methods_" in cls.__dict__]
    return tuple(sorted(found, key=type_id))


def _c_method_name(name: str, idlflags: Iterable[str] | None) -> str:
    flags = set(idlflags or ())
    for flag, prefix in (("propget", "get_"), ("propput", "put_"), ("propputref", "putref_")):
        if flag in flags:
            return prefix + name
    return name


def com_methods(cls: type) -> list[ComMethod]:
    methods: list[ComMethod] = []
    for base in reversed(cls.__mro__):
        for spec in base.__dict__.get("_methods_", ()):
            restype, name, argtypes = spec[0], spec[1], tuple(spec[2])
            idlflags = spec[4] if len(spec) > 4 else ()
            methods.append(ComMethod(len(methods), name, _c_method_name(name, idlflags), restype, argtypes))
    return methods


def vtable_requests() -> list[VtableRequest]:
    requests: list[VtableRequest] = []
    for cls in com_interfaces():
        key = type_id(cls)
        if key in specs.UNDOCUMENTED_INTERFACES:
            continue
        c_interface = specs.COM_INTERFACES.get(key, cls.__name__)
        requests.append(VtableRequest(key, c_interface, tuple(m.c_name for m in com_methods(cls))))
    return requests


@cache
def win32_constants() -> dict[str, dict[str, int]]:
    import_core_modules()
    found: dict[str, dict[str, int]] = {}
    for module in core_modules():
        if not CONSTANT_MODULES.match(module.name):
            continue
        runtime = importlib.import_module(module.name)
        names: dict[str, int] = {}
        for node in module.tree().body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
                value = getattr(runtime, name, None)
                if _CONSTANT_NAME.match(name) and isinstance(value, int) and not isinstance(value, bool):
                    names[name] = value
        if names:
            found[module.name] = names
    return found


@dataclass(frozen=True)
class Binding:
    """One module's declaration of one foreign function, as the module leaves it."""

    id: str
    module: str
    function: foreign.Function
    sites: tuple[foreign.Site, ...]
    argtypes: ast.expr | None
    restype: ast.expr | None
    cls: str | None


@cache
def foreign_bindings() -> tuple[Binding, ...]:
    grouped: dict[tuple[str, foreign.Function], list[foreign.Declaration]] = defaultdict(list)
    for decl in foreign.analyse().declarations:
        grouped[(decl.site.module, decl.function)].append(decl)
    names: defaultdict[tuple[str, str], int] = defaultdict(int)
    for module, function in grouped:
        names[(module, function.name)] += 1
    bindings: list[Binding] = []
    for (module, function), decls in grouped.items():
        last = {decl.attr: decl for decl in decls}
        binding_id = f"{function.name}@{module}"
        if names[(module, function.name)] > 1:
            binding_id += f"[{function.dll.library or function.dll.key}]"
        bindings.append(
            Binding(
                id=binding_id,
                module=module,
                function=function,
                sites=tuple(d.site for d in decls),
                argtypes=last["argtypes"].value if "argtypes" in last else None,
                restype=last["restype"].value if "restype" in last else None,
                cls=decls[-1].site.cls,
            )
        )
    return tuple(sorted(bindings, key=lambda b: b.id))


def evaluate(binding: Binding, node: ast.expr) -> object:
    module: ModuleType = importlib.import_module(binding.module)
    namespace = dict(vars(module))
    if binding.cls is not None:
        namespace["self"] = getattr(module, binding.cls, None)
    return eval(compile(ast.Expression(node), binding.module, "eval"), namespace)


def sdk_function_names() -> list[str]:
    code = foreign.analyse()
    functions = {b.function for b in foreign_bindings()}
    functions |= {call.function for call in code.calls if "restype" not in code.declared(call.function)}
    return sorted({f.name for f in functions if not f.ordinal and specs.not_in_sdk(f.name) is None})


def sdk_constant_name(name: str) -> str:
    return specs.CONSTANT_ALIASES.get(name, name)


class ProbeRequests(TypedDict):
    structs: list[StructRequest]
    functions: list[str]
    vtables: list[VtableRequest]
    constants: list[str]
    vendored: str


def probe_requests() -> ProbeRequests:
    constants = sorted({sdk_constant_name(name) for names in win32_constants().values() for name in names})
    return {
        "structs": struct_requests(),
        "functions": sdk_function_names(),
        "vtables": vtable_requests(),
        "constants": constants,
        "vendored": specs.VENDORED_DECLARATIONS,
    }
