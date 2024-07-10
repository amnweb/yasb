DEFAULTS = {
    'label_offline': 'Komorebi Offline',
    'label_workspace_btn': '{index}',
    'label_default_name': '',
    'label_zero_index': False,
    'hide_empty_workspaces': False
}

VALIDATION_SCHEMA = {
    'label_offline': {
        'type': 'string',
        'default': DEFAULTS['label_offline']
    },
    'label_workspace_btn': {
        'type': 'string',
        'default': DEFAULTS['label_workspace_btn']
    },
    'label_default_name': {
        'type': 'string',
        'default': DEFAULTS['label_default_name']
    },
    'label_zero_index': {
        'type': 'boolean',
        'default': DEFAULTS['label_zero_index']
    },
    'hide_empty_workspaces': {
        'type': 'boolean',
        'default': DEFAULTS['hide_empty_workspaces']
    }
}