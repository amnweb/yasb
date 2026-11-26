# Installation

YASB is built for Windows 11. It may work on Windows 10, but it isn't tested there. One known limitation: the blur
behind the bar and its popups needs Windows 11.

Install it with the installer or a package manager. On first start, YASB opens a short setup for your bar.

## Before you install

YASB draws its icons with the Segoe Fluent Icons font. Windows 11 has it. On Windows 10,
[download it from Microsoft](https://aka.ms/SegoeFluentIcons), open the font file and click **Install**. The setup
reminds you when it's missing.

For icons of your own in a theme or a widget, a [Nerd Font](https://www.nerdfonts.com/) has many more glyphs, such
as [JetBrainsMono Propo](https://github.com/ryanoasis/nerd-fonts/releases/latest/download/JetBrainsMono.zip).

## Install

### Installer

1. Open the [releases page](https://github.com/amnweb/yasb/releases).
2. Download the installer for your PC: `yasb-<version>-x64.msi`, or `yasb-<version>-aarch64.msi` on ARM64.
3. Run it and follow its steps.

### Preview

The [preview release](https://github.com/amnweb/yasb/releases/tag/preview) is built from the newest code. Its installers
are `yasb-preview-x64.msi` and `yasb-preview-aarch64.msi`. `yasbc set-channel` switches an installed YASB between the
stable and preview releases (see [YASB CLI](./CLI#yasbc-set-channel)).

### Package managers

Package managers install the stable release.

With [winget](https://learn.microsoft.com/en-us/windows/package-manager/winget/):

```powershell
winget install --id AmN.yasb
```

With [Scoop](https://scoop.sh/):

```powershell
scoop bucket add extras
scoop install extras/yasb
```

With [Chocolatey](https://chocolatey.org/):

```powershell
choco install yasb
```

### From the source

To run YASB from its source code, or build the installer yourself, see [Contributing](./Contributing).

## Start with Windows

The setup's last page can start YASB with Windows. To change it later, right-click YASB's tray icon and click **Enable
Autostart** or **Disable Autostart**. From a terminal:

```powershell
yasbc enable-autostart
yasbc disable-autostart
```

`--task` does the same with a Task Scheduler task that starts YASB when you sign in, such as
`yasbc enable-autostart --task`. Turn that one off with `yasbc disable-autostart --task`.

## First run: the setup

When YASB starts and finds no `config.yaml` in your config folder (`%USERPROFILE%\.config\yasb`), it opens the setup. It takes a few steps:

1. **Welcome**: on Windows 10, where Segoe Fluent Icons is missing, the setup asks you to get it first. Click **Download**, open the font file, click **Install**, then restart YASB.
2. **Your bar**: the screen edge (top or bottom), the style (full bar, floating or islands), the thickness in pixels, the screens that get a bar (all, or only the main one), and blur behind the bar, which needs Windows 11.
3. **How your bar behaves**: always on top, hiding while a game or video is fullscreen, auto-hide (never, always, or when a window is maximized), and keeping maximized windows off the bar.
4. **Widgets**: the widgets on the left, in the center and on the right of the bar.
5. **You're all set**: starting YASB with Windows, and checking for updates.

**Finish** writes three files in your config folder and starts the bar:
- `config.yaml`: YASB's settings and your bar, with its screens, edge, size, layout and widgets.
- `layouts\bar.qml`, `layouts\floating.qml` or `layouts\islands.qml`: the bar's look, for the style you picked.
- `themes\yasb.qml`: the colors and fonts of the bar, its widgets, popups and menus.

Existing layout and theme files aren't overwritten. When you save a change to any of the three files, YASB applies it.

> [!WARNING]
> YASB 3 can't read a `config.yaml` from YASB 2. If it finds one, the setup asks you to close YASB, move that `config.yaml` out of your config folder (or back it up and delete it), then start YASB again.

> [!TIP]
> To run the setup again, delete `config.yaml` from your config folder, or run `yasbc reset`. `yasbc reset` also stops YASB and clears its cache. Your layout and theme files stay.
