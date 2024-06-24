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
    subprocess.Popen(["python", "modules/gui.py"])
    logging.info("GUI started.")

def monitor_and_restart():
    while True:
        # Check memory usage
        for process in psutil.process_iter(['pid', 'name', 'cmdline']):
            if 'python' in process.info['name'] and 'gui.py' in process.info['cmdline']:
                memory_usage = process.memory_info().rss / 1024 ** 2  # Convert to MB

                # If memory usage exceeds a threshold, restart the GUI
                if memory_usage > 200:
                    logging.info("Memory usage exceeded threshold. Restarting GUI.")
                    restart_gui(process.info['pid'])

        time.sleep(10)  # Check every 10 seconds

def restart_gui(pid):
    # Terminate the current GUI process
    subprocess.run(["kill", str(pid)])
    logging.info(f"Terminated GUI process with PID: {pid}")

    time.sleep(1)

    # Restart the GUI
    subprocess.Popen(["python", "modules/gui.py"])
    logging.info("Restarted GUI.")

if __name__ == "__main__":
    try:
        start_gui()
        monitor_and_restart()
    except KeyboardInterrupt:
        logging.info("Watchdog stopped by user.")
        print(Fore.RED + "Watchdog stopped by user.")
