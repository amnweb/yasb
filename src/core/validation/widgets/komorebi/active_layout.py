DEFAULTS = {
    'hide_if_offline': False,
    "label": "{icon}",
    'layout_icons': {
        "bsp": "[\\\\]",
        "columns": "[||]",
        "rows": "[==]",
        "grid": "[G]",
        "vertical_stack": "[V]=",
        "horizontal_stack": "[H]=",
        "ultrawide_vertical_stack": "||=",
        "monocle": "[M]",
        "maximised": "[X]",
        "floating": "><>",
        "paused": "[P]"
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
