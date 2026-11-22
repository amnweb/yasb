import os
import sys
lazy import datetime
lazy import shutil
lazy import subprocess
lazy import tempfile
lazy import textwrap
lazy import time
lazy import winreg
lazy from collections.abc import Callable
lazy from pathlib import Path
lazy from typing import NoReturn
lazy from urllib.error import URLError
lazy from urllib.request import urlopen

lazy from PyQt6.QtGui import QGuiApplication

from core.cli.parser import Argument, Command, Option, build, print_help
from settings import (
    APP_NAME,
    BUILD_VERSION,
    CLI_VERSION,
    DEFAULT_CONFIG_DIRECTORY,
    RELEASE_CHANNEL,
    SCRIPT_PATH,
)
lazy from core.app.update.service import ReleaseInfo, get_update_service
lazy from core.cli.addons import CLIAddonsHandler
lazy from core.cli.pipe import CLI_SERVER_PIPE_NAME, LOG_SERVER_PIPE_NAME, read_message, write_message
lazy from core.cloud.cli import run as run_cloud
lazy from core.utils.process import is_process_running
lazy from core.utils.system import app_data_path, get_architecture
lazy from core.utils.win32.autostart import (
    AUTOSTART_FILE,
    EXE_PATH,
    disable_autostart,
    enable_autostart,
    is_autostart_enabled,
)
lazy from core.utils.win32.bindings.advapi32 import get_current_user_sid
lazy from core.utils.win32.bindings.kernel32 import CloseHandle, CreateFile, GetLastError, ReadFile, WriteFile
lazy from core.utils.win32.bindings.ole32 import create_dispatch
lazy from core.utils.win32.bindings.shell32 import IsUserAnAdmin
lazy from core.utils.win32.constants import (
    GENERIC_READ,
    GENERIC_WRITE,
    INVALID_HANDLE_VALUE,
    MINIDUMP_WITH_DATA_SEGS,
    MINIDUMP_WITH_FULL_MEMORY_INFO,
    MINIDUMP_WITH_HANDLE_DATA,
    MINIDUMP_WITH_INDIRECTLY_REFERENCED_MEMORY,
    MINIDUMP_WITH_PROCESS_THREAD_DATA,
    MINIDUMP_WITH_THREAD_INFO,
    MINIDUMP_WITH_UNLOADED_MODULES,
    OPEN_EXISTING,
)
lazy from core.utils.win32.registry_keys import WER_LOCAL_DUMPS_KEY

YASBC = Command(
    "yasbc",
    "The command-line interface for YASB Reborn",
    options=(
        Option(("-v", "--version"), "Print version"),
        Option(("-c", "--config"), "Print config directory path"),
    ),
    commands=(
        Command("start", "Start the application", options=(Option(("-s", "--silent"), "Silence print messages"),)),
        Command(
            "stop",
            "Stop the application",
            options=(
                Option(("-s", "--silent"), "Silence print messages"),
                Option(("-f", "--force"), "Force stop the application"),
            ),
        ),
        Command("reload", "Reload the application", options=(Option(("-s", "--silent"), "Silence print messages"),)),
        Command(
            "enable-autostart",
            "Enable autostart on system boot",
            options=(Option(("--task",), "Enable autostart as a scheduled task"),),
        ),
        Command(
            "disable-autostart",
            "Disable autostart on system boot",
            options=(Option(("--task",), "Disable autostart as a scheduled task"),),
        ),
        Command("enable-crash-dumps", "Enable crash dumps for troubleshooting"),
        Command("disable-crash-dumps", "Disable crash dumps"),
        Command("monitor-information", "Show information about connected monitors"),
        Command(
            "show-bar",
            "Show the bar on all or a specific screen",
            options=(Option(("-s", "--screen"), "Screen name (optional)", value="SCREEN"),),
        ),
        Command(
            "hide-bar",
            "Hide the bar on all or a specific screen",
            options=(Option(("-s", "--screen"), "Screen name (optional)", value="SCREEN"),),
        ),
        Command(
            "toggle-bar",
            "Toggle the bar on all or a specific screen",
            options=(Option(("-s", "--screen"), "Screen name (optional)", value="SCREEN"),),
        ),
        Command(
            "set-channel",
            "Switch release channels",
            arguments=(
                Argument(
                    "target_channel",
                    "'stable' for tested releases or 'preview' for the latest updates",
                    choices=("stable", "preview"),
                ),
            ),
        ),
        Command("update", "Update the application"),
        Command("log", "Tail yasb process logs (cancel with Ctrl-C)"),
        Command("reset", "Restore default config files and clear cache"),
        Command("cloud", "Back up and restore your config with YASB Cloud", passthrough=True),
        Command(
            "addons",
            "Copy YASB's widgets, and update, list and remove your addons",
            commands=(
                Command(
                    "copy",
                    "Copy a widget's settings to change them, or the whole widget with --full",
                    arguments=(Argument("name", "The widget, such as clock"),),
                    options=(
                        Option(("--full",), "Copy the whole widget, not only its settings"),
                        Option(("--force",), "Replace your copy if you have one"),
                    ),
                ),
                Command(
                    "update",
                    "Update your copies of YASB's widgets",
                    arguments=(Argument("name", "Only this widget", optional=True),),
                ),
                Command(
                    "remove",
                    "Delete a widget from your widgets folder",
                    arguments=(Argument("name", "The widget, such as clock"),),
                    options=(Option(("-y", "--yes"), "Delete without asking"),),
                ),
                Command("list", "List the widgets in your widgets folder"),
            ),
        ),
        Command("config-dir", "Open config directory in file explorer"),
    ),
)


def _stop_yasb() -> None:
    if is_process_running("yasb.exe"):
        subprocess.run(["taskkill", "/f", "/im", "yasb.exe"], creationflags=subprocess.CREATE_NO_WINDOW)


def _as_admin(action: Callable[[], object]) -> None:
    try:
        admin = IsUserAnAdmin()
    except BaseException:
        admin = False
    if admin:
        action()
    else:
        print("Please run this command as an administrator.")


class Format:
    reset = "\033[0m"
    yellow = "\033[93m"
    cyan = "\033[96m"
    magenta = "\033[95m"
    underline = "\033[4m"


class CLIHandler:
    """Handles the command-line interface for the application."""

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

    def enable_startup(self):
        if is_autostart_enabled(APP_NAME):
            print(f"{APP_NAME} is already set to start on boot.")
        elif enable_autostart(APP_NAME, f"{AUTOSTART_FILE}"):
            print(f"{APP_NAME} added to startup.")

    def disable_startup(self):
        if not is_autostart_enabled(APP_NAME):
            print(f"Startup entry for {APP_NAME} not found.")
        elif disable_autostart(APP_NAME):
            print(f"{APP_NAME} removed from startup.")

    def parse_arguments(self):
        parser = build(YASBC)
        args, passthrough = parser.parse_known_args()
        # Only `cloud` is allowed leftovers, every other command stays strict.
        if passthrough and args.command != "cloud":
            parser.error(f"unrecognized arguments: {' '.join(passthrough)}")
        if args.command == "start":
            if not args.silent:
                print(
                    textwrap.dedent(f"""\
                    Start YASB Reborn v{BUILD_VERSION} in background.

                    # Community
                    * Join the Discord https://discord.gg/qkeunvBFgX - Chat, ask questions, share your desktops and more...
                    * GitHub discussions https://github.com/amnweb/yasb/discussions - Ask questions, share your ideas and more...
                    * Offical Website https://yasb.dev
                    
                    # Documentation
                    * Read the docs https://docs.yasb.dev/latest - how to configure and use YASB
                    * Read the FAQ https://docs.yasb.dev/latest/faq
                    
                    # Support the project
                    * Consider sponsoring the project on GitHub Sponsors or Buy Me a Coffee
                    * Thank you for using YASB!
                """)
                )
            subprocess.Popen(["yasb.exe"])
            sys.exit(0)

        elif args.command == "stop":
            if args.force:
                _stop_yasb()
            else:
                self.send_command_to_application("stop")
            sys.exit(0)
        elif args.command == "cloud":
            sys.exit(run_cloud(passthrough))
        elif args.command == "help":
            if args.help_path[:1] == ["cloud"]:
                sys.exit(run_cloud(["help", *args.help_path[1:]]))
            sys.exit(print_help(YASBC, args.help_path))
        elif args.command == "addons":
            addons = CLIAddonsHandler()
            if args.addons_command == "copy":
                sys.exit(addons.copy(args.name, full=args.full, force=args.force))
            if args.addons_command == "update":
                sys.exit(addons.update(args.name))
            if args.addons_command == "remove":
                sys.exit(addons.remove(args.name, yes=args.yes))
            if args.addons_command == "list":
                sys.exit(addons.list())
            sys.exit(print_help(YASBC, ["addons", *(args.help_path if args.addons_command == "help" else [])]))
        elif args.command == "reload":
            if is_process_running("yasb.exe"):
                if not args.silent:
                    print("Reload YASB...")
                self.send_command_to_application("reload")
            else:
                print("YASB is not running. Reload aborted.")
            sys.exit(0)

        elif args.command in ("show-bar", "hide-bar", "toggle-bar"):
            screen_arg = f" --screen {args.screen}" if args.screen else ""
            self.send_command_to_application(f"{args.command}{screen_arg}")
            sys.exit(0)

        elif args.command == "set-channel":
            CLIChannelHandler().switch_channel(args.target_channel)
            sys.exit(0)

        elif args.command == "update":
            CLIUpdateHandler().update_yasb()

        elif args.command == "enable-autostart":
            if args.task:
                _as_admin(CLITaskHandler().create_task)
            else:
                self.enable_startup()
            sys.exit(0)

        elif args.command == "disable-autostart":
            if args.task:
                _as_admin(CLITaskHandler().delete_task)
            else:
                self.disable_startup()
            sys.exit(0)

        elif args.command == "enable-crash-dumps":
            _as_admin(CLICrashDumpHandler().enable)
            sys.exit(0)

        elif args.command == "disable-crash-dumps":
            _as_admin(CLICrashDumpHandler().disable)
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
                app = QGuiApplication([])

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

            config_path = Path(DEFAULT_CONFIG_DIRECTORY)
            _stop_yasb()

            # Delete config.yaml if it exists, so YASB opens the setup on its next start
            fpath = config_path / "config.yaml"
            if fpath.exists():
                try:
                    fpath.unlink()
                    print(f"Deleted {fpath}")
                except Exception as e:
                    print(f"Failed to delete {fpath}: {e}")

            # Clear all files in app_data_folder if it exists

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

        elif args.command == "config-dir":
            try:
                subprocess.Popen(["explorer", DEFAULT_CONFIG_DIRECTORY])
            except Exception as e:
                print(f"Failed to open config directory: {e}")
            sys.exit(0)

        elif args.config:
            print(DEFAULT_CONFIG_DIRECTORY)
            sys.exit(0)

        elif args.version:
            architecture = get_architecture()
            arch_suffix = f" {architecture}" if architecture else ""
            version_message = f"YASB Reborn v{BUILD_VERSION}{arch_suffix} ({RELEASE_CHANNEL})\nYASB-CLI v{CLI_VERSION}"
            print(version_message)
        else:
            sys.exit(print_help(YASBC))


class CLICrashDumpHandler:
    """Turn Windows crash dumps for yasb.exe on or off.

    Windows logs crashes to the Event Viewer but doesn't save a dump file unless
    you ask it to, so there is usually nothing left to debug after a native crash.

    https://learn.microsoft.com/en-us/windows/win32/wer/collecting-user-mode-dumps
    """

    KEY_PATH = WER_LOCAL_DUMPS_KEY + "\\yasb.exe"
    DUMP_FOLDER = os.path.join(DEFAULT_CONFIG_DIRECTORY, "dumps")
    # Minidump missing some information, so we use a custom dump type with the following flags.
    # See https://learn.microsoft.com/en-us/windows/win32/wer/collecting-user-mode-dumps#custom-dump-flags
    DUMP_TYPE = 0  # 0 = custom (CUSTOM_DUMP_FLAGS), 1 = mini dump, 2 = full dump
    CUSTOM_DUMP_FLAGS = (
        MINIDUMP_WITH_DATA_SEGS  # module globals (WER default)
        | MINIDUMP_WITH_HANDLE_DATA  # handle table, so !handle works
        | MINIDUMP_WITH_UNLOADED_MODULES  # catches DLL-unload races (WER default)
        | MINIDUMP_WITH_INDIRECTLY_REFERENCED_MEMORY  # heap reachable from registers/stack
        | MINIDUMP_WITH_PROCESS_THREAD_DATA  # PEB/TEB (WER default)
        | MINIDUMP_WITH_FULL_MEMORY_INFO  # VA layout, so !address works
        | MINIDUMP_WITH_THREAD_INFO  # thread times and state
    )
    DUMP_COUNT = 5
    OWNS_PARENT_VALUE = "YasbCreatedLocalDumps"

    def _parent_key_exists(self) -> bool:
        try:
            winreg.CloseKey(winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, WER_LOCAL_DUMPS_KEY))
            return True
        except OSError:
            return False

    def enable(self):
        # An empty LocalDumps key is itself a switch that makes Windows dump every
        # application, and creating our key creates it too. Remember whether it was
        # already there so disable() only removes one we made.
        parent_existed = self._parent_key_exists()

        try:
            with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, self.KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, "DumpFolder", 0, winreg.REG_EXPAND_SZ, self.DUMP_FOLDER)
                winreg.SetValueEx(key, "DumpType", 0, winreg.REG_DWORD, self.DUMP_TYPE)
                winreg.SetValueEx(key, "CustomDumpFlags", 0, winreg.REG_DWORD, self.CUSTOM_DUMP_FLAGS)
                winreg.SetValueEx(key, "DumpCount", 0, winreg.REG_DWORD, self.DUMP_COUNT)
                if not parent_existed:
                    winreg.SetValueEx(key, self.OWNS_PARENT_VALUE, 0, winreg.REG_DWORD, 1)
        except OSError as e:
            print(f"Failed to enable crash dumps: {e}")
            return

        try:
            os.makedirs(self.DUMP_FOLDER, exist_ok=True)
        except OSError as e:
            print(f"Warning: could not create the dump directory: {e}")

        print("Crash dumps enabled.")
        print(f"Dumps will be saved to {self.DUMP_FOLDER}")
        print(f"The last {self.DUMP_COUNT} are kept. Attach the newest one when reporting a crash.")
        print("A dump is a snapshot of memory, so it can contain data from your config.")

    def disable(self):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, self.KEY_PATH) as key:
                created_parent = bool(winreg.QueryValueEx(key, self.OWNS_PARENT_VALUE)[0])
        except OSError:
            created_parent = False

        try:
            winreg.DeleteKey(winreg.HKEY_LOCAL_MACHINE, self.KEY_PATH)
        except FileNotFoundError:
            print("Crash dumps are not enabled.")
            return
        except OSError as e:
            print(f"Failed to disable crash dumps: {e}")
            return

        # Only tear down LocalDumps if we were the ones who created it, and only while
        # nothing else has moved in since.
        if created_parent:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, WER_LOCAL_DUMPS_KEY) as key:
                    subkeys, values, _ = winreg.QueryInfoKey(key)
                if not subkeys and not values:
                    winreg.DeleteKey(winreg.HKEY_LOCAL_MACHINE, WER_LOCAL_DUMPS_KEY)
            except OSError:
                pass

        print("Crash dumps disabled. Existing dump files were left in place.")


class CLITaskHandler:
    """YASB as a scheduled task that starts at logon."""

    def create_task(self):
        scheduler = create_dispatch("Schedule.Service")
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
        principal.UserId = get_current_user_sid()
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
        action.WorkingDirectory = SCRIPT_PATH
        try:
            root_folder.RegisterTaskDefinition("YASB Reborn", task_def, 6, None, None, 3, None)
            print("Task YASB Reborn created successfully.")
        except Exception as e:
            print(f"Failed to create task YASB Reborn. Error: {e}")

    def delete_task(self):
        scheduler = create_dispatch("Schedule.Service")
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
            target_channel: Target channel ('stable' or 'preview')
        """
        update_service = get_update_service()
        current_channel = update_service.current_channel
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

        if target_channel == "preview":
            print("  * Bugs and instability may be present in preview channel")
            print("  * Read the changelog: https://github.com/amnweb/yasb/releases/tag/preview")
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
            if release_info is None:
                print(f"\nError switching channels: no {target_channel} release found.")
                sys.exit(1)
            if target_channel == "preview":
                version_display = f"build {release_info.version.replace('preview-', '')}"
            else:
                version_display = f"version {release_info.version}"
            print(f"Found {Format.magenta}{target_channel}{Format.reset} {version_display}")
            print(f"Installer {release_info.asset_name}")
            if release_info.asset_size:
                print(f"Size {release_info.asset_size / 1024 / 1024:.1f} MB")
            CLIUpdateHandler().install(release_info)

        except Exception as e:
            print(f"\nError switching channels: {e}")
            sys.exit(1)


class CLIUpdateHandler:
    """Handles the update functionality for the command-line interface."""

    def update_yasb(self) -> None:
        """Check for updates and install if available using centralized update service."""
        architecture = get_architecture()
        update_service = get_update_service()

        # Check if updates are supported
        if not update_service.is_update_supported():
            if RELEASE_CHANNEL.startswith("pr-"):
                print("\nAutomatic updates are disabled for PR build.")
            else:
                print("\nUpdates are not supported on this system.")
            if not architecture:
                print("Reason: Unsupported architecture")
            sys.exit(1)

        print("Checking for updates...")
        arch_suffix = f" ({architecture})" if architecture else ""
        print(f"Current version {BUILD_VERSION}{arch_suffix} ({RELEASE_CHANNEL})")

        try:
            release_info = update_service.check_for_updates(timeout=15)

            if release_info is None:
                print(f"YASB Reborn is already up to date (v{BUILD_VERSION}).\n")
                sys.exit(0)

            # Update available
            if update_service.current_channel == "preview":
                print(
                    f"Found {Format.cyan}YASB Reborn{Format.reset} Preview {release_info.version.replace('preview-', '')}"
                )
                print("Changelog https://github.com/amnweb/yasb/releases/tag/preview")
            else:
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

            self.install(release_info)

        except Exception as e:
            print(f"\nFailed to check for updates: {e}")
            sys.exit(1)

    def install(self, release_info: ReleaseInfo) -> NoReturn:
        """Downloads the release's installer, stops YASB and runs the installer, which starts YASB again."""
        msi_path = os.path.join(tempfile.gettempdir(), release_info.asset_name)
        self.download_yasb(release_info.download_url, msi_path)
        _stop_yasb()
        install_command = f'msiexec /i "{os.path.abspath(msi_path)}" /passive /norestart'
        print("Starting installer...")
        subprocess.Popen(f'{install_command} && "{EXE_PATH}"', shell=True)
        sys.exit(0)

    def download_yasb(self, msi_url: str, msi_path: str) -> None:
        """Download a file with progress bar.

        Args:
            msi_url: Download URL
            msi_path: Local file path
        """
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
                bar_length = 30
                print(f"Downloading {Format.magenta}{msi_url}{Format.reset}")
                with open(msi_path, "wb") as file:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        file.write(chunk)
                        downloaded += len(chunk)
                        percent = downloaded / total_length * 100
                        filled = int(bar_length * downloaded / total_length)
                        bar = "\u2588" * filled + "\u2591" * (bar_length - filled)
                        print(f"\r{bar} {percent:.1f}%", end="", flush=True)

                print("\r" + " " * (bar_length + 10) + "\rDownload completed.")

        except KeyboardInterrupt:
            print("\nDownload interrupted by user.")
            sys.exit(0)

        except URLError as e:
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
