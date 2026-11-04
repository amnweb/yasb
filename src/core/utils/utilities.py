from PyQt6.QtWidgets import (
    QWidget,
)

from core.utils.qobject import is_valid_qobject


def refresh_widget_style(*widgets: QWidget | None) -> None:
    """Refresh the style of the given widgets."""
    for widget in widgets:
        if widget is None or not is_valid_qobject(widget):
            continue
        style = widget.style()
        if not style:
            continue
        try:
            style.unpolish(widget)
            style.polish(widget)
        except Exception:
            pass
