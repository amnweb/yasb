import logging
import webbrowser
import os 
import shutil
import sys
from pathlib import Path
import subprocess
import winshell
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QCoreApplication, QSize
from core.bar_manager import BarManager
from settings import GITHUB_URL, SCRIPT_PATH, APP_NAME, DEFAULT_CONFIG_DIRECTORY

OS_STARTUP_FOLDER = os.path.join(os.environ['APPDATA'], r'Microsoft\Windows\Start Menu\Programs\Startup')
AUTOSTART_FILE = os.path.join(SCRIPT_PATH, 'yasb.vbs')
SHORTCUT_FILENAME = "yasb.lnk"

class TrayIcon(QSystemTrayIcon):

    def __init__(self, bar_manager: BarManager):
        super().__init__()
        self._bar_manager = bar_manager
        self._docs_url = GITHUB_URL
        self._icon = QIcon()
        self._load_favicon()
        self._load_context_menu()
        self.setToolTip(f"{APP_NAME}")

    def _load_favicon(self):
        self._icon.addFile(os.path.join(SCRIPT_PATH, 'assets', 'favicon', 'launcher.png'), QSize(48, 48))
        self.setIcon(self._icon)

    def _load_context_menu(self):
        menu = QMenu()

        style_sheet = """
        QMenu {
            background-color: #26292b;
            color: #ffffff;
            border:1px solid #373b3e;
            padding:5px 0;
            margin:0;
            border-radius:6px
        }

        QMenu::item {
            margin:0 4px;
            padding: 6px 16px;
            border-radius:4px
        }

        QMenu::item:selected {
            background-color: #373b3e;
        }

        QMenu::separator {
            height: 1px;
            background: #373b3e;
            margin:5px 0;
        }
        """

        menu.setStyleSheet(style_sheet)

        github_action = menu.addAction("Visit GitHub")
        github_action.triggered.connect(self._open_docs_in_browser)
        open_config_action = menu.addAction("Open Config")
        open_config_action.triggered.connect(self._open_config)
        reload_action = menu.addAction("Reload App")
        reload_action.triggered.connect(self._reload_application)
        menu.addSeparator()
        
        if self.is_komorebi_installed():
            start_komorebi = menu.addAction("Start Komorebi")
            start_komorebi.triggered.connect(self._start_komorebi)
            stop_komorebi = menu.addAction("Stop Komorebi")
            stop_komorebi.triggered.connect(self._stop_komorebi)
            menu.addSeparator()
        
        if self.is_autostart_enabled():
            disable_startup_action = menu.addAction("Disable Autostart")
            disable_startup_action.triggered.connect(self._disable_startup)
        else:
            enable_startup_action = menu.addAction("Enable Autostart")
            enable_startup_action.triggered.connect(self._enable_startup)
        
        menu.addSeparator()
        exit_action = menu.addAction("Exit")
        exit_action.triggered.connect(self._exit_application)

        self.setContextMenu(menu)

    def is_autostart_enabled(self):
        return os.path.exists(os.path.join(OS_STARTUP_FOLDER, SHORTCUT_FILENAME))

    def is_komorebi_installed(self):
        try:
            komorebi_path = shutil.which('komorebi')
            return komorebi_path is not None
        except Exception as e:
            logging.error(f"Error checking komorebi installation: {e}")
            return False

    def _enable_startup(self):
        shortcut_path = os.path.join(OS_STARTUP_FOLDER, SHORTCUT_FILENAME)
        try:
            with winshell.shortcut(shortcut_path) as shortcut:
                shortcut.path = AUTOSTART_FILE
                shortcut.working_directory = SCRIPT_PATH
                shortcut.description = "Shortcut to yasb.vbs"
            logging.info(f"Created shortcut at {shortcut_path}")
        except Exception as e:
            logging.error(f"Failed to create startup shortcut: {e}")
        self._load_context_menu()  # Reload context menu

    def _disable_startup(self):
        shortcut_path = os.path.join(OS_STARTUP_FOLDER, SHORTCUT_FILENAME)
        if os.path.exists(shortcut_path):
            try:
                os.remove(shortcut_path)
                logging.info(f"Removed shortcut from {shortcut_path}")
            except Exception as e:
                logging.error(f"Failed to remove startup shortcut: {e}")
        self._load_context_menu()  # Reload context menu

    def _open_config(self):
        CONFIG_DIR = os.path.join(Path.home(), DEFAULT_CONFIG_DIRECTORY)
        try:
            subprocess.run(["explorer", str(CONFIG_DIR)])
        except Exception as e:
            logging.error(f"Failed to open config directory: {e}")

    def _start_komorebi(self):
        try:
            subprocess.run("komorebic start --whkd", stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=True)
        except Exception as e:
            logging.error(f"Failed to start komorebi: {e}")

    def _stop_komorebi(self):
        try:
            subprocess.run("komorebic stop --whkd", stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=True)
        except Exception as e:
            logging.error(f"Failed to stop komorebi: {e}")

    def _reload_application(self):
        logging.info("Reloading Application...")
        os.execl(sys.executable, sys.executable, *sys.argv)

    def _exit_application(self):
        self._bar_manager.close_bars()
        logging.info("Exiting Application...")
        QCoreApplication.exit(0)

    def _open_docs_in_browser(self):
        webbrowser.open(self._docs_url)
