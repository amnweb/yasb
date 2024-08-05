DEFAULTS = {
    'label': "{icon}",
    'update_interval': 60,
    'change_automatically': False,
    'image_path': ""
}

VALIDATION_SCHEMA = {
    'label': {
        'type': 'string',
        'default': DEFAULTS['label']
    },
    'update_interval': {
        'type': 'integer',
        'default': DEFAULTS['update_interval'],
        'min': 60,
        'max': 86400
    },
    'change_automatically': {
        'type': 'boolean',
        'default': DEFAULTS['change_automatically']
    },
    'image_path': {
        'required': True,
        'type': 'string',
        'default': DEFAULTS['image_path']
    }
}
