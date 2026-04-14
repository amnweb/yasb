import yaml
from pydantic import ValidationError


def format_pydantic_errors_to_yaml(exc: ValidationError) -> str:
    """Format a Pydantic ValidationError to a YAML string."""
    tree = {}
    for error in exc.errors():
        current = tree
        loc = error["loc"]

        # Walk through the path (e.g., ('nested', 0, 'field'))
        for i, part in enumerate(loc):
            # If we are at the last part, it's the actual error location
            if i == len(loc) - 1:
                if part not in current:
                    current[part] = []
                # Handle cases where Pydantic returns multiple errors for one field
                current[part].append(error["msg"])
            else:
                # If the path doesn't exist, create a dict for the next level
                if part not in current or not isinstance(current[part], dict):
                    current[part] = {}
                current = current[part]

    return yaml.dump(tree, default_flow_style=False, sort_keys=False)
