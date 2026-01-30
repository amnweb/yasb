import importlib
import json
import os
import sys
from typing import Literal, Union

from pydantic import BaseModel, create_model

# Add src to sys.path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from core.validation.config import YasbConfig
from core.widgets.registry import WIDGET_REGISTRY


def import_all_widgets():
    """
    Walk through the widgets directory and import all modules.
    This triggers the __init_subclass__ hook in BaseWidget,
    populating WIDGET_REGISTRY.
    """
    widgets_path = os.path.join(os.path.dirname(__file__), "../widgets")
    widgets_path = os.path.abspath(widgets_path)

    for root, _dirs, files in os.walk(widgets_path):
        for file in files:
            if file.endswith(".py") and file != "__init__.py":
                # Construct module path
                rel_path = os.path.relpath(os.path.join(root, file), widgets_path)
                module_name = "core.widgets." + rel_path.replace(os.sep, ".")[:-3]

                try:
                    importlib.import_module(module_name)
                except Exception as e:
                    print(f"Failed to import {module_name}: {e}", file=sys.stderr)


def export_schema():
    """Export the combined schema for YasbConfig and all registered widgets"""
    # 1. Trigger Auto-Registration
    import_all_widgets()

    mappings: list[tuple[str, type[BaseModel]]] = []

    # 2. Iterate over registry to find widgets with validation schemas
    for type_str, widget_cls in WIDGET_REGISTRY.items():
        if hasattr(widget_cls, "validation_schema"):
            schema = widget_cls.validation_schema

            # Ensure schema is a Pydantic model and not None
            # Using basic check here as imports might be tricky with aliases
            if schema and hasattr(schema, "model_json_schema"):
                mappings.append((type_str, schema))

    print(f"Found {len(mappings)} registered widgets with validation schemas.", file=sys.stderr)

    widget_entry_models: list[type[BaseModel]] = []

    if not mappings:
        print("Warning: No registered widgets found.", file=sys.stderr)
        WidgetEntryUnion = dict
    else:
        for type_str, config_class in mappings:
            # Create a model for this specific widget type
            # class MyWidgetEntry(BaseModel):
            #     type: Literal["yasb.brightness.BrightnessWidget"]
            #     options: BrightnessConfig

            model_name = config_class.__name__.replace("Config", "Entry")

            entry_model = create_model(
                model_name,
                type=(Literal[type_str], ...),
                options=(config_class, ...),
            )
            widget_entry_models.append(entry_model)

        WidgetEntryUnion = Union[tuple(widget_entry_models)]

    # Create a new model for export that overrides the widgets field
    class ExportYasbConfig(YasbConfig):
        widgets: dict[str, WidgetEntryUnion]  # type: ignore

    schema = ExportYasbConfig.model_json_schema()

    # in case stdout output is needed
    # print(json.dumps(schema, indent=2))

    # save the schema to a file
    with open("schema.json", "w") as f:
        json.dump(schema, f, indent=2)


if __name__ == "__main__":
    export_schema()
