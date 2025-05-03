import os
import logging
from dotenv import load_dotenv


def get_env_path():
    config_home = os.environ.get("YASB_CONFIG_HOME")
    if config_home:
        return os.path.join(config_home, ".env")
    return os.path.join(os.path.expanduser("~"), ".config", "yasb", ".env")


def load_env():
    """
    Load environment variables from a env_file file specified in the YASB configuration.
    """
    env_path = get_env_path()
    if os.path.isfile(env_path):
        if not load_dotenv(env_path):
            logging.warning(f"Failed to load environment variables from {env_path}")
    else:
        logging.info(f"No env file found at {env_path}, skipping environment loading.")
