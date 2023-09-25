import requests
import time
import threading
import subprocess
import os
import re
from datetime import datetime

def run_ffmpeg(cmd, output_file):
    try:
        process = subprocess.Popen(cmd + [output_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        process.wait()
    except subprocess.CalledProcessError as e:
        print(f"An error occurred while downloading the stream. Error code: {e.returncode}")

def download_stream(username, m3u8_link, room_id, flv_link=None):
    print(f"Downloading stream for {username}")

    bypass_file = "./m3u8_bypass.txt"
    if os.path.exists(bypass_file):
        with open(bypass_file, 'r') as f:
            bypass_users = f.read().strip().split('\n')
            if username in bypass_users:
                print(f"Skipping M3U8 download for {username} as they are in the bypass list.")
                m3u8_link = None

    ffmpeg_path = './binaries/ffmpeg.exe'
    downloads_dir = "./downloads/segments"
    current_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

    lockfile_dir = "./locks"
    lockfile_path = f"{lockfile_dir}/{username}.lock"

    if not os.path.exists(lockfile_dir):
        os.makedirs(lockfile_dir)
    if not os.path.exists(downloads_dir):
        os.makedirs(downloads_dir)
    if not os.path.exists(ffmpeg_path):
        print(f"ffmpeg not found at {ffmpeg_path}. Please make sure it's installed and the path is correct.")
        return
    if os.path.exists(lockfile_path):
        print(f"Skipping download for {username}, lockfile exists.")
        return

    with open(lockfile_path, 'a') as f:
        f.close()

    cmd = [
        ffmpeg_path,
        "-i", m3u8_link,
        "-reconnect", "1",
        "-reconnect_at_eof", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "1",
        "-timeout", "30",
        "-c", "copy",
        "-bsf:a", "aac_adtstoasc"
    ]

    output_file_mp4 = f"{downloads_dir}/{username}_{current_time}_{room_id}.mp4"

    if m3u8_link:
        for attempt in range(12):
            run_ffmpeg(cmd, output_file_mp4)
            
            if os.path.exists(output_file_mp4) and os.path.getsize(output_file_mp4) > 0:
                break
            else:
                print(f"M3U8 download attempt {attempt + 1} failed for {username}. Retrying...")
                time.sleep(10)

    if flv_link:
        if not os.path.exists(output_file_mp4) or os.path.getsize(output_file_mp4) == 0:
            print(f"M3U8 download failed after 12 attempts for {username}. Attempting FLV fallback.")
            with open(bypass_file, 'a') as f:
                f.write(f"{username}\n")
            
            cmd[2] = flv_link
            output_file_flv = f"{downloads_dir}/{username}_{current_time}_{room_id}.flv"
            run_ffmpeg(cmd, output_file_flv)

    if os.path.exists(lockfile_path):
        os.remove(lockfile_path)

        try:
            video_files = [f for f in os.listdir(downloads_dir) if re.match(f"{username}_.*_{room_id}.(mp4|flv)", f)]
            video_files.sort()

            if len(video_files) > 1:
                extensions = [os.path.splitext(video_file)[1][1:] for video_file in video_files]
                common_extension = max(set(extensions), key=extensions.count)

                concat_file_path = f"{downloads_dir}/concat_list_{room_id}.txt"

                print(f"Creating concat list at: {os.path.abspath(concat_file_path)}")

                with open(concat_file_path, 'w') as f:
                    for video_file in video_files:
                        f.write(f"file '{video_file}'\n")

                output_concat_file = f"./downloads/{username}_{room_id}_TTAutoRecord.{common_extension}"
                concat_cmd = [
                    ffmpeg_path,
                    "-f", "concat",
                    "-safe", "0",
                    "-i", concat_file_path,
                    "-c", "copy",
                    output_concat_file
                ]
                
                subprocess.run(concat_cmd, cwd=downloads_dir)

                for video_file in video_files:
                    os.remove(f"{downloads_dir}/{video_file}")
                os.remove(concat_file_path)
        except Exception as e:
            print(f"An error occurred while concatenating videos for Room_ID {room_id}: {e}")

def fetch_m3u8_links(room_ids):
    m3u8_links = {}
    flv_links = {}
    for room_id in room_ids:
        url = f"https://webcast.tiktok.com/webcast/room/info/?aid=1988&room_id={room_id}"
        response = requests.get(url)
        content = response.text

        try:
            username_match = re.search(r'"display_id":"(.*?)"', content)
            m3u8_match = re.search(r'"hls_pull_url":"(.*?)"', content)
            flv_match = re.search(r'"FULL_HD1":"(.*?\.flv)"', content)
            
            username = username_match.group(1) if username_match else "unknown"
            
            if m3u8_match:
                m3u8_links[username] = m3u8_match.group(1)
            if flv_match:
                flv_links[username] = flv_match.group(1)
        except Exception as e:
            print(f"An error occurred while processing room_id {room_id}: {e}")

    return m3u8_links, flv_links

def thread_function():
    while True:
        try:
            with open('room_ids.txt', 'r') as f:
                room_ids = f.read().strip().split('\n')

            if room_ids:
                m3u8_links, flv_links = fetch_m3u8_links(room_ids)
                
                for room_id in room_ids:
                    for username, m3u8_link in m3u8_links.items():
                        flv_link = flv_links.get(username, None)
                        lockfile_path = f"./locks/{username}.lock"
                        
                        if not os.path.exists(lockfile_path):
                            threading.Thread(target=download_stream, args=(username, m3u8_link, room_id, flv_link)).start()
            
            time.sleep(15)
        except Exception as e:
            print(f"An error occurred in thread_function: {e}")

if __name__ == "__main__":
    x = threading.Thread(target=thread_function)
    x.start()
