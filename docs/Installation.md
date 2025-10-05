### Requirements
- Nerd Fonts. Install [Nerd Fonts](https://www.nerdfonts.com/font-downloads) ([JetBrainsMono](https://github.com/ryanoasis/nerd-fonts/releases/latest/download/JetBrainsMono.zip) recommended)
- Windows 10 & 11

### Manual Installation
1. Download the latest installer from the [GitHub releases page](https://github.com/amnweb/yasb/releases/latest).
2. Run the installer and follow the on-screen instructions to complete the installation.

***

### Winget
Install YASB using [winget](https://learn.microsoft.com/en-us/windows/package-manager/winget/):
```powershell
winget install --id AmN.yasb
```

***

### Scoop
Install YASB using [Scoop](https://scoop.sh/):
```powershell
scoop bucket add extras
scoop install extras/yasb
```

***

### Chocolatey
Install YASB using [Chocolatey](https://chocolatey.org/):
```powershell
choco install yasb
```

***

### Using Python
- Install Python >= 3.12
- Install the application and its dependencies:
  - `pip install .` (for regular installation)
  - `pip install -e .[dev]` (for development installation)
  - Create the directory `C:/Users/{username}/.config/yasb/` and copy [styles.css](https://github.com/amnweb/yasb/blob/main/src/styles.css) and [config.yaml](https://github.com/amnweb/yasb/blob/main/src/config.yaml) into folder. If you don't have the `.config/yasb/` directory, on first run the application will create it for you. To use a custom directory, set the `YASB_CONFIG_HOME` environment variable.
  - Configure [styles.css](https://github.com/amnweb/yasb/blob/main/src/styles.css) and [config.yaml](https://github.com/amnweb/yasb/blob/main/src/config.yaml) to your liking.
- Start the application:
  - run `python src/main.py` in your terminal (or click [yasb.vbs](https://github.com/amnweb/yasb/blob/main/src/yasb.vbs))


### Build from source
- Clone the repository: `git clone https://github.com/amnweb/yasb`
- Navigate to the project directory: `cd yasb`
- Install the required dependencies: `pip install -e .[dev]`
- Navigate to the `src` directory: `cd src`
- Build the installer using following command:
```powershell
python build.py build
python build.py bdist_msi
```