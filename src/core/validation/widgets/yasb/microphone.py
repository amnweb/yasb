DEFAULTS = {
    'label': '{icon}',
    'label_alt': '{icon} {level}%',
    'icons': {
        'normal': '\uf130',
        'muted': '\uf131',
    },
    'container_padding': {'top': 0, 'left': 0, 'bottom': 0, 'right': 0},
    'callbacks': {
        'on_left': 'toggle_mute',
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
    'icons': {
        'type': 'dict',
        'schema': {
            'normal': {'type': 'string', 'default': DEFAULTS['icons']['normal']},
            'muted': {'type': 'string', 'default': DEFAULTS['icons']['muted']}
        },
        'default': DEFAULTS['icons']
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
                'default': DEFAULTS['callbacks']['on_right'],
            }
        },
        'default': DEFAULTS['callbacks']
    }
}
