DEFAULTS = {
    "label": "{icon}",
    "label_alt": "Brightness {percent}%",
    "tooltip": True,
    "scroll_step": 1,
    "brightness_icons": [
        "\udb80\udcde",  # Icon for 0-25% brightness
        "\udb80\udcdd",  # Icon for 26-50% brightness
        "\udb80\udcdf",  # Icon for 51-75% brightness
        "\udb80\udce0",  # Icon for 76-100% brightness
    ],
    "brightness_toggle_level": [],
    "brightness_menu": {
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
    "hide_unsupported": True,  # deprecated
    "auto_light": False,
    "auto_light_icon": "\udb80\udce1",
    "auto_light_night_level": 50,
    "auto_light_night_start_time": "20:00",
    "auto_light_night_end_time": "06:30",
    "auto_light_day_level": 100,
    "container_padding": {"top": 0, "left": 0, "bottom": 0, "right": 0},
    "animation": {"enabled": True, "type": "fadeInOut", "duration": 200},
    "callbacks": {"on_left": "toggle_label", "on_middle": "do_nothing", "on_right": "do_nothing"},
}

VALIDATION_SCHEMA = {
    "label": {"type": "string", "default": DEFAULTS["label"]},
    "label_alt": {"type": "string", "default": DEFAULTS["label_alt"]},
    "tooltip": {"type": "boolean", "required": False, "default": DEFAULTS["tooltip"]},
    "scroll_step": {
        "type": "integer",
        "required": False,
        "default": DEFAULTS["scroll_step"],
        "min": 1,
        "max": 100,
    },
    "brightness_icons": {
        "type": "list",
        "default": DEFAULTS["brightness_icons"],
        "schema": {"type": "string", "required": False},
    },
    "brightness_toggle_level": {
        "type": "list",
        "default": DEFAULTS["brightness_toggle_level"],
        "schema": {"type": "integer", "required": False},
    },
    "brightness_menu": {
        "type": "dict",
        "required": False,
        "schema": {
            "blur": {"type": "boolean", "default": DEFAULTS["brightness_menu"]["blur"]},
            "round_corners": {"type": "boolean", "default": DEFAULTS["brightness_menu"]["round_corners"]},
            "round_corners_type": {"type": "string", "default": DEFAULTS["brightness_menu"]["round_corners_type"]},
            "border_color": {"type": "string", "default": DEFAULTS["brightness_menu"]["border_color"]},
            "alignment": {"type": "string", "default": DEFAULTS["brightness_menu"]["alignment"]},
            "direction": {"type": "string", "default": DEFAULTS["brightness_menu"]["direction"]},
            "distance": {"type": "integer", "default": DEFAULTS["brightness_menu"]["distance"]},
            "offset_top": {"type": "integer", "default": DEFAULTS["brightness_menu"]["offset_top"]},
            "offset_left": {"type": "integer", "default": DEFAULTS["brightness_menu"]["offset_left"]},
        },
        "default": DEFAULTS["brightness_menu"],
    },
    # deprecated: widget now always hides when unsupported
    "hide_unsupported": {"type": "boolean", "required": False, "default": DEFAULTS["hide_unsupported"]},
    "auto_light": {"type": "boolean", "required": False, "default": DEFAULTS["auto_light"]},
    "auto_light_icon": {"type": "string", "required": False, "default": DEFAULTS["auto_light_icon"]},
    "auto_light_night_level": {"type": "integer", "required": False, "default": DEFAULTS["auto_light_night_level"]},
    "auto_light_night_start_time": {
        "type": "string",
        "required": False,
        "default": DEFAULTS["auto_light_night_start_time"],
    },
    "auto_light_night_end_time": {
        "type": "string",
        "required": False,
        "default": DEFAULTS["auto_light_night_end_time"],
    },
    "auto_light_day_level": {"type": "integer", "required": False, "default": DEFAULTS["auto_light_day_level"]},
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
    "progress_bar": {
        "type": "dict",
        "default": {"enabled": False},
        "required": False,
        "schema": {
            "enabled": {"type": "boolean", "default": False},
            "size": {"type": "integer", "default": 18, "min": 8, "max": 64},
            "thickness": {"type": "integer", "default": 3, "min": 1, "max": 10},
            "color": {
                "anyof": [{"type": "string"}, {"type": "list", "schema": {"type": "string"}}],
                "default": "#00C800",
            },
            "background_color": {"type": "string", "default": "#3C3C3C"},
            "position": {"type": "string", "allowed": ["left", "right"], "default": "left"},
            "animation": {
                "type": "boolean",
                "default": True,
            },
        },
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
