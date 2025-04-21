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
from core.utils.utilities import add_shadow
from settings import DEBUG

class UpdateWorker(QThread):
    windows_update_signal = pyqtSignal(dict)
    winget_update_signal = pyqtSignal(dict)
    
    def __init__(self, update_type, exclude_list=None, parent=None):
        super().__init__(parent)
        self.update_type = update_type
        self.running = True
        self.exclude_list = exclude_list or []

    def filter_updates(self, updates, names):
        if not self.exclude_list:
            return len(updates), names
 
        valid_excludes = [x.lower() for x in self.exclude_list if x and x.strip()]
        filtered_names = []
        filtered_count = 0
        
        for name in names:
            if not any(excluded in name.lower() for excluded in valid_excludes):
                filtered_names.append(name)
                filtered_count += 1
                
        return filtered_count, filtered_names
    
    def stop(self):
        self.running = False
        self.wait()

    def run(self):
        try:
            if self.update_type == 'windows':
                update_session = win32com.client.Dispatch("Microsoft.Update.Session")
                update_searcher = update_session.CreateUpdateSearcher()
                search_result = update_searcher.Search("IsInstalled=0")
                update_names = [update.Title for update in search_result.Updates]
                count, filtered_names = self.filter_updates(search_result.Updates, update_names)
                self.windows_update_signal.emit({"count": count, "names": filtered_names})
                
            elif self.update_type == 'winget':
                result = subprocess.run(
                    ['winget', 'upgrade'],
                    capture_output=True,
                    encoding='utf-8',
                    text=True,
                    check=True,
                    shell=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                
                lines = result.stdout.strip().split('\n')
                fl = 0
                while fl < len(lines) and not lines[fl].startswith("Name"):
                    fl += 1
                
                if fl >= len(lines):
                    if DEBUG:
                        logging.warning("Invalid winget output format.")
                    self.winget_update_signal.emit({"count": 0, "names": []})
                    return
                
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
                count, filtered_names = self.filter_updates(upgrade_list, update_names)
                self.winget_update_signal.emit({
                    "count": count, 
                    "names": filtered_names
                })
                
        except Exception as e:
            logging.error(f"Error in {self.update_type} worker: {e}")
            if self.update_type == 'windows':
                self.windows_update_signal.emit({"count": 0, "names": []})
            else:
                self.winget_update_signal.emit({"count": 0, "names": []})

class UpdateManager:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._workers = {}
                cls._instance._subscribers = []
            return cls._instance
    
    def register_subscriber(self, callback):
        if callback not in self._subscribers:
            self._subscribers.append(callback)
            
    def unregister_subscriber(self, callback):
        if callback in self._subscribers:
            self._subscribers.remove(callback)
            
    def notify_subscribers(self, event_type, data):
        for subscriber in self._subscribers:
            subscriber(event_type, data)
            
    def start_worker(self, update_type, exclude_list=None):
        if update_type not in self._workers:
            worker = UpdateWorker(update_type, exclude_list)
            if update_type == 'windows':
                worker.windows_update_signal.connect(
                    lambda x: self.notify_subscribers('windows_update', x)
                )
            else:
                worker.winget_update_signal.connect(
                    lambda x: self.notify_subscribers('winget_update', x)
                )
            self._workers[update_type] = worker
            worker.start()
            
    def stop_all(self):
        for worker in self._workers.values():
            worker.stop()
        self._workers.clear()

    def handle_left_click(self, label_type):
        if label_type == 'windows':
            subprocess.Popen('start ms-settings:windowsupdate', shell=True)
        elif label_type == 'winget':
            powershell_path = shutil.which('pwsh') or shutil.which('powershell') or 'powershell.exe'
            command = f'start "Winget Upgrade" "{powershell_path}" -NoExit -Command "winget upgrade --all"'
            subprocess.Popen(command, shell=True)
        # Notify all subscribers to hide the container
        self.notify_subscribers(f'{label_type}_hide', {})

    def handle_right_click(self, label_type):
        # Stop existing worker if running
        if label_type in self._workers:
            self._workers[label_type].stop()
            del self._workers[label_type]
        # Get correct exclude list based on type
        exclude_list = []
        for subscriber in self._subscribers:
            if label_type == 'windows' and hasattr(subscriber, '_windows_update_exclude'):
                exclude_list.extend(subscriber._windows_update_exclude)
            elif label_type == 'winget' and hasattr(subscriber, '_winget_update_exclude'):
                exclude_list.extend(subscriber._winget_update_exclude)
        
        # Hide the container first
        self.notify_subscribers(f'{label_type}_hide', {})
        # Start new worker
        self.start_worker(label_type, exclude_list)

class UpdateCheckWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
            self,
            windows_update: dict[str, str],
            winget_update: dict[str, str],
            label_shadow: dict = None,
            container_shadow: dict = None
        ):
        super().__init__(class_name="update-check-widget")

        self._windows_update = windows_update
        self._winget_update = winget_update

        self._windows_update_tooltip = self._windows_update['tooltip']
        self._winget_update_tooltip = self._winget_update['tooltip']
        
        self._window_update_enabled = self._windows_update.get('enabled', False)
        self._windows_update_label = self._windows_update.get('label', '')
        self._windows_update_exclude = self._windows_update.get('exclude', [])

        self._winget_update_enabled = self._winget_update.get('enabled', False)
        self._winget_update_label = self._winget_update.get('label', '')
        self._winget_update_exclude = self._winget_update.get('exclude', [])
        
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow

        self.windows_update_data = 0
        self.winget_update_data = 0

        self._create_dynamically_label(self._winget_update_label, self._windows_update_label)

        self._update_manager = UpdateManager()
        self._update_manager.register_subscriber(self.emit_event)
        
        if self._window_update_enabled:
            self._update_manager.start_worker('windows', self._windows_update_exclude)
        if self._winget_update_enabled:
            self._update_manager.start_worker('winget', self._winget_update_exclude)

        self.update_widget_visibility()

    def emit_event(self, event_type, update_info):
        if event_type == 'windows_update':
            self.windows_update_data = update_info['count']
            self._update_label('windows', update_info['count'], update_info['names'])
        elif event_type == 'winget_update':
            self.winget_update_data = update_info['count']
            self._update_label('winget', update_info['count'], update_info['names'])
        elif event_type == 'windows_hide':
            self.hide_container('windows')
        elif event_type == 'winget_hide':
            self.hide_container('winget')
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
            add_shadow(container, self._container_shadow)
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
                    class_match = re.search(r'class=(["\'])([^"\']+?)\1', part)
                    class_result = class_match.group(2) if class_match else 'icon'
                    icon = re.sub(r'<span.*?>|</span>', '', part).strip()
                    label = QLabel(icon)
                    label.setProperty("class", class_result)
                else:
                    label = QLabel(part)
                    label.setProperty("class", "label")
                add_shadow(label, self._label_shadow)
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
                active_widgets[widget_index].setCursor(Qt.CursorShape.PointingHandCursor)
                if widget_type == 'windows' and self._windows_update_tooltip:
                    active_widgets[widget_index].setToolTip("\n".join(names))
                elif widget_type == 'winget' and self._winget_update_tooltip:
                    active_widgets[widget_index].setToolTip("\n".join(names))
                widget_index += 1


    def handle_mouse_events(self, label_type):
        def event_handler(event):
            if event.button() == Qt.MouseButton.LeftButton:
                self._update_manager.handle_left_click(label_type)
            elif event.button() == Qt.MouseButton.RightButton:
                self._update_manager.handle_right_click(label_type)
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
