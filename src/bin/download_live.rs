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
    let segment_path = format!("{}/{}_{}_{}.ts", user_segment_dir, username, stream_id, datetime);

    let status = Command::new(ffmpeg_path)
        .arg("-reconnect")
        .arg("1")
        .arg("-reconnect_at_eof")
        .arg("1")
        .arg("-reconnect_streamed")
        .arg("1")
        .arg("-err_detect")
        .arg("ignore_err")
        .arg("-fflags")
        .arg("+genpts+igndts")
        .arg("-i")
        .arg(stream_link)
        .arg("-map")
        .arg("0")
        .arg("-c")
        .arg("copy")
        .arg("-bsf:v")
        .arg("h264_mp4toannexb")
        .arg("-f")
        .arg("mpegts")
        .arg("-y")
        .arg(&segment_path)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()?;
    
    if status.success() {
        sleep(Duration::from_secs(1)).await;
        concatenate_segments(&user_segment_dir, username, &stream_id, ffmpeg_path)?;
    }

    if Path::new(&lock_file_path).exists() {
        fs::remove_file(lock_file_path)?;
    }
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
        .filter(|path| path.is_file() && path.display().to_string().contains(stream_id) && path.extension().unwrap_or_default() == "ts")
        .collect::<Vec<_>>();

    if !paths.is_empty() {
        let concat_file_path = format!("{}/{}_{}_concat.txt", user_segment_dir, username, stream_id);
        let mut concat_file = File::create(&concat_file_path)?;

        for path in &paths {
            writeln!(concat_file, "file '{}'", path.canonicalize()?.display().to_string().replace('\\', "/"))?;
        }

        let datetime = Local::now().format("%Y-%m-%d").to_string();
        let output_path = format!("{}/{}_{}_{}.mp4", VIDEOS_DIR, username, stream_id, datetime);

        let mut cmd = Command::new(ffmpeg_path);
        if paths.len() > 1 {
            cmd.arg("-f").arg("concat").arg("-safe").arg("0").arg("-i").arg(&concat_file_path);
        } else {
            cmd.arg("-i").arg(&paths[0]);
        }

        let status = cmd
            .arg("-c")
            .arg("copy")
            .arg("-y")
            .arg(&output_path)
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()?;

        if !status.success() {
            let now = Local::now().format("%Y-%m-%d %H:%M:%S").to_string();
            println!("{} - ERROR - Failed to finalize video for user {}", now, username);
        }
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
                        fs::write(&lock_file_path, "").ok();
                        
                        let lock = Arc::new(Mutex::new(()));
                        let username = username.clone();
                        let stream_link = stream_link.clone();
                        let handle = runtime.handle().clone();
                        let ffmpeg_path = current_exe_path()?.parent().unwrap().join("ffmpeg.exe");
                        
                        handle.spawn(async move {
                            if let Err(e) = download_livestream(&username, &stream_link, lock, &ffmpeg_path).await {
                                eprintln!(" - ERROR - failed to download livestream for user {}: {}", username, e);
                                let lock_path = format!("{}/{}.lock", LOCK_FILES_DIR, username);
                                fs::remove_file(lock_path).ok();
                            } else {
                                let now = Local::now().format("%Y-%m-%d %H:%M:%S").to_string();
                                println!("{} - INFO - Livestream finished for user: {}", now, username);
                            }
                        });
                        sleep(Duration::from_secs(1)).await;
                    }
                }
            }
            Err(e) => {
                eprintln!(" - ERROR - Failed to read stream links: {}", e);
                sleep(Duration::from_secs(5)).await;
            }
        }
        sleep(Duration::from_secs(3)).await;
    }
}