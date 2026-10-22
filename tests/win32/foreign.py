import ast
from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import cache, cached_property
from typing import TypeGuard

from tests.support.source import SourceModule, core_modules

LOADERS = {"windll", "oledll", "cdll"}
DLL_TYPES = {"WinDLL", "CDLL", "OleDLL", "LoadLibrary"}
DECLARATION_ATTRS = ("argtypes", "restype", "errcheck")
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
_MAX_DEPTH = 16


@dataclass(frozen=True)
class Dll:
    key: str
    library: str | None
    known: bool = True


@dataclass(frozen=True)
class Function:
    dll: Dll
    name: str

    @property
    def ordinal(self) -> bool:
        return self.name.startswith("#")


@dataclass(frozen=True)
class Site:
    module: str
    path: str
    line: int
    scope: str
    cls: str | None

    def __str__(self) -> str:
        return f"{self.path}:{self.line}"


@dataclass(frozen=True)
class Declaration:
    function: Function
    attr: str
    value: ast.expr
    site: Site


@dataclass(frozen=True)
class Call:
    function: Function
    site: Site
    result_used: bool = True


@dataclass(frozen=True)
class _Imported:
    module: str
    name: str


@dataclass
class _Scope:
    module: str
    qualname: str
    parent: _Scope | None
    cls: str | None
    is_class: bool = False
    bindings: dict[str, tuple[ast.expr | _Imported, _Scope]] = field(
        default_factory=lambda: dict[str, tuple[ast.expr | _Imported, _Scope]]()
    )
    globals_: set[str] = field(default_factory=set[str])

    @property
    def root(self) -> _Scope:
        scope = self
        while scope.parent is not None:
            scope = scope.parent
        return scope

    def lookup(self, name: str) -> tuple[ast.expr | _Imported, _Scope, _Scope] | None:
        scope: _Scope | None = self
        while scope is not None:
            if name in scope.bindings:
                value, defining = scope.bindings[name]
                return value, defining, scope
            scope = scope.parent
        return None


def _library_name(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value.replace("\\", "/").rsplit("/", 1)[-1].lower().removesuffix(".dll")
    return None


def _name_of(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _is_self_attr(node: ast.expr) -> TypeGuard[ast.Attribute]:
    return isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self"


def _creates_dll(node: ast.expr | _Imported) -> bool:
    return isinstance(node, ast.Call) and _name_of(node.func) in DLL_TYPES


def _scope_nodes(body: list[ast.stmt]) -> Iterator[ast.AST]:
    stack: list[ast.AST] = list(reversed(body))
    while stack:
        node = stack.pop()
        yield node
        if not isinstance(node, _SCOPES):
            stack.extend(reversed(list(ast.iter_child_nodes(node))))


class _ModuleAnalysis:
    def __init__(self, module: SourceModule, registry: dict[str, _ModuleAnalysis]) -> None:
        self.module = module
        self.registry = registry
        self.root = _Scope(module.name, "", None, None)
        self.star_imports: list[str] = []
        self.class_attrs: dict[str, dict[str, tuple[ast.expr, _Scope]]] = {}
        self.factories: dict[str, list[tuple[ast.expr, _Scope]]] = {}
        self.declarations: list[Declaration] = []
        self.calls: list[Call] = []
        self._scopes: list[tuple[list[ast.Assign | ast.Call], _Scope]] = []
        self._discarded: set[ast.Call] = set()

    @property
    def package(self) -> str:
        if self.module.path.name == "__init__.py":
            return self.module.name
        return self.module.name.rpartition(".")[0]

    def collect(self) -> None:
        self._collect(self.module.tree().body, self.root)

    def record(self) -> None:
        for nodes, scope in self._scopes:
            self._record(nodes, scope)

    def _import_base(self, node: ast.ImportFrom) -> str:
        if not node.level:
            return node.module or ""
        base = self.package.split(".")
        base = base[: len(base) - (node.level - 1)]
        return ".".join([*base, node.module] if node.module else base)

    def _collect(self, body: list[ast.stmt], scope: _Scope) -> None:
        records: list[ast.Assign | ast.Call] = []
        nested: list[ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef] = []
        for node in _scope_nodes(body):
            if isinstance(node, ast.Call):
                records.append(node)
            elif isinstance(node, ast.Assign):
                records.append(node)
                if len(node.targets) == 1:
                    self._bind(node.targets[0], node.value, scope)
            elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                nested.append(node)
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                self._discarded.add(node.value)
            elif isinstance(node, ast.Global):
                scope.globals_.update(node.names)
            elif isinstance(node, ast.ImportFrom):
                base = self._import_base(node)
                for alias in node.names:
                    if alias.name == "*":
                        self.star_imports.append(base)
                    else:
                        scope.bindings[alias.asname or alias.name] = (_Imported(base, alias.name), scope)
            elif isinstance(node, ast.Return) and node.value is not None and scope.qualname:
                self.factories.setdefault(scope.qualname.rpartition(".")[2], []).append((node.value, scope))
        self._scopes.append((records, scope))

        for node in nested:
            qualname = f"{scope.qualname}.{node.name}".lstrip(".")
            if isinstance(node, ast.ClassDef):
                self.class_attrs.setdefault(node.name, {})
                self._collect(node.body, _Scope(scope.module, qualname, scope, node.name, is_class=True))
            else:
                # Method bodies do not see names bound in the class body.
                parent = scope.parent if scope.is_class else scope
                self._collect(node.body, _Scope(scope.module, qualname, parent, scope.cls))

    def _bind(self, target: ast.expr, value: ast.expr, scope: _Scope) -> None:
        if isinstance(target, ast.Name):
            owner = self.root if target.id in scope.globals_ else scope
            owner.bindings[target.id] = (value, scope)
        elif _is_self_attr(target) and scope.cls is not None:
            self.class_attrs.setdefault(scope.cls, {})[target.attr] = (value, scope)

    def _exported(self, imported: _Imported, depth: int, *, want_dll: bool) -> Dll | Function | None:
        analysis = self.registry.get(imported.module)
        if analysis is None:
            return None
        if imported.name in analysis.root.bindings:
            node = ast.Name(id=imported.name)
            if want_dll:
                return analysis.dll(node, analysis.root, depth + 1)
            return analysis.function(node, analysis.root, depth=depth + 1)
        for star in analysis.star_imports:
            found = analysis._exported(_Imported(star, imported.name), depth + 1, want_dll=want_dll)
            if found is not None:
                return found
        return None

    def dll(self, node: ast.expr, scope: _Scope, depth: int = 0) -> Dll | None:
        if depth > _MAX_DEPTH:
            return None
        if isinstance(node, ast.Attribute) and _name_of(node.value) in LOADERS and node.attr != "LoadLibrary":
            return Dll(f"{_name_of(node.value)}.{node.attr.lower()}", node.attr.lower())
        if isinstance(node, ast.Call):
            if _creates_dll(node):
                library = _library_name(node.args[0] if node.args else None)
                return Dll(f"{self.module.name}:{node.lineno}:{node.col_offset}", library)
            if isinstance(node.func, ast.Name):
                for expr, defining in self.factories.get(node.func.id, []):
                    found = self.dll(expr, defining, depth + 1)
                    if found is not None:
                        return found
            return None
        if isinstance(node, ast.Name):
            bound = scope.lookup(node.id)
            if bound is None:
                return None
            value, defining, owner = bound
            if isinstance(value, _Imported):
                found = self._exported(value, depth, want_dll=True)
                return found if isinstance(found, Dll) else None
            found = self.dll(value, defining, depth + 1)
            if found is not None and _creates_dll(value):
                return Dll(f"{self.module.name}:{owner.qualname}:{node.id}", found.library)
            return found
        if _is_self_attr(node) and scope.cls is not None:
            bound = self.class_attrs.get(scope.cls, {}).get(node.attr)
            if bound is None:
                return None
            found = self.dll(bound[0], bound[1], depth + 1)
            if found is not None and isinstance(bound[0], ast.Call):
                return Dll(f"{self.module.name}:{scope.cls}.{node.attr}", found.library)
            return found
        return None

    def _symbol(self, node: ast.expr, scope: _Scope, depth: int = 0) -> str:
        if depth < _MAX_DEPTH and isinstance(node, ast.Name):
            bound = scope.lookup(node.id)
            if bound is not None:
                value, defining, owner = bound
                if isinstance(value, (ast.Name, ast.Attribute)):
                    return self._symbol(value, defining, depth + 1)
                return f"{self.module.name}:{owner.qualname}:{node.id}"
            return f"{self.module.name}::{node.id}"
        if _is_self_attr(node):
            return f"{self.module.name}:{scope.cls}.{node.attr}"
        return f"{self.module.name}:{ast.unparse(node)}"

    def function(self, node: ast.expr, scope: _Scope, *, depth: int = 0) -> Function | None:
        if depth > _MAX_DEPTH:
            return None
        if isinstance(node, ast.Attribute) and not _is_self_attr(node):
            dll = self.dll(node.value, scope)
            return Function(dll, node.attr) if dll is not None else None
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
            dll = self.dll(node.value, scope)
            if dll is not None:
                key = node.slice.value
                return Function(dll, key if isinstance(key, str) else f"#{key}")
            return None
        if isinstance(node, ast.Call) and _name_of(node.func) == "getattr" and len(node.args) >= 2:
            dll = self.dll(node.args[0], scope)
            if dll is not None and isinstance(node.args[1], ast.Constant):
                return Function(dll, str(node.args[1].value))
            return None
        if isinstance(node, ast.Name):
            bound = scope.lookup(node.id)
            if bound is None:
                return None
            value, defining, _ = bound
            if isinstance(value, _Imported):
                found = self._exported(value, depth, want_dll=False)
                return found if isinstance(found, Function) else None
            return self.function(value, defining, depth=depth + 1)
        if _is_self_attr(node) and scope.cls is not None:
            bound = self.class_attrs.get(scope.cls, {}).get(node.attr)
            if bound is not None:
                return self.function(bound[0], bound[1], depth=depth + 1)
        return None

    def _inferred(self, node: ast.expr, scope: _Scope) -> Function | None:
        if isinstance(node, ast.Attribute) and not _is_self_attr(node):
            return Function(Dll(f"?{self._symbol(node.value, scope)}", None, known=False), node.attr)
        return None

    def _site(self, node: ast.stmt | ast.expr, scope: _Scope) -> Site:
        return Site(self.module.name, self.module.rel, node.lineno, scope.qualname, scope.cls)

    def _record(self, nodes: list[ast.Assign | ast.Call], scope: _Scope) -> None:
        for node in nodes:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Attribute) and target.attr in DECLARATION_ATTRS:
                        function = self.function(target.value, scope) or self._inferred(target.value, scope)
                        if function is not None:
                            site = self._site(node, scope)
                            self.declarations.append(Declaration(function, target.attr, node.value, site))
            else:
                function = self.function(node.func, scope) or self._inferred(node.func, scope)
                if function is not None:
                    self.calls.append(Call(function, self._site(node, scope), node not in self._discarded))


@dataclass(frozen=True)
class ForeignCode:
    declarations: tuple[Declaration, ...]
    calls: tuple[Call, ...]

    @cached_property
    def _declared(self) -> dict[Function, set[str]]:
        declared: dict[Function, set[str]] = {}
        for declaration in self.declarations:
            declared.setdefault(declaration.function, set()).add(declaration.attr)
        return declared

    def declared(self, function: Function) -> set[str]:
        return self._declared.get(function, set())


@cache
def analyse() -> ForeignCode:
    registry: dict[str, _ModuleAnalysis] = {}
    for module in core_modules():
        registry[module.name] = _ModuleAnalysis(module, registry)
    for analysis in registry.values():
        analysis.collect()
    for analysis in registry.values():
        analysis.record()

    declarations = [d for analysis in registry.values() for d in analysis.declarations]
    # A method call on an object nothing declares argtypes on is ordinary Python, not a foreign call.
    declared_unknown = {d.function.dll.key for d in declarations if not d.function.dll.known}
    calls = [
        call
        for analysis in registry.values()
        for call in analysis.calls
        if call.function.dll.known or call.function.dll.key in declared_unknown
    ]
    return ForeignCode(tuple(declarations), tuple(calls))
