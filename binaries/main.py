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



# Get the current working directory
current_directory = os.getcwd()

# Clear monitored_users.txt
monitored_users_path = os.path.join(current_directory, 'config', 'lists', 'monitored_users.txt')
with open(monitored_users_path, 'w') as f:
    f.write("")

def start_browser():
    print("Starting browser..")
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
    print("Authenticating..")
    cookies_path = os.path.join(os.getcwd(), 'config', 'cookies.json')

    # Load cookies from the exported cookie file
    with open(cookies_path, 'r') as f:
        cookies = json.load(f)

    # Add each cookie to the browser
    for cookie in cookies:
        if 'sameSite' in cookie:
            del cookie['sameSite']
        driver.add_cookie(cookie)

    # Refresh the page to apply cookies
    driver.refresh()
    print("Successfully authenticated! Starting monitor..")


def get_live_users(driver):
    urls = []
    try:
        time.sleep(5)
        see_all_btn = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-e2e='live-side-more-button']"))
        )
        see_all_btn.click()
        # print("Clicked 'See All'.")
    except:
        # print("'See All' button not found. Proceeding to find 'Following' links.")
        pass
    
    try:
        # Get all divs that might be a container for Following links.
        candidate_divs = driver.find_elements(By.XPATH, "//div[contains(@class, 'tiktok-3hyjcz-DivSideNavChannelWrapper')]")
        
        # Find the div that actually contains the 'Following' text
        following_div = None
        for div in candidate_divs:
            if "Following" in div.text:
                following_div = div
                break
                
        if following_div is not None:
            # Find all anchor elements within the 'Following' div
            a_elements = following_div.find_elements(By.TAG_NAME, 'a')
            print(f"{len(a_elements)} users are currently live.")
            
            for a in a_elements:
                url = a.get_attribute('href')
                urls.append(url)
                #print(url)
        else:
            print("No div containing 'Following' found.")
    except Exception as e:
        #print(f"An exception occurred while locating 'Following' links: {e}")
        pass
    
    return urls

def extract_username(url):
    # Extract the username from the TikTok URL
    parsed_url = urlparse(url)
    username = parsed_url.path.split('/')[1]
    return username.replace("@", "")

def get_room_ids(urls):
    room_and_users = []
    max_retries = 10
    
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


# Start the browser
driver = start_browser()

# Authenticate
auth(driver)

script_dir = os.path.dirname(os.path.realpath(__file__))
exe_path = os.path.join(script_dir, "livestream_extractor.exe")

# Run the executable without blocking
print("Starting livestream extractor..")
subprocess.Popen([exe_path])


# Main loop for fetching TikTok room IDs
while True:
    driver.refresh()
    live_user_urls = get_live_users(driver)
    
    if live_user_urls:  # Only proceed if there are URLs to process
        room_and_users = get_room_ids(live_user_urls)
        #print("Extracted room IDs and usernames:", room_and_users)
    
    time.sleep(10)
