from pathlib import Path

from PyQt6.QtCore import QObject, QUrl
from PyQt6.QtQml import QQmlComponent, QQmlEngine

from core.bar.revisions import Revisions, path_key
from core.widget_files import file_name
from settings import DEFAULT_CONFIG_DIRECTORY, SCRIPT_PATH

USER_THEMES_DIR = Path(DEFAULT_CONFIG_DIRECTORY) / "themes"
THEME_QML = Path(SCRIPT_PATH) / "core" / "qml" / "Yasb" / "Themes" / "Theme.qml"
DEFAULT_THEME = "default"


class ThemeError(Exception):
    pass


def config_qml_file(name: str, folder: Path) -> Path:
    """The file config.yaml names, in any case: a .qml path, relative to the config folder; for an addon such as
    amnweb.nord, Nord.qml in folder/amnweb.nord; or name.qml in folder. A file that is not there keeps the path it
    would have."""
    if Path(name).suffix.lower() == ".qml":
        path = Path(DEFAULT_CONFIG_DIRECTORY) / name
    elif "." in name:
        path = folder / name / file_name(name)
    else:
        path = folder / f"{name}.qml"
    # QML refuses a path whose case differs from the file's; resolving gives the name as it is on disk
    return path.resolve() if path.is_file() else path


def find_theme_file(theme: str) -> Path | None:
    """A .qml path, relative to the config folder, or a name found in the themes folder as name.qml or as an addon's
    folder, in any case."""
    path = config_qml_file(theme, USER_THEMES_DIR)
    return path if path.is_file() else None


def load_theme(
    engine: QQmlEngine, revisions: Revisions, theme: str | None, parent: QObject
) -> tuple[QObject, set[str], list[str]]:
    """The theme a bar names, owned by parent, with the key of its file and its errors. A bar that names
    none, or whose theme could not be loaded, gets the default theme."""
    path = None
    created = None
    errors: list[str] = []
    if theme and theme.lower() != DEFAULT_THEME:
        path = find_theme_file(theme)
        try:
            if path is None:
                raise ThemeError(f"Theme '{theme}' not found: name a .qml file in {USER_THEMES_DIR}, or a path to one")
            created = _create(engine, revisions.url(path))
        except ThemeError as error:
            errors.append(str(error))
    if created is None:
        created = _create(engine, QUrl.fromLocalFile(str(THEME_QML)))
    created.setParent(parent)
    return created, {path_key(path)} if path is not None else set(), errors


def _create(engine: QQmlEngine, url: QUrl) -> QObject:
    component = QQmlComponent(engine, url)
    created = None if component.isError() else component.create()
    if created is None or created.property("colors") is None:
        if created is not None:
            created.deleteLater()
        errors = "; ".join(error.toString() for error in component.errors())
        raise ThemeError(
            errors or f"{url.toLocalFile()} is not a theme, its root must be Theme from 'import Yasb.Themes'"
        )
    return created
