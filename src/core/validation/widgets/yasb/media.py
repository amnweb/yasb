VALIDATION_SCHEMA = {
    'label_main': {
        'type': 'string',
        'default': '{title}'
    },
    'label_sub': {
        'type': 'string',
        'default': '{artist}'
    },
    'hide_empty': {
        'type': 'boolean',
        'default': False
    },
    'update_interval': {
        'type': 'integer',
        'default': 1000,
        'min': 0,
        'max': 60000
    },
    'callbacks': {
        'type': 'dict',
        'schema': {
            'on_left': {
                'type': 'string',
                'default': 'do_nothing',
            },
            'on_middle': {
                'type': 'string',
                'default': 'do_nothing',
            },
            'on_right': {
                'type': 'string',
                'default': 'do_nothing',
            }
        },
        'default': {
            'on_left': 'do_nothing',
            'on_middle': 'do_nothing',
            'on_right': 'do_nothing'
        }
    },
    'max_field_size': {
        'type': 'dict',
        'schema': {
            'label': {
                'type': 'integer',
                'default': 15,
                'min': 0,
                'max': 200
            },
            'label_alt': {
                'type': 'integer',
                'default': 30,
                'min': 0,
                'max': 200
            }
        }
    },
    'show_thumbnail': {
        'type': 'boolean',
        'default': True
    },
    'controls_only': {
        'type': 'boolean',
        'default': False
    },
    'controls_left': {
        'type': 'boolean',
        'default': True
    },
    'thumbnail_alpha_range': {
        'type': 'float',
        'default': 1.0,
        'min': 0.0,
        'max': 1.0
    },
    'thumbnail_alpha_multiplier': {
        'type': 'float',
        'default': 0.6,
        'min': 0.0,
        'max': 1.0},
    'thumbnail_padding': {
        'type': 'integer',
        'default': 8,
        'min': 0,
        'max': 200
    },
    'thumbnail_corner_radius': {
        'type': 'integer',
        'default': 0,
        'min': 0,
        'max': 100
    },
    'icons': {
        'type': 'dict',
        'schema': {
            'prev_track': {
                'type': 'string',
                'default': '\uf048',
            },
            'next_track': {
                'type': 'string',
                'default': '\uf051',
            },
            'play': {
                'type': 'string',
                'default': '\uf04b',
            },
            'pause': {
                'type': 'string',
                'default': '\uf04c',
            },
        },
    }
}
