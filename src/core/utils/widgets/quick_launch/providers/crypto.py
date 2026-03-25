import json
import logging
import time
import webbrowser

from PyQt6.QtWidgets import QApplication

from core.utils.widgets.quick_launch.base_provider import BaseProvider, ProviderResult
from core.utils.widgets.quick_launch.providers.resources.icons import ICON_CURRENCY

_CACHE_MAX_AGE = 30  # seconds

_CMC_SLUGS: dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "BNB": "bnb",
    "SOL": "solana",
    "XRP": "xrp",
    "ADA": "cardano",
    "DOGE": "dogecoin",
    "DOT": "polkadot-new",
    "AVAX": "avalanche",
    "MATIC": "polygon",
    "LINK": "chainlink",
    "SHIB": "shiba-inu",
    "LTC": "litecoin",
    "UNI": "uniswap",
    "ATOM": "cosmos",
    "TRX": "tron",
    "NEAR": "near-protocol",
    "APT": "aptos",
    "ARB": "arbitrum",
    "OP": "optimism-ethereum",
    "SUI": "sui",
    "FIL": "filecoin",
    "PEPE": "pepe",
    "USDT": "tether",
    "USDC": "usd-coin",
}


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

        results: list[ProviderResult] = []
        for pair in self._pairs:
            base = pair.split("/")[0]
            quote = pair.split("/")[1]
            if query and query not in pair and query not in base and query not in quote:
                continue

            price = prices.get(pair.replace("/", ""), 0)
            display = f"{price:,.{self._round}f}"
            results.append(
                ProviderResult(
                    title=f"1 {base} = {display} {quote}",
                    description=f"{'Open CoinMarketCap' if self._open_url else 'Copy'}",
                    icon_char=ICON_CURRENCY,
                    provider=self.name,
                    action_data={"pair": pair, "base": base, "value": display},
                )
            )

        if not results:
            return [
                ProviderResult(
                    title="No matching pairs",
                    description=f"No results for '{query}' in configured pairs",
                    icon_char=ICON_CURRENCY,
                    provider=self.name,
                )
            ]
        return results

    def execute(self, result: ProviderResult) -> bool:
        base = result.action_data.get("base", "")
        value = result.action_data.get("value", "")
        if not base:
            return False
        slug = _CMC_SLUGS.get(base, base.lower())
        url = f"https://coinmarketcap.com/currencies/{slug}/"
        if self._open_url:
            webbrowser.open(url)
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(f"{base} {value}")
        return True

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
                        logging.debug(f"Failed to request refresh: {e}")

            import threading

            threading.Thread(target=fetch_and_notify, daemon=True).start()

        return self._prices or None

    def _fetch_prices(self) -> dict[str, float] | None:
        try:
            import urllib.request

            symbols_json = json.dumps(self._pairs).replace("/", "").replace(" ", "")
            url = f"https://{self._domain}/api/v3/ticker/price?symbols={symbols_json}"
            logging.debug(f"Fetching Binance prices from {url}")
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
            logging.debug(f"Failed to fetch Binance prices: {e}")
            return None
