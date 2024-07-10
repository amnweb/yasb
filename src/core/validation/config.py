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
