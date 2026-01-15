"""
Centralized update service for checking, downloading, and managing YASB updates.

This module provides a unified interface for handling application updates across
both the automatic background update checker and the GUI update dialog. It supports
architecture-specific updates (x64 and ARM64) and ensures version consistency.
"""

import json
import logging
import platform
import re
import ssl
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

import certifi

from core.utils.utilities import ToastNotifier, app_data_path, get_app_identifier, get_architecture
from settings import APP_ID, BUILD_VERSION, RELEASE_CHANNEL, SCRIPT_PATH

# GitHub API configuration
GITHUB_API_URL = "https://api.github.com/repos/amnweb/yasb/releases/latest"
GITHUB_API_DEV_URL = "https://api.github.com/repos/amnweb/yasb/releases/tags/dev"
GITHUB_FALLBACK_URL = "https://api.yasb.dev/github-meta.json"
USER_AGENT_HEADER = {"User-Agent": "YASB Updater"}
CHECK_INTERVAL = 60 * 60  # 60 minutes
LAST_CHECK_FILE = app_data_path("last_update_check")
ARCHITECTURE = get_architecture()

# Module-level singletons
_update_service_instance: Optional["UpdateService"] = None
_update_checker_started = False


def _get_msi_arch_suffix() -> str:
    """Get the architecture suffix used in MSI filenames.

    Returns:
        Architecture suffix for MSI filename (x64 → x64, ARM64 → aarch64)
    """
    return "aarch64" if ARCHITECTURE == "ARM64" else ARCHITECTURE if ARCHITECTURE else ""


@dataclass(slots=True)
class ReleaseInfo:
    """Information about a GitHub release."""

    version: str
    changelog: str
    download_url: str
    asset_name: str
    asset_size: Optional[int]
    architecture: str


class UpdateService:
    """Centralized service for handling application updates.

    This singleton service provides:
    - Version comparison
    - Update checking against GitHub releases
    - Architecture-specific MSI asset selection
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the update service."""
        if self._initialized:
            return
        self._initialized = True
        self._current_version = BUILD_VERSION
        self._current_channel = self._get_current_channel()

    @property
    def current_version(self) -> str:
        """Get the current application version."""
        return self._current_version

    def _get_current_channel(self) -> str:
        """Detect the current release channel from RELEASE_CHANNEL.

        Returns:
            'dev' if running dev build, 'stable' otherwise
        """
        return "dev" if RELEASE_CHANNEL.startswith("dev-") else "stable"

    def _get_current_commit_hash(self) -> str:
        """Extract commit hash from dev RELEASE_CHANNEL.

        Returns:
            Commit hash if dev channel, empty string otherwise
        """
        if self._current_channel == "dev" and "-" in RELEASE_CHANNEL:
            return RELEASE_CHANNEL.split("-", 1)[1]
        return ""

    @staticmethod
    def _extract_commit_from_release_name(release_name: str) -> str:
        """Extract commit hash from dev release name.

        Args:
            release_name: Release name like "YASB Pre-release (abc1234)"

        Returns:
            Commit hash from parentheses, or empty string if not found
        """
        match = re.search(r"\(([a-f0-9]+)\)", release_name)
        return match.group(1) if match else ""

    @staticmethod
    def _normalize_version_segments(version: str) -> list[int]:
        """Extract numeric segments from version string.

        Args:
            version: Version string (e.g., "1.8.3" or "v1.8.3")

        Returns:
            List of integer segments
        """
        segments = [int(part) for part in re.findall(r"\d+", version)]
        return segments if segments else [0]

    def is_newer_version(self, latest: str, current: Optional[str] = None) -> bool:
        """Compare version strings to determine if an update is available.

        Args:
            latest: Latest version string
            current: Current version string (defaults to BUILD_VERSION)

        Returns:
            True if latest is newer than current
        """
        if current is None:
            current = self._current_version

        latest_segments = self._normalize_version_segments(latest)
        current_segments = self._normalize_version_segments(current)

        # Pad to same length
        max_length = max(len(latest_segments), len(current_segments))
        latest_segments.extend([0] * (max_length - len(latest_segments)))
        current_segments.extend([0] * (max_length - len(current_segments)))

        return latest_segments > current_segments

    def _select_asset_for_architecture(self, assets: list[dict], channel: str = "stable") -> Optional[dict]:
        """Select the appropriate MSI asset for the current architecture.

        Args:
            assets: List of release assets from GitHub API
            channel: Release channel ('stable' or 'dev')

        Returns:
            The matching asset dict, or None if not found
        """
        if not ARCHITECTURE:
            logging.warning("Cannot select asset: architecture not detected")
            return None

        arch_suffix = _get_msi_arch_suffix()

        # Asset naming patterns:
        # Stable: yasb-{version}-{arch}.msi (e.g., yasb-1.8.4-x64.msi)
        # Dev: yasb-dev-{arch}.msi (e.g., yasb-dev-x64.msi)
        if channel == "dev":
            pattern = f"yasb-dev-{arch_suffix}.msi"
        else:
            # Match any stable version pattern with architecture
            pattern = f"-{arch_suffix}.msi"

        for asset in assets:
            name = asset.get("name", "").lower()
            if channel == "dev":
                if name == pattern:
                    return asset
            else:
                if name.endswith(pattern) and not name.startswith("yasb-dev-"):
                    return asset

        logging.error(f"No suitable MSI asset found for {channel} channel, architecture: {ARCHITECTURE}")
        return None

    def _fetch_release_data(self, check_channel: str, timeout: int) -> dict:
        """Fetch release data from GitHub API with fallback to metadata endpoint."""
        context = ssl.create_default_context(cafile=certifi.where())
        api_url = GITHUB_API_DEV_URL if check_channel == "dev" else GITHUB_API_URL

        try:
            request = urllib.request.Request(api_url, headers=USER_AGENT_HEADER)
            with urllib.request.urlopen(request, context=context, timeout=timeout) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as e:
            if e.code not in (403, 429) and e.headers.get("X-RateLimit-Remaining") != "0":
                raise
        except urllib.error.URLError:
            pass

        # Fallback to metadata endpoint
        request = urllib.request.Request(GITHUB_FALLBACK_URL, headers=USER_AGENT_HEADER)
        with urllib.request.urlopen(request, context=context, timeout=timeout) as response:
            meta = json.loads(response.read())
        key = "nightly_release" if check_channel == "dev" else "stable_release"
        if key not in meta:
            raise ValueError(f"Fallback metadata missing {key}")
        return meta[key]

    def check_for_updates(
        self,
        timeout: int = 15,
        channel: Optional[str] = None,
        skip_version_check: bool = False,
    ) -> Optional[ReleaseInfo]:
        """Check GitHub for available updates.

        Supports both stable and dev channels:
        - Stable: Compares semantic versions
        - Dev: Compares commit hashes

        Args:
            timeout: Request timeout in seconds
            channel: Release channel to check ('stable' or 'dev'). If None, uses current channel
            skip_version_check: If True, returns release info without checking if it's newer

        Returns:
            ReleaseInfo if update is available (or skip_version_check=True), None otherwise

        Raises:
            urllib.error.URLError: Network errors
            ValueError: Invalid release data
        """
        check_channel = channel or self._current_channel

        try:
            release_data = self._fetch_release_data(check_channel, timeout)

            # Select appropriate asset for architecture
            assets = release_data.get("assets", [])
            msi_asset = self._select_asset_for_architecture(assets, channel=check_channel)

            if not msi_asset:
                raise ValueError(f"No MSI installer found for {ARCHITECTURE} architecture")

            # Get version display based on channel
            if check_channel == "dev":
                release_name = release_data.get("name", "")
                commit_hash = self._extract_commit_from_release_name(release_name)
                version = f"dev-{commit_hash}"

                # Check if it's actually an update for dev channel
                if not skip_version_check:
                    current_commit = self._get_current_commit_hash()
                    if commit_hash and commit_hash == current_commit:
                        logging.debug(f"Already on latest dev build: {current_commit}")
                        return None
            else:
                version = release_data.get("tag_name", "").lstrip("vV")
                if not version:
                    raise ValueError("Release tag is missing")

                # Check if it's actually an update for stable channel
                if not skip_version_check and not self.is_newer_version(version):
                    return None

            release_info = ReleaseInfo(
                version=version,
                changelog=release_data.get("body", ""),
                download_url=msi_asset.get("browser_download_url"),
                asset_name=msi_asset.get("name", ""),
                asset_size=msi_asset.get("size"),
                architecture=ARCHITECTURE,
            )

            return release_info

        except urllib.error.HTTPError as e:
            logging.error(f"GitHub API HTTP error: {e.code} {e.reason}")
            raise
        except urllib.error.URLError as e:
            logging.warning(f"Network error checking for updates: {e.reason}")
            raise
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse GitHub API response: {e}")
            raise ValueError("Invalid JSON response from GitHub API")
        except Exception as e:
            logging.error(f"Unexpected error checking for updates: {e}")
            raise

    def should_check_for_updates(self) -> bool:
        """Determine if enough time has passed since last update check.

        Returns:
            True if check should be performed
        """
        try:
            if LAST_CHECK_FILE.exists():
                last_check = float(LAST_CHECK_FILE.read_text().strip())
                elapsed = time.time() - last_check

                if elapsed < CHECK_INTERVAL:
                    return False
        except Exception as e:
            logging.debug(f"Could not read last check time: {e}")

        return True

    def update_last_check_time(self) -> None:
        """Record the current time as the last update check time."""
        try:
            LAST_CHECK_FILE.write_text(str(time.time()))
        except Exception as e:
            logging.warning(f"Failed to update last check time: {e}")

    def get_version_info(self) -> dict:
        """Get comprehensive version and architecture information.

        Returns:
            Dictionary with version, architecture, and system info
        """
        return {
            "version": self._current_version,
            "architecture": ARCHITECTURE,
            "platform": platform.platform(),
            "machine": platform.machine(),
        }

    def is_update_supported(self) -> bool:
        """Check if updates are supported on this system.

        Updates are supported when:
        1. App is frozen (running as bundled executable)
        2. YASB is installed (not running from source)
        3. Architecture is known (x64 or ARM64)
        4. Updates are disabled for PR build channels.

        Updates are disabled for PR build channels.

        Returns:
            True if updates are supported, False otherwise
        """

        is_forzen = getattr(sys, "frozen", False)
        is_installed = get_app_identifier() == APP_ID
        is_arch_supported = ARCHITECTURE is not None
        is_pr_build = RELEASE_CHANNEL.startswith("pr-")

        return is_installed and is_arch_supported and is_forzen and (not is_pr_build)


def get_update_service() -> UpdateService:
    """Get the singleton UpdateService instance.

    Returns:
        UpdateService instance
    """
    global _update_service_instance
    if _update_service_instance is None:
        _update_service_instance = UpdateService()
    return _update_service_instance


def start_update_checker() -> None:
    """Start the background update checker service.

    This function starts a daemon thread that periodically checks for updates
    and displays toast notifications when new versions are available.
    Uses a singleton pattern to ensure only one checker runs at a time.
    """
    global _update_checker_started

    if _update_checker_started:
        return

    _update_checker_started = True

    def _check_for_update() -> None:
        """Check for updates and show notification if available."""
        update_service = get_update_service()

        if not update_service.should_check_for_updates():
            return

        try:
            release_info = update_service.check_for_updates(timeout=10)

            if release_info:
                icon_path = f"{SCRIPT_PATH}/assets/images/app_transparent.png"
                toaster = ToastNotifier()

                # Determine launch URL and message based on channel
                update_service = get_update_service()
                if update_service._current_channel == "dev":
                    launch_url = "https://github.com/amnweb/yasb/releases/tag/dev"
                    message = "New dev build is available!"
                else:
                    launch_url = "https://github.com/amnweb/yasb/releases/latest"
                    message = f"New version {release_info.version} is available!"

                toaster.show(
                    icon_path=icon_path,
                    title="Update Available",
                    message=message,
                    launch_url=launch_url,
                    scenario="reminder",
                )
            # Update last check time
            update_service.update_last_check_time()

        except Exception as e:
            logging.warning(f"Background update check failed: {e}")

    # Start background thread
    threading.Thread(target=_check_for_update, daemon=True, name="UpdateChecker").start()
    logging.info("Background update checker started")
