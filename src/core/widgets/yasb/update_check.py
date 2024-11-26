import logging
import re
import shutil
import subprocess
import threading
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.update_check import VALIDATION_SCHEMA
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QWidget
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import win32com.client
import subprocess
import logging

class UpdateWorker(QThread):
    windows_update_signal = pyqtSignal(dict)
    winget_update_signal = pyqtSignal(dict)
    
    def __init__(self, update_type, parent=None):
        super().__init__(parent)
        self.update_type = update_type
        self.running = True

    def stop(self):
        self.running = False
        self.wait()

    def run(self):
        try:
            if self.update_type == 'windows':
                update_session = win32com.client.Dispatch("Microsoft.Update.Session")
                update_searcher = update_session.CreateUpdateSearcher()
                search_result = update_searcher.Search("IsInstalled=0")
                count = search_result.Updates.Count
                update_names = [update.Title for update in search_result.Updates]
                self.windows_update_signal.emit({"count": count, "names": update_names})
                
            elif self.update_type == 'winget':
                result = subprocess.run(
                    ['winget', 'upgrade'],
                    capture_output=True,
                    text=True,
                    check=True,
                    shell=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                
                lines = result.stdout.strip().split('\n')
                fl = 0
                while not lines[fl].startswith("Name"):
                    fl += 1
                    
                id_start = lines[fl].index("Id")
                version_start = lines[fl].index("Version")
                available_start = lines[fl].index("Available")
                source_start = lines[fl].index("Source")
                
                upgrade_list = []
                for line in lines[fl + 1:]:
                    if line.startswith("The following packages have an upgrade available"):
                        break
                    if len(line) > (available_start + 1) and not line.startswith('-'):
                        name = line[:id_start].strip()
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
                
                update_names = [
                    f"{software['name']} ({software['id']}): {software['version']} -> {software['available_version']}" 
                    for software in upgrade_list
                ]
                
                self.winget_update_signal.emit({
                    "count": len(upgrade_list), 
                    "names": update_names
                })
                
        except Exception as e:
            logging.error(f"Error in {self.update_type} worker: {e}")
            if self.update_type == 'windows':
                self.windows_update_signal.emit({"count": 0, "names": []})
            else:
                self.winget_update_signal.emit({"count": 0, "names": []})

class UpdateCheckWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    TOOLTIP_STYLE = """QToolTip { padding:4px;color: #cdd6f4;font-size:12px; background-color: #1e1e2e; border: 1px solid #313244; }"""

    def __init__(self, windows_update: dict[str, str], winget_update: dict[str, str]):
        super().__init__(class_name="update-check-widget")

        self._windows_update = windows_update
        self._winget_update = winget_update

        self._window_update_enabled = self._windows_update['enabled']
        self._windows_update_label = self._windows_update['label']
        self._window_update_interval = int(self._windows_update['interval'] * 60)
        self._windows_update_exclude = self._windows_update['exclude']

        self._winget_update_enabled = self._winget_update['enabled']
        self._winget_update_label = self._winget_update['label']
        self._winget_update_interval = int(self._winget_update['interval'] * 60)
        self._winget_update_exclude = self._winget_update['exclude']
        
        self.windows_update_data = 0
        self.winget_update_data = 0

        self._create_dynamically_label(self._winget_update_label, self._windows_update_label)

        self._stop_event = threading.Event()

        self.windows_worker = None
        self.winget_worker = None
        
        if self._window_update_enabled:
            self.start_windows_update_timer()
        if self._winget_update_enabled:
            self.start_winget_update_timer()

        self.update_widget_visibility()


    def start_windows_update_timer(self):
        self.windows_worker = UpdateWorker('windows')
        self.windows_worker.windows_update_signal.connect(
            lambda x: self.emit_event('windows_update', x)
        )
        self.windows_worker.start()


    def start_winget_update_timer(self):
        self.winget_worker = UpdateWorker('winget')
        self.winget_worker.winget_update_signal.connect(
            lambda x: self.emit_event('winget_update', x)
        )
        self.winget_worker.start()


    def emit_event(self, event_type, update_info):
        if event_type == 'windows_update':
            self.windows_update_data = update_info['count']
            self._update_label('windows', update_info['count'], update_info['names'])
        elif event_type == 'winget_update':
            self.winget_update_data = update_info['count']
            self._update_label('winget', update_info['count'], update_info['names'])
        self.update_widget_visibility()


    def _create_dynamically_label(self, windows_label: str, winget_label: str):
        def process_content(label_text, label_type):
            container = QWidget()
            container_layout = QHBoxLayout()
            container_layout.setSpacing(0)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container.setLayout(container_layout)
            class_name = "windows" if label_type == "windows" else "winget"
            container.setProperty("class", f"widget-container {class_name}")
            self.widget_layout.addWidget(container)
            container.hide()
            label_parts = re.split(r'(<span.*?>.*?</span>)', label_text)
            label_parts = [part for part in label_parts if part]
            widgets = []

            for part in label_parts:
                part = part.strip()
                if not part:
                    continue
                if '<span' in part and '</span>' in part:
                    class_name = re.search(r'class=(["\'])([^"\']+?)\1', part)
                    class_result = class_name.group(2) if class_name else 'icon'
                    icon = re.sub(r'<span.*?>|</span>', '', part).strip()
                    label = QLabel(icon)
                    label.setProperty("class", class_result)
                else:
                    label = QLabel(part)
                    label.setProperty("class", "label")

                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                container_layout.addWidget(label)
                widgets.append(label)
                label.mousePressEvent = self.handle_mouse_events(label_type)
            return container, widgets

        if self._winget_update_enabled:
            self._winget_container, self._widget_widget = process_content(self._winget_update_label, "winget")
        if self._window_update_enabled:
            self._windows_container, self._widget_windows = process_content(self._windows_update_label, "windows")


    def _update_label(self, widget_type, data, names):
        if widget_type == 'winget':
            active_widgets = self._widget_widget
            active_label_content = self._winget_update_label
            container = self._winget_container
        elif widget_type == 'windows':
            active_widgets = self._widget_windows
            active_label_content = self._windows_update_label
            container = self._windows_container
        else:
            return

        label_parts = re.split(r'(<span.*?>.*?</span>)', active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0
        if data == 0:
            container.hide()
            return
        container.show()
        for part in label_parts:
            part = part.strip()
            if part and widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                if '<span' in part and '</span>' in part:
                    icon = re.sub(r'<span.*?>|</span>', '', part).strip()
                    active_widgets[widget_index].setText(icon)
                else:
                    formatted_text = part.format(count=data)
                    active_widgets[widget_index].setText(formatted_text)
                active_widgets[widget_index].setToolTip("\n".join(names))
                active_widgets[widget_index].setStyleSheet(self.TOOLTIP_STYLE)
                widget_index += 1


    def reload_widget(self, widget_type, event=None):
        self.hide_container(widget_type)
        if widget_type == 'windows':
            if self.windows_worker:
                self.windows_worker.stop()
            self.start_windows_update_timer()
        elif widget_type == 'winget':
            if self.winget_worker:
                self.winget_worker.stop()
            self.start_winget_update_timer()


    def open_console(self, event=None):
        powershell_path = shutil.which('pwsh') or shutil.which('powershell') or 'powershell.exe'
        command = f'start "Winget Upgrade" "{powershell_path}" -NoExit -Command "winget upgrade --all"'
        subprocess.Popen(command, shell=True)
        self.hide_container('winget')


    def open_windows_update(self, event=None):
        subprocess.Popen('start ms-settings:windowsupdate', shell=True)
        self.hide_container('windows')


    def handle_mouse_events(self, label_type):
        def event_handler(event):
            if event.button() == Qt.MouseButton.LeftButton:
                if label_type == 'windows':
                    self.open_windows_update(event)
                elif label_type == 'winget':
                    self.open_console(event)
            elif event.button() == Qt.MouseButton.RightButton:
                self.reload_widget(label_type, event)
        return event_handler


    def hide_container(self, container):
        if container == 'windows':
            self.windows_update_data = 0
            self._update_label('windows', 0, [])
        elif container == 'winget':
            self.winget_update_data = 0
            self._update_label('winget', 0, [])
        self.update_widget_visibility()


    def update_widget_visibility(self):
        if self.windows_update_data == 0 and self.winget_update_data == 0:
            self.hide()
        else:
            self.show()

    # def get_windows_update(self):
    #     try:
    #         # Create the Windows Update Session
    #         update_session = win32com.client.Dispatch("Microsoft.Update.Session")
    #         update_searcher = update_session.CreateUpdateSearcher()
    #         # Search for updates that are not installed
    #         search_result = update_searcher.Search("IsInstalled=0")
    #         # Check if there are any updates available
    #         if (count := search_result.Updates.Count) > 0:
    #             update_names = [update.Title for update in search_result.Updates if update.Title not in self._windows_update_exclude]
    #             return {"count": count, "names": update_names}
    #         return {"count": 0, "names": []}
    #     except win32com.client.pywintypes.com_error:
    #         logging.error("No internet connection. Unable to check for Windows updates.")
    #         return {"count": 0, "names": []}
    #     except Exception as e:
    #         logging.error(f"Error running windows update: {e}")
    #         return {"count": 0, "names": []}

    # def get_winget_update(self):
    #     try:
    #         result = subprocess.run(
    #             ['winget', 'upgrade'],
    #             capture_output=True,
    #             text=True,
    #             check=True,
    #             shell=True,
    #             creationflags=subprocess.CREATE_NO_WINDOW
    #         )
    #         # Split the output into lines
    #         lines = result.stdout.strip().split('\n')
    #         # Find the line that starts with "Name", it contains the header
    #         fl = 0
    #         while not lines[fl].startswith("Name"):
    #             fl += 1
    #         # Line fl has the header, we can find char positions for Id, Version, Available, and Source
    #         id_start = lines[fl].index("Id")
    #         version_start = lines[fl].index("Version")
    #         available_start = lines[fl].index("Available")
    #         source_start = lines[fl].index("Source")
    #         # Now cycle through the real packages and split accordingly
    #         upgrade_list = []
            
    #         for line in lines[fl + 1:]:
    #             # Stop processing when reaching the explicit targeting section
    #             if line.startswith("The following packages have an upgrade available"):
    #                 break
    #             if len(line) > (available_start + 1) and not line.startswith('-'):
    #                 name = line[:id_start].strip()
    #                 if name in self._winget_update_exclude:
    #                     continue
    #                 id = line[id_start:version_start].strip()
    #                 version = line[version_start:available_start].strip()
    #                 available = line[available_start:source_start].strip()
    #                 software = {
    #                     "name": name,
    #                     "id": id,
    #                     "version": version,
    #                     "available_version": available
    #                 }
    #                 upgrade_list.append(software)
                    
    #         update_names = [f"{software['name']} ({software['id']}): {software['version']} -> {software['available_version']}" for software in upgrade_list]
    #         count = len(upgrade_list)
    #         return {"count": count, "names": update_names}
    #     except OSError:
    #         logging.error("No internet connection. Unable to check for winget updates.")
    #         return {"count": 0, "names": []}
    #     except subprocess.CalledProcessError as e:
    #         logging.error(f"Error running winget upgrade: {e}")
    #         return {"count": 0, "names": []}
    #     except Exception as e:
    #         logging.error(f"Unexpected error: {e}")
    #         return {"count": 0, "names": []}

    def stop_updates(self):
        if self.windows_worker:
            self.windows_worker.stop()
        if self.winget_worker:
            self.winget_worker.stop()