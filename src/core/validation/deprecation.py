"""Centralized deprecation registry and CLI migration tool.

All deprecated or renamed config fields are registered here - both for
runtime warnings (handle_deprecated_fields) and CLI migration (migrate_config).

Adding a new deprecation
------------------------

1. Field removed from ALL widgets/models (global):

    DEPRECATED_FIELDS = {
        "label_shadow": "Use CSS text-shadow instead.",
    }

2. Field removed from a SPECIFIC model only (scoped):

    SCOPED_DEPRECATED_FIELDS = {
        "HomeConfig": {
            "container_padding": "Use CSS padding instead.",
        },
    }

3. Field renamed in a SPECIFIC model (scoped):

    SCOPED_RENAMED_FIELDS = {
        "MenuLabelsConfig": {
            "logout": ("log_out", "Use 'log_out' instead."),
        },
    }

4. Field renamed in ALL models (global):

    RENAMED_FIELDS = {
        "old_name": ("new_name", "Use 'new_name' instead."),
    }

The class name key (e.g. "HomeConfig", "BarBlurEffect") must match
the Pydantic model's __name__ exactly.
"""

import logging
from importlib import import_module
from typing import Any

from yaml import safe_load

logger = logging.getLogger("deprecation")

# Global - removed from any model that doesn't recognize it
DEPRECATED_FIELDS: dict[str, str] = {
    "container_padding": "Use CSS padding instead.",
}

RENAMED_FIELDS: dict[str, tuple[str, str]] = {}

# Scoped - keyed by class name (for runtime)
SCOPED_DEPRECATED_FIELDS: dict[str, dict[str, str]] = {
    "BarBlurEffect": {
        "acrylic": "No longer supported and can be removed from the config.",
    },
    "BarAlignment": {
        "center": "Use 'align' instead.",
    },
    "VSCodeMenuConfig": {
        "distance": "Use 'offset_top' instead.",
    },
    "BrightnessMenuConfig": {
        "distance": "Use 'offset_top' instead.",
    },
    "ClockCalendarConfig": {
        "distance": "Use 'offset_top' instead.",
    },
    "GroupLabelConfig": {
        "distance": "Use 'offset_top' instead.",
    },
    "MenuConfig": {
        "distance": "Use 'offset_top' instead.",
    },
    "AudioMenuConfig": {
        "distance": "Use 'offset_top' instead.",
    },
    "WeatherCardConfig": {
        "distance": "Use 'offset_top' instead.",
    },
    "HomeConfig": {
        "distance": "Use 'offset_top' instead.",
    },
}

SCOPED_RENAMED_FIELDS: dict[str, dict[str, tuple[str, str]]] = {}


def handle_deprecated_fields(cls: type, data: Any) -> Any:
    """Runtime handler - called by model_validator on CustomBaseModel."""
    if not isinstance(data, dict):
        return data
    cls_name = cls.__name__
    deprecated = {**DEPRECATED_FIELDS, **SCOPED_DEPRECATED_FIELDS.get(cls_name, {})}
    renamed = {**RENAMED_FIELDS, **SCOPED_RENAMED_FIELDS.get(cls_name, {})}
    for key in list(data.keys()):
        if key in cls.model_fields:
            continue
        if key in deprecated:
            logger.warning("[DEPRECATED] %s: '%s' - %s", cls_name, key, deprecated[key])
            del data[key]
        elif key in renamed:
            new_name, message = renamed[key]
            logger.warning("[DEPRECATED] %s: '%s' renamed to '%s' - %s", cls_name, key, new_name, message)
            if new_name not in data:
                data[new_name] = data[key]
            del data[key]
    return data


def _check(data: dict, path: str, class_name: str, issues: list[dict]):
    """Check dict keys against global + scoped deprecated/renamed for *class_name*."""
    deprecated = {**DEPRECATED_FIELDS, **SCOPED_DEPRECATED_FIELDS.get(class_name, {})}
    renamed = {**RENAMED_FIELDS, **SCOPED_RENAMED_FIELDS.get(class_name, {})}
    for key in data:
        kp = f"{path}.{key}"
        if key in deprecated:
            issues.append({"path": kp, "key": key, "action": "remove", "message": deprecated[key]})
        elif key in renamed:
            new_name, msg = renamed[key]
            issues.append({"path": kp, "key": key, "action": "rename", "new_name": new_name, "message": msg})


def _check_model(data: dict, path: str, model: type, issues: list[dict]):
    """Check data against a Pydantic model and recurse into its sub-models."""
    import typing

    _check(data, path, model.__name__, issues)
    for name, field in model.model_fields.items():
        ann = field.annotation
        val = data.get(name)
        if isinstance(ann, type) and hasattr(ann, "model_fields"):
            if isinstance(val, dict):
                _check_model(val, f"{path}.{name}", ann, issues)
        elif args := typing.get_args(ann):
            inner = args[0]
            if isinstance(inner, type) and hasattr(inner, "model_fields") and isinstance(val, list):
                for i, item in enumerate(val):
                    if isinstance(item, dict):
                        _check_model(item, f"{path}.{name}[{i}]", inner, issues)


def _scan(config: dict) -> list[dict]:
    """Walk parsed YAML and collect all deprecated/renamed fields."""
    from core.validation.bar import BarConfig

    issues: list[dict] = []

    for bar_name, bar in (config.get("bars") or {}).items():
        if isinstance(bar, dict):
            _check_model(bar, f"bars.{bar_name}", BarConfig, issues)

    for wname, wdata in (config.get("widgets") or {}).items():
        if not isinstance(wdata, dict):
            continue
        try:
            mod, cls_name = wdata.get("type", "").rsplit(".", 1)
            schema = getattr(import_module(f"core.widgets.{mod}"), cls_name).validation_schema
        except Exception:
            continue
        opts = wdata.get("options")
        if isinstance(opts, dict):
            _check_model(opts, f"widgets.{wname}.options", schema, issues)

    return issues


def _patch(raw: str, issues: list[dict]) -> str:
    """Remove/rename lines in raw text matched by exact YAML path."""
    issue_paths = {i["path"]: i for i in issues}
    lines = raw.splitlines(True)
    result: list[str] = []
    path_stack: list[tuple[int, str]] = []
    skip_indent = -1

    for line in lines:
        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        if skip_indent >= 0:
            if not stripped or indent > skip_indent:
                continue
            skip_indent = -1

        if stripped.strip() and ":" in stripped:
            while path_stack and path_stack[-1][0] >= indent:
                path_stack.pop()
            key = stripped.split(":")[0].strip().strip("- ")
            if key:
                path_stack.append((indent, key))

        current_path = ".".join(k for _, k in path_stack)

        if current_path in issue_paths:
            issue = issue_paths[current_path]
            if issue["action"] == "remove":
                skip_indent = indent
                path_stack.pop()
                continue
            if issue["action"] == "rename":
                line = line.replace(issue["key"], issue["new_name"], 1)

        result.append(line)

    return "".join(result)


def migrate_config(raw: str) -> tuple[str, list[dict]]:
    """Find and fix deprecated fields. safe_load to find, text to save."""
    config = safe_load(raw)
    if not isinstance(config, dict):
        return raw, []
    issues = _scan(config)
    if not issues:
        return raw, []
    return _patch(raw, issues), issues
