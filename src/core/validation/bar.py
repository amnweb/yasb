BAR_DEFAULTS = {
    'enabled': True,
    'screens': ['*'],
    'class_name': 'yasb-bar',
    'alignment': {'position': 'top', 'center': False},
    'blur_effect': {'enabled': False, 'dark_mode': False, 'acrylic': False,'round_corners': False,'round_corners_type':'normal','border_color': "System"},
    'animation': {'enabled': True, 'duration': 500},
    'window_flags': {'always_on_top': False, 'windows_app_bar': False, 'hide_on_fullscreen': False},
    'dimensions': {'width': '100%', 'height': 30},
    'padding': {'top': 0, 'left': 0, 'bottom': 0, 'right': 0},
    'widgets': {'left': [], 'center': [], 'right': []}
}

BAR_SCHEMA = {
    'type': 'dict',
    'required': True,
    'schema': {
        'enabled': {
            'type': 'boolean',
            'required': True,
            'default': BAR_DEFAULTS['enabled']
        },
        'screens': {
            'type': 'list',
            'schema': {
                'type': 'string'
            },
            'default': BAR_DEFAULTS['screens']
        },
        'class_name': {
            'type': 'string',
            'default': BAR_DEFAULTS['class_name']
        },
        'alignment': {
            'type': 'dict',
            'schema': {
                'position': {
                    'type': 'string',
                    'allowed': ['top', 'bottom'],
                    'default': BAR_DEFAULTS['alignment']['position']
                },
                'center': {
                    'type': 'boolean',
                    'default': BAR_DEFAULTS['alignment']['center']
                }
            },
            'default': BAR_DEFAULTS['alignment']
        },
        'blur_effect': {
            'type': 'dict',
            'schema': {
                'enabled': {
                    'type': 'boolean',
                    'default': BAR_DEFAULTS['blur_effect']['enabled']
                },
                'dark_mode': {
                    'type': 'boolean',
                    'default': BAR_DEFAULTS['blur_effect']['dark_mode']
                },
                'acrylic': {
                    'type': 'boolean',
                    'default': BAR_DEFAULTS['blur_effect']['acrylic']
                },
                'round_corners': {
                    'type': 'boolean',
                    'default': BAR_DEFAULTS['blur_effect']['round_corners']
                },
                'round_corners_type': {
                    'type': 'string',
                    'allowed': ['normal', 'small'],
                    'default': BAR_DEFAULTS['blur_effect']['round_corners_type']
                },
                'border_color': {
                    'type': 'string',
                    'default': BAR_DEFAULTS['blur_effect']['border_color']
                }
            },
            'default': BAR_DEFAULTS['blur_effect']
        },
        'animation': {
            'type': 'dict',
            'required': False,
            'schema': {
                'enabled': {
                    'type': 'boolean',
                    'default': BAR_DEFAULTS['animation']['enabled']
                },
                'duration': {
                    'type': 'integer',
                    'min': 0,
                    'default': BAR_DEFAULTS['animation']['duration']
                }
            },
            'default': BAR_DEFAULTS['animation']
        },
        'window_flags': {
            'type': 'dict',
            'schema': {
                'always_on_top': {
                    'type': 'boolean',
                    'default':  BAR_DEFAULTS['window_flags']['always_on_top']
                },
                'windows_app_bar': {
                    'type': 'boolean',
                    'default': BAR_DEFAULTS['window_flags']['windows_app_bar']
                },
                'hide_on_fullscreen': {
                    'type': 'boolean',
                    'default': BAR_DEFAULTS['window_flags']['hide_on_fullscreen']
                }
            },
            'default': BAR_DEFAULTS['window_flags']
        },
        'dimensions': {
            'type': 'dict',
            'schema': {
                'width': {
                    'anyof': [
                        {'type': 'string', 'minlength': 2, 'maxlength': 4, 'regex': '\\d+%'},
                        {'type': 'integer', 'min': 0}
                    ],
                    'default': BAR_DEFAULTS['dimensions']['width']
                },
                'height': {
                    'type': 'integer',
                    'min': 0,
                    'default': BAR_DEFAULTS['dimensions']['height']
                }
            },
            'default': BAR_DEFAULTS['dimensions']
        },
        'padding': {
            'type': 'dict',
            'schema': {
                'top': {
                    'type': 'integer',
                    'default': BAR_DEFAULTS['padding']['top']
                },
                'left': {
                    'type': 'integer',
                    'default': BAR_DEFAULTS['padding']['left']
                },
                'bottom': {
                    'type': 'integer',
                    'default': BAR_DEFAULTS['padding']['bottom']
                },
                'right': {
                    'type': 'integer',
                    'default': BAR_DEFAULTS['padding']['right']
                }
            },
            'default': BAR_DEFAULTS['padding']
        },
        'widgets': {
            'type': 'dict',
            'schema': {
                'left': {
                    'type': 'list',
                    'schema': {
                        'type': 'string'
                    },
                    'default': BAR_DEFAULTS['widgets']['left']
                },
                'center': {
                    'type': 'list',
                    'schema': {
                        'type': 'string'
                    },
                    'default': BAR_DEFAULTS['widgets']['center']
                },
                'right': {
                    'type': 'list',
                    'schema': {
                        'type': 'string'
                    },
                    'default': BAR_DEFAULTS['widgets']['right']
                }
            },
            'default': BAR_DEFAULTS['widgets']
        }
    },
    'default': BAR_DEFAULTS
}
