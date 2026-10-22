"""Structural guards for the core.cloud package.

YASB Cloud ships as a separate executable and must stay decoupled from the bar. These
tests fail loudly the first time someone reaches across the line, which is much cheaper
than discovering it when the build starts pulling in widget code.

    python -m pytest tests/cloud/test_boundaries.py -q
"""

import ast
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
CLOUD = SRC / "core" / "cloud"

ALLOWED_PREFIXES = (
    "core.cloud",
    "core.ui",
    "core.utils.win32",
    "core.utils.system",
    "core.utils.utilities",
    # Leaf helper for opening URLs in the browser; depends only on stdlib and
    # core.utils.win32, so it drags nothing from the bar in behind it.
    "core.utils.shell_utils",
    # Same shape: a process-table lookup over core.utils.win32 and nothing else. Used to
    # tell whether the bar is running before a restore stops it.
    "core.utils.process",
    "settings",
)
"""Everything else in the tree is off limits - bar, widgets, setup, validation, events."""

ENCRYPTION_STDLIB_ONLY = CLOUD / "encryption"
"""The encryption package must not depend on Qt or anything outside core.cloud."""


def _encryption_modules() -> list[Path]:
    """Every module the rules below apply to.

    The emptiness check is the point: these tests scan by path, and rglob on a directory
    that has been renamed away yields nothing at all, so every one of them would pass
    while checking no code.
    """
    paths = sorted(ENCRYPTION_STDLIB_ONLY.rglob("*.py"))
    assert paths, f"no modules under {ENCRYPTION_STDLIB_ONLY} - was the package moved?"
    return paths


def _modules() -> list[Path]:
    return sorted(CLOUD.rglob("*.py"))


def _imported_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative import
                names.add(f".{node.module or ''}")
            elif node.module:
                names.add(node.module)
    return names


def _is_first_party(module: str) -> bool:
    return module.split(".")[0] in {"core", "settings"}


def test_cloud_only_imports_allowed_first_party_modules():
    violations: list[str] = []
    for path in _modules():
        for name in _imported_names(path):
            if not _is_first_party(name):
                continue
            if not any(name == prefix or name.startswith(prefix + ".") for prefix in ALLOWED_PREFIXES):
                violations.append(f"{path.relative_to(SRC)} imports {name}")

    assert not violations, "core.cloud reached outside its allowed dependencies:\n  " + "\n  ".join(violations)


def test_encryption_has_no_qt_or_cross_package_dependency():
    violations: list[str] = []
    for path in _encryption_modules():
        for name in _imported_names(path):
            root = name.split(".")[0]
            if root in {"PyQt6", "PySide6", "qasync"}:
                violations.append(f"{path.relative_to(SRC)} imports {name} (encryption must stay Qt-free)")
            elif _is_first_party(name) and not name.startswith("core.cloud"):
                violations.append(f"{path.relative_to(SRC)} imports {name} (encryption may only use core.cloud)")

    assert not violations, "encryption package dependency violations:\n  " + "\n  ".join(violations)


def test_encryption_never_uses_the_random_module():
    """Randomness must come from ``secrets`` (OS CSPRNG), never ``random`` (Mersenne Twister).

    This replaces an earlier wrapper module that existed only to centralise this rule. A
    test enforces it without making every call site route through an extra indirection.
    """
    violations: list[str] = []
    for path in _encryption_modules():
        for name in _imported_names(path):
            if name == "random" or name.startswith("random."):
                violations.append(f"{path.relative_to(SRC)} imports {name}")

    assert not violations, "encryption must use secrets, not random:\n  " + "\n  ".join(violations)


def test_encryption_uses_no_third_party_packages():
    """The client constraint: stdlib and ctypes only, no new dependencies."""
    stdlib = set(sys.stdlib_module_names)
    violations: list[str] = []
    for path in _encryption_modules():
        for name in _imported_names(path):
            root = name.split(".")[0]
            if root in stdlib or name.startswith("core.cloud") or name.startswith("."):
                continue
            violations.append(f"{path.relative_to(SRC)} imports third-party {name}")

    assert not violations, "encryption must depend only on the standard library:\n  " + "\n  ".join(violations)


SECRETISH_NAMES = ("key", "secret", "token", "password", "passphrase", "credential", "apikey")
"""Substrings that make a *constant* suspicious. Local variables are not checked - a
variable named ``secret`` holding a caller's key is correct code, not a leak."""

PEM_MARKERS = ("BEGIN PRIVATE KEY", "BEGIN RSA PRIVATE KEY", "BEGIN OPENSSH PRIVATE KEY", "BEGIN EC PRIVATE KEY")


def test_no_secrets_or_credentials_are_hardcoded():
    """core/cloud ships on GitHub. Nothing resembling embedded key material may live in it.

    Only module-level constants assigned a literal are flagged: that is what an embedded
    credential actually looks like. Names of locals and parameters are irrelevant.
    """
    violations: list[str] = []

    for path in _modules():
        text = path.read_text(encoding="utf-8")
        for marker in PEM_MARKERS:
            if marker in text:
                violations.append(f"{path.relative_to(SRC)} contains a PEM private key block")

        tree = ast.parse(text, filename=str(path))
        for node in tree.body:  # module level only
            if not isinstance(node, ast.Assign):
                continue
            if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str | bytes):
                continue
            literal = node.value.value
            if len(literal) < 16:  # too short to be a real credential
                continue
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue
                lowered = target.id.lower().replace("_", "")
                if any(word in lowered for word in SECRETISH_NAMES):
                    violations.append(f"{path.relative_to(SRC)}:{node.lineno} constant {target.id} holds a literal")

    assert not violations, "possible secret material in a public package:\n  " + "\n  ".join(violations)
