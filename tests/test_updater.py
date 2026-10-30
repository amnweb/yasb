# pyright: reportPrivateUsage=false

import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, QUrl
from PyQt6.QtGui import QImage
from PyQt6.QtQml import QQmlComponent, QQmlEngine
from PyQt6.QtWidgets import QApplication

from core import about as about_module
from core.about import About
from core.updater import Updater, changelog_html, download_installer, fit_images
from core.utils.update_service import ReleaseInfo
from settings import QML_IMPORT_PATH
from tests.support.qt import wait


def png(width: int, height: int) -> bytes:
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(0xFF336699)
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(data.data())


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


def test_changelog_images_are_embedded_and_shrink_to_the_text_width(server: tuple[str, dict[str, bytes]]):
    url, files = server
    files["/wide.png"] = png(1600, 100)
    files["/small.png"] = png(40, 20)
    html, images = changelog_html(
        f'![wide]({url}/wide.png)\n\n<img src="{url}/small.png">\n\n![gone]({url}/missing.png)'
    )
    assert [(image.width, image.height) for image in images] == [(1600, 100), (40, 20)]
    fitted = fit_images(html, images, 800)
    assert 'width="800" height="50"' in fitted
    assert 'width="40" height="20"' in fitted
    assert fitted.count("data:image/png;base64,") == 2
    assert f"{url}/missing.png" in fitted
    assert 'width="1600" height="100"' in fit_images(html, images, 0)


def test_changelog_images_follow_the_window_width(qapp: QApplication, server: tuple[str, dict[str, bytes]]):
    url, files = server
    files["/wide.png"] = png(1600, 100)
    updater = Updater(release(changelog=f"![wide]({url}/wide.png)"))
    updater.setProperty("textWidth", 800)
    updater.loadChangelog()
    for _ in range(100):
        if updater.property("changelog"):
            break
        wait(50)
    assert 'width="800" height="50"' in updater.property("changelog")
    updater.setProperty("textWidth", 400)
    wait(200)
    assert 'width="400" height="25"' in updater.property("changelog")


def test_a_failed_download_lets_the_user_try_again(qapp: QApplication):
    updater = Updater(release())
    updater.download()
    for _ in range(100):
        if updater.property("state") == "ready":
            break
        wait(50)
    assert updater.property("state") == "ready"
    assert updater.property("status").startswith("Download failed")


def test_an_available_update_opens_on_the_second_click(qapp: QApplication, monkeypatch: pytest.MonkeyPatch):
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
def test_the_windows_load(qapp: QApplication, name: str):
    engine = QQmlEngine()
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(Path(QML_IMPORT_PATH, "Yasb", "Common", f"{name}.qml"))))
    controller = About() if name == "AboutWindow" else Updater(release())
    window = component.createWithInitialProperties({"about" if name == "AboutWindow" else "updater": controller})
    assert window is not None, [error.toString() for error in component.errors()]
    window.deleteLater()
    wait(0)
