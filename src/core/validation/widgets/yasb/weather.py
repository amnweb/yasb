from typing import Any

DEFAULTS = {
    "label": "0",
    "label_alt": "0",
    "update_interval": 3600,
    "hide_decimal": False,
    "location": "",
    "api_key": "0",
    "units": "metric",
    "show_alerts": False,
    "icons": {
        "sunnyDay": "\ue30d",
        "clearNight": "\ue32b",
        "cloudyDay": "\ue312",
        "cloudyNight": "\ue311",
        "rainyDay": "\udb81\ude7e",
        "rainyNight": "\udb81\ude7e",
        "snowyIcyDay": "\udb81\udd98",
        "snowyIcyNight": "\udb81\udd98",
        "blizzardDay": "\uebaa",
        "blizzardNight": "\uebaa",
        "foggyDay": "\ue303",
        "foggyNight": "\ue346",
        "thunderstormDay": "\ue30f",
        "thunderstormNight": "\ue338",
        "default": "\uebaa",
    },
    "weather_card": {
        "blur": True,
        "round_corners": True,
        "round_corners_type": "normal",
        "border_color": "System",
        "alignment": "right",
        "direction": "down",
        "distance": 6,  # deprecated
        "offset_top": 6,
        "offset_left": 0,
        "icon_size": 64,
    },
    "animation": {"enabled": True, "type": "fadeInOut", "duration": 200},
    "container_padding": {"top": 0, "left": 0, "bottom": 0, "right": 0},
    "callbacks": {"on_left": "do_nothing", "on_middle": "do_nothing", "on_right": "do_nothing"},
}

VALIDATION_SCHEMA: dict[str, Any] = {
    "label": {"type": "string", "default": DEFAULTS["label"]},
    "label_alt": {"type": "string", "default": DEFAULTS["label_alt"]},
    "update_interval": {"type": "integer", "default": DEFAULTS["update_interval"], "min": 60, "max": 36000000},
    "hide_decimal": {"type": "boolean", "default": DEFAULTS["hide_decimal"]},
    "location": {"type": "string", "default": DEFAULTS["location"]},
    "api_key": {"type": "string", "default": DEFAULTS["api_key"]},
    "units": {"type": "string", "default": DEFAULTS["units"], "allowed": ["metric", "imperial"]},
    "show_alerts": {"type": "boolean", "default": DEFAULTS["show_alerts"]},
    "icons": {
        "type": "dict",
        "required": False,
        "schema": {
            "sunnyDay": {"type": "string", "default": DEFAULTS["icons"]["sunnyDay"]},
            "clearNight": {
                "type": "string",
                "default": DEFAULTS["icons"]["clearNight"],
            },
            "cloudyDay": {
                "type": "string",
                "default": DEFAULTS["icons"]["cloudyDay"],
            },
            "cloudyNight": {
                "type": "string",
                "default": DEFAULTS["icons"]["cloudyNight"],
            },
            "rainyDay": {
                "type": "string",
                "default": DEFAULTS["icons"]["rainyDay"],
            },
            "rainyNight": {
                "type": "string",
                "default": DEFAULTS["icons"]["rainyNight"],
            },
            "snowyIcyDay": {
                "type": "string",
                "default": DEFAULTS["icons"]["snowyIcyDay"],
            },
            "snowyIcyNight": {
                "type": "string",
                "default": DEFAULTS["icons"]["snowyIcyNight"],
            },
            "blizzardDay": {
                "type": "string",
                "default": DEFAULTS["icons"]["blizzardDay"],
            },
            "blizzardNight": {
                "type": "string",
                "default": DEFAULTS["icons"]["blizzardNight"],
            },
            "foggyDay": {
                "type": "string",
                "default": DEFAULTS["icons"]["foggyDay"],
            },
            "foggyNight": {
                "type": "string",
                "default": DEFAULTS["icons"]["foggyNight"],
            },
            "thunderstormDay": {
                "type": "string",
                "default": DEFAULTS["icons"]["thunderstormDay"],
            },
            "thunderstormNight": {
                "type": "string",
                "default": DEFAULTS["icons"]["thunderstormNight"],
            },
            "blizzard": {  # deprecated
                "type": "string",
                "default": DEFAULTS["icons"]["blizzardDay"],
            },
            "default": {
                "type": "string",
                "default": DEFAULTS["icons"]["default"],
            },
        },
        "default": DEFAULTS["icons"],
    },
    "weather_card": {
        "type": "dict",
        "schema": {
            "blur": {"type": "boolean", "default": DEFAULTS["weather_card"]["blur"]},
            "round_corners": {"type": "boolean", "default": DEFAULTS["weather_card"]["round_corners"]},
            "round_corners_type": {
                "type": "string",
                "default": DEFAULTS["weather_card"]["round_corners_type"],
                "allowed": ["normal", "small"],
            },
            "border_color": {"type": "string", "default": DEFAULTS["weather_card"]["border_color"]},
            "alignment": {"type": "string", "default": DEFAULTS["weather_card"]["alignment"]},
            "direction": {"type": "string", "default": DEFAULTS["weather_card"]["direction"]},
            "distance": {"type": "integer", "default": DEFAULTS["weather_card"]["distance"]},
            "offset_top": {"type": "integer", "default": DEFAULTS["weather_card"]["offset_top"]},
            "offset_left": {"type": "integer", "default": DEFAULTS["weather_card"]["offset_left"]},
            "icon_size": {"type": "integer", "default": DEFAULTS["weather_card"]["icon_size"]},
        },
        "default": DEFAULTS["weather_card"],
    },
    "animation": {
        "type": "dict",
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
                "nullable": True,
                "default": DEFAULTS["callbacks"]["on_left"],
            },
            "on_middle": {
                "type": "string",
                "nullable": True,
                "default": DEFAULTS["callbacks"]["on_middle"],
            },
            "on_right": {"type": "string", "nullable": True, "default": DEFAULTS["callbacks"]["on_right"]},
        },
        "default": DEFAULTS["callbacks"],
    },
}
