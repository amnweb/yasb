<p align="center"><img src="https://raw.githubusercontent.com/amnweb/yasb/main/src/assets/images/app_icon.png" width="180"></p>
<h2 align="center">Yasb - Yet Another Status Bar</h2>
<p align="center">
  A highly configurable cross-platform (Windows) status bar written in Python.
  <br><br>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg"></a>
  <a href="https://github.com/amnweb/yasb"><img src="https://img.shields.io/github/languages/top/amnweb/yasb"></a>
  <a href="https://github.com/amnweb/yasb/issues"><img src="https://img.shields.io/github/issues/amnweb/yasb?label=Issues"></a>
  <a href="https://github.com/amnweb/yasb/releases"><img src="https://img.shields.io/github/downloads/amnweb/yasb/total?label=Total%20Downloads"></a>
  <a href="https://github.com/amnweb/yasb/releases/latest"><img src="https://img.shields.io/github/v/release/amnweb/yasb?label=Latest%20Release"></a>
</p>

***

<h3 align="center">
<a href="https://github.com/amnweb/yasb/wiki">Wiki</a>・<a href="https://github.com/amnweb/yasb-themes">Share Your Theme</a>・<a href="https://github.com/amnweb/yasb/discussions">Discussions</a>・<a href="https://github.com/amnweb/yasb/issues">Report a bug</a>
</h3>


### Requirements
- Nerd Fonts. Install [Nerd Fonts](https://www.nerdfonts.com/font-downloads) (JetBrainsMono recommended)
- Windows 10 & 11

### Installer
- Visit the [releases page](https://github.com/amnweb/yasb/releases) on GitHub.
- Look for the latest release version, which will typically be listed at the top.
- Under the "Assets" section of the release, you’ll find various files. Click on the installer file to download it.

***

### Using Python
- Install Python 3.12
- Install required Python Modules:
  - pip install -r [requirements.txt](requirements.txt)
  - Create the directory `C:/Users/{username}/.config/yasb/` and copy [styles.css](src/styles.css) and [config.yaml](src/config.yaml) into folder.
  - Configure [styles.css](src/styles.css) and [config.yaml](src/config.yaml) to your liking.
- Start the application:
  - run `python src/main.py` in your terminal (or click [yasb.vbs](src/yasb.vbs))

***

### Winget
Make sure you have installed the latest version of [winget](https://learn.microsoft.com/en-us/windows/package-manager/winget/) and verified that installed binaries are available in your `$PATH` before proceeding.
Install the YASB using winget install
```
winget install --id AmN.yasb
```

## Demo YASB
![Reborn](demo/demo3.png)

## Demo YASB + Komorebi
![Theme Catppuccin Mocha](demo/demo.png)
![Theme Catppuccin Mocha](demo/demo2.png)

> [!NOTE]  
> This repository is updated on a regular basis; when you update files, always check [styles.css](src/styles.css) and [config.yaml](src/config.yaml) for new features and changes; otherwise, your config can be broken.

## How to style
```
.widget .label {} -> Global label for all
.active-window-widget {} -> Styles specific to the active window widget
.clock-widget {} -> Styles specific to the clock widget
.cpu-widget {} -> Styles specific to the CPU widget
.memory-widget {} -> Styles specific to the memory widget
.weather-widget {} -> Styles specific to the weather widget
.komorebi-workspaces {} -> Styles specific to komorebi workspaces
.komorebi-active-layout {} -> Styles specific to komorebi active layout
.volume-widget {} -> Styles specific to the volume widget 
.apps-widget {} -> Styles specific to the apps widget
.power-menu-widget {} -> Styles for the power menu button widget
.power-menu-popup {} -> Styles for the power menu popup widget
.power-menu-popup > .button {} -> Styles for power buttons inside the popup 
.power-menu-popup > .button > .icon,
.power-menu-popup > .button > .label {} -> Styles for power buttons icons and labels inside the popup
.media-widget {} -> Styles specific to the media widget
.github-widget {} -> Styles specific to the github widget
.language-widget {} -> Styles specific to the language widget
.disk-widget {} -> Styles specific to the disk widget
```


## 🏆 Contributors
Thanks to our amazing contributors!

[![YASB Contributors](https://contrib.rocks/image?repo=amnweb/yasb)](https://github.com/amnweb/yasb/graphs/contributors)