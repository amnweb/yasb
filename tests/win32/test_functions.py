from collections.abc import Iterable
from typing import cast

import pytest

from tests.win32 import abi, discovery, known_issues, specs
from tests.win32.discovery import Binding
from tests.win32.known_issues import xfail_if_known
from tests.win32.probe import MISSING_HEADER_HINT, ProbeResult, function_key

pytestmark = pytest.mark.sdk


def _params():
    for binding in discovery.foreign_bindings():
        function = binding.function
        if function.ordinal or specs.not_in_sdk(function.name):
            continue
        yield pytest.param(binding, id=binding.id, marks=xfail_if_known(known_issues.SIGNATURES, binding.id))


def _evaluate(binding: Binding, attr: str) -> object:
    try:
        return discovery.evaluate(binding, getattr(binding, attr))
    except Exception as exc:
        pytest.fail(f"cannot evaluate {binding.function.name}.{attr} at {binding.sites[-1]}: {exc!r}")


@pytest.mark.parametrize("binding", list(_params()))
def test_signature_matches_sdk(binding: Binding, sdk: ProbeResult):
    name = binding.function.name
    key = function_key(name)
    if key in sdk.errors:
        pytest.fail(
            f"{name} is not declared by the SDK headers: {sdk.errors[key]}\n"
            f"Check the spelling. {MISSING_HEADER_HINT} "
            "Only an undocumented function goes in tests/win32/specs.py:NOT_IN_SDK.",
            pytrace=False,
        )

    native = sdk.functions[name]
    sites = ", ".join(str(site) for site in binding.sites)
    problems: list[str] = []

    if binding.restype is not None:
        restype = _evaluate(binding, "restype")
        python_ret, native_ret = abi.of(restype), abi.Abi.from_json(native["ret"])
        if not (python_ret.kind == "v" and native_ret.kind != "v"):
            reason = abi.mismatch(python_ret, native_ret, check_sign=True)
            if reason:
                problems.append(
                    f"restype {abi.describe(restype)} is {python_ret}, the SDK returns {native_ret}: {reason}"
                )

    if binding.argtypes is not None:
        argtypes = list(cast(Iterable[object], _evaluate(binding, "argtypes")))
        native_args = [abi.Abi.from_json(arg) for arg in native["args"]]
        if len(argtypes) != len(native_args) and not (native["variadic"] and len(argtypes) > len(native_args)):
            problems.append(f"argtypes has {len(argtypes)} entries, the SDK takes {len(native_args)} parameters")
        for index, (ctype, native_arg) in enumerate(zip(argtypes, native_args)):
            python_arg = abi.of(ctype, argument=True, opaque=discovery.is_prefix_struct)
            reason = abi.mismatch(python_arg, native_arg, check_sign=False)
            if reason:
                problems.append(
                    f"argument {index}: {abi.describe(ctype)} is {python_arg}, the SDK takes {native_arg}: {reason}"
                )

    if problems:
        pytest.fail(f"{name} declared at {sites}:\n  " + "\n  ".join(problems), pytrace=False)
