import logging
import os
import shutil
import subprocess
import threading
import webbrowser
from pathlib import Path

from PyQt6.QtCore import QEvent, QSize, Qt
from PyQt6.QtGui import QCursor, QIcon
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

from core.bar_manager import BarManager
from core.config import get_config
from core.ui.windows.about import AboutDialog
from core.utils.controller import exit_application, reload_application
from core.utils.win32.utilities import apply_qmenu_style, disable_autostart, enable_autostart, is_autostart_enabled
from settings import (
    APP_NAME,
    DEFAULT_CONFIG_DIRECTORY,
    GITHUB_URL,
    SCRIPT_PATH,
)

VBS_PATH = os.path.join(SCRIPT_PATH, "yasb.vbs")
EXE_PATH = os.path.join(SCRIPT_PATH, "yasb.exe")
THEME_EXE_PATH = os.path.join(SCRIPT_PATH, "yasb_themes.exe")
SHORTCUT_FILENAME = "yasb.lnk"
AUTOSTART_FILE = EXE_PATH if os.path.exists(EXE_PATH) else VBS_PATH


class SystemTrayManager(QSystemTrayIcon):
    def __init__(self, bar_manager: BarManager):
        super().__init__()
        self._bar_manager = bar_manager
        self._icon = QIcon()
        self._load_favicon()
        self.setToolTip(APP_NAME)
        self._load_config()
        self.activated.connect(self._on_tray_activated)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            if self.menu and self.menu.isVisible():
                global_pos = event.globalPosition().toPoint()
                all_menus = [self.menu]
                all_menus += [act.menu() for act in self.menu.actions() if act.menu() and act.menu().isVisible()]
                if not any(m.geometry().contains(global_pos) for m in all_menus):
                    self.menu.hide()
                    self.menu.deleteLater()
                    return True
        return super().eventFilter(obj, event)

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Context:
            self._load_context_menu()
            self.menu.popup(QCursor.pos())
            self.menu.activateWindow()

    def _load_config(self):
        try:
            config = get_config(show_error_dialog=True)
        except Exception as e:
            logging.error(f"Error loading config: {e}")
            return
        if config["komorebi"]:
            self.komorebi_start = config["komorebi"]["start_command"]
            self.komorebi_stop = config["komorebi"]["stop_command"]
            self.komorebi_reload = config["komorebi"]["reload_command"]

        if config["glazewm"]:
            self.glazewm_start = config["glazewm"]["start_command"]
            self.glazewm_stop = config["glazewm"]["stop_command"]
            self.glazewm_reload = config["glazewm"]["reload_command"]

    def _load_favicon(self):
        # Get the current directory of the script
        self._icon.addFile(os.path.join(SCRIPT_PATH, "assets", "images", "app_icon.png"), QSize(48, 48))
        self.setIcon(self._icon)

    def _load_context_menu(self):
        self.menu = QMenu()
        self.menu.setWindowModality(Qt.WindowModality.WindowModal)
        apply_qmenu_style(self.menu)
        style_sheet = """
        QMenu {
            background-color: #202020;
            color: #ffffff;
            border:1px solid #303030;
            padding:5px 0;
            margin:0;
            border-radius:8px
        }
        QMenu::item {
            margin:0 4px;
            padding: 4px 24px 5px 24px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            font-family: 'Segoe UI';
        }
        QMenu::item:selected {
            background-color: #333333;
        }
        QMenu::separator {
            height: 1px;
            background: #404040;
            margin: 4px 8px;
        }
        QMenu::right-arrow {
            width: 8px;
            height: 8px;
            padding-right:24px;
        }
        """
        self.menu.setStyleSheet(style_sheet)

        def _on_menu_about_to_hide():
            # Restart autohide timers for all registered autohide owners.
            # Use the central global_state registry so we don't need a widget with a bar_id here.
            from core.global_state import get_all_autohide_owners

            try:
                for owner in get_all_autohide_owners():
                    mgr = getattr(owner, "_autohide_manager", None)
                    if mgr and getattr(mgr, "_hide_timer", None):
                        mgr._hide_timer.start(getattr(mgr, "_autohide_delay", 400))
            except Exception:
                pass

        self.menu.aboutToHide.connect(_on_menu_about_to_hide)

        open_config_action = self.menu.addAction("Open Config")
        open_config_action.triggered.connect(self._open_config)
        if os.path.exists(THEME_EXE_PATH):
            yasb_themes_action = self.menu.addAction("Get Themes")
            yasb_themes_action.triggered.connect(lambda: os.startfile(THEME_EXE_PATH))

        reload_action = self.menu.addAction("Reload YASB")
        reload_action.triggered.connect(self._reload_application)
        self.reload_action = reload_action

        self.menu.addSeparator()
        if self.is_wm_installed("komorebi"):
            komorebi_menu = self.menu.addMenu("Komorebi")
            start_komorebi = komorebi_menu.addAction("Start Komorebi")
            start_komorebi.triggered.connect(
                lambda checked=False, wm="Komorebi", cmd=self.komorebi_start: self._run_wm_command(wm, cmd)
            )

            stop_komorebi = komorebi_menu.addAction("Stop Komorebi")
            stop_komorebi.triggered.connect(
                lambda checked=False, wm="Komorebi", cmd=self.komorebi_stop: self._run_wm_command(wm, cmd)
            )

            reload_komorebi = komorebi_menu.addAction("Reload Komorebi")
            reload_komorebi.triggered.connect(
                lambda checked=False, wm="Komorebi", cmd=self.komorebi_reload: self._run_wm_command(wm, cmd)
            )

            apply_qmenu_style(komorebi_menu)

            self.menu.addSeparator()

        if self.is_wm_installed("glazewm"):
            glazewm_menu = self.menu.addMenu("Glazewm")
            start_glazewm = glazewm_menu.addAction("Start Glazewm")
            start_glazewm.triggered.connect(
                lambda checked=False, wm="Glazewm", cmd=self.glazewm_start: self._run_wm_command(wm, cmd)
            )

            stop_glazewm = glazewm_menu.addAction("Stop Glazewm")
            stop_glazewm.triggered.connect(
                lambda checked=False, wm="Glazewm", cmd=self.glazewm_stop: self._run_wm_command(wm, cmd)
            )

            reload_glazewm = glazewm_menu.addAction("Reload Glazewm")
            reload_glazewm.triggered.connect(
                lambda checked=False, wm="Glazewm", cmd=self.glazewm_reload: self._run_wm_command(wm, cmd)
            )

            apply_qmenu_style(glazewm_menu)

            self.menu.addSeparator()

        if self._chek_startup():
            disable_startup_action = self.menu.addAction("Disable Autostart")
            disable_startup_action.triggered.connect(self._disable_startup)
        else:
            enable_startup_action = self.menu.addAction("Enable Autostart")
            enable_startup_action.triggered.connect(self._enable_startup)

        help_action = self.menu.addAction("Help")
        help_action.triggered.connect(lambda: self._open_in_browser(f"{GITHUB_URL}/wiki"))

        about_action = self.menu.addAction("About")
        about_action.triggered.connect(self._show_about_dialog)

        self.menu.addSeparator()
        exit_action = self.menu.addAction("Exit")
        exit_action.triggered.connect(self._exit_application)

    def is_wm_installed(self, wm) -> bool:
        try:
            wm_path = shutil.which(wm)
            return wm_path is not None
        except Exception as e:
            logging.error(f"Error checking {wm} installation: {e}")
            return False

    def _enable_startup(self):
        enable_autostart(APP_NAME, AUTOSTART_FILE)

    def _disable_startup(self):
        disable_autostart(APP_NAME)

    def _chek_startup(self):
        if is_autostart_enabled(APP_NAME):
            return True
        else:
            return False

    def _open_config(self):
        try:
            subprocess.run(["explorer", str(os.path.join(Path.home(), DEFAULT_CONFIG_DIRECTORY))])
        except Exception as e:
            logging.error(f"Failed to open config directory: {e}")

    def _run_wm_command(self, wm, command):
        def wm_command():
            try:
                subprocess.run(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    shell=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            except Exception as e:
                logging.error(f"Failed to start {wm}: {e}")

        threading.Thread(target=wm_command).start()

    def _reload_application(self):
        reload_application("Reloading Application from tray...")

    def _exit_application(self):
        exit_application("Exiting Application from tray...")

    def _open_in_browser(self, url):
        try:
            webbrowser.open(url)
        except Exception as e:
            logging.error(f"Failed to open browser: {e}")

    def _show_about_dialog(self):
        dialog = AboutDialog(self)
        dialog.exec()
