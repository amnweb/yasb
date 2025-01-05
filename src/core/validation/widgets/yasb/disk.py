DEFAULTS = {
    'label': "{volume_label} {space[used][percent]}",
    'label_alt': "{volume_label} {space[used][gb]} / {space[total][gb]}",
    'volume_label': "C",
    'update_interval': 60,
    'decimal_display': 1,
    'group_label': {
        'enabled': False,
        'volume_labels': ['C'],
        'blur': True,
        'alignment': 'right',
        'direction': 'down',
        'distance': 6,
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
    'volume_label': {
        'type': 'string',
        'default': DEFAULTS['volume_label']
    },
    'update_interval': {
        'type': 'integer',
        'default': DEFAULTS['update_interval'],
        'min': 0,
        'max': 3600
    },
    'decimal_display': {
        'required': False,
        'type': 'integer',
        'default': DEFAULTS['decimal_display'],
        'min': 0,
        'max': 3
    },
    'group_label': {
        'type': 'dict',
        'required': False,
        'schema': {
            'enabled': {
                'type': 'boolean',
                'default': DEFAULTS['group_label']['enabled']
            },
            'volume_labels': {
                'type': 'list',
                'schema': {
                    'type': 'string'
                },
                'default': DEFAULTS['group_label']['volume_labels']
            },
            'blur': {
                'type': 'boolean',
                'default': DEFAULTS['group_label']['blur']
            },
            'alignment': {
                'type': 'string',
                'default': DEFAULTS['group_label']['alignment']
            },
            'direction': {
                'type': 'string',
                'default': DEFAULTS['group_label']['direction']
            },
            'distance': {
                'type': 'integer',
                'default': DEFAULTS['group_label']['distance']
            }
        },
        'default': DEFAULTS['group_label']
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