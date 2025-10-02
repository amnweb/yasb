"""
Global state management for the application.
This module provides functions to manage the global state of the application
"""

_bar_screens = set()
_autohide_widgets_by_bar_id: dict[str, object] = {}


def set_bar_screens(screens):
    """Set the screens where the bar should be displayed."""
    global _bar_screens
    _bar_screens = set(screens)


def get_bar_screens():
    """Get the screens where the bar should be displayed."""
    return _bar_screens


def set_autohide_owner_for_bar(bar_id: str, widget: object):
    """Register an autohide owner widget for a particular bar id."""
    if bar_id:
        _autohide_widgets_by_bar_id[bar_id] = widget


def get_autohide_owner_for_widget(widget: object):
    """Locate the autohide owner for the provided widget (by bar_id)."""
    if widget is None:
        return None

    bar_id = getattr(widget, "bar_id", None)
    if bar_id:
        return _autohide_widgets_by_bar_id.get(bar_id)
    return None


def get_all_autohide_owners():
    """Return a list of all registered autohide owner widgets."""
    return list(_autohide_widgets_by_bar_id.values())


def unset_autohide_owner_for_bar(bar_id: str):
    """Unregister an autohide widget previously registered under bar_id."""
    if bar_id:
        _autohide_widgets_by_bar_id.pop(bar_id, None)
