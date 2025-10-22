"""
Used to tokenize a string with placeholders and separators.
Can filter out separators that are not enclosed by placeholders.
"""

import re
from dataclasses import dataclass
from typing import Literal

TOKEN_PATTERN = re.compile(r"(\{[^{}]*\}|[^{]+)")


@dataclass
class Token:
    type: Literal["literal", "placeholder", "separator"]
    placeholder: str
    value: str


def tokenize(s: str, values: dict[str, str]) -> list[Token]:
    """Tokenize a string into a list of tokens."""
    tokens: list[Token] = []
    matches: list[str] = TOKEN_PATTERN.findall(s)
    for match in matches:
        if match == "{s}":
            tokens.append(Token("separator", match, values.get(match[1:-1], "")))
        elif match.startswith("{") and match.endswith("}"):
            tokens.append(Token("placeholder", match, values.get(match[1:-1], "")))
        else:
            tokens.append(Token("literal", match, values.get(match[1:-1], "")))
    return tokens


def filter_separators(tokens: list[Token]) -> list[Token]:
    """
    Keep a separator only if there is at least one placeholder before
    and at least one placeholder after it in the token list.
    """
    result: list[Token] = []
    placeholder_positions = [i for i, t in enumerate(tokens) if t.type == "placeholder"]

    for i, tok in enumerate(tokens):
        if tok.type == "separator":
            has_left = any(pos < i for pos in placeholder_positions)
            has_right = any(pos > i for pos in placeholder_positions)
            if has_left and has_right:
                result.append(tok)
        else:
            result.append(tok)
    return result


def drop_empty_placeholders(tokens: list[Token]) -> list[Token]:
    """Drop placeholders with empty value"""
    result: list[Token] = []
    for tok in tokens:
        if tok.type == "placeholder":
            if tok.value:
                result.append(tok)
        else:
            result.append(tok)
    return result


def clean_string(content: str, values: dict[str, str]) -> str:
    """Clean a string by tokenizing, filtering, and dropping empty placeholders."""
    t_content = tokenize(content, values)
    s_content = drop_empty_placeholders(t_content)
    f_content = filter_separators(s_content)
    return "".join(t.placeholder for t in f_content)
