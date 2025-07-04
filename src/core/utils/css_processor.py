import logging
import os
import re
from typing import Dict, Set

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFontDatabase, QIcon
from PyQt6.QtWidgets import QCheckBox, QMessageBox

from core.utils.utilities import app_data_path
from settings import DEBUG, SCRIPT_PATH


class CSSProcessor:
    """
    Processes CSS files: handles @import, CSS variables, and removes comments.
    """

    SKIP_FONT_CHECK = app_data_path("skip_font_check")
    _localdata_initialized = False

    def __init__(self, css_path: str):
        self.css_path = css_path
        self.base_path = os.path.dirname(css_path)
        self.imported_files: Set[str] = set()
        self.css_content = self._read_css_file(css_path)

    def process(self) -> str:
        """
        Processes the CSS file: handles imports, variables, removes comments and checks for missing fonts.
        """
        if not self.css_content:
            return ""
        # Remove comments from the CSS content
        css = self._remove_comments(self.css_content)
        # Process @import statements and CSS variables
        css = self._process_imports(css)
        # Remove comments again after processing imports
        css = self._remove_comments(css)
        # Extract and replace CSS variables
        css = self._extract_and_replace_variables(css)
        # Check for missing fonts and warn the user
        self._check_font_families(css)
        return css

    def _read_css_file(self, file_path: str) -> str:
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                return file.read()
        except (FileNotFoundError, OSError) as e:
            logging.error(f"CSSProcessor Error '{file_path}': {e}")
        return ""

    def _remove_comments(self, css: str) -> str:
        # Remove /* ... */ and // ... comments
        css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
        css = re.sub(r"//.*", "", css)
        return css

    def _process_imports(self, css: str) -> str:
        # Handle @import url("..."); and @import "...";
        import_pattern = re.compile(r'@import\s+(?:url\((["\']?)([^)]+?)\1\)|(["\'])(.+?)\3)\s*;', re.IGNORECASE)

        def import_replacer(match):
            path = match.group(2) or match.group(4)
            import_path = path.strip("'\"")
            full_import_path = os.path.normpath(os.path.join(self.base_path, import_path))
            if full_import_path in self.imported_files:
                logging.warning(f"Circular import detected: {full_import_path}")
                return ""
            self.imported_files.add(full_import_path)
            imported_css = self._read_css_file(full_import_path)
            if imported_css:
                return self._process_imports(imported_css)
            return ""

        return import_pattern.sub(import_replacer, css)

    def _extract_and_replace_variables(self, css: str) -> str:
        # Extract variables from :root
        root_vars: Dict[str, str] = {}

        def root_replacer(match):
            content = match.group(1)
            for var_match in re.finditer(r"--([\w-]+)\s*:\s*([^;]+);", content):
                var_name = f"--{var_match.group(1).strip()}"
                var_value = var_match.group(2).strip()
                root_vars[var_name] = var_value
            return ""  # Remove :root block

        css = re.sub(r":root\s*{([^}]*)}", root_replacer, css, flags=re.DOTALL)

        # Replace var(--name) with value
        def var_replacer(match):
            var_name = match.group(1).strip()
            return root_vars.get(var_name, match.group(0))

        css = re.sub(r"var\((--[\w-]+)\)", var_replacer, css)

        css = self._css_to_qt_hex_alpha(css)

        return css

    def _css_to_qt_hex_alpha(self, css: str) -> str:
        """
        Converts CSS hex colors with alpha (#RRGGBBAA) to Qt format (#AARRGGBB).
        """

        def hex_alpha_replacer(match):
            hex_color = match.group(1)
            if len(hex_color) == 8:
                rr = hex_color[0:2]
                gg = hex_color[2:4]
                bb = hex_color[4:6]
                aa = hex_color[6:8]
                return f"#{aa}{rr}{gg}{bb}"
            return match.group(0)

        # Match hex colors with # followed by exactly 8 hex digits
        return re.sub(r"#([0-9a-fA-F]{8})\b", hex_alpha_replacer, css)

    def _check_font_families(self, css: str):
        """
        Checks for missing font families in the CSS and optionally warns the user.
        Uses case-insensitive comparison for font names.
        """
        if not self._should_check_fonts():
            return set(), {}

        # Generic font families that should be ignored in the check
        generic_families = {
            "sans-serif",
            "serif",
            "monospace",
            "cursive",
            "fantasy",
            "system-ui",
            "ui-serif",
            "ui-sans-serif",
            "ui-monospace",
            "ui-rounded",
            "emoji",
            "math",
            "fangsong",
            "initial",
            "inherit",
            "default",
        }

        # Check for available fonts (converted to lowercase for case-insensitive comparison)
        available_fonts = {font.lower() for font in QFontDatabase.families()}

        font_families = set()
        font_status = {}

        matches = re.findall(r"font-family\s*:\s*([^;}\n]+)\s*[;}]+", css, flags=re.IGNORECASE)
        for match in matches:
            fonts = [f.strip(" '\"\t\r\n") for f in match.split(",")]
            for font in fonts:
                if font:
                    font_families.add(font)
                    font_status[font] = font.lower() in generic_families or font.lower() in available_fonts

        missing_fonts = [font for font, installed in font_status.items() if not installed]
        if missing_fonts:
            details = [
                f'<a href="https://www.nerdfonts.com/font-downloads">{font}</a>'
                if ("nerd font" in font.lower() or font.lower().endswith(" nf") or font.lower().endswith(" nfp"))
                else font
                for font in missing_fonts
            ]
            if self._show_font_warning(details):
                self._set_skip_font_check()
        if DEBUG:
            logging.debug(f"Missing fonts: {missing_fonts}")
        return font_families, font_status

    def _set_skip_font_check(self):
        try:
            self.SKIP_FONT_CHECK.touch(exist_ok=True)
        except OSError as e:
            logging.error(f"Error writing skip_font_check.flag: {e}")
        except Exception as e:
            logging.error(f"Unexpected error writing skip_font_check.flag: {e}")

    def _should_check_fonts(self) -> bool:
        return not self.SKIP_FONT_CHECK.exists()

    def _show_font_warning(self, details: list) -> bool:
        """
        Show a warning message box with the missing fonts and an option to not show it again.
        """
        msg_box = QMessageBox()
        msg_box.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        icon_path = os.path.join(SCRIPT_PATH, "assets", "images", "app_icon.png")
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowIcon(QIcon(icon_path))
        msg_box.setWindowTitle("Missing font(s) detected in CSS")
        msg_box.setText(
            "Some fonts specified in your stylesheet are not installed on your system, "
            "some icons or symbols may not be visible or may not display correctly."
        )
        msg_box.setInformativeText(
            "Please install the missing fonts.<br>" + "<br>".join(f"<strong>{font}</strong>" for font in details)
        )
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.setTextFormat(Qt.TextFormat.RichText)

        checkbox = QCheckBox("Don't show this warning again")
        msg_box.setCheckBox(checkbox)

        msg_box.exec()
        return checkbox.isChecked()
