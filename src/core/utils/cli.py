import argparse
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
from settings import BUILD_VERSION
from colorama import just_fix_windows_console
just_fix_windows_console()

# Check if exe file exists
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
    line = re.sub(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', f"{Format.gray}\\g<0>{Format.end}", line, count=1)
    
    log_levels = ["CRITICAL", "ERROR", "WARNING", "NOTICE", "INFO", "DEBUG", "TRACE"]
    for level in log_levels:
        if level in line:
            padded_level = level.ljust(8)
            if level in ['CRITICAL', 'ERROR']:
                line = line.replace(level, f"{Format.red}{padded_level}{Format.end}")
            elif level == "WARNING":
                line = line.replace(level, f"{Format.yellow}{padded_level}{Format.end}")
            elif level == "NOTICE":
                line = line.replace(level, f"{Format.green}{padded_level}{Format.end}")
            elif level == "TRACE":
                line = line.replace(level, f"{Format.blue}{padded_level}{Format.end}")
            else:
                line = line.replace(level, padded_level)
            break
    return line

class CustomArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        print(f'\n{Format.red}Error:{Format.end} {message}\n')
        sys.exit(2)

class CLIHandler:
        
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
        
        enable_autostart_parser = subparsers.add_parser('enable-autostart', help='Enable autostart on system boot')
        enable_autostart_parser.add_argument('--task', action='store_true', help='Enable autostart as a scheduled task')
        
        disable_autostart_parser = subparsers.add_parser('disable-autostart', help='Disable autostart on system boot')
        disable_autostart_parser.add_argument('--task', action='store_true', help='Disable autostart as a scheduled task')
        
        subparsers.add_parser('help', help='Show help message')
        subparsers.add_parser('log', help='Tail yasb process logs (cancel with Ctrl-C)')
        parser.add_argument('-v', '--version', action='version', version=f'YASB Reborn v{BUILD_VERSION}', help="Show program's version number and exit.")
        parser.add_argument('-h', '--help', action='store_true', help='Show help message')
        args = parser.parse_args()
 
        if args.command == 'start':
            print("Start YASB in background...")
            subprocess.Popen(["yasb.exe"])
            sys.exit(0)
            
        elif args.command == 'stop':
            print("Stop YASB...")
            subprocess.run(["taskkill", "/f", "/im", "yasb.exe"], creationflags=subprocess.CREATE_NO_WINDOW)
            sys.exit(0)
            
        elif args.command == 'reload':
            if is_process_running("yasb.exe"):
                print("Reload YASB...")
                subprocess.run(["taskkill", "/f", "/im", "yasb.exe"], creationflags=subprocess.CREATE_NO_WINDOW)
                subprocess.Popen(["yasb.exe"])
            else:
                print("YASB is not running. Reload aborted.")
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
            log_file = os.path.join(os.path.expanduser("~"), ".config", "yasb", "yasb.log")
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
            print("  log                Tail yasb process logs (cancel with Ctrl-C)")
            print("  help               Print this message")
            print('\n' + Format.underline + 'Options' + Format.end + ':')
            print("  --version  Print version")
            print("  --help     Print this message")
            sys.exit(0)

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
        
    
if __name__ == "__main__":
    CLIHandler.parse_arguments()
    sys.exit(0)