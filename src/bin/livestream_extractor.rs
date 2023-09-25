#![allow(deprecated)]
use reqwest;
use std::time::Duration;
use chrono::Local;
use once_cell::sync::Lazy;
use regex::Regex;
use std::fs;
use std::io::{BufRead, BufReader, Write};
use std::path::Path;
use std::error::Error;
use tokio::time::timeout;
use config::{Config, File, FileFormat};
use std::process::Stdio;


static IPHONE_USER_AGENT: &str = "Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1";
static FFMPEG_PATH: &str = "ffmpeg.exe";
static LOCK_DIRECTORY: &str = "../lock_files";
static RE_M3U8: Lazy<Regex> = Lazy::new(|| Regex::new("https://[^\"']+.m3u8").unwrap());
static RE_FLV: Lazy<Regex> = Lazy::new(|| Regex::new(r#""([^"]+\.flv)""#).unwrap());
static RE_USERNAME: Lazy<Regex> = Lazy::new(|| Regex::new(r#""display_id":"([^"]+)""#).unwrap());

enum FetchResult {
    UrlAndUsername(String, String),
    NotFound,
    NoUrlInResponse,
    NotLive,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
   // hide_console_window();
    let mut config = Config::default();
    config.merge(File::new("./config/config.toml", FileFormat::Toml))?;
    let chunks: usize = config.get("chunks")?;
    let duration: u64 = config.get("duration")?;

    clear_lock_files_directory().await?;
    fs::create_dir_all(LOCK_DIRECTORY)?;

    let client = reqwest::Client::builder()
        .user_agent(IPHONE_USER_AGENT)
        .build()?;

        loop {
            let urls = read_room_ids_from_file()?;
            for chunk in urls.chunks(chunks) {
                let futures: Vec<_> = chunk.iter().map(|url| {
                    download_video(&client, url)
                }).collect();
                futures::future::join_all(futures).await;
                tokio::time::sleep(Duration::from_secs(duration)).await;
    
            }
        }
}


fn read_room_ids_from_file() -> Result<Vec<String>, Box<dyn Error>> {
    let file = fs::File::open("./config/lists/monitored_users.txt")?;
    let reader = BufReader::new(file);
    let room_ids: Vec<String> = reader.lines()
        .filter_map(Result::ok)
        .filter_map(|line| {
            let parts: Vec<&str> = line.split('=').collect();
            if parts.len() == 2 {
                Some(parts[1].trim().to_string())
            } else {
                None
            }
        })
        .collect();
    Ok(room_ids)
}

async fn clear_lock_files_directory() -> Result<(), Box<dyn std::error::Error>> {
    if Path::new(LOCK_DIRECTORY).exists() {
        let mut dir = tokio::fs::read_dir(LOCK_DIRECTORY).await?;
        while let Some(entry) = dir.next_entry().await? {
            if entry.path().is_file() {
                tokio::fs::remove_file(entry.path()).await?;
            }
        }
    }
    Ok(())
}

async fn fetch_room_info_and_extract(client: &reqwest::Client, room_id: &str) -> Result<FetchResult, Box<dyn std::error::Error>> {
    let url = format!("https://webcast.tiktok.com/webcast/room/info/?aid=1988&room_id={}", room_id);
    let response = timeout(Duration::from_secs(10), client.get(&url).send()).await??;

    if response.status() == reqwest::StatusCode::NOT_FOUND {
        return Ok(FetchResult::NotFound);
    }

    let content = response.bytes().await?;
    let text = String::from_utf8_lossy(&content);

    if text.contains("\"status\":2") {
        if let Some(username_cap) = RE_USERNAME.captures(&text) {
            let username = username_cap[1].to_string();
            let mut flv_urls: Vec<String> = Vec::new();
            let m3u8_url = match RE_M3U8.find(&text) {
                Some(m) => Some(m.as_str().to_string()),
                None => None,
            };
            flv_urls.extend(RE_FLV.captures_iter(&text).map(|cap| cap[1].to_string()));

            if let Some(url) = &m3u8_url {
                return Ok(FetchResult::UrlAndUsername(url.clone(), username));
            }

            for flv_url in &flv_urls {
                let response = client.get(flv_url).send().await;

                if let Ok(response) = response {
                    if response.status().is_success() {
                        let flv_url_actual = response.url().to_string();
                        return Ok(FetchResult::UrlAndUsername(flv_url_actual, username));
                    }
                }
            }

            if let Some(flv_url) = flv_urls.first() {
                return Ok(FetchResult::UrlAndUsername(flv_url.to_string(), username));
            }
            
            return Ok(FetchResult::NoUrlInResponse);
        }
    } else {
        return Ok(FetchResult::NotLive);
    }

    Ok(FetchResult::NoUrlInResponse)
}

fn extract_stream_id(url: &str) -> Option<String> {
    let re = Regex::new(r"stream-(\d+)_").unwrap();
    re.captures(url).and_then(|cap| cap.get(1).map(|m| m.as_str().to_string()))
}

async fn download_video(client: &reqwest::Client, room_id: &str) -> Result<(), Box<dyn std::error::Error>> {
    let fetch_result = fetch_room_info_and_extract(client, room_id).await?;

    match fetch_result {
        FetchResult::UrlAndUsername(url, username) => {
            let lock_file_path = format!("{}/{}.lock", LOCK_DIRECTORY, username);
            if Path::new(&lock_file_path).exists() {
                return Ok(());
            }
            fs::File::create(&lock_file_path)?;
            println!("{}: Downloading video for {}", Local::now().format("%Y-%m-%d %H:%M:%S"), username);

            let datetime = Local::now().format("%Y-%m-%d_%H-%M-%S").to_string();
            let date: String = Local::now().format("%Y-%m-%d").to_string();
            let stream_id = extract_stream_id(&url).unwrap_or_else(|| "unknown".to_string());
            let video_folder = format!("../videos/{}/segments/", username);
            fs::create_dir_all(&video_folder)?; // Create the user-specific folder if it doesn't exist

            let video_path = format!("{}/{}_{}_{}.mp4", video_folder, username, stream_id, datetime);
            let output_path = format!("../videos/{}/{}_{}_{}.mp4", username, username, stream_id, date);
            let output_folder = format!("../videos/{}", username);

            //println!("{}: {} is live", Local::now().format("%Y-%m-%d %H:%M:%S"), username);


            //download video
            tokio::spawn(async move {
                let mut ffmpeg = tokio::process::Command::new(FFMPEG_PATH)
                    .arg("-i")
                    .arg(&url)
                    .arg("-reconnect")          // Enable reconnect
                    .arg("1")
                    .arg("-reconnect_at_eof")   // Reconnect at end of file
                    .arg("1")
                    .arg("-reconnect_streamed") // Reconnect streamed
                    .arg("1")
                    .arg("-reconnect_delay_max") // Max reconnect delay in seconds
                    .arg("1")
                    .arg("-timeout")            // Set timeout to 30 seconds
                    .arg("30")
                    .arg("-c")
                    .arg("copy")
                    .arg("-bsf:a")
                    .arg("aac_adtstoasc")
                    .arg(&video_path)
                    .stdout(Stdio::null()) // Redirect stdout to null
                    .stderr(Stdio::null()) // Redirect stderr to null
                    .spawn()
                    .expect("Failed to start ffmpeg process");

                    ffmpeg.wait().await.expect("Failed to wait for ffmpeg process");

            let mut video_files_to_concat: Vec<String> = Vec::new();

            let concat_file_name = format!("concat-{}.txt", stream_id); // Define concat file name

            let mut dir = tokio::fs::read_dir(&video_folder).await.expect("Failed to read video folder");
            while let Some(entry) = dir.next_entry().await.expect("Failed to read video folder") {
                if entry.path().is_file() {
                    let file_name = entry.file_name();
                    let file_name = file_name.to_str().unwrap();
        
                    // Skip adding concat file to the list
                    if file_name.contains(&stream_id) && file_name != concat_file_name {
                        video_files_to_concat.push(file_name.to_string());
                    }
                }
            }

            video_files_to_concat.sort();

            let mut concat_file = fs::File::create(format!("{}concat-{}.txt", video_folder, stream_id)).expect("Failed to create concat file");
            for video_file in &video_files_to_concat {
                Write::write_all(&mut concat_file, format!("file '{}'\n", video_file).as_bytes()).expect("Failed to write to concat file");
            }

            if video_files_to_concat.len() < 2 {
                // If there's only one video, copy and rename it
                let copied_path = format!("{}/{}_{}_{}.mp4", output_folder, username, stream_id, date);
                if let Err(copy_error) = fs::copy(&video_path, &copied_path) {
                    //println!("Failed to copy video to main folder: {}", copy_error);
                    tokio::fs::remove_file(&lock_file_path).await.expect("Failed to remove lock file");
                }
            } else if video_files_to_concat.len() >= 2 {
                println!("{}: Concatenating LIVE segments: {}", Local::now().format("%Y-%m-%d %H:%M:%S"), username);
                let mut ffmpeg = tokio::process::Command::new(FFMPEG_PATH)
                    .arg("-f")
                    .arg("concat")
                    .arg("-safe")
                    .arg("0")
                    .arg("-i")
                    .arg(format!("{}concat-{}.txt", video_folder, stream_id))
                    .arg("-c")
                    .arg("copy")
                    .arg("-y")
                    .arg(&output_path)
                    .stdout(Stdio::null()) // Redirect stdout to null
                    .stderr(Stdio::null()) // Redirect stderr to null
                    .spawn()
                    .expect("Failed to start ffmpeg process");

                ffmpeg.wait().await.expect("Failed to wait for ffmpeg process");

                let concat_file_path = format!("{}/concat.txt", video_folder);
                if Path::new(&concat_file_path).exists() {
                    fs::remove_file(&concat_file_path).expect("Failed to remove concat file");
                    //println!("{}: Video Concatenated: {}", Local::now().format("%Y-%m-%d %H:%M:%S"), username);
                }

            }

            if Path::new(&lock_file_path).exists() {
                tokio::fs::remove_file(&lock_file_path).await.expect("Failed to remove lock file");
            }
        });
        },
        FetchResult::NotFound => {
            println!("{}: {} is not found", Local::now().format("%Y-%m-%d %H:%M:%S"), room_id);
        },
        FetchResult::NoUrlInResponse => {
            println!("{}: No stream URL found for {} - You are most likely rate limited! Tweak your config.toml", Local::now().format("%Y-%m-%d %H:%M:%S"), room_id);
        },
        FetchResult::NotLive => {
            // show nothing
        },
    }

    Ok(())
}