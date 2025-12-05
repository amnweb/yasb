from typing import Any

DEFAULTS: dict[str, Any] = {
    "label": "0",
    "label_alt": "0",
    "class_name": "",
    "update_interval": 3600,
    "hide_decimal": False,
    "location": "",
    "api_key": "0",
    "units": "metric",
    "show_alerts": False,
    "tooltip": True,
    "icons": {
        "sunnyDay": "\ue30d",
        "clearNight": "\ue32b",
        "cloudyDay": "\ue312",
        "cloudyNight": "\ue311",
        "rainyDay": "\udb81\ude7e",
        "rainyNight": "\udb81\ude7e",
        "snowyDay": "\udb81\udd98",
        "snowyNight": "\udb81\udd98",
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
        "show_hourly_forecast": False,
        "time_format": "24h",
        "hourly_point_spacing": 76,
        "hourly_icon_size": 32,
        "icon_smoothing": True,
        "temp_line_width": 2,
        "current_line_color": "#8EAEE8",
        "current_line_width": 1,
        "current_line_style": "dot",
        "hourly_gradient": {
            "enabled": False,
            "top_color": "#8EAEE8",
            "bottom_color": "#2A3E68",
        },
        "hourly_forecast_buttons": {
            "enabled": False,
            "default_view": "temperature",
            "snow_icon": "\udb81\udd98",
            "rain_icon": "\udb81\udd96",
            "temperature_icon": "\udb81\udd99",
        },
        "weather_animation": {
            "enabled": False,
            "snow_overrides_rain": True,
            "temp_line_animation_style": "both",
            "rain_effect_intensity": 1.0,
            "snow_effect_intensity": 1.0,
            "scale_with_chance": True,
            "enable_debug": False,
        },
    },
    "animation": {"enabled": True, "type": "fadeInOut", "duration": 200},
    "container_padding": {"top": 0, "left": 0, "bottom": 0, "right": 0},
    "callbacks": {"on_left": "do_nothing", "on_middle": "do_nothing", "on_right": "do_nothing"},
}

VALIDATION_SCHEMA: dict[str, Any] = {
    "label": {"type": "string", "default": DEFAULTS["label"]},
    "label_alt": {"type": "string", "default": DEFAULTS["label_alt"]},
    "class_name": {"type": "string", "required": False, "default": DEFAULTS["class_name"]},
    "update_interval": {"type": "integer", "default": DEFAULTS["update_interval"], "min": 60, "max": 36000000},
    "hide_decimal": {"type": "boolean", "default": DEFAULTS["hide_decimal"]},
    "location": {"type": "string", "default": DEFAULTS["location"]},
    "api_key": {"type": "string", "default": DEFAULTS["api_key"]},
    "units": {"type": "string", "default": DEFAULTS["units"], "allowed": ["metric", "imperial"]},
    "show_alerts": {"type": "boolean", "default": DEFAULTS["show_alerts"]},
    "tooltip": {"type": "boolean", "default": DEFAULTS["tooltip"]},
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
            "snowyDay": {
                "type": "string",
                "default": DEFAULTS["icons"]["snowyDay"],
            },
            "snowyNight": {
                "type": "string",
                "default": DEFAULTS["icons"]["snowyNight"],
            },
            "snowyIcyDay": {  # deprecated
                "type": "string",
                "default": DEFAULTS["icons"]["snowyDay"],
            },
            "snowyIcyNight": {  # deprecated
                "type": "string",
                "default": DEFAULTS["icons"]["snowyNight"],
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
            "icon_smoothing": {"type": "boolean", "default": DEFAULTS["weather_card"]["icon_smoothing"]},
            "show_hourly_forecast": {
                "type": "boolean",
                "default": DEFAULTS["weather_card"]["show_hourly_forecast"],
            },
            "time_format": {
                "type": "string",
                "allowed": ["12h", "24h"],
                "default": DEFAULTS["weather_card"]["time_format"],
            },
            "hourly_point_spacing": {"type": "integer", "default": DEFAULTS["weather_card"]["hourly_point_spacing"]},
            "hourly_icon_size": {
                "type": "integer",
                "min": 8,
                "max": 64,
                "default": DEFAULTS["weather_card"]["hourly_icon_size"],
            },
            "temp_line_width": {
                "type": "integer",
                "min": 0,
                "max": 10,
                "default": DEFAULTS["weather_card"]["temp_line_width"],
            },
            "current_line_color": {"type": "string", "default": DEFAULTS["weather_card"]["current_line_color"]},
            "current_line_width": {
                "type": "integer",
                "min": 0,
                "max": 10,
                "default": DEFAULTS["weather_card"]["current_line_width"],
            },
            "current_line_style": {
                "type": "string",
                "allowed": ["solid", "dash", "dot", "dashDot", "dashDotDot"],
                "default": DEFAULTS["weather_card"]["current_line_style"],
            },
            "hourly_gradient": {
                "type": "dict",
                "schema": {
                    "enabled": {
                        "type": "boolean",
                        "default": DEFAULTS["weather_card"]["hourly_gradient"]["enabled"],
                    },
                    "top_color": {
                        "type": "string",
                        "default": DEFAULTS["weather_card"]["hourly_gradient"]["top_color"],
                    },
                    "bottom_color": {
                        "type": "string",
                        "default": DEFAULTS["weather_card"]["hourly_gradient"]["bottom_color"],
                    },
                },
                "default": DEFAULTS["weather_card"]["hourly_gradient"],
            },
            "hourly_forecast_buttons": {
                "type": "dict",
                "schema": {
                    "enabled": {
                        "type": "boolean",
                        "default": DEFAULTS["weather_card"]["hourly_forecast_buttons"]["enabled"],
                    },
                    "default_view": {
                        "type": "string",
                        "allowed": ["temperature", "rain", "snow"],
                        "default": DEFAULTS["weather_card"]["hourly_forecast_buttons"]["default_view"],
                    },
                    "snow_icon": {
                        "type": "string",
                        "default": DEFAULTS["weather_card"]["hourly_forecast_buttons"]["snow_icon"],
                    },
                    "rain_icon": {
                        "type": "string",
                        "default": DEFAULTS["weather_card"]["hourly_forecast_buttons"]["rain_icon"],
                    },
                    "temperature_icon": {
                        "type": "string",
                        "default": DEFAULTS["weather_card"]["hourly_forecast_buttons"]["temperature_icon"],
                    },
                },
                "default": DEFAULTS["weather_card"]["hourly_forecast_buttons"],
            },
            "weather_animation": {
                "type": "dict",
                "schema": {
                    "enabled": {"type": "boolean", "default": DEFAULTS["weather_card"]["weather_animation"]["enabled"]},
                    "snow_overrides_rain": {
                        "type": "boolean",
                        "default": DEFAULTS["weather_card"]["weather_animation"]["snow_overrides_rain"],
                    },
                    "temp_line_animation_style": {
                        "type": "string",
                        "allowed": ["rain", "snow", "both", "none"],
                        "default": DEFAULTS["weather_card"]["weather_animation"]["temp_line_animation_style"],
                    },
                    "rain_effect_intensity": {
                        "type": "float",
                        "min": 0.01,
                        "max": 10.0,
                        "default": DEFAULTS["weather_card"]["weather_animation"]["rain_effect_intensity"],
                    },
                    "snow_effect_intensity": {
                        "type": "float",
                        "min": 0.01,
                        "max": 10.0,
                        "default": DEFAULTS["weather_card"]["weather_animation"]["snow_effect_intensity"],
                    },
                    "scale_with_chance": {
                        "type": "boolean",
                        "default": DEFAULTS["weather_card"]["weather_animation"]["scale_with_chance"],
                    },
                    "enable_debug": {
                        "type": "boolean",
                        "default": DEFAULTS["weather_card"]["weather_animation"]["enable_debug"],
                    },
                },
                "default": DEFAULTS["weather_card"]["weather_animation"],
            },
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
