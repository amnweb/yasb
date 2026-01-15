import logging
import re
import shutil
import subprocess
import threading

import win32com.client
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel

from core.utils.tooltip import set_tooltip
from core.utils.utilities import add_shadow
from core.validation.widgets.yasb.update_check import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget
from settings import DEBUG


class UpdateWorker(QThread):
    windows_update_signal = pyqtSignal(dict)
    winget_update_signal = pyqtSignal(dict)

    def __init__(self, update_type, exclude_list=None, parent=None):
        super().__init__(parent)
        self.update_type = update_type
        self.running = True
        self.exclude_list = exclude_list or []

    def filter_updates(self, updates, names, update_type):
        if not updates:
            return 0, [], [] if type == "winget" else 0, []

        if not self.exclude_list:
            if update_type == "winget":
                filtered_ids = [u["id"] for u in updates]
                return len(updates), names, filtered_ids
            else:
                return len(updates), names

        valid_excludes = [x.lower() for x in self.exclude_list if x and x.strip()]
        filtered_names = []
        filtered_ids = []

        if update_type == "winget":
            for update, name in zip(updates, names):
                if not any(
                    excluded in update["id"].lower() or excluded in update["name"].lower()
                    for excluded in valid_excludes
                ):
                    filtered_names.append(name)
                    filtered_ids.append(update["id"])
            return len(filtered_names), filtered_names, filtered_ids
        else:
            for name in names:
                if not any(excluded in name.lower() for excluded in valid_excludes):
                    filtered_names.append(name)
            return len(filtered_names), filtered_names

    def stop(self):
        self.running = False
        self.wait()

    def run(self):
        try:
            if self.update_type == "windows":
                update_session = win32com.client.Dispatch("Microsoft.Update.Session")
                update_searcher = update_session.CreateUpdateSearcher()
                search_result = update_searcher.Search("IsInstalled=0")
                update_names = [update.Title for update in search_result.Updates]
                count, filtered_names = self.filter_updates(search_result.Updates, update_names, self.update_type)
                self.windows_update_signal.emit({"count": count, "names": filtered_names})

            elif self.update_type == "winget":
                WINGET_COLUMN_HEADERS = {
                    "en": {
                        "name": "Name",
                        "id": "Id",
                        "version": "Version",
                        "available": "Available",
                        "source": "Source",
                    },
                    "de": {
                        "name": "Name",
                        "id": "ID",
                        "version": "Version",
                        "available": "Verfügbar",
                        "source": "Quelle",
                    },
                    "it": {
                        "name": "Nome",
                        "id": "Id",
                        "version": "Versione",
                        "available": "Disponibile",
                        "source": "Origine",
                    },
                    "br": {
                        "name": "Nome",
                        "id": "ID",
                        "version": "Versão",
                        "available": "Disponível",
                        "source": "Origem",
                    },
                }
                WINGET_SECTION_HEADERS = {
                    "en": "The following packages have an upgrade available",
                    "de": "Für die folgenden Pakete ist ein Upgrade verfügbar",
                    "it": "Per i pacchetti seguenti è disponibile un aggiornamento",
                    "br": "Os pacotes a seguir têm uma atualização disponível",
                }

                result = subprocess.run(
                    ["winget", "upgrade"],
                    capture_output=True,
                    encoding="utf-8",
                    text=True,
                    check=True,
                    shell=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )

                lines = result.stdout.strip().split("\n")

                # Find header row by looking for any of the known name columns
                fl = -1
                detected_language = None

                for i, line in enumerate(lines):
                    for lang, headers in WINGET_COLUMN_HEADERS.items():
                        if (
                            headers["name"] in line
                            and headers["id"] in line
                            and headers["version"] in line
                            and headers["available"] in line
                            and headers["source"] in line
                        ):
                            fl = i
                            detected_language = lang
                            break
                    if fl >= 0:
                        break
                # Skip if language is not supported
                if fl < 0 or detected_language not in WINGET_COLUMN_HEADERS:
                    if DEBUG:
                        logging.warning("Could not identify header row in any supported language. Skipping processing.")
                    self.winget_update_signal.emit({"count": 0, "names": []})
                    return

                # Get the column headers for the detected language
                headers = WINGET_COLUMN_HEADERS[detected_language]

                # Find column positions
                id_start = lines[fl].index(headers["id"])
                version_start = lines[fl].index(headers["version"])
                available_start = lines[fl].index(headers["available"])
                source_start = lines[fl].index(headers["source"])

                upgrade_list = []
                for line in lines[fl + 1 :]:
                    # Check for known terminators in the detected language
                    if detected_language in WINGET_SECTION_HEADERS and line.startswith(
                        WINGET_SECTION_HEADERS[detected_language]
                    ):
                        break

                    # Skip lines that are too short or are separators
                    if len(line) < source_start + 1 or line.strip().startswith("-"):
                        continue

                    try:
                        name = line[:id_start].strip()
                        id_value = line[id_start:version_start].strip()
                        version = line[version_start:available_start].strip()
                        available = line[available_start:source_start].strip()

                        # Only add if all fields are present, id has no spaces, and version fields look like versions
                        if (
                            all([name, id_value, version, available])
                            and " " not in id_value
                            and any(char.isdigit() for char in version)
                            and any(char.isdigit() for char in available)
                        ):
                            software = {
                                "name": name,
                                "id": id_value,
                                "version": version,
                                "available_version": available,
                            }
                            upgrade_list.append(software)
                    except Exception as e:
                        if DEBUG:
                            logging.warning(f"Error parsing winget line: {line}, {e}")

                update_names = [
                    f"{software['name']} ({software['id']}): {software['version']} -> {software['available_version']}"
                    for software in upgrade_list
                ]

                count, filtered_names, filtered_app_ids = self.filter_updates(
                    upgrade_list, update_names, self.update_type
                )
                self.winget_update_signal.emit({"count": count, "names": filtered_names, "app_ids": filtered_app_ids})

        except Exception as e:
            logging.error(f"Error in {self.update_type} worker: {e}")
            if self.update_type == "windows":
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
        if event_type == "winget_update" and "app_ids" in data:
            self._winget_app_ids = data["app_ids"]
        for subscriber in self._subscribers:
            if hasattr(subscriber, "emit_event"):
                subscriber.emit_event(event_type, data)

    def start_worker(self, update_type, exclude_list=None):
        if update_type not in self._workers:
            worker = UpdateWorker(update_type, exclude_list)
            if update_type == "windows":
                worker.windows_update_signal.connect(lambda x: self.notify_subscribers("windows_update", x))
            else:
                worker.winget_update_signal.connect(lambda x: self.notify_subscribers("winget_update", x))
            self._workers[update_type] = worker
            worker.start()

    def stop_all(self):
        for worker in self._workers.values():
            worker.stop()
        self._workers.clear()

    def handle_left_click(self, label_type):
        if label_type == "windows":
            subprocess.Popen("start ms-settings:windowsupdate", shell=True)
        elif label_type == "winget":
            powershell_path = shutil.which("pwsh") or shutil.which("powershell") or "powershell.exe"
            # Use stored app_ids
            if self._winget_app_ids:
                count = len(self._winget_app_ids)
                package_label = "PACKAGE" if count == 1 else "PACKAGES"
                id_args = " ".join([f'"{app_id}"' for app_id in self._winget_app_ids])
                command = (
                    f'start "Winget Upgrade" "{powershell_path}" -NoExit -Command '
                    f'"Write-Host \\"=========================================\\"; '
                    f'Write-Host \\"YASB FOUND {count} {package_label} READY TO UPDATE\\"; '
                    f'Write-Host \\"=========================================\\"; '
                    f'winget upgrade {id_args}"'
                )
            else:
                command = f'start "Winget Upgrade" "{powershell_path}" -NoExit -Command "winget upgrade --all"'
            subprocess.Popen(command, shell=True)
        self.notify_subscribers(f"{label_type}_hide", {})

    def handle_right_click(self, label_type):
        # Stop existing worker if running
        if label_type in self._workers:
            self._workers[label_type].stop()
            del self._workers[label_type]
        # Get correct exclude list based on type
        exclude_list = []
        for subscriber in self._subscribers:
            if label_type == "windows" and hasattr(subscriber, "_windows_update_exclude"):
                exclude_list.extend(subscriber._windows_update_exclude)
            elif label_type == "winget" and hasattr(subscriber, "_winget_update_exclude"):
                exclude_list.extend(subscriber._winget_update_exclude)

        # Hide the container first
        self.notify_subscribers(f"{label_type}_hide", {})
        # Start new worker
        self.start_worker(label_type, exclude_list)


class UpdateCheckWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
        self,
        windows_update: dict[str, str],
        winget_update: dict[str, str],
        label_shadow: dict = None,
        container_shadow: dict = None,
    ):
        super().__init__(class_name="update-check-widget")

        self._windows_update = windows_update
        self._winget_update = winget_update

        self._windows_update_tooltip = self._windows_update["tooltip"]
        self._winget_update_tooltip = self._winget_update["tooltip"]

        self._window_update_enabled = self._windows_update.get("enabled", False)
        self._windows_update_label = self._windows_update.get("label", "")
        self._windows_update_exclude = self._windows_update.get("exclude", [])

        self._winget_update_enabled = self._winget_update.get("enabled", False)
        self._winget_update_label = self._winget_update.get("label", "")
        self._winget_update_exclude = self._winget_update.get("exclude", [])

        self._label_shadow = label_shadow
        self._container_shadow = container_shadow

        self.windows_update_data = 0
        self.winget_update_data = 0

        self._create_dynamically_label(self._winget_update_label, self._windows_update_label)

        self._update_manager = UpdateManager()
        self._update_manager.register_subscriber(self)

        self._workers_started = False
        self._startup_timer = None
        if self._window_update_enabled or self._winget_update_enabled:
            self._schedule_worker_start()

        self.update_widget_visibility()

    def _schedule_worker_start(self):
        if self._workers_started:
            return
        self._startup_timer = QTimer(self)
        self._startup_timer.setSingleShot(True)
        self._startup_timer.timeout.connect(self._start_workers)
        self._startup_timer.start(10000)

    def _start_workers(self):
        if self._workers_started:
            return
        self._workers_started = True
        if self._startup_timer:
            self._startup_timer.stop()
            self._startup_timer = None

        if self._window_update_enabled:
            self._update_manager.start_worker("windows", self._windows_update_exclude)
        if self._winget_update_enabled:
            self._update_manager.start_worker("winget", self._winget_update_exclude)

    def emit_event(self, event_type, update_info):
        if event_type == "windows_update":
            self.windows_update_data = update_info["count"]
            self._update_label("windows", update_info["count"], update_info["names"])
        elif event_type == "winget_update":
            self.winget_update_data = update_info["count"]
            self._update_label("winget", update_info["count"], update_info["names"])
        elif event_type == "windows_hide":
            self.hide_container("windows")
        elif event_type == "winget_hide":
            self.hide_container("winget")
        self.update_widget_visibility()

    def _create_dynamically_label(self, windows_label: str, winget_label: str):
        def process_content(label_text, label_type):
            container = QFrame()
            container_layout = QHBoxLayout()
            container_layout.setSpacing(0)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container.setLayout(container_layout)
            class_name = "windows" if label_type == "windows" else "winget"
            container.setProperty("class", f"widget-container {class_name}")
            add_shadow(container, self._container_shadow)
            self.widget_layout.addWidget(container)
            container.hide()
            label_parts = re.split(r"(<span.*?>.*?</span>)", label_text)
            label_parts = [part for part in label_parts if part]
            widgets = []

            for part in label_parts:
                part = part.strip()
                if not part:
                    continue
                if "<span" in part and "</span>" in part:
                    class_match = re.search(r'class=(["\'])([^"\']+?)\1', part)
                    class_result = class_match.group(2) if class_match else "icon"
                    icon = re.sub(r"<span.*?>|</span>", "", part).strip()
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
        if widget_type == "winget":
            active_widgets = self._widget_widget
            active_label_content = self._winget_update_label
            container = self._winget_container
        elif widget_type == "windows":
            active_widgets = self._widget_windows
            active_label_content = self._windows_update_label
            container = self._windows_container
        else:
            return

        label_parts = re.split(r"(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0
        if data == 0:
            container.hide()
            return
        container.show()
        for part in label_parts:
            part = part.strip()
            if part and widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                if "<span" in part and "</span>" in part:
                    icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                    active_widgets[widget_index].setText(icon)
                else:
                    formatted_text = part.format(count=data)
                    active_widgets[widget_index].setText(formatted_text)
                active_widgets[widget_index].setCursor(Qt.CursorShape.PointingHandCursor)
                widget_index += 1
        if widget_type == "windows" and self._windows_update_tooltip:
            set_tooltip(container, "\n".join(names))
        elif widget_type == "winget" and self._winget_update_tooltip:
            set_tooltip(container, "\n".join(names))

    def handle_mouse_events(self, label_type):
        def event_handler(event):
            if event.button() == Qt.MouseButton.LeftButton:
                self._update_manager.handle_left_click(label_type)
            elif event.button() == Qt.MouseButton.RightButton:
                self._update_manager.handle_right_click(label_type)

        return event_handler

    def hide_container(self, container):
        if container == "windows":
            self.windows_update_data = 0
            self._update_label("windows", 0, [])
        elif container == "winget":
            self.winget_update_data = 0
            self._update_label("winget", 0, [])
        self.update_widget_visibility()

    def update_widget_visibility(self):
        if self.windows_update_data == 0 and self.winget_update_data == 0:
            self.hide()
        else:
            self.show()
