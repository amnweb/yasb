import logging
import os
import re
import shutil
import sys
from os import makedirs, path
from pathlib import Path
from sys import argv, exit
from typing import Union
from xml.dom import SyntaxErr

from cerberus import Validator, schema
from yaml import dump, safe_load
from yaml.parser import ParserError

import settings
from core.utils.alert_dialog import raise_info_alert
from core.utils.css_processor import CSSProcessor
from core.validation.config import CONFIG_SCHEMA

SRC_CONFIGURATION_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(argv[0])
HOME_CONFIGURATION_DIR = path.join(Path.home(), settings.DEFAULT_CONFIG_DIRECTORY)
HOME_STYLES_PATH = path.normpath(path.join(HOME_CONFIGURATION_DIR, settings.DEFAULT_STYLES_FILENAME))
HOME_CONFIG_PATH = path.normpath(path.join(HOME_CONFIGURATION_DIR, settings.DEFAULT_CONFIG_FILENAME))
DEFAULT_STYLES_PATH = path.normpath(path.join(SRC_CONFIGURATION_DIR, settings.DEFAULT_STYLES_FILENAME))
DEFAULT_CONFIG_PATH = path.normpath(path.join(SRC_CONFIGURATION_DIR, settings.DEFAULT_CONFIG_FILENAME))
GITHUB_ISSUES_URL = f"{settings.GITHUB_URL}/issues"


class ConfigValidationError(TypeError):
    def __init__(self, message: str, errors: str, filetype: str, filepath: str):
        super().__init__(message)
        self.errors = errors
        self.filetype = filetype
        self.filepath = filepath


try:
    yaml_validator = Validator(CONFIG_SCHEMA)
except schema.SchemaError:
    logging.exception("Failed to load configuration schema for yaml validator.")


def get_config_dir() -> str:
    if path.isdir(HOME_CONFIGURATION_DIR):
        return HOME_CONFIGURATION_DIR
    else:
        try:
            makedirs(HOME_CONFIGURATION_DIR)
            return HOME_CONFIGURATION_DIR
        except OSError:
            logging.error(f"Failed to create configuration directory at {HOME_CONFIGURATION_DIR}.")
            return SRC_CONFIGURATION_DIR


def get_config_path() -> str:
    if path.isdir(HOME_CONFIGURATION_DIR) and path.isfile(HOME_CONFIG_PATH):
        return HOME_CONFIG_PATH
    elif not path.isfile(HOME_CONFIG_PATH):
        # Create default config file if it doesn't exist
        if not path.isdir(HOME_CONFIGURATION_DIR):
            makedirs(HOME_CONFIGURATION_DIR)
        shutil.copy2(DEFAULT_CONFIG_PATH, HOME_CONFIG_PATH)
        logging.info(f"Created default config file at {HOME_CONFIG_PATH}")
        return HOME_CONFIG_PATH
    else:
        return DEFAULT_CONFIG_PATH


def get_stylesheet_path() -> str:
    if path.isdir(HOME_CONFIGURATION_DIR) and path.isfile(HOME_STYLES_PATH):
        return HOME_STYLES_PATH
    elif not path.isfile(HOME_STYLES_PATH):
        # Create default stylesheet if it doesn't exist
        if not path.isdir(HOME_CONFIGURATION_DIR):
            makedirs(HOME_CONFIGURATION_DIR)
        shutil.copy2(DEFAULT_STYLES_PATH, HOME_STYLES_PATH)
        logging.info(f"Created default stylesheet at {HOME_STYLES_PATH}")
        return HOME_STYLES_PATH
    else:
        return DEFAULT_STYLES_PATH


def parse_env(obj):
    """
    Recursively expand $env:VARIABLE_NAME or $Env:VARIABLE_NAME patterns in strings,
    dicts, and lists.
    """
    if isinstance(obj, dict):
        return {k: parse_env(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [parse_env(item) for item in obj]
    elif isinstance(obj, str):
        pattern = r"\$env:([\w_]+)"

        def repl(match):
            var = match.group(1)
            return os.environ.get(var, "")

        obj = re.sub(pattern, repl, obj, flags=re.IGNORECASE)
    return obj


def get_config(show_error_dialog=False) -> Union[dict, None]:
    config_path = get_config_path()

    try:
        with open(config_path, encoding="utf-8") as yaml_stream:
            config = safe_load(yaml_stream)

        if yaml_validator.validate(config, CONFIG_SCHEMA):
            return parse_env(yaml_validator.normalized(config))
        else:
            pretty_errors = dump(yaml_validator.errors)
            logging.error(f"The config file '{config_path}' contains validation errors. Please fix:\n{pretty_errors}")
            if show_error_dialog:
                raise_info_alert(
                    title="Failed to load recently updated config file.",
                    msg=f"The file '{config_path}' contains validation error(s) and has not been loaded.",
                    informative_msg="For more information, click 'Show Details'.",
                    additional_details=pretty_errors,
                )
    except ParserError as e:
        logging.error(f"The file '{config_path}' contains Parser Error(s). Please fix:\n{str(e)}")
    except FileNotFoundError:
        logging.error(f"The file '{config_path}' could not be found. Does it exist?")
    except OSError:
        logging.error(f"The file '{config_path}' could not be read. Do you have read/write permissions?")


def get_stylesheet(show_error_dialog=False) -> Union[str, None]:
    styles_path = get_stylesheet_path()
    try:
        css_processor = CSSProcessor(styles_path)
        css_content = css_processor.process()
        return css_content

    except SyntaxErr as e:
        logging.error(f"The file '{styles_path}' contains Syntax Error(s). Please fix:\n{str(e)}")
        if show_error_dialog:
            raise_info_alert(
                title="Failed to load recently updated stylesheet file.",
                msg=f"The file '{styles_path}' contains syntax error(s) and has not been loaded.",
                informative_msg="For more information, click 'Show Details'.",
                additional_details=str(e),
            )
    except FileNotFoundError:
        logging.error(f"The file '{styles_path}' could not be found. Does it exist?")
    except OSError:
        logging.error(f"The file '{styles_path}' could not be read. Do you have read/write permissions?")
    return None


def get_config_and_stylesheet() -> tuple[dict, str]:
    config = get_config()
    stylesheet = get_stylesheet()

    if not config:
        error_msg = "User config file could not be loaded. Exiting Application."
    elif not stylesheet:
        error_msg = "User stylesheet could not be loaded. Exiting Application."
    elif not config["bars"]:
        error_msg = "No bars have been configured. Please edit the config to add a status bar."
    else:
        return config, stylesheet

    if error_msg:
        logging.error(error_msg)
        exit(1)
