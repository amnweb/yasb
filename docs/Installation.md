### Requirements
- Windows 10 & 11
- Default YASB theme uses Segoe Fluent Icons font, which is included in Windows 11 by default. **Windows 10 users** need to download and install the font manually from [Microsoft](https://aka.ms/SegoeFluentIcons).
- For custom themes, It's recommended to install Nerd Fonts, which provides a large collection of patched fonts with additional glyphs/icons. You can download and install Nerd Fonts from their [official website](https://www.nerdfonts.com/). Recommended [JetBrainsMono Propo](https://github.com/ryanoasis/nerd-fonts/releases/latest/download/JetBrainsMono.zip) 

### Installation (stable release)
1. Go to the [releases page](htpps://github.com/amnweb/yasb/releases).
2. Choice the architecture that matches your system (x64 or ARM64).
3. Download the `yasb-{version}-{architecture}.msi` installer.
4. Run the installer and follow the on-screen instructions.


### Installation (latest development build)
1. Go to the [pre release](https://github.com/amnweb/yasb/releases/tag/dev)
2. Choice the architecture that matches your system (x64 or ARM64).
3. Download the `yasb-dev-{architecture}.msi` installer.
4. Run the installer and follow the on-screen instructions.


### Using Package Managers (only stable releases)
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
- Install Python >= 3.14
- Install the application and its dependencies:
  - `pip install .` (for regular installation)
  - `pip install -e .[dev]` (for development installation)
  - `pip install -e .[dev,packaging]` (for packaging development installation)
- Start the application:
  - run `python src/main.py`


### Build from source
- Clone the repository: `git clone https://github.com/amnweb/yasb`
- Navigate to the project directory: `cd yasb`
- Install the required dependencies: `pip install -e .[packaging]`
- Navigate to the `src` directory: `cd src`
- Build the installer using following command:
```powershell
python build.py build
python build.py bdist_msi
```