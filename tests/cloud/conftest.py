import pytest

UNREACHABLE_API = "http://127.0.0.1:9"


@pytest.fixture(autouse=True)
def offline_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("core.cloud.api.API_BASE_URL", UNREACHABLE_API)
