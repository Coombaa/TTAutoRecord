import os
import time
import json
import logging
from urllib.parse import urlparse
from selenium.common.exceptions import WebDriverException, NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .login import check_login_status, launch_login

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

script_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
json_dir = os.path.join(script_dir, 'json')

def browser_operations(driver, window_handle, on_login_success=None, on_login_fail=None):
    driver.switch_to.window(window_handle)

    driver.get("https://www.tiktok.com/@tiktok/live")

    login_successful = False
    
    while True:
        try:
            time.sleep(5)

            # Check if the user is logged in, and if not, prompt for login
            logging.info("Checking login status...")
            if not check_login_status(driver):
                logging.info("User is not logged in. Redirecting to login page...")
                launch_login(driver)

                # Check again after attempting to log in
                if not check_login_status(driver):
                    logging.error("User failed to log in. Retrying in the next iteration...")
                    
                    # Call on_login_fail callback if login fails
                    if on_login_fail is not None and not login_successful:
                        on_login_fail()
                    continue  # Skip this iteration and retry login in the next loop

                logging.info("User successfully logged in after login attempt.")
            else:
                logging.info("User is already logged in.")

            # Trigger on_login_success only once after successful login
            if not login_successful:
                login_successful = True
                logging.info("Login success - triggering get_stream_link.")
                if on_login_success is not None:
                    on_login_success()

            # Continue checking for live users
            logging.info("Refreshing the page to check for live users...")
            driver.refresh()

            # Get the live users and write them to a JSON file
            logging.info("Getting live users...")
            live_user_urls = get_live_users(driver)

            if live_user_urls:
                logging.info(f"Found {len(live_user_urls)} users currently live.")
            else:
                logging.info("No live users found.")

            write_to_json(live_user_urls)
            logging.info("Live users written to JSON file.")

            # Wait for a while before checking again
            logging.info("Waiting for 10 seconds before checking again...")
            time.sleep(10)

        except WebDriverException as e:
            logging.error(f"WebDriverException occurred: {e}")
            time.sleep(5)

        except Exception as e:
            logging.error(f"Unexpected error occurred: {e}")
            time.sleep(5)


def click_element(driver, element):
    try:
        driver.execute_script("arguments[0].scrollIntoView(true);", element)
        element.click()
    except WebDriverException as e:
        logging.error(f"Error clicking element: {e}")

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
    
    logging.info(f"{len(live_users_data)} users currently live.")

def main(driver, window_handle, on_login_success=None):
    return browser_operations(driver, window_handle, on_login_success)

