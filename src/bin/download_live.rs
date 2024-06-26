use chrono::Local;
use regex::Regex;
use std::collections::HashMap;
use std::env;
use std::fs::{self, File};
use std::io::{self, Read, Write};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::Arc;
use tokio::sync::Mutex;
use tokio::time::{sleep, Duration};
use tokio::runtime::Builder;

static STREAM_LINKS_JSON_PATH: &str = "../json/stream_links.json";
static LOCK_FILES_DIR: &str = "../lock_files";
static SEGMENTS_DIR: &str = "../segments";
static VIDEOS_DIR: &str = "../videos";

async fn clear_lock_files(directory: &str) -> std::io::Result<()> {
    let paths = fs::read_dir(directory)?;
    for path in paths {
        let path = path?.path();
        if path.is_file() && path.extension().and_then(|s| s.to_str()) == Some("lock") {
            fs::remove_file(path)?;
        }
    }
    Ok(())
}

async fn read_stream_links() -> Result<HashMap<String, String>, Box<dyn std::error::Error>> {
    let mut contents = String::new();
    File::open(STREAM_LINKS_JSON_PATH)?.read_to_string(&mut contents)?;
    Ok(serde_json::from_str(&contents)?)
}

async fn download_livestream(username: &str, stream_link: &str, lock: Arc<Mutex<()>>, ffmpeg_path: &Path) -> Result<(), Box<dyn std::error::Error>> {
    let _lock = lock.lock().await;
    let lock_file_path = format!("{}/{}.lock", LOCK_FILES_DIR, username);
    let user_segment_dir = format!("{}/{}", SEGMENTS_DIR, username);
    fs::create_dir_all(&user_segment_dir)?;

    let stream_id = extract_stream_id(stream_link);
    let datetime = Local::now().format("%Y-%m-%d_%H-%M-%S").to_string();
    let segment_path = format!("{}/{}_{}_{}.mp4", user_segment_dir, username, stream_id, datetime);

    let status = Command::new(ffmpeg_path)
        .arg("-i")
        .arg(stream_link)
        .arg("-c")
        .arg("copy")
        .arg("-bsf:a")
        .arg("aac_adtstoasc")
        .arg("-y")
        .arg(&segment_path)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()?;
    
    if status.success() {
        sleep(Duration::from_secs(1)).await;
        concatenate_segments(&user_segment_dir, username, &stream_id, ffmpeg_path)?;
        sleep(Duration::from_secs(1)).await;
    }

    fs::remove_file(lock_file_path)?;
    Ok(())
}

fn extract_stream_id(url: &str) -> String {
    Regex::new(r"stream-(\d+)_")
        .unwrap()
        .captures(url)
        .and_then(|caps| caps.get(1).map(|m| m.as_str().to_string()))
        .unwrap_or_else(|| "unknownid".to_string())
}

fn concatenate_segments(user_segment_dir: &str, username: &str, stream_id: &str, ffmpeg_path: &Path) -> io::Result<()> {
    let paths = fs::read_dir(user_segment_dir)?
        .filter_map(|entry| entry.ok())
        .map(|entry| entry.path())
        .filter(|path| path.is_file() && path.display().to_string().contains(stream_id) && path.extension().unwrap_or_default() == "mp4")
        .collect::<Vec<_>>();

    if paths.len() > 0 {
        let concat_file_path = format!("{}/{}_{}_concat.txt", user_segment_dir, username, stream_id);
        let mut concat_file = File::create(&concat_file_path)?;

        let _now = Local::now().format("%Y-%m-%d %H:%M:%S").to_string();

        for path in &paths {
            writeln!(concat_file, "file '{}'", path.canonicalize()?.display().to_string().replace('\\', "/"))?;
        }

        if paths.len() > 1 {
            let datetime = Local::now().format("%Y-%m-%d").to_string();
            let output_path = format!("{}/{}_{}_{}.mp4", VIDEOS_DIR, username, stream_id, datetime);
            let status = Command::new(ffmpeg_path)
                .arg("-f")
                .arg("concat")
                .arg("-safe")
                .arg("0")
                .arg("-i")
                .arg(&concat_file_path)
                .arg("-c")
                .arg("copy")
                .arg("-y")
                .arg(&output_path)
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .status()?;

            if !status.success() {
                let now = Local::now().format("%Y-%m-%d %H:%M:%S").to_string();
                println!("{} - ERROR - Error concatenating videos for user {} with stream id {}", now, username, stream_id);
            }
        } else {
            let datetime = Local::now().format("%Y-%m-%d").to_string();
            let single_output_path = format!("{}/{}_{}_{}.mp4", VIDEOS_DIR, username, stream_id, datetime);
            fs::copy(&paths[0], &single_output_path)?;
            let _now = Local::now().format("%Y-%m-%d %H:%M:%S").to_string();
        }
    } else {
        let now = Local::now().format("%Y-%m-%d %H:%M:%S").to_string();
        println!("{} - ERROR - No valid segments found for user {} with stream id {}", now, username, stream_id);
    }

    Ok(())
}

fn current_exe_path() -> Result<PathBuf, Box<dyn std::error::Error>> {
    Ok(env::current_exe()?)
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let lock_files_dir = "../lock_files";
    let segments_dir = "../segments";
    let videos_dir = "../videos";

    // Clear .lock files from lock_files directory
    if let Err(e) = clear_lock_files(lock_files_dir).await {
        eprintln!(" - ERROR - Failed to clear lock files: {}", e);
    }

    fs::create_dir_all(lock_files_dir)?;
    fs::create_dir_all(segments_dir)?;
    fs::create_dir_all(videos_dir)?;

    let runtime = Builder::new_multi_thread()
        .worker_threads(128)
        .enable_all()
        .build()
        .unwrap();

    loop {
        match read_stream_links().await {
            Ok(links) => {
                for (username, stream_link) in links.iter() {
                    let lock_file_path = format!("{}/{}.lock", lock_files_dir, username);
                    if !Path::new(&lock_file_path).exists() {
                        let now = Local::now().format("%Y-%m-%d %H:%M:%S").to_string();
                        println!("{} - INFO - Downloading livestream for user: {}", now, username);
                        if let Err(e) = fs::write(&lock_file_path, "") {
                            eprintln!("- ERROR - Error creating lock file for user {}: {}", username, e);
                            continue;
                        }
                        let lock = Arc::new(Mutex::new(()));
                        let username = username.clone();
                        let stream_link = stream_link.clone();
                        let handle = runtime.handle().clone();
                        let ffmpeg_path = current_exe_path()?.parent().unwrap().join("ffmpeg.exe");
                        handle.spawn(async move {
                            if let Err(e) = download_livestream(&username, &stream_link, lock, &ffmpeg_path).await {
                                eprintln!(" - ERROR - failed to download livestream for user {}: {}", username, e);
                            } else {
                                let now = Local::now().format("%Y-%m-%d %H:%M:%S").to_string();
                                println!("{} - INFO - Livestream downloaded successfully for user: {}", now, username);
                            }
                        });
                        sleep(Duration::from_secs(1)).await;
                    }
                }
            }
            Err(e) => {
                eprintln!(" - ERROR - Failed to read stream links: {}", e);
                sleep(Duration::from_secs(3)).await;
                continue; // Skip this loop iteration and try again
            }
        }
        sleep(Duration::from_secs(3)).await;
    }
}
