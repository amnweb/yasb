import logging
import os
import sys
from PyQt6.QtCore import QCoreApplication, QProcess
from PyQt6.QtWidgets import QApplication


def reload_application(msg="Reloading Application..."):
    try:
        QApplication.processEvents()
        logging.info(msg)
        QProcess.startDetached(sys.executable, sys.argv)
        QCoreApplication.exit(0)
    except Exception as e:
        logging.error(f"Error during reload: {e}")
        os._exit(0)


def exit_application():
    logging.info("Exiting Application...")
    try:
        sys.exit(0)
    except:
        os._exit(0)


def process_cli_command(command):
    """
    Process CLI commands received from the Named Pipe server.
    Args:
        command (str): The command received from the CLI.
    """
    if command == "reload":
        reload_application("Reloading Application from CLI...")
    elif command == "stop":
        exit_application()
