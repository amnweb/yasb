# pyright: reportPrivateUsage=false

import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from comtypes import GUID
from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QGuiApplication, QImage, QTextDocument
from PyQt6.QtQml import QQmlComponent, QQmlEngine

from core.app.update.installer import Updater, download_installer
from core.app.update.service import UPDATE_TOAST_ACTION, ReleaseInfo
from core.app.windows import about as about_module
from core.app.windows import toast
from core.app.windows.about import About
from core.qml_types import register_qml_types
from core.utils.markdown import fit_images
from core.utils.win32.bindings.ole32 import create_com_object
from core.utils.win32.bindings.shell32 import INotificationActivationCallback
from core.utils.win32.constants import CLSCTX_LOCAL_SERVER
from settings import QML_IMPORT_PATH, TOAST_ACTIVATOR_CLSID
from tests.support.qt import wait


@pytest.fixture
def server() -> Iterator[tuple[str, dict[str, bytes]]]:
    files: dict[str, bytes] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            body = files.get(self.path)
            if body is None:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/png" if self.path.endswith(".png") else "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", files
    httpd.shutdown()
    httpd.server_close()


def release(**changes: Any) -> ReleaseInfo:
    values: dict[str, Any] = {
        "version": "9.9.9",
        "changelog": "## Fixed\n* a thing",
        "download_url": "http://127.0.0.1:9/yasb.msi",
        "asset_name": "yasb.msi",
        "asset_size": None,
        "architecture": "x64",
    }
    return ReleaseInfo(**(values | changes))


def test_the_download_reports_progress_and_keeps_the_file(server: tuple[str, dict[str, bytes]], tmp_path: Path):
    url, files = server
    files["/yasb.msi"] = b"x" * 200_000
    progress: list[int] = []
    path = tmp_path / "yasb.msi"
    download_installer(f"{url}/yasb.msi", path, None, threading.Event(), progress.append)
    assert path.read_bytes() == files["/yasb.msi"]
    assert progress[-1] == 100 and progress == sorted(progress)


@pytest.mark.parametrize("cancelled, expected_size", [(True, None), (False, 300_000)])
def test_a_cancelled_or_short_download_leaves_no_file(
    server: tuple[str, dict[str, bytes]], tmp_path: Path, cancelled: bool, expected_size: int | None
):
    url, files = server
    files["/yasb.msi"] = b"x" * 200_000
    stop = threading.Event()
    if cancelled:
        stop.set()
    path = tmp_path / "yasb.msi"
    with pytest.raises(InterruptedError if cancelled else OSError):
        download_installer(f"{url}/yasb.msi", path, expected_size, stop, lambda _percent: None)
    assert not path.exists()


def test_the_changelog_loads_as_markdown_with_short_links(qapp: QGuiApplication):
    commit = "https://github.com/amnweb/yasb/commit/8926b9de686c75c0fed8fb1a4155cfd7e675c8ee"
    updaters = [Updater(release(changelog=f'<img src="https://x.y/banner.png">\n\n* add a thing {commit}'))]
    updaters.append(Updater(release(changelog=" ")))
    for updater in updaters:
        assert updater.property("changelog") == ""
        updater.loadChangelog()
    for _ in range(100):
        if all(updater.property("changelog") for updater in updaters):
            break
        wait(10)
    assert updaters[0].property("changelog") == f"![](https://x.y/banner.png)\n\n* add a thing [8926b9d]({commit})"
    assert updaters[1].property("changelog") == "_No changelog provided._"


def test_images_shrink_to_the_text_width(qapp: QGuiApplication):
    document = QTextDocument()
    document.setMarkdown("![wide](wide.png) ![small](small.png) ![gone](missing.png)")
    # Added after the text, as a TextEdit loads them
    for name, width, height in (("wide.png", 1600, 100), ("small.png", 40, 20)):
        document.addResource(
            QTextDocument.ResourceType.ImageResource.value,
            QUrl(name),
            QImage(width, height, QImage.Format.Format_ARGB32),
        )

    def sizes() -> list[tuple[float, float]]:
        fragments = document.begin().begin()
        found: list[tuple[float, float]] = []
        while not fragments.atEnd():
            image = fragments.fragment().charFormat().toImageFormat()
            if image.isValid():
                found.append((image.width(), image.height()))
            fragments += 1
        return found

    fit_images(document, 800)
    assert sizes()[:2] == [(800, 50), (40, 20)]
    fit_images(document, 400)
    assert sizes()[:2] == [(400, 25), (40, 20)]


def test_a_failed_download_lets_the_user_try_again(qapp: QGuiApplication):
    updater = Updater(release())
    updater.download()
    for _ in range(100):
        if updater.property("state") == "ready":
            break
        wait(50)
    assert updater.property("state") == "ready"
    assert updater.property("status").startswith("Download failed")


def test_an_available_update_opens_on_the_second_click(qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch):
    found = release()

    def check_for_updates(timeout: int) -> ReleaseInfo:
        return found

    service = SimpleNamespace(is_update_supported=lambda: True, check_for_updates=check_for_updates)
    monkeypatch.setattr(about_module, "get_update_service", lambda: service)
    about = About()
    requested: list[ReleaseInfo] = []
    about.updateRequested.connect(requested.append)
    about.checkForUpdates()
    for _ in range(100):
        if about.property("updateState") == "available":
            break
        wait(20)
    assert about.property("updateState") == "available" and requested == []
    about.checkForUpdates()
    assert requested == [found]


@pytest.mark.parametrize("name", ["AboutWindow", "UpdateWindow"])
def test_the_windows_load(qapp: QGuiApplication, name: str):
    register_qml_types()
    engine = QQmlEngine()
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(Path(QML_IMPORT_PATH, "Yasb", "Common", f"{name}.qml"))))
    controller = About() if name == "AboutWindow" else Updater(release())
    window = component.createWithInitialProperties({"about" if name == "AboutWindow" else "updater": controller})
    assert window is not None, [error.toString() for error in component.errors()]
    window.deleteLater()
    wait(0)


def test_a_click_on_the_update_toast_reaches_its_action(qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(toast, "_actions", {})
    clicks: list[str] = []
    toast.on_toast(UPDATE_TOAST_ACTION, lambda: clicks.append(UPDATE_TOAST_ACTION))
    toast.register_activator()
    try:
        # As the notification center and the notification widget find and call it
        activator = create_com_object(GUID(TOAST_ACTIVATOR_CLSID), INotificationActivationCallback, CLSCTX_LOCAL_SERVER)
        assert activator is not None
        activator.Activate("YASB", UPDATE_TOAST_ACTION, None, 0)
        activator.Activate("YASB", "unknown", None, 0)
    finally:
        toast.revoke_activator()
    assert clicks == [UPDATE_TOAST_ACTION]
