DEFAULTS = {
    "label": "{volume[percent]}%",
    "label_alt": "{volume[percent]}%",
    "mute_text": "mute",
    "tooltip": True,
    "scroll_step": 2,
    "volume_icons": [
        "\ueee8",  # Icon for muted
        "\uf026",  # Icon for 0-10% volume
        "\uf027",  # Icon for 11-30% volume
        "\uf027",  # Icon for 31-60% volume
        "\uf028",  # Icon for 61-100% volume
    ],
    "audio_menu": {
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
    "callbacks": {"on_left": "toggle_volume_menu", "on_middle": "do_nothing", "on_right": "toggle_mute"},
}

VALIDATION_SCHEMA = {
    "label": {"type": "string", "default": DEFAULTS["label"]},
    "label_alt": {"type": "string", "default": DEFAULTS["label_alt"]},
    "mute_text": {"type": "string", "required": False, "default": DEFAULTS["mute_text"]},
    "tooltip": {"type": "boolean", "required": False, "default": DEFAULTS["tooltip"]},
    "scroll_step": {
        "type": "integer",
        "required": False,
        "default": DEFAULTS["scroll_step"],
        "min": 1,
        "max": 100,
    },
    "volume_icons": {
        "type": "list",
        "default": DEFAULTS["volume_icons"],
        "schema": {"type": "string", "required": False},
    },
    "audio_menu": {
        "type": "dict",
        "required": False,
        "schema": {
            "blur": {"type": "boolean", "default": DEFAULTS["audio_menu"]["blur"]},
            "round_corners": {"type": "boolean", "default": DEFAULTS["audio_menu"]["round_corners"]},
            "round_corners_type": {"type": "string", "default": DEFAULTS["audio_menu"]["round_corners_type"]},
            "border_color": {"type": "string", "default": DEFAULTS["audio_menu"]["border_color"]},
            "alignment": {"type": "string", "default": DEFAULTS["audio_menu"]["alignment"]},
            "direction": {"type": "string", "default": DEFAULTS["audio_menu"]["direction"]},
            "distance": {"type": "integer", "default": DEFAULTS["audio_menu"]["distance"]},
            "offset_top": {"type": "integer", "default": DEFAULTS["audio_menu"]["offset_top"]},
            "offset_left": {"type": "integer", "default": DEFAULTS["audio_menu"]["offset_left"]},
        },
        "default": DEFAULTS["audio_menu"],
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
            "on_right": {
                "type": "string",
                "default": DEFAULTS["callbacks"]["on_right"],
            },
        },
        "default": DEFAULTS["callbacks"],
    },
}
