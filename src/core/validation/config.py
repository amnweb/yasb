from core.validation.bar import BAR_SCHEMA, BAR_DEFAULTS

CONFIG_SCHEMA = {
    'watch_config': {
        'type': 'boolean',
        'default': True
    },
    'watch_stylesheet': {
        'type': 'boolean',
        'default': True,
    },
    'debug': {
        'type': 'boolean',
        'default': False,
        'required': False,
    },
    'hide_taskbar': {
        'type': 'boolean',
        'default': False,
        'required': False,
    },
    'komorebi': {
        'type': 'dict',
        'schema': {
            'start_command': {
                'type': 'string',
                'required': False,
            },
            'stop_command': {
                'type': 'string',
                'required': False,
            },
            'reload_command': {
                'type': 'string',
                'required': False,
            }
        },
        'default': {
            'start_command': 'komorebic start --whkd',
            'stop_command': 'komorebic stop --whkd',
            'reload_command': 'komorebic reload-configuration'
        }
    },
    'bars': {
        'type': 'dict',
        'keysrules': {
            'type': 'string'
        },
        'valuesrules': BAR_SCHEMA,
        'default': {
            'yasb-bar': BAR_DEFAULTS
        }
    },
    'widgets': {
        'type': 'dict',
        'keysrules': {
            'type': 'string',
        },
        'valuesrules': {
            'type': ['string', 'dict']
        },
        'default': {}
    }
}
