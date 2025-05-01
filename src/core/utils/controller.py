import logging
import os
import sys

from PyQt6.QtCore import QProcess, QCoreApplication
from PyQt6.QtWidgets import QApplication

from core.utils.cli_server import CliPipeHandler

def reload_application(msg="Reloading Application...", forced=False):
    try:
        logging.info(msg)
        if hasattr(sys, '_cli_pipe_handler') and sys._cli_pipe_handler is not None:
            sys._cli_pipe_handler.stop_cli_pipe_server()
        QApplication.processEvents()
        QProcess.startDetached(sys.executable, sys.argv)
        if forced:
            os._exit(0)
        else:
            QCoreApplication.exit(0)
    except Exception as e:
        logging.error(f"Error during reload: {e}")
        os._exit(0)


def exit_application(msg="Exiting Application..."):
    logging.info(msg)
    try:
        if hasattr(sys, '_cli_pipe_handler') and sys._cli_pipe_handler is not None:
            sys._cli_pipe_handler.stop_cli_pipe_server()
        QCoreApplication.exit(0)
        #sys.exit(0)
    except:
        os._exit(0)


def process_cli_command(command: str):
    """
    Process CLI commands received from the Named Pipe server.
    Args:
        command (str): The command received from the CLI.
    """
    if command == "reload":
        reload_application("Reloading Application from CLI...")
    elif command == "stop":
        exit_application("Exiting Application from CLI...")

def start_cli_server():
    handler = CliPipeHandler(process_cli_command)
    handler.start_cli_pipe_server()
    sys._cli_pipe_handler = handler
