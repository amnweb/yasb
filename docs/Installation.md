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
  - `pip install -r requirements.txt`
  - Create the directory `C:/Users/{username}/.config/yasb/` and copy [styles.css](https://github.com/amnweb/yasb/blob/main/src/styles.css) and [config.yaml](https://github.com/amnweb/yasb/blob/main/src/config.yaml) into folder.
  - Configure [styles.css](https://github.com/amnweb/yasb/blob/main/src/styles.css) and [config.yaml](https://github.com/amnweb/yasb/blob/main/src/config.yaml) to your liking.
- Start the application:
  - run `python src/main.py` in your terminal (or click [yasb.vbs](https://github.com/amnweb/yasb/blob/main/src/yasb.vbs))


***

### Winget
Make sure you have installed the latest version of [winget](https://learn.microsoft.com/en-us/windows/package-manager/winget/).
Install the YASB using winget install
```
winget install --id AmN.yasb
```