# Writing widgets

A widget is a QML file in your config folder. YASB's Python services provide the data, such as CPU usage or what's
playing, and the widget decides how to display it. This page builds one widget step by step: a CPU meter that warns when
the CPU is busy and opens a popup with the busiest processes. Each step shows the whole file.

You'll need some basic QML. Qt's [QML introduction](https://doc.qt.io/qt-6/qmlfirststeps.html) covers everything this
page uses, and all of [Qt Quick's types](https://doc.qt.io/qt-6/qtquick-qmlmodule.html) are available to widgets.

## A widget on the bar

A widget is a folder in `widgets` with a QML file of the same name in it. Make
`widgets\CpuLoad\CpuLoad.qml` in your config folder:

```qml
// %USERPROFILE%\.config\yasb\widgets\CpuLoad\CpuLoad.qml
import QtQuick
import QtQuick.Controls
import Yasb.Bar

Item {
    // Set by YASB to the bar the widget is in
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

The bar now shows "Hello". YASB sizes the widget to the bar's height, or its width on a bar at the left or right, and
`implicitWidth` tells it how much space the widget needs along the bar. A `Label` uses the theme's bar font by default.
With `watch` on, the bar reloads the file every time you save it. If the file has an error, an alert shows it and the
bar keeps the previous version.

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

The label updates whenever `monitor.data` changes. `root.bar.theme` is the bar's [Theme](./(Type)-Theme), so the text
uses the theme's color and follows it between light and dark mode.

## Options

The built-in widgets declare all their options at the top, in a `component Settings`, each with its default value.
Defaults bound to the theme stay in sync with it, and anyone who opens the file can see right away what's configurable.
The widget creates one `Settings` and reads its options from `settings`:

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

- A [BackdropPopup](./(Type)-BackdropPopup) opens on a click. It's a separate window that the widget positions next to
  itself. It closes on Escape or when you click elsewhere, and its background is blurred when the bar has
  `backdrop: true`.
- A [Process](./(Service)-Process) runs a PowerShell command when the popup opens, and the popup shows its output: the
  five processes that have used the most CPU time.
- A [Hotkey](./(Type)-Hotkey) opens the popup from the keyboard, and [Notifier](./(Type)-Notifier) shows a Windows toast
  when the CPU gets busy.

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

    // The popup is a separate window, so hide it when the widget is destroyed
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

Because the popup's `anchor` is the widget, clicking the widget again closes the popup instead of opening it a second
time. `backdropItem` is the item the blur follows, including its rounded corners. Each `Label` in the popup uses the
popup's `font` and gets its text color from the theme.

## Keep a token out of the file

A widget that calls an API often needs a key or a token. Put it in the `.env` file in your config folder, one
`NAME=value` per line:

```text
IPINFO_TOKEN=your-token
```

Read it with [Environment](./(Type)-Environment), and the widget file stays safe to share. This widget shows your
country, fetched every ten minutes while the widget is visible:

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

A widget's folder can hold more files, such as icons or sounds. `Qt.resolvedUrl()` resolves paths relative to the widget
file: `Image { source: Qt.resolvedUrl("icon.svg") }`, or `Notifier.playSound(Qt.resolvedUrl("ding.wav"))`.

## What a widget can use

- **Services**, from `import Yasb`: one type for each thing YASB reads, such as the CPU, the battery, the media playing
  or your windows. Each one has a page in the sidebar, under **Services**.
- **Utilities**, from `import Yasb`: [Process](./(Service)-Process) runs a program, [Hotkey](./(Type)-Hotkey) registers
  a global shortcut, [Notifier](./(Type)-Notifier) shows toasts and plays sounds, and
  [Environment](./(Type)-Environment) reads environment variables.
- **Popups**, from `import Yasb.Common`: [BackdropPopup](./(Type)-BackdropPopup), and
  [LoadingLine](./(Type)-LoadingLine), a loading indicator for popups.
- **The bar and its theme**, from `import Yasb.Bar` and `import Yasb.Themes`: the `bar` property is a
  [BarBase](./(Type)-BarBase), with its `edge`, `vertical` and `theme`.
- **Qt**: everything in Qt Quick, Qt Quick Controls, Qt Quick Layouts and Qt Quick Shapes.

YASB's own widgets are in `core\qml\Yasb\Widgets` in YASB's folder, or in
[YASB's repository](https://github.com/amnweb/yasb/tree/main/src/core/qml/Yasb/Widgets). Each one is a full example.

## Share your widget

To let others install your widget with `yasbc addons install`, add a `manifest.json` and publish it as an addon.
[Addons](./Addons) explains how.
