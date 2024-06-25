import json
import os
import threading
import requests
import logging
import gc
import weakref
from colorama import Fore, init
import customtkinter as ctk
import tkinter as tk
from PIL import Image, ImageTk, ImageDraw, ImageOps, UnidentifiedImageError
from io import BytesIO
import tkinter.font as tkFont
import psutil

image_cache = {}
lock_file_cache = set()
init(autoreset=True)
ctk.set_appearance_mode("dark")
stop_threads = False

logging.basicConfig(filename='gui.log', level=logging.ERROR,
                    format='%(asctime)s:%(levelname)s:%(message)s')

script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
json_dir = os.path.join(script_dir, 'json')
lock_files_dir = os.path.join(script_dir, 'lock_files')

current_live_users = {}
image_references = []

def update_lock_file_cache():
    global lock_file_cache
    lock_file_cache.clear()
    lock_file_path = 'lock_files'
    if not os.path.exists(lock_file_path):
        os.makedirs(lock_file_path)
    lock_file_cache.update({filename.replace('.lock', '') for filename in os.listdir(lock_files_dir) if filename.endswith('.lock')})
    threading.Timer(30, update_lock_file_cache).start()

update_lock_file_cache()

def clear_image_cache():
    global image_cache
    image_cache.clear()
    gc.collect()

def clear_all_caches():
    clear_image_cache()
    update_lock_file_cache()
    gc.collect()
    threading.Timer(300, clear_all_caches).start()

def lock_file_exists(username):
    return os.path.exists(os.path.join(lock_files_dir, f'{username}.lock'))

def load_placeholder_image(size):
    placeholder_image = Image.new('RGB', size, (255, 0, 0))
    draw = ImageDraw.Draw(placeholder_image)
    draw.ellipse((0, 0) + size, fill=(0, 255, 0))
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
                photo_image = load_placeholder_image(size)
                image_cache[url] = photo_image
                root.after(0, lambda: callback(photo_image))
            except Exception as e:
                error_message = f"Unexpected error for URL {url}: {e}"
                print(error_message)
                logging.error(error_message)
                photo_image = load_placeholder_image(size)
                image_cache[url] = photo_image
                root.after(0, lambda: callback(photo_image))
            finally:
                gc.collect()
    threading.Thread(target=thread_target).start()

def set_image(index, img, canvas):
    try:
        y_position = index * 80 + 35
        canvas.create_image(50, y_position, image=img)
        image_references.append(img)  # Store reference to prevent garbage collection
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
    global current_live_users
    image_references = []

    username_font = tkFont.Font(family="Helvetica", size=12, weight="bold")
    recording_font = tkFont.Font(family="Helvetica", size=8)

    users = []

    try:
        live_users_file_path = os.path.join(json_dir, 'live_users.json')
        with open(live_users_file_path, 'r') as file:
            file_content = file.read().strip()
            if file_content:
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

    update_lock_file_cache()
    currently_recording_count = len(lock_file_cache)

    currently_live_label.configure(text=f"Currently Recording: {currently_recording_count}/{total_live_users}")

    new_live_users = {}
    canvas.delete("all")
    for index, user in enumerate(users):
        username = user.get('username', 'N/A')
        y_position = index * 80
        canvas.create_rectangle(0, y_position, canvas.winfo_width(), y_position + 70, fill="#1c1c1c", outline="")
        canvas.create_text(100, y_position + 35, text=username, anchor="w", font=username_font, fill="white")
        if user.get('profile_picture'):
            if username not in current_live_users:
                def callback(photo_image, index=index, username=username):
                    set_image(index, photo_image, canvas)
                    current_live_users[username] = photo_image
                load_image_from_url_async(user['profile_picture'], callback, root)
            else:
                set_image(index, current_live_users[username], canvas)
                image_references.append(current_live_users[username])  # Store reference to prevent garbage collection
        if lock_file_exists(username):
            text_x = canvas.winfo_width() - 35
            square_x = canvas.winfo_width() - 20
            canvas.create_text(text_x, y_position + 35, text="Recording", anchor="e", font=recording_font, fill="white")
            create_red_square(canvas, root, square_x, y_position + 35)
        new_live_users[username] = current_live_users.get(username)

    current_live_users = new_live_users

    canvas.config(scrollregion=canvas.bbox("all"))
    root.after(5000, lambda: update_gui(canvas, root, currently_live_label))
    gc.collect()

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
        root.title("TTAutoRecord v4.1.3")
        root.geometry("500x800")

        canvas = tk.Canvas(root, bg="black", highlightthickness=0)
        
        top_frame = ctk.CTkFrame(root, fg_color="black")
        top_frame.pack(side="top", fill="x")

        currently_live_label = ctk.CTkLabel(top_frame, text="Currently Recording: 0/0", fg_color="black", bg_color="black", font=("Helvetica", 18, "bold"), anchor="w")
        currently_live_label.pack(side="left", anchor="nw", padx=10, pady=1)
        
        scrollbar = ctk.CTkScrollbar(root, command=canvas.yview, fg_color="gray", bg_color="black")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        canvas.bind_all("<MouseWheel>", lambda event: on_mousewheel(event, canvas))
        
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
    clear_all_caches()
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
