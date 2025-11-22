DEFAULTS = {
    "label_placeholder": "Loading...",
    "label_max_length": None,
    "tooltip": False,
    "tooltip_label": None,
    "exec_options": {
        "run_cmd": None,
        "run_once": False,
        "run_interval": 120000,
        "return_format": "json",
        "hide_empty": False,
        "use_shell": True,
        "encoding": None,
    },
    "animation": {"enabled": True, "type": "fadeInOut", "duration": 200},
    "container_padding": {"top": 0, "left": 0, "bottom": 0, "right": 0},
    "callbacks": {
        "on_left": "toggle_label",
        "on_middle": "do_nothing",
        "on_right": "do_nothing",
    },
}


VALIDATION_SCHEMA = {
    "class_name": {
        "type": "string",
        "required": True,
    },
    "label": {"type": "string", "required": True},
    "label_alt": {"type": "string", "default": True},
    "label_placeholder": {"type": "string", "required": False, "default": DEFAULTS["label_placeholder"]},
    "label_max_length": {"type": "integer", "nullable": True, "default": DEFAULTS["label_max_length"], "min": 1},
    "tooltip": {"type": "boolean", "required": False, "default": DEFAULTS["tooltip"]},
    "tooltip_label": {"type": "string", "nullable": True, "required": False, "default": DEFAULTS["tooltip_label"]},
    "exec_options": {
        "type": "dict",
        "schema": {
            "run_cmd": {"type": "string", "nullable": True, "default": DEFAULTS["exec_options"]["run_cmd"]},
            "run_once": {"type": "boolean", "default": DEFAULTS["exec_options"]["run_once"]},
            "run_interval": {"type": "integer", "default": DEFAULTS["exec_options"]["run_interval"], "min": 0},
            "return_format": {
                "type": "string",
                "allowed": ["string", "json"],
                "default": DEFAULTS["exec_options"]["return_format"],
            },
            "hide_empty": {"type": "boolean", "required": False, "default": DEFAULTS["exec_options"]["hide_empty"]},
            "use_shell": {"type": "boolean", "default": DEFAULTS["exec_options"]["use_shell"]},
            "encoding": {"type": "string", "nullable": True, "default": DEFAULTS["exec_options"]["encoding"]},
        },
        "default": DEFAULTS["exec_options"],
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
            "on_right": {"type": "string", "default": DEFAULTS["callbacks"]["on_right"]},
        },
        "default": DEFAULTS["callbacks"],
    },
}
