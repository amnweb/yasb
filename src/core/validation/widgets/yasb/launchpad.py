DEFAULTS = {
    "label": "\udb85\udcde",
    "search_placeholder": "Search applications...",
    "app_icon_size": 64,
    "window": {"fullscreen": False, "width": 800, "height": 600, "overlay_block": True},
    "window_animation": {"fade_in_duration": 400, "fade_out_duration": 400},
    "window_style": {
        "enable_blur": True,
        "round_corners": True,
        "round_corners_type": "normal",
        "border_color": "system",
    },
    "animation": {"enabled": True, "type": "fadeInOut", "duration": 200},
    "shortcuts": {"add_app": "Ctrl+N", "edit_app": "F2", "show_context_menu": "Shift+F10", "delete_app": "Delete"},
    "container_padding": {"top": 0, "left": 0, "bottom": 0, "right": 0},
    "callbacks": {"on_left": "toggle_launchpad", "on_right": "do_nothing", "on_middle": "do_nothing"},
}

VALIDATION_SCHEMA = {
    "label": {"type": "string", "default": DEFAULTS["label"]},
    "search_placeholder": {"type": "string", "default": DEFAULTS["search_placeholder"]},
    "app_icon_size": {"type": "integer", "default": DEFAULTS["app_icon_size"]},
    "window": {
        "type": "dict",
        "schema": {
            "fullscreen": {"type": "boolean", "default": DEFAULTS["window"]["fullscreen"]},
            "width": {"type": "integer", "default": DEFAULTS["window"]["width"]},
            "height": {"type": "integer", "default": DEFAULTS["window"]["height"]},
            "overlay_block": {"type": "boolean", "default": DEFAULTS["window"]["overlay_block"]},
        },
        "default": DEFAULTS["window"],
    },
    "window_animation": {
        "type": "dict",
        "schema": {
            "fade_in_duration": {"type": "integer", "default": DEFAULTS["window_animation"]["fade_in_duration"]},
            "fade_out_duration": {"type": "integer", "default": DEFAULTS["window_animation"]["fade_out_duration"]},
        },
        "default": DEFAULTS["window_animation"],
    },
    "window_style": {
        "type": "dict",
        "schema": {
            "enable_blur": {"type": "boolean", "default": DEFAULTS["window_style"]["enable_blur"]},
            "round_corners": {"type": "boolean", "default": DEFAULTS["window_style"]["round_corners"]},
            "round_corners_type": {
                "type": "string",
                "allowed": ["normal", "sharp"],
                "default": DEFAULTS["window_style"]["round_corners_type"],
            },
            "border_color": {"type": "string", "default": DEFAULTS["window_style"]["border_color"]},
        },
        "default": DEFAULTS["window_style"],
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
    "shortcuts": {
        "type": "dict",
        "schema": {
            "add_app": {"type": "string", "default": DEFAULTS["shortcuts"]["add_app"]},
            "edit_app": {"type": "string", "default": DEFAULTS["shortcuts"]["edit_app"]},
            "show_context_menu": {"type": "string", "default": DEFAULTS["shortcuts"]["show_context_menu"]},
            "delete_app": {"type": "string", "default": DEFAULTS["shortcuts"]["delete_app"]},
        },
        "default": DEFAULTS["shortcuts"],
    },
    "container_padding": {
        "type": "dict",
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
            "on_left": {"type": "string", "default": DEFAULTS["callbacks"]["on_left"]},
            "on_right": {"type": "string", "default": DEFAULTS["callbacks"]["on_right"]},
            "on_middle": {"type": "string", "default": DEFAULTS["callbacks"]["on_middle"]},
        },
        "default": DEFAULTS["callbacks"],
    },
    "label_shadow": {
        "type": "dict",
        "required": False,
        "schema": {
            "enabled": {"type": "boolean", "default": False},
            "color": {"type": "string", "default": "black"},
            "radius": {"type": "integer", "default": 3},
            "offset": {"type": "list", "default": [1, 1]},
        },
        "default": {"enabled": False, "color": "black", "offset": [1, 1], "radius": 3},
    },
    "container_shadow": {
        "type": "dict",
        "required": False,
        "schema": {
            "enabled": {"type": "boolean", "default": False},
            "color": {"type": "string", "default": "black"},
            "radius": {"type": "integer", "default": 3},
            "offset": {"type": "list", "default": [1, 1]},
        },
        "default": {"enabled": False, "color": "black", "offset": [1, 1], "radius": 3},
    },
    "app_title_shadow": {
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
    "app_icon_shadow": {
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
