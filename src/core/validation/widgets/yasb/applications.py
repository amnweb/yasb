VALIDATION_SCHEMA = {
    'label': {
        'type': 'string'
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
