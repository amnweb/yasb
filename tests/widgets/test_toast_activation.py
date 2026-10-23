# pyright: reportPrivateUsage=false

from pathlib import Path

from comtypes import GUID  # pyright: ignore[reportMissingTypeStubs]

from core.widgets.services.notifications.toast_activation import _manifest_activator

MANIFEST = (
    "<Package xmlns='http://schemas.microsoft.com/appx/manifest/foundation/windows10'"
    " xmlns:desktop='http://schemas.microsoft.com/appx/manifest/desktop/windows10'>"
    "<Applications><Application Id='App'><Extensions>{}</Extensions></Application></Applications></Package>"
)


def manifest(folder: Path, extension: str) -> Path:
    folder.mkdir()
    (folder / "AppxManifest.xml").write_text(MANIFEST.format(extension), encoding="utf-8")
    return folder


def test_packaged_apps_declare_their_activator_in_the_manifest(tmp_path: Path):
    folder = manifest(
        tmp_path / "App_1.0",
        "<desktop:Extension Category='windows.toastNotificationActivation'>"
        "<desktop:ToastNotificationActivation ToastActivatorCLSID='bebd6a5e-1b14-4a57-a195-c772d28b6d15'/>"
        "</desktop:Extension>",
    )
    assert _manifest_activator(folder) == GUID("{bebd6a5e-1b14-4a57-a195-c772d28b6d15}")


def test_a_manifest_without_an_activator_has_none(tmp_path: Path):
    assert _manifest_activator(manifest(tmp_path / "Plain", "")) is None
    assert (
        _manifest_activator(manifest(tmp_path / "Bad", "<ToastNotificationActivation ToastActivatorCLSID='x'/>"))
        is None
    )
    assert _manifest_activator(manifest(tmp_path / "Broken", "<unclosed>")) is None
    assert _manifest_activator(tmp_path / "Missing") is None
    assert _manifest_activator(None) is None
