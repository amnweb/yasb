DEFAULTS = {
    "label": "\udb80\uddd9",
    "icons": {
        "start": "\uead3",
        "stop": "\uead7",
        "reload": "\uead2",
    },
    "run_ahk": False,
    "run_whkd": False,
    "run_masir": False,
    "config_path": None,
    "show_version": True,
    "komorebi_menu": {
        "blur": True,
        "round_corners": True,
        "round_corners_type": "normal",
        "border_color": "System",
        "alignment": "right",
        "direction": "down",
        "offset_top": 6,
        "offset_left": 0,
    },
    "animation": {"enabled": True, "type": "fadeInOut", "duration": 200},
    "container_padding": {"top": 0, "left": 0, "bottom": 0, "right": 0},
    "callbacks": {"on_left": "toggle_menu", "on_middle": "do_nothing", "on_right": "do_nothing"},
}

VALIDATION_SCHEMA = {
    "label": {"type": "string", "default": DEFAULTS["label"]},
    "icons": {
        "type": "dict",
        "required": False,
        "schema": {
            "start": {"type": "string", "default": DEFAULTS["icons"]["start"]},
            "stop": {"type": "string", "default": DEFAULTS["icons"]["stop"]},
            "reload": {"type": "string", "default": DEFAULTS["icons"]["reload"]},
        },
        "default": DEFAULTS["icons"],
    },
    "run_ahk": {"type": "boolean", "default": DEFAULTS["run_ahk"]},
    "run_whkd": {"type": "boolean", "default": DEFAULTS["run_whkd"]},
    "run_masir": {"type": "boolean", "default": DEFAULTS["run_masir"]},
    "config_path": {
        "type": "string",
        "required": False,
        "default": DEFAULTS["config_path"],
        "nullable": True,
    },
    "show_version": {"type": "boolean", "default": DEFAULTS["show_version"]},
    "komorebi_menu": {
        "type": "dict",
        "required": False,
        "schema": {
            "blur": {"type": "boolean", "default": DEFAULTS["komorebi_menu"]["blur"]},
            "round_corners": {"type": "boolean", "default": DEFAULTS["komorebi_menu"]["round_corners"]},
            "round_corners_type": {
                "type": "string",
                "default": DEFAULTS["komorebi_menu"]["round_corners_type"],
                "allowed": ["normal", "small"],
            },
            "border_color": {"type": "string", "default": DEFAULTS["komorebi_menu"]["border_color"]},
            "alignment": {"type": "string", "default": DEFAULTS["komorebi_menu"]["alignment"]},
            "direction": {"type": "string", "default": DEFAULTS["komorebi_menu"]["direction"]},
            "offset_top": {"type": "integer", "default": DEFAULTS["komorebi_menu"]["offset_top"]},
            "offset_left": {"type": "integer", "default": DEFAULTS["komorebi_menu"]["offset_left"]},
        },
        "default": DEFAULTS["komorebi_menu"],
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
    "container_padding": {"type": "dict", "default": DEFAULTS["container_padding"], "required": False},
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
            "on_right": {
                "type": "string",
                "default": DEFAULTS["callbacks"]["on_right"],
            },
        },
        "default": DEFAULTS["callbacks"],
    },
}
