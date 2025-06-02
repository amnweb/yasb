DEFAULTS = {
    'class_name': 'grouper',
    'widgets': [],
    'container_padding': {'top': 0, 'left': 0, 'bottom': 0, 'right': 0},
}

VALIDATION_SCHEMA = {
    'class_name': {
        'type': 'string',
        'default': DEFAULTS['class_name']
    },
    'widgets': {
        'type': 'list',
        'default': DEFAULTS['widgets'],
        'schema': {
            'type': 'string',
            'required': False,
        }
    },
    'container_padding': {
        'type': 'dict',
        'required': False,
        'schema': {
            'top': {
                'type': 'integer',
                'default': DEFAULTS['container_padding']['top']
            },
            'left': {
                'type': 'integer',
                'default': DEFAULTS['container_padding']['left']
            },
            'bottom': {
                'type': 'integer',
                'default': DEFAULTS['container_padding']['bottom']
            },
            'right': {
                'type': 'integer',
                'default': DEFAULTS['container_padding']['right']
            }
        },
        'default': DEFAULTS['container_padding']
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
}