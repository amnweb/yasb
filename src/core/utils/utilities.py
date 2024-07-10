from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QScreen


# General Utility Methods


def percent_to_float(percent: str) -> float:
    return float(percent.strip('%')) / 100.0


def is_valid_percentage_str(s: str) -> bool:
    return s.endswith("%") and len(s) <= 4 and s[:-1].isdigit()


def get_screen_by_name(screen_name: str) -> QScreen:
    return next(filter(lambda scr: screen_name in scr.name(), QApplication.screens()), None)
