# Services

A service is what YASB reads from Windows, or from another program, for your widgets: the CPU, the battery,
what's playing, your windows, the weather and more. Each one is a QML type from `import Yasb`. Your widget creates
it, tells it what to do, and shows what it reads. YASB's own widgets are built on the same services.

This page explains how every service is used. Each service's own page then shows what you can do with it, and
lists everything it has.

## Create it

Put the service's type in your widget, with an `id` to reach it by:

```qml
import QtQuick
import QtQuick.Controls
import Yasb

Item {
    BatteryMonitor {
        id: battery
    }

    Label {
        text: `${battery.data.percent}%`
    }
}
```

Each widget creates its own. A service that reads something costly, such as the tray or Bluetooth, shares one
reader between every widget that creates it, so a second widget costs nothing extra, its page says so.

A few services are singletons: there is only one, and you use it by its name without creating it, such as
`PowerPlans.plans`. Their pages say so.

## Settings

Settings are properties you set, such as how often to read:

```qml
BatteryMonitor {
    id: battery
    updateInterval: 10000
}
```

Each page lists them with their defaults, a setting you leave out keeps its default. You can bind one to your
widget's own options, such as `updateInterval: settings.updateInterval`, and the service follows when it changes.

## Data

Data are properties you read. Bind to them and your widget changes by itself whenever the service reads something
new, you never ask for it.

Some data is an object with keys, such as `battery.data.percent`. Until the service has read it, or where Windows
doesn't say, a value can be `-1`, `""` or `null`, as each page explains. `??` gives a value to show instead:

```qml
Label {
    text: battery.data.temperature ?? "No temperature"
}
```

## Lists

A list of things, such as screens, devices or tray icons, is a model: give it to a `Repeater`, `ListView` or
`GridView`, and it makes one delegate for each row. The delegate gets the row's fields by declaring them as
`required property`, with their names and types from the service's page:

```qml
BluetoothMonitor {
    id: bluetooth
    // devices fills only while watching; see "While it isn't seen" below
    watching: true
}

Repeater {
    model: bluetooth.devices
    Label {
        required property string name
        required property bool connected
        text: connected ? `${name} (connected)` : name
    }
}
```

When a row changes, such as a device that connects, the delegate stays and only its fields change.

> [!NOTE]
> A row's field hides anything else of the same name in the delegate. Give the service an `id` that no row field
> has, such as `screens` when the rows have a `brightness`.

## Functions

Functions make the service do something, such as connect a device or set the volume. Call them from a handler:

```qml
Button {
    text: "Mute"
    onClicked: output.toggleMute()
}
```

A function that acts on one thing in a list takes a value from that thing's row, such as a device's `address` or a
screen's `monitor`. Take it from the row each time you call, don't keep it, as it can change.

## While it isn't seen

Some services do more work than others, such as scanning for devices. They have a setting that pauses that work,
such as `watching` or `running`. Bind it to whether your popup or widget is seen, such as
`watching: popup.visible`, and the service only does the work while it's needed.

## The services

| Service | What it gives |
| --- | --- |
| [Active window](./(Service)-ActiveWindow) | The window you're working in. |
| [Audio visualizer](./(Service)-AudioVisualizer) | The level of each frequency band in the sound playing. |
| [Battery](./(Service)-Battery) | The battery's charge, time left and health. |
| [Bluetooth](./(Service)-Bluetooth) | The radio, and connecting your devices. |
| [Brightness](./(Service)-Brightness) | The brightness and contrast of your screens. |
| [Clock](./(Service)-Clock) | The time in any time zone, written your way. |
| [CPU](./(Service)-Cpu) | How busy the processor is, and how fast it runs. |
| [Do not disturb](./(Service)-Dnd) | Windows' do not disturb, and changing it. |
| [GitHub](./(Service)-Github) | Your GitHub notifications, and marking them read. |
| [GlazeWM](./(Service)-Glazewm) | GlazeWM's workspaces, tiling direction and binding modes. |
| [GPU](./(Service)-Gpu) | How busy a graphics card is, its memory, temperature, fan and power. |
| [Keyboard language](./(Service)-Language) | The keyboard language and layout, caps lock, and switching layouts. |
| [Komorebi](./(Service)-Komorebi) | Komorebi's workspaces on the bar's monitor, and switching them. |
| [Launchpad](./(Service)-Launchpad) | Your apps in your own order, with groups, and starting them. |
| [Media](./(Service)-Media) | What's playing on your PC, and controlling it. |
| [Memory](./(Service)-Memory) | The memory in use and free, the cache, and the page file. |
| [Microphone](./(Service)-Microphone) | Your microphones, their level and muting them. |
| [Network](./(Service)-Network) | Your internet connection, and Wi-Fi networks. |
| [Network traffic](./(Service)-NetworkTraffic) | Your download and upload speed, and the data each day and hour. |
| [Notifications](./(Service)-Notifications) | Your Windows notifications, opening and clearing them. |
| [OBS](./(Service)-Obs) | Recording and streaming in OBS Studio, and controlling them. |
| [Power menu](./(Service)-PowerMenu) | The signed-in user, uptime, and locking, sleeping, restarting or shutting down. |
| [Power mode](./(Service)-PowerMode) | Windows' power mode on battery and plugged in, and changing it. |
| [Power plan](./(Service)-PowerPlan) | Windows' power plans, and switching them. |
| [Process](./(Service)-Process) | Runs a program or command, and gives what it printed. |
| [Quick launch](./(Service)-QuickLaunch) | Search across apps, files, the calculator, the web and more, and run what you pick. |
| [Recycle bin](./(Service)-RecycleBin) | What the Recycle Bin holds, and emptying it. |
| [Server monitor](./(Service)-ServerMonitor) | Whether your servers and websites are online, and their certificates. |
| [System tray](./(Service)-Systray) | The tray icons of your apps. |
| [Taskbar](./(Service)-Taskbar) | Pinned apps and open windows, switching and pinning them, and live window pictures. |
| [Updates](./(Service)-Updates) | Updates waiting from Windows Update, winget and Scoop, and installing them. |
| [Virtual desktops](./(Service)-WindowsDesktops) | Windows' virtual desktops, switching them, and moving windows between them. |
| [Volume](./(Service)-Volume) | Your sound volume, output devices, and each app's volume. |
| [Wallpapers](./(Service)-Wallpapers) | Your wallpaper images, setting them with a transition, and thumbnails. |
| [Weather](./(Service)-Weather) | The weather now, by hour and by day, for a place you choose. |
| [Window switcher](./(Service)-WindowSwitcher) | Your open windows, front to back, and switching to them. |
| [Windows theme](./(Service)-Theme) | Windows' dark or light mode, and switching it. |
