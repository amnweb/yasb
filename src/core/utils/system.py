import os
import platform
import sys
from pathlib import Path


def app_data_path(filename: str = None) -> Path:
    """
    Get the YASB local data folder (creating it if it doesn't exist),
    or a file path inside it if filename is provided.
    """
    folder = Path(os.environ["LOCALAPPDATA"]) / "YASB"
    folder.mkdir(parents=True, exist_ok=True)
    if filename is not None:
        return folder / filename
    return folder


def is_windows_10() -> bool:
    v = sys.getwindowsversion()
    return v.major == 10 and v.build < 22000


def detect_architecture() -> tuple[str, str] | None:
    """Detect the system architecture for build purposes.

    Returns:
        Tuple of (display_name, msi_suffix): ("ARM64", "aarch64") or ("x64", "x64"), or None if unknown
    """
    try:
        machine = platform.machine().lower()

        # Check for ARM64
        if machine in ["arm64", "aarch64"]:
            return ("ARM64", "aarch64")

        # Check for x64
        if machine in ["amd64", "x86_64", "x64"]:
            return ("x64", "x64")

        # Fallback: check if running on 64-bit Windows
        if platform.architecture()[0] == "64bit":
            return ("x64", "x64")

        return None
    except Exception:
        return None


def get_architecture() -> str | None:
    """Get the build architecture from BUILD_CONSTANTS.

    Returns:
        Architecture string from frozen build, or None if not frozen/built
    """
    try:
        from BUILD_CONSTANTS import ARCHITECTURE  # type: ignore[import-not-found]

        return ARCHITECTURE
    except ImportError:
        return None
