use regex::Regex;
use reqwest::{self, Client, Proxy};
use std::error::Error;
use std::io::{BufReader, Write, BufRead};
use std::fs::File;
use std::time::Instant;
use futures::stream::{self, StreamExt};
use tokio::sync::Semaphore;
use std::fs::OpenOptions;
use rand::seq::SliceRandom;
use std::sync::Arc;
use rand::Rng;
use tokio::time::Duration;
use tokio::time::sleep;
use config::{Config, File as ConfigFile};
use serde::Deserialize;

#[derive(Debug, Deserialize, Clone)]
struct ConfigData {
    retry_delay_min: u64,
    retry_delay_max: u64,
    id_check_concurrency: usize,
    live_urls_recheck: u64,
}

const USER_AGENTS: &[&str] = &[
    "Mozilla/5.0 (iPhone; U; CPU iPhone OS 4_3_5 like Mac OS X; en-us) AppleWebKit/533.17.9 (KHTML, like Gecko) Version/5.0.2 Mobile/8L1 Safari/6533.18.5",
    "Mozilla/5.0 (iPhone; U; CPU iPhone OS 3_1_3 like Mac OS X; en-us) AppleWebKit/528.18 (KHTML, like Gecko) Version/4.0 Mobile/7E18 Safari/528.16",
    "Mozilla/5.0 (iPhone; U; CPU iPhone OS 4_3_3 like Mac OS X; es-es) AppleWebKit/533.17.9 (KHTML, like Gecko) Version/5.0.2 Mobile/8J2 Safari/6533.18.5",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 5_0 like Mac OS X) AppleWebKit/534.46 (KHTML, like Gecko) Mobile/9A5313e",
    "Mozilla/5.0 (iPhone; U; CPU iPhone OS 4_3_3 like Mac OS X; es-es) AppleWebKit/533.17.9 (KHTML, like Gecko) Version/5.0.2 Mobile/8J2 Safari/6533.18.5",
    "Mozilla/5.0 (iPhone; U; CPU iPhone OS 4_3_5 like Mac OS X; en-us) AppleWebKit/533.17.9 (KHTML, like Gecko) Version/5.0.2 Mobile/8L1 Safari/6533.18.5",
    "Mozilla/5.0 (iPhone; U; CPU iPhone OS 4_3_5 like Mac OS X; en-us) AppleWebKit/533.17.9 (KHTML, like Gecko) Mobile/8L1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 5_0 like Mac OS X) AppleWebKit/534.46 (KHTML, like Gecko) Version/5.1 Mobile/9A5313e Safari/7534.48.3",
    "Mozilla/5.0 (iPhone; U; CPU iPhone OS 3_1_3 like Mac OS X; en-us) AppleWebKit/528.18 (KHTML, like Gecko) Version/4.0 Mobile/7E18 Safari/528.16",
    "Mozilla/5.0 (iPhone; U; CPU iPhone OS 4_3_3 like Mac OS X; en-us) AppleWebKit/533.17.9 (KHTML, like Gecko) Mobile/8J2",
    "Mozilla/5.0 (iPhone; U; CPU iPhone OS 4_3_5 like Mac OS X; en-us) AppleWebKit/533.17.9 (KHTML, like Gecko) Version/5.0.2 Mobile/8L1 Safari/6533.18.5",
    "Mozilla/5.0 (iPhone; U; CPU iPhone OS 3_1_3 like Mac OS X; en-us) AppleWebKit/528.18 (KHTML, like Gecko) Version/4.0 Mobile/7E18 Safari/528.16",
    "Mozilla/5.0 (iPhone; U; CPU iPhone OS 3_1_3 like Mac OS X; en-us) AppleWebKit/528.18 (KHTML, like Gecko) Version/4.0 Mobile/7E18 Safari/528.16",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 5_0 like Mac OS X) AppleWebKit/534.46 (KHTML, like Gecko) Mobile/9A5313e",
];


const RETRIES: usize = 5; // Define the number of retries here

fn get_random_user_agent() -> &'static str {
    USER_AGENTS.choose(&mut rand::thread_rng()).expect("Failed to select a user agent")
}

async fn read_lives_from_file(file_path: &str) -> Result<Vec<String>, Box<dyn Error + Send + Sync>> {
    let file = File::open(file_path)?;
    let reader = BufReader::new(file);
    let lines: Vec<String> = reader.lines().filter_map(Result::ok).collect();
    Ok(lines)
}

async fn fetch_live_page(_client: &Client, url: &str, proxy: &str, config_data: &ConfigData) -> Result<Option<(String, String)>, Box<dyn Error + Send + Sync>> {
    let username_regex = Regex::new(r"@([a-zA-Z0-9_]+)").expect("Failed to create username regex");
    let room_id_regex = Regex::new(r"room_id=(\d+)").expect("Failed to create room ID regex");

    for retry in 0..RETRIES {
        //println!("Debug: Attempt {} for URL: {}", retry + 1, url);
    
        let parts: Vec<&str> = proxy.split(':').collect();
        let proxy_ip = parts[0];
        let proxy_port = parts[1];
        let proxy_url = format!("http://{}:{}", proxy_ip, proxy_port);
        let proxy = Proxy::http(&proxy_url)?;

        // Use a random user agent for each request
        let user_agent = get_random_user_agent();

        let client = Client::builder().proxy(proxy.clone()).build()?;
        let response_result: Result<reqwest::Response, reqwest::Error> = client.get(url)
            .header("User-Agent", user_agent)
            .send()
            .await;

            if retry < RETRIES - 1 {
                let retry_delay = rand::thread_rng().gen_range(config_data.retry_delay_min..=config_data.retry_delay_max);
                sleep(Duration::from_millis(retry_delay)).await;
            }

        // Add a delay here to allow the page to load
       // sleep(Duration::from_secs(5)).await;


        if let Ok(response) = response_result {
            let mut response_body = response.bytes_stream();
            let mut html_content = Vec::new();
            let mut username: Option<String> = None;
            let mut room_id: Option<String> = None;

            while let Some(chunk) = response_body.next().await {
                let chunk = chunk?;
                html_content.extend(&chunk);
                let html_str = String::from_utf8_lossy(&html_content);

                if username.is_none() {
                    if let Some(captures) = username_regex.captures(&html_str) {
                        username = captures.get(1).map(|m| m.as_str().to_string());
                        //println!("Debug: Found username: {:?}", username); // Logging when username is found
                    }
                }

                if room_id.is_none() {
                    if let Some(captures) = room_id_regex.captures(&html_str) {
                        room_id = captures.get(1).map(|m| m.as_str().to_string());
                        println!("Debug: Found room_id: {:?}", room_id); // Logging when room_id is found
                    }
                }

                if let (Some(_), Some(_)) = (&username, &room_id) {
                    //println!("Debug: Found both username and room_id, returning");
                    return Ok(Some((username.unwrap(), room_id.unwrap())));
                }
            }

            if let (Some(_), Some(_)) = (&username, &room_id) {
                //println!("Debug: Found both username and room_id outside loop, returning");
                return Ok(Some((username.unwrap(), room_id.unwrap())));
            }

            // Add a delay to allow more time for the page to load
           //sleep(Duration::from_secs(10)).await;
          

        } else {
        }
    }

    println!("WARNING: All retries failed for URL: {} - Adjust your settings!", url);
    Err(Box::new(std::io::Error::new(std::io::ErrorKind::Other, "All retries failed")))
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error + Send + Sync>> {
    let mut config = Config::default();
    config.merge(ConfigFile::with_name("../config/config.toml"))?;

    let config_data: ConfigData = config.try_into()?;

    let client = Client::builder()
        .timeout(Duration::from_secs(30))
        .connection_verbose(true)
        .build()
        .map_err(|e| Box::new(e) as Box<dyn Error + Send + Sync>)?;

    let semaphore = Arc::new(Semaphore::new(config_data.id_check_concurrency));

    loop {
        let start_time = Instant::now();
        let proxies = read_lives_from_file("../config/lists/proxies.txt").await?;
        let urls = read_lives_from_file("../config/lists/live_urls.txt").await?;
        
        let url_stream = stream::iter(urls);

        let extracted_data: Vec<_> = url_stream
            .map(|url| {
                let client = client.clone();
                let semaphore = Arc::clone(&semaphore);
                let proxy = proxies.choose(&mut rand::thread_rng()).unwrap().clone();
                let config_data = config_data.clone();
                
                async move {
                    let permit = semaphore.acquire().await.expect("acquire permit");
                    let _permit = permit;
                    fetch_live_page(&client, &url, &proxy, &config_data).await.unwrap_or(None)
                }
            })
            .buffer_unordered(config_data.id_check_concurrency)
            .collect()
            .await;

        let mut monitored_users_file = OpenOptions::new().write(true).truncate(true).open("../config/lists/room_ids.txt")?;

        for entry in extracted_data.iter() {
            if let Some((username, room_id)) = entry {
                writeln!(monitored_users_file, "{} = {}", username, room_id)?;
            }
        }

        let elapsed_time = start_time.elapsed();
        println!("All users checked in {:.2} seconds!", elapsed_time.as_secs_f64());

        println!("Waiting for {} seconds before the next cycle.", config_data.live_urls_recheck);
        sleep(Duration::from_secs(config_data.live_urls_recheck)).await;
    }
}