"""Country + timezone reference data for the editor dropdowns.

Countries come from the ``iso3166`` package (ISO-3166-1 name <-> alpha-2 code;
the code drives ``auto`` method resolution) and timezones from the standard
library (``zoneinfo.available_timezones()``). Nothing here is hand-maintained.
"""

from __future__ import annotations

import zoneinfo

import iso3166

_COUNTRIES: list[tuple[str, str]] = sorted(((c.name, c.alpha2) for c in iso3166.countries), key=lambda x: x[0])
_NAME_TO_CODE = {name: code for name, code in _COUNTRIES}
_CODE_TO_NAME = {code: name for name, code in _COUNTRIES}


def country_names() -> list[str]:
    return [name for name, _ in _COUNTRIES]


def code_to_name(code: str) -> str:
    return _CODE_TO_NAME.get((code or "").upper(), "")


def name_to_code(text: str) -> str:
    """Map a country name (or a raw 2-letter code) to an ISO-3166 alpha-2 code."""
    text = (text or "").strip()
    if not text:
        return ""
    if text in _NAME_TO_CODE:
        return _NAME_TO_CODE[text]
    if len(text) == 2 and text.upper() in _CODE_TO_NAME:
        return text.upper()
    return ""


def timezones() -> list[str]:
    """All IANA timezone identifiers, sorted (from the stdlib tz database)."""
    return sorted(zoneinfo.available_timezones())
