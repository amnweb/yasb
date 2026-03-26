import json
import logging
import re
import time
import webbrowser

from PyQt6.QtWidgets import QApplication

from core.utils.widgets.quick_launch.base_provider import BaseProvider, ProviderResult
from core.utils.widgets.quick_launch.providers.resources.icons import ICON_CURRENCY

_CACHE_MAX_AGE = 30  # seconds


class CryptoProvider(BaseProvider):
    """Show live crypto prices from Binance."""

    name = "crypto"
    display_name = "Crypto"
    input_placeholder = "Search crypto prices..."
    icon = ICON_CURRENCY

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self._pairs: list[str] = [p.upper() for p in self.config.get("pairs", ["BTC/USDT"])]
        self._round: int = self.config.get("round", 2)
        self._prices: dict[str, float] = {}
        self._cache_timestamp: float = 0
        self._fetch_attempted: bool = False
        self._is_fetching: bool = False
        self._error_msg: str | None = None
        self._open_url: bool = self.config.get("open_url", False)
        self._domain: str = self.config.get("domain", "api-gcp.binance.com")

    def match(self, text: str) -> bool:
        if self.prefix:
            return text.strip().startswith(self.prefix)
        return True

    def get_results(self, text: str, **kwargs) -> list[ProviderResult]:
        query = self.get_query_text(text).strip().upper()

        prices = self._get_prices()
        if prices is None:
            if self._is_fetching:
                return [
                    ProviderResult(
                        title="Loading crypto prices...",
                        description="Fetching latest data from Binance",
                        icon_char=ICON_CURRENCY,
                        provider=self.name,
                        is_loading=True,
                    )
                ]
            else:
                desc = "Could not fetch prices from Binance"
                if self._error_msg:
                    desc = f"API Error: {self._error_msg}"
                return [
                    ProviderResult(
                        title="Crypto prices unavailable",
                        description=desc,
                        icon_char=ICON_CURRENCY,
                        provider=self.name,
                    )
                ]

        quantity, symbol = self._parse_query(query)

        dyn_pair = None
        pair_match = re.match(r"^([A-Z0-9]+)(?:\s+TO\s+|\s*/\s*|\s+)([A-Z0-9]+)$", symbol.strip())
        if pair_match:
            dyn_pair = f"{pair_match.group(1)}/{pair_match.group(2)}"

        pairs_to_check = list(self._pairs)
        if dyn_pair and dyn_pair not in pairs_to_check:
            pairs_to_check.insert(0, dyn_pair)

        results: list[ProviderResult] = []
        for pair in pairs_to_check:
            if "/" not in pair:
                continue
            base = pair.split("/")[0]
            quote = pair.split("/")[1]

            if dyn_pair:
                if pair != dyn_pair:
                    continue
            elif symbol and symbol not in base:
                continue

            price = prices.get(pair.replace("/", ""), 0)

            if price == 0 and pair == dyn_pair and pair not in self._pairs:
                continue

            total = quantity * price

            if total > 0 and total < 0.01:
                display = f"{total:,.6f}"
            elif total > 0 and total < 1.0:
                display = f"{total:,.4f}"
            else:
                display = f"{total:,.{self._round}f}"

            title = f"{quantity} {base} = {display} {quote}"
            results.append(
                ProviderResult(
                    title=title,
                    description=f"{'Open Binance' if self._open_url else 'Copy'}",
                    icon_char=ICON_CURRENCY,
                    provider=self.name,
                    action_data={
                        "pair": pair,
                        "base": base,
                        "value": display,
                        "title": title,
                    },
                )
            )

        if not results:
            return [
                ProviderResult(
                    title="No matching pairs",
                    description=f"No results for '{symbol}' in configured pairs",
                    icon_char=ICON_CURRENCY,
                    provider=self.name,
                )
            ]
        return results

    def execute(self, result: ProviderResult) -> bool:
        pair = result.action_data.get("pair", "")
        base = result.action_data.get("base", "")
        title = result.action_data.get("title", "")
        if not base:
            return False

        if self._open_url:
            trade_pair = pair.replace("/", "_") if "/" in pair else f"{base}_USDT"
            url = f"https://www.binance.com/en/trade/{trade_pair}"
            webbrowser.open(url)

        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(title)
        return True

    def _parse_query(self, query: str):
        query = query.lower().strip().replace(",", "")
        quantity = 1.0
        match = re.match(r"^(\d+(?:\.\d+)?)([kmbt]?)", query)

        if match:
            num = float(match.group(1))
            suffix = match.group(2)

            if suffix == "k":
                num *= 1_000
            elif suffix == "m":
                num *= 1_000_000
            elif suffix == "b":
                num *= 1_000_000_000
            elif suffix == "t":
                num *= 1_000_000_000_000
            else:
                num = int(num) if num == int(num) else num

            quantity = num
            query = query[match.end() :].strip()

        symbol = query
        return quantity, symbol.upper()

    def _get_prices(self) -> dict[str, float] | None:
        if self._prices and (time.time() - self._cache_timestamp) < _CACHE_MAX_AGE:
            return self._prices

        if not self._is_fetching and (
            not self._fetch_attempted or (time.time() - self._cache_timestamp) >= _CACHE_MAX_AGE
        ):
            self._fetch_attempted = True
            self._is_fetching = True

            def fetch_and_notify():
                try:
                    fresh = self._fetch_prices()
                    if fresh:
                        self._prices = fresh
                finally:
                    self._cache_timestamp = time.time()
                    self._is_fetching = False

                if self.request_refresh:
                    try:
                        self.request_refresh()
                    except Exception as e:
                        logging.debug("Failed to request refresh: %s", e)

            import threading

            threading.Thread(target=fetch_and_notify, daemon=True).start()

        return self._prices or None

    def _fetch_prices(self) -> dict[str, float] | None:
        try:
            import urllib.request

            url = f"https://{self._domain}/api/v3/ticker/price"
            logging.debug("Fetching all prices from %s", url)
            req = urllib.request.Request(url, headers={"User-Agent": "yasb/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
                data = json.loads(resp.read())

            prices: dict[str, float] = {}
            for entry in data:
                symbol = entry.get("symbol", "")
                price = entry.get("price")
                if symbol and price:
                    prices[symbol] = float(price)
            self._error_msg = None
            return prices if prices else None
        except Exception as e:
            self._error_msg = str(e)
            if hasattr(e, "read"):
                try:
                    error_data = json.loads(e.read())
                    if isinstance(error_data, dict) and "msg" in error_data:
                        self._error_msg = error_data["msg"]
                except Exception:
                    pass
            logging.debug("Failed to fetch Binance prices: %s", e)
            return None
