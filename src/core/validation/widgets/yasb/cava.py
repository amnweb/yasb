DEFAULTS = {
    'bar_height': 20,
    'bars_number': 10,
    'output_bit_format': "16bit",
    'bar_spacing': 1,
    'bar_width': 3,
    'sleep_timer': 0,
    'sensitivity': 100,
    'lower_cutoff_freq': 50,
    'higher_cutoff_freq': 10000,
    'framerate': 60,
    'noise_reduction': 0.77,
    'channels': 'stereo',
    'mono_option': 'average',
    'reverse': 0,
    'foreground': '#ffffff',
    'gradient': 1,
    'gradient_color_1': '#74c7ec',
    'gradient_color_2': '#89b4fa',
    'gradient_color_3': '#cba6f7',
    'hide_empty': False,
    'container_padding': {'top': 0, 'left': 0, 'bottom': 0, 'right': 0},
}

VALIDATION_SCHEMA = {
    'bar_height': {
        'type': 'integer',
        'required': False,
        'default': DEFAULTS['bar_height']
    },
    'bars_number': {
        'type': 'integer',
        'required': False,
        'default': DEFAULTS['bars_number']
    },
    'output_bit_format': {
        'type': 'string',
        'required': False,
        'default': DEFAULTS['output_bit_format']
    },
    'bar_spacing': {
        'type': 'integer',
        'required': False,
        'default': DEFAULTS['bar_spacing']
    },
    'bar_width': {
        'type': 'integer',
        'required': False,
        'default': DEFAULTS['bar_width']
    },
    'sleep_timer': {
        'type': 'integer',
        'required': False,
        'default': DEFAULTS['sleep_timer']
    },
    'sensitivity': {
        'type': 'integer',
        'required': False,
        'default': DEFAULTS['sensitivity']
    },
    'lower_cutoff_freq': {
        'type': 'integer',
        'required': False,
        'default': DEFAULTS['lower_cutoff_freq']
    },
    'higher_cutoff_freq': {
        'type': 'integer',
        'required': False,
        'default': DEFAULTS['higher_cutoff_freq']
    },
    'framerate': {
        'type': 'integer',
        'required': False,
        'default': DEFAULTS['framerate']
    },
    'noise_reduction': {
        'type': 'float',
        'required': False,
        'default': DEFAULTS['noise_reduction']
    },
    'channels': {
        'type': 'string',
        'required': False,
        'default': DEFAULTS['channels']
    },
    'mono_option': {
        'type': 'string',
        'required': False,
        'default': DEFAULTS['mono_option']
    },
    'reverse': {
        'type': 'integer',
        'required': False,
        'default': DEFAULTS['reverse']
    },
    'foreground': {
        'type': 'string',
        'required': False,
        'default': DEFAULTS['foreground']
    },
    'gradient': {
        'type': 'integer',
        'required': False,
        'default': DEFAULTS['gradient']
    },
    'gradient_color_1': {
        'type': 'string',
        'required': False,
        'default': DEFAULTS['gradient_color_1']
    },
    'gradient_color_2': {
        'type': 'string',
        'required': False,
        'default': DEFAULTS['gradient_color_2']
    },
    'gradient_color_3': {
        'type': 'string',
        'required': False,
        'default': DEFAULTS['gradient_color_3']
    },
    'hide_empty': {
        'type': 'boolean',
        'required': False,
        'default': DEFAULTS['hide_empty']
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