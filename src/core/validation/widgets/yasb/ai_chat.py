DEFAULTS = {
    "label": "AI Chat",
    "chat": {
        "blur": True,
        "round_corners": True,
        "round_corners_type": "normal",
        "border_color": "system",
        "alignment": "right",
        "direction": "down",
        "offset_top": 6,
        "offset_left": 0,
    },
    "icons": {
        "send": "\uf1d8",
        "stop": "\uf04d",
        "clear": "\uf1f8",
        "assistant": "\udb81\ude74",
        "attach": "\uf0c6",
    },
    "notification_dot": {
        "enabled": True,
        "corner": "bottom_left",
        "color": "red",
        "margin": [1, 1],
    },
    "animation": {"enabled": True, "type": "fadeInOut", "duration": 200},
    "container_padding": {"top": 0, "left": 0, "bottom": 0, "right": 0},
    "callbacks": {"on_left": "toggle_chat", "on_middle": "do_nothing", "on_right": "do_nothing"},
}

VALIDATION_SCHEMA = {
    "label": {"type": "string", "default": DEFAULTS["label"]},
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
    "chat": {
        "type": "dict",
        "required": False,
        "schema": {
            "blur": {"type": "boolean", "default": DEFAULTS["chat"]["blur"]},
            "round_corners": {"type": "boolean", "default": DEFAULTS["chat"]["round_corners"]},
            "round_corners_type": {
                "type": "string",
                "default": DEFAULTS["chat"]["round_corners_type"],
                "allowed": ["normal", "small"],
            },
            "border_color": {"type": "string", "default": DEFAULTS["chat"]["border_color"]},
            "alignment": {
                "type": "string",
                "default": DEFAULTS["chat"]["alignment"],
                "allowed": ["left", "right", "center"],
            },
            "direction": {"type": "string", "default": DEFAULTS["chat"]["direction"], "allowed": ["up", "down"]},
            "offset_top": {"type": "integer", "default": DEFAULTS["chat"]["offset_top"]},
            "offset_left": {"type": "integer", "default": DEFAULTS["chat"]["offset_left"]},
        },
        "default": DEFAULTS["chat"],
    },
    "icons": {
        "type": "dict",
        "required": False,
        "schema": {
            "send": {"type": "string", "default": DEFAULTS["icons"]["send"]},
            "stop": {"type": "string", "default": DEFAULTS["icons"]["stop"]},
            "clear": {"type": "string", "default": DEFAULTS["icons"]["clear"]},
            "assistant": {"type": "string", "default": DEFAULTS["icons"]["assistant"]},
            "attach": {"type": "string", "default": DEFAULTS["icons"]["attach"]},
        },
        "default": DEFAULTS["icons"],
    },
    "notification_dot": {
        "type": "dict",
        "required": False,
        "schema": {
            "enabled": {
                "type": "boolean",
                "default": DEFAULTS["notification_dot"]["enabled"],
            },
            "corner": {
                "type": "string",
                "default": DEFAULTS["notification_dot"]["corner"],
                "allowed": ["top_left", "top_right", "bottom_left", "bottom_right"],
            },
            "color": {
                "type": "string",
                "default": DEFAULTS["notification_dot"]["color"],
            },
            "margin": {"type": "list", "default": [1, 1]},
        },
        "default": DEFAULTS["notification_dot"],
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
    "callbacks": {
        "type": "dict",
        "schema": {
            "on_left": {
                "type": "string",
                "default": DEFAULTS["callbacks"]["on_left"],
                "allowed": ["toggle_chat", "do_nothing"],
            },
            "on_middle": {
                "type": "string",
                "default": DEFAULTS["callbacks"]["on_middle"],
                "allowed": ["toggle_chat", "do_nothing"],
            },
            "on_right": {
                "type": "string",
                "default": DEFAULTS["callbacks"]["on_right"],
                "allowed": ["toggle_chat", "do_nothing"],
            },
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
    "providers": {
        "type": "list",
        "required": True,
        "schema": {
            "type": "dict",
            "schema": {
                "provider": {"type": "string", "required": True},
                "api_endpoint": {"type": "string", "required": True},
                "credential": {"type": "string", "required": True},
                "models": {
                    "type": "list",
                    "required": True,
                    "schema": {
                        "type": "dict",
                        "schema": {
                            "name": {"type": "string", "required": True},
                            "label": {"type": "string", "required": True},
                            "default": {"type": "boolean", "required": False, "default": False},
                            "max_tokens": {"type": "integer", "required": False, "default": 0},
                            "temperature": {"type": "number", "required": False, "default": 0.7},
                            "top_p": {"type": "number", "required": False, "default": 0.95},
                            "max_image_size": {"type": "integer", "required": False, "default": 0, "min": 0},
                            "max_attachment_size": {"type": "integer", "required": False, "default": 256, "min": 0},
                            "instructions": {
                                "type": "string",
                                "required": False,
                                "regex": ".*_chatmode\\.md$",
                            },
                        },
                    },
                },
            },
        },
    },
}
