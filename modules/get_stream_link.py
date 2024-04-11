import json
import os
import re
import sys
import time
import logging
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from pathlib import Path
from modules.SharedDataStore import shared_stream_links_store



# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class StreamLink:
    def __init__(self, username, stream_link, profile_picture):
        self.username = username
        self.stream_link = stream_link
        self.profile_picture = profile_picture

# Adjusted to use the parent directory of the current script's directory
script_dir = Path(__file__).parent.parent
json_dir = script_dir / 'json'
lock_files_dir = script_dir / 'lock_files'
binaries_dir = script_dir / 'binaries'

def load_cookies():
    with open(json_dir / "cookies.json", "r") as file:
        cookies = json.load(file)
    return cookies

def correct_url_format(url):
    return url.replace("\\u002F", "/").replace("\\u0026", "&")

def find_room_id(page_source):
    room_id_pattern = re.compile(r'room_id=(\d+)')
    search = room_id_pattern.search(page_source)
    if search:
        return search.group(1)
    else:
        logging.info("No room ID found in the page source.")
        return None

def find_stream_link(page_source, username, force_flv_users):
    flv_pattern = re.compile(r'"rtmp_pull_url":\s*"([^"]+)"')
    m3u8_pattern = re.compile(r'"hls_pull_url":\s*"([^"]+)"')

    if username in force_flv_users:
        search = flv_pattern.search(page_source)
        if search:
            return correct_url_format(search.group(1))

    search = flv_pattern.search(page_source)
    if search:
        return correct_url_format(search.group(1))

    search = m3u8_pattern.search(page_source)
    if search:
        return correct_url_format(search.group(1))

    logging.info("No matching stream link found in the page source.")
    return None

def load_force_flv_users():
    with open("./json/force_flv.json", "r") as file:
        data = json.load(file)
    return data.get("force_flv_users", [])

def start_browser():
    geckodriver_path = binaries_dir / "geckodriver.exe"    
    firefox_binary_path = 'C:/Program Files/Mozilla Firefox/firefox.exe'
    options = Options()
    options.binary_location = firefox_binary_path
    options.add_argument('-headless')
    options.set_preference("browser.cache.disk.enable", False)
    options.set_preference("browser.cache.memory.enable", False)
    options.set_preference("browser.cache.offline.enable", False)
    options.set_preference("network.http.use-cache", False)
    service = Service(executable_path=geckodriver_path)
    driver = webdriver.Firefox(service=service, options=options)
    return driver

def auth(driver):
    time.sleep(2)
    driver.get("https://www.tiktok.com")
    cookies_path = json_dir / 'cookies.json'
    if os.path.getsize(cookies_path) <= 0:
        logging.error("Error: cookies.json is empty. Read the README file!")
        sys.exit()
    else:
        with open(cookies_path, 'r') as f:
            cookies = json.load(f)
        for cookie in cookies:
            if 'sameSite' in cookie:
                del cookie['sameSite']
            driver.add_cookie(cookie)
        driver.refresh()

def read_stream_links(path=json_dir / "live_users.json"):
    try:
        with open(path, "r") as file:
            data = json.load(file)
        return [StreamLink(**item) for item in data]
    except json.JSONDecodeError:
        logging.error(f"Empty or invalid JSON in {path}.")
        return []  # Return an empty list or some default value


def clear_old_stream_links(active_usernames):
    all_usernames = list(shared_stream_links_store.data.keys())
    for username in all_usernames:
        if username not in active_usernames:
            shared_stream_links_store.remove_value(username)
            logging.info(f"Removed stream link for inactive user: {username}")


def process_user(driver, user, force_flv_users):
    lock_file_path = lock_files_dir / f"{user.username}.lock"
    if lock_file_path.exists():
        return

    try:
        driver.get(f"view-source:{user.stream_link}")
        page_source = driver.page_source
        room_id = find_room_id(page_source)
                
        if room_id:
            webcast_url = f"https://webcast.tiktok.com/webcast/room/info/?aid=1988&room_id={room_id}"
            driver.get(f"view-source:{webcast_url}")
            page_source = driver.page_source
            stream_link = find_stream_link(page_source, user.username, force_flv_users)
            if stream_link:
                shared_stream_links_store.set_value(user.username, stream_link)
            else:
                logging.info(f"No stream link found for {user.username}")
        else:
            logging.info(f"No room ID found for {user.username}. Passing firewall challenge...")
            driver.get(user.stream_link)  # Retrying without 'view-source:' prefix
            time.sleep(3)  # Wait for JavaScript execution
            page_source = driver.page_source
            room_id = find_room_id(page_source)
            if room_id:
                webcast_url = f"https://webcast.tiktok.com/webcast/room/info/?aid=1988&room_id={room_id}"
                driver.get(f"view-source:{webcast_url}")
                page_source = driver.page_source
                stream_link = find_stream_link(page_source, user.username, force_flv_users)
                if stream_link:
                    shared_stream_links_store.set_value(user.username, stream_link)
                else:
                    logging.info(f"No stream link found for {user.username} after retry.")
            else:
                logging.info(f"No room ID found for {user.username} after retry.")
    except Exception as e:
        logging.error(f"Error processing {user.username}: {e}")


def main():
    logging.info("Starting the program...")
    driver = start_browser()
    auth(driver)

    while True:
        logging.info("Checking for updates.")
        force_flv_users = load_force_flv_users()
        active_stream_links = read_stream_links()
        active_usernames = [user.username for user in active_stream_links]
        if active_stream_links:
            for user in active_stream_links:
                process_user(driver, user, force_flv_users)
        else:
            logging.info("No active stream links found.")
        
        clear_old_stream_links(set(active_usernames))
        time.sleep(5)


if __name__ == "__main__":
    main()
