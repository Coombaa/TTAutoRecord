
# TTAutoRecord: Automated TikTok Live Stream Recorder

TTAutoRecord is a specialized utility designed to automate the recording of live streams on TikTok. 


## Features

- Automatically record users you follow
- Concatenates laggy lives into one file
- Records age restricted lives
- Records sub-only lives
- GUI displaying status of recordings

## Prerequisites

1. Install [Python](https://www.python.org/downloads/)

3. Install required modules:

```bash
  pip install -r requirements.txt
```

3. Install the [EditThisCookie](https://chrome.google.com/webstore/detail/editthiscookie/fngmhnnpilhplaeedifhccceomclgfbg)  Chrome browser extension.

4. Install [Mozilla Firefox](https://www.mozilla.org/en-GB/firefox/browsers/windows-64-bit/) **(64-bit version)**
## Setup
1. Set your TikTok language to **English** if it isn't already.

2. Download and extract the requried files **Here**

3. **Authenticate on TikTok**
   - Access [TikTok Live](https://www.tiktok.com/live) via your web browser and authenticate your account.
   - Open the EditThisCookie extension and select the 'Export' icon.
   - Paste the Cookies into \json\cookies.json
   - **Important** - Do not log out after extracting your cookies!
    
## Usage

1. Run with GUI
```bash
py main.py
```
2. Run without GUI
```bash
py main.py --nogui
```
