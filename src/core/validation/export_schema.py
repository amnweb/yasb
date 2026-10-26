import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from core.validation.config import YasbConfig


def export_schema():
    with open("schema.json", "w") as f:
        json.dump(YasbConfig.model_json_schema(), f, indent=2)


if __name__ == "__main__":
    export_schema()
