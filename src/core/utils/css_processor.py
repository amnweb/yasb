import logging
import os
import re
from typing import Dict, Set


class CSSProcessor:
    """
    Processes CSS files: handles @import, CSS variables, and removes comments.
    """

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

        # Resolve variables recursively
        resolved_vars = root_vars.copy()
        max_iterations = 10  # Make sure we never get stuck in a loop.
        for iteration in range(max_iterations):
            changed = False

            for var_name, var_value in resolved_vars.items():

                def var_replacer(match):
                    nonlocal changed
                    nested_var_name = match.group(1).strip()
                    if nested_var_name in resolved_vars:
                        changed = True
                        return resolved_vars[nested_var_name]
                    return match.group(0)

                # Replace var(--name) with their value until it's no longer another variable
                new_value = re.sub(r"var\((--[\w-]+)\)", var_replacer, var_value)
                if new_value != var_value:
                    resolved_vars[var_name] = new_value
                    changed = True
            if not changed:
                break  # No more changes, resolution complete

        def final_var_replacer(match):
            var_name = match.group(1).strip()
            return resolved_vars.get(var_name, match.group(0))

        # Replace final var(--name) with resolved CSS value
        css = re.sub(r"var\((--[\w-]+)\)", final_var_replacer, css)
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
