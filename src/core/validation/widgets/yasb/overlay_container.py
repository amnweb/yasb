VALIDATION_SCHEMA = {
    "target": {
        "type": "string",
        "default": "full",
        "required": False,
        "allowed": ["full", "left", "center", "right", "custom", "widget"]
    },
    "target_widget": {
        "type": "string",
        "default": "",
        "required": False
    },
    "position": {
        "type": "string",
        "default": "behind",
        "required": False,
        "allowed": ["behind", "above"]
    },
    "offset_x": {
        "type": "integer",
        "default": 0,
        "required": False
    },
    "offset_y": {
        "type": "integer",
        "default": 0,
        "required": False
    },
    "width": {
        "type": ["string", "integer"],
        "default": "auto",
        "required": False
    },
    "height": {
        "type": ["string", "integer"],
        "default": "auto",
        "required": False
    },
    "opacity": {
        "type": "float",
        "default": 0.5,
        "required": False,
        "min": 0.0,
        "max": 1.0
    },
    "pass_through_clicks": {
        "type": "boolean",
        "default": True,
        "required": False
    },
    "z_index": {
        "type": "integer",
        "default": -1,
        "required": False,
        "min": -1,
        "max": 1
    },
    "child_widget_name": {
        "type": "string",
        "default": "",
        "required": True
    },
    "show_toggle": {
        "type": "boolean",
        "default": False,
        "required": False
    },
    "toggle_label": {
        "type": "string",
        "default": "\uf06e",
        "required": False
    },
    "auto_show": {
        "type": "boolean",
        "default": True,
        "required": False
    },
    "callbacks": {
        "type": "dict",
        "default": {
            "on_left": "toggle_overlay",
            "on_middle": "do_nothing",
            "on_right": "do_nothing"
        },
        "required": False,
        "schema": {
            "on_left": {
                "type": "string",
                "default": "toggle_overlay",
                "required": False,
            },
            "on_middle": {
                "type": "string",
                "default": "do_nothing",
                "required": False,
            },
            "on_right": {
                "type": "string",
                "default": "do_nothing",
                "required": False,
            }
        }
    },
    "container_padding": {
        "type": "dict",
        "default": {"top": 0, "left": 0, "bottom": 0, "right": 0},
        "required": False,
        "schema": {
            "top": {
                "type": "integer",
                "default": 0,
                "required": False
            },
            "left": {
                "type": "integer",
                "default": 0,
                "required": False
            },
            "bottom": {
                "type": "integer",
                "default": 0,
                "required": False
            },
            "right": {
                "type": "integer",
                "default": 0,
                "required": False
            }
        }
    },
    "container_shadow": {
        "type": "dict",
        "default": {
            "enabled": False,
            "color": "#000000",
            "offset": [0, 0],
            "radius": 0
        },
        "required": False,
        "schema": {
            "enabled": {
                "type": "boolean",
                "default": False,
                "required": False
            },
            "color": {
                "type": "string",
                "default": "#000000",
                "required": False
            },
            "offset": {
                "type": "list",
                "default": [0, 0],
                "required": False,
                "schema": {
                    "type": "integer"
                }
            },
            "radius": {
                "type": "integer",
                "default": 0,
                "required": False
            }
        }
    },
    "label_shadow": {
        "type": "dict",
        "default": {
            "enabled": False,
            "color": "#000000",
            "offset": [0, 0],
            "radius": 0
        },
        "required": False,
        "schema": {
            "enabled": {
                "type": "boolean",
                "default": False,
                "required": False
            },
            "color": {
                "type": "string",
                "default": "#000000",
                "required": False
            },
            "offset": {
                "type": "list",
                "default": [0, 0],
                "required": False,
                "schema": {
                    "type": "integer"
                }
            },
            "radius": {
                "type": "integer",
                "default": 0,
                "required": False
            }
        }
    },
    "background_media": {
        "type": "dict",
        "default": {
            "enabled": False,
            "file": "",
            "type": "auto",
            "fit": "cover",
            "opacity": 1.0,
            "loop": True,
            "muted": True,
            "playback_rate": 1.0,
            "volume": 1.0,
            "offset_x": 0,
            "offset_y": 0
        },
        "required": False,
        "schema": {
            "enabled": {
                "type": "boolean",
                "default": False,
                "required": False
            },
            "file": {
                "type": "string",
                "default": "",
                "required": False
            },
            "type": {
                "type": "string",
                "default": "auto",
                "required": False,
                "allowed": ["auto", "image", "animated", "video"]
            },
            "fit": {
                "type": "string",
                "default": "cover",
                "required": False,
                "allowed": ["fill", "contain", "cover", "stretch", "center", "tile", "scale-down"]
            },
            "opacity": {
                "type": "float",
                "default": 1.0,
                "required": False,
                "min": 0.0,
                "max": 1.0
            },
            "loop": {
                "type": "boolean",
                "default": True,
                "required": False
            },
            "muted": {
                "type": "boolean",
                "default": True,
                "required": False
            },
            "playback_rate": {
                "type": "float",
                "default": 1.0,
                "required": False,
                "min": 0.1,
                "max": 5.0
            },
            "volume": {
                "type": "float",
                "default": 1.0,
                "required": False,
                "min": 0.0,
                "max": 1.0
            },
            "offset_x": {
                "type": "integer",
                "default": 0,
                "required": False
            },
            "offset_y": {
                "type": "integer",
                "default": 0,
                "required": False
            },
            "alignment": {
                "type": "string",
                "default": "center",
                "required": False,
                "allowed": ["top-left", "top-center", "top-right", "center-left", "center", "center-right", "bottom-left", "bottom-center", "bottom-right"]
            },
            "css_class": {
                "type": "string",
                "default": "",
                "required": False
            },
            "view_offset_x": {
                "type": "integer",
                "default": 0,
                "required": False
            },
            "view_offset_y": {
                "type": "integer",
                "default": 0,
                "required": False
            }
        }
    },
    "background_shader": {
        "type": "dict",
        "default": {
            "enabled": False,
            "preset": "plasma",
            "custom_vertex_file": "",
            "custom_fragment_file": "",
            "speed": 1.0,
            "scale": 1.0,
            "opacity": 1.0,
            "colors": []
        },
        "required": False,
        "schema": {
            "enabled": {
                "type": "boolean",
                "default": False,
                "required": False
            },
            "preset": {
                "type": "string",
                "default": "plasma",
                "required": False,
                "allowed": ["plasma", "wave", "ripple", "tunnel", "mandelbrot", "noise", "gradient", "custom"]
            },
            "custom_vertex_file": {
                "type": "string",
                "default": "",
                "required": False
            },
            "custom_fragment_file": {
                "type": "string",
                "default": "",
                "required": False
            },
            "speed": {
                "type": "float",
                "default": 1.0,
                "required": False,
                "min": 0.1,
                "max": 10.0
            },
            "scale": {
                "type": "float",
                "default": 1.0,
                "required": False,
                "min": 0.1,
                "max": 10.0
            },
            "opacity": {
                "type": "float",
                "default": 1.0,
                "required": False,
                "min": 0.0,
                "max": 1.0
            },
            "colors": {
                "type": "list",
                "default": [],
                "required": False,
                "schema": {
                    "type": "string"
                }
            }
        }
    }
}
