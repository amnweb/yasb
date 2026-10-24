# pyright: reportPrivateUsage=false

from pathlib import Path

from comtypes import GUID  # pyright: ignore[reportMissingTypeStubs]

from core.widgets.services.notifications.toast_activation import _manifest_activator

MANIFEST = (
    "<Package xmlns='http://schemas.microsoft.com/appx/manifest/foundation/windows10'"
    " xmlns:desktop='http://schemas.microsoft.com/appx/manifest/desktop/windows10'>"
    "<Applications>{}</Applications></Package>"
)


def app(app_id: str, clsid: str | None = None) -> str:
    activation = (
        "<desktop:Extension Category='windows.toastNotificationActivation'>"
        f"<desktop:ToastNotificationActivation ToastActivatorCLSID='{clsid}'/></desktop:Extension>"
        if clsid is not None
        else ""
    )
    return f"<Application Id='{app_id}'><Extensions>{activation}</Extensions></Application>"


def manifest(folder: Path, *apps: str) -> Path:
    folder.mkdir()
    (folder / "AppxManifest.xml").write_text(MANIFEST.format("".join(apps)), encoding="utf-8")
    return folder


def test_each_app_of_a_package_gets_its_own_activator(tmp_path: Path):
    folder = manifest(
        tmp_path / "Package_1.0",
        app("Main", "bebd6a5e-1b14-4a57-a195-c772d28b6d15"),
        app("Cli"),
        app("Launcher", "18a68f64-72dd-42ce-a75d-edbdac226f5d"),
    )
    assert _manifest_activator(folder, "Main") == GUID("{bebd6a5e-1b14-4a57-a195-c772d28b6d15}")
    assert _manifest_activator(folder, "Launcher") == GUID("{18a68f64-72dd-42ce-a75d-edbdac226f5d}")
    assert _manifest_activator(folder, "Cli") is None
    assert _manifest_activator(folder, "Other") is None
    assert _manifest_activator(folder, "") is None


def test_a_manifest_without_an_activator_has_none(tmp_path: Path):
    assert _manifest_activator(manifest(tmp_path / "Bad", app("App", "x")), "App") is None
    assert _manifest_activator(manifest(tmp_path / "Broken", "<unclosed>"), "App") is None
    assert _manifest_activator(tmp_path / "Missing", "App") is None
    assert _manifest_activator(None, "App") is None
