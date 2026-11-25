"""Settings copies of YASB's own widgets: the user's file that sets a widget's options and nothing else."""

import re

_PROPERTY = re.compile(r"(?:readonly )?property \S+ (\w+)(?:: (.*))?")


def _statements(lines: list[str], start: int) -> list[list[str]]:
    """What the object opened on line start holds, each line one step in with the lines under it: those further
    in, and those that close its brackets."""
    outer = lines[start][: len(lines[start]) - len(lines[start].lstrip())]
    indent = f"{outer}    "
    statements: list[list[str]] = []
    for line in lines[start + 1 : lines.index(f"{outer}}}", start)]:
        if not line.strip():
            continue
        if statements and not (line.startswith(indent) and line[len(indent)] not in " }])"):
            statements[-1].append(line.removeprefix(indent))
        else:
            statements.append([line.removeprefix(indent)])
    return statements


def _options(text: str) -> list[list[str]] | None:
    """The lines of the widget's component Settings, None for a widget without one."""
    lines = text.splitlines()
    start = next((index for index, line in enumerate(lines) if line.strip() == "component Settings: QtObject {"), None)
    return None if start is None else _statements(lines, start)


def has_settings(text: str) -> bool:
    """Whether the widget's file has a component Settings, which a settings copy needs."""
    return _options(text) is not None


def _setting(first: str, rest: list[str], names: set[str]) -> list[str]:
    """An option as the lines a user's settings block sets it with; none for one with no value, which keeps its
    default."""
    match = _PROPERTY.fullmatch(first)
    if match is None:
        # A part, such as popupFont.pixelSize: 13
        return [first, *rest]
    name, value = match[1], match[2]
    if value is None:
        return []
    # A group, such as popupIcons: PopupIcons {, with its lines as they are
    if value[0].isupper() and value.endswith("{"):
        return [f"{name} {{", *rest]
    return [f"{name}: {f'settings.{value}' if value in names else value}", *rest]


def _copy_text(widget: str, settings: list[list[str]], others: list[list[str]] | None = None) -> str:
    """The user's file: the settings block, then the file's other lines."""
    block = "".join(f"        {line}\n" for statement in settings for line in statement)
    more = "".join(f"    {line}\n" for statement in others or [] for line in statement)
    return (
        f"import Yasb.Widgets\n\n// YASB's {widget} with its settings; change any value here\n"
        f"{widget} {{\n    settings {{\n{block}    }}\n{more}}}\n"
    )


def _copy_statements(text: str) -> list[list[str]] | None:
    options = _options(text)
    if options is None:
        return None
    names = {match[1] for first, *_ in options if (match := _PROPERTY.fullmatch(first))}
    copied: list[list[str]] = []
    comments: list[list[str]] = []
    for first, *rest in options:
        if first.startswith("//"):
            comments.append([first])
            continue
        setting = [] if first.startswith("required ") else _setting(first, rest, names)
        if setting:
            copied += [*comments, setting]
            comments = []
        # An option with no value keeps its comments for its parts set below it
        elif not (match := _PROPERTY.fullmatch(first)) or not any(o[0].startswith(f"{match[1]}.") for o in options):
            comments = []
    return copied


def settings_copy(widget: str, text: str) -> str | None:
    """The user's file of a widget: a settings block with every option of its component Settings that has a value,
    the value and the comments above it as written; None for a widget without one."""
    statements = _copy_statements(text)
    return None if statements is None else _copy_text(widget, statements)


def _setting_name(line: str) -> str | None:
    """The option a line of a settings block sets, such as apps for apps {; None for a comment."""
    match = re.match(r"([\w.]+)\s*[:{]", line)
    return match[1] if match else None


def refresh_copy(widget: str, old: str, text: str) -> tuple[str, list[str]]:
    """A fresh settings copy of the built-in widget whose file is text, with each option old's settings block sets
    put back where it still exists, and old's other lines kept; returns the copy and the options that no longer
    exist."""
    lines = old.splitlines()
    start = next(index for index, line in enumerate(lines) if re.match(rf"{widget}\s*\{{$", line))
    kept: dict[str, list[str]] = {}
    others: list[list[str]] = []
    for statement in _statements(lines, start):
        if re.fullmatch(r"settings\s*\{", statement[0]):
            kept |= {name: inner for inner in _statements(statement, 0) if (name := _setting_name(inner[0]))}
        else:
            others.append(statement)
    statements = _copy_statements(text) or []
    for index, statement in enumerate(statements):
        statements[index] = kept.pop(_setting_name(statement[0]) or "", statement)
    return _copy_text(widget, statements, others), list(kept)
