# Widgets

YASB comes with these widgets. Put a widget on a bar by its id, as
[Widgets in a bar](./Configuration#widgets-in-a-bar) explains.

| Widget | Id | What it shows |
| --- | --- | --- |
| Active window | `ActiveWindow` | The window you're working in. |
| Audio visualizer | `AudioVisualizer` | An animation that moves with the sound playing. |
| Battery | `Battery` | Your battery level. |
| Bluetooth | `Bluetooth` | Bluetooth and your paired devices. |
| Brightness | `Brightness` | Your screen brightness. |
| Clock | `Clock` | The time and date. |
| CPU | `Cpu` | Your processor usage. |
| Do not disturb | `Dnd` | Windows' do not disturb mode: off, priority only or alarms only. |
| GitHub | `Github` | Your GitHub notifications. |
| GlazeWM workspaces | `GlazewmWorkspaces` | Workspaces of the GlazeWM tiling window manager. |
| GPU | `Gpu` | Your graphics card usage. |
| Keyboard language | `Language` | Your keyboard layout. |
| Komorebi workspaces | `KomorebiWorkspaces` | Workspaces of the Komorebi tiling window manager. |
| Launchpad | `Launchpad` | All your apps in one grid, with your own groups. |
| Media | `Media` | What's playing on your PC. |
| Memory | `Memory` | Your memory usage. |
| Microphone | `Microphone` | Your microphone. |
| Network | `Network` | Your network connection. |
| Network traffic | `NetworkTraffic` | Your download and upload speed. |
| Notifications | `Notifications` | Your Windows notifications menu. |
| OBS | `Obs` | Recording and streaming in OBS Studio. |
| Power menu | `PowerMenu` | A power menu to lock, sign out, sleep, restart or shut down. |
| Power plan | `PowerPlan` | The Windows power plan. |
| Quick Launch | `QuickLaunch` | A search launcher for your apps, files and more. |
| Server monitor | `ServerMonitor` | Whether your servers and websites are online. |
| System tray | `Systray` | The tray icons of apps running in the background. |
| Taskbar | `Taskbar` | Your pinned and open apps, like the Windows taskbar. |
| Updates | `Updates` | Available updates for Windows and your apps. |
| Virtual desktops | `WindowsDesktops` | Your Windows virtual desktops. |
| Volume | `Volume` | Your sound volume. |
| Wallpapers | `Wallpapers` | A gallery of your wallpapers. |
| Weather | `Weather` | The weather for your location. |
| Window switcher | `WindowSwitcher` | Your open windows in a row, to switch between them. |

## Get a widget's options

A widget's options are in a QML file. To change them, run `yasbc addons install` with the widget's id:

```powershell
yasbc addons install Clock
```

This writes all the widget's options, with their values and comments, to a file in your config folder:

```text
%USERPROFILE%\.config\yasb\widgets\Clock\Clock.qml
```

Open that file, change what you like and save it. From then on, YASB uses this file instead of the default options and
applies each change when you save. Delete the folder to go back to the defaults.

## Where the widgets are

YASB's own widgets are in YASB's install folder, under `core\qml\Yasb\Widgets`, one folder each, and on GitHub in
[src/core/qml/Yasb/Widgets](https://github.com/amnweb/yasb/tree/main/src/core/qml/Yasb/Widgets).
