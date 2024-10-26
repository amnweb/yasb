DEFAULTS = {
    'windows_update': {
        'enabled': False,
        'label': '{count}',
        'interval': 1440,
        'exclude': []
    },
    'winget_update': {
        'enabled': False,
        'label': '{count}',
        'interval': 240,
        'exclude': []
    }
}

VALIDATION_SCHEMA = {
    'windows_update': {
        'type': 'dict',
        'schema': {
            'enabled': {
                'type': 'boolean',
                'default': DEFAULTS['windows_update']['enabled']
            },
            'label': {
                'type': 'string',
                'default': DEFAULTS['windows_update']['label']
            },
            'interval': {
                'type': 'integer',
                'default': DEFAULTS['windows_update']['interval'],
                'min': 30,
                'max': 10080
            },
            'exclude': {
                'type': 'list',
                'default': DEFAULTS['windows_update']['exclude'],
                'schema': {
                    'type': 'string'
                }
            }
        }
    },
    'winget_update': {
        'type': 'dict',
        'schema': {
            'enabled': {
                'type': 'boolean',
                'default': DEFAULTS['winget_update']['enabled']
            },
            'label': {
                'type': 'string',
                'default': DEFAULTS['winget_update']['label']
            },
            'interval': {
                'type': 'integer',
                'default': DEFAULTS['winget_update']['interval'],
                'min': 10,
                'max': 10080
            },
            'exclude': {
                'type': 'list',
                'default': DEFAULTS['winget_update']['exclude'],
                'schema': {
                    'type': 'string'
                }
            }
        }
    }
}
