import logging
import re
import subprocess

from PyQt6.QtCore import QObject, pyqtSlot

from core.utils.win32.system_function import function_map


class Commands(QObject):
    @pyqtSlot(str)
    def execute(self, command_line: str) -> None:
        """Run `name args...`, with quotes around an argument that has spaces. A name from the system
        function map, like start_menu, runs that instead of a program."""
        args = [arg.strip('"') for arg in re.findall(r'".+?"|[^ ]+', command_line)]
        if not args:
            return
        command, *rest = args
        if command in function_map:
            function_map[command]()
            return
        try:
            subprocess.Popen([command, *rest], shell=True)
        except OSError:
            logging.exception("Failed to run %s", command_line)
