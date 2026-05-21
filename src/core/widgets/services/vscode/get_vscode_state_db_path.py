import json
import logging
import os


def get_state_db_path() -> str:
    product_json_path = find_vscode_product_json()
    try:
        if os.path.exists(product_json_path):
            with open(product_json_path, encoding="utf-8") as f:
                product = json.load(f)

            shared_folder = product.get("sharedDataFolderName")
            if shared_folder:
                shared_path = os.path.join(os.path.expanduser("~"), shared_folder, "sharedStorage", "state.vscdb")

                if os.path.exists(shared_path):
                    return shared_path
    except Exception as e:
        logging.error("Shared storage detection failed: %s", e)

    return os.path.expandvars(r"%APPDATA%\Code\User\globalStorage\state.vscdb")


def find_vscode_product_json() -> str | None:
    base_path = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code")

    if not os.path.exists(base_path):
        return None

    try:
        candidates = []
        for name in os.listdir(base_path):
            full_path = os.path.join(base_path, name)
            product_path = os.path.join(full_path, "resources", "app", "product.json")

            if os.path.isfile(product_path):
                candidates.append((os.path.getmtime(full_path), product_path))

        if not candidates:
            return None

        candidates.sort(reverse=True)
        return candidates[0][1]

    except Exception as e:
        logging.error("Failed to locate VSCode product.json: %s", e)
        return None
