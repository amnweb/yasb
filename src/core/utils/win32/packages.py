"""Lookups for packaged (Store) applications.

An AUMID is the only name a notification carries, and for a packaged sender it is also the
way to its install folder, which is what the resources it names are relative to.
"""

import logging
from pathlib import Path


def package_family_name(aumid: str) -> str:
    """The package family name of a packaged sender, which its AUMID is prefixed with."""
    return aumid.split("!")[0] if "!" in aumid else ""


# family name -> install folder, for packages that were found
_installed: dict[str, Path] = {}


def installed_path(family_name: str) -> Path | None:
    """Where a packaged app is installed, which is what ms-appx: is relative to.

    Only a package that was found is remembered, so one installed while YASB is running is
    picked up the next time it is asked for rather than staying missing until a restart.
    """
    if not family_name:
        return None
    if family_name in _installed:
        return _installed[family_name]
    try:
        from winrt.windows.management.deployment import PackageManager

        # The user scoped lookup is the one that works without elevation
        for package in PackageManager().find_packages_by_user_security_id_package_family_name("", family_name):
            path = package.installed_path
            if path:
                _installed[family_name] = Path(path)
                return _installed[family_name]
    except Exception as e:
        logging.debug("Failed to locate package %s: %s", family_name, e)
    return None
