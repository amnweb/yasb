import argparse
import subprocess
import sys
import logging
import os
import time
import re
from settings import BUILD_VERSION
from colorama import just_fix_windows_console
just_fix_windows_console()

class Format:
    end = '\033[0m'
    underline = '\033[4m'
    gray = '\033[90m'
    red = '\033[91m'
    yellow = '\033[93m'
    blue = '\033[94m'
    green = '\033[92m'

def format_log_line(line):
    line = re.sub(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', f"{Format.gray}\\g<0>{Format.end}", line, count=1)
    
    log_levels = ["CRITICAL", "ERROR", "WARNING", "NOTICE", "INFO", "DEBUG", "TRACE"]
    for level in log_levels:
        if level in line:
            padded_level = level.ljust(8)
            if level in ['CRITICAL', 'ERROR']:
                line = line.replace(level, f"{Format.red}{padded_level}{Format.end}")
            elif level == "WARNING":
                line = line.replace(level, f"{Format.yellow}{padded_level}{Format.end}")
            elif level == "NOTICE":
                line = line.replace(level, f"{Format.green}{padded_level}{Format.end}")
            elif level == "TRACE":
                line = line.replace(level, f"{Format.blue}{padded_level}{Format.end}")
            else:
                line = line.replace(level, padded_level)
            break
    return line

class CustomArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        print(f'\n{Format.red}Error:{Format.end} {message}\n')
        sys.exit(2)

class CLIHandler:
    # @staticmethod
    # def is_executable() -> bool:
    #     """
    #     is_executable will return True if the application is running as a standalone executable and False if it is running as a script.
    #     """
    #     return getattr(sys, 'frozen', False)
            
    @staticmethod
    def parse_arguments():
        parser = CustomArgumentParser(description="The command-line interface for YASB Reborn.", add_help=False)
        subparsers = parser.add_subparsers(dest='command', help='Commands')

        subparsers.add_parser('start', help='Start the application')
        subparsers.add_parser('stop', help='Stop the application')
        subparsers.add_parser('reload', help='Reload the application')
        subparsers.add_parser('help', help='Show help message')
        subparsers.add_parser('log', help='Tail yasb process logs (cancel with Ctrl-C)')
        parser.add_argument('-v', '--version', action='version', version=f'YASB Reborn v{BUILD_VERSION}', help="Show program's version number and exit.")
        parser.add_argument('-h', '--help', action='store_true', help='Show help message')
        args = parser.parse_args()
 
        if args.command == 'start':
            print("Start YASB in background...")
            subprocess.Popen(["yasb.exe"])
            sys.exit(0)
            
        elif args.command == 'stop':
            print("Stop YASB...")
            subprocess.run(["taskkill", "/f", "/im", "yasb.exe"], creationflags=subprocess.CREATE_NO_WINDOW)
            sys.exit(0)
            
        elif args.command == 'reload':
            print("Reload YASB...")
            subprocess.run(["taskkill", "/f", "/im", "yasb.exe"], creationflags=subprocess.CREATE_NO_WINDOW)
            subprocess.Popen(["yasb.exe"])
            sys.exit(0)
            
        elif args.command == 'log':
            log_file = os.path.join(os.path.expanduser("~"), ".config", "yasb", "yasb.log")
            try:
                with open(log_file, 'r') as f:
                    f.seek(0, os.SEEK_END)
                    while True:
                        line = f.readline()
                        if not line:
                            time.sleep(0.2)
                            continue
                        formatted_line = format_log_line(line)
                        print(formatted_line, end='')
            except KeyboardInterrupt:
                pass
            sys.exit(0)
            
        elif args.command == 'help' or args.help:
            print("The command-line interface for YASB Reborn.")
            print('\n' + Format.underline + 'Usage' + Format.end + ': yasbc <COMMAND>')
            print('\n' + Format.underline + 'Commands' + Format.end + ':')
            print("  start   Start the application")
            print("  stop    Stop the application")
            print("  reload  Reload the application")
            print("  log     Tail yasb process logs (cancel with Ctrl-C)")
            print("  help    Print this message")
            print('\n' + Format.underline + 'Options' + Format.end + ':')
            print("  --version  Print version")
            print("  --help     Print this message")
            sys.exit(0)
                  
        else:
            logging.info("Unknown command. Use --help for available options.")
            sys.exit(1)

if __name__ == "__main__":
    CLIHandler.parse_arguments()
    sys.exit(0)