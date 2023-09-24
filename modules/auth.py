from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
import json
import time

# Path to geckodriver.exe
geckodriver_path = './binaries/geckodriver.exe'

# Path to Firefox binary (Modify this path accordingly)
firefox_binary_path = 'C:/Program Files/Mozilla Firefox/firefox.exe'  # Modify this

# Initialize Firefox options
options = Options()
options.binary_location = firefox_binary_path

# Initialize the Service
service = Service(executable_path=geckodriver_path)

# Initialize Firefox browser with the specified service and options
driver = webdriver.Firefox(service=service, options=options)

# Navigate to TikTok live webpage
driver.get("https://www.tiktok.com/@lol/live")

# Give it some time to load (optional but may be necessary depending on network speed)
time.sleep(3)

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