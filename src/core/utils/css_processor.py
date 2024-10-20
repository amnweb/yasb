import logging
import os
import re

class CSSProcessor:
    """
    CSSProcessor is a class designed to process CSS files, handling imports and variable replacements.
    """
    def __init__(self, css_path: str):
        self.css_path = css_path
        self.base_path = os.path.dirname(css_path)
        self.css_content = self.read_css_file(css_path)
        self.imported_files = []

    def read_css_file(self, file_path: str) -> str:
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except (FileNotFoundError, OSError) as e:
            logging.error(f"CSSProcessor Error '{file_path}': {e}")
        return ''
    
    def remove_comments(self):
        self.css_content = re.sub(r'/\*.*?\*/|//.*', '', self.css_content, flags=re.DOTALL)
        
    def process_imports(self):
        import_patterns = [
            re.compile(r'@import\s+url\(([^)]+)\);'),
            re.compile(r'@import\s+"([^"]+)";')
        ]
        while True:
            initial_content = self.css_content
            for import_pattern in import_patterns:
                matches = import_pattern.findall(self.css_content)
                for match in matches:
                    import_path = match.strip('\'"')
                    full_import_path = os.path.normpath(os.path.join(self.base_path, import_path))
                    imported_css = self.read_css_file(full_import_path)
                    if imported_css:
                        self.css_content = self.css_content.replace(f'@import url({match});', imported_css)
                        self.css_content = self.css_content.replace(f'@import "{match}";', imported_css)
                        self.imported_files.append(full_import_path)
                    else:
                        self.css_content = self.css_content.replace(f'@import url({match});', '')
                        self.css_content = self.css_content.replace(f'@import "{match}";', '')
            if self.css_content == initial_content:
                self.remove_comments()
                break

    def process_variables(self):
        root_vars = {}
        root_matches = re.findall(r':root\s*{([^}]*)}', self.css_content)
        for root_content in root_matches:
            var_matches = re.findall(r'--([^:]+):\s*([^;]+);', root_content)
            root_vars.update({f'--{name.strip()}': value.strip() for name, value in var_matches})
        
        self.css_content = re.sub(r':root\s*{[^}]*}', '', self.css_content)
        for var_name, var_value in root_vars.items():
            self.css_content = self.css_content.replace(f'var({var_name})', var_value)
        self.remove_comments()

    def process(self) -> str:
        if not self.css_content:
            return ''
        self.process_imports()
        self.process_variables()
        return self.css_content