import importlib

import pytest

from tests.support.source import SourceModule, core_modules


@pytest.mark.parametrize("module", core_modules(), ids=lambda module: module.name)
def test_module_imports(module: SourceModule):
    importlib.import_module(module.name)
