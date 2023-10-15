use fantoccini::ClientBuilder;
use serde_json::Value;
use std::env;
use std::fs::File;
use std::io::BufReader;
use std::path::PathBuf;
use std::process::{Command, Child};
use cookie::Cookie;
use std::error::Error;

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error + Send + Sync>> {
    // Get the current executable's directory.
    let mut geckodriver_path = env::current_exe()?
        .parent()
        .ok_or("Failed to get the executable's directory")?
        .to_path_buf();
    
    // Append the relative path to geckodriver.
    geckodriver_path.push("binaries");
    geckodriver_path.push("geckodriver.exe");

    let mut geckodriver: Child = Command::new(geckodriver_path)
        .spawn()
        .expect("Failed to start geckodriver");

    let client = ClientBuilder::native()
        .connect("http://localhost:4444")
        .await
        .map_err(|e| format!("Failed to connect: {}", e))?;
    
    let url = "https://www.tiktok.com";
    client.goto(url).await.expect("Failed to navigate");

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

    let live_url = "https://www.tiktok.com/@lol/live";
    client.goto(live_url).await.expect("Failed to navigate");

    // ... your code to interact with the page ...

    client.close().await.expect("Failed to close the client");
    
    geckodriver.kill().expect("Failed to kill geckodriver");
    
    Ok(())
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
