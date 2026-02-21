"""Windows Update module.

Provides synchronous functions for interacting with the Windows Update Agent
COM API (``Microsoft.Update.Session``).

All functions are synchronous and intended to be called from background
threads (QThread workers).
"""

import logging
import subprocess

import win32com.client


def check_updates() -> list[dict[str, str]]:
    """Check for available Windows updates.

    Uses the Windows Update Agent COM API to search for updates
    that are not yet installed.

    Returns:
        List of dicts with standardized keys:
        ``name``, ``id``, ``version``, ``available``, ``source``,
        plus extras: ``description``, ``severity``, ``is_downloaded``.
        Returns an empty list on error.
    """
    try:
        update_session = win32com.client.Dispatch("Microsoft.Update.Session")
        update_searcher = update_session.CreateUpdateSearcher()
        search_result = update_searcher.Search("IsInstalled=0")

        results: list[dict[str, str]] = []
        for update in search_result.Updates:
            kb_ids = []
            for i in range(update.KBArticleIDs.Count):
                kb_ids.append(update.KBArticleIDs.Item(i))
            kb_str = ", ".join(f"KB{kb}" for kb in kb_ids) if kb_ids else ""

            results.append(
                {
                    "name": update.Title,
                    "id": kb_str or update.Title,
                    "version": "",
                    "available": "",
                    "source": "windows",
                    "description": getattr(update, "Description", ""),
                    "severity": getattr(update, "MsrcSeverity", ""),
                    "is_downloaded": str(getattr(update, "IsDownloaded", False)),
                }
            )
        return results

    except Exception:
        logging.exception("Error checking Windows updates")
        return []


def upgrade_packages(package_ids: list[str] | None = None) -> None:
    """Open the Windows Update settings page to install updates."""
    subprocess.Popen("start ms-settings:windowsupdate", shell=True)
