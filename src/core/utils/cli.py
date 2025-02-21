import argparse
import pywintypes
import win32file
import subprocess
import sys
import logging
import os
import time
import re
import winshell
import psutil
import win32com.client
import datetime
import getpass
import win32security
import ctypes
import requests
import tempfile
from settings import BUILD_VERSION
from colorama import just_fix_windows_console

just_fix_windows_console()

YASB_VERSION = BUILD_VERSION
YASB_CLI_VERSION = "1.0.7"

OS_STARTUP_FOLDER = os.path.join(os.environ['APPDATA'], r'Microsoft\Windows\Start Menu\Programs\Startup')
INSTALLATION_PATH = os.path.abspath(os.path.join(__file__, "../../.."))
EXE_PATH = os.path.join(INSTALLATION_PATH, 'yasb.exe')
SHORTCUT_FILENAME = "yasb.lnk"
AUTOSTART_FILE = EXE_PATH if os.path.exists(EXE_PATH) else None
WORKING_DIRECTORY = INSTALLATION_PATH if os.path.exists(EXE_PATH) else None

def is_process_running(process_name):
    for proc in psutil.process_iter(['name']):
        if proc.info['name'] == process_name:
            return True
    return False
    
class Format:
    end = '\033[0m'
    underline = '\033[4m'
    gray = '\033[90m'
    red = '\033[91m'
    yellow = '\033[93m'
    blue = '\033[94m'
    green = '\033[92m'

def format_log_line(line):
    # Color timestamp
    line = re.sub(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', f"{Format.gray}\\g<0>{Format.end}", line, count=1)
    # Remove filename:line: pattern, generally we don't need this in logs
    line = re.sub(r'\s+\w+\.py:\d+:\s*', ' ', line)
    log_levels = ["CRITICAL", "ERROR", "WARNING", "NOTICE", "INFO", "DEBUG", "TRACE"]
    for level in log_levels:
        if level in line:
            padding = max(8, len(level))
            padded_level = level.rjust(padding)
            if level in ['CRITICAL', 'ERROR']:
                line = line.replace(level, f"{Format.red}{padded_level}{Format.end}")
            elif level == "WARNING":
                line = line.replace(level, f"{Format.yellow}{padded_level}{Format.end}")
            elif level == "NOTICE":
                line = line.replace(level, f"{Format.green}{padded_level}{Format.end}")
            elif level == "TRACE":
                line = line.replace(level, f"{Format.blue}{padded_level}{Format.end}")
            elif level == "INFO":
                line = line.replace(level, f"{Format.green}{padded_level}{Format.end}")
            elif level == "DEBUG":
                line = line.replace(level, f"{Format.green}{padded_level}{Format.end}")
            else:
                line = line.replace(level, padded_level)
            break
    return line

class CustomArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        print(f'\n{Format.red}Error:{Format.end} {message}\n')
        sys.exit(2)

class CLIHandler:

    def stop_or_reload_application(reload=False):
        pipe_name = r'\\.\pipe\yasb_pipe_cli'
        try:
            pipe_handle = win32file.CreateFile(
                pipe_name,
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0,
                None,
                win32file.OPEN_EXISTING,
                0,
                None
            )
            cmd = b'reload' if reload else b'stop'
            win32file.WriteFile(pipe_handle, cmd)
            _, response = win32file.ReadFile(pipe_handle, 64 * 1024)
            if response.decode('utf-8').strip() != 'ACK':
                print(f"Received unexpected response: {response.decode('utf-8').strip()}")
            win32file.CloseHandle(pipe_handle)
        except pywintypes.error as e:
            # ERROR_FILE_NOT_FOUND can indicate the pipe doesn't exist
            if e.args[0] == 2:
                print("Failed to connect to YASB. Pipe not found. It may not be running.")
            else:
                print(f"Pipe error: {e}")
        except Exception as e:
            print(f"Error: {e}")

    def _enable_startup():
        shortcut_path = os.path.join(OS_STARTUP_FOLDER, SHORTCUT_FILENAME)
        try:
            with winshell.shortcut(shortcut_path) as shortcut:
                shortcut.path = AUTOSTART_FILE
                shortcut.working_directory = WORKING_DIRECTORY
                shortcut.description = "Shortcut to yasb.exe"
            logging.info(f"Created shortcut at {shortcut_path}")
            print(f"Created shortcut at {shortcut_path}")
        except Exception as e:
            logging.error(f"Failed to create startup shortcut: {e}")
            print(f"Failed to create startup shortcut: {e}")
        
    def _disable_startup():
        shortcut_path = os.path.join(OS_STARTUP_FOLDER, SHORTCUT_FILENAME)
        if os.path.exists(shortcut_path):
            try:
                os.remove(shortcut_path)
                logging.info(f"Removed shortcut from {shortcut_path}")
                print(f"Removed shortcut from {shortcut_path}")
            except Exception as e:
                logging.error(f"Failed to remove startup shortcut: {e}")
                print(f"Failed to remove startup shortcut: {e}")
        
        
    def parse_arguments():
        parser = CustomArgumentParser(description="The command-line interface for YASB Reborn.", add_help=False)
        subparsers = parser.add_subparsers(dest='command', help='Commands')

        subparsers.add_parser('start', help='Start the application')
        subparsers.add_parser('stop', help='Stop the application')
        subparsers.add_parser('reload', help='Reload the application')
        subparsers.add_parser('update', help='Update the application')
        
        enable_autostart_parser = subparsers.add_parser('enable-autostart', help='Enable autostart on system boot')
        enable_autostart_parser.add_argument('--task', action='store_true', help='Enable autostart as a scheduled task')
        
        disable_autostart_parser = subparsers.add_parser('disable-autostart', help='Disable autostart on system boot')
        disable_autostart_parser.add_argument('--task', action='store_true', help='Disable autostart as a scheduled task')
        
        subparsers.add_parser('help', help='Show help message')
        subparsers.add_parser('log', help='Tail yasb process logs (cancel with Ctrl-C)')
        parser.add_argument('-v', '--version', action='store_true', help="Show program's version number and exit.")
        parser.add_argument('-h', '--help', action='store_true', help='Show help message')
        args = parser.parse_args()
 
        if args.command == 'start':
            print("Start YASB in background...")
            subprocess.Popen(["yasb.exe"])
            sys.exit(0)
            
        elif args.command == 'stop':
            print("Stop YASB...")
            CLIHandler.stop_or_reload_application()
            sys.exit(0)
            
        elif args.command == 'reload':
            if is_process_running("yasb.exe"):
                print("Reload YASB...")
                CLIHandler.stop_or_reload_application(reload=True)
            else:
                print("YASB is not running. Reload aborted.")
            sys.exit(0)
        elif args.command == 'update':
            CLIUpdateHandler.update_yasb(YASB_VERSION)
            sys.exit(0)
            
        elif args.command == 'enable-autostart':
            if args.task:
                if not CLITaskHandler.is_admin():
                    print("Please run this command as an administrator.")
                else:
                    CLITaskHandler.create_task()
            else:
                CLIHandler._enable_startup()
            sys.exit(0)
        
        elif args.command == 'disable-autostart':
            if args.task:
                if not CLITaskHandler.is_admin():
                    print("Please run this command as an administrator.")
                else:
                    CLITaskHandler.delete_task()
            else:
                CLIHandler._disable_startup()
            sys.exit(0)    
            
        elif args.command == 'log':
            config_home = os.getenv('YASB_CONFIG_HOME') if os.getenv('YASB_CONFIG_HOME') else os.path.join(os.path.expanduser("~"), ".config", "yasb")
            log_file = os.path.join(config_home, "yasb.log")
            if not os.path.exists(log_file):
                print("Log file does not exist. Please restart YASB to generate logs.")
                sys.exit(1)
            try:
                with open(log_file, 'r') as f:
                    f.seek(0, os.SEEK_END)
                    while True:
                        line = f.readline()
                        if not line:
                            time.sleep(0.1)
                            continue
                        formatted_line = format_log_line(line)
                        print(formatted_line, end='')
            except KeyboardInterrupt:
                pass
            sys.exit(0)
            
        elif args.command == 'help' or args.help:
            print("The command-line interface for YASB Reborn.")
            print('\n' + Format.underline + 'Usage' + Format.end + ': yasbc <COMMAND>')
            print('\n' + Format.underline + 'Commands' + Format.end + ':')
            print("  start              Start the application")
            print("  stop               Stop the application")
            print("  reload             Reload the application")
            print("  enable-autostart   Enable autostart on system boot")
            print("  disable-autostart  Disable autostart on system boot")
            print("  update             Update the application")
            print("  log                Tail yasb process logs (cancel with Ctrl-C)")
            print("  help               Print this message")
            print('\n' + Format.underline + 'Options' + Format.end + ':')
            print("-v, --version  Print version")
            print("-h, --help     Print this message")
            sys.exit(0)
            
        elif args.version:
            version_message = f"YASB Reborn v{YASB_VERSION}\nYASB-CLI v{YASB_CLI_VERSION}"
            print(version_message)
        else:
            logging.info("Unknown command. Use --help for available options.")
            sys.exit(1)



class CLITaskHandler:
    
    def is_admin():
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False

    def get_current_user_sid():
        username = getpass.getuser()
        domain = os.environ['USERDOMAIN']
        user, domain, type = win32security.LookupAccountName(None, username)
        sid = win32security.ConvertSidToStringSid(user)
        return sid
    
    def create_task():
        scheduler = win32com.client.Dispatch('Schedule.Service')
        scheduler.Connect()
        root_folder = scheduler.GetFolder('\\')
        task_def = scheduler.NewTask(0)
        task_def.RegistrationInfo.Description = 'A highly configurable Windows status bar.'
        task_def.RegistrationInfo.Author = "AmN"
        task_def.Settings.Compatibility = 6
        trigger = task_def.Triggers.Create(9)
        trigger.Enabled = True
        trigger.StartBoundary = datetime.datetime.now().isoformat()
        principal = task_def.Principal
        principal.UserId = CLITaskHandler.get_current_user_sid()
        principal.LogonType = 3
        principal.RunLevel = 0
        settings = task_def.Settings
        settings.Enabled = True
        settings.StartWhenAvailable = True
        settings.AllowHardTerminate = True
        settings.ExecutionTimeLimit = 'PT0S'
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
            root_folder.RegisterTaskDefinition(
                'YASB Reborn',
                task_def,
                6,
                None,
                None,
                3,
                None
            )
            print(f"Task YASB Reborn created successfully.")
        except Exception as e:
            print(f"Failed to create task YASB Reborn. Error: {e}")
        
    def delete_task():
        scheduler = win32com.client.Dispatch('Schedule.Service')
        scheduler.Connect()
        root_folder = scheduler.GetFolder('\\')
        try:
            root_folder.DeleteTask('YASB Reborn', 0)
            print(f"Task YASB Reborn deleted successfully.")
        except Exception:
            print(f"Failed to delete task YASB or task does not exist.")
        
class CLIUpdateHandler():

    def get_installed_product_code():
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
    
    def update_yasb(YASB_VERSION):
        # Fetch the latest tag from the GitHub API
        api_url = f"https://api.github.com/repos/amnweb/yasb/releases/latest"
        response = requests.get(api_url)
        latest_release = response.json()
        tag = latest_release['tag_name'].lstrip('v')
        changelog = "https://github.com/amnweb/yasb/releases/latest"
        # Step 2: Generate the download link based on the latest tag
        msi_url = f"https://github.com/amnweb/yasb/releases/download/v{tag}/yasb-{tag}-win64.msi"
        temp_dir = tempfile.gettempdir()
        msi_path = os.path.join(temp_dir, f"yasb-{tag}-win64.msi")
        if tag <= YASB_VERSION:
            print("\nYASB Reborn is already up to date.\n")
            sys.exit(0)
        print(f"\nYASB Reborn version " + Format.underline + f"{tag}" + Format.end + " is available.")
        print(f"\nChangelog {changelog}")
        # Ask the user if they want to continue with the update
        try:
            user_input = input("\nDo you want to continue with the update? (Y/n): ").strip().lower()
            if user_input not in ['y', 'yes', '']:
                print("\nUpdate canceled.")
                sys.exit(0)
        except KeyboardInterrupt:
            print("\nUpdate canceled.")
            sys.exit(0)
        # Step 3: Download the latest MSI file
        try:
            response = requests.get(msi_url, stream=True)
            total_length = int(response.headers.get('content-length'))
            downloaded = 0
            chunk_size = 4096
            with open(msi_path, "wb") as file:
                for data in response.iter_content(chunk_size=chunk_size):
                    file.write(data)
                    downloaded += len(data)
                    print(f"\rDownloading {downloaded / total_length * 100:.1f}%", end='')
            print("\rDownload completed.          ")
        except KeyboardInterrupt:
            print("\nDownload interrupted by user.")
            sys.exit(0)
            
        # Verify the downloaded file size
        downloaded_size = os.path.getsize(msi_path)
        if downloaded_size != total_length:
            print("Error: Downloaded file size does not match expected size.")
            sys.exit(0)
        # Step 4: Run the MSI installer in silent mode and restart the application
        if is_process_running("yasb.exe"):
            subprocess.run(["taskkill", "/f", "/im", "yasb.exe"], creationflags=subprocess.CREATE_NO_WINDOW)
        if is_process_running("yasb_themes.exe"):
            subprocess.run(["taskkill", "/f", "/im", "yasb_themes.exe"], creationflags=subprocess.CREATE_NO_WINDOW)

        # Construct the uninstall command as a string
        # product_code = CLIUpdateHandler.get_installed_product_code()
        # if product_code is not None:
        #     uninstall_command = f'msiexec /x {product_code} /passive'
        # else:
        #     uninstall_command = ""
            
        # Construct the install command as a string
        install_command = f'msiexec /i "{os.path.abspath(msi_path)}" /passive /norestart'
        run_after_command = f'"{EXE_PATH}"'
        #combined_command = f'{uninstall_command} && {install_command} && {run_after_command}'
        combined_command = f'{install_command} && {run_after_command}'
        # Finally run update and restart the application
        subprocess.Popen(combined_command, shell=True)
        sys.exit(0)
    
if __name__ == "__main__":
    CLIHandler.parse_arguments()
    sys.exit(0)