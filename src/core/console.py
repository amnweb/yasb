import os
from os import path
from pathlib import Path
from PyQt6.QtWidgets import QVBoxLayout, QTextEdit, QDialog, QDialogButtonBox
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
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets', 'images', 'app_icon.png')
        
        icon = QIcon(icon_path)
        self.setWindowIcon(QIcon(icon.pixmap(48, 48)))

        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMinimizeButtonHint)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setContentsMargins(0, 0, 0, 0)

        layout = QVBoxLayout()
        self.output_viewer = QTextEdit()
        self.output_viewer.setReadOnly(True)
        self.output_viewer.setStyleSheet("""
            QTextEdit {
                background-color: #13161a;
                color: #cfd1e1;
                border:1px solid #2c323b;
                font-family: 'JetBrainsMono NFP','Courier New', Consolas, monospace;
                font-size:13px;
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
        layout.addWidget(self.output_viewer)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.close_dialog)
        layout.addWidget(button_box)

        self.setLayout(layout)

        HOME_CONFIGURATION_DIR = path.join(Path.home(), DEFAULT_CONFIG_DIRECTORY)
        log_file_path = f"{HOME_CONFIGURATION_DIR}\\{DEFAULT_LOG_FILENAME}"

        self.log_tailer = LogTailer(log_file_path)
        self.log_tailer.new_line.connect(self.append_colored_text)
        self.log_tailer.start()

        self.output_viewer.append(f"Log started {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    def append_colored_text(self, line):
        if "CRITICAL" in line:
            formatted_line = f'<span style="color:#ff000;font-weight:bold">{line}</span>'
        elif "ERROR" in line:
            formatted_line = f'<span style="color:#ff4d4d;;font-weight:bold">{line}</span>'
        elif "WARNING" in line:
            formatted_line = f'<span style="color:#ffb64d;">{line}</span>'
        else:
            formatted_line = f'<span>{line}</span>'
        self.output_viewer.append(formatted_line)

    def close_dialog(self):
        self.log_tailer.stop()
        self.close()

    def closeEvent(self, event):
        self.log_tailer.stop()
        event.accept()