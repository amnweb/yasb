"""
Syntax highlighting module for code blocks in AI chat.
Provides simple regex-based syntax highlighting with inline color styles.
"""

import re

from core.utils.widgets.ai_chat.constants import MAX_HIGHLIGHTED_CODE_LENGTH

# COLORS - All syntax highlighting colors in one place
SYNTAX_COLORS = {
    # General colors (used by most languages)
    "keyword": "#ff79c6",  # pink - keywords, reserved words
    "string": "#f1fa8c",  # yellow - string literals
    "number": "#bd93f9",  # purple - numbers, constants
    "comment": "#6272a4",  # gray - comments
    "function": "#50fa7b",  # green - function names
    "property": "#66d9ef",  # cyan - properties, attributes
    # CSS specific
    "selector": "#50fa7b",  # green - CSS class/id selectors
    "value": "#f1fa8c",  # yellow - CSS values
    # YAML specific
    "yaml_key": "#7ee787",  # green - YAML keys
    "yaml_value": "#a5d6ff",  # light blue - YAML values
}

# LANGUAGE CONFIGURATION, Language aliases for detection (maps alias -> canonical name)
LANG_ALIASES = {
    # JavaScript variants
    "js": "javascript",
    "ts": "javascript",
    "typescript": "javascript",
    "jsx": "javascript",
    "tsx": "javascript",
    # Python
    "py": "python",
    "python3": "python",
    # C/C++
    "c++": "cpp",
    "cxx": "cpp",
    "cc": "cpp",
    "h": "c",
    "hpp": "cpp",
    # C#
    "cs": "csharp",
    "c#": "csharp",
    # Other languages
    "golang": "go",
    "rs": "rust",
    "rb": "ruby",
    # PHP
    "php3": "php",
    "php4": "php",
    "php5": "php",
    "php7": "php",
    "php8": "php",
    "phtml": "php",
    # Shell
    "sh": "bash",
    "shell": "bash",
    "zsh": "bash",
    "powershell": "bash",
    "ps1": "bash",
    "bat": "bash",
    "cmd": "bash",
    "makefile": "bash",
    "make": "bash",
    # Data formats
    "yml": "yaml",
    "jsonc": "json",
    # SQL variants
    "mysql": "sql",
    "postgresql": "sql",
    "sqlite": "sql",
    "plsql": "sql",
    "tsql": "sql",
    # Java-like
    "kt": "java",
    "kts": "java",
    "kotlin": "java",
    # C-like
    "objc": "c",
    "m": "c",
}

# Comment styles per language
HASH_COMMENT_LANGS = {"python", "ruby", "bash", "yaml", "powershell", "toml"}
SLASH_COMMENT_LANGS = {"javascript", "c", "cpp", "java", "csharp", "go", "rust", "php"}

# KEYWORDS PER LANGUAGE
KEYWORDS = {
    "python": [
        "def",
        "class",
        "import",
        "from",
        "return",
        "if",
        "elif",
        "else",
        "for",
        "while",
        "try",
        "except",
        "finally",
        "with",
        "as",
        "lambda",
        "yield",
        "raise",
        "pass",
        "break",
        "continue",
        "and",
        "or",
        "not",
        "in",
        "is",
        "None",
        "True",
        "False",
        "async",
        "await",
        "self",
        "global",
        "nonlocal",
        "assert",
        "del",
    ],
    "javascript": [
        "function",
        "const",
        "let",
        "var",
        "return",
        "if",
        "else",
        "for",
        "while",
        "try",
        "catch",
        "finally",
        "throw",
        "new",
        "class",
        "extends",
        "import",
        "export",
        "default",
        "async",
        "await",
        "this",
        "true",
        "false",
        "null",
        "undefined",
        "typeof",
        "instanceof",
        "switch",
        "case",
        "break",
        "continue",
        "of",
        "in",
        "delete",
        "void",
        "yield",
        "static",
        "get",
        "set",
        "super",
    ],
    "c": [
        "auto",
        "break",
        "case",
        "char",
        "const",
        "continue",
        "default",
        "do",
        "double",
        "else",
        "enum",
        "extern",
        "float",
        "for",
        "goto",
        "if",
        "int",
        "long",
        "register",
        "return",
        "short",
        "signed",
        "sizeof",
        "static",
        "struct",
        "switch",
        "typedef",
        "union",
        "unsigned",
        "void",
        "volatile",
        "while",
        "NULL",
        "true",
        "false",
        "bool",
        "inline",
        "restrict",
        "uint8_t",
        "uint16_t",
        "uint32_t",
        "int8_t",
        "int16_t",
        "int32_t",
    ],
    "cpp": [
        "auto",
        "break",
        "case",
        "char",
        "const",
        "continue",
        "default",
        "do",
        "double",
        "else",
        "enum",
        "extern",
        "float",
        "for",
        "goto",
        "if",
        "int",
        "long",
        "register",
        "return",
        "short",
        "signed",
        "sizeof",
        "static",
        "struct",
        "switch",
        "typedef",
        "union",
        "unsigned",
        "void",
        "volatile",
        "while",
        "NULL",
        "true",
        "false",
        "class",
        "public",
        "private",
        "protected",
        "virtual",
        "override",
        "final",
        "new",
        "delete",
        "this",
        "throw",
        "try",
        "catch",
        "namespace",
        "using",
        "template",
        "typename",
        "nullptr",
        "constexpr",
        "noexcept",
        "decltype",
    ],
    "java": [
        "abstract",
        "assert",
        "boolean",
        "break",
        "byte",
        "case",
        "catch",
        "char",
        "class",
        "const",
        "continue",
        "default",
        "do",
        "double",
        "else",
        "enum",
        "extends",
        "final",
        "finally",
        "float",
        "for",
        "if",
        "implements",
        "import",
        "instanceof",
        "int",
        "interface",
        "long",
        "native",
        "new",
        "null",
        "package",
        "private",
        "protected",
        "public",
        "return",
        "short",
        "static",
        "strictfp",
        "super",
        "switch",
        "synchronized",
        "this",
        "throw",
        "throws",
        "transient",
        "true",
        "false",
        "try",
        "void",
        "volatile",
        "while",
        "var",
        "record",
        "sealed",
    ],
    "csharp": [
        "abstract",
        "as",
        "base",
        "bool",
        "break",
        "byte",
        "case",
        "catch",
        "char",
        "checked",
        "class",
        "const",
        "continue",
        "decimal",
        "default",
        "delegate",
        "do",
        "double",
        "else",
        "enum",
        "event",
        "explicit",
        "extern",
        "false",
        "finally",
        "fixed",
        "float",
        "for",
        "foreach",
        "goto",
        "if",
        "implicit",
        "in",
        "int",
        "interface",
        "internal",
        "is",
        "lock",
        "long",
        "namespace",
        "new",
        "null",
        "object",
        "operator",
        "out",
        "override",
        "params",
        "private",
        "protected",
        "public",
        "readonly",
        "ref",
        "return",
        "sbyte",
        "sealed",
        "short",
        "sizeof",
        "static",
        "string",
        "struct",
        "switch",
        "this",
        "throw",
        "true",
        "try",
        "typeof",
        "uint",
        "ulong",
        "unchecked",
        "unsafe",
        "ushort",
        "using",
        "var",
        "virtual",
        "void",
        "volatile",
        "while",
        "async",
        "await",
    ],
    "go": [
        "break",
        "case",
        "chan",
        "const",
        "continue",
        "default",
        "defer",
        "else",
        "fallthrough",
        "for",
        "func",
        "go",
        "goto",
        "if",
        "import",
        "interface",
        "map",
        "package",
        "range",
        "return",
        "select",
        "struct",
        "switch",
        "type",
        "var",
        "true",
        "false",
        "nil",
        "int",
        "int8",
        "int16",
        "int32",
        "int64",
        "uint",
        "uint8",
        "uint16",
        "uint32",
        "uint64",
        "float32",
        "float64",
        "complex64",
        "complex128",
        "bool",
        "byte",
        "rune",
        "string",
        "error",
    ],
    "rust": [
        "as",
        "break",
        "const",
        "continue",
        "crate",
        "else",
        "enum",
        "extern",
        "false",
        "fn",
        "for",
        "if",
        "impl",
        "in",
        "let",
        "loop",
        "match",
        "mod",
        "move",
        "mut",
        "pub",
        "ref",
        "return",
        "self",
        "Self",
        "static",
        "struct",
        "super",
        "trait",
        "true",
        "type",
        "unsafe",
        "use",
        "where",
        "while",
        "async",
        "await",
        "dyn",
        "i8",
        "i16",
        "i32",
        "i64",
        "i128",
        "isize",
        "u8",
        "u16",
        "u32",
        "u64",
        "u128",
        "usize",
        "f32",
        "f64",
        "bool",
        "char",
        "str",
        "String",
        "Vec",
        "Option",
        "Result",
        "Some",
        "None",
        "Ok",
        "Err",
    ],
    "php": [
        "function",
        "class",
        "public",
        "private",
        "protected",
        "return",
        "if",
        "else",
        "elseif",
        "foreach",
        "for",
        "while",
        "try",
        "catch",
        "throw",
        "new",
        "echo",
        "print",
        "require",
        "include",
        "use",
        "namespace",
        "true",
        "false",
        "null",
        "static",
        "final",
        "abstract",
        "extends",
        "implements",
        "interface",
        "trait",
        "array",
        "string",
        "int",
        "float",
        "bool",
        "void",
        "match",
        "fn",
        "isset",
        "empty",
        "die",
        "exit",
        "global",
        "const",
        "var",
        "self",
        "parent",
    ],
    "ruby": [
        "def",
        "class",
        "module",
        "end",
        "if",
        "elsif",
        "else",
        "unless",
        "case",
        "when",
        "while",
        "until",
        "for",
        "do",
        "begin",
        "rescue",
        "ensure",
        "raise",
        "return",
        "yield",
        "break",
        "next",
        "redo",
        "retry",
        "self",
        "super",
        "nil",
        "true",
        "false",
        "and",
        "or",
        "not",
        "in",
        "then",
        "alias",
        "defined?",
        "lambda",
        "proc",
        "attr",
        "attr_reader",
        "attr_writer",
        "attr_accessor",
        "private",
        "protected",
        "public",
        "require",
        "include",
        "extend",
        "new",
    ],
    "sql": [
        "SELECT",
        "FROM",
        "WHERE",
        "INSERT",
        "INTO",
        "VALUES",
        "UPDATE",
        "SET",
        "DELETE",
        "CREATE",
        "TABLE",
        "DROP",
        "ALTER",
        "INDEX",
        "VIEW",
        "JOIN",
        "LEFT",
        "RIGHT",
        "INNER",
        "OUTER",
        "ON",
        "AND",
        "OR",
        "NOT",
        "NULL",
        "IS",
        "IN",
        "LIKE",
        "BETWEEN",
        "EXISTS",
        "CASE",
        "WHEN",
        "THEN",
        "ELSE",
        "END",
        "AS",
        "ORDER",
        "BY",
        "GROUP",
        "HAVING",
        "LIMIT",
        "OFFSET",
        "UNION",
        "ALL",
        "DISTINCT",
        "COUNT",
        "SUM",
        "AVG",
        "MIN",
        "MAX",
        "PRIMARY",
        "KEY",
        "FOREIGN",
        "REFERENCES",
        "CONSTRAINT",
        "DEFAULT",
        "UNIQUE",
        "CHECK",
        "INT",
        "VARCHAR",
        "TEXT",
        "BOOLEAN",
        "DATE",
        "TIMESTAMP",
        "FLOAT",
        "DECIMAL",
    ],
    "bash": [
        "if",
        "then",
        "else",
        "elif",
        "fi",
        "case",
        "esac",
        "for",
        "while",
        "until",
        "do",
        "done",
        "in",
        "function",
        "return",
        "exit",
        "break",
        "continue",
        "local",
        "export",
        "readonly",
        "declare",
        "unset",
        "shift",
        "source",
        "echo",
        "printf",
        "read",
        "cd",
        "pwd",
        "ls",
        "cp",
        "mv",
        "rm",
        "mkdir",
        "cat",
        "grep",
        "sed",
        "awk",
        "find",
        "xargs",
        "test",
        "true",
        "false",
    ],
    "yaml": ["true", "false", "null", "yes", "no", "on", "off"],
    "json": ["true", "false", "null"],
    "toml": ["true", "false"],
}


_CSS_PATTERN = re.compile(
    r"(/\*[\s\S]*?\*/)"  # /* */ comments
    r'|("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')'  # strings
    r"|(@[\w-]+)"  # at-rules
    r"|(#[a-fA-F0-9]{3,8}\b)"  # hex colors
    r"|((?:\.|#)[\w-]+)"  # class/id selectors
    r"|(:[\w-]+)"  # pseudo selectors
    r"|([\w-]+)\s*(?=\()"  # function names
    r"|([\w-]+)\s*:"  # property names
    r"|(\b\d+\.?\d*(?:px|em|rem|%|vh|vw|vmin|vmax|deg|s|ms|fr|ch|ex)?\b)"  # numbers
)


_HTML_PATTERN = re.compile(
    r"(<!--[\s\S]*?--(?:>|!>))"  # HTML comments (support --> and --!>)
    r"|(<!\w+[^>]*>)"  # DOCTYPE
    r"|(</?)([\w-]+)"  # tags
    r"|([\w-]+)\s*="  # attribute names
    r'|("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')'  # strings
)


_YAML_PATTERN = re.compile(
    r"(#[^\n]*)"  # comments
    r"|([\w][\w\s.-]*)(:)",  # keys with colon
    re.MULTILINE,
)


def _escape_html(s):
    """Escape HTML special characters."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _highlight_css(code):
    """CSS syntax highlighting."""
    if len(code) > MAX_HIGHLIGHTED_CODE_LENGTH:
        return _escape_html(code)

    result = []
    last_end = 0

    for match in _CSS_PATTERN.finditer(code):
        before = code[last_end : match.start()]
        result.append(_escape_html(before))

        if match.group(1):  # comment
            result.append(f'<span style="color:{SYNTAX_COLORS["comment"]};">{_escape_html(match.group(1))}</span>')
        elif match.group(2):  # string
            result.append(f'<span style="color:{SYNTAX_COLORS["string"]};">{_escape_html(match.group(2))}</span>')
        elif match.group(3):  # at-rule
            result.append(f'<span style="color:{SYNTAX_COLORS["keyword"]};">{_escape_html(match.group(3))}</span>')
        elif match.group(4):  # hex color
            result.append(f'<span style="color:{SYNTAX_COLORS["number"]};">{match.group(4)}</span>')
        elif match.group(5):  # selector
            result.append(f'<span style="color:{SYNTAX_COLORS["selector"]};">{_escape_html(match.group(5))}</span>')
        elif match.group(6):  # pseudo
            result.append(f'<span style="color:{SYNTAX_COLORS["keyword"]};">{_escape_html(match.group(6))}</span>')
        elif match.group(7):  # function
            result.append(f'<span style="color:{SYNTAX_COLORS["function"]};">{_escape_html(match.group(7))}</span>')
        elif match.group(8):  # property
            result.append(f'<span style="color:{SYNTAX_COLORS["property"]};">{_escape_html(match.group(8))}</span>:')
        elif match.group(9):  # number
            result.append(f'<span style="color:{SYNTAX_COLORS["number"]};">{match.group(9)}</span>')

        last_end = match.end()

    result.append(_escape_html(code[last_end:]))
    return "".join(result)


def _highlight_html(code):
    """HTML/XML syntax highlighting."""
    if len(code) > MAX_HIGHLIGHTED_CODE_LENGTH:
        return _escape_html(code)

    result = []
    last_end = 0

    for match in _HTML_PATTERN.finditer(code):
        before = code[last_end : match.start()]
        result.append(_escape_html(before))

        if match.group(1):  # comment
            result.append(f'<span style="color:{SYNTAX_COLORS["comment"]};">{_escape_html(match.group(1))}</span>')
        elif match.group(2):  # DOCTYPE
            result.append(f'<span style="color:{SYNTAX_COLORS["comment"]};">{_escape_html(match.group(2))}</span>')
        elif match.group(3) and match.group(4):  # tag
            bracket = _escape_html(match.group(3))
            tag_name = match.group(4)
            result.append(f'{bracket}<span style="color:{SYNTAX_COLORS["keyword"]};">{tag_name}</span>')
        elif match.group(5):  # attribute
            result.append(f'<span style="color:{SYNTAX_COLORS["property"]};">{_escape_html(match.group(5))}</span>=')
        elif match.group(6):  # string
            result.append(f'<span style="color:{SYNTAX_COLORS["string"]};">{_escape_html(match.group(6))}</span>')

        last_end = match.end()

    result.append(_escape_html(code[last_end:]))
    return "".join(result)


def _highlight_yaml(code):
    """YAML syntax highlighting - simple two-color approach."""
    if len(code) > MAX_HIGHLIGHTED_CODE_LENGTH:
        return _escape_html(code)

    result = []
    last_end = 0

    for match in _YAML_PATTERN.finditer(code):
        before = code[last_end : match.start()]
        if before:
            result.append(f'<span style="color:{SYNTAX_COLORS["yaml_value"]};">{_escape_html(before)}</span>')

        if match.group(1):  # comment
            result.append(f'<span style="color:{SYNTAX_COLORS["comment"]};">{_escape_html(match.group(1))}</span>')
        elif match.group(2) and match.group(3):  # key:
            result.append(
                f'<span style="color:{SYNTAX_COLORS["yaml_key"]};">{_escape_html(match.group(2))}{match.group(3)}</span>'
            )

        last_end = match.end()

    remaining = code[last_end:]
    if remaining:
        result.append(f'<span style="color:{SYNTAX_COLORS["yaml_value"]};">{_escape_html(remaining)}</span>')
    return "".join(result)


def _highlight_generic(code, lang):
    """Generic syntax highlighting for programming languages."""
    if len(code) > MAX_HIGHLIGHTED_CODE_LENGTH:
        return _escape_html(code)

    # Get keywords for this language
    keywords = KEYWORDS.get(lang, [])
    if not keywords:
        return _escape_html(code)

    case_insensitive = lang == "sql"

    # Build keyword pattern
    if case_insensitive:
        kw_pattern = re.compile(r"\b(" + "|".join(re.escape(k) for k in keywords) + r")\b", re.IGNORECASE)
    else:
        kw_pattern = r"\b(" + "|".join(re.escape(k) for k in keywords) + r")\b"

    # Build comment patterns
    comment_patterns = []
    if lang in HASH_COMMENT_LANGS:
        comment_patterns.append(r"#[^\n]*")
    if lang in SLASH_COMMENT_LANGS or not lang:
        comment_patterns.append(r"//[^\n]*")
        comment_patterns.append(r"/\*[\s\S]*?\*/")

    # Build token pattern
    patterns = [
        r'("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|`(?:[^`\\]|\\.)*`)',  # strings
    ]
    if comment_patterns:
        patterns.append("(" + "|".join(comment_patterns) + ")")
    else:
        patterns.append("((?!))")  # empty placeholder
    patterns.append(r"(\b\d+\.?\d*(?:e[+-]?\d+)?\b)")  # numbers
    patterns.append(r"([a-zA-Z_]\w*)\s*(?=\()")  # functions

    token_pattern = re.compile("|".join(patterns))

    def highlight_keywords(text):
        if not text:
            return text
        escaped = _escape_html(text)
        if case_insensitive:
            return kw_pattern.sub(f'<span style="color:{SYNTAX_COLORS["keyword"]};">\\1</span>', escaped)
        return re.sub(kw_pattern, f'<span style="color:{SYNTAX_COLORS["keyword"]};">\\1</span>', escaped)

    result = []
    last_end = 0

    for match in token_pattern.finditer(code):
        before = code[last_end : match.start()]
        result.append(highlight_keywords(before))

        if match.group(1):  # string
            result.append(f'<span style="color:{SYNTAX_COLORS["string"]};">{_escape_html(match.group(1))}</span>')
        elif match.group(2):  # comment
            result.append(f'<span style="color:{SYNTAX_COLORS["comment"]};">{_escape_html(match.group(2))}</span>')
        elif match.group(3):  # number
            result.append(f'<span style="color:{SYNTAX_COLORS["number"]};">{match.group(3)}</span>')
        elif match.group(4):  # function
            result.append(f'<span style="color:{SYNTAX_COLORS["function"]};">{match.group(4)}</span>')

        last_end = match.end()

    result.append(highlight_keywords(code[last_end:]))
    return "".join(result)


def simple_syntax_highlight(code, lang=""):
    """
    Apply syntax highlighting to code.

    Args:
        code: The source code to highlight (not HTML-escaped)
        lang: Language identifier (e.g., 'python', 'javascript', 'yaml')

    Returns:
        HTML string with inline color styles
    """
    if len(code) > MAX_HIGHLIGHTED_CODE_LENGTH:
        return _escape_html(code)

    lang = lang.lower().strip()
    lang = LANG_ALIASES.get(lang, lang)

    # No language specified - just escape HTML
    if not lang:
        return _escape_html(code)

    # Route to specialized highlighters
    if lang in ("css", "scss", "sass", "less"):
        return _highlight_css(code)

    if lang in ("html", "htm", "xml", "xhtml", "svg", "vue", "svelte"):
        return _highlight_html(code)

    if lang in ("yaml", "yml"):
        return _highlight_yaml(code)

    # Only use generic highlighter if language has defined keywords
    if lang in KEYWORDS:
        return _highlight_generic(code, lang)

    # Unknown language - just escape HTML, no highlighting
    return _escape_html(code)
