DEFAULTS = {
    'label': "{win[title]}",
    'label_alt': "[class_name='{win[class_name]}' exe='{win[process][name]}' hwnd={win[hwnd]}]",
    'label_no_window': None,
    'max_length': None,
    'max_length_ellipsis': '...',
    'monitor_exclusive': True,
    'ignore_windows': {
        'classes': [],
        'processes': [],
        'titles': []
    },
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
    'label_no_window': {
        'type': 'string',
        'nullable': True,
        'default': DEFAULTS['label_no_window']
    },
    'max_length': {
        'type': 'integer',
        'min': 1,
        'nullable': True,
        'default': DEFAULTS['max_length']
    },
    'max_length_ellipsis': {
        'type': 'string',
        'default': DEFAULTS['max_length_ellipsis']
    },
    'monitor_exclusive': {
        'type': 'boolean',
        'required': False,
        'default': DEFAULTS['monitor_exclusive']
    },
    'ignore_window': {
        'type': 'dict',
        'schema': {
            'classes': {
                'type': 'list',
                'schema': {
                    'type': 'string'
                },
                'default': DEFAULTS['ignore_windows']['classes']
            },
            'processes': {
                'type': 'list',
                'schema': {
                    'type': 'string'
                },
                'default': DEFAULTS['ignore_windows']['processes']
            },
            'titles': {
                'type': 'list',
                'schema': {
                    'type': 'string'
                },
                'default': DEFAULTS['ignore_windows']['titles']
            }
        },
        'default': DEFAULTS['ignore_windows']
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
                'default': DEFAULTS['callbacks']['on_right']
            }
        },
        'default': DEFAULTS['callbacks']
    }
}
