"""Problems these tests found in src/ that are not fixed yet.

Each entry keeps CI green while the problem stays on record. An entry that no longer reproduces fails
the run until it is deleted, so this file can only shrink: fix the code, then remove the line.
"""

from collections.abc import Iterable

import pytest

# Foreign function declarations that disagree with the SDK prototype, by "Function@module".
SIGNATURES: dict[str, str] = {}

# ctypes structures whose layout disagrees with the SDK, by "module.Class".
STRUCTS: dict[str, str] = {}

# comtypes interfaces whose vtable disagrees with the SDK, by "module.Class".
INTERFACES: dict[str, str] = {}

# Constants whose value disagrees with the SDK, by module then name.
CONSTANTS: dict[str, dict[str, str]] = {}

# Names looked up on a DLL that does not export them, by library then name.
EXPORTS: dict[str, dict[str, str]] = {}

# Calls without restype whose result ctypes reads with the wrong size, by module.
UNDECLARED: dict[str, tuple[str, ...]] = {}


def xfail_if_known(table: dict[str, str], key: str) -> tuple[pytest.MarkDecorator, ...]:
    if key not in table:
        return ()
    reason = f"known issue: {table[key]} (if this passes now, delete {key!r} from tests/win32/known_issues.py)"
    return (pytest.mark.xfail(reason=reason, strict=True),)


def assert_matches_baseline(
    found: dict[str, str], known: Iterable[str], table: str, scope: str, *, hint: str = ""
) -> None:
    known = set(known)
    new = [message for name, message in sorted(found.items()) if name not in known]
    stale = sorted(known - found.keys())
    lines = list(new)
    if stale:
        lines.append(f"fixed now, delete from tests/win32/known_issues.py {table}[{scope!r}]: {', '.join(stale)}")
    if new and hint:
        lines += ["", hint]
    if lines:
        pytest.fail("\n".join(lines), pytrace=False)
