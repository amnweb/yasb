EXAMPLE_VALIDATION_SCHEMA = {
    'label': {
        'type': 'string',
        'default': 'Example Label'
    },
    'label_alt': {
        'type': 'string',
        'default': 'Example Label Alt'
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
                'default': 'toggle_label',
            },
            'on_middle': {
                'type': 'string',
                'default': 'do_nothing',
            },
            'on_right': {
                'type': 'string',
                'default': 'toggle_label',
            }
        },
        'default': {
            'on_left': 'toggle_label',
            'on_middle': 'do_nothing',
            'on_right': 'toggle_label'
        }
    }
}
