DEFAULTS = {
    'label_workspace_btn': '{index}',
    'label_workspace_active_btn': '{index}',
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
    'container_padding': {
        'type': 'dict',
        'default': DEFAULTS['container_padding'],
        'required': False
    }
}