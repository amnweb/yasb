import pytest
from pydantic import BaseModel

from tests.support.source import import_core_modules


def _registered_widgets():
    import_core_modules()
    from core.widgets.registry import WIDGET_REGISTRY

    return [pytest.param(widget, id=name) for name, widget in sorted(WIDGET_REGISTRY.items())]


@pytest.mark.parametrize("widget", _registered_widgets())
def test_widget_has_a_config_schema(widget: type):
    schema = getattr(widget, "validation_schema", None)
    assert isinstance(schema, type) and issubclass(schema, BaseModel), (
        f"{widget.__qualname__}.validation_schema is not a pydantic model"
    )
    schema.model_json_schema()


def test_yasb_config_schema_builds():
    from core.validation.config import YasbConfig

    YasbConfig.model_json_schema()
