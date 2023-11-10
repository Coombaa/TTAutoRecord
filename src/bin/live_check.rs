use fantoccini::{ClientBuilder, Locator, Client};
use serde_json::{map::Map, Value};
use std::{
    env,
    fs::{self, OpenOptions, File},
    io::{self, BufReader, Write},
    path::PathBuf,
    process::{Command, Child},
    time::Duration
};
use cookie::Cookie;
use tokio::time::{sleep, timeout};
use tokio_util::sync::CancellationToken;
use std::sync::Arc;
use log::{info, debug, error};
use env_logger;
use std::fmt;


const MAX_RETRIES: usize = 3;
const RETRY_DELAY: u64 = 5; // in seconds

#[derive(Debug)]
enum MyError {
    CmdError(fantoccini::error::CmdError),
    NewSessionError(fantoccini::error::NewSessionError),  // New variant for NewSessionError
    IoError(std::io::Error),
    SerdeError(serde_json::Error),
    StrError(String),
}

impl From<fantoccini::error::NewSessionError> for MyError {
    fn from(err: fantoccini::error::NewSessionError) -> MyError {
        MyError::NewSessionError(err)
    }
}

impl From<fantoccini::error::CmdError> for MyError {
    fn from(err: fantoccini::error::CmdError) -> MyError {
        MyError::CmdError(err)
    }
}

impl From<std::io::Error> for MyError {
    fn from(err: std::io::Error) -> MyError {
        MyError::IoError(err)
    }
}

impl From<serde_json::Error> for MyError {
    fn from(err: serde_json::Error) -> MyError {
        MyError::SerdeError(err)
    }
}

impl From<&str> for MyError {
    fn from(err: &str) -> MyError {
        MyError::StrError(err.to_string())
    }
}

impl fmt::Display for MyError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "{:?}", self)
    }
}

#[tokio::main]
async fn main() {
    env::set_var("RUST_LOG", "debug");
    env_logger::init();

    match run().await {
        Ok(_) => info!("Program completed successfully."),
        Err(e) => eprintln!("Error: {}", e),
    }
}

async fn run() -> Result<(), MyError> {
    debug!("Initializing environment...");
    initialize_environment()?;

    debug!("Getting geckodriver path...");
    let mut geckodriver_path = env::current_exe()?
    .parent()
    .ok_or("Failed to get the executable's directory")?
    .to_path_buf();

    geckodriver_path.push("geckodriver.exe");

    debug!("Starting geckodriver...");
    let _geckodriver: Child = Command::new(geckodriver_path)
        .spawn()?;

    debug!("Entering main loop...");
    
    loop {
        debug!("Creating new client...");
        let mut client = create_client().await?;

        loop {
            debug!("Getting live users...");
            match get_live_users(&mut client, Arc::new(CancellationToken::new())).await {
                Ok(_) => debug!("Successfully fetched live users."),
                Err(e) => {
                    eprintln!("Error fetching live users: {}", e);
                    if e.to_string().contains("InactiveActor") {
                        debug!("InactiveActor error detected, disposing current client...");
                        drop(client); // Explicitly drop the client
                        debug!("Client dropped successfully.");
                        break; // Exit the loop to create a new client
                    } else {
                        debug!("Error did not contain InactiveActor, continuing...");
                    }
                }
            }

            debug!("Sleeping for 10 seconds before next iteration...");
            sleep(Duration::from_secs(10)).await;
        }
        debug!("Exiting inner loop, proceeding to create a new client...");
    }
}

async fn create_client() -> Result<Client, MyError> {
    debug!("Setting up capabilities...");
    let mut capabilities = Map::new();
    let options = serde_json::json!({ "args": ["--headless"] });
    capabilities.insert("moz:firefoxOptions".to_string(), options.clone());

    debug!("Creating client...");
    let client = ClientBuilder::native()
        .capabilities(capabilities)
        .connect("http://localhost:4444")
        .await.map_err(MyError::NewSessionError)?;  // Updated map_err to use the new variant

    debug!("Navigating to live URL...");
    let live_url = "https://www.tiktok.com/@lol/live";
    client.goto(live_url).await.map_err(MyError::CmdError)?;

    debug!("Opening cookies.json...");
    let cookies_path = get_config_path("cookies.json")?;
    let cookies_file = File::open(&cookies_path)?;
    let reader = BufReader::new(cookies_file);
    let cookies: Value = serde_json::from_reader(reader)?;

    debug!("Adding cookies...");
    for cookie in cookies.as_array().ok_or("Failed to get cookie array")? {
        if let Value::Object(c) = cookie {
            let name_str = c["name"].as_str().ok_or("Failed to get cookie name")?.to_string();
            let value_str = c["value"].as_str().ok_or("Failed to get cookie value")?.to_string();
            let domain_str = c["domain"].as_str().ok_or("Failed to get cookie domain")?.to_string();
            let path_str = c["path"].as_str().unwrap_or("/").to_string();
            let secure = c["secure"].as_bool().unwrap_or(false);
            let http_only = c["httpOnly"].as_bool().unwrap_or(false);
            let cookie = Cookie::build(name_str, value_str)
                .domain(domain_str)
                .path(path_str)
                .secure(secure)
                .http_only(http_only)
                .finish();
            client.add_cookie(cookie).await.map_err(MyError::CmdError)?;
        }
    }

    debug!("Refreshing client...");
    client.refresh().await.map_err(MyError::CmdError)?;

    Ok(client)
}

fn initialize_environment() -> Result<(), MyError> {
    debug!("Ensuring config directory exists...");
    let config_dir = get_config_path("")?;
    if !config_dir.exists() {
        fs::create_dir_all(&config_dir)?;
    }

    debug!("Ensuring config/cookies.json file exists...");
    let cookies_file_path = get_config_path("cookies.json")?;
    if !cookies_file_path.exists() {
        let file = fs::File::create(&cookies_file_path)?;
        file.set_len(0)?;  // Ensures the file is empty
    }

    debug!("Ensuring config/lists directory exists...");
    let lists_dir = get_config_path("lists")?;
    if !lists_dir.exists() {
        fs::create_dir_all(&lists_dir)?;
    }

    Ok(())
}

fn get_config_path(filename: &str) -> Result<PathBuf, MyError> {
    debug!("Getting config path for: {}", filename);
    let mut config_path = env::current_exe()?
        .parent()
        .ok_or("Failed to get the executable's directory")?
        .to_path_buf();
    config_path.push("config");
    config_path.push(filename);
    Ok(config_path)
}

async fn get_live_users(client: &mut Client, cancel_token: Arc<CancellationToken>) -> Result<(), MyError> {
    debug!("Waiting for following div...");
    sleep(Duration::from_secs(2)).await;
    let _ = cancel_token;

    for attempt in 0..MAX_RETRIES {
        match timeout(Duration::from_secs(5), client.wait().for_element(Locator::Css("div.tiktok-abirwa-DivSideNavChannel"))).await {
            Ok(Ok(following_div)) => {
                debug!("Following div found.");

                debug!("Finding live-side-more-button...");
                if let Ok(btn) = client.find(Locator::Css("div[data-e2e='live-side-more-button']")).await {
                    btn.click().await.map_err(MyError::CmdError)?;
                }

                debug!("Finding all a elements...");
                let a_elements = following_div.find_all(Locator::Css("a")).await.map_err(MyError::CmdError)?;
                let mut usernames = Vec::new();

                for a in a_elements {
                    debug!("Finding username span...");
                    if let Ok(span) = timeout(Duration::from_secs(5), a.find(Locator::Css("span[data-e2e='live-side-nav-name']"))).await {
                        let username = span?.text().await.map_err(MyError::CmdError)?;
                        usernames.push(username);
                    }
                }

                debug!("Ensuring config/lists directory exists...");
                let mut file_path = get_config_path("lists")?;
                fs::create_dir_all(&file_path)?;

                debug!("Opening live_urls.txt for writing...");
                file_path.push("live_urls.txt");
                let file = OpenOptions::new()
                    .write(true)
                    .create(true)
                    .truncate(true)
                    .open(file_path)?;

                debug!("Writing usernames to live_urls.txt...");
                let mut writer = io::BufWriter::new(file);
                for username in usernames {
                    writeln!(writer, "https://www.tiktok.com/@{}/live", username)?;
                }

                client.refresh().await.map_err(MyError::CmdError)?;

                return Ok(());
            }
            Ok(Err(e)) => {
                error!("Attempt {}: Error while waiting for following div: {:?}", attempt + 1, e);
            }
            Err(_) => {
                error!("Attempt {}: Timeout elapsed while waiting for following div", attempt + 1);
            }
        }
        if attempt < MAX_RETRIES - 1 {
            debug!("Retrying in {} seconds...", RETRY_DELAY);
            sleep(Duration::from_secs(RETRY_DELAY)).await;
        }
    }

    debug!("Maximum attempts reached. Refreshing client...");
    client.refresh().await.map_err(MyError::CmdError)?;
    Err(MyError::StrError("Maximum attempts reached while waiting for following div".to_string()))
}

