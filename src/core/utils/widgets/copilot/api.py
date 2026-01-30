"""
GitHub Copilot API client for fetching premium request usage data.
"""

import json
import logging
import os
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock, Thread
from typing import Any, Callable

API_BASE_URL = "https://api.github.com"
# I have set version of GitHub API to a fixed date to avoid unexpected changes
API_VERSION = "2022-11-28"
DEFAULT_TIMEOUT = 30

# Plan allowances for premium requests per month
PLAN_ALLOWANCES = {
    "pro": 300,
    "pro_plus": 1500,
}


@dataclass
class CopilotUsageData:
    """Aggregated Copilot usage data."""

    total_requests: int = 0
    total_cost: float = 0.0
    allowance: int = 0
    plan_type: str = ""
    username: str = ""
    requests_by_model: dict[str, int] = field(default_factory=dict)
    cost_by_model: dict[str, float] = field(default_factory=dict)
    daily_usage: list[dict[str, Any]] = field(default_factory=list)
    last_updated: datetime | None = None
    error: str | None = None


class CopilotDataManager:
    """
    Singleton manager for GitHub Copilot usage data.
    Handles API requests and caching.
    """

    _instance: "CopilotDataManager | None" = None
    _lock = Lock()
    _initialized = False
    _token: str = ""
    _username: str = ""
    _plan_type: str = "pro"
    _allowance: int = 0
    _update_interval: int = 3600
    _data: CopilotUsageData = CopilotUsageData()
    _callbacks: list[Callable[[CopilotUsageData], None]] = []
    _update_thread: Thread | None = None
    _chart_enabled: bool = True
    _daily_cache: dict[str, int] = {}  # Cache for daily data (date_str -> requests)

    @classmethod
    def get_instance(cls) -> "CopilotDataManager":
        """Get or create the singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def initialize(cls, token: str, plan: str = "pro", update_interval: int = 3600, chart: bool = True) -> None:
        """Initialize the data manager."""
        logging.info("CopilotDataManager started...")
        instance = cls.get_instance()
        with cls._lock:
            cls._token = token if token != "env" else os.getenv("YASB_COPILOT_TOKEN", "")
            cls._plan_type = plan if plan in PLAN_ALLOWANCES else "pro"
            cls._allowance = PLAN_ALLOWANCES[cls._plan_type]
            cls._update_interval = update_interval
            cls._chart_enabled = chart
            cls._initialized = True
        instance._start_update()

    @classmethod
    def register_callback(cls, callback: Callable[[CopilotUsageData], None]) -> None:
        """Register a callback for data updates."""
        if callback not in cls._callbacks:
            cls._callbacks.append(callback)

    @classmethod
    def unregister_callback(cls, callback: Callable[[CopilotUsageData], None]) -> None:
        """Unregister a callback."""
        if callback in cls._callbacks:
            cls._callbacks.remove(callback)

    @classmethod
    def get_data(cls) -> CopilotUsageData:
        """Get the current cached data."""
        return cls._data

    @classmethod
    def refresh(cls) -> None:
        """Manually trigger a data refresh."""
        cls.get_instance()._start_update()

    def _start_update(self) -> None:
        """Start a background thread to update data."""
        if CopilotDataManager._update_thread is not None and CopilotDataManager._update_thread.is_alive():
            return
        CopilotDataManager._update_thread = Thread(target=self._fetch_data, daemon=True)
        CopilotDataManager._update_thread.start()

    def _fetch_data(self) -> None:
        """Fetch data from GitHub API."""
        cls = CopilotDataManager
        if not cls._token:
            cls._data = CopilotUsageData(error="Token not configured")
            self._notify_callbacks()
            return

        try:
            # Get username if not cached
            if not cls._username:
                username, error = self._fetch_authenticated_user()
                if error:
                    cls._data = CopilotUsageData(error=error)
                    self._notify_callbacks()
                    return
                cls._username = username

            # Fetch monthly usage
            now = datetime.now(timezone.utc)
            url = (
                f"{API_BASE_URL}/users/{cls._username}/settings/billing/premium_request/usage"
                f"?year={now.year}&month={now.month}"
            )

            data, status_code, error = self._make_request(url)

            if error:
                cls._data = CopilotUsageData(error=error)
            elif status_code == 200 and data:
                usage_data = self._parse_usage_response(data)

                # Use configured plan type and allowance
                usage_data.plan_type = cls._plan_type
                usage_data.allowance = cls._allowance
                usage_data.username = cls._username

                # Fetch daily data in parallel (only if chart enabled)
                if cls._chart_enabled:
                    usage_data.daily_usage = self._fetch_daily_data_parallel(now)
                usage_data.last_updated = now
                cls._data = usage_data
            elif status_code == 403:
                cls._data = CopilotUsageData(error="Access denied. Token needs Plan permission.")
            elif status_code == 404:
                cls._data = CopilotUsageData(error="Requires Copilot Pro/Pro+ subscription.")
            else:
                cls._data = CopilotUsageData(error=f"API error: {status_code}")

        except Exception:
            logging.exception("Error fetching Copilot data")
            cls._data = CopilotUsageData(error="Unexpected error occurred")

        self._notify_callbacks()

    def _fetch_authenticated_user(self) -> tuple[str | None, str | None]:
        """Fetch username from GitHub API."""
        data, status_code, error = self._make_request(f"{API_BASE_URL}/user")
        if error:
            return None, error
        if status_code == 200 and data:
            return data.get("login"), None
        if status_code == 401:
            return None, "Invalid token"
        return None, f"Failed to get user: {status_code}"

    def _make_request(self, url: str, timeout: int = DEFAULT_TIMEOUT) -> tuple[dict[str, Any] | None, int, str | None]:
        """Make an HTTP GET request."""
        cls = CopilotDataManager
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {cls._token}",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "YASB-Copilot-Widget",
        }
        try:
            request = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data, response.status, None
        except urllib.error.HTTPError as e:
            return None, e.code, None
        except urllib.error.URLError as e:
            error = "Request timed out" if "timed out" in str(e.reason).lower() else f"Connection error: {e.reason}"
            return None, 0, error
        except json.JSONDecodeError:
            return None, 0, "Invalid JSON response"
        except Exception as e:
            return None, 0, str(e)

    def _parse_usage_response(self, data: dict[str, Any]) -> CopilotUsageData:
        """Parse API response into CopilotUsageData."""
        usage_data = CopilotUsageData()

        for item in data.get("usageItems", []):
            if "copilot" not in item.get("product", "").lower():
                continue

            model = item.get("model") or "Unknown"
            quantity = int(item.get("grossQuantity") or item.get("netQuantity") or 0)
            amount = item.get("netAmount", 0.0)

            usage_data.total_requests += quantity
            usage_data.total_cost += amount
            usage_data.requests_by_model[model] = usage_data.requests_by_model.get(model, 0) + quantity
            usage_data.cost_by_model[model] = usage_data.cost_by_model.get(model, 0.0) + amount

        return usage_data

    def _fetch_daily_data_parallel(self, now: datetime) -> list[dict[str, Any]]:
        """Fetch daily usage data, using cache for past days."""
        cls = CopilotDataManager
        year, month, current_day = now.year, now.month, now.day

        # Clear cache if month changed
        cache_month_key = f"{year}-{month:02d}"
        if cls._daily_cache and not any(k.startswith(cache_month_key) for k in cls._daily_cache):
            cls._daily_cache.clear()

        # Determine which days need fetching (today always, past days only if not cached)
        days_to_fetch = []
        for day in range(1, current_day + 1):
            date_str = f"{year}-{month:02d}-{day:02d}"
            if day == current_day or date_str not in cls._daily_cache:
                days_to_fetch.append(day)

        def fetch_day(day: int) -> tuple[str, int]:
            date_str = f"{year}-{month:02d}-{day:02d}"
            url = f"{API_BASE_URL}/users/{cls._username}/settings/billing/premium_request/usage?year={year}&month={month}&day={day}"
            data, status_code, _ = self._make_request(url, timeout=10)
            if status_code == 200 and data:
                total = sum(
                    int(item.get("grossQuantity") or item.get("netQuantity") or 0)
                    for item in data.get("usageItems", [])
                    if "copilot" in item.get("product", "").lower()
                )
                return date_str, total
            return date_str, 0

        # Fetch only needed days in parallel
        if days_to_fetch:
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(fetch_day, day): day for day in days_to_fetch}
                for future in as_completed(futures):
                    date_str, requests = future.result()
                    cls._daily_cache[date_str] = requests

        # Build result from cache
        return [
            {
                "date": f"{year}-{month:02d}-{day:02d}",
                "requests": cls._daily_cache.get(f"{year}-{month:02d}-{day:02d}", 0),
            }
            for day in range(1, current_day + 1)
        ]

    def _notify_callbacks(self) -> None:
        """Notify all registered callbacks."""
        cls = CopilotDataManager
        for callback in cls._callbacks:
            try:
                callback(cls._data)
            except Exception:
                logging.exception("Error in Copilot data callback")
