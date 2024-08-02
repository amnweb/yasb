VALIDATION_SCHEMA = {
    'label': {
        'type': 'string'
    },
    'class_name': {
        'type': 'string',
        'required': False,
        'default': ""
    },
    'app_list': {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                'icon': {'type': 'string'},
                'launch': {'type': 'string'}
            }
        }
    }
}
