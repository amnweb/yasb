# Writing widgets

A widget is a QML file in your config folder. YASB's Python services give it the data, such as the CPU usage or
what's playing, and the widget decides how to show it. This page builds one widget step by step: a CPU meter that
warns when the CPU is busy and opens a popup with the busiest processes. Each step shows the whole file.

You'll need a little QML. Qt's [QML introduction](https://doc.qt.io/qt-6/qmlfirststeps.html) covers what this page
uses, and [Qt Quick's types](https://doc.qt.io/qt-6/qtquick-qmlmodule.html) are all there for a widget to use.

## A widget on the bar

A widget is a folder in `widgets` with a QML file of the same name in it. Make
`widgets\CpuLoad\CpuLoad.qml` in your config folder:

```qml
// %USERPROFILE%\.config\yasb\widgets\CpuLoad\CpuLoad.qml
import QtQuick
import QtQuick.Controls
import Yasb.Bar

Item {
    // The bar the widget is in; YASB sets it
    required property BarBase bar

    implicitWidth: label.implicitWidth
    implicitHeight: label.implicitHeight

    Label {
        id: label

        anchors.verticalCenter: parent.verticalCenter
        text: "Hello"
    }
}
```

Then put it on a bar in `config.yaml`:

```yaml
bars:
  yasb-bar:
    widgets:
      right:
        - CpuLoad
```

The bar shows "Hello". YASB makes the widget as tall as the bar, or as wide on a bar at the left or right, and
`implicitWidth` tells it how much room the widget needs along the bar. A `Label` takes the theme's bar font by
itself. While `watch` is on, the bar loads the file again each time you save it. If the file has an error, an
alert shows it, and the bar keeps the version it showed.

## Data from a service

Each service is a QML type from `import Yasb`. [CpuMonitor](./(Service)-Cpu) reads the CPU usage. The widget
creates one and shows its `data`:

```qml
// %USERPROFILE%\.config\yasb\widgets\CpuLoad\CpuLoad.qml
import QtQuick
import QtQuick.Controls
import Yasb
import Yasb.Bar

Item {
    id: root

    required property BarBase bar

    implicitWidth: label.implicitWidth
    implicitHeight: label.implicitHeight

    CpuMonitor {
        id: monitor

        updateInterval: 2000
    }

    Label {
        id: label

        anchors.verticalCenter: parent.verticalCenter
        text: `CPU ${monitor.data.percent.total.toFixed(0)}%`
        color: root.bar.theme.colors.text
    }
}
```

The label changes each time `monitor.data` does. `root.bar.theme` is the bar's [Theme](./(Type)-Theme), so the text
takes the theme's color, and changes with it in light and dark mode.

## Options

YASB's widgets keep their options together at the top, in a `component Settings`, each with its value. Values from
the theme stay up to date with it, and anyone who opens the file sees at once what they can change. The widget
makes one `Settings` and reads its options from `settings`:

```qml
// %USERPROFILE%\.config\yasb\widgets\CpuLoad\CpuLoad.qml
import QtQuick
import QtQuick.Controls
import Yasb
import Yasb.Bar
import Yasb.Themes

Item {
    id: root

    component Settings: QtObject {
        required property Theme theme

        // Milliseconds between two readings
        property int updateInterval: 2000
        // The usage, in percent, from which the text turns to warnColor
        property real warnAt: 90
        property color textColor: theme.colors.text
        property color warnColor: theme.colors.critical
    }

    required property BarBase bar
    readonly property Theme theme: bar.theme
    readonly property Settings settings: Settings {
        theme: root.theme
    }
    readonly property real usage: monitor.data.percent.total

    implicitWidth: label.implicitWidth
    implicitHeight: label.implicitHeight

    CpuMonitor {
        id: monitor

        updateInterval: root.settings.updateInterval
    }

    Label {
        id: label

        anchors.verticalCenter: parent.verticalCenter
        text: `CPU ${root.usage.toFixed(0)}%`
        color: root.usage >= root.settings.warnAt ? root.settings.warnColor : root.settings.textColor
    }
}
```

## A popup, a hotkey and a toast

The finished widget adds three things:

- A [BackdropPopup](./(Type)-BackdropPopup) opens on a click. It's a window of its own, which the widget places next
  to itself. It closes on Escape, or when you click elsewhere, and it blurs what's behind it when the bar has
  `backdrop: true`.
- A [Process](./(Service)-Process) runs PowerShell when the popup opens, and the popup shows what it printed: the five
  processes that have used the most CPU time.
- A [Hotkey](./(Type)-Hotkey) opens the popup from the keyboard, and [Notifier](./(Type)-Notifier) shows a Windows
  toast when the CPU gets busy.

```qml
// %USERPROFILE%\.config\yasb\widgets\CpuLoad\CpuLoad.qml
import QtQuick
import QtQuick.Controls
import Yasb
import Yasb.Bar
import Yasb.Common
import Yasb.Themes

Item {
    id: root

    component Settings: QtObject {
        required property Theme theme

        // Milliseconds between two readings
        property int updateInterval: 2000
        // The usage, in percent, from which the text turns to warnColor and a toast shows
        property real warnAt: 90
        // Keys that open the popup, such as "alt+shift+l"; "" for none
        property string hotkey: ""
        property color textColor: theme.colors.text
        property color warnColor: theme.colors.critical
        // The popup: the theme's, unless set here
        property int popupWidth: 240
        property color popupColor: theme.popup.background
        property color popupBorderColor: theme.popup.border
        property real popupRadius: theme.popup.radius
        property real popupGap: theme.popup.gap
        property font popupFont
        popupFont.family: theme.popup.font.family
        popupFont.pixelSize: 13
    }

    required property BarBase bar
    readonly property Theme theme: bar.theme
    readonly property Settings settings: Settings {
        theme: root.theme
    }
    readonly property real usage: monitor.data.percent.total
    readonly property bool busy: usage >= settings.warnAt

    function togglePopup() {
        if (popup.visible) {
            popup.close()
            return
        }
        const start = mapToGlobal(0, 0)
        popup.x = Math.round(start.x + (width - popup.width) / 2)
        popup.y = Math.round(bar.edge === "bottom" ? start.y - popup.height - settings.popupGap
            : start.y + height + settings.popupGap)
        busiest.run()
        popup.open()
    }

    implicitWidth: label.implicitWidth
    implicitHeight: label.implicitHeight

    onBusyChanged: {
        if (busy)
            Notifier.toast("CPU", `The CPU is at ${usage.toFixed(0)}%`)
    }

    // The popup is a window of its own, so it goes when the widget does
    Component.onDestruction: popup.hide()

    CpuMonitor {
        id: monitor

        updateInterval: root.settings.updateInterval
    }

    Process {
        id: busiest

        command: ["powershell", "-NoProfile", "-Command",
            "Get-Process | Sort-Object CPU -Descending | Select-Object -First 5 -ExpandProperty ProcessName"]
    }

    Hotkey {
        keys: root.settings.hotkey
        onActivated: root.togglePopup()
    }

    Label {
        id: label

        anchors.verticalCenter: parent.verticalCenter
        text: `CPU ${root.usage.toFixed(0)}%`
        color: root.busy ? root.settings.warnColor : root.settings.textColor
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: root.togglePopup()
    }

    BackdropPopup {
        id: popup

        width: root.settings.popupWidth
        height: list.implicitHeight + 24
        anchor: root
        theme: root.theme
        font: root.settings.popupFont
        backdropItem: surface

        Rectangle {
            id: surface

            anchors.fill: parent
            radius: root.settings.popupRadius
            color: root.settings.popupColor
            border.width: 1
            border.color: root.settings.popupBorderColor

            Label {
                id: list

                x: 12
                y: 12
                width: parent.width - 24
                wrapMode: Text.Wrap
                text: busiest.running ? "Loading..." : busiest.error || busiest.output.trim()
            }
        }
    }
}
```

The popup's `anchor` is the widget, so a click on the widget closes the popup again instead of opening a second one.
`backdropItem` is the item the blur follows, with its corners. Each `Label` in the popup takes the popup's `font`,
and its text color from the theme.

## Keep a token out of the file

A widget that calls an API often needs a key or a token. Put it in the `.env` file in your config folder, one
`NAME=value` per line:

```text
IPINFO_TOKEN=your-token
```

[Environment](./(Type)-Environment) reads it, and the widget file stays safe to share. This widget shows your
country, asked every ten minutes while the widget shows:

```qml
// %USERPROFILE%\.config\yasb\widgets\Country\Country.qml
import QtQuick
import QtQuick.Controls
import Yasb
import Yasb.Bar

Item {
    id: root

    required property BarBase bar

    implicitWidth: label.implicitWidth
    implicitHeight: label.implicitHeight

    Process {
        id: ip

        command: ["curl.exe", "-s", "-H", `Authorization: Bearer ${Environment.value("IPINFO_TOKEN")}`,
            "https://api.ipinfo.io/lite/me"]
        format: "json"
        interval: 600000
        active: root.visible
    }

    Label {
        id: label

        anchors.verticalCenter: parent.verticalCenter
        text: ip.data?.country ?? (ip.error ? "offline" : "...")
        color: root.bar.theme.colors.text
    }
}
```

YASB reads `.env` when it starts, so reload YASB after you change it.

## Files beside the widget

A widget's folder can hold more files, such as icons or sounds. `Qt.resolvedUrl()` finds them next to the widget
file: `Image { source: Qt.resolvedUrl("icon.svg") }`, or `Notifier.playSound(Qt.resolvedUrl("ding.wav"))`.

## What a widget can use

- **Services**, from `import Yasb`: one type for each thing YASB reads, such as the CPU, the battery, the media
  playing or your windows. Each one has a page in the sidebar, under **Services**.
- **Utilities**, from `import Yasb`: [Process](./(Service)-Process) runs a program, [Hotkey](./(Type)-Hotkey) gives a
  global key combination, [Notifier](./(Type)-Notifier) shows toasts and plays sounds, and
  [Environment](./(Type)-Environment) reads environment variables.
- **Popups**, from `import Yasb.Common`: [BackdropPopup](./(Type)-BackdropPopup), and
  [LoadingLine](./(Type)-LoadingLine) for a popup that is loading.
- **The bar and its theme**, from `import Yasb.Bar` and `import Yasb.Themes`: [BarBase](./(Type)-BarBase) is the
  `bar` property, with its `edge`, `vertical` and `theme`.
- **Qt**: everything in Qt Quick, Qt Quick Controls, Qt Quick Layouts and Qt Quick Shapes.

YASB's own widgets are in `core\qml\Yasb\Widgets` in YASB's folder, or in
[YASB's repository](https://github.com/amnweb/yasb/tree/main/src/core/qml/Yasb/Widgets). Each one is a full example.

## Share your widget

To let others install your widget with `yasbc addons install`, add a `manifest.json` and publish it as an addon.
[Addons](./Addons) explains how.
