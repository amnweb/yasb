# A python wrapper for font_family_util.cpp

import os
import sys
import ctypes
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.WARNING)

is_init_succeeded_flag = False

def init() -> bool:
    global family_util 
    global is_init_succeeded_flag

    script_dir = os.path.dirname(os.path.abspath(__file__))
    dll_name = 'font_family_util.dll'
    dll_path = os.path.join(script_dir, 'Release', dll_name) 

    try:
        family_util = ctypes.CDLL(
                winmode=0 # LOAD_WITH_ALTERED_SEARCH_PATH
                ,name=dll_path # should be an absolute path
                )
    except Exception as e:
        logger.debug(f'Failed to load {dll_name}')
        is_init_succeeded_flag = False
        return False

    if family_util is None:
        logger.debug(f'{dll_name} is not loaded correctly')
        is_init_succeeded_flag = False
        return False

    try:
        family_util.init.restype = ctypes.c_bool
        family_util.get_gdi_family_from_directwrite.restype = ctypes.c_char_p
        family_util.get_directwrite_family_from_gdi.restype = ctypes.c_char_p
    except Exception as e:
        logger.debug(f'An error occured while setting restypes : {e}')
        is_init_succeeded_flag = False
        return False

    ir = family_util.init()

    if not ir:
        logger.debug('family_util.init() returned False')
        is_init_succeeded_flag = False
    else:
        is_init_succeeded_flag = True

    return ir

def is_init_succeeded() -> bool:
    return is_init_succeeded_flag

def get_gdi_family_from_directwrite(direct_write_family : str) -> str | None:
    '''
    direct_write_family should be UTF-8.
    Returns a UTF-8 string of a gdi font family name which corresponds to direct_write_family.
    '''

    direct_write_family_b = direct_write_family.encode('UTF-8')
    gdi_family : bytes | None = family_util.get_gdi_family_from_directwrite(direct_write_family_b)

    if gdi_family is None:
        return None

    return gdi_family.decode('UTF-8')

def get_directwrite_family_from_gdi(gdi_family : str) -> str | None:
    '''
    gdi_family should be UTF-8.
    Returns a UTF-8 string of a directwrite family name which corresponds to gdi_family.
    '''

    gdi_family_b = gdi_family.encode('UTF-8')
    directwrite_family : bytes | None = family_util.get_directwrite_family_from_gdi(gdi_family_b)

    if directwrite_family is None:
        return None

    return directwrite_family.decode('UTF-8')

if __name__ == "__main__":
    init()
    print(get_directwrite_family_from_gdi('JetBrainsMono NFP'))
    print(get_gdi_family_from_directwrite('JetBrainsMono Nerd Font Propo'))
