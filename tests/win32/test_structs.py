import ctypes

import pytest

from tests.win32 import abi, discovery, known_issues, specs
from tests.win32.known_issues import xfail_if_known
from tests.win32.probe import MISSING_HEADER_HINT, ProbeResult, field_key, struct_key

pytestmark = pytest.mark.sdk


def _params():
    for cls in discovery.ctypes_structs():
        key = discovery.type_id(cls)
        yield pytest.param(cls, id=key, marks=xfail_if_known(known_issues.STRUCTS, key))


@pytest.mark.parametrize("cls", list(_params()))
def test_layout_matches_sdk(cls: type[ctypes.Structure | ctypes.Union], sdk: ProbeResult):
    key = discovery.type_id(cls)
    spec = specs.struct_spec(key, cls.__name__)
    if struct_key(key) in sdk.errors:
        vendored = isinstance(spec, specs.Vendored)
        where = "specs.VENDORED_DECLARATIONS" if vendored else "the SDK headers"
        hint = "" if vendored else f" {MISSING_HEADER_HINT}"
        pytest.fail(
            f"{spec.c_type} is not declared by {where}: {sdk.errors[struct_key(key)]}\n"
            f"Name the class after its SDK type, or map it in tests/win32/specs.py:STRUCTS.{hint}",
            pytrace=False,
        )

    native = sdk.structs[key]
    problems: list[str] = []
    fields_match = True
    for name, ctype in discovery.struct_fields(cls):
        target = spec.fields.get(name, name)
        if target is None:
            continue
        offset_only = isinstance(target, specs.Offset)
        member = target.member if offset_only else target
        if field_key(key, name) in sdk.errors:
            problems.append(f"{name}: {spec.c_type} has no member {member!r}; map it in specs.py:STRUCTS")
            fields_match = False
            continue
        c_field = sdk.fields[key][name]
        offset = getattr(cls, name).offset
        if offset != c_field["offset"]:
            problems.append(f"{name}: offset {offset}, the SDK has {member} at {c_field['offset']}")
            fields_match = False
        if not offset_only:
            native_abi = abi.Abi.from_json(c_field["abi"])
            python_abi = abi.of(ctype, opaque=discovery.is_prefix_struct)
            reason = abi.mismatch(python_abi, native_abi, check_sign=False)
            if reason:
                problems.append(f"{name}: {abi.describe(ctype)} is {python_abi}, {member} is {native_abi}: {reason}")
                fields_match = False

    size = ctypes.sizeof(cls)
    prefix = isinstance(spec, specs.Sdk) and spec.prefix
    if size != native["size"] and not (prefix and size < native["size"]):
        hint = ""
        if fields_match and size < native["size"]:
            hint = " (every field matches, so members are missing after the last one)"
        problems.append(f"sizeof is {size}, the SDK's {spec.c_type} is {native['size']}{hint}")

    if problems:
        pytest.fail(f"{key} does not match {spec.c_type}:\n  " + "\n  ".join(problems), pytrace=False)
