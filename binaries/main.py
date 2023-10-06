from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import time
import json
import requests
import re
from urllib.parse import urlparse
import os
import subprocess
from requests.exceptions import ChunkedEncodingError
import aiohttp
import asyncio
import sys
import ctypes
import threading
from colorama import Fore, Back, Style, init
import ctypes


init(autoreset=True)

# Get the current working directory
current_directory = os.getcwd()

# Clear monitored_users.txt
monitored_users_path = os.path.join(current_directory, 'config', 'lists', 'monitored_users.txt')
with open(monitored_users_path, 'w') as f:
    f.write("")

def disable_quick_edit():
    # The function uses STD_INPUT_HANDLE to get a handle to stdin
    STD_INPUT_HANDLE = -10

    # Retrieve the console mode
    handle = ctypes.windll.kernel32.GetStdHandle(STD_INPUT_HANDLE)
    mode = ctypes.c_ulong(0)

    # Get current mode
    ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode))

    # Clear the ENABLE_QUICK_EDIT_MODE bit
    ENABLE_QUICK_EDIT_MODE = 0x0040
    new_mode = mode.value & (~ENABLE_QUICK_EDIT_MODE)

    # Set the new mode
    ctypes.windll.kernel32.SetConsoleMode(handle, new_mode)
    
disable_quick_edit()

class COORD(ctypes.Structure):
    _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]

class SMALL_RECT(ctypes.Structure):
    _fields_ = [("Left", ctypes.c_short), ("Top", ctypes.c_short), ("Right", ctypes.c_short), ("Bottom", ctypes.c_short)]

class CONSOLE_SCREEN_BUFFER_INFO(ctypes.Structure):
    _fields_ = [("dwSize", COORD), ("dwCursorPosition", COORD), ("wAttributes", ctypes.c_ushort),
                ("srWindow", SMALL_RECT), ("dwMaximumWindowSize", COORD)]

def set_console_fullscreen():
    kernel32 = ctypes.windll.kernel32
    hWnd = kernel32.GetConsoleWindow()
    
    # 3 = SW_MAXIMIZE
    ctypes.windll.user32.ShowWindow(hWnd, 3)

# Make the console go fullscreen
set_console_fullscreen()

def start_browser():
    print(Fore.YELLOW + "Starting browser..")
    script_dir = os.path.dirname(os.path.realpath(__file__))
    geckodriver_path = os.path.join(script_dir, "geckodriver.exe")
    firefox_binary_path = 'C:/Program Files/Mozilla Firefox/firefox.exe'
    options = Options()
    options.binary_location = firefox_binary_path
    options.add_argument('-headless')
    # Disable logs
    service = Service(executable_path=geckodriver_path, log_output=os.devnull)
    driver = webdriver.Firefox(service=service, options=options)

    # Navigate to blank TikTok live webpage
    driver.get("https://www.tiktok.com/@lol/live")
    
    return driver
    
def auth(driver):
    print(Fore.YELLOW + "Authenticating..")
    cookies_path = os.path.join(os.getcwd(), 'config', 'cookies.json')

    # Load cookies from the exported cookie file, if its empty then print error and pause
    if os.path.getsize(cookies_path) <= 0:
        print(Fore.RED + "Error: cookies.json is empty. Read the README file!")
        time.sleep(10)
        sys.exit()
    else:
        with open(cookies_path, 'r') as f:
            cookies = json.load(f)

    # Add each cookie to the browser
    for cookie in cookies:
        if 'sameSite' in cookie:
            del cookie['sameSite']
        driver.add_cookie(cookie)

    # Refresh the page to apply cookies
    driver.refresh()
    print(Fore.GREEN + "Successfully authenticated! Starting monitor..")


def loading_spinner(message):
    spinner = ['|', '/', '-', '\\']
    while True:
        for spin in spinner:
            sys.stdout.write(f"\033[K{Fore.GREEN}{message} {spin}{Style.RESET_ALL}\r")
            sys.stdout.flush()
            time.sleep(0.1)

def get_live_users(driver):
    urls = []
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

        candidate_divs = driver.find_elements(By.XPATH, "//div[contains(@class, 'tiktok-3hyjcz-DivSideNavChannelWrapper')]")
        
        following_div = None
        for div in candidate_divs:
            if "Following" in div.text:
                following_div = div
                break
                
        if following_div is not None:
            a_elements = following_div.find_elements(By.TAG_NAME, 'a')
            
            # Start the spinner in a separate thread if you want to run it in parallel with your code
            threading.Thread(target=loading_spinner, args=(f"--> {len(a_elements)} users are currently live.",)).start()
            
            for a in a_elements:
                url = a.get_attribute('href')
                urls.append(url)
        else:
            pass
    except Exception as e:
        print(Fore.RED + f"An unexpected exception occurred: {e}")
    
    return urls

def extract_username(url):
    # Extract the username from the TikTok URL
    parsed_url = urlparse(url)
    username = parsed_url.path.split('/')[1]
    return username.replace("@", "")

def get_room_ids(urls):
    room_and_users = []
    max_retries = 10
    
    # Load ignored_users from the file and create if it doesnt exist
    ignored_users_path = os.path.join(os.getcwd(), 'config', 'lists', 'ignored_users.txt')
    if not os.path.exists(ignored_users_path):
        with open(ignored_users_path, 'w') as f:
            f.write("")
    with open(ignored_users_path, 'r') as f:
        ignored_users = set(line.strip() for line in f.readlines())
    
    for url in urls:
        if not url.startswith('http'):
            url = f"https://{url}"
        
        username = extract_username(url)
        response = None  # Initialize response variable
        
        for i in range(max_retries):
            try:
                response = requests.get(url, timeout=60)
                break  # Successful request, break the retry loop
            except ChunkedEncodingError:
                if i == max_retries - 1:
                    print(f"Failed to fetch {url} after {max_retries} retries.")
                    continue

        # If after all retries, response is still None, skip this URL
        if response is None:
            print(f"Skipping {url} due to failed requests.")
            continue

        content = response.content
        matches = list(re.finditer(b"room_id=(\d+)", content))
        
        if matches:
            longest_room_id = max([match.group(1).decode("utf-8") for match in matches], key=len)
            room_and_users.append((username, longest_room_id))
    
    monitored_users_path = os.path.join(os.getcwd(), 'config', 'lists', 'monitored_users.txt')
    
    # Writing room IDs and usernames to room_ids.txt and overwriting each time
    with open(monitored_users_path, 'w') as f:
        for username, room_id in room_and_users:
            f.write(f"{username} = {room_id}\n")
    
    return room_and_users


# create ../videos directory if it doesn't exist
def create_videos_dir():
    videos_dir = os.path.join(os.getcwd(), '../videos')
    if not os.path.exists(videos_dir):
        os.makedirs(videos_dir)


print(r"""
/************************************************************************************************************
 *                                            ████████▀▀▀████
 *                                            ████████────▀██
 *                                            ████████──█▄──█
 *                                            ███▀▀▀██──█████
 *                                            █▀──▄▄██──█████
 *                                            █──█████──█████
 *                                            █▄──▀▀▀──▄█████
 *                                            ███▄▄▄▄▄███████
 *
 *
 *    ████████╗████████╗ █████╗ ██╗   ██╗████████╗ ██████╗ ██████╗ ███████╗ ██████╗ ██████╗ ██████╗ ██████╗ 
 *    ╚══██╔══╝╚══██╔══╝██╔══██╗██║   ██║╚══██╔══╝██╔═══██╗██╔══██╗██╔════╝██╔════╝██╔═══██╗██╔══██╗██╔══██╗
 *       ██║      ██║   ███████║██║   ██║   ██║   ██║   ██║██████╔╝█████╗  ██║     ██║   ██║██████╔╝██║  ██║
 *       ██║      ██║   ██╔══██║██║   ██║   ██║   ██║   ██║██╔══██╗██╔══╝  ██║     ██║   ██║██╔══██╗██║  ██║
 *       ██║      ██║   ██║  ██║╚██████╔╝   ██║   ╚██████╔╝██║  ██║███████╗╚██████╗╚██████╔╝██║  ██║██████╔╝
 *       ╚═╝      ╚═╝   ╚═╝  ╚═╝ ╚═════╝    ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚═════╝ ╚═╝  ╚═╝╚═════╝ 
 *                                                                                                          
 ************************************************************************************************************/
""")


# Start the browser
driver = start_browser()

create_videos_dir()

# Authenticate
auth(driver)

script_dir = os.path.dirname(os.path.realpath(__file__))
exe_path = os.path.join(script_dir, "livestream_extractor.exe")

# Run the executable without blocking
print(Fore.YELLOW + "Starting livestream extractor..")
subprocess.Popen([exe_path])


# Main loop for fetching TikTok room IDs
while True:
    driver.refresh()
    live_user_urls = get_live_users(driver)
    
    if live_user_urls:  # Only proceed if there are URLs to process
        room_and_users = get_room_ids(live_user_urls)
        #print("Extracted room IDs and usernames:", room_and_users)
    
    time.sleep(10)
