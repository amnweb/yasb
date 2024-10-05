import os
import sys
from os import path
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QTextEdit, QDialog, QDialogButtonBox
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QProcess, Qt
from settings import DEFAULT_CONFIG_DIRECTORY, DEFAULT_LOG_FILENAME
from datetime import datetime

class WindowShellDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YASB Console")
        self.resize(1060, 600)
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets', 'images', 'app_icon.png')
        
        icon = QIcon(icon_path)
        # Create a pixmap of size 48x48 and set it as the window icon
        self.setWindowIcon(QIcon(icon.pixmap(48, 48)))
 
        icon = QIcon(icon_path)
        self.setWindowIcon(icon)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMinimizeButtonHint)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setContentsMargins(0, 0, 0, 0)
        # Create a layout for the dialog
        layout = QVBoxLayout()
        # Create a QTextEdit widget for the output
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

        # Add a button box for closing the dialog
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.close_dialog)
        layout.addWidget(button_box)

        # Set the layout for the dialog
        self.setLayout(layout)

        # Create a QProcess to run PowerShell commands
        self.process = QProcess()
        self.process.readyReadStandardOutput.connect(self.update_output)
        self.process.readyReadStandardError.connect(self.update_output)
        self.process.started.connect(lambda: self.output_viewer.append(f"Log started {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"))

        # Run the PowerShell command
        self.run_powershell_command()

    def run_powershell_command(self):
        HOME_CONFIGURATION_DIR = path.join(Path.home(), DEFAULT_CONFIG_DIRECTORY)
        # Run a PowerShell command to watch the log file in real-time
        log_file_path = f"{HOME_CONFIGURATION_DIR}\\{DEFAULT_LOG_FILENAME}"
        command = f"Get-Content -Path '{log_file_path}' -Tail 10 -Wait"
        self.process.start("powershell.exe", ["-Command", command])

    def update_output(self):
        # Update the output viewer with the latest output from the process
        output = self.process.readAllStandardOutput().data().decode()
        error = self.process.readAllStandardError().data().decode()
        
        if output:
            self.append_colored_text(output)
        if error:
            self.append_colored_text(error)

    def append_colored_text(self, text):
        # Split the text into lines and apply color formatting
        for line in text.splitlines():
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
        # Terminate the PowerShell process when the dialog is closed
        self.terminate_process()
        self.close()

    def closeEvent(self, event):
        # Terminate the PowerShell process when the window is closed
        self.terminate_process()
        event.accept()

    def terminate_process(self):
        if self.process.state() == QProcess.ProcessState.Running:
            self.process.kill()