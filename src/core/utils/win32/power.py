import subprocess
import win32api
import win32security
from PyQt6.QtCore import QCoreApplication
import ctypes

class PowerOperations:
    def __init__(self, main_window, overlay):
        self.main_window = main_window
        self.overlay = overlay
        
    def signout(self):
        self.main_window.hide()
        self.overlay.hide()
        QCoreApplication.exit(0)
        subprocess.Popen("shutdown /l", stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=True)

    def lock(self):
        self.main_window.hide()
        self.overlay.hide()
        subprocess.Popen("rundll32.exe user32.dll,LockWorkStation", stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=True)

    def sleep(self):
        self.main_window.hide()
        self.overlay.hide()
        access = (win32security.TOKEN_ADJUST_PRIVILEGES | win32security.TOKEN_QUERY)
        htoken = win32security.OpenProcessToken(win32api.GetCurrentProcess(), access)
        if htoken:
            priv_id = win32security.LookupPrivilegeValue(None, win32security.SE_SHUTDOWN_NAME)
            win32security.AdjustTokenPrivileges(htoken, 0,
                [(priv_id, win32security.SE_PRIVILEGE_ENABLED)])
            ctypes.windll.powrprof.SetSuspendState(False, True, False)
            win32api.CloseHandle(htoken)

    def restart(self):
        self.main_window.hide()
        self.overlay.hide()
        QCoreApplication.exit(0)
        subprocess.Popen("shutdown /r /t 0", stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=True)

    def shutdown(self):
        self.main_window.hide()
        self.overlay.hide()
        QCoreApplication.exit(0)
        subprocess.Popen("shutdown /s /hybrid /t 0", stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=True)

    def force_shutdown(self):
        self.main_window.hide()
        self.overlay.hide()
        QCoreApplication.exit(0)
        subprocess.Popen("shutdown /s /f /t 0", stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=True)

    def force_restart(self):
        self.main_window.hide()
        self.overlay.hide()
        QCoreApplication.exit(0)
        subprocess.Popen("shutdown /r /f /t 0", stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=True)
    
    def hibernate(self):
        self.main_window.hide()
        self.overlay.hide()
        subprocess.Popen("shutdown /h", stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=True)

    def cancel(self):
        if hasattr(self.overlay, 'timer'):
            self.overlay.timer.stop()
        if self.overlay:
            self.overlay.fade_out()
        self.main_window.fade_out()

