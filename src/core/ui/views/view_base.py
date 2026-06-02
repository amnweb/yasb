"""Base mixin for top-level views (dialogs, main windows, splash screens)."""

import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from core.ui.theme import get_tokens, is_dark
from core.utils.win32.backdrop import enable_mica, is_mica_supported, set_dark_mode
from settings import SCRIPT_PATH


class ViewBase:
    """Mixin for any top-level QWidget subclass.

    Provides:
      - Mica backdrop setup with base stylesheet
      - Dark title bar on Windows 10 when in dark mode
      - Application icon
    """

    def build_view(self) -> bool:
        """
        Apply Mica backdrop and base stylesheet.
        Returns True if Mica applied, False if unsupported.
        """
        t = get_tokens()
        has_mica = is_mica_supported()
        bg = "transparent" if has_mica else t["solid_bg_base"]
        self.setStyleSheet(f"""
            QDialog, QMainWindow {{
                background-color: {bg};
            }}
            QLabel {{
                color: {t["text_primary"]};
            }}
            QFrame[class="layer"] {{
                background-color: {t["layer_default"]};
                border-radius: 8px;
            }}
            QFrame[class="layer-alt"] {{
                background-color: {t["layer_alt"]};
                border-radius: 8px;
            }}
        """)
        if not has_mica:
            # Apply dark title bar when system is in dark mode
            if is_dark():
                try:
                    set_dark_mode(int(self.winId()))
                except Exception:
                    pass
            return False
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        enable_mica(int(self.winId()))
        return True

    def build_app_icon(self) -> QIcon:
        """Set the shared application icon. Returns the QIcon instance."""
        icon_path = os.path.join(SCRIPT_PATH, "assets", "images", "app_icon.png")
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()
        if not icon.isNull():
            self.setWindowIcon(icon)
        return icon
