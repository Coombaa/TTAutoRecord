import os
import threading
import psutil
import logging
import undetected_chromedriver as uc
import shutil
import time

from modules.get_stream_link import main as get_stream_link_main
from modules.user_check import main as user_check_main
from modules.get_stream_link import load_cookies

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_DIR = os.path.join(BASE_DIR, 'session')
USER_CHECK_PROFILE = os.path.join(SESSION_DIR, "UserCheck")
GET_STREAM_LINK_PROFILE = os.path.join(SESSION_DIR, "GetStreamLink")
CHROMEDRIVER_CACHE_1 = os.path.join(SESSION_DIR, "chrome_cache_1")
CHROMEDRIVER_CACHE_2 = os.path.join(SESSION_DIR, "chrome_cache_2")
CHROMEDRIVER_PATH_1 = os.path.join(SESSION_DIR, 'chromedriver_1.exe')
CHROMEDRIVER_PATH_2 = os.path.join(SESSION_DIR, 'chromedriver_2.exe')

cookies_updated = threading.Event()

get_stream_link_driver = None

logging.basicConfig(filename='watchdog.log', level=logging.INFO,
                    format='%(asctime)s:%(levelname)s:%(message)s')

def create_folders():
    os.makedirs(SESSION_DIR, exist_ok=True)
    os.makedirs(USER_CHECK_PROFILE, exist_ok=True)
    os.makedirs(GET_STREAM_LINK_PROFILE, exist_ok=True)
    os.makedirs(CHROMEDRIVER_CACHE_1, exist_ok=True)
    os.makedirs(CHROMEDRIVER_CACHE_2, exist_ok=True)

def copy_chromedriver_executable():
    chrome_instance = uc.Chrome()
    original_driver_path = chrome_instance.patcher.executable_path
    shutil.copyfile(original_driver_path, CHROMEDRIVER_PATH_1)
    shutil.copyfile(original_driver_path, CHROMEDRIVER_PATH_2)
    chrome_instance.quit()

def start_browser(profile_dir, cache_dir, chromedriver_path):
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)

    options = uc.ChromeOptions()
    options.add_argument(f'--user-data-dir={profile_dir}')
    
    # Start a separate Chrome instance with a unique cache and driver executable
    driver = uc.Chrome(options=options, driver_executable_path=chromedriver_path, patcher_args={'path': cache_dir})
    return driver

def kill_chrome_processes():
    # Kill all Chrome and ChromeDriver processes when the script ends
    for process in psutil.process_iter(['name']):
        if process.info['name'] == 'chrome.exe' or process.info['name'] == 'chromedriver.exe':
            process.kill()

def run_user_check(user_check_driver):
    logging.info("Running user_check...")

    def trigger_get_stream_link():
        logging.info("Login successful, triggering get_stream_link.")
        cookies_updated.set()

    user_check_main(user_check_driver, user_check_driver.window_handles[-1], on_login_success=trigger_get_stream_link)

def run_get_stream_link():
    global get_stream_link_driver
    logging.info("Waiting for user to log in or cookies to update...")

    # Wait until the user_check process signals that cookies are updated
    while True:
        try:
            if cookies_updated.is_set():
                logging.info("Reloading cookies on successful login...")
                cookie_file_path = os.path.join(BASE_DIR, 'json', 'cookies.json')
                try:
                    get_stream_link_driver.get("https://www.tiktok.com")
                    load_cookies(get_stream_link_driver, cookie_file_path)
                    get_stream_link_driver.refresh()
                    cookies_updated.clear()
                    logging.info("Cookies reloaded and page refreshed.")
                except Exception as e:
                    logging.error(f"Failed to reload cookies: {e}")

            logging.info("Running get_stream_link operations...")
            get_stream_link_main(get_stream_link_driver, get_stream_link_driver.window_handles[-1])
            time.sleep(10)
        except Exception as e:
            logging.error(f"Error in get_stream_link loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    try:
        create_folders()
        copy_chromedriver_executable()

        # Start user_check browser session
        logging.info("Starting user_check browser...")
        user_check_driver = start_browser(USER_CHECK_PROFILE, CHROMEDRIVER_CACHE_1, CHROMEDRIVER_PATH_1)

        # Start get_stream_link browser session
        logging.info("Starting get_stream_link browser...")
        get_stream_link_driver = start_browser(GET_STREAM_LINK_PROFILE, CHROMEDRIVER_CACHE_2, CHROMEDRIVER_PATH_2)

        # Run user_check first
        logging.info("Running user_check thread...")
        user_check_thread = threading.Thread(target=run_user_check, args=(user_check_driver,))
        user_check_thread.start()

        # Run get_stream_link only after cookies are updated or user is logged in
        logging.info("Running get_stream_link thread...")
        get_stream_link_thread = threading.Thread(target=run_get_stream_link)
        get_stream_link_thread.start()

        # Wait for get_stream_link to finish
        get_stream_link_thread.join(timeout=300)

    finally:
        kill_chrome_processes()
