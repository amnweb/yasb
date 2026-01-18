DEFAULTS = {
    "label": "\uf489",
    "container_padding": {"top": 0, "left": 4, "bottom": 0, "right": 0},
    "blur": True,
    "round_corners": True,
    "round_corners_type": "small",
    "border_color": "None",
    "alignment": "left",
    "direction": "down",
    "offset_top": 6,
    "offset_left": 0,
    "shield_icon": "\ud83d\udee1",  # 🛡 Unicode shield icon
    "terminal_list": [
        {"name": "Git Bash", "path": "C:\\Program Files\\Git\\git-bash.exe"},
        {"name": "Git GUI", "path": "C:\\Program Files\\Git\\cmd\\git-gui.exe"},
        {"name": "Git CMD", "path": "C:\\Program Files\\Git\\git-cmd.exe"},
        {"name": "CMD", "path": "cmd.exe"},
        {"name": "PowerShell", "path": "powershell.exe"},
    ],
    "animation": {"enabled": True, "type": "fadeInOut", "duration": 200},
    "callbacks": {"on_left": "toggle_menu"},
}

VALIDATION_SCHEMA = {
    "label": {"type": "string", "default": DEFAULTS["label"]},
    "terminal_list": {
        "required": False,
        "type": "list",
        "schema": {
            "type": "dict",
            "schema": {
                "name": {"type": "string", "required": True},
                "path": {"type": "string", "required": True},
                "icon": {"type": "string", "required": False},  # Optional custom icon per terminal
            },
        },
        "default": DEFAULTS["terminal_list"],
    },
    "container_padding": {
        "type": "dict",
        "required": False,
        "schema": {
            "top": {"type": "integer", "default": DEFAULTS["container_padding"]["top"]},
            "left": {"type": "integer", "default": DEFAULTS["container_padding"]["left"]},
            "bottom": {"type": "integer", "default": DEFAULTS["container_padding"]["bottom"]},
            "right": {"type": "integer", "default": DEFAULTS["container_padding"]["right"]},
        },
        "default": DEFAULTS["container_padding"],
    },
    "blur": {"type": "boolean", "default": DEFAULTS["blur"], "required": False},
    "round_corners": {"type": "boolean", "default": DEFAULTS["round_corners"], "required": False},
    "round_corners_type": {"type": "string", "default": DEFAULTS["round_corners_type"], "required": False},
    "border_color": {"type": "string", "default": DEFAULTS["border_color"], "required": False},
    "alignment": {"type": "string", "default": DEFAULTS["alignment"], "required": False},
    "direction": {"type": "string", "default": DEFAULTS["direction"], "required": False},
    "offset_top": {"type": "integer", "default": DEFAULTS["offset_top"], "required": False},
    "offset_left": {"type": "integer", "default": DEFAULTS["offset_left"], "required": False},
    "shield_icon": {"type": "string", "default": DEFAULTS["shield_icon"], "required": False},
    "animation": {
        "type": "dict",
        "required": False,
        "schema": {
            "enabled": {"type": "boolean", "default": DEFAULTS["animation"]["enabled"]},
            "type": {"type": "string", "default": DEFAULTS["animation"]["type"]},
            "duration": {"type": "integer", "default": DEFAULTS["animation"]["duration"]},
        },
        "default": DEFAULTS["animation"],
    },
    "label_shadow": {
        "type": "dict",
        "required": False,
        "schema": {
            "enabled": {"type": "boolean", "default": False},
            "color": {"type": "string", "default": "black"},
            "offset": {"type": "list", "default": [1, 1]},
            "radius": {"type": "integer", "default": 3},
        },
        "default": {"enabled": False, "color": "black", "offset": [1, 1], "radius": 3},
    },
    "container_shadow": {
        "type": "dict",
        "required": False,
        "schema": {
            "enabled": {"type": "boolean", "default": False},
            "color": {"type": "string", "default": "black"},
            "offset": {"type": "list", "default": [1, 1]},
            "radius": {"type": "integer", "default": 3},
        },
        "default": {"enabled": False, "color": "black", "offset": [1, 1], "radius": 3},
    },
    "callbacks": {
        "required": False,
        "type": "dict",
        "schema": {"on_left": {"type": "string", "default": DEFAULTS["callbacks"]["on_left"]}},
        "default": DEFAULTS["callbacks"],
    },
}
