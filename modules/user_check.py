import os
import time
import sys
import json
import logging
from urllib.parse import urlparse
from colorama import Fore, init
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.common.exceptions import WebDriverException, NoSuchElementException, TimeoutException
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Initialize colorama
init()

# Setup basic logging with date and time format
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

script_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
binaries_dir = os.path.join(script_dir, 'binaries')
json_dir = os.path.join(script_dir, 'json')
lock_files_dir = os.path.join(script_dir, 'lock_files')

stop_threads = False

# Browser operations function
def browser_operations():
    global stop_threads
    driver = start_browser()
    auth(driver)

    while not stop_threads:
        try:
            driver.refresh()
            live_user_urls = get_live_users(driver)
            write_to_json(live_user_urls)
            time.sleep(10)
        except WebDriverException as e:
            logging.error(f"WebDriverException occurred: {e}")
            logging.info("Attempting to restart browser...")
            driver.quit()
            time.sleep(5)
            driver = start_browser()
            auth(driver)

    driver.quit()

def start_browser():
    logging.info("Starting browser..")
    geckodriver_path = os.path.join(binaries_dir, "geckodriver.exe")
    firefox_binary_path = 'C:/Program Files/Mozilla Firefox/firefox.exe'
    options = Options()
    options.binary_location = firefox_binary_path
    options.add_argument('-headless')
    service = Service(executable_path=geckodriver_path, log_output=os.devnull)
    driver = webdriver.Firefox(service=service, options=options)
    driver.get("https://www.tiktok.com/@tiktok/live")
    return driver

def auth(driver):
    logging.info("Authenticating..")
    cookies_path = os.path.join(json_dir, 'cookies.json')
    if os.path.getsize(cookies_path) <= 0:
        logging.error("Error: cookies.json is empty. Read the README file!")
        time.sleep(10)
        sys.exit()
    else:
        with open(cookies_path, 'r') as f:
            cookies = json.load(f)
        for cookie in cookies:
            if 'sameSite' in cookie:
                del cookie['sameSite']
            driver.add_cookie(cookie)
        driver.refresh()
        logging.info("Successfully authenticated! Starting monitor..")

def get_live_users(driver):
    live_users_data = []
    try:
        time.sleep(5)
        try:
            see_all_btn = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-e2e='live-side-more-button']"))
            )
            see_all_btn.click()
        except TimeoutException:
            pass
        except NoSuchElementException:
            pass

        candidate_divs = driver.find_elements(By.CSS_SELECTOR, "div[data-e2e='live-side-nav-channel']")
        following_div = None
        for div in candidate_divs:
            if "Following" in div.text:
                following_div = div
                break
        if following_div is not None:
            a_elements = following_div.find_elements(By.CSS_SELECTOR, "a[href*='/@']")
            for a in a_elements:
                user_data = {}
                url = a.get_attribute('href')
                username = extract_username(url)
                user_data['username'] = username
                user_data['stream_link'] = url
                try:
                    image_element = a.find_element(By.TAG_NAME, 'img')
                    image_url = image_element.get_attribute('src')
                    user_data['profile_picture'] = image_url
                except NoSuchElementException:
                    user_data['profile_picture'] = None
                live_users_data.append(user_data)
    except Exception as e:
        logging.error(f"An unexpected exception occurred: {e}")
    return live_users_data

def extract_username(url):
    parsed_url = urlparse(url)
    username = parsed_url.path.split('/')[1]
    return username.replace("@", "")

def write_to_json(live_users_data, filename='live_users.json'):
    json_folder_path = json_dir
    file_path = os.path.join(json_folder_path, filename)
    if not os.path.exists(json_folder_path):
        os.makedirs(json_folder_path)
    with open(file_path, 'w') as file:
        json.dump(live_users_data, file, indent=4)
    logging.info("Live User List Updated!")
        
def lock_file_exists(username):
    lock_file_path = os.path.join(lock_files_dir, f'{username}.lock')
    return os.path.exists(lock_file_path)
        
def main():
    global stop_threads

    browser_operations()
        
if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Script execution stopped by user.")
    except Exception as e:
        logging.critical(f"Critical error, stopping script: {e}")
