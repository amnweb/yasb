DEFAULTS = {
    'label': "\uf11c",
    'container_padding': {'top': 0, 'left': 0, 'bottom': 0, 'right': 0},
}
VALIDATION_SCHEMA = {
    'label': {
        'type': 'string',
        'default': DEFAULTS['label']
    },
    'container_padding': {
        'type': 'dict',
        'default': DEFAULTS['container_padding'],
        'required': False
    },
}