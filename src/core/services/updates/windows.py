"""Windows Update's pending updates, through the Windows Update Agent's COM API."""

import logging
from ctypes import COMError
from typing import Any

from core.utils.shell_utils import shell_open
from core.utils.win32.bindings.ole32 import CoInitialize, CoUninitialize, create_dispatch
from core.utils.win32.constants import DISP_E_EXCEPTION

NAME = "Windows Update"
# Updates not yet installed, leaving out the ones hidden in Settings
SEARCH = "IsInstalled=0 and IsHidden=0"


def installed() -> bool:
    return True


def _search() -> dict[str, Any]:
    # COM objects must be released before CoUninitialize, so they stay local to this function
    searcher = create_dispatch("Microsoft.Update.Session").CreateUpdateSearcher()
    found = searcher.Search(SEARCH).Updates
    updates: list[dict[str, Any]] = []
    for index in range(found.Count):
        update = found.Item(index)
        articles = update.KBArticleIDs
        kb = ", ".join(f"KB{articles.Item(i)}" for i in range(articles.Count))
        # Its classification, such as "Security Updates" or "Drivers"; the other categories name products
        categories = update.Categories
        category = next(
            (
                str(categories.Item(i).Name)
                for i in range(categories.Count)
                if str(categories.Item(i).Type) == "UpdateClassification"
            ),
            "",
        )
        updates.append(
            {
                "id": str(update.Identity.UpdateID),
                "name": str(update.Title),
                "category": category,
                "kb": kb,
                "severity": str(update.MsrcSeverity or ""),
                "downloaded": bool(update.IsDownloaded),
                "installedVersion": "",
                "availableVersion": "",
            }
        )
    restart = bool(create_dispatch("Microsoft.Update.SystemInfo").RebootRequired)
    return {"updates": updates, "restartRequired": restart}


def check() -> dict[str, Any]:
    """The pending updates and whether Windows waits for a restart, as {updates, restartRequired}.

    Raises RuntimeError with what went wrong.
    """
    result = CoInitialize()
    try:
        return _search()
    except COMError as error:
        if error.hresult == DISP_E_EXCEPTION:
            raise RuntimeError("Could not reach Windows Update. Check the internet connection.") from error
        logging.exception("Could not check Windows Update")
        raise RuntimeError("Could not check Windows Update.") from error
    finally:
        if result >= 0:
            CoUninitialize()


def open_settings() -> None:
    """Windows installs its own updates, from Windows Update in Settings."""
    shell_open("ms-settings:windowsupdate")
