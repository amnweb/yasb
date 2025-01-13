DEFAULTS = {
    'class_name': 'libre-monitor-widget',
    'label': '<span>\udb82\udcae </span> {info[value]}{info[unit]}',
    'label_alt': '<span>\uf437 </span>{info[histogram]} {info[value]} ({info[min]}/{info[max]}) {info[unit]}',
    'update_interval': 1000,
    'sensor_id': '/amdcpu/0/load/0',
    'histogram_icons': [
        r'\u2581',
        r'\u2581',
        r'\u2582',
        r'\u2583',
        r'\u2584',
        r'\u2585',
        r'\u2586',
        r'\u2587',
        r'\u2588'
    ],
    'histogram_num_columns': 10,
    'precision': 2,
    'history_size': 60,
    'histogram_fixed_min': None,
    'histogram_fixed_max': None,
    'sensor_id_error_label': "N/A",
    'connection_error_label': "Connection error...",
    'auth_error_label': "Auth Failed...",
    'server_host': 'localhost',
    'server_port': 8085,
    'server_username': '',
    'server_password': '',
    'callbacks': {
        'on_left': 'toggle_label',
        'on_middle': 'do_nothing',
        'on_right': 'do_nothing'
    },
    'container_padding': {'top': 0, 'left': 0, 'bottom': 0, 'right': 0},
    'animation': {
        'enabled': True,
        'type': 'fadeInOut',
        'duration': 200
    }
}

VALIDATION_SCHEMA = {
    'class_name': {
        'type': 'string',
        'default': DEFAULTS['class_name'],
        'required': False,
    },
    'label': {
        'type': 'string',
        'default': DEFAULTS['label']
    },
    'label_alt': {
        'type': 'string',
        'default': DEFAULTS['label_alt']
    },
    'update_interval': {
        'type': 'integer',
        'default': DEFAULTS['update_interval'],
        'min': 0,
        'max': 60000
    },
    'sensor_id': {
        'type': 'string',
        'default': DEFAULTS['sensor_id'],
    },
    'histogram_icons': {
        'type': 'list',
        'default': DEFAULTS['histogram_icons'],
        'minlength': 9,
        'maxlength': 9,
        "schema": {
            'type': 'string'
        }
    },
    'histogram_num_columns': {
        'type': 'integer',
        'default': DEFAULTS['histogram_num_columns'],
        'min': 0,
        'max': 128
    },
    'precision': {
        'type': 'integer',
        'default': DEFAULTS['precision'],
        'min': 0,
        'max': 30,
        'required': False,
    },
    'history_size': {
        'type': 'integer',
        'default': DEFAULTS['history_size'],
        'min': DEFAULTS["histogram_num_columns"],
        'max': 50000,
        'required': False,
    },
    'histogram_fixed_min': {
        'type': 'float',
        'default': DEFAULTS['histogram_fixed_min'],
        'min': -10000.0,
        'max': 10000.0,
        'required': False,
        'nullable': True
    },
    'histogram_fixed_max': {
        'type': 'float',
        'default': DEFAULTS['histogram_fixed_max'],
        'min': -10000.0,
        'max': 10000.0,
        'required': False,
        'nullable': True
    },
    'sensor_id_error_label': {
        'type': 'string',
        'default': DEFAULTS['sensor_id_error_label'],
        'required': False,
    },
    'connection_error_label': {
        'type': 'string',
        'default': DEFAULTS['connection_error_label'],
        'required': False,
    },
    'auth_error_label': {
        'type': 'string',
        'default': DEFAULTS['auth_error_label'],
        'required': False,
    },
    'server_host': {
        'type': 'string',
        'default': DEFAULTS['server_host'],
        'required': False,
    },
    'server_port': {
        'type': 'integer',
        'default': DEFAULTS['server_port'],
        'min': 0,
        'max': 65535,
        'required': False,
    },
    'server_username': {
        'type': 'string',
        'default': DEFAULTS['server_username'],
        'required': False,
    },
    'server_password': {
        'type': 'string',
        'default': DEFAULTS['server_password'],
        'required': False,
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
    }
}
