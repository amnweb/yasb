import hashlib
import json
import os
from pathlib import Path

import pytest

from tests.win32 import discovery
from tests.win32.msvc import ToolchainMissing, find_toolchain
from tests.win32.probe import ProbeResult, run_probe

_CACHE_KEY = "yasb/win32-sdk-probe"
_PROBE_SOURCES = ("probe.py", "msvc.py", "specs.py")
_TOOLCHAIN = pytest.StashKey[str]()


def _sdk_required() -> bool:
    return os.environ.get("YASB_REQUIRE_SDK", "") not in ("", "0")


def _fingerprint(toolchain_description: str, requests: discovery.ProbeRequests) -> str:
    digest = hashlib.sha256(toolchain_description.encode())
    for name in _PROBE_SOURCES:
        digest.update((Path(__file__).parent / name).read_bytes())
    digest.update(json.dumps(requests, default=lambda o: o.__dict__, sort_keys=True).encode())
    return digest.hexdigest()


@pytest.fixture(scope="session")
def sdk(request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory) -> ProbeResult:
    try:
        toolchain = find_toolchain()
    except ToolchainMissing as exc:
        if _sdk_required():
            pytest.fail(f"YASB_REQUIRE_SDK is set but the Windows SDK toolchain is unavailable: {exc}")
        pytest.skip(f"MSVC with the Windows SDK is not installed ({exc}); CI runs these checks")

    request.config.stash[_TOOLCHAIN] = toolchain.description
    requests = discovery.probe_requests()
    fingerprint = _fingerprint(toolchain.description, requests)
    cache = getattr(request.config, "cache", None)
    cached = cache.get(_CACHE_KEY, None) if cache else None
    if cached and cached.get("fingerprint") == fingerprint:
        return ProbeResult.from_json(cached["result"])

    result = run_probe(toolchain, tmp_path_factory.mktemp("sdk-probe"), **requests)
    if cache:
        cache.set(_CACHE_KEY, {"fingerprint": fingerprint, "result": result.to_json()})
    return result


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter, config: pytest.Config) -> None:
    toolchain = config.stash.get(_TOOLCHAIN, None)
    if toolchain:
        terminalreporter.write_line(f"Windows SDK checks: {toolchain}")
