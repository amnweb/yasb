# pyright: reportPrivateUsage=false

from pathlib import Path
from typing import Any

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QEvent, QMetaObject, QObject, QSize, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QGuiApplication, QImage, QKeyEvent
from PyQt6.QtQml import QQmlComponent, QQmlEngine, QQmlError, QQmlProperty
from PyQt6.QtQuick import QQuickItem, QQuickWindow

from core.qml_types import register_qml_types
from core.services.wallpapers import images, manager, thumbnails
from core.services.wallpapers.library import WallpaperLibrary
from core.services.wallpapers.manager import WallpaperManager
from core.services.wallpapers.thumbnails import WallpaperThumbnail, thumbnail_file
from core.widget_files import BUILTIN_WIDGETS_DIR
from settings import QML_IMPORT_PATH
from tests.support.qt import find_item, wait


def until(condition: Any) -> None:
    for _ in range(200):
        if condition():
            return
        wait(10)
    assert condition()


@pytest.fixture
def folder(tmp_path: Path, qapp: QGuiApplication) -> Path:
    """Wallpapers named so File Explorer's order differs from a plain sort."""
    for number, colour in ((1, "#ff0000"), (2, "#00ff00"), (10, "#0000ff")):
        image = QImage(160, 90, QImage.Format.Format_RGB32)
        image.fill(QColor(colour))
        image.save(str(tmp_path / f"wallpaper {number}.png"))
    return tmp_path


class FakeDesktop:
    def __init__(self, shown: str) -> None:
        self.set: list[tuple[str | None, str]] = []
        # What Windows shows on every screen
        self.shown = shown

    def GetMonitorDevicePathCount(self) -> int:
        return 2

    def GetMonitorDevicePathAt(self, index: int) -> str:
        return f"monitor-{index}"

    def SetWallpaper(self, monitor: str | None, path: str) -> None:
        self.set.append((monitor, Path(path).name))
        if monitor is None:
            self.shown = path


class FakeEngine(QObject):
    finished = pyqtSignal()
    made: list[FakeEngine] = []

    def __init__(self, image_path: str, animation: str):
        super().__init__()
        self.animation = animation
        FakeEngine.made.append(self)

    def start(self) -> None:
        pass


@pytest.fixture
def desktop(monkeypatch: pytest.MonkeyPatch, folder: Path) -> FakeDesktop:
    desktop = FakeDesktop(str(folder / "wallpaper 2.png"))
    FakeEngine.made = []
    monkeypatch.setattr(manager, "_desktop_wallpaper", lambda: desktop)
    monkeypatch.setattr(manager, "WallpaperEngine", FakeEngine)
    monkeypatch.setattr(WallpaperManager, "_engine", None)
    monkeypatch.setattr(WallpaperLibrary, "_last_random", None)

    def current_wallpapers(screens: dict[str, tuple[int, int, int, int]]) -> dict[str, str]:
        return dict.fromkeys(screens, desktop.shown)

    monkeypatch.setattr(images, "current_wallpapers", current_wallpapers)
    return desktop


def test_a_thumbnail_covers_the_size_and_is_cached(folder: Path):
    path = thumbnail_file(str(folder / "wallpaper 1.png"), 40, 40)
    image = QImage(path)
    assert (image.width(), image.height()) == (40, 40)
    assert image.pixelColor(20, 20) == QColor("#ff0000")
    assert thumbnails.cached_file(str(folder / "wallpaper 1.png"), 40, 40) == path
    assert thumbnail_file(str(folder / "missing.png"), 40, 40) == ""


def test_a_thumbnail_object_gives_qml_a_file_once_it_is_made(folder: Path):
    made = WallpaperThumbnail()
    made.setProperty("path", str(folder / "wallpaper 10.png"))
    made.setProperty("size", QSize(32, 18))
    until(lambda: not made.property("source").isEmpty())
    image = QImage(made.property("source").toLocalFile())
    assert (image.width(), image.height()) == (32, 18)


def test_the_library_lists_wallpapers_and_finds_the_one_set(desktop: FakeDesktop, folder: Path):
    library = WallpaperLibrary()
    library.setProperty("folders", [str(folder)])
    library.refresh()
    until(lambda: not library.property("scanning"))
    assert [image["name"] for image in library.property("images")] == ["wallpaper 1", "wallpaper 2", "wallpaper 10"]
    screen = QGuiApplication.primaryScreen()
    assert screen is not None
    assert library.currentIndex(screen.name()) == 1
    assert library.currentIndex("elsewhere") == -1


def test_setting_a_wallpaper_plays_the_transition_first(desktop: FakeDesktop, folder: Path):
    library = WallpaperLibrary()
    path = str(folder / "wallpaper 1.png")
    library.setWallpaper(path)
    assert desktop.set == [(None, "wallpaper 1.png")]

    library.setProperty("animation", "circle")
    library.setWallpaper(path)
    # One transition at a time; the second change waits for none and is dropped
    library.setWallpaper(str(folder / "wallpaper 2.png"))
    [engine] = FakeEngine.made
    assert engine.animation == "circle" and len(desktop.set) == 1
    engine.finished.emit()
    assert desktop.set[-1] == (None, "wallpaper 1.png")

    # One screen never animates
    library.setWallpaperOn(path, 1)
    assert desktop.set[-1] == ("monitor-1", "wallpaper 1.png")
    assert library.screenCount() == 2


def test_a_random_wallpaper_is_never_the_last_random_one(desktop: FakeDesktop, folder: Path):
    library = WallpaperLibrary()
    library.setProperty("folders", [str(folder)])
    picks: list[str] = []
    for _ in range(6):
        library.setRandomWallpaper()
        until(lambda: len(desktop.set) > len(picks))
        picks.append(desktop.set[-1][1])
    assert all(first != second for first, second in zip(picks, picks[1:], strict=False))


def load_widget(folder: Path) -> tuple[QQuickItem, QQuickWindow, QQmlEngine, list[str]]:
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    warnings: list[str] = []

    def collect(errors: list[QQmlError]) -> None:
        warnings.extend(error.toString() for error in errors)

    engine.warnings.connect(collect)
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(BUILTIN_WIDGETS_DIR / "Wallpapers" / "Wallpapers.qml")))
    widget = component.createWithInitialProperties({"folders": [str(folder)], "animationDuration": 10})
    assert isinstance(widget, QQuickItem), [error.toString() for error in component.errors()]
    host = QQuickWindow()
    widget.setParentItem(host.contentItem())
    return widget, host, engine, warnings


def open_gallery(widget: QQuickItem) -> QQuickWindow:
    QMetaObject.invokeMethod(widget, "toggleGallery")
    window = QQmlProperty.read(widget, "opened")
    assert isinstance(window, QQuickWindow)
    until(lambda: QQmlProperty.read(gallery_list(window), "count") == 3)
    return window


def gallery_list(window: QQuickWindow) -> QQuickItem:
    view = find_item(window.contentItem(), "wallpapers")  # type: ignore[arg-type]
    assert view is not None
    return view


def press(window: QQuickWindow, key: Qt.Key, held: bool = False) -> None:
    event = QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier, "", held)
    QGuiApplication.sendEvent(window, event)


def centred(view: QQuickItem) -> int:
    """The index of the thumbnail drawn largest, the one in the centre."""
    cards = [item for item in view.childItems() if item.property("growth") is not None]
    return max(cards, key=lambda item: item.property("growth")).property("index")


def test_the_gallery_opens_on_the_wallpaper_set_and_enter_sets_the_selected_one(desktop: FakeDesktop, folder: Path):
    widget, host, _engine, warnings = load_widget(folder)
    window = open_gallery(widget)
    view = gallery_list(window)
    assert QQmlProperty.read(view, "selected") == 1
    press(window, Qt.Key.Key_End)
    assert QQmlProperty.read(view, "selected") == 2
    # A carousel: the first wallpaper follows the last
    press(window, Qt.Key.Key_Right)
    assert QQmlProperty.read(view, "selected") == 0
    press(window, Qt.Key.Key_Left)
    assert QQmlProperty.read(view, "selected") == 2
    press(window, Qt.Key.Key_Return)
    assert desktop.set == [(None, "wallpaper 10.png")]
    until(lambda: QQmlProperty.read(widget, "opened") is None)
    assert not warnings
    sip.delete(widget)
    sip.delete(host)


def test_a_held_key_slides_at_a_steady_speed_and_stops_where_it_is_let_go(desktop: FakeDesktop, folder: Path):
    widget, host, _engine, warnings = load_widget(folder)
    window = open_gallery(widget)
    view = gallery_list(window)
    until(lambda: centred(view) == 1)
    press(window, Qt.Key.Key_Right)
    # Repeats of a held key wait for the carousel to catch up instead of piling up ahead of it
    for _ in range(5):
        press(window, Qt.Key.Key_Right, held=True)
    assert QQmlProperty.read(view, "target") == 2
    until(lambda: abs(QQmlProperty.read(view, "position") - 2) < 0.01)
    assert centred(view) == 2 and QQmlProperty.read(view, "selected") == 2
    assert not warnings
    sip.delete(widget)
    sip.delete(host)


def test_a_held_page_key_pages_once_per_slide_and_stops_where_it_is_let_go(desktop: FakeDesktop, folder: Path):
    widget, host, _engine, warnings = load_widget(folder)
    window = open_gallery(widget)
    view = gallery_list(window)
    start, page = QQmlProperty.read(view, "target"), QQmlProperty.read(view, "page")
    press(window, Qt.Key.Key_PageDown)
    for _ in range(20):
        press(window, Qt.Key.Key_PageDown, held=True)
    assert QQmlProperty.read(view, "target") == start + page
    until(lambda: abs(QQmlProperty.read(view, "position") - (start + page)) < 0.01)
    press(window, Qt.Key.Key_PageUp)
    assert QQmlProperty.read(view, "target") == start
    assert not warnings
    sip.delete(widget)
    sip.delete(host)


def test_escape_closes_the_gallery_without_setting_anything(desktop: FakeDesktop, folder: Path):
    widget, host, engine, _warnings = load_widget(folder)
    window = open_gallery(widget)
    # The open gallery is held, so the garbage collector leaves it alone
    engine.collectGarbage()
    wait(10)
    assert not sip.isdeleted(window) and window.isVisible()
    press(window, Qt.Key.Key_Escape)
    until(lambda: QQmlProperty.read(widget, "opened") is None)
    assert desktop.set == []
    sip.delete(widget)
    sip.delete(host)


def test_reopening_after_setting_a_wallpaper_shows_the_new_one(desktop: FakeDesktop, folder: Path):
    widget, host, _engine, warnings = load_widget(folder)
    [library] = widget.findChildren(WallpaperLibrary)
    window = open_gallery(widget)
    press(window, Qt.Key.Key_End)
    press(window, Qt.Key.Key_Return)
    until(lambda: QQmlProperty.read(widget, "opened") is None)

    window = open_gallery(widget)
    assert QQmlProperty.read(gallery_list(window), "selected") == 2
    until(lambda: not library.property("scanning"))
    assert QQmlProperty.read(gallery_list(window), "selected") == 2
    assert not warnings
    sip.delete(widget)
    sip.delete(host)


@pytest.mark.parametrize("moved", [False, True])
def test_a_rescan_finding_another_wallpaper_recentres_unless_the_user_moved(
    desktop: FakeDesktop, folder: Path, moved: bool
):
    widget, host, _engine, _warnings = load_widget(folder)
    [library] = widget.findChildren(WallpaperLibrary)
    window = open_gallery(widget)
    until(lambda: not library.property("scanning"))
    view = gallery_list(window)
    if moved:
        press(window, Qt.Key.Key_Right)
    # Changed outside YASB, such as in Windows settings
    desktop.shown = str(folder / "wallpaper 1.png")
    library.refresh()
    until(lambda: not library.property("scanning"))
    wait(10)
    assert QQmlProperty.read(view, "selected") == (2 if moved else 0)
    sip.delete(widget)
    sip.delete(host)
