from fnmatch import fnmatchcase

import pytest

from tests.win32 import discovery, known_issues, specs
from tests.win32.probe import MISSING_HEADER_HINT, ProbeResult, constant_key

pytestmark = pytest.mark.sdk

UNDECLARED_HINT = (
    f"Check the spelling. {MISSING_HEADER_HINT} "
    "An undocumented Windows value goes in src/core/utils/win32/undocumented.py; "
    "tests/win32/specs.py:CONSTANTS_NOT_IN_SDK is only for vendor SDK constants in the bindings."
)


@pytest.mark.parametrize("module", sorted(discovery.win32_constants()))
def test_values_match_sdk(module: str, sdk: ProbeResult):
    found: dict[str, str] = {}
    undeclared = False
    for name, value in discovery.win32_constants()[module].items():
        c_name = discovery.sdk_constant_name(name)
        label = name if c_name == name else f"{name} ({c_name})"
        native = sdk.constants.get(c_name)
        listed = module != "core.utils.win32.constants" and specs.constant_not_in_sdk(name) is not None
        if native is None:
            if not listed:
                error = sdk.errors.get(constant_key(c_name))
                found[name] = f"{label} is not declared by the SDK headers" + (f": {error}" if error else "")
                undeclared = True
        elif listed:
            found[name] = f"{label} is declared by the SDK headers, delete it from specs.CONSTANTS_NOT_IN_SDK"
        elif native.get("skip"):
            found[name] = f"{label} is not a number in the SDK headers"
        else:
            mask = (1 << (8 * native["size"])) - 1
            if value & mask != native["value"] & mask:
                found[name] = f"{label} = {value:#x}, the SDK says {native['value'] & mask:#x}"
    known_issues.assert_matches_baseline(
        found,
        known_issues.CONSTANTS.get(module, {}),
        "CONSTANTS",
        module,
        hint=UNDECLARED_HINT if undeclared else "",
    )


def test_constant_aliases_are_used():
    defined = {name for names in discovery.win32_constants().values() for name in names}
    assert not set(specs.CONSTANT_ALIASES) - defined, "specs.CONSTANT_ALIASES lists constants that no longer exist"


def test_constants_not_in_sdk_are_used():
    defined = {name for names in discovery.win32_constants().values() for name in names}
    unused = [pattern for pattern in specs.CONSTANTS_NOT_IN_SDK if not any(fnmatchcase(n, pattern) for n in defined)]
    assert not unused, f"specs.CONSTANTS_NOT_IN_SDK lists patterns no constant matches: {', '.join(unused)}"
