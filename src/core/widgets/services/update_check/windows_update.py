"""Windows Update module.

Provides synchronous functions for interacting with the Windows Update Agent
COM API (``Microsoft.Update.Session``).

All functions are synchronous and intended to be called from background
threads (QThread workers).
"""

import logging
from typing import Any

from comtypes import COMError  # pyright: ignore[reportMissingTypeStubs]

from core.utils.shell_utils import shell_open
from core.utils.win32.bindings.ole32 import CoInitialize, CoUninitialize, create_dispatch
from core.utils.win32.constants import DISP_E_EXCEPTION


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
    hr = CoInitialize()
    try:
        return _search_updates()
    except Exception as e:
        # When offline, Search("IsInstalled=0") fails with DISP_E_EXCEPTION
        if isinstance(e, COMError) and e.hresult == DISP_E_EXCEPTION:
            logging.warning("Offline or network issue while checking Windows updates.")
        else:
            logging.exception("Error checking Windows updates")
        return []
    finally:
        if hr >= 0:
            CoUninitialize()


def _search_updates() -> list[dict[str, str]]:
    # COM objects must be released before CoUninitialize, so they stay local to this function
    update_session = create_dispatch("Microsoft.Update.Session")
    update_searcher = update_session.CreateUpdateSearcher()
    search_result = update_searcher.Search("IsInstalled=0")

    results: list[dict[str, str]] = []
    for update in search_result.Updates:
        kb_ids: list[Any] = []
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


def upgrade_packages(package_ids: list[str] | None = None) -> None:
    """Open the Windows Update settings page to install updates."""
    shell_open("ms-settings:windowsupdate")
