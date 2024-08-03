DEFAULTS = {
    'label': "{wifi_icon}",
    'label_alt': "{wifi_icon} {wifi_name}",
    'update_interval': 1000,
    'callbacks': {
        'on_left': 'toggle_label',
        'on_middle': 'do_nothing',
        'on_right': 'do_nothing'
    },
    'wifi_icons': [
        "\ueb5e",  # Icon for 0% strength
        "\ue872",  # Icon for 1-25% strength
        "\ue873",  # Icon for 26-50% strength
        "\ue874",  # Icon for 51-75% strength
        "\ue701"   # Icon for 76-100% strength
    ],
    'ethernet_icon': "\ue839"
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
    'wifi_icons': {
        'type': 'list',
        'default': DEFAULTS['wifi_icons'],
        "schema": {
            'type': 'string',
            'required': False
        }
    },
    'ethernet_icon': {
        'type': 'string',
        'default': DEFAULTS['ethernet_icon']
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
