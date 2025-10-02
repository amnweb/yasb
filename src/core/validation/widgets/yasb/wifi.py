from typing import Any

DEFAULTS: dict[str, Any] = {
    "label": "{wifi_icon}",
    "label_alt": "{wifi_icon} {wifi_name}",
    "update_interval": 1000,
    "class_name": "",
    "callbacks": {"on_left": "toggle_label", "on_middle": "do_nothing", "on_right": "do_nothing"},
    "wifi_icons": [
        "\udb82\udd2e",  # Icon for 0% strength
        "\udb82\udd1f",  # Icon for 1-24% strength
        "\udb82\udd22",  # Icon for 25-49% strength
        "\udb82\udd25",  # Icon for 50-74% strength
        "\udb82\udd28",  # Icon for 75-100% strength
    ],
    "ethernet_label": "{wifi_icon}",
    "ethernet_label_alt": "{wifi_icon} {ip_addr}",
    "ethernet_icon": "\ueba9",
    "get_exact_wifi_strength": False,
    "hide_if_ethernet": False,
    "container_padding": {"top": 0, "left": 0, "bottom": 0, "right": 0},
    "animation": {"enabled": True, "type": "fadeInOut", "duration": 200},
    "menu_config": {
        "blur": True,
        "round_corners": True,
        "round_corners_type": "normal",
        "border_color": "System",
        "alignment": "right",
        "direction": "down",
        "offset_top": 6,
        "offset_left": 0,
        "wifi_icons_secured": [
            "\ue670",
            "\ue671",
            "\ue672",
            "\ue673",
        ],
        "wifi_icons_unsecured": [
            "\uec3c",
            "\uec3d",
            "\uec3e",
            "\uec3f",
        ],
    },
}

VALIDATION_SCHEMA: dict[str, Any] = {
    "label": {"type": "string", "default": DEFAULTS["label"]},
    "label_alt": {"type": "string", "default": DEFAULTS["label_alt"]},
    "update_interval": {"type": "integer", "default": DEFAULTS["update_interval"], "min": 0, "max": 60000},
    "class_name": {"type": "string", "required": False, "default": DEFAULTS["class_name"]},
    "wifi_icons": {"type": "list", "default": DEFAULTS["wifi_icons"], "schema": {"type": "string", "required": False}},
    "ethernet_label": {"type": "string", "default": DEFAULTS["ethernet_label"]},
    "ethernet_label_alt": {"type": "string", "default": DEFAULTS["ethernet_label_alt"]},
    "ethernet_icon": {"type": "string", "default": DEFAULTS["ethernet_icon"]},
    "get_exact_wifi_strength": {"type": "boolean", "default": DEFAULTS["get_exact_wifi_strength"]},
    "hide_if_ethernet": {"type": "boolean", "default": DEFAULTS["hide_if_ethernet"]},
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
    "menu_config": {
        "type": "dict",
        "required": False,
        "schema": {
            "blur": {"type": "boolean", "default": DEFAULTS["menu_config"]["blur"]},
            "round_corners": {"type": "boolean", "default": DEFAULTS["menu_config"]["round_corners"]},
            "round_corners_type": {
                "type": "string",
                "default": DEFAULTS["menu_config"]["round_corners_type"],
                "allowed": ["normal", "small"],
            },
            "border_color": {"type": "string", "default": DEFAULTS["menu_config"]["border_color"]},
            "alignment": {"type": "string", "default": DEFAULTS["menu_config"]["alignment"]},
            "direction": {"type": "string", "default": DEFAULTS["menu_config"]["direction"]},
            "offset_top": {"type": "integer", "default": DEFAULTS["menu_config"]["offset_top"]},
            "offset_left": {"type": "integer", "default": DEFAULTS["menu_config"]["offset_left"]},
            "wifi_icons_secured": {"type": "list", "default": DEFAULTS["menu_config"]["wifi_icons_secured"]},
            "wifi_icons_unsecured": {"type": "list", "default": DEFAULTS["menu_config"]["wifi_icons_unsecured"]},
        },
        "default": DEFAULTS["menu_config"],
    },
}
