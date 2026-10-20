import json
from pathlib import Path

from core.plugins.manifest import (
    MANIFEST_FILENAME,
    PLUGIN_API_VERSION,
    PluginError,
    PluginManifest,
    plugin_widget_type,
    version_tuple,
)
from settings import BUILD_VERSION

_WIDGET = """\
from PyQt6.QtWidgets import QLabel

from yasb_api import BaseWidget, WidgetConfig


class {config_class}(WidgetConfig):
    label: str = {label}


class {widget_class}(BaseWidget):
    validation_schema = {config_class}

    def __init__(self, config: {config_class}):
        super().__init__(class_name="{css_class}")
        self.label = QLabel(config.label)
        self.label.setProperty("class", "label")
        self.widget_layout.addWidget(self.label)
"""

_README = """\
# {name}

{description}

## Configuration

Add the widget to `config.yaml`, then put `{widget_key}` on a bar:

```yaml
widgets:
  {widget_key}:
    type: "{widget_type}"
    options:
      label: {label}
```

| Option | Type | Default | Description |
|---|---|---|---|
| `label` | string | `{label}` | The text the widget shows. |

## Styling

Add this to `styles.css` and change it as you like:

```css
.{css_class} .label {{
    padding: 0 4px;
}}
```
"""


def widget_class_name(plugin_id: str) -> str:
    return "".join(part.capitalize() for part in plugin_id.split("-")) + "Widget"


def create_plugin(root: Path, plugin_id: str, name: str, author: str, description: str) -> Path:
    directory = root / plugin_id
    if directory.exists():
        raise PluginError(f"{directory} already exists")
    widget_class = widget_class_name(plugin_id)
    widget_key = f"plugin-{plugin_id}"
    manifest = PluginManifest(
        id=plugin_id,
        name=name,
        version="0.1.0",
        author=author,
        description=description,
        api=str(PLUGIN_API_VERSION),
        min_yasb=".".join(str(part) for part in version_tuple(BUILD_VERSION)),
        widgets={widget_class: f"widget:{widget_class}"},
    )
    values = {
        "name": name,
        "description": description,
        "widget_key": widget_key,
        "widget_type": plugin_widget_type(plugin_id, widget_class),
        "widget_class": widget_class,
        "config_class": widget_class.removesuffix("Widget") + "Config",
        "css_class": widget_key,
        "label": json.dumps(name, ensure_ascii=False),
    }
    files = {
        MANIFEST_FILENAME: json.dumps(manifest.model_dump(), indent=2, ensure_ascii=False) + "\n",
        "widget.py": _WIDGET.format(**values),
        "README.md": _README.format(**values),
    }
    directory.mkdir(parents=True)
    for filename, text in files.items():
        (directory / filename).write_text(text, encoding="utf-8")
    return directory
