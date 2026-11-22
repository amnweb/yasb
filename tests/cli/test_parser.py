import inspect
import io

import pytest

import cli
from core.cli.parser import Command, build, help_text, print_help
from core.cloud import cli as cloud_cli


@pytest.mark.parametrize(
    ("root", "argv", "expected"),
    [
        (cli.YASBC, ["addons", "copy", "clock", "--full"], {"addons_command": "copy", "name": "clock", "full": True}),
        (cli.YASBC, ["addons", "update"], {"addons_command": "update", "id": None, "all": False}),
        (cli.YASBC, ["show-bar", "-s", "DP1"], {"command": "show-bar", "screen": "DP1"}),
        (cli.YASBC, ["set-channel", "preview"], {"command": "set-channel", "target_channel": "preview"}),
        (cli.YASBC, ["help", "addons", "copy"], {"command": "help", "help_path": ["addons", "copy"]}),
        (cloud_cli.CLOUD, ["list", "-p", "2"], {"command": "list", "page": 2, "search": ""}),
        (cloud_cli.CLOUD, ["restore", "latest", "-y"], {"command": "restore", "backup": "latest", "yes": True}),
    ],
)
def test_arguments_land_where_the_dispatch_reads_them(root: Command, argv: list[str], expected: dict[str, object]):
    args = vars(build(root).parse_args(argv))
    assert {name: args[name] for name in expected} == expected


def test_help_lists_usage_arguments_and_options_in_padded_columns():
    set_channel = next(command for command in cli.YASBC.commands if command.name == "set-channel")
    assert help_text(set_channel, "yasbc set-channel", io.StringIO()) == (
        "Switch release channels\n"
        "\n"
        "Usage: yasbc set-channel [OPTIONS] <TARGET_CHANNEL>\n"
        "\n"
        "Arguments:\n"
        "  <TARGET_CHANNEL>  'stable' for tested releases or 'preview' for the latest updates"
        " [possible values: stable, preview]\n"
        "\n"
        "Options:\n"
        "  -h, --help  Print help\n"
    )


def test_dash_h_prints_help_before_a_missing_argument_is_an_error(capsys: pytest.CaptureFixture[str]):
    with pytest.raises(SystemExit) as exit_:
        build(cli.YASBC).parse_args(["addons", "copy", "-h"])
    assert exit_.value.code == 0
    assert "Usage: yasbc addons copy [OPTIONS] <NAME>" in capsys.readouterr().out


def test_help_finds_a_command_by_its_path(capsys: pytest.CaptureFixture[str]):
    assert print_help(cli.YASBC, ["addons", "copy"]) == 0
    assert capsys.readouterr().out.startswith("Copy a widget's settings")
    assert print_help(cli.YASBC, ["nope"]) == 2
    assert "error: no command 'nope'" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("argv", "usage"),
    [
        (["addons", "nope"], "yasbc addons [OPTIONS] [COMMAND]"),
        (["addons", "copy"], "yasbc addons copy [OPTIONS] <NAME>"),
    ],
)
def test_errors_show_the_usage_of_the_command_they_happened_in(
    argv: list[str], usage: str, capsys: pytest.CaptureFixture[str]
):
    with pytest.raises(SystemExit) as exit_:
        build(cli.YASBC).parse_args(argv)
    assert exit_.value.code == 2
    err = capsys.readouterr().err
    assert err.startswith("error: ")
    assert err.endswith(f"\n\nUsage: {usage}\n\nFor more information, try '--help'.\n")


def test_every_listed_command_has_a_handler():
    dispatch = inspect.getsource(cli.CLIHandler.parse_arguments)
    addons = next(command for command in cli.YASBC.commands if command.name == "addons")
    names = [command.name for command in (*cli.YASBC.commands, *addons.commands)]
    assert [name for name in names if f'"{name}"' not in dispatch] == []
    cloud_dispatch = inspect.getsource(cloud_cli.run)
    assert [command.name for command in cloud_cli.CLOUD.commands if f'"{command.name}"' not in cloud_dispatch] == []
