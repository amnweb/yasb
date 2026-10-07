import os
import shutil
import tempfile
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication

_REDIRECTED_ENV = ("YASB_CONFIG_HOME", "LOCALAPPDATA")
_saved_env: dict[str, str | None] = {}
_sandbox: Path | None = None
_qapp: QApplication | None = None


def pytest_configure(config: pytest.Config) -> None:
    # Runs before any test module imports src, so module-level paths such as
    # settings.DEFAULT_CONFIG_DIRECTORY resolve inside the sandbox, never the user's real config.
    global _sandbox
    _sandbox = Path(tempfile.mkdtemp(prefix="yasb-tests-"))
    for name in _REDIRECTED_ENV:
        _saved_env[name] = os.environ.get(name)
        target = _sandbox / name.lower()
        target.mkdir()
        os.environ[name] = str(target)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def pytest_unconfigure(config: pytest.Config) -> None:
    for name, value in _saved_env.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
    if _sandbox is not None:
        shutil.rmtree(_sandbox, ignore_errors=True)


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    global _qapp
    app = QApplication.instance()
    _qapp = app if isinstance(app, QApplication) else QApplication([])
    return _qapp
