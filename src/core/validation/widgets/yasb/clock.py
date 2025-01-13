DEFAULTS = {
    'label': '\uf017 {%H:%M:%S}',
    'label_alt': '\uf017 {%d-%m-%y %H:%M:%S}',
    'update_interval': 1000,
    'locale':"",
    'tooltip': True,
    'timezones': [],
    'animation': {
        'enabled': True,
        'type': 'fadeInOut',
        'duration': 200
    },
    'container_padding': {'top': 0, 'left': 0, 'bottom': 0, 'right': 0},
    'callbacks': {
        'on_left': 'toggle_label',
        'on_middle': 'do_nothing',
        'on_right': 'next_timezone'
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
    'locale': {
        'required': False,
        'type': 'string',
        'default': DEFAULTS['locale']
    },
    'tooltip': {
        'type': 'boolean',
        'required': False,
        'default': DEFAULTS['tooltip']
    },
    'update_interval': {
        'type': 'integer',
        'default': 1000,
        'min': 0,
        'max': 60000
    },
    'timezones': {
        'type': 'list',
        'default': DEFAULTS['timezones'],
        "schema": {
            'type': 'string',
            'required': False
        }
    },
    'animation': {
        'type': 'dict',
        'required': False,
        'schema': {
            'enabled': {
                'type': 'boolean',
                'default': DEFAULTS['animation']['enabled']
            },
            'type': {
                'type': 'string',
                'default': DEFAULTS['animation']['type']
            },
            'duration': {
                'type': 'integer',
                'default': DEFAULTS['animation']['duration']
            }
        },
        'default': DEFAULTS['animation']
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
