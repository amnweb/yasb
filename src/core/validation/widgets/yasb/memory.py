DEFAULTS = {
    'label': "\uf538 {virtual_mem_free}/{virtual_mem_total}",
    'label_alt': "\uf538 VIRT: {virtual_mem_percent}% SWAP: {swap_mem_percent}%",
    'update_interval': 5000,
    'callbacks': {
        'on_left': "toggle_label",
        'on_middle': "do_nothing",
        'on_right': "do_nothing"
    },
    'memory_thresholds': {
        'low': 25,
        'medium': 50,
        'high': 90,
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
    'memory_thresholds': {
        'type': 'dict',
        'required': False,
        'schema': {
            'low': {
                'type': 'integer',
                'default': DEFAULTS['memory_thresholds']['low'],
                'min': 0,
                'max': 100
            },
            'medium': {
                'type': 'integer',
                'default': DEFAULTS['memory_thresholds']['medium'],
                'min': 0,
                'max': 100
            },
            'high': {
                'type': 'integer',
                'default': DEFAULTS['memory_thresholds']['high'],
                'min': 0,
                'max': 100
            }
        },
        'default': DEFAULTS['memory_thresholds']
    },
    'callbacks': {
        'type': 'dict',
        'schema': {
            'on_left': {
                'type': 'string',
                'nullable': True,
                'default': DEFAULTS['callbacks']['on_left'],
            },
            'on_middle': {
                'type': 'string',
                'nullable': True,
                'default': DEFAULTS['callbacks']['on_middle'],
            },
            'on_right': {
                'type': 'string',
                'nullable': True,
                'default': DEFAULTS['callbacks']['on_right']
            }
        },
        'default': DEFAULTS['callbacks']
    }
}
