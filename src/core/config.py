import logging
import os
import re
import sys
from os import makedirs, path
from typing import Any, cast

from pydantic import ValidationError
from yaml import safe_load
from yaml.parser import ParserError

from core.utils.alert_dialog import raise_info_alert
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


def get_config(show_error_dialog: bool = False) -> YasbConfig | None:
    config_path = get_config_path()

    try:
        with open(config_path, encoding="utf-8") as yaml_stream:
            config = safe_load(yaml_stream)

        if config is None:
            config = {}

        try:
            # Parse environment variables in raw config
            config = parse_env(config)

            # Validate and normalize with Pydantic
            validated_config = YasbConfig(**cast(dict[str, Any], config if isinstance(config, dict) else {}))

            # Return as dict for compatibility with the rest of the app
            return validated_config

        except ValidationError as e:
            validation_errors = format_pydantic_errors_to_yaml(e)
            logging.error(
                "The config file '%s' contains validation errors. Please fix:\n%s",
                config_path,
                validation_errors,
            )
            if show_error_dialog:
                raise_info_alert(
                    title="Failed to load recently updated config file.",
                    msg=f"The file '{config_path}' contains validation error(s) and has not been loaded.",
                    informative_msg="For more information, click 'Show Details'.",
                    additional_details=validation_errors,
                )
            return None
    except ParserError as e:
        logging.error("The file '%s' contains Parser Error(s). Please fix:\n%s", config_path, e)
    except FileNotFoundError:
        logging.error("The file '%s' could not be found. Does it exist?", config_path)
    except OSError:
        logging.error("The file '%s' could not be read. Do you have read/write permissions?", config_path)


def load_config() -> YasbConfig:
    config = get_config()
    if config is None:
        logging.error("User config file could not be loaded. Exiting Application.")
        sys.exit(1)
    if not config.bars:
        logging.error("No bars have been configured. Please edit the config to add a status bar.")
        sys.exit(1)
    return config
