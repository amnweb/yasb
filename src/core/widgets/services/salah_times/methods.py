"""Method resolution, display labels, calculation parameters and Hijri date.

Keeps the widget-specific logic — pick a method from a location's ISO-3166
country ("auto"), method-name aliases, display labels — and build an adhanpy
CalculationParameters for a method key. Prayer times are computed by adhanpy;
the Hijri date comes from hijridate (Umm al-Qura).
"""

from __future__ import annotations

from datetime import date

from adhanpy.calculation import CalculationMethod
from adhanpy.calculation.CalculationParameters import CalculationParameters
from adhanpy.calculation.Madhab import Madhab
from adhanpy.calculation.PrayerAdjustments import PrayerAdjustments
from hijridate import Gregorian

METHOD_KEYS = [
    "MuslimWorldLeague",
    "Egyptian",
    "Karachi",
    "UmmAlQura",
    "Dubai",
    "MoonsightingCommittee",
    "NorthAmerica",
    "Kuwait",
    "Qatar",
    "Singapore",
    "Tehran",
    "Turkey",
    "Other",
]

METHOD_ALIASES = {
    "isna": "NorthAmerica",
    "northamerica": "NorthAmerica",
    "north_america": "NorthAmerica",
    "mwl": "MuslimWorldLeague",
    "muslimworldleague": "MuslimWorldLeague",
    "muslim_world_league": "MuslimWorldLeague",
    "ummalqura": "UmmAlQura",
    "umm_al_qura": "UmmAlQura",
    "umm_alqura": "UmmAlQura",
    "egyptian": "Egyptian",
    "egypt": "Egyptian",
    "karachi": "Karachi",
    "dubai": "Dubai",
    "kuwait": "Kuwait",
    "qatar": "Qatar",
    "singapore": "Singapore",
    "turkey": "Turkey",
    "moonsighting": "MoonsightingCommittee",
    "moonsightingcommittee": "MoonsightingCommittee",
    "moonsighting_committee": "MoonsightingCommittee",
    "tehran": "Tehran",
    "other": "Other",
}

COUNTRY_METHOD_BY_ISO2 = {
    "SA": "UmmAlQura",
    "AE": "Dubai",
    "BH": "Dubai",
    "OM": "Dubai",
    "KW": "Kuwait",
    "QA": "Qatar",
    "JO": "MuslimWorldLeague",
    "PS": "MuslimWorldLeague",
    "EG": "Egyptian",
    "LY": "Egyptian",
    "SD": "Egyptian",
    "TN": "Egyptian",
    "DZ": "Egyptian",
    "MA": "MuslimWorldLeague",
    "PT": "MuslimWorldLeague",
    "TR": "Turkey",
    "RU": "MuslimWorldLeague",
    "KZ": "MuslimWorldLeague",
    "UZ": "MuslimWorldLeague",
    "KG": "MuslimWorldLeague",
    "TJ": "MuslimWorldLeague",
    "TM": "MuslimWorldLeague",
    "AZ": "MuslimWorldLeague",
    "GE": "MuslimWorldLeague",
    "AM": "MuslimWorldLeague",
    "BY": "MuslimWorldLeague",
    "UA": "MuslimWorldLeague",
    "MY": "Singapore",
    "BN": "Singapore",
    "ID": "Singapore",
    "SG": "Singapore",
    "FR": "MuslimWorldLeague",
    "BE": "MuslimWorldLeague",
    "NL": "MuslimWorldLeague",
    "LU": "MuslimWorldLeague",
    "GB": "MoonsightingCommittee",
    "IE": "MoonsightingCommittee",
    "PK": "Karachi",
    "IN": "Karachi",
    "BD": "Karachi",
    "AF": "Karachi",
    "LK": "Karachi",
    "NP": "Karachi",
    "MV": "Karachi",
    "US": "NorthAmerica",
    "CA": "NorthAmerica",
}

METHOD_LABELS = {
    "Karachi": "Karachi",
    "NorthAmerica": "ISNA",
    "MuslimWorldLeague": "Muslim World League",
    "UmmAlQura": "Umm al-Qura",
    "Egyptian": "Egyptian",
    "Dubai": "Dubai",
    "Kuwait": "Kuwait",
    "Qatar": "Qatar",
    "Singapore": "Singapore",
    "Turkey": "Turkey",
    "MoonsightingCommittee": "Moonsighting Committee",
    "Tehran": "Tehran",
    "Other": "Other",
}

# "auto" plus every method key — used to populate the editor dropdown.
METHOD_OPTIONS = ["auto", *METHOD_KEYS]


# adhanpy ships these as presets; the remaining methods are built from the
# angles/adjustments the original adhan presets used.
_ADHANPY_METHOD = {
    "MuslimWorldLeague": CalculationMethod.MUSLIM_WORLD_LEAGUE,
    "Egyptian": CalculationMethod.EGYPTIAN,
    "Karachi": CalculationMethod.KARACHI,
    "UmmAlQura": CalculationMethod.UMM_AL_QURA,
    "Dubai": CalculationMethod.DUBAI,
    "MoonsightingCommittee": CalculationMethod.MOON_SIGHTING_COMMITTEE,
    "NorthAmerica": CalculationMethod.NORTH_AMERICA,
    "Kuwait": CalculationMethod.KUWAIT,
    "Qatar": CalculationMethod.QATAR,
    "Singapore": CalculationMethod.SINGAPORE,
}


def _custom_parameters(method_key: str) -> CalculationParameters:
    """Parameters for methods adhanpy does not ship as presets."""
    if method_key == "Tehran":
        # adhanpy has no maghrib-angle option, so Tehran's 4.5-degree maghrib
        # is approximated as sunset (a few minutes earlier).
        return CalculationParameters(fajr_angle=17.7, isha_angle=14)
    if method_key == "Turkey":
        return CalculationParameters(
            fajr_angle=18,
            isha_angle=17,
            method_adjustments=PrayerAdjustments(sunrise=-7, dhuhr=5, asr=4, maghrib=7),
        )
    return CalculationParameters(fajr_angle=0, isha_angle=0)  # "Other"


def build_parameters(method_key: str, asr_school: str) -> CalculationParameters:
    """Build adhanpy CalculationParameters for a method key + Asr school."""
    if method_key in _ADHANPY_METHOD:
        params = CalculationParameters(method=_ADHANPY_METHOD[method_key])
    else:
        params = _custom_parameters(method_key)
    params.madhab = Madhab.HANAFI if asr_school == "hanafi" else Madhab.SHAFI
    return params


def parse_method_option(raw: str | None) -> str:
    """Return a canonical method option: ``"auto"`` or a method key."""
    if not raw:
        return "auto"
    normalized = raw.strip()
    if not normalized or normalized.lower() == "auto":
        return "auto"
    for key in METHOD_KEYS:
        if key.lower() == normalized.lower():
            return key
    alias = METHOD_ALIASES.get(normalized.lower())
    if alias:
        return alias
    raise ValueError(f"Invalid method '{raw}'. Valid: auto | {' | '.join(METHOD_KEYS)}")


def resolve_auto_method(country_code: str) -> str:
    cc = (country_code or "").strip().upper()
    if not cc:
        return "MuslimWorldLeague"
    return COUNTRY_METHOD_BY_ISO2.get(cc, "MuslimWorldLeague")


def method_label(method_key: str) -> str:
    return METHOD_LABELS.get(method_key, method_key)


def hijri_date(g: date) -> str:
    """Umm al-Qura Hijri date, e.g. '2 Safar 1448 AH'."""
    h = Gregorian(g.year, g.month, g.day).to_hijri()
    return f"{h.day} {h.month_name()} {h.year} AH"
