import argparse
import ctypes
import datetime
import getpass
import logging
import os
import subprocess
import sys
import tempfile
import textwrap
import time

import requests
import win32com.client
import win32security
from packaging.version import Version
from win32con import (
    GENERIC_READ,
    GENERIC_WRITE,
    OPEN_EXISTING,
)

from core.log import Format
from core.utils.utilities import is_process_running
from core.utils.win32.bindings import (
    CloseHandle,
    CreateFile,
    ReadFile,
    WriteFile,
)
from core.utils.win32.constants import INVALID_HANDLE_VALUE
from core.utils.win32.utilities import create_shortcut
from settings import BUILD_VERSION, CLI_VERSION

YASB_VERSION = BUILD_VERSION
YASB_CLI_VERSION = CLI_VERSION

OS_STARTUP_FOLDER = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup")
INSTALLATION_PATH = os.path.abspath(os.path.join(__file__, "../../.."))
EXE_PATH = os.path.join(INSTALLATION_PATH, "yasb.exe")
SHORTCUT_FILENAME = "yasb.lnk"
AUTOSTART_FILE = EXE_PATH if os.path.exists(EXE_PATH) else None
WORKING_DIRECTORY = INSTALLATION_PATH if os.path.exists(EXE_PATH) else None

CLI_SERVER_PIPE_NAME = r"\\.\pipe\yasb_pipe_cli"
LOG_SERVER_PIPE_NAME = r"\\.\pipe\yasb_pipe_log"


class CustomArgumentParser(argparse.ArgumentParser):
    def error(self, message: str):
        print(f"\n{Format.red}Error:{Format.reset} {message}\n")
        sys.exit(2)


class CLIHandler:
    """Handles the command-line interface for the application."""

    def __init__(self):
        self.task_handler = CLITaskHandler()
        self.update_handler = CLIUpdateHandler()

    def stop_or_reload_application(self, reload: bool = False):
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
            cmd = b"reload" if reload else b"stop"
            WriteFile(pipe_handle, cmd)
            response = ReadFile(pipe_handle, 64 * 1024)
            if response.decode("utf-8").strip() != "ACK":
                print(f"Received unexpected response: {response.decode('utf-8').strip()}")
            CloseHandle(pipe_handle)
        except Exception as e:
            print(f"Error: {e}")

    def _enable_startup(self):
        shortcut_path = os.path.join(OS_STARTUP_FOLDER, SHORTCUT_FILENAME)
        if not AUTOSTART_FILE or not WORKING_DIRECTORY:
            print("Failed to enable autostart. Autostart file or working directory not found.")
            return
        create_shortcut(shortcut_path, AUTOSTART_FILE, WORKING_DIRECTORY)

    def _disable_startup(self):
        shortcut_path = os.path.join(OS_STARTUP_FOLDER, SHORTCUT_FILENAME)
        if os.path.exists(shortcut_path):
            try:
                os.remove(shortcut_path)
                logging.info(f"Removed shortcut from {shortcut_path}")
                print(f"Removed shortcut from {shortcut_path}")
            except Exception as e:
                logging.error(f"Failed to remove startup shortcut: {e}")
                print(f"Failed to remove startup shortcut: {e}")

    def parse_arguments(self):
        parser = CustomArgumentParser(description="The command-line interface for YASB Reborn.", add_help=False)
        subparsers = parser.add_subparsers(dest="command", help="Commands")

        start_parser = subparsers.add_parser("start", help="Start the application")
        start_parser.add_argument("-s", "--silent", action="store_true", help="Silence print messages")

        stop_parser = subparsers.add_parser("stop", help="Stop the application")
        stop_parser.add_argument("-s", "--silent", action="store_true", help="Silence print messages")

        reload_parser = subparsers.add_parser("reload", help="Reload the application")
        reload_parser.add_argument("-s", "--silent", action="store_true", help="Silence print messages")

        subparsers.add_parser("update", help="Update the application")

        enable_autostart_parser = subparsers.add_parser("enable-autostart", help="Enable autostart on system boot")
        enable_autostart_parser.add_argument("--task", action="store_true", help="Enable autostart as a scheduled task")

        disable_autostart_parser = subparsers.add_parser("disable-autostart", help="Disable autostart on system boot")
        disable_autostart_parser.add_argument(
            "--task", action="store_true", help="Disable autostart as a scheduled task"
        )

        subparsers.add_parser("help", help="Show help message")
        subparsers.add_parser("log", help="Tail yasb process logs (cancel with Ctrl-C)")
        parser.add_argument("-v", "--version", action="store_true", help="Show program's version number and exit.")
        parser.add_argument("-h", "--help", action="store_true", help="Show help message")
        args = parser.parse_args()

        if args.command == "start":
            if not args.silent:
                print(f"Start YASB Reborn v{YASB_VERSION} in background.")
                print("\n# Community")
                print(
                    "* Join the Discord https://discord.gg/qkeunvBFgX - Chat, ask questions, share your desktops and more..."
                )
                print(
                    "* GitHub discussions https://github.com/amnweb/yasb/discussions - Ask questions, share your ideas and more..."
                )
                print("\n# Documentation")
                print("* Read the docs https://github.com/amnweb/yasb/wiki - how to configure and use YASB")
            subprocess.Popen(["yasb.exe"])
            sys.exit(0)

        elif args.command == "stop":
            self.stop_or_reload_application()
            sys.exit(0)

        elif args.command == "reload":
            if is_process_running("yasb.exe"):
                if not args.silent:
                    print("Reload YASB...")
                self.stop_or_reload_application(reload=True)
            else:
                print("YASB is not running. Reload aborted.")
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
                self._enable_startup()
            sys.exit(0)

        elif args.command == "disable-autostart":
            if args.task:
                if not self.task_handler.is_admin():
                    print("Please run this command as an administrator.")
                else:
                    self.task_handler.delete_task()
            else:
                self._disable_startup()
            sys.exit(0)

        elif args.command == "log":
            print("Starting YASB log client. Press Ctrl+C to exit.")
            try:
                while True:
                    pipe_handle = self._handle_log_pipe_connection()
                    if pipe_handle is None:
                        print("Could not establish connection. Exiting.")
                        break
                    result = self._handle_log_stream(pipe_handle)
                    print("Closing handle...")
                    CloseHandle(pipe_handle)
                    if result is None:  # KeyboardInterrupt
                        break
                    print("Connection lost. Attempting to reconnect...")
            except KeyboardInterrupt:
                print("\nExiting YASB log client.")

        elif args.command == "help" or args.help:
            print(
                textwrap.dedent(f"""\
                The command-line interface for YASB Reborn.

                {Format.underline}Usage{Format.reset}: yasbc <COMMAND>

                {Format.underline}Commands{Format.reset}:
                  start              Start the application
                  stop               Stop the application
                  reload             Reload the application
                  enable-autostart   Enable autostart on system boot
                  disable-autostart  Disable autostart on system boot
                  update             Update the application
                  log                Tail yasb process logs (cancel with Ctrl-C)
                  help               Print this message

                {Format.underline}Options{Format.reset}:
                -v, --version  Print version
                -h, --help     Print this message
            """)
            )
            sys.exit(0)

        elif args.version:
            version_message = f"YASB Reborn v{YASB_VERSION}\nYASB-CLI v{YASB_CLI_VERSION}"
            print(version_message)
        else:
            logging.info("Unknown command. Use --help for available options.")
            sys.exit(1)

    def _handle_log_pipe_connection(self):
        """Attempt to connect to the named pipe with retry"""
        retries = 0
        pipe_handle = 0
        while retries < 24000:  # Wait for 120 seconds
            try:
                if retries == 0:
                    print("Attempting to connect to YASB log pipe...")

                pipe_handle = CreateFile(
                    LOG_SERVER_PIPE_NAME,
                    GENERIC_READ | GENERIC_WRITE,
                    0,
                    None,
                    OPEN_EXISTING,
                    0,
                    None,
                )

                if pipe_handle == INVALID_HANDLE_VALUE:
                    CloseHandle(pipe_handle)
                    retries += 1
                    time.sleep(0.005)
                    continue

                print("Connected to YASB log stream.")
                retries = 0
                return pipe_handle
            except KeyboardInterrupt:
                print("\nExiting YASB log client.")
                break
            except Exception as e:
                print(f"Error connecting to YASB log pipe: {e}")
        print("Closing handle...")
        CloseHandle(pipe_handle)
        return None

    def _handle_log_stream(self, pipe_handle: int) -> bool | None:
        """Handle reading logs from the pipe with reconnection capability"""
        try:
            while True:
                try:
                    # Wait for the initial PING
                    server_data = ReadFile(pipe_handle, 64 * 1024)
                    if not bool(server_data):
                        print("Empty data received, connection might be closed.")
                        return False  # Empty data received, signal to reconnect.
                    decoded_data = server_data.decode("utf-8").strip()
                    if decoded_data == "PING":
                        WriteFile(pipe_handle, b"PONG")
                    else:
                        print(decoded_data)
                except Exception as e:
                    print(f"\nConnection error: {e}")
                    return False
        except KeyboardInterrupt:
            print("\nStopping log stream...")
            return None  # Signal to fully exit
        except Exception as e:
            print(f"\nUnexpected error: {e}")
            return False  # Signal to reconnect


class CLITaskHandler:
    """Handles tasks related to the command-line interface."""

    def is_admin(self):
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except BaseException:
            return False

    def get_current_user_sid(self):
        username = getpass.getuser()
        user, _, _ = win32security.LookupAccountName(None, username)
        sid = win32security.ConvertSidToStringSid(user)
        return sid

    def create_task(self):
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
        settings.Priority = 7
        settings.MultipleInstances = 0
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
        scheduler = win32com.client.Dispatch("Schedule.Service")
        scheduler.Connect()
        root_folder = scheduler.GetFolder("\\")
        try:
            root_folder.DeleteTask("YASB Reborn", 0)
            print("Task YASB Reborn deleted successfully.")
        except Exception:
            print("Failed to delete task YASB or task does not exist.")


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
        # Fetch the latest tag from the GitHub API
        api_url = "https://api.github.com/repos/amnweb/yasb/releases/latest"
        response = requests.get(api_url)
        latest_release = response.json()
        tag: str = latest_release["tag_name"].lstrip("v")
        changelog = "https://github.com/amnweb/yasb/releases/latest"
        # Step 2: Generate the download link based on the latest tag
        msi_url = f"https://github.com/amnweb/yasb/releases/download/v{tag}/yasb-{tag}-win64.msi"
        temp_dir = tempfile.gettempdir()
        msi_path = os.path.join(temp_dir, f"yasb-{tag}-win64.msi")
        if Version(tag) <= Version(yasb_version):
            print("\nYASB Reborn is already up to date.\n")
            sys.exit(0)
        print(f"\nYASB Reborn version {Format.underline}{tag}{Format.reset} is available.")
        print(f"\nChangelog {changelog}")
        # Ask the user if they want to continue with the update
        try:
            user_input = input("\nDo you want to continue with the update? (Y/n): ").strip().lower()
            if user_input not in ["y", "yes", ""]:
                print("\nUpdate canceled.")
                sys.exit(0)
        except KeyboardInterrupt:
            print("\nUpdate canceled.")
            sys.exit(0)
        # Step 3: Download the latest MSI file
        self.download_yasb(msi_url, msi_path)

        # Step 4: Run the MSI installer in silent mode and restart the application
        if is_process_running("yasb.exe"):
            subprocess.run(["taskkill", "/f", "/im", "yasb.exe"], creationflags=subprocess.CREATE_NO_WINDOW)
        if is_process_running("yasb_themes.exe"):
            subprocess.run(["taskkill", "/f", "/im", "yasb_themes.exe"], creationflags=subprocess.CREATE_NO_WINDOW)

        # Construct the install command as a string
        install_command = f'msiexec /i "{os.path.abspath(msi_path)}" /passive /norestart'
        run_after_command = f'"{EXE_PATH}"'
        # combined_command = f'{uninstall_command} && {install_command} && {run_after_command}'
        combined_command = f"{install_command} && {run_after_command}"
        # Finally run update and restart the application
        subprocess.Popen(combined_command, shell=True)
        sys.exit(0)

    def download_yasb(self, msi_url: str, msi_path: str) -> None:
        try:
            response = requests.get(msi_url, stream=True)
            response.raise_for_status()

            content_length = response.headers.get("content-length")
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

            with open(msi_path, "wb") as file:
                for data in response.iter_content(chunk_size=chunk_size):
                    if not data:
                        continue
                    file.write(data)
                    downloaded += len(data)
                    percent = downloaded / total_length * 100
                    print(f"\rDownloading {percent:.1f}%", end="")

            print("\rDownload completed.          ")

        except KeyboardInterrupt:
            print("\nDownload interrupted by user.")
            sys.exit(0)

        except requests.RequestException as e:
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
