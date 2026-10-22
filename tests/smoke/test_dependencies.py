import importlib.metadata
import tomllib
from collections.abc import Iterator

import pytest
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from tests.support.source import REPO_ROOT

BLOCKED_PACKAGES = {
    "pywin32": "YASB calls Windows through ctypes, use the bindings in src/core/utils/win32/bindings",
}

_BLOCKED = {canonicalize_name(name): reason for name, reason in BLOCKED_PACKAGES.items()}


def test_pyproject_has_no_blocked_packages():
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    groups = [project.get("dependencies", []), *project.get("optional-dependencies", {}).values()]
    found = [
        f"{spec}: {_BLOCKED[name]}"
        for group in groups
        for spec in group
        if (name := canonicalize_name(Requirement(spec).name)) in _BLOCKED
    ]
    if found:
        pytest.fail("pyproject.toml lists a blocked package:\n" + "\n".join(found), pytrace=False)


def _requirements(name: str, extras: frozenset[str]) -> Iterator[Requirement]:
    try:
        requires = importlib.metadata.distribution(name).requires or []
    except importlib.metadata.PackageNotFoundError:
        return
    for spec in requires:
        requirement = Requirement(spec)
        marker = requirement.marker
        if marker is None or any(marker.evaluate({"extra": extra}) for extra in {"", *extras}):
            yield requirement


def test_no_dependency_pulls_in_a_blocked_package():
    try:
        importlib.metadata.distribution("YASB")
    except importlib.metadata.PackageNotFoundError:
        pytest.skip("YASB isn't installed in this environment; run pip install -e .[test]")

    seen: set[tuple[str, frozenset[str]]] = set()
    pending: list[tuple[str, frozenset[str], tuple[str, ...]]] = [("YASB", frozenset(), ("YASB",))]
    while pending:
        name, extras, chain = pending.pop()
        for requirement in _requirements(name, extras):
            path = (*chain, requirement.name)
            dependency = canonicalize_name(requirement.name)
            if dependency in _BLOCKED:
                pytest.fail(f"{' -> '.join(path)}: {_BLOCKED[dependency]}", pytrace=False)
            key = (dependency, frozenset(requirement.extras))
            if key not in seen:
                seen.add(key)
                pending.append((*key, path))
