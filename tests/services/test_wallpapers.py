# pyright: reportPrivateUsage=false

from pathlib import Path
from typing import Any

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QEvent, QMetaObject, QObject, QSize, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QGuiApplication, QImage, QImageIOHandler, QImageWriter, QKeyEvent
from PyQt6.QtQml import QQmlComponent, QQmlEngine, QQmlError, QQmlProperty
from PyQt6.QtQuick import QQuickItem, QQuickWindow

from core.qml_types import register_qml_types
from core.services.wallpapers import images, manager, thumbnails
from core.services.wallpapers.engine import _ImageLoader
from core.services.wallpapers.library import WallpaperLibrary
from core.services.wallpapers.manager import WallpaperManager
from core.services.wallpapers.thumbnails import WallpaperThumbnail, thumbnail_file
from core.utils.win32.composition import drawing_surface
from core.widget_files import BUILTIN_WIDGETS_DIR
from settings import QML_IMPORT_PATH
from tests.support.bar import create_with_bar
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
        self.failing = False

    def GetMonitorDevicePathCount(self) -> int:
        return 2

    def GetMonitorDevicePathAt(self, index: int) -> str:
        return f"monitor-{index}"

    def GetWallpaper(self, monitor: str | None) -> str:
        return self.shown

    def SetWallpaper(self, monitor: str | None, path: str) -> None:
        if self.failing:
            raise OSError("SetWallpaper failed")
        self.set.append((monitor, Path(path).name))
        if monitor is None:
            self.shown = path


class FakeEngine(QObject):
    finished = pyqtSignal(str)
    wallpaperSet = pyqtSignal(str)
    closed = pyqtSignal()
    made: list[FakeEngine] = []

    def __init__(self, image_path: str, animation: str, shown_path: str):
        super().__init__()
        self.image_path = image_path
        self.animation = animation
        self.shown_path = shown_path
        self.on_desktop = True
        self.playing = True
        FakeEngine.made.append(self)

    def start(self) -> None:
        pass

    def finish(self) -> None:
        self.playing = False
        self.finished.emit(self.image_path)

    def close(self) -> None:
        """As when Windows destroys the window, putting the wallpaper up."""
        self.on_desktop = False
        self.closed.emit()


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
    [engine] = FakeEngine.made
    # From the wallpaper Windows was given
    assert engine.animation == "circle" and engine.shown_path == desktop.shown and len(desktop.set) == 1
    engine.finish()
    assert desktop.set[-1] == (None, "wallpaper 1.png")
    engine.close()

    # One screen never animates
    library.setWallpaperOn(path, 1)
    assert desktop.set[-1] == ("monitor-1", "wallpaper 1.png")
    assert library.screenCount() == 2


def test_no_wallpaper_is_set_while_a_transition_plays(desktop: FakeDesktop, folder: Path):
    library = WallpaperLibrary()
    library.setProperty("animation", "circle")
    library.setWallpaper(str(folder / "wallpaper 1.png"))
    [engine] = FakeEngine.made
    assert not library.setWallpaper(str(folder / "wallpaper 10.png"))
    assert not library.setWallpaperOn(str(folder / "wallpaper 2.png"), 1)
    assert len(FakeEngine.made) == 1 and desktop.set == []
    engine.finish()
    assert not WallpaperManager.transition_playing()
    # The next one takes the finished transition off the desktop
    assert library.setWallpaper(str(folder / "wallpaper 10.png"))
    assert not engine.on_desktop and FakeEngine.made[-1].image_path == str(folder / "wallpaper 10.png")


def test_a_transition_whose_wallpaper_windows_refuses_closes_itself(desktop: FakeDesktop, folder: Path):
    library = WallpaperLibrary()
    library.setProperty("animation", "circle")
    announced: list[str] = []
    library.wallpaperSet.connect(announced.append)
    desktop.failing = True
    library.setWallpaper(str(folder / "wallpaper 1.png"))
    [engine] = FakeEngine.made
    engine.finish()
    # Windows would never destroy it
    assert not engine.on_desktop and not WallpaperManager.transition_playing()
    # Nor is a wallpaper Windows did not take announced, with or without a transition
    library.setWallpaperOn(str(folder / "wallpaper 2.png"), 1)
    assert announced == []


def test_a_wallpaper_is_announced_once_windows_has_it(desktop: FakeDesktop, folder: Path):
    library = WallpaperLibrary()
    library.setProperty("animation", "circle")
    announced: list[tuple[str, str]] = []

    def announce(path: str) -> None:
        # With the wallpaper Windows shows by then
        announced.append((path, desktop.shown))

    library.wallpaperSet.connect(announce)
    first, second = str(folder / "wallpaper 1.png"), str(folder / "wallpaper 10.png")
    library.setWallpaper(first)
    # Not set, so never announced
    library.setWallpaper(second)
    assert announced == []
    [engine] = FakeEngine.made
    engine.finish()
    assert announced == [(first, first)]
    engine.close()
    library.setWallpaperOn(second, 1)
    assert announced[-1][0] == second


def test_an_image_becomes_a_surface_of_the_shared_compositor(qapp: QGuiApplication):
    # Through Direct3D and the composition interop, which a PyWinRT update could break
    image = QImage(64, 32, QImage.Format.Format_RGB32)
    image.fill(QColor("#336699"))
    surface = drawing_surface(image)
    assert (surface.size.width, surface.size.height) == (64, 32)


def test_the_transition_turns_both_wallpapers_as_their_exif_orientation_asks(tmp_path: Path):
    path = str(tmp_path / "turned.jpg")
    writer = QImageWriter(path)
    writer.setTransformation(QImageIOHandler.Transformation.TransformationRotate90)
    assert writer.write(QImage(40, 20, QImage.Format.Format_RGB32))
    assert _ImageLoader._read(path).size() == QSize(20, 40)


def test_a_random_pick_refused_while_a_transition_is_up_is_not_remembered(desktop: FakeDesktop, folder: Path):
    library = WallpaperLibrary()
    library.setProperty("folders", [str(folder)])
    library.setProperty("animation", "circle")
    library.refresh()
    until(lambda: not library.property("scanning"))
    library.setWallpaper(str(folder / "wallpaper 1.png"))
    library._set_random()
    assert len(FakeEngine.made) == 1 and WallpaperLibrary._last_random is None


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
    widget = create_with_bar(component)
    assert isinstance(widget, QQuickItem), [error.toString() for error in component.errors()]
    settings = widget.property("settings")
    settings.setProperty("folders", [str(folder)])
    settings.setProperty("animationDuration", 10)
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


def test_a_refused_pick_keeps_the_gallery_open(desktop: FakeDesktop, folder: Path, monkeypatch: pytest.MonkeyPatch):
    widget, host, _engine, warnings = load_widget(folder)
    window = open_gallery(widget)
    # A transition still playing
    monkeypatch.setattr(WallpaperManager, "_engine", FakeEngine("wallpaper 1.png", "circle", ""))
    press(window, Qt.Key.Key_Return)
    # Longer than the gallery takes to fade out and close
    wait(400)
    assert desktop.set == [] and QQmlProperty.read(widget, "opened") is window and window.isVisible()
    monkeypatch.setattr(WallpaperManager, "_engine", None)
    press(window, Qt.Key.Key_Return)
    assert desktop.set == [(None, "wallpaper 2.png")]
    until(lambda: QQmlProperty.read(widget, "opened") is None)
    assert not warnings
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
