import json
import os
import threading
import requests
import logging
import gc
from colorama import Fore, init
import customtkinter as ctk
import tkinter as tk
from PIL import Image, ImageTk, ImageDraw, ImageOps, UnidentifiedImageError
from io import BytesIO
import tkinter.font as tkFont
import psutil

# Initialize global variables
image_cache = {}  # Global image cache
lock_file_cache = set()  # Global lock file cache
init(autoreset=True)
ctk.set_appearance_mode("dark")  # Set theme for CustomTkinter
stop_threads = False

# Configure logging
logging.basicConfig(filename='app.log', level=logging.ERROR,
                    format='%(asctime)s:%(levelname)s:%(message)s')

script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
json_dir = os.path.join(script_dir, 'json')
lock_files_dir = os.path.join(script_dir, 'lock_files')

def log_memory_usage():
    process = psutil.Process(os.getpid())
    logging.info(f"Memory usage: {process.memory_info().rss / 1024 ** 2:.2f} MB")

# Function to update lock file cache
def update_lock_file_cache():
    global lock_file_cache
    lock_file_cache.clear()
    lock_file_path = 'lock_files'
    if not os.path.exists(lock_file_path):
        os.makedirs(lock_file_path)
    lock_file_cache.update({filename.replace('.lock', '') for filename in os.listdir(lock_files_dir) if filename.endswith('.lock')})
    threading.Timer(30, update_lock_file_cache).start()  # Update lock file cache every 30 seconds

update_lock_file_cache()  # Initialize the lock file cache update

def clear_image_cache():
    global image_cache
    image_cache.clear()  # Clear the cache
    gc.collect()  # Force garbage collection to free up memory
    log_memory_usage()

def clear_all_caches():
    clear_image_cache()
    update_lock_file_cache()  # Refresh the lock file cache
    threading.Timer(300, clear_all_caches).start()  # Schedule this function to run every 5 minutes

def lock_file_exists(username):
    return os.path.exists(os.path.join(lock_files_dir, f'{username}.lock'))

def load_placeholder_image(size):
    placeholder_image = Image.new('RGB', size, (255, 0, 0))  # Red placeholder
    draw = ImageDraw.Draw(placeholder_image)
    draw.ellipse((0, 0) + size, fill=(0, 255, 0))  # Green circle in the placeholder
    return ImageTk.PhotoImage(placeholder_image)

def load_image_from_url_async(url, callback, root, size=(50, 50)):
    def thread_target():
        if url in image_cache:
            root.after(0, lambda: callback(image_cache[url]))
        else:
            try:
                response = requests.get(url)
                response.raise_for_status()
                img = Image.open(BytesIO(response.content))
                img.thumbnail(size)
                mask = Image.new('L', size, 0)
                draw = ImageDraw.Draw(mask)
                draw.ellipse((0, 0) + size, fill=255)
                img = ImageOps.fit(img, mask.size, centering=(0.5, 0.5))
                img.putalpha(mask)
                photo_image = ImageTk.PhotoImage(img)
                image_cache[url] = photo_image
                root.after(0, lambda: callback(photo_image))
            except (requests.RequestException, UnidentifiedImageError, IOError) as e:
                error_message = f"Error loading image from URL {url}: {e}"
                print(error_message)
                logging.error(error_message)
                # Load placeholder image in case of error
                photo_image = load_placeholder_image(size)
                image_cache[url] = photo_image
                root.after(0, lambda: callback(photo_image))
            except Exception as e:
                error_message = f"Unexpected error for URL {url}: {e}"
                print(error_message)
                logging.error(error_message)
                # Load placeholder image in case of unexpected error
                photo_image = load_placeholder_image(size)
                image_cache[url] = photo_image
                root.after(0, lambda: callback(photo_image))
            finally:
                gc.collect()  # Force garbage collection to free up memory
    threading.Thread(target=thread_target).start()

def set_image(index, img, canvas):
    try:
        y_position = index * 80 + 35
        image_id = canvas.create_image(50, y_position, image=img)
        image_references.append(img)
    except Exception as e:
        error_message = f"Failed to allocate bitmap for index {index}: {e}"
        print(error_message)
        logging.error(error_message)

def create_red_square(canvas, root, x, y):
    try:
        size = 8
        square_id = canvas.create_rectangle(x - size//2, y - size//2, x + size//2, y + size//2, fill="red", outline="red")
        return square_id
    except Exception as e:
        error_message = f"Error creating red square at ({x}, {y}): {e}"
        print(error_message)
        logging.error(error_message)

def update_gui(canvas, root, currently_live_label):
    global image_references
    image_references = []

    # Define fonts
    username_font = tkFont.Font(family="Helvetica", size=12, weight="bold")
    recording_font = tkFont.Font(family="Helvetica", size=8)

    # Initialize users as an empty list in case JSON loading fails
    users = []

    try:
        # Adjusted to use the json_dir for the correct path
        live_users_file_path = os.path.join(json_dir, 'live_users.json')
        with open(live_users_file_path, 'r') as file:
            file_content = file.read().strip()
            if file_content:  # Check if the file content is not empty
                users = json.loads(file_content)
            else:
                error_message = "JSON file is empty"
                print(error_message)
                logging.error(error_message)
        total_live_users = len(users)
    except json.JSONDecodeError as e:
        error_message = f"Error decoding JSON: {e}"
        print(error_message)
        logging.error(error_message)
    except Exception as e:
        error_message = f"Unexpected error reading live users: {e}"
        print(error_message)
        logging.error(error_message)

    # Ensure the lock_file_cache is updated.
    update_lock_file_cache()
    currently_recording_count = len(lock_file_cache)

    # Update the label with current recording and live user counts
    currently_live_label.configure(text=f"Currently Recording: {currently_recording_count}/{total_live_users}")

    canvas.delete("all")
    for index, user in enumerate(users):
        y_position = index * 80
        canvas.create_rectangle(0, y_position, canvas.winfo_width(), y_position + 70, fill="#1c1c1c", outline="")
        canvas.create_text(100, y_position + 35, text=user.get('username', 'N/A'), anchor="w", font=username_font, fill="white")
        if user.get('profile_picture'):
            # Use a lambda to correctly pass the index and img to set_image function
            load_image_from_url_async(user['profile_picture'], lambda img, index=index: set_image(index, img, canvas), root)
        if lock_file_exists(user.get('username', '')):
            text_x = canvas.winfo_width() - 35
            square_x = canvas.winfo_width() - 20
            canvas.create_text(text_x, y_position + 35, text="Recording", anchor="e", font=recording_font, fill="white")
            create_red_square(canvas, root, square_x, y_position + 35)

    canvas.config(scrollregion=canvas.bbox("all"))
    root.after(5000, lambda: update_gui(canvas, root, currently_live_label))

def on_mousewheel(event, canvas):
    try:
        canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    except Exception as e:
        error_message = f"Error handling mouse wheel event: {e}"
        print(error_message)
        logging.error(error_message)

def run_gui():
    global stop_threads

    try:
        root = ctk.CTk()
        root.title("TTAutoRecord v4.1.0")
        root.geometry("500x800")

        canvas = tk.Canvas(root, bg="black", highlightthickness=0)
        
        top_frame = ctk.CTkFrame(root, fg_color="black")
        top_frame.pack(side="top", fill="x")

        # Create and pack the label inside the frame
        currently_live_label = ctk.CTkLabel(top_frame, text="Currently Recording: 0/0", fg_color="black", bg_color="black", font=("Helvetica", 18, "bold"), anchor="w")
        currently_live_label.pack(side="left", anchor="nw" , padx=10, pady=1)
        
        scrollbar = ctk.CTkScrollbar(root, command=canvas.yview, fg_color="gray", bg_color="black")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        canvas.bind_all("<MouseWheel>", lambda event: on_mousewheel(event, canvas))
        
        # Pass the label as an argument to update_gui
        root.after(1000, update_gui, canvas, root, currently_live_label)

        def on_closing():
            global stop_threads
            stop_threads = True
            root.destroy()

        root.protocol("WM_DELETE_WINDOW", on_closing)
        root.mainloop()
    except Exception as e:
        error_message = f"Error running GUI: {e}"
        print(error_message)
        logging.error(error_message)

def main():
    clear_all_caches()  # Start the periodic cache clearing function
    run_gui()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Script execution stopped by user.")
    except Exception as e:
        error_message = f"Critical error, stopping script: {e}"
        print(error_message)
        logging.critical(error_message)
