import re
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

PLUGIN_API_VERSION = 1
MANIFEST_FILENAME = "manifest.json"
PLUGIN_TYPE_PREFIX = "plugins."
PLUGIN_ID_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
DESCRIPTION_MAX_LENGTH = 70
_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"


class PluginError(Exception):
    pass


def is_plugin_id(value: str) -> bool:
    return re.fullmatch(PLUGIN_ID_PATTERN, value) is not None


def plugin_slug(plugin_id: str) -> str:
    return plugin_id.replace("-", "_")


def plugin_widget_type(plugin_id: str, widget_class: str) -> str:
    return f"{PLUGIN_TYPE_PREFIX}{plugin_id}.{widget_class}"


def plugin_id_of(widget_type: str) -> str | None:
    if not widget_type.startswith(PLUGIN_TYPE_PREFIX):
        return None
    plugin_id, _, widget_class = widget_type.removeprefix(PLUGIN_TYPE_PREFIX).partition(".")
    return plugin_id if plugin_id and widget_class and "." not in widget_class else None


def version_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", version)[:3])


type WidgetName = Annotated[str, StringConstraints(pattern=rf"^{_IDENTIFIER}$")]
type EntryPoint = Annotated[str, StringConstraints(pattern=rf"^{_IDENTIFIER}(?:\.{_IDENTIFIER})*:{_IDENTIFIER}$")]


class PluginManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(pattern=PLUGIN_ID_PATTERN)
    name: str = Field(min_length=1)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
    author: str = Field(min_length=1)
    description: str = Field(min_length=1, max_length=DESCRIPTION_MAX_LENGTH)
    api: str = Field(pattern=r"^\d+$")
    min_yasb: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    widgets: dict[WidgetName, EntryPoint] = Field(min_length=1)

    @property
    def slug(self) -> str:
        return plugin_slug(self.id)
