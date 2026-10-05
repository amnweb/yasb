import pytest

from tests.win32 import abi, discovery, known_issues, specs
from tests.win32.known_issues import xfail_if_known
from tests.win32.probe import MISSING_HEADER_HINT, ProbeResult, method_key, vtable_key

pytestmark = pytest.mark.sdk


def _params():
    for cls in discovery.com_interfaces():
        key = discovery.type_id(cls)
        if key not in specs.UNDOCUMENTED_INTERFACES:
            yield pytest.param(cls, id=key, marks=xfail_if_known(known_issues.INTERFACES, key))


@pytest.mark.parametrize("cls", list(_params()))
def test_vtable_matches_sdk(cls: type, sdk: ProbeResult):
    key = discovery.type_id(cls)
    c_interface = specs.COM_INTERFACES.get(key, cls.__name__)
    if vtable_key(key) in sdk.errors:
        pytest.fail(
            f"{c_interface} is not declared by the SDK headers: {sdk.errors[vtable_key(key)]}\n"
            f"Map it in tests/win32/specs.py:COM_INTERFACES. {MISSING_HEADER_HINT} "
            "Only an undocumented interface goes in UNDOCUMENTED_INTERFACES.",
            pytrace=False,
        )

    native_methods = sdk.methods.get(key, {})
    problems = []
    for method in discovery.com_methods(cls):
        if method_key(key, method.c_name) in sdk.errors:
            problems.append(f"slot {method.index}: {c_interface} has no method {method.c_name}")
            continue
        native = native_methods[method.c_name]
        if native["index"] != method.index:
            problems.append(f"{method.c_name} is vtable slot {method.index} in Python, {native['index']} in the SDK")
            continue
        native_ret = abi.Abi.from_json(native["ret"])
        reason = abi.mismatch(abi.of(method.restype), native_ret, check_sign=True)
        if reason and method.restype is not None:
            problems.append(
                f"{method.c_name} returns {abi.describe(method.restype)}, the SDK returns {native_ret}: {reason}"
            )
        native_args = [abi.Abi.from_json(arg) for arg in native["args"][1:]]
        if len(method.argtypes) != len(native_args):
            problems.append(f"{method.c_name} takes {len(method.argtypes)} arguments, the SDK takes {len(native_args)}")
            continue
        for index, (ctype, native_arg) in enumerate(zip(method.argtypes, native_args)):
            python_arg = abi.of(ctype, argument=True, opaque=discovery.is_prefix_struct)
            reason = abi.mismatch(python_arg, native_arg, check_sign=False)
            if reason:
                problems.append(f"{method.c_name} argument {index}: {abi.describe(ctype)} vs {native_arg}: {reason}")

    if problems:
        pytest.fail(f"{key} does not match {c_interface}:\n  " + "\n  ".join(problems), pytrace=False)
