import ast
import importlib
from dataclasses import dataclass
from functools import cache, cached_property
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
CORE_ROOT = SRC_ROOT / "core"


@dataclass(frozen=True)
class SourceModule:
    name: str
    path: Path

    @cached_property
    def rel(self) -> str:
        return self.path.relative_to(REPO_ROOT).as_posix()

    def tree(self) -> ast.Module:
        return parse(self.path)


def _module_name(path: Path) -> str:
    parts = path.relative_to(SRC_ROOT).with_suffix("").parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


@cache
def core_modules() -> tuple[SourceModule, ...]:
    return tuple(SourceModule(_module_name(path), path) for path in sorted(CORE_ROOT.rglob("*.py")))


@cache
def parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


@cache
def import_core_modules() -> dict[str, str]:
    failures = {}
    for module in core_modules():
        try:
            importlib.import_module(module.name)
        except Exception as exc:
            failures[module.name] = f"{type(exc).__name__}: {exc}"
    return failures


def all_subclasses(cls: type) -> list[type]:
    seen: dict[type, None] = {}
    stack = [cls]
    while stack:
        for sub in stack.pop().__subclasses__():
            if sub not in seen:
                seen[sub] = None
                stack.append(sub)
    return list(seen)


def defined_in_core(cls: type) -> bool:
    return cls.__module__ == "core" or cls.__module__.startswith("core.")
