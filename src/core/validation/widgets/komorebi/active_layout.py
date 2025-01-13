DEFAULTS = {
    'hide_if_offline': False,
    "label": "{icon}",
    'layouts': ['bsp', 'columns', 'rows', 'grid', 'vertical_stack', 'horizontal_stack', 'ultrawide_vertical_stack', 'right_main_vertical_stack'],
    'layout_icons': {
        "bsp": "[\\\\]",
        "columns": "[||]",
        "rows": "[==]",
        "grid": "[G]",
        "vertical_stack": "[V]=",
        "horizontal_stack": "[H]=",
        "ultrawide_vertical_stack": "||=",
        "right_main_vertical_stack": "=||",
        "monocle": "[M]",
        "maximised": "[X]",
        "floating": "><>",
        "paused": "[P]"
    },
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
    "toggle_pause"
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
        },
        'default': DEFAULTS['layout_icons']
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