import argparse
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, NoReturn, TextIO

HELP = "Print help"


@dataclass(frozen=True)
class Option:
    flags: tuple[str, ...]
    help: str
    # The placeholder of an option that takes a value, such as SCREEN; None for an on/off flag
    value: str | None = None
    value_type: type = str
    default: Any = None


@dataclass(frozen=True)
class Argument:
    name: str
    help: str
    optional: bool = False
    many: bool = False
    choices: tuple[str, ...] = ()
    dest: str | None = None


@dataclass(frozen=True)
class Command:
    name: str
    help: str
    arguments: tuple[Argument, ...] = ()
    options: tuple[Option, ...] = ()
    commands: tuple[Command, ...] = ()
    # Hands everything after its name, -h included, to a parser of its own
    passthrough: bool = False


def _styles(stream: TextIO) -> tuple[str, str, str, str]:
    """Header, literal, error and reset codes; empty when the stream isn't a terminal or NO_COLOR is set."""
    if not stream.isatty() or "NO_COLOR" in os.environ:
        return "", "", "", ""
    return "\033[1;4m", "\033[1m", "\033[1;31m", "\033[0m"


def _commands(command: Command) -> tuple[Command, ...]:
    if not command.commands:
        return ()
    help_command = Command(
        "help",
        "Print this message or the help of the given command",
        arguments=(Argument("command", "", optional=True, many=True, dest="help_path"),),
    )
    return (*command.commands, help_command)


def _options(command: Command) -> tuple[Option, ...]:
    return () if command.passthrough else (*command.options, Option(("-h", "--help"), HELP))


def _placeholder(argument: Argument) -> str:
    name = argument.name.upper()
    if argument.many:
        return f"[{name}]..."
    return f"[{name}]" if argument.optional else f"<{name}>"


def _flags(option: Option) -> str:
    flags = ", ".join(option.flags)
    # A long flag alone lines up with the long flags after a short one
    if all(flag.startswith("--") for flag in option.flags):
        flags = f"    {flags}"
    return f"{flags} <{option.value}>" if option.value else flags


def _possible_values(argument: Argument) -> str:
    return f" [possible values: {', '.join(argument.choices)}]" if argument.choices else ""


def usage(command: Command, prog: str) -> str:
    parts = [prog]
    if _options(command):
        parts.append("[OPTIONS]")
    parts += [_placeholder(argument) for argument in command.arguments]
    if command.commands:
        parts.append("[COMMAND]")
    return " ".join(parts)


def help_text(command: Command, prog: str, stream: TextIO) -> str:
    header, literal, _, reset = _styles(stream)

    def section(title: str, rows: list[tuple[str, str]]) -> str:
        width = max(len(name) for name, _ in rows)
        lines = (f"  {literal}{name}{reset}{' ' * (width - len(name))}  {text}".rstrip() for name, text in rows)
        return f"\n{header}{title}:{reset}\n" + "\n".join(lines) + "\n"

    text = f"{command.help}\n\n{header}Usage:{reset} {literal}{prog}{reset}"
    text += usage(command, prog).removeprefix(prog) + "\n"
    if commands := _commands(command):
        text += section("Commands", [(sub.name, sub.help) for sub in commands])
    if command.arguments:
        rows = [(_placeholder(argument), argument.help + _possible_values(argument)) for argument in command.arguments]
        text += section("Arguments", rows)
    if options := _options(command):
        text += section("Options", [(_flags(option), option.help) for option in options])
    return text


def _find(root: Command, path: Sequence[str]) -> tuple[Command, str] | None:
    command, prog = root, root.name
    for name in path:
        found = next((sub for sub in _commands(command) if sub.name == name), None)
        if found is None:
            return None
        command, prog = found, f"{prog} {name}"
    return command, prog


def print_help(root: Command, path: Sequence[str] = ()) -> int:
    """Prints the help of the command path names under root, or an error for a name that isn't one."""
    found = _find(root, path)
    if found is None:
        _print_error(f"no command '{' '.join(path)}'", usage(root, root.name), f"{root.name} --help")
        return 2
    print(help_text(*found, sys.stdout), end="")
    return 0


def _print_error(message: str, usage_line: str, more: str) -> None:
    header, literal, error, reset = _styles(sys.stderr)
    print(
        f"{error}error:{reset} {message}\n\n{header}Usage:{reset} {usage_line}\n\n"
        f"For more information, try '{literal}{more}{reset}'.",
        file=sys.stderr,
    )


class YasbArgumentParser(argparse.ArgumentParser):
    yasb_command: Command | None = None
    yasb_prog: str = ""

    def error(self, message: str) -> NoReturn:
        command = self.yasb_command
        usage_line = usage(command, self.yasb_prog) if command else self.yasb_prog
        _print_error(message, usage_line, "--help")
        sys.exit(2)


def _help_action(command: Command, prog: str) -> type[argparse.Action]:
    class PrintHelp(argparse.Action):
        def __call__(self, parser: argparse.ArgumentParser, namespace: argparse.Namespace, *_: Any) -> None:
            print(help_text(command, prog, sys.stdout), end="")
            sys.exit(0)

    return PrintHelp


def _fill(parser: YasbArgumentParser, command: Command, prog: str, dest: str) -> None:
    parser.yasb_command, parser.yasb_prog = command, prog
    if command.passthrough:
        return
    for option in command.options:
        if option.value is None:
            parser.add_argument(*option.flags, action="store_true", help=option.help)
        else:
            parser.add_argument(
                *option.flags,
                type=option.value_type,
                default=option.default,
                metavar=option.value,
                help=option.help,
            )
    parser.add_argument("-h", "--help", action=_help_action(command, prog), nargs=0, help=HELP)
    for argument in command.arguments:
        nargs = "*" if argument.many else "?" if argument.optional else None
        parser.add_argument(
            argument.dest or argument.name,
            nargs=nargs,
            choices=argument.choices or None,
            metavar=f"<{argument.name.upper()}>",
            help=argument.help,
        )
    if commands := _commands(command):
        subparsers = parser.add_subparsers(dest=dest, metavar="<COMMAND>")
        for sub in commands:
            child = subparsers.add_parser(sub.name, add_help=False, color=False)
            _fill(child, sub, f"{prog} {sub.name}", f"{sub.name}_command")


def build(root: Command) -> YasbArgumentParser:
    parser = YasbArgumentParser(prog=root.name, add_help=False, color=False)
    _fill(parser, root, root.name, "command")
    return parser
