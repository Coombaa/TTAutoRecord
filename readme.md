# TTAutoRecord: Automated TikTok Live Stream Recorder

TTAutoRecord is a specialized utility designed to automate the recording of live streams on TikTok. The software is packaged as a standalone `.exe` executable for ease of use.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Installation and Setup](#installation-and-setup)
- [Important Notes](#important-notes)
- [Configuration Files](#configuration-files)

## Prerequisites

### Critical Precondition
**It is required to set the language of your TikTok account to English prior to cookie extraction.**

1. **Install the EditThisCookie Browser Extension**
   - Navigate to the [EditThisCookie extension on the Chrome Web Store](https://chrome.google.com/webstore/detail/editthiscookie/fngmhnnpilhplaeedifhccceomclgfbg) and proceed with the installation.

2. **Authenticate on TikTok**
   - Access [TikTok Live](https://www.tiktok.com/live) via your web browser and authenticate your account.
   - Invoke the EditThisCookie extension and select the 'Export' icon.

3. **Configure Cookie Settings**
   - Paste the exported cookie data into the `/binaries/config/cookies.json` file.

4. **Install Mozilla Firefox (64-bit version)**
   - Ensure that the 64-bit version of Mozilla Firefox is installed on your system.

## Installation and Setup

1. **Execute the Program**
   - Double-click the `START.bat` file to initialize the application.

## Important Notes

- It may be necessary to whitelist `TTAutoRecord.exe` within your antivirus software, as the executable is not digitally signed.

## Configuration Files

- **config.toml**: The default settings are optimized for general use-cases, specifically for querying Webcast URLs. A rate of 10 URLs per second is generally sufficient for most users.
  
- **flv_users.txt**: For users experiencing issues with HLS streams, the software will automatically switch to FLV links after 10 unsuccessful attempts. To preemptively bypass the m3u8 validation for these users, include their usernames in this file. It is hoped that TikTok will resolve this issue in the near future.

- **monitored_users.txt**: This file is autonomously updated by the application. Manual modifications are discouraged.

- **ignored_users.txt**: Usernames listed in this file will be explicitly excluded from the recording process.


## Disclaimer

By using TTAutoRecord, you assume all responsibilities and risks that may come with the use of this software. I am not responsible for any actions taken against your TikTok account. It is strongly advised to create a new TikTok account specifically for this utility and to utilize a Virtual Private Network (VPN) while operating the software.
