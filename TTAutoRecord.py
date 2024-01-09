import json
import os
import sys
import time
import subprocess
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from urllib.parse import urlparse
from colorama import Fore, init

init(autoreset=True)

def start_browser():
    print(Fore.YELLOW + "Starting browser..")
    script_dir = os.path.dirname(os.path.realpath(__file__))
    geckodriver_path = os.path.join(script_dir, "geckodriver.exe")
    firefox_binary_path = 'C:/Program Files/Mozilla Firefox/firefox.exe'
    options = Options()
    options.binary_location = firefox_binary_path
    options.add_argument('-headless')
    service = Service(executable_path=geckodriver_path, log_output=os.devnull)
    driver = webdriver.Firefox(service=service, options=options)
    driver.get("https://www.tiktok.com/@lol/live")
    return driver

def auth(driver):
    print(Fore.YELLOW + "Authenticating..")
    cookies_path = os.path.join(os.getcwd(), 'config', 'cookies.json')
    if os.path.getsize(cookies_path) <= 0:
        print(Fore.RED + "Error: cookies.json is empty. Read the README file!")
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
        print(Fore.GREEN + "Successfully authenticated! Starting monitor..")

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

        candidate_divs = driver.find_elements(By.XPATH, "//div[contains(@class, 'tiktok-3hyjcz-DivSideNavChannelWrapper')]")
        following_div = None
        for div in candidate_divs:
            if "Following" in div.text:
                following_div = div
                break
        if following_div is not None:
            a_elements = following_div.find_elements(By.TAG_NAME, 'a')
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
        print(f"An unexpected exception occurred: {e}")
    return live_users_data

def extract_username(url):
    parsed_url = urlparse(url)
    username = parsed_url.path.split('/')[1]
    return username.replace("@", "")

def write_to_json(live_users_data, filename='live_users.json'):
    with open(filename, 'w') as file:
        json.dump(live_users_data, file, indent=4)
    print(f"{Fore.GREEN}Live user data written to {filename}")

driver = start_browser()
auth(driver)
script_dir = os.path.dirname(os.path.realpath(__file__))
exe_path = os.path.join(script_dir, "livestream_extractor.exe")
subprocess.Popen([exe_path])

while True:
    driver.refresh()
    live_user_urls = get_live_users(driver)
    write_to_json(live_user_urls)
    time.sleep(10)
