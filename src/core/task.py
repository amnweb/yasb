# Create a Task Scheduler task to run the status bar on user logon.
# Command line arguments are used to create, delete, enable, or disable the task.
# example: python task.py create
import argparse
import ctypes
import datetime
import getpass
import os
import shutil
import sys

import win32com.client
import win32security


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def get_current_user_sid():
    username = getpass.getuser()
    domain = os.environ["USERDOMAIN"]
    user, domain, type = win32security.LookupAccountName(None, username)
    sid = win32security.ConvertSidToStringSid(user)
    return sid


def find_pythonw_exe():
    pythonw_path = shutil.which("pythonw.exe")
    if pythonw_path is None:
        ctypes.windll.user32.MessageBoxW(0, "pythonw.exe not found in PATH.", "Error", 0x10)
        sys.exit(1)
    return pythonw_path


def create_logon_task(task_name, script_path, working_directory):
    scheduler = win32com.client.Dispatch("Schedule.Service")
    scheduler.Connect()
    root_folder = scheduler.GetFolder("\\")
    task_def = scheduler.NewTask(0)
    task_def.RegistrationInfo.Description = (
        "A highly configurable cross-platform (Windows) status bar written in Python."
    )
    task_def.RegistrationInfo.Author = "AmN"
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
    pythonw_path = find_pythonw_exe()
    action = task_def.Actions.Create(0)
    action.Path = pythonw_path
    action.Arguments = script_path
    action.WorkingDirectory = working_directory
    try:
        root_folder.RegisterTaskDefinition(task_name, task_def, 6, None, None, 3, None)
        print(f"Task '{task_name}' created successfully.")
    except Exception as e:
        print(f"Failed to create task '{task_name}'. Error: {e}")


def delete_task(task_name):
    scheduler = win32com.client.Dispatch("Schedule.Service")
    scheduler.Connect()
    root_folder = scheduler.GetFolder("\\")
    try:
        root_folder.DeleteTask(task_name, 0)
    except Exception as e:
        message = f"Failed to delete task '{task_name}'. Error: {e}"
        ctypes.windll.user32.MessageBoxW(0, message, "Error", 0x10)
        print(message)


def enable_task(task_name, enable):
    scheduler = win32com.client.Dispatch("Schedule.Service")
    scheduler.Connect()
    root_folder = scheduler.GetFolder("\\")
    try:
        task = root_folder.GetTask(task_name)
        task.Enabled = enable
        status = "enabled" if enable else "disabled"
        print(f"Task '{task_name}' {status} successfully.")
    except Exception as e:
        message = f"Task '{task_name}' does not exist. Error: {e}"
        ctypes.windll.user32.MessageBoxW(0, message, "Error", 0x10)
        print(message)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage Windows Task Scheduler tasks.")
    parser.add_argument(
        "action", choices=["create", "delete", "enable", "disable"], help="Action to perform on the task."
    )
    args = parser.parse_args()
    if not is_admin():
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    else:
        task_name = "YASB"
        script_path = r"src\main.py"
        current_dir = os.path.dirname(os.path.abspath(__file__))
        working_directory = os.path.abspath(os.path.join(current_dir, "..", ".."))
        if args.action == "create":
            create_logon_task(task_name, script_path, working_directory)
        elif args.action == "delete":
            delete_task(task_name)
        elif args.action == "enable":
            enable_task(task_name, True)
        elif args.action == "disable":
            enable_task(task_name, False)
