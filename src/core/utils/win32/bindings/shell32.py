"""Wrappers for Shell32 win32 API functions to make them easier to use and have proper types.

This module exposes the `shell32` handle and sets argtypes/restype for the Shell
functions we call from Python so ctypes marshaling is explicit and safe.
"""

from ctypes import windll

shell32 = windll.shell32
