import os
import logging
import yaml
from dotenv import load_dotenv


def get_config_path():
    config_home = os.environ.get("YASB_CONFIG_HOME")
    if config_home:
        return os.path.join(config_home, "config.yaml")
    return os.path.join(os.path.expanduser("~"), ".config", "yasb", "config.yaml")


def get_resolved_env_file_path(env_file):
    if os.path.isabs(env_file):
        return env_file
    config_dir = os.path.dirname(get_config_path())
    return os.path.join(config_dir, env_file)


def load_env():
    """
    Load environment variables from a env_file file specified in the YASB configuration.
    """
    config_path = get_config_path()
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)
        env_file = config_data.get("env_file")
        if env_file:
            env_path = get_resolved_env_file_path(env_file)
            if not load_dotenv(env_path):
                logging.warning(f"Failed to load environment variables from {env_path}")
    except Exception as e:
        logging.warning(f"Could not load env file from config: {e}")
