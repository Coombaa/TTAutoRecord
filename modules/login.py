import os
import time
import logging
import json
from selenium.common.exceptions import NoSuchElementException, WebDriverException
from selenium.webdriver.common.by import By

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def check_login_status(driver):
    """
    Check if the user is logged in by looking for the login button or a valid username in the profile link.
    """
    try:
        # Check for the login button
        login_button = driver.find_element(By.ID, "nav-login-button")
        if login_button.is_displayed():
            logging.error("User is not logged in.")
            return False
    except NoSuchElementException:
        pass

    try:
        # Check if a profile link is visible, indicating the user is logged in
        profile_link = driver.find_element(By.CSS_SELECTOR, 'a[data-e2e="nav-profile"]')
        username_url = profile_link.get_attribute('href')
        username = username_url.split('/')[-1]
        if username and username != "@":
            logging.info(f"Logged in as: {username}")
            return True
        else:
            raise NoSuchElementException("Profile link found but username is invalid.")
    except NoSuchElementException:
        logging.error("Profile link not found. User is not logged in.")
    
    return False

def save_cookies_to_file(driver, file_name='cookies.json'):
    """
    Save cookies from the current browser session to a JSON file in a 'json' folder one level above the script.
    """
    try:
        parent_directory = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        json_directory = os.path.join(parent_directory, 'json')

        if not os.path.exists(json_directory):
            os.makedirs(json_directory)

        file_path = os.path.join(json_directory, file_name)

        cookies = driver.get_cookies()
        with open(file_path, 'w') as file:
            json.dump(cookies, file)
        logging.info(f"Cookies saved to {file_path}.")
    except Exception as e:
        logging.error(f"Failed to save cookies: {e}")

def launch_login(driver):
    """
    Launches the TikTok login page and waits for the user to log in by checking if the URL contains 'foryou'.
    """
    try:
        driver.get("https://www.tiktok.com/login")
        logging.info("Navigated to TikTok login page.")
        
        # Poll the URL to see if it changes to one containing "foryou"
        logged_in = False
        timeout = 300
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            current_url = driver.current_url
            if "foryou" in current_url:
                logging.info("Login successful.")
                logged_in = True
                driver.get("https://www.tiktok.com/@tiktok/live")
                break
            time.sleep(2)

        if not logged_in:
            logging.info("Waiting for login...")
        else:
            if check_login_status(driver):
                logging.info("Login confirmed.")
                save_cookies_to_file(driver)
                driver.get("https://www.tiktok.com/@tiktok/live")

            else:
                logging.info("Waiting for login...")
    
    except WebDriverException as e:
        logging.error(f"Error occurred during login process: {e}")

