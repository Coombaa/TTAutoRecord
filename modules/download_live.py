import os
import subprocess
import concurrent.futures
import time
import datetime
import re
import logging
import shutil
from modules.SharedDataStore import shared_stream_links_store


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BINARIES_DIR = os.path.join(BASE_DIR, 'binaries')
FFMPEG_BIN_PATH = os.path.join(BINARIES_DIR, 'ffmpeg.exe')
LOCK_FILES_DIR = os.path.join(BASE_DIR, 'lock_files')
SEGMENTS_DIR = os.path.join(BASE_DIR, 'segments')
VIDEOS_DIR = os.path.join(BASE_DIR, 'videos')

for lock_file in os.listdir(LOCK_FILES_DIR):
    os.remove(os.path.join(LOCK_FILES_DIR, lock_file))

def get_stream_links():
    return [(username, shared_stream_links_store.get_value(username)) for username in shared_stream_links_store.data]


def extract_stream_id(url):
    match = re.search(r'stream-(\d+)_', url)
    return match.group(1) if match else 'unknownid'

def concatenate_segments(username, stream_id):
    user_segment_dir = os.path.join(SEGMENTS_DIR, username)
    segments = [f for f in os.listdir(user_segment_dir) if f.startswith(f"{username}_{stream_id}") and f.endswith(".mp4")]
    
    if len(segments) == 1:
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")
        single_segment_path = os.path.join(user_segment_dir, segments[0])
        output_file = os.path.join(VIDEOS_DIR, f"{username}_{stream_id}_{current_date}.mp4")
        shutil.copy(single_segment_path, output_file)
        logging.info(f"Copied single segment for {username} with stream ID {stream_id}")
    elif len(segments) > 1:
        list_file_path = os.path.join(user_segment_dir, f"{stream_id}_list.txt")
        with open(list_file_path, 'w') as list_file:
            for segment_file in sorted(segments):
                list_file.write(f"file '{os.path.join(user_segment_dir, segment_file)}'\n")

        current_date = datetime.datetime.now().strftime("%Y-%m-%d")
        output_file = os.path.join(VIDEOS_DIR, f"{username}_{stream_id}_{current_date}.mp4")
        ffmpeg_cmd = [
            FFMPEG_BIN_PATH, '-f', 'concat', '-safe', '0',
            '-i', list_file_path, '-c', 'copy', '-y', output_file
        ]
        subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logging.info(f"Concatenation completed for {username} with stream ID {stream_id}")
    else:
        logging.info(f"No segments found for {username} with stream ID {stream_id}, nothing to concatenate or copy.")


def download_livestream(username, stream_link):
    lock_file_path = os.path.join(LOCK_FILES_DIR, f'{username}.lock')
    user_segment_dir = os.path.join(SEGMENTS_DIR, username)
    os.makedirs(user_segment_dir, exist_ok=True)
    stream_id = extract_stream_id(stream_link)
    current_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    segment_path = os.path.join(user_segment_dir, f"{username}_{stream_id}_{current_time}.mp4")

    ffmpeg_cmd = [
        FFMPEG_BIN_PATH, '-i', stream_link,
        '-reconnect', '1', '-reconnect_at_eof', '1',
        '-reconnect_streamed', '1', '-reconnect_delay_max', '1', '-timeout', '30000000',
        '-c', 'copy', '-bsf:a', 'aac_adtstoasc', '-y', segment_path
    ]

    try:
        with open(lock_file_path, 'w') as lock_file:
            lock_file.write('')
        subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logging.info(f"Download completed for {username}.")
    except subprocess.CalledProcessError as e:
        logging.error(f"FFmpeg process error for {username}: {e}")
    finally:
        if os.path.exists(lock_file_path):
            concatenate_segments(username, stream_id)
            os.remove(lock_file_path)
            logging.info(f"Lock file removed and concatenation attempted for {username}.")


def main():
    with concurrent.futures.ThreadPoolExecutor() as executor:
        while True:
            logging.info("Checking for new stream links")
            stream_links = get_stream_links()
            logging.info(f"Found {len(stream_links)} stream links.")

            for username, stream_link in stream_links:
                if stream_link and not os.path.exists(os.path.join(LOCK_FILES_DIR, f'{username}.lock')):
                    executor.submit(download_livestream, username, stream_link)

            time.sleep(3)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Script execution stopped by user.")
    except Exception as e:
        logging.critical(f"Critical error, stopping script: {e}")
