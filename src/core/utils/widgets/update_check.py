import win32com.client
import subprocess
import threading
import logging
from core.event_service import EventService
from core.config import get_config

class UpdateCheckServiceConfig:
    @staticmethod
    def load_config():       
        try:
            config = get_config(show_error_dialog=True)
        except Exception as e:
            logging.error(f"Error loading config: {e}")
            return None
        
        if 'widgets' in config:
            for widget_name, widget_config in config['widgets'].items():
                if widget_config.get('type') == 'yasb.update_check.UpdateCheckWidget':
                    winget_update_options   = widget_config['options'].get('winget_update', {})
                    windows_update_options  = widget_config['options'].get('windows_update', {})
                    winget_update_enabled   = winget_update_options.get('enabled', False)
                    windows_update_enabled  = windows_update_options.get('enabled', False)
                    winget_update_interval  = int(winget_update_options.get('interval') * 60)
                    windows_update_interval = int(windows_update_options.get('interval') * 60)
                    winget_update_exclude   = winget_update_options.get('exclude',[])
                    windows_update_exclude  = windows_update_options.get('exclude',[])
                    return {
                        'winget_update_enabled': winget_update_enabled,
                        'windows_update_enabled': windows_update_enabled,
                        'winget_update_interval': winget_update_interval,
                        'windows_update_interval': windows_update_interval,
                        'winget_update_exclude': winget_update_exclude,
                        'windows_update_exclude': windows_update_exclude
                    }
        else:
            logging.error("No widgets found in the configuration")
            return None

class UpdateCheckService:
    def __init__(self):
        self.event_service = EventService()
        
        config = UpdateCheckServiceConfig.load_config()
        if config:
            self.winget_update_enabled = config['winget_update_enabled']
            self.windows_update_enabled = config['windows_update_enabled']
            self.winget_update_interval = config['winget_update_interval']
            self.windows_update_interval = config['windows_update_interval']
            self.winget_update_exclude = config['winget_update_exclude']
            self.windows_update_exclude = config['windows_update_exclude']
        else:
            self.winget_update_enabled = False
            self.windows_update_enabled = False
            self.winget_update_interval = 86400
            self.windows_update_interval = 86400
        
    def start(self):
        if self.windows_update_enabled:
            self.start_windows_update_timer()
        if self.winget_update_enabled:
            self.start_winget_update_timer()
        
    def start_windows_update_timer(self):
        thread = threading.Thread(target=self.windows_update_timer_callback)
        thread.daemon = True
        thread.start()

    def start_winget_update_timer(self):
        thread = threading.Thread(target=self.winget_update_timer_callback)
        thread.daemon = True
        thread.start()

    def windows_update_timer_callback(self):
        update_info = self.get_windows_update()
        self.emit_event('windows_update', update_info)
        threading.Timer(self.windows_update_interval, self.windows_update_timer_callback).start()

    def winget_update_timer_callback(self):
        update_info = self.get_winget_update()
        self.emit_event('winget_update', update_info)
        threading.Timer(self.winget_update_interval, self.winget_update_timer_callback).start()
        
    def windows_update_reload(self):
        update_info = self.get_windows_update()
        self.emit_event('windows_update', update_info)

    def winget_update_reload(self):
        update_info = self.get_winget_update()
        self.emit_event('winget_update', update_info)
        
    def emit_event(self, event_name, data):
        self.event_service.emit_event(event_name, data)

    def get_windows_update(self):
        try:
            # Create the Windows Update Session
            update_session = win32com.client.Dispatch("Microsoft.Update.Session")
            update_searcher = update_session.CreateUpdateSearcher()
            # Search for updates that are not installed
            search_result = update_searcher.Search("IsInstalled=0")
            # Check if there are any updates available
            if (count := search_result.Updates.Count) > 0:
                update_names = [update.Title for update in search_result.Updates if update.Title not in self.windows_update_exclude]
                return {"count": count, "names": update_names}
            return {"count": 0, "names": []}
        except Exception as e:
            logging.error(f"Error running windows update: {e}")

    def get_winget_update(self):
        try:
            result = subprocess.run(
                ['winget', 'upgrade'],
                capture_output=True,
                text=True,
                check=True,
                shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            # Split the output into lines
            lines = result.stdout.strip().split('\n')
            # Find the line that starts with "Name", it contains the header
            fl = 0
            while not lines[fl].startswith("Name"):
                fl += 1
            # Line fl has the header, we can find char positions for Id, Version, Available, and Source
            id_start = lines[fl].index("Id")
            version_start = lines[fl].index("Version")
            available_start = lines[fl].index("Available")
            source_start = lines[fl].index("Source")
            # Now cycle through the real packages and split accordingly
            upgrade_list = []
            
            for line in lines[fl + 1:]:
                # Stop processing when reaching the explicit targeting section
                if line.startswith("The following packages have an upgrade available"):
                    break
                if len(line) > (available_start + 1) and not line.startswith('-'):
                    name = line[:id_start].strip()
                    if name in self.winget_update_exclude:
                        continue
                    id = line[id_start:version_start].strip()
                    version = line[version_start:available_start].strip()
                    available = line[available_start:source_start].strip()
                    software = {
                        "name": name,
                        "id": id,
                        "version": version,
                        "available_version": available
                    }
                    upgrade_list.append(software)
                    
            update_names = [f"{software['name']} ({software['id']}): {software['version']} -> {software['available_version']}" for software in upgrade_list]
            count = len(upgrade_list)
            return {"count": count, "names": update_names}
        
        except subprocess.CalledProcessError as e:
            logging.error(f"Error running winget upgrade: {e}")
            return {"count": 0, "names": []}