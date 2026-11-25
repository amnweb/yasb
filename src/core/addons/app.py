"""The Addons window's entry point."""

import logging
import os
import sys

from PyQt6 import sip
from PyQt6.QtCore import QTimer, QUrl
from PyQt6.QtGui import QGuiApplication, QIcon, QWindow
from PyQt6.QtQml import QQmlComponent, QQmlEngine, qmlRegisterSingletonType, qmlRegisterUncreatableType

from core.addons.window import Addons
from core.app.log import init_logger
from core.app.single_instance import single_instance_lock
from core.utils.markdown import Markdown
from core.utils.system import app_data_path
from core.utils.win32.dwm import enable_mica
from env import set_defaults
from settings import APP_ICON, QML_IMPORT_PATH


def main() -> int:
    init_logger(path=str(app_data_path("addons.log")), app="YASB Addons")
    set_defaults()
    app = QGuiApplication([*sys.argv, "-style", "FluentWinUI3"])
    app.setApplicationName("YASB Addons")
    app.setWindowIcon(QIcon(APP_ICON))

    qmlRegisterUncreatableType(Addons, "Yasb", 1, 0, "Addons is created by the Addons window", "Addons")
    qmlRegisterSingletonType(Markdown, "Yasb", 1, 0, lambda _engine, _script_engine: Markdown(), "Markdown")

    addons = Addons()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    component = QQmlComponent(
        engine, QUrl.fromLocalFile(os.path.join(QML_IMPORT_PATH, "Yasb", "Addons", "AddonsWindow.qml"))
    )
    window = component.createWithInitialProperties({"addons": addons})
    if not isinstance(window, QWindow):
        logging.error("Could not open the Addons window: %s", [error.toString() for error in component.errors()])
        return 1
    addons.setParent(window)
    window.setProperty("mica", enable_mica(int(window.winId())))
    window.show()
    QTimer.singleShot(0, addons.refresh)
    result = app.exec()
    addons.wait()
    # Deleted before Python shuts down
    sip.delete(window)
    sip.delete(engine)
    return result


if __name__ == "__main__":
    with single_instance_lock("yasb_addons"):
        sys.exit(main())
