DEFAULTS = {
    'icon_size': 16,
    'animation': False,
    'ignore_apps': {
        'classes': [],
        'processes': [],
        'titles': []
    },
    'container_padding': {'top': 0, 'left': 0, 'bottom': 0, 'right': 0},
    'callbacks': {
        'on_left': 'toggle_app',
        'on_middle': 'do_nothing',
        'on_right': 'do_nothing'
    }
}

VALIDATION_SCHEMA = {
    'icon_size': {
        'type': 'integer',
        'default': DEFAULTS['icon_size']
    },
    'animation': {
        'type': 'boolean',
        'default': DEFAULTS['animation'],
        'required': False
    },
    'ignore_apps': {
        'type': 'dict',
        'schema': {
            'classes': {
                'type': 'list',
                'schema': {
                    'type': 'string'
                },
                'default': DEFAULTS['ignore_apps']['classes']
            },
            'processes': {
                'type': 'list',
                'schema': {
                    'type': 'string'
                },
                'default': DEFAULTS['ignore_apps']['processes']
            },
            'titles': {
                'type': 'list',
                'schema': {
                    'type': 'string'
                },
                'default': DEFAULTS['ignore_apps']['titles']
            }
        },
        'default': DEFAULTS['ignore_apps']
    },
    'container_padding': {
        'type': 'dict',
        'default': DEFAULTS['container_padding'],
        'required': False
    },
    'callbacks': {
        'type': 'dict',
        'schema': {
            'on_left': {
                'type': 'string',
                'default': DEFAULTS['callbacks']['on_left'],
            },
            'on_middle': {
                'type': 'string',
                'default': DEFAULTS['callbacks']['on_middle'],
            },
            'on_right': {
                'type': 'string',
                'default': DEFAULTS['callbacks']['on_right']
            }
        },
        'default': DEFAULTS['callbacks']
    }
}