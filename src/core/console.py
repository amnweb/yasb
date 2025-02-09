import os
from os import path
from pathlib import Path
import re
from PyQt6.QtWidgets import QVBoxLayout, QTextEdit, QDialog
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from settings import DEFAULT_CONFIG_DIRECTORY, DEFAULT_LOG_FILENAME
from datetime import datetime

class LogTailer(QThread):
    new_line = pyqtSignal(str)
    
    def __init__(self, log_file_path):
        super().__init__()
        self.log_file_path = log_file_path
        self._running = True

    def run(self):
        with open(self.log_file_path, 'r') as file:
            file.seek(0, os.SEEK_END)
            while self._running:
                line = file.readline()
                if not line:
                    self.msleep(100)
                    continue
                self.new_line.emit(line)

    def stop(self):
        self._running = False

class WindowShellDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YASB Console")
        self.resize(1060, 600)
        self.setStyleSheet("""
            QTextEdit {
                background-color: #13161a;
                color: #cfd1e1;
                border:1px solid #2c323b;
                font-family: 'JetBrainsMono Nerd Font Propo','JetBrainsMono NFP', 'JetBrains Mono', Consolas, 'Courier New', monospace;
                font-size:14px;
                selection-background-color: #373b3e;
                selection-color: #cfd1e1;
            }
            QTextEdit:focus {
                color: #cfd1e1;
            }
            QTextEdit:unfocus {
                color: #cfd1e1;
            }
        """)
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets', 'images', 'app_icon.png')
        
        icon = QIcon(icon_path)
        self.setWindowIcon(QIcon(icon.pixmap(48, 48)))

        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMinimizeButtonHint)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setContentsMargins(0, 0, 0, 0)

        layout = QVBoxLayout()
        self.output_viewer = QTextEdit()
        self.output_viewer.setReadOnly(True)

        layout.addWidget(self.output_viewer)
 
        self.setLayout(layout)
            
        HOME_CONFIGURATION_DIR = path.join(Path.home(), DEFAULT_CONFIG_DIRECTORY)
        log_file_path = f"{HOME_CONFIGURATION_DIR}\\{DEFAULT_LOG_FILENAME}"

        self.log_tailer = LogTailer(log_file_path)
        self.log_tailer.new_line.connect(self.append_colored_text)
        self.log_tailer.start()

        self.output_viewer.append(f"Log started {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    def append_colored_text(self, line):
        # Regular expression to match the date part at the beginning of the line
        date_pattern = r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})'
        match = re.match(date_pattern, line)
        
        if match:
            date_part = match.group(1)
            log_line = line[len(date_part):]
            formatted_date = f'<span style="color:rgba(255, 255, 255, 0.3);">{date_part}</span>'
        else:
            formatted_date = ''
            log_line = line

        if "CRITICAL" in log_line:
            formatted_line = f'{formatted_date}<span style="color:#ff000;font-weight:bold">{log_line}</span>'
        elif "ERROR" in log_line:
            formatted_line = f'{formatted_date}<span style="color:#ff4d4d;font-weight:bold">{log_line}</span>'
        elif "WARNING" in log_line:
            formatted_line = f'{formatted_date}<span style="color:#ffb64d;">{log_line}</span>'
        else:
            formatted_line = f'{formatted_date}<span>{log_line}</span>'

        self.output_viewer.append(formatted_line)

    def close_dialog(self):
        self.log_tailer.stop()
        self.close()

    def closeEvent(self, event):
        self.log_tailer.stop()
        event.accept()