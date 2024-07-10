DEFAULTS = {
    'label': '\uf200 {info[histograms][cpu_percent]}',
    'label_alt': '\uf200 CPU: {info[percent][total]}% | freq: {info[freq][current]:.2f} Mhz',
    'update_interval': 1000,
    'histogram_icons': [
        '\u2581',
        '\u2581',
        '\u2582',
        '\u2583',
        '\u2584',
        '\u2585',
        '\u2586',
        '\u2587',
        '\u2588'
    ],
    'histogram_num_columns': 10,
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
    'update_interval': {
        'type': 'integer',
        'default': DEFAULTS['update_interval'],
        'min': 0,
        'max': 60000
    },
    'histogram_icons': {
        'type': 'list',
        'default': DEFAULTS['histogram_icons'],
        'minlength': 9,
        'maxlength': 9,
        "schema": {
            'type': 'string'
        }
    },
    'histogram_num_columns': {
        'type': 'integer',
        'default': DEFAULTS['histogram_num_columns'],
        'min': 0,
        'max': 128
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
