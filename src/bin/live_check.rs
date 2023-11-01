use fantoccini::{ClientBuilder, Locator, Client};
use serde_json::{map::Map, Value};
use std::{
    env,
    fs::{self, OpenOptions, File},
    io::{self, BufReader, Write},
    path::PathBuf,
    process::{Command, Child},
    error::Error,
    time::Duration
};
use cookie::Cookie;
use tokio::time::sleep;
use tokio_util::sync::CancellationToken;
use std::sync::Arc;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let mut geckodriver_path = env::current_exe()?
        .parent()
        .ok_or("Failed to get the executable's directory")?
        .to_path_buf();

    geckodriver_path.push("binaries");
    geckodriver_path.push("geckodriver.exe");

    let _geckodriver: Child = Command::new(geckodriver_path)
        .spawn()
        .expect("Failed to start geckodriver");

    let mut capabilities = Map::new();
    let options = serde_json::json!({ "args": ["--headless"] });
    capabilities.insert("moz:firefoxOptions".to_string(), options.clone());

    let client = ClientBuilder::native()
        .capabilities(capabilities)
        .connect("http://localhost:4444")
        .await
        .map_err(|e| format!("Failed to connect: {}", e))?;

    let live_url = "https://www.tiktok.com/@lol/live";
    client.goto(live_url).await.expect("Failed to navigate");

    let cookies_path = get_config_path("cookies.json")?;
    let cookies_file = File::open(&cookies_path).expect("Failed to open cookies.json");
    let reader = BufReader::new(cookies_file);
    let cookies: Value = serde_json::from_reader(reader).expect("Failed to parse cookies.json");

    for cookie in cookies.as_array().expect("Failed to get cookie array") {
        if let Value::Object(c) = cookie {
            let name_str = c["name"].as_str().expect("Failed to get cookie name").to_string();
            let value_str = c["value"].as_str().expect("Failed to get cookie value").to_string();
            let domain_str = c["domain"].as_str().expect("Failed to get cookie domain").to_string();
            let path_str = c["path"].as_str().unwrap_or("/").to_string();
            let secure = c["secure"].as_bool().unwrap_or(false);
            let http_only = c["httpOnly"].as_bool().unwrap_or(false);
            let cookie = Cookie::build(name_str, value_str)
                .domain(domain_str)
                .path(path_str)
                .secure(secure)
                .http_only(http_only)
                .finish();
            client.add_cookie(cookie).await.expect("Failed to add cookie");
        }
    }

    client.refresh().await.expect("Failed to refresh");
    sleep(Duration::from_secs(5)).await;

    let cancel_token = Arc::new(CancellationToken::new());

    loop {
        match get_live_users(&mut client.clone(), cancel_token.clone()).await {
            Ok(_) => {},
            Err(e) => eprintln!("Error: {}", e),
        }

        client.refresh().await.expect("Failed to refresh");
        sleep(Duration::from_secs(10)).await;
    }
}

fn get_config_path(filename: &str) -> Result<PathBuf, Box<dyn Error + Send + Sync>> {
    let mut config_path = env::current_exe()?
        .parent()
        .ok_or("Failed to get the executable's directory")?
        .to_path_buf();
    config_path.push("config");
    config_path.push(filename);
    Ok(config_path)
}

async fn get_live_users(client: &mut Client, cancel_token: Arc<CancellationToken>) -> Result<(), Box<dyn Error + Send + Sync>> {
    let _ = cancel_token;
    #[allow(deprecated)]
    let following_div = client.wait_for_find(Locator::Css("div.tiktok-abirwa-DivSideNavChannel")).await?;

    match client.find(Locator::Css("div[data-e2e='live-side-more-button']")).await {
        Ok(btn) => {
            btn.click().await?;
        }
        Err(_) => {}
    }

    let a_elements = following_div.find_all(Locator::Css("a")).await?;
    let mut usernames = Vec::new();
    for a in a_elements {
        match a.find(Locator::Css("span[data-e2e='live-side-nav-name']")).await {
            Ok(span) => {
                let username = span.text().await?;
                usernames.push(username);
            },
            Err(_) => {
                eprintln!("Failed to find username span");
            }
        }
    }

    // Ensure the config/lists directory exists
    let mut file_path = get_config_path("lists").expect("Failed to get config path");
    fs::create_dir_all(&file_path).expect("Failed to create directories");

    // Open the live_urls.txt file for writing
    file_path.push("live_urls.txt");
    let file = OpenOptions::new()
        .write(true)
        .create(true)
        .truncate(true)
        .open(file_path)
        .expect("Failed to open live_urls.txt");

    // Write the TikTok live URLs to the file
    let mut writer = io::BufWriter::new(file);
    for username in usernames {
        writeln!(writer, "https://www.tiktok.com/@{}/live", username).expect("Failed to write to live_urls.txt");
    }

    Ok(())
}
