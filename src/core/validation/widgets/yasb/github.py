DEFAULTS = {
    'label': '{icon}',
    'label_alt': '{data} Notifications',
    'update_interval': 600,
    'token': "",
    'tooltip': True,
    'max_notification':20,
    'only_unread': False,
    'max_field_size': 100,
    'menu_width': 400,
    'menu_height': 400,
    'menu_offset': 240,
    'animation': {
        'enabled': True,
        'type': 'fadeInOut',
        'duration': 200
    },
    'container_padding': {'top': 0, 'left': 0, 'bottom': 0, 'right': 0}
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
        'min': 60,
        'max': 3600
    },
    'token': {
        'type': 'string',
        'default': DEFAULTS['token']
    },
    'tooltip': {
        'type': 'boolean',
        'required': False,
        'default': DEFAULTS['tooltip']
    },
    'max_notification': {
        'type': 'integer',
        'default': DEFAULTS['max_notification']
    },
    'only_unread': {
        'type': 'boolean',
        'default': DEFAULTS['only_unread']
    },
    'max_field_size': {
        'type': 'integer',
        'default': DEFAULTS['max_field_size']
    },
    'menu_width': {
        'type': 'integer',
        'default': DEFAULTS['menu_width']
    },
    'menu_height': {
        'type': 'integer',
        'default': DEFAULTS['menu_height']
    },
    'menu_offset': {
        'type': 'integer',
        'default': DEFAULTS['menu_offset']
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
    }
}
