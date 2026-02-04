from typing import Any

WIDGET_REGISTRY: dict[str, Any] = {}


def register_widget_class(cls: type[Any]):
    """
    Register a widget class in the global registry.
    The key is generated based on the class module and name.
    """
    module = cls.__module__
    # Remove 'core.widgets.' prefix if present
    if module.startswith("core.widgets."):
        module = module.replace("core.widgets.", "")

    key = f"{module}.{cls.__name__}"
    WIDGET_REGISTRY[key] = cls
