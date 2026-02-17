import re

_CAMEL_RE = re.compile(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def _get_initials(target: str) -> str:
    """Extract initials (word-boundary characters) from *target*."""
    initials: list[str] = []
    for i, ch in enumerate(target):
        if i == 0:
            initials.append(ch.lower())
        elif ch.isupper() and not target[i - 1].isupper():
            initials.append(ch.lower())
        elif target[i - 1] == " " and ch != " ":
            initials.append(ch.lower())
    return "".join(initials)


def _split_camel(name: str) -> str:
    """Split a CamelCase name into space-separated words.

    Examples:
        WindowsTerminal -> Windows Terminal
        WindowsAlarms   -> Windows Alarms
        VLC             -> VLC
    """
    return _CAMEL_RE.sub(" ", name)


def fuzzy_score(query: str, target: str) -> int | None:
    """Score how well *query* matches *target*.

    Returns an integer tier (higher = better match) or None for no match.

    Tiers:
        6  Exact initials match  (query == initials)
        5  Initials starts-with  (initials.startswith(query))
        4  Full prefix           (target starts with query)
        3  Word prefix           (a word in target starts with query)
        2  Substring             (query found inside target)
        1  Subsequence           (characters appear in order)
    """
    if not query or not target:
        return 0 if not query else None

    q = query.lower()
    t = target.lower()

    # Initials match (highest priority)
    initials = _get_initials(target)
    if initials.startswith(q):
        return 6 if q == initials else 5

    # Prefix match
    if t.startswith(q):
        return 4

    # Word prefix match
    for word in t.split():
        if word.startswith(q):
            return 3

    # Substring match
    if q in t:
        return 2

    # Subsequence match (characters appear in order)
    qi = 0
    for ch in t:
        if qi < len(q) and ch == q[qi]:
            qi += 1
    if qi == len(q):
        return 1

    return None
