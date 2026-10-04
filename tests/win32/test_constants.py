import pytest

from tests.win32 import discovery, known_issues, specs
from tests.win32.probe import ProbeResult

pytestmark = pytest.mark.sdk


@pytest.mark.parametrize("module", sorted(discovery.win32_constants()))
def test_values_match_sdk(module: str, sdk: ProbeResult):
    found = {}
    for name, value in discovery.win32_constants()[module].items():
        c_name = discovery.sdk_constant_name(name)
        native = sdk.constants.get(c_name)
        if native is None:
            if name in specs.CONSTANT_ALIASES:
                found[name] = f"{name}: its alias {c_name} is not declared by the SDK headers"
            continue
        mask = (1 << (8 * native["size"])) - 1
        if value & mask != native["value"] & mask:
            label = name if c_name == name else f"{name} ({c_name})"
            found[name] = f"{label} = {value:#x}, the SDK says {native['value'] & mask:#x}"
    known_issues.assert_matches_baseline(found, known_issues.CONSTANTS.get(module, {}), "CONSTANTS", module)


def test_constant_aliases_are_used():
    defined = {name for names in discovery.win32_constants().values() for name in names}
    assert not set(specs.CONSTANT_ALIASES) - defined, "specs.CONSTANT_ALIASES lists constants that no longer exist"
