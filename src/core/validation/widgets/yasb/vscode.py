DEFAULTS = {
    "label": "<span>\udb82\ude1e</span>",
    "label_alt": "<span>\udb82\ude1e</span> recents",
    "menu_title": "<span style='font-weight:bold'>VScode</span> recents",
    "folder_icon": "\uf114",
    "file_icon": "\uf016",
    "hide_folder_icon": False,
    "hide_file_icon": False,
    "truncate_to_root_dir": False,
    "max_number_of_folders": 30,
    "max_number_of_files": 30,
    "max_field_size": 100,
    "modified_date_format": "Date modified: %Y-%m-%d %H:%M",
    "cli_command": "code",
    "menu": {
        "blur": True,
        "round_corners": True,
        "round_corners_type": "normal",
        "border_color": "System",
        "alignment": "right",
        "direction": "down",
        "distance": 6,  # deprecated
        "offset_top": 6,
        "offset_left": 0,
    },
    "animation": {"enabled": True, "type": "fadeInOut", "duration": 200},
    "container_padding": {"top": 0, "left": 0, "bottom": 0, "right": 0},
    "callbacks": {"on_left": "toggle_menu", "on_middle": "do_nothing", "on_right": "toggle_label"},
}

VALIDATION_SCHEMA = {
    "label": {"type": "string", "default": DEFAULTS["label"]},
    "label_alt": {"type": "string", "default": DEFAULTS["label_alt"]},
    "menu_title": {
        "type": "string",
        "default": DEFAULTS["menu_title"],
    },
    "folder_icon": {
        "type": "string",
        "default": DEFAULTS["folder_icon"],
    },
    "file_icon": {
        "type": "string",
        "default": DEFAULTS["file_icon"],
    },
    "hide_folder_icon": {
        "type": "boolean",
        "default": DEFAULTS["hide_folder_icon"],
    },
    "hide_file_icon": {
        "type": "boolean",
        "default": DEFAULTS["hide_file_icon"],
    },
    "truncate_to_root_dir": {
        "type": "boolean",
        "default": DEFAULTS["truncate_to_root_dir"],
    },
    "max_number_of_folders": {
        "type": "integer",
        "default": DEFAULTS["max_number_of_folders"],
        "min": 0,
    },
    "max_number_of_files": {
        "type": "integer",
        "default": DEFAULTS["max_number_of_files"],
        "min": 0,
    },
    "max_field_size": {
        "type": "integer",
        "default": DEFAULTS["max_field_size"],
        "min": 1,
    },
    "state_storage_path": {
        "type": "string",
        "default": "",
    },
    "modified_date_format": {
        "type": "string",
        "default": DEFAULTS["modified_date_format"],
    },
    "cli_command": {
        "type": "string",
        "default": DEFAULTS["cli_command"],
    },
    "menu": {
        "type": "dict",
        "required": False,
        "schema": {
            "blur": {"type": "boolean", "default": DEFAULTS["menu"]["blur"]},
            "round_corners": {"type": "boolean", "default": DEFAULTS["menu"]["round_corners"]},
            "round_corners_type": {"type": "string", "default": DEFAULTS["menu"]["round_corners_type"]},
            "border_color": {"type": "string", "default": DEFAULTS["menu"]["border_color"]},
            "alignment": {"type": "string", "default": DEFAULTS["menu"]["alignment"]},
            "direction": {"type": "string", "default": DEFAULTS["menu"]["direction"]},
            "distance": {"type": "integer", "default": DEFAULTS["menu"]["distance"]},
            "offset_top": {"type": "integer", "default": DEFAULTS["menu"]["offset_top"]},
            "offset_left": {"type": "integer", "default": DEFAULTS["menu"]["offset_left"]},
        },
        "default": DEFAULTS["menu"],
    },
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
    "callbacks": {
        "type": "dict",
        "schema": {
            "on_left": {
                "type": "string",
                "default": DEFAULTS["callbacks"]["on_left"],
            },
            "on_middle": {
                "type": "string",
                "default": DEFAULTS["callbacks"]["on_middle"],
            },
            "on_right": {
                "type": "string",
                "default": DEFAULTS["callbacks"]["on_right"],
            },
        },
        "default": DEFAULTS["callbacks"],
    },
}
