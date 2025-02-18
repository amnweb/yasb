<p align="center"><img src="https://raw.githubusercontent.com/amnweb/yasb/main/src/assets/images/app_icon.png" width="180"></p>
<h1 align="center">YASB Reborn</h1>
<p align="center">
  A highly configurable Windows status bar written in Python.
  <br><br>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg"></a>
  <a href="https://github.com/amnweb/yasb"><img src="https://img.shields.io/github/languages/top/amnweb/yasb"></a>
  <a href="https://github.com/amnweb/yasb/issues"><img src="https://img.shields.io/github/issues/amnweb/yasb?label=Issues"></a>
  <a href="https://github.com/amnweb/yasb/releases"><img src="https://img.shields.io/github/downloads/amnweb/yasb/total?label=Total%20Downloads"></a>
  <a href="https://github.com/amnweb/yasb/releases/latest"><img src="https://img.shields.io/github/v/release/amnweb/yasb?label=Latest%20Release"></a>
  <a href="https://discord.gg/Db6t9bUnQn" title="Discord"><img alt="Discord" src="https://img.shields.io/discord/898554690126630914?label=Discord&cacheSeconds=600"></a>
</p>

***

<h3 align="center">
<a href="https://github.com/amnweb/yasb/wiki">Wiki</a>・<a href="https://github.com/amnweb/yasb-themes">Share Your Theme</a>・<a href="https://github.com/amnweb/yasb/discussions">Discussions</a>・<a href="https://github.com/amnweb/yasb/issues">Report a bug</a>
</h3>

***

# Installation

### Requirements
- Nerd Fonts. Install [Nerd Fonts](https://www.nerdfonts.com/font-downloads) ([JetBrainsMono](https://github.com/ryanoasis/nerd-fonts/releases/latest/download/JetBrainsMono.zip) recommended)
- Windows 10 & 11

### Installer
- Visit the [releases page](https://github.com/amnweb/yasb/releases).
- Look for the latest release version, which will typically be listed at the top.
- Under the "Assets" section of the release, you’ll find various files. Click on the installer file to download it.

***

### Winget
Install the YASB using winget install
```
winget install --id AmN.yasb
```
***

### Using Python
- Install Python 3.12
- Install required Python Modules:
  - `pip install -r requirements.txt`
  - Create the directory `C:/Users/{username}/.config/yasb/` and copy [styles.css](src/styles.css) and [config.yaml](src/config.yaml) into folder. If you don't have the `.config/yasb/` directory, on first run, the application will create it for you with the default configuration.
  - Configure [styles.css](src/styles.css) and [config.yaml](src/config.yaml) to your liking.
- Start the application:
  - run `python src/main.py` in your terminal (or click [yasb.vbs](src/yasb.vbs))



## Demo YASB
![Reborn](demo/demo3.png)
![Windows 11](https://raw.githubusercontent.com/amnweb/yasb-themes/refs/heads/main/themes/7d3895d4-454b-40db-a2f9-44a238d5793b/image.png)
![Yasb 001](https://raw.githubusercontent.com/amnweb/yasb-themes/refs/heads/main/themes/61e6a045-e090-4f33-a41b-6938702eb446/image.png)
for more themes visit [yasb-themes](https://github.com/amnweb/yasb-themes)
## Demo YASB + Komorebi
![Theme Catppuccin Mocha](demo/demo.png)
![Theme Catppuccin Mocha](demo/demo2.png)

https://github.com/user-attachments/assets/aab8d8e8-248f-46a1-919c-9b0601236ac1



> [!NOTE]  
> This repository is updated on a regular basis; when you update files, always check [styles.css](src/styles.css) and [config.yaml](src/config.yaml) for new features and changes; otherwise, your config can be broken.


## List of currently available widgets in YASB.

- **[Active Windows Title](https://github.com/amnweb/yasb/wiki/(Widget)-Active-Windows-Title)**: Displays the title of the currently active window.
- **[Applications](https://github.com/amnweb/yasb/wiki/(Widget)-Applications)**: Shows a list of predefined applications.
- **[Battery](https://github.com/amnweb/yasb/wiki/(Widget)-Battery)**: Displays the current battery status.
- **[Bluetooth](https://github.com/amnweb/yasb/wiki/(Widget)-Bluetooth)**: Shows the current Bluetooth status and connected devices.
- **[Brightness](https://github.com/amnweb/yasb/wiki/(Widget)-Brightness)**: Displays and change the current brightness level.
- **[Cava](https://github.com/amnweb/yasb/wiki/(Widget)-Cava)**: Displays audio visualizer using Cava.
- **[CPU](https://github.com/amnweb/yasb/wiki/(Widget)-CPU)**: Shows the current CPU usage.
- **[Clock](https://github.com/amnweb/yasb/wiki/(Widget)-Clock)**: Displays the current time and date.
- **[Custom](https://github.com/amnweb/yasb/wiki/(Widget)-Custom)**: Create a custom widget.
- **[Github](https://github.com/amnweb/yasb/wiki/(Widget)-Github)**: Shows notifications from GitHub.
- **[GlazeWM Workspaces](https://github.com/amnweb/yasb/wiki/(Widget)-GlazeWM-Workspaces)**: GlazeWM workspaces widget.
- **[GlazeWM Tiling Direction](https://github.com/amnweb/yasb/wiki/(Widget)-GlazeWM-Tiling-Direction)**: GlazeWM tiling direction widget.
- **[Home](https://github.com/amnweb/yasb/wiki/(Widget)-Home)**: A customizable home widget menu.
- **[Disk](https://github.com/amnweb/yasb/wiki/(Widget)-Disk)**: Displays disk usage information.
- **[Language](https://github.com/amnweb/yasb/wiki/(Widget)-Language)**: Shows the current input language.
- **[Libre Hardware Monitor](https://github.com/amnweb/yasb/wiki/(Widget)-Libre-HW-Monitor)**: Connects to Libre Hardware Monitor to get sensor data.
- **[Media](https://github.com/amnweb/yasb/wiki/(Widget)-Media)**: Displays media controls and information.
- **[Memory](https://github.com/amnweb/yasb/wiki/(Widget)-Memory)**: Shows current memory usage.
- **[Microphone](https://github.com/amnweb/yasb/wiki/(Widget)-Microphone)**: Displays the current microphone status.
- **[Notifications](https://github.com/amnweb/yasb/wiki/(Widget)-Notifications)**: Shows the number of notifications from Windows.
- **[OBS](https://github.com/amnweb/yasb/wiki/(Widget)-Obs)**: Integrates with OBS Studio to show recording status.
- **[Server Monitor](https://github.com/amnweb/yasb/wiki/(Widget)-Server-Monitor)**: Monitors server status.
- **[Traffic](https://github.com/amnweb/yasb/wiki/(Widget)-Traffic)**: Displays network traffic information.
- **[Taskbar](https://github.com/amnweb/yasb/wiki/(Widget)-Taskbar)**: A customizable taskbar for launching applications.
- **[Power Menu](https://github.com/amnweb/yasb/wiki/(Widget)-Power-Menu)**: A menu for power options.
- **[Update Checker](https://github.com/amnweb/yasb/wiki/(Widget)-Update-Check)**: Checks for available updates using Windows Update and Winget.
- **[Volume](https://github.com/amnweb/yasb/wiki/(Widget)-Volume)**: Shows and controls the system volume.
- **[Wallpapers](https://github.com/amnweb/yasb/wiki/(Widget)-Wallpapers)**: Allows changing wallpapers.
- **[Weather](https://github.com/amnweb/yasb/wiki/(Widget)-Weather)**: Displays current weather information.
- **[WiFi](https://github.com/amnweb/yasb/wiki/(Widget)-WiFi)**: Shows the current WiFi status.
- **[WHKD](https://github.com/amnweb/yasb/wiki/(Widget)-Whkd)**: Shows the current hotkey.
- **[Windows-Desktops](https://github.com/amnweb/yasb/wiki/(Widget)-Windows-Desktops)**: Windows desktops switcher.
- **[Komorebi Workspaces](https://github.com/amnweb/yasb/wiki/(Widget)-Komorebi-Workspaces)**: Komorebi workspaces widget.
- **[Komorebi Layout](https://github.com/amnweb/yasb/wiki/(Widget)-Komorebi-Layout)**: Shows the current layout of Komorebi.


## 🏆 Contributors
Thanks to our amazing contributors!

[![YASB Contributors](https://contrib.rocks/image?repo=amnweb/yasb)](https://github.com/amnweb/yasb/graphs/contributors)