DEFAULTS = {
    'label': '\udb80\udcb1',
    'label_alt': '\uf293',
    'icons': {
        'bluetooth_on': '\udb80\udcaf',
        'bluetooth_off': '\udb80\udcb2',
        'bluetooth_connected': '\udb80\udcb1',
    },
    'container_padding': {'top': 0, 'left': 0, 'bottom': 0, 'right': 0},
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
    'icons': {
        'type': 'dict',
        'schema': {
            'bluetooth_on': {
                'type': 'string',
                'default': DEFAULTS['icons']['bluetooth_on']
            },
            'bluetooth_off': {
                'type': 'string',
                'default': DEFAULTS['icons']['bluetooth_off']
            },
            'bluetooth_connected': {
                'type': 'string',
                'default': DEFAULTS['icons']['bluetooth_connected']
            }
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
