DEFAULTS = {
    'label': '{icon}',
    'label_alt': '{data} Notifications',
    'update_interval': 600,
    "token": "",
    "max_notification":20,
    "only_unread": False,
    "max_field_size": 100,
    "menu_width": 400,
    "menu_height": 400,
    "menu_offset": 240
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
    }
}
