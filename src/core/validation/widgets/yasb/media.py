DEFAULTS = {
    'label': '\uf017 {%H:%M:%S}',
    'label_alt': '\uf017 {%d-%m-%y %H:%M:%S}',
    'callbacks': {
        'on_left': 'toggle_label',
        'on_middle': 'do_nothing',
        'on_right': 'do_nothing'
    }
}

VALIDATION_SCHEMA = {
    'label': {
        'type': 'string',
        'default': DEFAULTS['label']
    },
    'label_alt': {
        'type': 'string',
        'default': DEFAULTS['label_alt']
    },
    'hide_empty': {
        'type': 'boolean',
        'default': False
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
                'default': DEFAULTS['callbacks']['on_right'],
            }
        },
        'default': DEFAULTS['callbacks']
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
    'thumbnail_alpha': {
        'type': 'integer',
        'default': 50,
        'min': 0,
        'max': 255
    },
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
