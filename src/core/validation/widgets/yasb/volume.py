DEFAULTS = {
    'label': "{volume[percent]}%",
    'label_alt': "{volume[percent]}%",
    'tooltip': True,
    'volume_icons': [
        "\ueee8",  # Icon for muted
        "\uf026",  # Icon for 0-10% volume
        "\uf027",  # Icon for 11-30% volume
        "\uf027",  # Icon for 31-60% volume
        "\uf028"   # Icon for 61-100% volume
    ],
    'animation': {
        'enabled': True,
        'type': 'fadeInOut',
        'duration': 200
    },
    'container_padding': {'top': 0, 'left': 0, 'bottom': 0, 'right': 0},
    'callbacks': {
        'on_middle': 'do_nothing',
        'on_right': 'do_nothing'
    },
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
    'tooltip': {
        'type': 'boolean',
        'required': False,
        'default': DEFAULTS['tooltip']
    },
    'volume_icons': {
        'type': 'list',
        'default': DEFAULTS['volume_icons'],
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
