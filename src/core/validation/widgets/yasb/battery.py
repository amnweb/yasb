DEFAULTS = {
    'label': '{icon}',
    'label_alt': '{percent}% | remaining: {time_remaining}',
    'update_interval': 5000,
    'time_remaining_natural': False,
    'charging_options': {
        'icon_format': '{charging_icon} {icon}',
        'blink_charging_icon': True
    },
    'status_thresholds': {
        'critical': 10,
        'low': 25,
        'medium': 75,
        'high': 95,
        'full': 100,
    },
    'status_icons': {
        'icon_charging': '\uf0e7',
        'icon_critical': '\uf244',
        'icon_low': '\uf243',
        'icon_medium': '\uf242',
        'icon_high': '\uf241',
        'icon_full': '\uf240'
    },
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
        'min': 0,
        'max': 60000,
        'default': DEFAULTS['update_interval']
    },
    'time_remaining_natural': {
        'type': 'boolean',
        'default': DEFAULTS['time_remaining_natural']
    },
    'charging_options': {
        'type': 'dict',
        'schema': {
            'icon_format': {
                'type': 'string',
                'default': DEFAULTS['charging_options']['icon_format']
            },
            'blink_charging_icon': {
                'type': 'boolean',
                'default': DEFAULTS['charging_options']['blink_charging_icon']
            }
        },
        'default': DEFAULTS['charging_options']
    },
    'status_thresholds': {
        'type': 'dict',
        'schema': {
            'critical': {
                'type': 'integer',
                'min': 0,
                'max': 100,
                'default': DEFAULTS['status_thresholds']['critical']
            },
            'low': {
                'type': 'integer',
                'min': 0,
                'max': 100,
                'default': DEFAULTS['status_thresholds']['low']
            },
            'medium': {
                'type': 'integer',
                'min': 0,
                'max': 100,
                'default': DEFAULTS['status_thresholds']['medium']
            },
            'high': {
                'type': 'integer',
                'min': 0,
                'max': 100,
                'default': DEFAULTS['status_thresholds']['high']
            },
            'full': {
                'type': 'integer',
                'min': 0,
                'max': 100,
                'default': DEFAULTS['status_thresholds']['full']
            }
        },
        'default': DEFAULTS['status_thresholds']
    },
    'status_icons': {
        'type': 'dict',
        'schema': {
            'icon_charging': {
                'type': 'string',
                'default': DEFAULTS['status_icons']['icon_charging']
            },
            'icon_critical': {
                'type': 'string',
                'default': DEFAULTS['status_icons']['icon_critical']
            },
            'icon_low': {
                'type': 'string',
                'default': DEFAULTS['status_icons']['icon_low']
            },
            'icon_medium': {
                'type': 'string',
                'default': DEFAULTS['status_icons']['icon_medium']
            },
            'icon_high': {
                'type': 'string',
                'default': DEFAULTS['status_icons']['icon_high']
            },
            'icon_full': {
                'type': 'string',
                'default': DEFAULTS['status_icons']['icon_full']
            },
        },
        'default': DEFAULTS['status_icons']
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
                'default': DEFAULTS['callbacks']['on_right']
            }
        },
        'default': DEFAULTS['callbacks']
    }
}
