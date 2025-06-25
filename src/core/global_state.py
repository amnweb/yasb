"""
Global state management for the application.
This module provides functions to manage the global state of the application
"""

bar_screens = set()


def set_bar_screens(screens):
    """Set the screens where the bar should be displayed."""
    global bar_screens
    bar_screens = set(screens)


def get_bar_screens():
    """Get the screens where the bar should be displayed."""
    return bar_screens
