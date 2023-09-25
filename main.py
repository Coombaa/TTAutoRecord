from modules import browser
from modules.download import thread_function
import threading
import time

# Start the download thread
download_thread = threading.Thread(target=thread_function)
download_thread.daemon = True
download_thread.start()

# Start the browser
driver = browser.start_browser()

# Authenticate
browser.auth(driver)

# Main loop for fetching TikTok room IDs
while True:
    driver.refresh()
    live_user_urls = browser.get_live_users(driver)
    
    if live_user_urls:  # Only proceed if there are URLs to process
        room_ids = browser.get_room_ids(live_user_urls)
        print("Extracted room IDs:", room_ids)
    
    time.sleep(10)
