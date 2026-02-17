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


def fuzzy_score(query: str, target: str) -> int | None:
    """Score how well *query* matches *target*."""
    if not query or not target:
        return 0 if not query else None

    q = query.lower()
    t = target.lower()

    # Initials match (highest priority)
    initials = _get_initials(target)
    if initials.startswith(q):
        # More of the initials covered -> higher score
        score = 200 + len(q) * 10
        # Bonus for exact initials match
        if q == initials:
            score += 20
        return score

    # Prefix match (query starts the target or a word in the target)
    if t.startswith(q):
        return 200 + len(q) * 5

    # Check if query is a prefix of any word in the target
    for word in t.split():
        if word.startswith(q):
            return 150 + len(q) * 5

    # Substring match (query found anywhere inside target)
    idx = t.find(q)
    if idx != -1:
        return 100 + len(q) * 5

    # Subsequence match (characters appear in order, e.g. "np" in "Notepad")
    qi = 0
    for ch in t:
        if qi < len(q) and ch == q[qi]:
            qi += 1
    if qi == len(q):
        return 50

    return None
