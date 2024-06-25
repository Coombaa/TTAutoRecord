import time
import subprocess
import psutil
import logging
from colorama import Fore, init

# Initialize colorama
init(autoreset=True)

logging.basicConfig(filename='gui.log', level=logging.INFO,
                    format='%(asctime)s:%(levelname)s:%(message)s')

def start_gui():
    logging.info("Starting GUI..")
    # Use pythonw.exe to run the GUI without a console window
    process = subprocess.Popen(
        ["pythonw", "modules/gui.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    logging.info("GUI started.")
    return process

def monitor_and_restart():
    gui_process = start_gui()
    while True:
        try:
            # Check memory usage
            memory_usage = psutil.Process(gui_process.pid).memory_info().rss / 1024 ** 2  # Convert to MB
            print(Fore.YELLOW + f"Current memory usage: {memory_usage:.2f} MB")

            # If memory usage exceeds a threshold, restart the GUI
            if memory_usage > 100:
                logging.info("Memory usage exceeded threshold. Restarting GUI.")
                gui_process.terminate()
                gui_process.wait()
                gui_process = start_gui()

            time.sleep(10)  # Check every 10 seconds
        except psutil.NoSuchProcess:
            logging.error("GUI process not found, restarting GUI.")
            gui_process = start_gui()
        except Exception as e:
            logging.error(f"Unexpected error in monitor loop: {e}")
            time.sleep(10)  # Delay before retrying to avoid rapid looping

if __name__ == "__main__":
    try:
        monitor_and_restart()
    except KeyboardInterrupt:
        logging.info("Watchdog stopped by user.")
        print(Fore.RED + "Watchdog stopped by user.")
