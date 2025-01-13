DEFAULTS = {
    'label_workspace_btn': '{index}',
    'label_workspace_active_btn': '{index}',
    'switch_workspace_animation': True,
    'container_padding': {'top': 0, 'left': 0, 'bottom': 0, 'right': 0},
}
VALIDATION_SCHEMA = {
    'label_workspace_btn': {
        'type': 'string',
        'default': DEFAULTS['label_workspace_btn']
    },
    'label_workspace_active_btn': {
        'type': 'string',
        'default': DEFAULTS['label_workspace_active_btn']
    },
    'switch_workspace_animation': {
        'type': 'boolean',
        'required': False,
        'default': DEFAULTS['switch_workspace_animation']
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