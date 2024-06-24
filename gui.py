import time
import subprocess
import psutil
import logging
from colorama import Fore, init

# Initialize colorama
init()

logging.basicConfig(filename='gui.log', level=logging.INFO,
                    format='%(asctime)s:%(levelname)s:%(message)s')

def start_gui():
    logging.info("Starting GUI..")
    process = subprocess.Popen(["python", "modules/gui.py"])
    logging.info("GUI started.")
    return process

def monitor_and_restart():
    gui_process = start_gui()
    while True:
        # Check memory usage
        memory_usage = psutil.Process(gui_process.pid).memory_info().rss / 1024 ** 2  # Convert to MB
        print(Fore.YELLOW + f"Current memory usage: {memory_usage:.2f} MB")

        # If memory usage exceeds a threshold, restart the GUI
        if memory_usage > 200:
            logging.info("Memory usage exceeded threshold. Restarting GUI.")
            gui_process.terminate()
            gui_process.wait()
            gui_process = start_gui()

        time.sleep(10)  # Check every 10 seconds

if __name__ == "__main__":
    try:
        monitor_and_restart()
    except KeyboardInterrupt:
        logging.info("Watchdog stopped by user.")
        print(Fore.RED + "Watchdog stopped by user.")
