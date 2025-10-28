"""Centralized update service for checking, downloading, and managing YASB updates.

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
from enum import Enum
from typing import Optional

import certifi

from core.utils.utilities import ToastNotifier, app_data_path, get_app_identifier
from settings import APP_ID, BUILD_VERSION, SCRIPT_PATH

# GitHub API configuration
GITHUB_API_URL = "https://api.github.com/repos/amnweb/yasb/releases/latest"
USER_AGENT_HEADER = {"User-Agent": "YASB Updater"}

# Update check configuration
CHECK_INTERVAL = 60 * 60  # 60 minutes
LAST_CHECK_FILE = app_data_path("last_update_check")

# Module-level singletons
_update_service_instance: Optional["UpdateService"] = None
_update_checker_started = False


class Architecture(Enum):
    """System architecture types."""

    X64 = "x64"
    ARM64 = "aarch64"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class ReleaseInfo:
    """Information about a GitHub release."""

    version: str
    changelog: str
    download_url: str
    asset_name: str
    asset_size: Optional[int]
    architecture: Architecture


class UpdateService:
    """Centralized service for handling application updates.

    This singleton service provides:
    - Architecture detection (x64 vs ARM64)
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
        self._architecture = self._detect_architecture()

    @staticmethod
    def _detect_architecture() -> Architecture:
        """Detect the system architecture.

        Returns:
            Architecture enum value (X64, ARM64, or UNKNOWN)
        """
        try:
            machine = platform.machine().lower()

            # Check for ARM64
            if machine in ["arm64", "aarch64"]:
                return Architecture.ARM64

            # Check for x64
            if machine in ["amd64", "x86_64", "x64"]:
                return Architecture.X64

            # Fallback: check if running on 64-bit Windows
            if platform.architecture()[0] == "64bit":
                return Architecture.X64

            logging.warning(f"Unknown architecture detected: {machine}")
            return Architecture.UNKNOWN
        except Exception as e:
            logging.error(f"Failed to detect architecture: {e}")
            return Architecture.UNKNOWN

    @property
    def current_version(self) -> str:
        """Get the current application version."""
        return self._current_version

    @property
    def architecture(self) -> Architecture:
        """Get the detected system architecture."""
        return self._architecture

    @property
    def architecture_display(self) -> str:
        """Get a human-readable architecture name."""
        if self._architecture == Architecture.X64:
            return "x64"
        elif self._architecture == Architecture.ARM64:
            return "ARM64"
        return "Unknown"

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

    def _select_asset_for_architecture(self, assets: list[dict]) -> Optional[dict]:
        """Select the appropriate MSI asset for the current architecture.

        Args:
            assets: List of release assets from GitHub API

        Returns:
            The matching asset dict, or None if not found
        """
        if self._architecture == Architecture.UNKNOWN:
            logging.warning("Cannot select asset for unknown architecture")
            return None

        # Look for architecture-specific MSI
        arch_suffix = f"-{self._architecture.value}.msi"
        for asset in assets:
            name = asset.get("name", "").lower()
            if name.endswith(arch_suffix):
                logging.info(f"Found architecture-specific asset: {asset.get('name')}")
                return asset

        logging.error(f"No suitable MSI asset found for architecture: {self._architecture.value}")
        return None

    def check_for_updates(self, timeout: int = 15) -> Optional[ReleaseInfo]:
        """Check GitHub for available updates.

        Args:
            timeout: Request timeout in seconds

        Returns:
            ReleaseInfo if update is available, None otherwise

        Raises:
            urllib.error.URLError: Network errors
            ValueError: Invalid release data
        """
        try:
            request = urllib.request.Request(GITHUB_API_URL, headers=USER_AGENT_HEADER)
            context = ssl.create_default_context(cafile=certifi.where())

            with urllib.request.urlopen(request, context=context, timeout=timeout) as response:
                data = response.read()

            release_data = json.loads(data)
            latest_version = release_data.get("tag_name", "").lstrip("vV")

            if not latest_version:
                raise ValueError("Latest release tag is missing")

            # Check if update is available
            if not self.is_newer_version(latest_version):
                return None

            # Select appropriate asset for architecture
            assets = release_data.get("assets", [])
            msi_asset = self._select_asset_for_architecture(assets)

            if not msi_asset:
                raise ValueError(f"No MSI installer found for {self._architecture.value} architecture")

            release_info = ReleaseInfo(
                version=latest_version,
                changelog=release_data.get("body", ""),
                download_url=msi_asset.get("browser_download_url"),
                asset_name=msi_asset.get("name", f"yasb-{latest_version}-{self._architecture.value}.msi"),
                asset_size=msi_asset.get("size"),
                architecture=self._architecture,
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
            "architecture": self._architecture.value,
            "architecture_display": self.architecture_display,
            "platform": platform.platform(),
            "machine": platform.machine(),
        }

    def is_update_supported(self) -> bool:
        """Check if updates are supported on this system.

        Updates are supported only when:
        1. App is frozen (running as bundled executable)
        2. YASB is installed (not running from source)
        3. Architecture is supported (x64 or ARM64, not UNKNOWN)

        Returns:
            True if updates are supported, False otherwise
        """

        is_forzen = getattr(sys, "frozen", False)
        is_installed = get_app_identifier() == APP_ID
        is_arch_supported = self._architecture != Architecture.UNKNOWN

        return is_installed and is_arch_supported and is_forzen


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
                toaster.show(
                    icon_path=icon_path,
                    title="Update Available",
                    message=f"New version {release_info.version} is available!",
                    launch_url="https://github.com/amnweb/yasb/releases/latest",
                    scenario="reminder",
                )
            # Update last check time
            update_service.update_last_check_time()

        except Exception as e:
            logging.warning(f"Background update check failed: {e}")

    # Start background thread
    threading.Thread(target=_check_for_update, daemon=True, name="UpdateChecker").start()
    logging.info("Background update checker started")
