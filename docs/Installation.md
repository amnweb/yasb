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

### Enabling Autostart (Run on Startup)

There are two ways to make YASB start automatically when you boot your PC:

#### Method 1: Using the System Tray Menu (Recommended)
1. Locate the **YASB icon** in your Windows system tray (in the bottom-right corner of your screen).
2. **Right-click** the icon to open the context menu.
3. Select **Enable Autostart** to turn it on, or click it again to disable it.

#### Method 2: Using the Command Line (CLI)
You can also configure autostart from your terminal using the YASB CLI client:
* **Enable**: `yasbc enable-autostart`
* **Disable**: `yasbc disable-autostart`

If you experience startup delays or want YASB to run with administrator rights:
* **Enable via Task Scheduler**: `yasbc enable-autostart --task`
* **Disable via Task Scheduler**: `yasbc disable-autostart --task`

***

### First Run: The Setup Wizard

When you launch YASB for the very first time (or if you start fresh by clearing your configuration), you'll be greeted by an interactive **Setup Wizard**. This wizard runs automatically to help you get the status bar configured and running without having to manually edit files or download fonts from the start.

Here is what the wizard handles for you:

1. **Font Installation**: YASB checks your system for the fonts it needs to display icons and text cleanly. If they aren't installed, you can download and install them directly from the wizard:
   * **JetBrains Mono Nerd Font**: This patched font provides all the special glyphs and status icons used in the bar.
   * **Segoe Fluent Icons**: Used for modern Windows-style system icons. It is built into Windows 11, but Windows 10 users can install it through the wizard.
2. **Window Manager Integration**: You can select which tiling window manager you use (such as **GlazeWM** or **Komorebi**). The wizard will pre-configure workspace indicators and layouts for you. If you don't use one, just select **None** to use YASB as a standard Windows status bar.
3. **Layout & Placement**: Choose the default widgets you want to show (like CPU, RAM, active window, clock, volume, or quick launch shortcuts) and decide if you want a floating bar or a full-width taskbar style, along with its screen position (top or bottom).

Once you finish, the wizard creates a default `config.yaml` and `styles.css` in your configuration folder and starts the bar.

> [!TIP]
> If you ever want to run the Setup Wizard again to build a fresh configuration, you can delete `config.yaml` and `styles.css` from your configuration folder, or open your terminal and run `yasbc reset`.