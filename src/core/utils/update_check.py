import json
import logging
import threading
import time
import urllib.request

from core.utils.utilities import ToastNotifier, app_data_path
from settings import BUILD_VERSION, SCRIPT_PATH

LAST_CHECK_FILE = app_data_path("last_update_check")
CHECK_INTERVAL = 30 * 60  # 30 minutes


class UpdateCheckService:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._initialized = True
        self.current_version = BUILD_VERSION
        self.icon_path = f"{SCRIPT_PATH}/assets/images/app_transparent.png"
        threading.Thread(target=self.check_for_update, daemon=True).start()

    def check_for_update(self):
        if not self.should_check():
            return
        try:
            url = "https://api.github.com/repos/amnweb/yasb/releases/latest"
            with urllib.request.urlopen(url, timeout=10) as response:
                data = response.read()
                release_info = json.loads(data)
                latest_version = release_info["tag_name"].lstrip("v")
            if latest_version != self.current_version:
                toaster = ToastNotifier()
                toaster.show(
                    icon_path=self.icon_path,
                    title="Update Available",
                    message=f"New version {latest_version} is available!",
                    launch_url="https://github.com/amnweb/yasb/releases/latest",
                    scenario="reminder",
                )
            self.update_last_check()
        except urllib.error.URLError:
            logging.warning("UpdateCheckService Failed to check for updates: Network error.")
        except Exception as e:
            logging.warning(f"UpdateCheckService Failed to check for updates: {e}")

    def should_check(self):
        try:
            if LAST_CHECK_FILE.exists():
                last_check = float(LAST_CHECK_FILE.read_text().strip())
                if time.time() - last_check < CHECK_INTERVAL:
                    return False
        except Exception:
            pass
        return True

    def update_last_check(self):
        try:
            LAST_CHECK_FILE.write_text(str(time.time()))
        except Exception:
            pass
