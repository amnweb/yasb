import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

from core.plugins.manifest import PluginError, PluginManifest, plugin_widget_type
from settings import DEFAULT_CONFIG_DIRECTORY, DEFAULT_CONFIG_FILENAME


@dataclass(frozen=True)
class AddedWidget:
    name: str
    widget_type: str
    bar: str | None


def config_path() -> Path:
    return Path(DEFAULT_CONFIG_DIRECTORY) / DEFAULT_CONFIG_FILENAME


def _compose(text: str, what: str = "config.yaml") -> MappingNode | None:
    try:
        node = cast(Node | None, yaml.compose(text, Loader=yaml.SafeLoader))  # pyright: ignore[reportUnknownMemberType]
    except yaml.YAMLError as e:
        raise PluginError(f"{what} is not valid YAML: {e}") from e
    if node is None:
        return None
    if not isinstance(node, MappingNode):
        raise PluginError(f"{what} must be a mapping at the top level")
    return node


def _get(mapping: MappingNode, key: str) -> tuple[ScalarNode, Node] | None:
    for key_node, value_node in mapping.value:
        if isinstance(key_node, ScalarNode) and key_node.value == key:
            return key_node, value_node
    return None


def _block_mapping(node: Node, where: str) -> MappingNode:
    if not isinstance(node, MappingNode) or node.flow_style:
        raise PluginError(f"{where} in config.yaml is not a block mapping, so it can't be edited automatically")
    return node


def _is_empty(node: Node) -> bool:
    return isinstance(node, ScalarNode) and node.value == "" and node.start_mark.index == node.end_mark.index


def _end(node: Node) -> int:
    if isinstance(node, MappingNode) and not node.flow_style and node.value:
        key, value = node.value[-1]
        return _end(key) if _is_empty(value) else _end(value)
    if isinstance(node, SequenceNode) and not node.flow_style and node.value:
        return _end(node.value[-1])
    return node.end_mark.index


def _line_start(text: str, index: int) -> int:
    return text.rfind("\n", 0, index) + 1


def _after_line(text: str, index: int) -> int:
    while index > 0 and text[index - 1] in " \t\r\n":
        index -= 1
    newline = text.find("\n", index)
    return len(text) if newline == -1 else newline + 1


def _insert_lines(text: str, index: int, lines: list[str], newline: str) -> str:
    block = "".join(line + newline for line in lines)
    if index == len(text) and text and not text.endswith("\n"):
        block = newline + block
    return text[:index] + block + text[index:]


def _newline(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def _widget_name(widget_class: str) -> str:
    base = widget_class.removesuffix("Widget") or widget_class
    return re.sub(r"(?<!^)(?=[A-Z])", "_", base).lower()


def _quoted(name: str, like: Node | None) -> str:
    style = like.style if isinstance(like, ScalarNode) else '"'
    if style == "'":
        return f"'{name}'"
    if style is None and re.fullmatch(r"[A-Za-z_][\w-]*", name):
        return name
    return f'"{name}"'


def _entry_type(value: Node) -> str | None:
    if isinstance(value, MappingNode) and (entry := _get(value, "type")) and isinstance(entry[1], ScalarNode):
        return entry[1].value
    return None


def _example_entry(manifest: PluginManifest, directory: Path) -> tuple[str, str, list[str]] | None:
    if not manifest.example_config or not (path := directory / manifest.example_config).is_file():
        return None
    example = path.read_text(encoding="utf-8")
    root = _compose(example, "the plugin's example config")
    if root is None:
        return None
    for key, value in root.value:
        widget_type = _entry_type(value) or ""
        if (
            isinstance(key, ScalarNode)
            and widget_type.removeprefix(plugin_widget_type(manifest.id, "")) in manifest.widgets
        ):
            start = _line_start(example, key.start_mark.index)
            body = [
                line[key.start_mark.column :]
                for line in example[start : _after_line(example, _end(value))].splitlines()
            ]
            key_text = example[key.start_mark.index : key.end_mark.index]
            return key.value, widget_type, [body[0][len(key_text) :], *body[1:]]
    return None


def _definition(manifest: PluginManifest, directory: Path) -> tuple[str, str, list[str]]:
    if entry := _example_entry(manifest, directory):
        return entry
    widget_class = next(iter(manifest.widgets))
    widget_type = plugin_widget_type(manifest.id, widget_class)
    return _widget_name(widget_class), widget_type, [":", f'  type: "{widget_type}"']


def _first_bar(root: MappingNode | None) -> tuple[str, MappingNode] | None:
    entry = _get(root, "bars") if root else None
    if entry is None or not isinstance(entry[1], MappingNode):
        return None
    for key, bar in entry[1].value:
        if not isinstance(key, ScalarNode) or not isinstance(bar, MappingNode):
            continue
        enabled = _get(bar, "enabled")
        if (
            enabled is None
            or not isinstance(enabled[1], ScalarNode)
            or enabled[1].value.lower() not in ("false", "no", "off")
        ):
            return key.value, bar
    return None


def widget_types(text: str) -> dict[str, str]:
    root = _compose(text)
    entry = _get(root, "widgets") if root else None
    if entry is None or not isinstance(entry[1], MappingNode):
        return {}
    return {
        key.value: widget_type
        for key, value in entry[1].value
        if isinstance(key, ScalarNode) and (widget_type := _entry_type(value))
    }


def plugin_widget_names(text: str, plugin_id: str) -> list[str]:
    return [
        name
        for name, widget_type in widget_types(text).items()
        if widget_type.startswith(plugin_widget_type(plugin_id, ""))
    ]


def _add_definition(text: str, name: str, body: list[str]) -> tuple[str, str]:
    newline = _newline(text)
    root = _compose(text)
    entry = _get(root, "widgets") if root else None
    taken: set[str] = set()
    if entry and not _is_empty(entry[1]):
        taken = {key.value for key, _ in _block_mapping(entry[1], "widgets").value if isinstance(key, ScalarNode)}
    unique, number = name, 2
    while unique in taken:
        unique, number = f"{name}_{number}", number + 1
    lines = [unique + body[0], *body[1:]]
    if entry is None:
        return _insert_lines(text, len(text), ["widgets:", *(f"  {line}" for line in lines)], newline), unique
    key, value = entry
    if _is_empty(value):
        indented = [f"  {line}" if line else "" for line in lines]
        return _insert_lines(text, _after_line(text, key.end_mark.index), indented, newline), unique
    mapping = _block_mapping(value, "widgets")
    pad = " " * mapping.value[0][0].start_mark.column
    indented = [pad + line if line else "" for line in lines]
    return _insert_lines(text, _after_line(text, _end(mapping)), indented, newline), unique


def _add_first_on_left(text: str, name: str, bar: str, bar_value: MappingNode) -> str:
    newline = _newline(text)
    bar_node = _block_mapping(bar_value, f"bars.{bar}")
    widgets_entry = _get(bar_node, "widgets")
    if widgets_entry is None:
        pad = " " * bar_node.value[0][0].start_mark.column
        lines = [f"{pad}widgets:", f'{pad}  left: ["{name}"]']
        return _insert_lines(text, _after_line(text, _end(bar_node)), lines, newline)
    widgets_key, widgets_value = widgets_entry
    if _is_empty(widgets_value):
        pad = " " * (widgets_key.start_mark.column + 2)
        return _insert_lines(text, _after_line(text, widgets_key.end_mark.index), [f'{pad}left: ["{name}"]'], newline)
    widgets = _block_mapping(widgets_value, f"bars.{bar}.widgets")
    left = _get(widgets, "left")
    if left is None:
        first_key = widgets.value[0][0]
        pad = " " * first_key.start_mark.column
        return _insert_lines(text, _line_start(text, first_key.start_mark.index), [f'{pad}left: ["{name}"]'], newline)
    left_key, items = left
    if _is_empty(items):
        colon = text.index(":", left_key.end_mark.index) + 1
        return f'{text[:colon]} ["{name}"]{text[colon:]}'
    if not isinstance(items, SequenceNode):
        raise PluginError(f"bars.{bar}.widgets.left in config.yaml is not a list")
    first = items.value[0] if items.value else None
    if items.flow_style:
        open_bracket = items.start_mark.index + 1
        separator = ", " if first else ""
        return f"{text[:open_bracket]}{_quoted(name, first)}{separator}{text[open_bracket:]}"
    if first is None:
        raise PluginError(f"bars.{bar}.widgets.left in config.yaml is an empty list")
    line_start = _line_start(text, first.start_mark.index)
    prefix = text[line_start : first.start_mark.index]
    return _insert_lines(text, line_start, [prefix + _quoted(name, first)], newline)


def add_widget(text: str, manifest: PluginManifest, directory: Path) -> tuple[str, AddedWidget | None]:
    if plugin_widget_names(text, manifest.id):
        return text, None
    default_name, widget_type, body = _definition(manifest, directory)
    text, name = _add_definition(text, default_name, body)
    found = _first_bar(_compose(text))
    if found is None:
        return text, AddedWidget(name, widget_type, None)
    bar, bar_value = found
    return _add_first_on_left(text, name, bar, bar_value), AddedWidget(name, widget_type, bar)


def remove_plugin_widgets(text: str, plugin_id: str) -> tuple[str, list[str]]:
    names = set(plugin_widget_names(text, plugin_id))
    root = _compose(text)
    if not names or root is None:
        return text, []
    spans: list[tuple[int, int, str]] = []
    widgets_entry = _get(root, "widgets")
    if widgets_entry:
        widgets = _block_mapping(widgets_entry[1], "widgets")
        for key, value in widgets.value:
            if isinstance(key, ScalarNode) and key.value in names:
                spans.append((_line_start(text, key.start_mark.index), _after_line(text, _end(value)), ""))
    bars_entry = _get(root, "bars")
    if bars_entry and isinstance(bars_entry[1], MappingNode):
        for _, bar in bars_entry[1].value:
            bar_widgets = _get(bar, "widgets") if isinstance(bar, MappingNode) else None
            if bar_widgets is None or not isinstance(bar_widgets[1], MappingNode):
                continue
            for _, items in bar_widgets[1].value:
                if not isinstance(items, SequenceNode):
                    continue
                removed = [item for item in items.value if isinstance(item, ScalarNode) and item.value in names]
                if not removed:
                    continue
                if items.flow_style:
                    kept = [text[i.start_mark.index : i.end_mark.index] for i in items.value if i not in removed]
                    spans.append((items.start_mark.index, items.end_mark.index, f"[{', '.join(kept)}]"))
                else:
                    for item in removed:
                        spans.append((_line_start(text, item.start_mark.index), _after_line(text, _end(item)), ""))
    for start, end, replacement in sorted(spans, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text, sorted(names)


def edit_config[T](path: Path, edit: Callable[[str], tuple[str, T]]) -> T:
    with open(path, encoding="utf-8", newline="") as file:
        text = file.read()
    new_text, result = edit(text)
    if new_text != text:
        try:
            yaml.safe_load(new_text)
        except yaml.YAMLError as e:
            raise PluginError(f"editing config.yaml would make it invalid, so it was left unchanged: {e}") from e
        shutil.copyfile(path, path.with_name(path.name + ".bak"))
        with open(path, "w", encoding="utf-8", newline="") as file:
            file.write(new_text)
    return result
