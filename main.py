import os
import threading
import argparse
import time
from modules.download_live import main as download_live_main
from modules.get_stream_link import main as get_stream_link_main
from modules.user_check import main as user_check_main
from modules.gui import main as gui_main

# Set up argument parsing
parser = argparse.ArgumentParser(description="Run the application with or without GUI.")
parser.add_argument('--nogui', action='store_true', help="Disable the GUI to save resources.")

# Parse arguments
args = parser.parse_args()

# Define paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BINARIES_DIR = os.path.join(BASE_DIR, 'binaries')
LOCK_FILES_DIR = os.path.join(BASE_DIR, 'lock_files')
SEGMENTS_DIR = os.path.join(BASE_DIR, 'segments')
VIDEOS_DIR = os.path.join(BASE_DIR, 'videos')

# Ensure directories exist
os.makedirs(LOCK_FILES_DIR, exist_ok=True)
os.makedirs(SEGMENTS_DIR, exist_ok=True)
os.makedirs(VIDEOS_DIR, exist_ok=True)
os.makedirs(BINARIES_DIR, exist_ok=True) 


def disable_quickedit():
    if not os.name == 'posix':
        try:
            import msvcrt
            import ctypes
            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            device = r'\\.\CONIN$'
            with open(device, 'r') as con:
                hCon = msvcrt.get_osfhandle(con.fileno())
                kernel32.SetConsoleMode(hCon, 0x0080)
        except Exception as e:
            print('Cannot disable QuickEdit mode! ' + str(e))
            print('.. As a consequence the script might be automatically\
            paused on Windows terminal, please disable it manually!')


if __name__ == "__main__":
    
    disable_quickedit()
    
    # Create threads for each module's main function
    download_live_thread = threading.Thread(target=download_live_main)
    get_stream_link_thread = threading.Thread(target=get_stream_link_main)
    user_check_thread = threading.Thread(target=user_check_main)
    
    # Start the threads
    download_live_thread.start()
    get_stream_link_thread.start()
    time.sleep(15)
    user_check_thread.start()

    # Only start GUI thread if --nogui is not specified
    if not args.nogui:
        gui_thread = threading.Thread(target=gui_main)
        gui_thread.start()

    # Wait for all threads to finish
    download_live_thread.join()
    get_stream_link_thread.join()
    user_check_thread.join()
    
    if not args.nogui:
        gui_thread.join()
