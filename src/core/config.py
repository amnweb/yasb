import logging
import os
import re
from os import makedirs, path
from typing import Any, cast

from pydantic import ValidationError
from yaml import YAMLError, safe_load

from core.utils.alert_dialog import show_alert
from core.utils.validation_errors import format_pydantic_errors_to_yaml
from core.validation.config import YasbConfig
from settings import DEFAULT_CONFIG_DIRECTORY, DEFAULT_CONFIG_FILENAME, DEFAULT_STYLES_FILENAME, GITHUB_URL

HOME_CONFIGURATION_DIR = DEFAULT_CONFIG_DIRECTORY
HOME_STYLES_PATH = path.normpath(path.join(HOME_CONFIGURATION_DIR, DEFAULT_STYLES_FILENAME))
HOME_CONFIG_PATH = path.normpath(path.join(HOME_CONFIGURATION_DIR, DEFAULT_CONFIG_FILENAME))
GITHUB_ISSUES_URL = f"{GITHUB_URL}/issues"


class ConfigValidationError(TypeError):
    def __init__(self, message: str, errors: str, filetype: str, filepath: str):
        super().__init__(message)
        self.errors = errors
        self.filetype = filetype
        self.filepath = filepath


def is_first_run() -> bool:
    """Return True when neither config file nor stylesheet exist yet."""
    return not path.isfile(HOME_CONFIG_PATH) and not path.isfile(HOME_STYLES_PATH)


def get_config_dir() -> str:
    if path.isdir(HOME_CONFIGURATION_DIR):
        return HOME_CONFIGURATION_DIR
    try:
        makedirs(HOME_CONFIGURATION_DIR)
        return HOME_CONFIGURATION_DIR
    except OSError:
        logging.error("Failed to create configuration directory at %s.", HOME_CONFIGURATION_DIR)
        return HOME_CONFIGURATION_DIR


def get_config_path() -> str:
    return HOME_CONFIG_PATH


def parse_env(obj: Any) -> Any:
    """
    Recursively expand $env:VARIABLE_NAME or $Env:VARIABLE_NAME patterns in strings,
    dicts, and lists.
    """
    if isinstance(obj, dict):
        return {k: parse_env(v) for k, v in cast(dict[Any, Any], obj).items()}
    elif isinstance(obj, list):
        return [parse_env(item) for item in cast(list[Any], obj)]
    elif isinstance(obj, str):
        pattern = r"\$env:([\w_]+)"

        def repl(match: re.Match[str]) -> str:
            var = match.group(1)
            return os.environ.get(var, "")

        obj = re.sub(pattern, repl, obj, flags=re.IGNORECASE)
    return obj


class ConfigError(Exception):
    """The config can't be used: the message says why and details holds the errors."""

    def __init__(self, message: str, details: str = ""):
        super().__init__(message)
        self.details = details


def read_config() -> YasbConfig:
    config_path = get_config_path()
    try:
        with open(config_path, encoding="utf-8") as yaml_stream:
            config = safe_load(yaml_stream)
    except FileNotFoundError:
        raise ConfigError(f"The file '{config_path}' could not be found.") from None
    except OSError as e:
        raise ConfigError(f"The file '{config_path}' could not be read.", str(e)) from None
    except YAMLError as e:
        raise ConfigError(f"The file '{config_path}' is not valid YAML.", str(e)) from None
    try:
        config = parse_env(config or {})
        return YasbConfig(**cast(dict[str, Any], config if isinstance(config, dict) else {}))
    except ValidationError as e:
        raise ConfigError(
            f"The file '{config_path}' contains validation error(s).", format_pydantic_errors_to_yaml(e)
        ) from None


def get_config(show_error_dialog: bool = False) -> YasbConfig | None:
    try:
        return read_config()
    except ConfigError as e:
        logging.error("%s\n%s", e, e.details)
        if show_error_dialog:
            show_alert(
                title="Failed to load recently updated config file.",
                message=f"{e} It has not been loaded.",
                details=e.details,
            )
        return None


def load_config() -> YasbConfig:
    config = read_config()
    if not config.bars:
        raise ConfigError("No bars are configured. Add a bar to config.yaml.")
    return config
