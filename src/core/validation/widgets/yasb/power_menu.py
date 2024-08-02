DEFAULTS = {
    'label': "power",
    'uptime': True,
    'blur': False,
    'blur_background': True,
    'animation_duration': 200,
    'button_row': 3
}

VALIDATION_SCHEMA = {
    'label': {
        'type': 'string',
        'default': DEFAULTS['label']
    },
    'uptime': {
        'type': 'boolean',
        'default': DEFAULTS['uptime'],
        'required': False
    },
    'blur': {
        'type': 'boolean',
        'default': DEFAULTS['blur']
    },
    'blur_background': {
        'type': 'boolean',
        'default': DEFAULTS['blur_background']
    },
    'animation_duration': {
        'type': 'integer',
        'default': DEFAULTS['animation_duration'],
        'min': 0,
        'max': 2000
    },
    'button_row': {
        'type': 'integer',
        'default': DEFAULTS['button_row'],
        'min': 1,
        'max': 5
    },
    'buttons': {
        'type': 'dict',
        'schema': {
            'lock': {
                'type': 'list',
                'required': False
            },
            'signout': {
                'type': 'list',
                'required': False
            },
            'sleep': {
                'type': 'list',
                'required': False
            },
            'restart': {
                'type': 'list',
                'required': True
            },
            'shutdown': {
                'type': 'list',
                'required': True
            },
            'cancel': {
                'type': 'list',
                'required': True
            },
            'hibernate': {
                'type': 'list',
                'required': False
            },
            'force_shutdown': {
                'type': 'list',
                'required': False
            },
            'force_restart': {
                'type': 'list',
                'required': False
            }
        }
    }
}