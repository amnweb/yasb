import logging
from collections.abc import Callable, Mapping
from typing import Any, cast

from pydantic import BaseModel, ValidationError
from PyQt6.QtCore import QObject, QThread

from core.plugins.manifest import PluginError
from core.plugins.resolver import resolve_widget_class
from core.utils.alert_dialog import raise_info_alert
from core.utils.validation_errors import format_pydantic_errors_to_yaml
from core.widgets.base import BaseWidget
from settings import DEFAULT_CONFIG_FILENAME


def _is_grouper(widget_cls: type[BaseWidget]) -> bool:
    return widget_cls.__name__ == "GrouperWidget" and widget_cls.__module__.endswith("yasb.grouper")


class WidgetBuilder(QObject):
    def __init__(self, widget_configs: Mapping[str, Any]):
        super().__init__()
        self._widget_event_listeners: set[type[QThread]] = set()
        self._widget_configurations = widget_configs
        self._missing_widget_types: set[str] = set()
        self._invalid_widget_names: set[str] = set()
        self._invalid_widget_types: dict[str, str] = {}
        self._invalid_widget_options: dict[str, str] = {}
        self._plugin_errors: dict[str, str] = {}

    def build_widgets(self, widget_map: dict[str, list[str]]) -> tuple[dict[str, list[BaseWidget]], set[type[QThread]]]:
        bar_widgets: dict[str, list[BaseWidget]] = {}

        for column, widget_names in widget_map.items():
            built_widgets = [self.build_widget(widget_name) for widget_name in widget_names]
            bar_widgets[column] = [widget for widget in built_widgets if widget is not None]

        return bar_widgets, self._widget_event_listeners

    def build_widget(self, widget_name: str) -> BaseWidget | None:
        widget_config = self._widget_configurations.get(widget_name, None)

        if (widget_name in self._invalid_widget_names) or (widget_name in self._invalid_widget_options):
            logging.warning("Ignoring construction of invalid widget '%s'", widget_name)
        elif not widget_config:
            self._invalid_widget_names.add(widget_name)
            logging.warning("No widget config could be found for widget '%s", widget_name)
        else:
            try:
                widget_cls = resolve_widget_class(widget_config["type"])
                widget_schema = getattr(widget_cls, "validation_schema")
                widget_event_listener = getattr(widget_cls, "event_listener")

                if not widget_schema:
                    raise Exception(f"The widget {widget_cls.__name__} has no validation_schema")

                if widget_event_listener:
                    self._widget_event_listeners.add(widget_event_listener)

                widget_options = widget_config.get("options", {})

                if not (isinstance(widget_schema, type) and issubclass(widget_schema, BaseModel)):
                    raise Exception(
                        f"The widget {widget_cls.__name__} has an invalid validation_schema (must be a Pydantic V2 model)"
                    )

                try:
                    normalized_instance = widget_schema.model_validate(widget_options)
                    normalized_options = normalized_instance.model_dump()
                    pydantic_config = normalized_instance
                except ValidationError as e:
                    validation_errors = format_pydantic_errors_to_yaml(e)
                    indented_validation_errors = f"\n{validation_errors}".replace("\n", "\n      ")
                    self._invalid_widget_options[widget_name] = indented_validation_errors
                    return None

                # If this widget is a Grouper, proactively collect child listeners so BarManager can manage them
                try:
                    if _is_grouper(widget_cls):
                        child_names: list[str] = normalized_options.get("widgets") or []
                        self._collect_nested_listeners(child_names)
                except Exception:
                    logging.debug("WidgetBuilder failed to collect nested listeners for Grouper")

                # Pass widget_configs to GrouperWidget
                widget_factory = cast(Callable[..., BaseWidget], widget_cls)
                if _is_grouper(widget_cls):
                    widget = widget_factory(config=pydantic_config, widget_configs=self._widget_configurations)
                else:
                    widget = widget_factory(config=pydantic_config)
                widget.widget_name = widget_name
                return widget
            except PluginError as e:
                logging.error("Failed to load plugin widget '%s': %s", widget_name, e)
                self._plugin_errors[widget_name] = str(e)
            except AttributeError, ValueError, ModuleNotFoundError:
                logging.exception("Failed to import widget with type %s", widget_config["type"])
                self._invalid_widget_types[widget_name] = widget_config["type"]
            except KeyError:
                logging.exception("No type specified for widget '%s'", widget_name)
                self._missing_widget_types.add(widget_name)
            except Exception:
                logging.exception("Failed to import widget '%s'", widget_name)

    def raise_alerts_if_errors_present(self):
        if self._invalid_widget_names:
            undefined_widgets = "\n".join(
                [f' - The widget "{widget_name}" is undefined.' for widget_name in self._invalid_widget_names]
            )
            logging.error("Failed to add undefined widget(s) %s", undefined_widgets)
            raise_info_alert(
                title=f"Failed to add undefined widget(s) in {DEFAULT_CONFIG_FILENAME}",
                msg="Failed to add undefined widget(s) to bar.",
                informative_msg="Please click 'Show Details' to find out more.",
                additional_details=undefined_widgets,
            )
        if self._invalid_widget_options:
            additional_details = "\n".join(
                [
                    (f" - {widget_name}{validation_errors}")
                    for widget_name, validation_errors in self._invalid_widget_options.items()
                ]
            )
            logging.error("Failed to validate widget(s) due to invalid options %s", additional_details)
            raise_info_alert(
                title=f"Failed to validate widget(s) in {DEFAULT_CONFIG_FILENAME}",
                msg="Failed to validate widget(s) due to invalid options",
                informative_msg="Please click 'Show Details' to find out more.",
                additional_details=additional_details,
            )

        if self._invalid_widget_types:
            widget_names_and_types = "\n".join(
                [
                    f' - {widget_name} has unknown type "{widget_type}"'
                    for widget_name, widget_type in self._invalid_widget_types.items()
                ]
            )
            logging.error("Failed to build widget(s) due to unknown widget type(s) %s", widget_names_and_types)
            raise_info_alert(
                title=f"Failed to build widget(s) in {DEFAULT_CONFIG_FILENAME}",
                msg="Failed to build widget(s) of unknown widget type(s)",
                informative_msg="Click 'Show Details' to find out more.",
                additional_details=widget_names_and_types,
            )
        if self._plugin_errors:
            plugin_errors = "\n".join(
                f" - {widget_name}: {error}" for widget_name, error in self._plugin_errors.items()
            )
            logging.error("Failed to load plugin widget(s) %s", plugin_errors)
            raise_info_alert(
                title=f"Failed to load plugin widget(s) in {DEFAULT_CONFIG_FILENAME}",
                msg="Failed to load widget(s) provided by plugins",
                informative_msg="Click 'Show Details' to find out more.",
                additional_details=plugin_errors,
            )
        if self._missing_widget_types:
            widget_names = "\n".join([f" - {widget_name}" for widget_name in self._missing_widget_types])
            logging.error("Failed to import widget(s) due to missing widget type(s) %s", widget_names)
            raise_info_alert(
                title=f"Failed to import widget(s) in {DEFAULT_CONFIG_FILENAME}",
                msg="Failed to import widget(s) with missing widget type(s)",
                informative_msg="Please click 'Show Details' to find out more.",
                additional_details=f"The following widget(s) have no widget type defined:\n{widget_names}",
            )

    def _collect_nested_listeners(self, widget_names: list[str]) -> None:
        """Recursively collect event listeners from nested widgets."""
        for name in widget_names:
            try:
                cfg = self._widget_configurations.get(name)
                if not cfg or "type" not in cfg:
                    continue
                cls = resolve_widget_class(cfg["type"])
                listener = cls.event_listener
                if listener:
                    self._widget_event_listeners.add(listener)
                # If nested grouper, recurse into its configured child names
                if _is_grouper(cls):
                    child_opts = cfg.get("options", {})
                    child_names: list[str] = child_opts.get("widgets") or []
                    if child_names:
                        self._collect_nested_listeners(child_names)
            except Exception:
                logging.debug("WidgetBuilder skipped collecting listener for nested widget '%s'", name)
