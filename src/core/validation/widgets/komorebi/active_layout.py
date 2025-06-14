DEFAULTS = {
    'hide_if_offline': False,
    "label": "{icon}",
    'layouts': ['bsp', 'columns', 'rows', 'grid', 'scrolling', 'vertical_stack', 'horizontal_stack', 'ultrawide_vertical_stack', 'right_main_vertical_stack'],
    'layout_icons': {
        "bsp": "[\\\\]",
        "columns": "[||]",
        "rows": "[==]",
        "grid": "[G]",
        'scrolling': "[SC]",
        "vertical_stack": "[V]=",
        "horizontal_stack": "[H]=",
        "ultrawide_vertical_stack": "||=",
        "right_main_vertical_stack": "=||",
        "monocle": "[M]",
        "maximised": "[X]",
        "floating": "><>",
        "paused": "[P]",
        'tiling': "[T]"
    },
    'layout_menu': {
        'blur': True,
        'round_corners': True,
        'round_corners_type': 'normal',
        'border_color': 'System',
        'alignment': 'left',
        'direction': 'down',
        'offset_top': 6,
        'offset_left': 0,
        'show_layout_icons': True,
    },
    "generate_layout_icons": False,
    'container_padding': {'top': 0, 'left': 0, 'bottom': 0, 'right': 0},
    'animation': {
        'enabled': True,
        'type': 'fadeInOut',
        'duration': 200
    },
    'callbacks': {
        'on_left': 'next_layout',
        'on_middle': 'toggle_monocle',
        'on_right': 'prev_layout'
    }
}

ALLOWED_CALLBACKS = [
    "next_layout",
    "prev_layout",
    "flip_layout",
    "flip_layout_horizontal",
    "flip_layout_vertical",
    "flip_layout_horizontal_and_vertical",
    "first_layout",
    "toggle_tiling",
    "toggle_float",
    "toggle_monocle",
    "toggle_maximise",
    "toggle_pause",
    "toggle_layout_menu"
]

VALIDATION_SCHEMA = {
    'hide_if_offline': {
        'type': 'boolean',
        'default': DEFAULTS['hide_if_offline']
    },
    'label': {
        'type': 'string',
        'default': DEFAULTS['label']
    },
    'layouts': {
        'type': 'list',
        'schema': {
            'type': 'string',
            'required': False
        },
        'default': DEFAULTS['layouts']
    },
    'layout_icons': {
        'type': 'dict',
        'schema': {
            "bsp": {
                'type': 'string',
                'default': DEFAULTS['layout_icons']['bsp']
            },
            "columns": {
                'type': 'string',
                'default': DEFAULTS['layout_icons']['columns']
            },
            "rows": {
                'type': 'string',
                'default': DEFAULTS['layout_icons']['rows']
            },
            "grid": {
                'type': 'string',
                'default': DEFAULTS['layout_icons']['grid']
            },
            'scrolling': {
                'type': 'string',
                'default': DEFAULTS['layout_icons']['scrolling']
            },
            "vertical_stack": {
                'type': 'string',
                'default': DEFAULTS['layout_icons']['vertical_stack']
            },
            "horizontal_stack": {
                'type': 'string',
                'default': DEFAULTS['layout_icons']['horizontal_stack']
            },
            "ultrawide_vertical_stack": {
                'type': 'string',
                'default': DEFAULTS['layout_icons']['ultrawide_vertical_stack']
            },
            "right_main_vertical_stack": {
                'type': 'string',
                'default': DEFAULTS['layout_icons']['right_main_vertical_stack']
            },
            "monocle": {
                'type': 'string',
                'default': DEFAULTS['layout_icons']['monocle']
            },
            "maximised": {
                'type': 'string',
                'default': DEFAULTS['layout_icons']['maximised']
            },
            "floating": {
                'type': 'string',
                'default': DEFAULTS['layout_icons']['floating']
            },
            "paused": {
                'type': 'string',
                'default': DEFAULTS['layout_icons']['paused']
            },
            'tiling': {
                'type': 'string',
                'default': DEFAULTS['layout_icons']['tiling']
            }
        },
        'default': DEFAULTS['layout_icons']
    },
    'layout_menu': {
        'type': 'dict',
        'schema': {
            'blur': {
                'type': 'boolean',
                'default': DEFAULTS['layout_menu']['blur']
            },
            'round_corners': {
                'type': 'boolean',
                'default': DEFAULTS['layout_menu']['round_corners']
            },
            'round_corners_type': {
                'type': 'string',
                'default': DEFAULTS['layout_menu']['round_corners_type']
            },
            'border_color': {
                'type': 'string',
                'default': DEFAULTS['layout_menu']['border_color']
            },
            'alignment': {
                'type': 'string',
                'default': DEFAULTS['layout_menu']['alignment']
            },
            'direction': {
                'type': 'string',
                'default': DEFAULTS['layout_menu']['direction']
            },
            'offset_top': {
                'type': 'integer',
                'default': DEFAULTS['layout_menu']['offset_top']
            },
            'offset_left': {
                'type': 'integer',
                'default': DEFAULTS['layout_menu']['offset_left']
            },
            'show_layout_icons': {
                'type': 'boolean',
                'default': DEFAULTS['layout_menu']['show_layout_icons']
            }
        },
        'default': DEFAULTS['layout_menu']
    },
    "generate_layout_icons": {
        "type": "boolean",
        "default": DEFAULTS["generate_layout_icons"],
    },
    'container_padding': {
        'type': 'dict',
        'default': DEFAULTS['container_padding'],
        'required': False
    },
    'animation': {
        'type': 'dict',
        'schema': {
            'enabled': {
                'type': 'boolean',
                'default': DEFAULTS['animation']['enabled']
            },
            'type': {
                'type': 'string',
                'default': DEFAULTS['animation']['type']
            },
            'duration': {
                'type': 'integer',
                'default': DEFAULTS['animation']['duration']
            }
        },
        'default': DEFAULTS['animation']
    },
    'label_shadow': {
        'type': 'dict',
        'required': False,
        'schema': {
            'enabled': {'type': 'boolean', 'default': False},
            'color': {'type': 'string', 'default': 'black'},
            'offset': {'type': 'list', 'default': [1, 1]},
            'radius': {'type': 'integer', 'default': 3},
        },
        'default': {'enabled': False, 'color': 'black', 'offset': [1, 1], 'radius': 3}
    },
    'container_shadow': {
        'type': 'dict',
        'required': False,
        'schema': {
            'enabled': {'type': 'boolean', 'default': False},
            'color': {'type': 'string', 'default': 'black'},
            'offset': {'type': 'list', 'default': [1, 1]},
            'radius': {'type': 'integer', 'default': 3},
        },
        'default': {'enabled': False, 'color': 'black', 'offset': [1, 1], 'radius': 3}
    },
    'callbacks': {
        'type': 'dict',
        'schema': {
            'on_left': {
                'type': 'string',
                'default': DEFAULTS['callbacks']['on_left'],
                'allowed': ALLOWED_CALLBACKS
            },
            'on_middle': {
                'type': 'string',
                'default': DEFAULTS['callbacks']['on_middle'],
                'allowed': ALLOWED_CALLBACKS
            },
            'on_right': {
                'type': 'string',
                'default': DEFAULTS['callbacks']['on_middle'],
                'allowed': ALLOWED_CALLBACKS
            }
        },
        'default': DEFAULTS['callbacks']
    }
}