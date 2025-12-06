"""
YASB CLI

NOTE: Avoid importing heavy libraries directly to avoid slowing down the startup time.

To check the startup time, use the following commands (from venv):
python -X importtime src/cli.py 2> import_times.log
pip install tuna
tuna import_times.log
"""

import argparse
import ctypes
import datetime
import getpass
import json
import os
import subprocess
import sys
import textwrap
import time
import winreg
from ctypes import GetLastError

from win32con import (
    GENERIC_READ,
    GENERIC_WRITE,
    OPEN_EXISTING,
)

from core.utils.win32.bindings import (
    CloseHandle,
    CreateFile,
    ReadFile,
    WriteFile,
)
from core.utils.win32.constants import INVALID_HANDLE_VALUE
from settings import APP_NAME, BUILD_VERSION, CLI_VERSION, RELEASE_CHANNEL

BUFSIZE = 65536
YASB_VERSION = BUILD_VERSION
YASB_CLI_VERSION = CLI_VERSION
YASB_RELEASE_CHANNEL = RELEASE_CHANNEL

INSTALLATION_PATH = os.path.abspath(os.path.join(__file__, "../../.."))
EXE_PATH = os.path.join(INSTALLATION_PATH, "yasb.exe")
AUTOSTART_FILE = EXE_PATH if os.path.exists(EXE_PATH) else None

CLI_SERVER_PIPE_NAME = r"\\.\pipe\yasb_pipe_cli"
LOG_SERVER_PIPE_NAME = r"\\.\pipe\yasb_pipe_log"


def is_process_running(process_name: str) -> bool:
    import psutil

    for proc in psutil.process_iter(["name"]):
        if proc.info["name"] == process_name:
            return True
    return False


def write_message(handle: int, msg_dict: dict[str, str]):
    try:
        data = json.dumps(msg_dict).encode("utf-8")
    except Exception as e:
        print(f"JSON encode error: {e}")
        print(f"Data: {msg_dict}")
        return False
    success = WriteFile(handle, data)
    return success


def read_message(handle: int) -> dict[str, str] | None:
    success, data = ReadFile(handle, BUFSIZE)
    if not success or len(data) == 0:
        return None
    try:
        messages: list[str] = []
        # This is needed in case there are multiple json objects in one data block
        for line in data.split(b"\0"):
            if not line.strip():
                continue
            json_object = json.loads(line.decode().strip())
            if json_object.get("type") == "DATA":
                messages.append(json_object.get("data"))
            else:
                # If it's ping/pong, just return the object as is
                return json_object
        return {"type": "DATA", "data": "\n".join(messages)}
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        print(f"Data: {data}")
        return None


class Format:
    reset = "\033[0m"
    green = "\033[92m"
    yellow = "\033[93m"
    red = "\033[91m"
    red_bg = "\033[41m"
    gray = "\033[90m"
    blue = "\033[94m"
    cyan = "\033[96m"
    magenta = "\033[95m"
    underline = "\033[4m"


class CustomArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("suggest_on_error", True)
        super().__init__(*args, **kwargs)

    def error(self, message: str):
        print(f"\n{Format.red}Error:{Format.reset} {message}\n")
        sys.exit(2)


class CLIHandler:
    """Handles the command-line interface for the application."""

    def __init__(self):
        self.task_handler = CLITaskHandler()
        self.update_handler = CLIUpdateHandler()
        self.channel_handler = CLIChannelHandler()

    def send_command_to_application(self, command: str):
        """
        Send a command to the running YASB application through the pipe.

        Commands can be:
        - "stop" - Stop the application
        - "reload" - Reload the application
        - "show-bar [screen]" - Show the bar on a specific screen
        - "hide-bar [screen]" - Hide the bar on a specific screen
        - "toggle-bar [screen]" - Toggle the bar on a specific screen

        Args:
            command: The command to send
        """
        try:
            pipe_handle = CreateFile(
                CLI_SERVER_PIPE_NAME,
                GENERIC_READ | GENERIC_WRITE,
                0,
                None,
                OPEN_EXISTING,
                0,
                None,
            )
            if pipe_handle == INVALID_HANDLE_VALUE:
                print("Failed to connect to YASB. Pipe not found. It may not be running.")
                return

            # Send the command as bytes
            command_bytes = command.encode("utf-8")
            success = WriteFile(pipe_handle, command_bytes)
            if not success:
                print(f"Failed to write command. Err: {GetLastError()}")
                CloseHandle(pipe_handle)
                return

            success, response = ReadFile(pipe_handle, 64 * 1024)
            if not success or len(response) == 0:
                print(f"Failed to read response. Err: {GetLastError()}")
                CloseHandle(pipe_handle)
                return

            response_text = response.decode("utf-8").strip()
            if response_text != "ACK":
                print(f"Received unexpected response: {response_text}")

            CloseHandle(pipe_handle)
        except Exception as e:
            print(f"Error: {e}")

    def _open_startup_registry(self, access_flag: int):
        """Helper function to open the startup registry key."""
        registry_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
        return winreg.OpenKey(winreg.HKEY_CURRENT_USER, registry_path, 0, access_flag)

    def is_autostart_enabled(self, app_name: str) -> bool:
        """Check if application is in Windows startup."""
        try:
            with self._open_startup_registry(winreg.KEY_READ) as key:
                winreg.QueryValueEx(key, APP_NAME)
            return True
        except FileNotFoundError:
            return False
        except Exception as e:
            print(f"Failed to check startup status for {app_name}: {e}")
            return False

    def enable_startup(self):
        if self.is_autostart_enabled(APP_NAME):
            print(f"{APP_NAME} is already set to start on boot.")
            return
        try:
            with self._open_startup_registry(winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f"{AUTOSTART_FILE}")
            print(f"{APP_NAME} added to startup.")
        except Exception as e:
            print(f"Failed to add {APP_NAME} to startup: {e}")

    def disable_startup(self):
        try:
            with self._open_startup_registry(winreg.KEY_ALL_ACCESS) as key:
                winreg.DeleteValue(key, APP_NAME)
            print(f"{APP_NAME} removed from startup.")
        except FileNotFoundError:
            print(f"Startup entry for {APP_NAME} not found.")
        except Exception as e:
            print(f"Failed to remove {APP_NAME} from startup: {e}")

    def parse_arguments(self):
        parser = CustomArgumentParser(
            description="The command-line interface for YASB Reborn.",
            add_help=False,
            prog="yasbc",
        )
        subparsers = parser.add_subparsers(
            dest="command",
            help="Commands",
        )

        start_parser = subparsers.add_parser(
            "start",
            help="Start the application",
            prog="yasbc start",
        )
        start_parser.add_argument(
            "-s",
            "--silent",
            action="store_true",
            help="Silence print messages",
        )

        stop_parser = subparsers.add_parser(
            "stop",
            help="Stop the application",
            prog="yasbc stop",
        )
        stop_parser.add_argument(
            "-s",
            "--silent",
            action="store_true",
            help="Silence print messages",
        )
        stop_parser.add_argument(
            "-f",
            "--force",
            action="store_true",
            help="Force stop the application",
        )

        reload_parser = subparsers.add_parser(
            "reload",
            help="Reload the application",
            prog="yasbc reload",
        )
        reload_parser.add_argument(
            "-s",
            "--silent",
            action="store_true",
            help="Silence print messages",
        )

        subparsers.add_parser(
            "update",
            help="Update the application",
            add_help=False,
        )

        enable_autostart_parser = subparsers.add_parser(
            "enable-autostart",
            help="Enable autostart on system boot",
            prog="yasbc enable-autostart",
        )
        enable_autostart_parser.add_argument(
            "--task",
            action="store_true",
            help="Enable autostart as a scheduled task",
        )

        disable_autostart_parser = subparsers.add_parser(
            "disable-autostart",
            help="Disable autostart on system boot",
            prog="yasbc disable-autostart",
        )
        disable_autostart_parser.add_argument(
            "--task",
            action="store_true",
            help="Disable autostart as a scheduled task",
        )

        subparsers.add_parser(
            "monitor-information",
            help="Show information about connected monitors",
            add_help=False,
        )

        show_bar_parser = subparsers.add_parser(
            "show-bar",
            help="Show the bar on a specific screen",
            prog="yasbc show-bar",
        )
        show_bar_parser.add_argument(
            "-s",
            "--screen",
            type=str,
            help="Screen name (optional)",
        )

        hide_bar_parser = subparsers.add_parser(
            "hide-bar",
            help="Hide the bar on a specific screen",
            prog="yasbc hide-bar",
        )
        hide_bar_parser.add_argument(
            "-s",
            "--screen",
            type=str,
            help="Screen name (optional)",
        )

        toggle_bar_parser = subparsers.add_parser(
            "toggle-bar",
            help="Toggle the bar on a specific screen",
            prog="yasbc toggle-bar",
        )
        toggle_bar_parser.add_argument(
            "-s",
            "--screen",
            type=str,
            help="Screen name (optional)",
        )

        widget_toggle_parser = subparsers.add_parser(
            "toggle-widget",
            help="Toggle a widget show/hide",
            prog="yasbc toggle-widget",
        )
        widget_toggle_parser.add_argument(
            "widget_name",
            type=str,
            help="Name of the widget to toggle",
        )
        widget_toggle_parser.add_argument(
            "-s",
            "--screen",
            type=str,
            help="Screen name (optional)",
        )
        widget_toggle_parser.add_argument(
            "--follow-mouse",
            action="store_true",
            help="Follow mouse cursor (optional)",
        )
        widget_toggle_parser.add_argument(
            "--follow-focus",
            action="store_true",
            help="Follow focused window (optional)",
        )

        # Channel management
        set_channel_parser = subparsers.add_parser(
            "set-channel",
            help="Switch release channels",
            prog="yasbc set-channel",
        )
        set_channel_parser.add_argument(
            "target_channel",
            type=str,
            choices=["stable", "dev"],
            help="Channel to switch to 'stable' for tested releases or 'dev' for latest updates",
        )

        subparsers.add_parser(
            "reset",
            help="Restore default config files and clear cache",
            add_help=False,
        )

        subparsers.add_parser(
            "help",
            help="Show help message",
            add_help=False,
        )
        subparsers.add_parser(
            "log",
            help="Tail yasb process logs (cancel with Ctrl-C)",
            add_help=False,
        )
        parser.add_argument(
            "-v",
            "--version",
            action="store_true",
            help="Show program's version number and exit.",
        )
        parser.add_argument(
            "-h",
            "--help",
            action="store_true",
            help="Show help message",
        )
        args = parser.parse_args()

        if args.command == "start":
            if not args.silent:
                print(
                    textwrap.dedent(f"""\
                    Start YASB Reborn v{YASB_VERSION} in background.

                    # Community
                    * Join the Discord https://discord.gg/qkeunvBFgX - Chat, ask questions, share your desktops and more...
                    * GitHub discussions https://github.com/amnweb/yasb/discussions - Ask questions, share your ideas and more...

                    # Documentation
                    * Read the docs https://github.com/amnweb/yasb/wiki - how to configure and use YASB
                    * Read the FAQ https://github.com/amnweb/yasb/wiki/FAQ
                    
                    # Support the project
                    * Consider sponsoring the project on GitHub Sponsors or Buy Me a Coffee
                    * Thank you for using YASB!
                """)
                )
            subprocess.Popen(["yasb.exe"])
            sys.exit(0)

        elif args.command == "stop":
            if args.force:
                for proc in ["yasb.exe", "yasb_themes.exe"]:
                    if is_process_running(proc):
                        subprocess.run(["taskkill", "/f", "/im", proc], creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                self.send_command_to_application("stop")
            sys.exit(0)

        elif args.command == "reload":
            if is_process_running("yasb.exe"):
                if not args.silent:
                    print("Reload YASB...")
                self.send_command_to_application("reload")
            else:
                print("YASB is not running. Reload aborted.")
            sys.exit(0)

        elif args.command == "show-bar":
            screen_arg = f" --screen {args.screen}" if args.screen else ""
            self.send_command_to_application(f"show-bar{screen_arg}")
            sys.exit(0)

        # For hide-bar command
        elif args.command == "hide-bar":
            screen_arg = f" --screen {args.screen}" if args.screen else ""
            self.send_command_to_application(f"hide-bar{screen_arg}")
            sys.exit(0)

        # For toggle-bar command
        elif args.command == "toggle-bar":
            screen_arg = f" --screen {args.screen}" if args.screen else ""
            self.send_command_to_application(f"toggle-bar{screen_arg}")
            sys.exit(0)

        elif args.command == "toggle-widget":
            if not args.widget_name:
                sys.exit(1)
            if args.screen:
                arg = f" --screen {args.screen}" if args.screen else ""
            elif args.follow_mouse:
                arg = " --follow-mouse"
            elif args.follow_focus:
                arg = " --follow-focus"
            else:
                arg = ""
            self.send_command_to_application(f"toggle-widget {args.widget_name}{arg}")
            sys.exit(0)

        elif args.command == "set-channel":
            self.channel_handler.switch_channel(args.target_channel)
            sys.exit(0)

        elif args.command == "update":
            self.update_handler.update_yasb(YASB_VERSION)

        elif args.command == "enable-autostart":
            if args.task:
                if not self.task_handler.is_admin():
                    print("Please run this command as an administrator.")
                else:
                    self.task_handler.create_task()
            else:
                self.enable_startup()
            sys.exit(0)

        elif args.command == "disable-autostart":
            if args.task:
                if not self.task_handler.is_admin():
                    print("Please run this command as an administrator.")
                else:
                    self.task_handler.delete_task()
            else:
                self.disable_startup()
            sys.exit(0)

        elif args.command == "log":
            print("Starting YASB log client. Press Ctrl+C to exit.")
            try:
                while True:
                    # Wait for the log pipe to be created
                    while True:
                        handle = CreateFile(
                            LOG_SERVER_PIPE_NAME,
                            GENERIC_READ | GENERIC_WRITE,
                            0,
                            None,
                            OPEN_EXISTING,
                            0,
                            None,
                        )
                        if handle != INVALID_HANDLE_VALUE:
                            break
                        time.sleep(0.1)

                    # Start reading the log stream
                    while True:
                        if not write_message(handle, {"type": "PING"}):
                            print(f"Failed to write PING. Err: {GetLastError()}")
                            break
                        for _ in range(2):
                            msg = read_message(handle)
                            if msg is None:
                                print(f"Failed to read message. Err: {GetLastError()}")
                                break
                            if msg.get("type") == "PONG":
                                break
                            elif msg.get("type") == "DATA":
                                print(msg.get("data"))
            except KeyboardInterrupt:
                print("\nExiting YASB log client.")

        elif args.command == "monitor-information":
            try:
                from PyQt6.QtGui import QGuiApplication
                from PyQt6.QtWidgets import QApplication

                app = QApplication([])

                screens = QGuiApplication.screens()
                primary_screen = QGuiApplication.primaryScreen()

                for i, screen in enumerate(screens, 1):
                    geometry = screen.geometry()
                    print(
                        textwrap.dedent(f"""\
                        {Format.underline}Monitor {i}:{Format.reset}
                          Name: {screen.name()}
                          Resolution: {geometry.width()}x{geometry.height()}
                          Position: ({geometry.left()},{geometry.top()}) to ({geometry.left() + geometry.width()},{geometry.top() + geometry.height()})
                          Primary: {"Yes" if screen == primary_screen else "No"}
                          Scale Factor: {screen.devicePixelRatio():.2f}
                          Manufacturer: {screen.manufacturer() or "Unknown"}
                          Model: {screen.model() or "Unknown"}
                    """)
                    )
                app.quit()
            except Exception as e:
                print(f"Error retrieving monitor information: {e}")

        elif args.command == "reset":
            confirm = (
                input(
                    "YASB will be stopped if it is running.\n"
                    "Do you want to continue and restore default config files and clear the cache? (Y/n): "
                )
                .strip()
                .lower()
            )

            if confirm not in ["y", "yes", ""]:
                print("Reset cancelled.")
                sys.exit(0)

            import shutil
            from pathlib import Path

            # Determine config path
            config_home = os.environ.get("YASB_CONFIG_HOME")
            if config_home:
                config_path = Path(config_home)
            else:
                config_path = Path.home() / ".config" / "yasb"

            # Stop YASB if it is running
            for proc in ["yasb.exe", "yasb_themes.exe"]:
                if is_process_running(proc):
                    subprocess.run(["taskkill", "/f", "/im", proc], creationflags=subprocess.CREATE_NO_WINDOW)

            # Delete styles.css and config.yaml if they exist
            for fname in ["styles.css", "config.yaml"]:
                fpath = config_path / fname
                if fpath.exists():
                    try:
                        fpath.unlink()
                        print(f"Deleted {fpath}")
                    except Exception as e:
                        print(f"Failed to delete {fpath}: {e}")

            # Clear all files in app_data_folder if it exists
            from core.utils.utilities import app_data_path

            app_data_folder = app_data_path()
            if app_data_folder.exists() and app_data_folder.is_dir():
                for child in app_data_folder.iterdir():
                    try:
                        if child.is_file() or child.is_symlink():
                            child.unlink()
                            print(f"Deleted {child}")
                        elif child.is_dir():
                            shutil.rmtree(child)
                            print(f"Deleted folder {child}")
                    except Exception as e:
                        print(f"Failed to delete {child}: {e}")

            print("Reset complete.")
            sys.exit(0)

        elif args.command == "help" or args.help:
            print(
                textwrap.dedent(f"""\
                The command-line interface for YASB Reborn.

                {Format.underline}Usage{Format.reset}: yasbc <COMMAND>

                {Format.underline}Commands{Format.reset}:
                  start                     Start the application
                  stop                      Stop the application
                  reload                    Reload the application
                  enable-autostart          Enable autostart on system boot
                  disable-autostart         Disable autostart on system boot
                  monitor-information       Show information about connected monitors
                  show-bar                  Show the bar on all or a specific screen
                  hide-bar                  Hide the bar on all or a specific screen
                  toggle-bar                Toggle the bar on all or a specific screen
                  toggle-widget             Toggle a widget show/hide
                  set-channel               Switch release channels (stable, dev)
                  update                    Update the application
                  log                       Tail yasb process logs (cancel with Ctrl-C)
                  reset                     Restore default config files and clear cache
                  help                      Print this message

                {Format.underline}Options{Format.reset}:
                -v, --version  Print version
                -h, --help     Print this message
            """)
            )
            sys.exit(0)

        elif args.version:
            from core.utils.utilities import get_architecture

            architecture = get_architecture()
            arch_suffix = f" {architecture}" if architecture else ""
            version_message = (
                f"YASB Reborn v{YASB_VERSION}{arch_suffix} ({YASB_RELEASE_CHANNEL})\nYASB-CLI v{YASB_CLI_VERSION}"
            )
            print(version_message)
        else:
            print("Unknown command. Use --help for available options.")
            sys.exit(1)


class CLITaskHandler:
    """Handles tasks related to the command-line interface."""

    def is_admin(self):
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except BaseException:
            return False

    def get_current_user_sid(self):
        import win32security

        username = getpass.getuser()
        user, _, _ = win32security.LookupAccountName(None, username)
        sid = win32security.ConvertSidToStringSid(user)
        return sid

    def create_task(self):
        import win32com.client

        scheduler = win32com.client.Dispatch("Schedule.Service")
        scheduler.Connect()
        root_folder = scheduler.GetFolder("\\")
        task_def = scheduler.NewTask(0)
        task_def.RegistrationInfo.Description = "A highly configurable Windows status bar."
        task_def.RegistrationInfo.Author = "AmN"
        task_def.Settings.Compatibility = 6
        trigger = task_def.Triggers.Create(9)
        trigger.Enabled = True
        trigger.StartBoundary = datetime.datetime.now().isoformat()
        principal = task_def.Principal
        principal.UserId = self.get_current_user_sid()
        principal.LogonType = 3
        principal.RunLevel = 0
        settings = task_def.Settings
        settings.Enabled = True
        settings.StartWhenAvailable = True
        settings.AllowHardTerminate = True
        settings.ExecutionTimeLimit = "PT0S"
        settings.Priority = 4
        settings.MultipleInstances = 3
        settings.DisallowStartIfOnBatteries = False
        settings.StopIfGoingOnBatteries = False
        settings.Hidden = False
        settings.RunOnlyIfIdle = False
        settings.DisallowStartOnRemoteAppSession = False
        settings.UseUnifiedSchedulingEngine = True
        settings.WakeToRun = False
        idle_settings = settings.IdleSettings
        idle_settings.StopOnIdleEnd = True
        idle_settings.RestartOnIdle = False
        action = task_def.Actions.Create(0)
        action.Path = EXE_PATH
        action.WorkingDirectory = INSTALLATION_PATH
        try:
            root_folder.RegisterTaskDefinition("YASB Reborn", task_def, 6, None, None, 3, None)
            print("Task YASB Reborn created successfully.")
        except Exception as e:
            print(f"Failed to create task YASB Reborn. Error: {e}")

    def delete_task(self):
        import win32com.client

        scheduler = win32com.client.Dispatch("Schedule.Service")
        scheduler.Connect()
        root_folder = scheduler.GetFolder("\\")
        try:
            root_folder.DeleteTask("YASB Reborn", 0)
            print("Task YASB Reborn deleted successfully.")
        except Exception:
            print("Failed to delete task YASB or task does not exist.")


class CLIChannelHandler:
    """Handles channel management operations."""

    def switch_channel(self, target_channel: str):
        """Switch to a different release channel.

        Args:
            target_channel: Target channel ('stable' or 'dev')
        """
        import tempfile

        from core.utils.update_service import get_update_service
        from core.utils.utilities import get_architecture

        update_service = get_update_service()
        current_channel = update_service._current_channel
        architecture = get_architecture()

        # Check if already on target channel
        if current_channel == target_channel:
            print(f"\nYou are already on the {target_channel} channel.")
            sys.exit(0)

        # Check if updates are supported
        if not architecture:
            print("\nError: Cannot switch channels - unsupported architecture.")
            sys.exit(1)

        # Show warning message
        print(f"\n{Format.yellow}WARNING: Switching release channels{Format.reset}\n")
        print(
            f"You are about to switch from {Format.yellow}{current_channel}{Format.reset} to {Format.yellow}{target_channel}{Format.reset} channel.\n"
        )
        print("Things to consider:")
        print("  * Configuration files may be incompatible between versions")
        print("  * You may need to reconfigure some settings after switching")
        print("  * Switching channels will download and install a new version of YASB")

        if target_channel == "dev":
            print("  * Bugs and instability may be present in dev channel")
            print("  * Read the changelog: https://github.com/amnweb/yasb/releases/tag/dev")
        else:
            print("  * Read the changelog: https://github.com/amnweb/yasb/releases")

        print()

        # Ask for confirmation
        try:
            user_input = input("Do you want to continue? [y/N]: ").strip().lower()
            if user_input not in ["y", "yes"]:
                print("\nChannel switch canceled.")
                sys.exit(0)
        except KeyboardInterrupt:
            print("\n\nChannel switch canceled.")
            sys.exit(0)

        print(f"\nFetching {Format.magenta}{target_channel}{Format.reset} channel release...")

        try:
            release_info = update_service.check_for_updates(channel=target_channel, skip_version_check=True, timeout=15)
            if target_channel == "dev":
                version_display = f"build {release_info.version.replace('dev-', '')}"
            else:
                version_display = f"version {release_info.version}"
            print(f"Found {Format.magenta}{target_channel}{Format.reset} {version_display}")
            print(f"Installer {release_info.asset_name}")
            if release_info.asset_size:
                print(f"Size {release_info.asset_size / 1024 / 1024:.1f} MB")
            # Download the MSI
            temp_dir = tempfile.gettempdir()
            msi_path = os.path.join(temp_dir, release_info.asset_name)

            # Use CLIUpdateHandler's download method
            update_handler = CLIUpdateHandler()
            update_handler.download_yasb(release_info.download_url, msi_path)

            # Kill running processes
            for proc in ["yasb.exe", "yasb_themes.exe"]:
                if is_process_running(proc):
                    subprocess.run(["taskkill", "/f", "/im", proc], creationflags=subprocess.CREATE_NO_WINDOW)

            # Install and restart
            install_command = f'msiexec /i "{os.path.abspath(msi_path)}" /passive /norestart'
            run_after_command = f'"{EXE_PATH}"'
            combined_command = f"{install_command} && {run_after_command}"

            print("Starting installer...")
            subprocess.Popen(combined_command, shell=True)
            sys.exit(0)

        except Exception as e:
            print(f"\nError switching channels: {e}")
            sys.exit(1)


class CLIUpdateHandler:
    """Handles the update functionality for the command-line interface."""

    def get_installed_product_code(self):
        ERROR_NO_MORE_ITEMS = 259
        MAX_GUID_CHARS = 39
        msi = ctypes.windll.msi
        product_code = ctypes.create_unicode_buffer(MAX_GUID_CHARS + 1)
        index = 0
        while True:
            result = msi.MsiEnumRelatedProductsW("{3f620cf5-07b5-47fd-8e37-9ca8ad14b608}", 0, index, product_code)
            if result == ERROR_NO_MORE_ITEMS:
                break
            elif result == 0:
                return product_code.value
            index += 1
        return None

    def update_yasb(self, yasb_version: str):
        """Check for updates and install if available using centralized update service."""
        import tempfile

        from core.utils.update_service import get_update_service
        from core.utils.utilities import get_architecture

        architecture = get_architecture()
        update_service = get_update_service()

        # Check if updates are supported
        if not update_service.is_update_supported():
            if YASB_RELEASE_CHANNEL.startswith("pr-"):
                print("\nAutomatic updates are disabled for PR build.")
            else:
                print("\nUpdates are not supported on this system.")
            if not architecture:
                print("Reason: Unsupported architecture")
            sys.exit(1)

        print("Checking for updates...")
        arch_suffix = f" ({architecture})" if architecture else ""
        print(f"Current version {yasb_version}{arch_suffix} ({YASB_RELEASE_CHANNEL})")

        try:
            release_info = update_service.check_for_updates(timeout=15)

            if release_info is None:
                print(f"YASB Reborn is already up to date (v{yasb_version}).\n")
                sys.exit(0)

            # Update available
            print(f"Found {Format.cyan}YASB Reborn{Format.reset} Version {release_info.version}")
            print("Changelog https://github.com/amnweb/yasb/releases/latest")
            # Ask the user if they want to continue with the update
            try:
                user_input = input("\nDo you want to continue with the update? (Y/n): ").strip().lower()
                if user_input not in ["y", "yes", ""]:
                    print("\nUpdate canceled.")
                    sys.exit(0)
            except KeyboardInterrupt:
                print("\n\nUpdate canceled.")
                sys.exit(0)

            # Download the MSI
            temp_dir = tempfile.gettempdir()
            msi_path = os.path.join(temp_dir, release_info.asset_name)
            self.download_yasb(release_info.download_url, msi_path)

            # Kill running processes
            for proc in ["yasb.exe", "yasb_themes.exe"]:
                if is_process_running(proc):
                    subprocess.run(["taskkill", "/f", "/im", proc], creationflags=subprocess.CREATE_NO_WINDOW)

            # Install and restart
            install_command = f'msiexec /i "{os.path.abspath(msi_path)}" /passive /norestart'
            run_after_command = f'"{EXE_PATH}"'
            combined_command = f"{install_command} && {run_after_command}"

            print("Starting installer...")
            subprocess.Popen(combined_command, shell=True)
            sys.exit(0)

        except Exception as e:
            print(f"\nFailed to check for updates: {e}")
            sys.exit(1)

    def download_yasb(self, msi_url: str, msi_path: str) -> None:
        """Download a file with progress bar.

        Args:
            msi_url: Download URL
            msi_path: Local file path
        """
        import urllib.error
        from urllib.request import urlopen

        try:
            with urlopen(msi_url) as response:
                content_length = response.getheader("Content-Length")
                if content_length is None:
                    print("Error: Missing Content-Length header.")
                    sys.exit(1)

                try:
                    total_length = int(content_length)
                except ValueError:
                    print(f"Error: Invalid Content-Length value: {content_length}")
                    sys.exit(1)

                downloaded = 0
                chunk_size = 4096
                print(f"Downloading {Format.magenta}{msi_url}{Format.reset}")
                with open(msi_path, "wb") as file:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        file.write(chunk)
                        downloaded += len(chunk)
                        percent = downloaded / total_length * 100
                        bar_length = 30
                        filled = int(bar_length * downloaded / total_length)
                        bar = "\u2588" * filled + "\u2591" * (bar_length - filled)
                        print(f"\r{bar} {percent:.1f}%", end="", flush=True)

                print("\r" + " " * (bar_length + 10) + "\rDownload completed.")

        except KeyboardInterrupt:
            print("\nDownload interrupted by user.")
            sys.exit(0)

        except urllib.error.URLError as e:
            print(f"Download failed: {e}")
            sys.exit(1)

        # Verify the downloaded file size
        downloaded_size = os.path.getsize(msi_path)
        if downloaded_size != total_length:
            print("Error: Downloaded file size does not match expected size.")
            sys.exit(1)


if __name__ == "__main__":
    cli_handler = CLIHandler()
    cli_handler.parse_arguments()
    sys.exit(0)
