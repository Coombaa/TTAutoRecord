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

def start_browser():

    # Path to geckodriver.exe
    geckodriver_path = './binaries/geckodriver.exe'

    # Path to Firefox binary (Modify this path accordingly)
    firefox_binary_path = 'C:/Program Files/Mozilla Firefox/firefox.exe'  # Modify this

    # Initialize Firefox options
    options = Options()
    options.binary_location = firefox_binary_path

    # Enable headless mode
    options.headless = True

    # Initialize the Service
    service = Service(executable_path=geckodriver_path)

    # Initialize Firefox browser with the specified service and options
    driver = webdriver.Firefox(service=service, options=options)

    # Navigate to TikTok live webpage
    driver.get("https://www.tiktok.com/@lol/live")
    
    return driver
    
def auth(driver):

    # Load cookies from the exported cookie file
    with open('cookies.json', 'r') as f:
        cookies = json.load(f)

    # Add each cookie to the browser
    for cookie in cookies:
        if 'sameSite' in cookie:
            del cookie['sameSite']
        driver.add_cookie(cookie)

    # Refresh the page to apply cookies
    driver.refresh()

def get_live_users(driver):
    urls = []
    try:
        time.sleep(5)
        see_all_btn = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-e2e='live-side-more-button']"))
        )
        see_all_btn.click()
        print("Clicked 'See All'.")
    except:
        print("'See All' button not found. Proceeding to find 'Following' links.")

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
            print(f"Found {len(a_elements)} links in the 'Following' section.")
            
            for a in a_elements:
                url = a.get_attribute('href')
                urls.append(url)
                print(url)
        else:
            print("No div containing 'Following' found.")
    except Exception as e:
        print(f"An exception occurred while locating 'Following' links: {e}")
    
    return urls

def extract_username(url):
    # Extract the username from the TikTok URL
    parsed_url = urlparse(url)
    username = parsed_url.path.split('/')[1]
    return username.replace("@", "")

def get_room_ids(urls):
    room_and_users = []
    for url in urls:
        if not url.startswith('http'):
            url = f"https://{url}"
        
        username = extract_username(url)
        response = requests.get(url)
        content = response.content
        matches = list(re.finditer(b"room_id=(\d+)", content))
        
        if matches:
            longest_room_id = max([match.group(1).decode("utf-8") for match in matches], key=len)
            room_and_users.append((username, longest_room_id))
    
    # Writing room IDs and usernames to room_ids.txt and overwriting each time
    with open('./config/lists/monitored_users.txt', 'w') as f:
        for username, room_id in room_and_users:
            f.write(f"{username} = {room_id}\n")
    return room_and_users


# Start the browser
driver = start_browser()

# Authenticate
auth(driver)

# Main loop for fetching TikTok room IDs
while True:
    driver.refresh()
    live_user_urls = get_live_users(driver)
    
    if live_user_urls:  # Only proceed if there are URLs to process
        room_and_users = get_room_ids(live_user_urls)
        print("Extracted room IDs and usernames:", room_and_users)
    
    time.sleep(10)
