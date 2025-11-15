DEFAULTS = {
    "label": "\uf4a0 {count}/{completed}",
    "label_alt": "\uf4a0 Tasks: {count}",
    "data_path": "",
    "container_padding": {"top": 0, "left": 0, "bottom": 0, "right": 0},
    "animation": {"enabled": True, "type": "fadeInOut", "duration": 200},
    "menu": {
        "blur": True,
        "round_corners": True,
        "round_corners_type": "normal",
        "border_color": "system",
        "alignment": "left",
        "direction": "down",
        "offset_top": 6,
        "offset_left": 0,
    },
    "icons": {
        "add": "New Task",
        "edit": "Edit",
        "delete": "Delete",
        "date": "\ue641",
        "category": "\uf412",
        "checked": "\udb80\udd34",
        "unchecked": "\udb80\udd30",
        "sort": "\ueab4",
        "no_tasks": "\uf4a0",
    },
    "categories": {
        "default": {"label": "General"},
        "urgent": {"label": "Urgent"},
        "important": {"label": "Important"},
        "soon": {"label": "Complete soon"},
        "today": {"label": "End of day"},
    },
    "callbacks": {"on_left": "toggle_menu", "on_middle": "do_nothing", "on_right": "toggle_label"},
}

VALIDATION_SCHEMA = {
    "label": {"type": "string", "default": DEFAULTS["label"]},
    "label_alt": {"type": "string", "default": DEFAULTS["label_alt"]},
    "data_path": {"type": "string", "required": False, "default": DEFAULTS["data_path"]},
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
    "menu": {
        "type": "dict",
        "required": False,
        "schema": {
            "blur": {"type": "boolean", "default": DEFAULTS["menu"]["blur"]},
            "round_corners": {"type": "boolean", "default": DEFAULTS["menu"]["round_corners"]},
            "round_corners_type": {
                "type": "string",
                "default": DEFAULTS["menu"]["round_corners_type"],
                "allowed": ["normal", "small"],
            },
            "border_color": {"type": "string", "default": DEFAULTS["menu"]["border_color"]},
            "alignment": {"type": "string", "default": DEFAULTS["menu"]["alignment"]},
            "direction": {"type": "string", "default": DEFAULTS["menu"]["direction"]},
            "offset_top": {"type": "integer", "default": DEFAULTS["menu"]["offset_top"]},
            "offset_left": {"type": "integer", "default": DEFAULTS["menu"]["offset_left"]},
        },
        "default": DEFAULTS["menu"],
    },
    "icons": {
        "type": "dict",
        "required": False,
        "schema": {
            "add": {"type": "string", "default": DEFAULTS["icons"]["add"]},
            "edit": {"type": "string", "default": DEFAULTS["icons"]["edit"]},
            "delete": {"type": "string", "default": DEFAULTS["icons"]["delete"]},
            "date": {"type": "string", "default": DEFAULTS["icons"]["date"]},
            "category": {"type": "string", "default": DEFAULTS["icons"]["category"]},
            "checked": {"type": "string", "default": DEFAULTS["icons"]["checked"]},
            "unchecked": {"type": "string", "default": DEFAULTS["icons"]["unchecked"]},
            "sort": {"type": "string", "default": DEFAULTS["icons"]["sort"]},
            "no_tasks": {"type": "string", "default": DEFAULTS["icons"]["no_tasks"]},
        },
        "default": DEFAULTS["icons"],
    },
    "categories": {
        "type": "dict",
        "required": False,
        "schema": {
            "default": {
                "type": "dict",
                "schema": {
                    "label": {"type": "string", "default": DEFAULTS["categories"]["default"]["label"]},
                },
                "default": DEFAULTS["categories"]["default"],
            },
            "urgent": {
                "type": "dict",
                "schema": {
                    "label": {"type": "string", "default": DEFAULTS["categories"]["urgent"]["label"]},
                },
                "default": DEFAULTS["categories"]["urgent"],
            },
            "important": {
                "type": "dict",
                "schema": {
                    "label": {"type": "string", "default": DEFAULTS["categories"]["important"]["label"]},
                },
                "default": DEFAULTS["categories"]["important"],
            },
            "soon": {
                "type": "dict",
                "schema": {
                    "label": {"type": "string", "default": DEFAULTS["categories"]["soon"]["label"]},
                },
                "default": DEFAULTS["categories"]["soon"],
            },
            "today": {
                "type": "dict",
                "schema": {
                    "label": {"type": "string", "default": DEFAULTS["categories"]["today"]["label"]},
                },
                "default": DEFAULTS["categories"]["today"],
            },
        },
        "allowed": ["default", "urgent", "important", "soon", "today"],
        "default": DEFAULTS["categories"],
    },
    "callbacks": {
        "type": "dict",
        "required": False,
        "schema": {
            "on_left": {"type": "string", "default": DEFAULTS["callbacks"]["on_left"]},
            "on_middle": {"type": "string", "default": DEFAULTS["callbacks"]["on_middle"]},
            "on_right": {"type": "string", "default": DEFAULTS["callbacks"]["on_right"]},
        },
        "default": DEFAULTS["callbacks"],
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
}
