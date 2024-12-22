DEFAULTS = {
    'label': '\ue71a',
    'container_padding': {'top': 0, 'left': 0, 'bottom': 0, 'right': 0},
    'power_menu': True,
    'system_menu': True,
    'blur': False,
    'alignment': 'left',
    'direction': 'down',
    'distance': 6,
    'menu_labels': {'shutdown': 'Shutdown', 'restart': 'Restart', 'logout': 'Logout', 'lock': 'Lock', 'sleep': 'Sleep', 'system': 'System Settings', 'about': 'About This PC', 'task_manager': 'Task Manager'},
    'callbacks': {
        'on_left': 'toggle_menu'
    }
}

VALIDATION_SCHEMA = {
    'label': {
        'type': 'string',
        'default': DEFAULTS['label']
    },
    'menu_list': {
        'required': False,
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                'title': {'type': 'string'},
                'path': {'type': 'string'}
            }
        }
    },
    'container_padding': {
        'type': 'dict',
        'default': DEFAULTS['container_padding'],
        'required': False
    },
    'power_menu': {
        'type': 'boolean',
        'default': DEFAULTS['power_menu'],
        'required': False
    },
    'system_menu': {
        'type': 'boolean',
        'default': DEFAULTS['system_menu'],
        'required': False
    },
    'blur': {
        'type': 'boolean',
        'default': DEFAULTS['blur'],
        'required': False
    },
    'alignment': {
        'type': 'string',
        'default': DEFAULTS['alignment'],
        'required': False
    },
    'direction': {
        'type': 'string',
        'default': DEFAULTS['direction'],
        'required': False
    },
    'distance': {
        'type': 'integer',
        'default': DEFAULTS['distance'],
        'required': False
    },
    'menu_labels': {
        'type': 'dict',
        'required': False,
        'schema': {
            'shutdown': {'type': 'string', 'default': DEFAULTS['menu_labels']['shutdown']},
            'restart': {'type': 'string', 'default': DEFAULTS['menu_labels']['restart']},
            'logout': {'type': 'string', 'default': DEFAULTS['menu_labels']['logout']},
            'lock': {'type': 'string', 'default': DEFAULTS['menu_labels']['lock']},
            'sleep': {'type': 'string', 'default': DEFAULTS['menu_labels']['sleep']},
            'system': {'type': 'string', 'default': DEFAULTS['menu_labels']['system']},
            'about': {'type': 'string', 'default': DEFAULTS['menu_labels']['about']},
            'task_manager': {'type': 'string', 'default': DEFAULTS['menu_labels']['task_manager']}
        },
        'default': DEFAULTS['menu_labels']
    },
    'callbacks': {
        'required': False,
        'type': 'dict',
        'schema': {
            'on_left': {
                'type': 'string',
                'default': DEFAULTS['callbacks']['on_left']
            }
        },
        'default': DEFAULTS['callbacks']
    }
}
