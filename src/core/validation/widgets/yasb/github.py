DEFAULTS = {
    'label': '{icon}',
    'label_alt': '{data} Notifications',
    'update_interval': 600,
    'token': "",
    'tooltip': True,
    'max_notification':30,
    'only_unread': False,
    'max_field_size': 100,
    'menu': {
        'blur': True,
        'round_corners': True,
        'round_corners_type': 'normal',
        'border_color': 'System',
        'alignment': 'right',
        'direction': 'down',
        'distance': 6
    },
    'icons': {
        'issue': '\uf41b',
        'pull_request': '\uea64',
        'release': '\uea84',
        'discussion': '\uf442',
        'default': '\uea84',
        'github_logo': '\uea84'
    },
    'animation': {
        'enabled': True,
        'type': 'fadeInOut',
        'duration': 200
    },
    'container_padding': {'top': 0, 'left': 0, 'bottom': 0, 'right': 0}
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
    'update_interval': {
        'type': 'integer',
        'default': DEFAULTS['update_interval'],
        'min': 60,
        'max': 3600
    },
    'token': {
        'type': 'string',
        'default': DEFAULTS['token']
    },
    'tooltip': {
        'type': 'boolean',
        'required': False,
        'default': DEFAULTS['tooltip']
    },
    'max_notification': {
        'type': 'integer',
        'default': DEFAULTS['max_notification']
    },
    'only_unread': {
        'type': 'boolean',
        'default': DEFAULTS['only_unread']
    },
    'max_field_size': {
        'type': 'integer',
        'default': DEFAULTS['max_field_size']
    },
    'menu': {
        'type': 'dict',
        'required': False,
        'schema': {
            'blur': {
                'type': 'boolean',
                'default': DEFAULTS['menu']['blur']
            },
            'round_corners': {
                'type': 'boolean',
                'default': DEFAULTS['menu']['round_corners']
            },
            'round_corners_type': {
                'type': 'string',
                'default': DEFAULTS['menu']['round_corners_type']
            },
            'border_color': {
                'type': 'string',
                'default': DEFAULTS['menu']['border_color']
            },
            'alignment': {
                'type': 'string',
                'default': DEFAULTS['menu']['alignment']
            },
            'direction': {
                'type': 'string',
                'default': DEFAULTS['menu']['direction']
            },
            'distance': {
                'type': 'integer',
                'default': DEFAULTS['menu']['distance']
            }
        },
        'default': DEFAULTS['menu']
    },
    'icons': {
        'type': 'dict',
        'required': False,
        'schema': {
            'issue': {
                'type': 'string',
                'default': DEFAULTS['icons']['issue']
            },
            'pull_request': {
                'type': 'string',
                'default': DEFAULTS['icons']['pull_request']
            },
            'release': {
                'type': 'string',
                'default': DEFAULTS['icons']['release']
            },
            'discussion': {
                'type': 'string',
                'default': DEFAULTS['icons']['discussion']
            },
            'default': {
                'type': 'string',
                'default': DEFAULTS['icons']['default']
            },
            'github_logo': {
                'type': 'string',
                'default': DEFAULTS['icons']['github_logo']
            }
        },
        'default': DEFAULTS['icons']
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
