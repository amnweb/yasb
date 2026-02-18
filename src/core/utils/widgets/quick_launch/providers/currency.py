import json
import logging
import os
import re
import time
from xml.etree import ElementTree

from PyQt6.QtWidgets import QApplication

from core.utils.utilities import app_data_path
from core.utils.widgets.quick_launch.base_provider import BaseProvider, ProviderResult
from core.utils.widgets.quick_launch.providers.resources.icons import ICON_CURRENCY

_ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
_ECB_NS = {
    "gesmes": "http://www.gesmes.org/xml/2002-08-01",
    "ecb": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref",
}
_CACHE_FILE = str(app_data_path("currency_rates.json"))
_CACHE_MAX_AGE = 12 * 3600  # 12 hours

# Common currencies shown when only source currency is typed
_COMMON_TARGETS = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "CNY")

_CURRENCY_SYMBOLS: dict[str, str] = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
    "CNY": "¥",
    "CHF": "CHF",
    "CAD": "C$",
    "AUD": "A$",
    "KRW": "₩",
    "INR": "₹",
    "BRL": "R$",
    "TRY": "₺",
    "PLN": "zł",
    "SEK": "kr",
    "NOK": "kr",
    "DKK": "kr",
    "CZK": "Kč",
    "HUF": "Ft",
    "RUB": "₽",
    "THB": "฿",
    "MXN": "Mex$",
    "ZAR": "R",
    "SGD": "S$",
    "HKD": "HK$",
    "NZD": "NZ$",
}

# Input pattern: amount, source currency, optional target currency
_QUERY_RE = re.compile(
    r"^([\d.,]+)?\s*([a-zA-Z]{3})\s+(?:to\s+)?([a-zA-Z]{3})$",
)
# Single currency pattern for showing rate overview
_SINGLE_RE = re.compile(r"^([\d.,]+)?\s*([a-zA-Z]{3})$")


class CurrencyProvider(BaseProvider):
    """Convert between currencies using ECB daily rates (cached 12h)."""

    name = "currency"
    display_name = "Currency Converter"
    input_placeholder = "Convert currency, e.g. 100 usd eur..."
    icon = ICON_CURRENCY

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self._rates: dict[str, float] | None = None  # rates relative to EUR
        self._rates_timestamp: float = 0
        self._fetch_attempted = False

    def match(self, text: str) -> bool:
        if self.prefix:
            return text.strip().startswith(self.prefix)
        return True

    def get_results(self, text: str, **kwargs) -> list[ProviderResult]:
        query = self.get_query_text(text).strip()
        if not query:
            return [
                ProviderResult(
                    title="Type currency conversion",
                    description="e.g. 100 usd eur, 50 gbp jpy, usd eur",
                    icon_char=ICON_CURRENCY,
                    provider=self.name,
                )
            ]

        rates = self._get_rates()
        if rates is None:
            return [
                ProviderResult(
                    title="Currency rates unavailable",
                    description="No internet connection and no cached rates",
                    icon_char=ICON_CURRENCY,
                    provider=self.name,
                )
            ]

        # Try full conversion: [amount] SRC DST
        m = _QUERY_RE.match(query)
        if m:
            amount_str, src, dst = m.group(1), m.group(2).upper(), m.group(3).upper()
            amount = self._parse_amount(amount_str) if amount_str else 1.0
            return self._convert(rates, amount, src, dst)

        # Try single currency: [amount] SRC -> show common targets
        m = _SINGLE_RE.match(query)
        if m:
            amount_str, src = m.group(1), m.group(2).upper()
            amount = self._parse_amount(amount_str) if amount_str else 1.0
            if src in rates or src == "EUR":
                return self._show_overview(rates, amount, src)

        # Try partial match - suggest currencies
        upper_query = query.upper().split()
        if len(upper_query) == 1 and len(upper_query[0]) <= 3:
            partial = upper_query[0]
            matches = [c for c in sorted(rates.keys()) if c.startswith(partial)]
            if "EUR".startswith(partial):
                matches.insert(0, "EUR")
            if matches:
                results = []
                for code in matches[:10]:
                    sym = _CURRENCY_SYMBOLS.get(code, code)
                    results.append(
                        ProviderResult(
                            title=f"{code}",
                            description=f"{sym} · Type amount and target e.g. 100 {code.lower()} usd",
                            icon_char=ICON_CURRENCY,
                            provider=self.name,
                        )
                    )
                return results

        return [
            ProviderResult(
                title="Invalid format",
                description="Use: [amount] SRC DST  e.g. 100 usd eur",
                icon_char=ICON_CURRENCY,
                provider=self.name,
            )
        ]

    def execute(self, result: ProviderResult) -> bool:
        value = result.action_data.get("copy_value", "")
        if value:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(value)
        return False  # Keep popup open

    def _convert(self, rates: dict, amount: float, src: str, dst: str) -> list[ProviderResult]:
        src_rate = self._get_rate(rates, src)
        dst_rate = self._get_rate(rates, dst)
        if src_rate is None:
            return [
                ProviderResult(
                    title=f"Unknown currency: {src}",
                    description="Check currency code",
                    icon_char=ICON_CURRENCY,
                    provider=self.name,
                )
            ]
        if dst_rate is None:
            return [
                ProviderResult(
                    title=f"Unknown currency: {dst}",
                    description="Check currency code",
                    icon_char=ICON_CURRENCY,
                    provider=self.name,
                )
            ]

        converted = amount * (dst_rate / src_rate)
        rate = dst_rate / src_rate
        dst_sym = _CURRENCY_SYMBOLS.get(dst, dst)

        # Format the converted value
        if converted >= 1000:
            display = f"{converted:,.2f}"
        elif converted >= 1:
            display = f"{converted:.4f}".rstrip("0").rstrip(".")
        else:
            display = f"{converted:.6f}".rstrip("0").rstrip(".")

        # Format amount
        if amount == int(amount):
            amt_display = f"{int(amount):,}"
        else:
            amt_display = f"{amount:,.2f}"

        return [
            ProviderResult(
                title=f"{dst_sym}{display} {dst}",
                description=f"{amt_display} {src} → {dst} · Rate: {rate:.6f}".rstrip("0").rstrip("."),
                icon_char=ICON_CURRENCY,
                provider=self.name,
                action_data={"copy_value": display},
            )
        ]

    def _show_overview(self, rates: dict, amount: float, src: str) -> list[ProviderResult]:
        targets = [c for c in _COMMON_TARGETS if c != src]
        results = []
        src_rate = self._get_rate(rates, src)
        if src_rate is None:
            return []

        if amount == int(amount):
            amt_display = f"{int(amount):,}"
        else:
            amt_display = f"{amount:,.2f}"

        for dst in targets:
            dst_rate = self._get_rate(rates, dst)
            if dst_rate is None:
                continue
            converted = amount * (dst_rate / src_rate)
            dst_sym = _CURRENCY_SYMBOLS.get(dst, dst)

            if converted >= 1000:
                display = f"{converted:,.2f}"
            elif converted >= 1:
                display = f"{converted:.4f}".rstrip("0").rstrip(".")
            else:
                display = f"{converted:.6f}".rstrip("0").rstrip(".")

            results.append(
                ProviderResult(
                    title=f"{dst_sym}{display} {dst}",
                    description=f"{amt_display} {src} → {dst}",
                    icon_char=ICON_CURRENCY,
                    provider=self.name,
                    action_data={"copy_value": display},
                )
            )
        return results

    def _get_rate(self, rates: dict, code: str) -> float | None:
        if code == "EUR":
            return 1.0
        return rates.get(code)

    def _parse_amount(self, s: str) -> float:
        s = s.replace(",", "")
        try:
            return float(s)
        except ValueError:
            return 1.0

    def _get_rates(self) -> dict[str, float] | None:
        # Return in-memory cache if fresh
        if self._rates and (time.time() - self._rates_timestamp) < _CACHE_MAX_AGE:
            return self._rates

        # Try loading from disk cache
        rates, ts = self._load_cache()
        if rates and (time.time() - ts) < _CACHE_MAX_AGE:
            self._rates = rates
            self._rates_timestamp = ts
            return self._rates

        # Fetch fresh rates (only attempt once per session to avoid repeated slow calls)
        if not self._fetch_attempted:
            self._fetch_attempted = True
            fresh = self._fetch_rates()
            if fresh:
                self._rates = fresh
                self._rates_timestamp = time.time()
                self._save_cache(fresh)
                return self._rates

        # Fall back to stale disk cache if available
        if rates:
            self._rates = rates
            self._rates_timestamp = ts
            return self._rates

        return None

    def _fetch_rates(self) -> dict[str, float] | None:
        try:
            import urllib.request

            req = urllib.request.Request(_ECB_URL, headers={"User-Agent": "yasb/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
                xml_data = resp.read()

            root = ElementTree.fromstring(xml_data)  # noqa: S314
            cube = root.find(".//ecb:Cube/ecb:Cube", _ECB_NS)
            if cube is None:
                return None

            rates: dict[str, float] = {}
            for child in cube:
                currency = child.get("currency")
                rate = child.get("rate")
                if currency and rate:
                    rates[currency] = float(rate)

            return rates if rates else None
        except Exception as e:
            logging.debug(f"Failed to fetch ECB rates: {e}")
            return None

    def _load_cache(self) -> tuple[dict[str, float] | None, float]:
        try:
            if not os.path.isfile(_CACHE_FILE):
                return None, 0
            with open(_CACHE_FILE, encoding="utf-8") as f:
                data = json.load(f)
            return data.get("rates"), data.get("timestamp", 0)
        except Exception:
            return None, 0

    def _save_cache(self, rates: dict[str, float]):
        try:
            with open(_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump({"rates": rates, "timestamp": time.time()}, f)
        except Exception as e:
            logging.debug(f"Failed to save currency cache: {e}")
