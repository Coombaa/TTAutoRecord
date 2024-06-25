
# TTAutoRecord: Automated TikTok Live Stream Recorder

TTAutoRecord is a specialized utility designed to automate the recording of live streams on TikTok. 

## Features

- Automatically record users you follow
- Concatenates laggy lives into one file
- Records age restricted lives
- Records sub-only lives
- GUI displaying status of recordings

## System Requirements

- 4GB **Spare** RAM
- 64Bit Desktop CPU (I have tested this on a Xeon D-1521 and it works, however a high frequency desktop CPU will perform better)
- SSD - Recommended to keep things running smoothly, of course you can offload recordings to a hard drive for storage.
- 50Mbps FTTC/FTTP internet connection recommended.

If you can, I would suggest having a PC/Server dedicated to running this. I have done my best to minimize the amount of requests to TikTok, however their webpages are incredibly demanding to render so it may cause other applications to lag.

## Prerequisites

1. Install [Python](https://www.python.org/downloads/)

2. Install the [EditThisCookie](https://chrome.google.com/webstore/detail/editthiscookie/fngmhnnpilhplaeedifhccceomclgfbg)  Chrome browser extension.

3. Install [Mozilla Firefox](https://www.mozilla.org/en-GB/firefox/browsers/windows-64-bit/) **(64-bit version)**

## Setup
1. Set your TikTok language to **English** if it isn't already.

2. Download and extract the requried files [here](https://github.com/Coombaa/TTAutoRecord/releases/download/v4.1.2/TTAutoRecord-4.1.2.zip)

3. Install required modules from the requirements file:

```bash
  pip install -r requirements.txt
```

4. **Authenticate on TikTok**
   - Access [TikTok Live](https://www.tiktok.com/live) via your web browser and authenticate your account.
   - Open the EditThisCookie extension and select the 'Export' icon.
   - Paste the Cookies into \json\cookies.json
   - **Important** - Do not log out after extracting your cookies!
    
## Usage

1. Run main.py
2. run gui.pyw
