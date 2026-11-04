pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Yasb
import Yasb.Common

Item {
    id: bluetooth

    property Item bar: null
    // Label placeholders: {device_name} and {device_count}; empty shows only the icon
    property string label: ""
    property string alternateLabel: "{device_name}"
    property string noDeviceLabel: "No devices connected"
    property string deviceSeparator: ", "
    // Longest label in characters, 0 for no limit
    property int maxLength: 0
    // Names to show instead of the devices' own, such as ({ "WH-1000XM4": "Headphones" })
    property var deviceAliases: ({})
    // The connected devices when the pointer rests on the widget
    property bool tooltip: true
    property int iconSize: 16
    property string offIcon: "\ue702"
    property string onIcon: "\ue702"
    property string connectedIcon: "\ue702"
    // Popup glyphs for each kind of device
    property var deviceIcons: ({
        headphones: "\ue7f6",
        headset: "\ue95b",
        speaker: "\ue7f5",
        phone: "\ue8ea",
        tablet: "\ue70a",
        laptop: "\ue7f8",
        computer: "\ue950",
        keyboard: "\ue765",
        mouse: "\ue962",
        controller: "\ue7fc",
        watch: "\ue918",
        camera: "\ue722",
        generic: "\ue702"
    })
    // Battery glyphs for up to 10, 30, 60, 90 and 100 percent
    property list<string> batteryIcons: ["\ueba0", "\ueba2", "\ueba5", "\ueba8", "\uebaa"]
    property int popupWidth: 360
    // Popup alignment relative to the widget on a horizontal bar: left, right or center
    property string popupAlignment: "center"
    // Scroll the device list when it exceeds this height
    property int maxListHeight: 320
    property color errorColor: dark ? "#ff99a4" : "#c42b1c"

    property bool showAlternate: false

    readonly property bool dark: bar ? bar.dark : Qt.styleHints.colorScheme === Qt.ColorScheme.Dark
    // Text on the bar takes the bar's colour and font, each part unless the widget file sets it
    property color textColor: bar?.textColor ?? (dark ? "#ffffff" : "#000000")
    // The bar icon, by state for example: !radioOn ? "#808080" : names.length > 0 ? palette.active.accent : textColor
    property color iconColor: !radioOn ? textColor : names.length > 0 ? palette.active.accent : textColor
    property font font
    font.family: bar?.font.family ?? Qt.application.font.family
    font.pixelSize: bar?.font.pixelSize ?? 13
    font.weight: bar?.font.weight ?? Font.Normal
    font.italic: bar?.font.italic ?? false
    font.letterSpacing: bar?.font.letterSpacing ?? 0
    font.capitalization: bar?.font.capitalization ?? Font.MixedCase
    font.variableAxes: bar?.font.variableAxes ?? ({})
    // Glyphs take the family and weight of the bar's icon font unless the widget file sets them
    property font iconFont
    iconFont.family: bar?.iconFont?.family ?? "Segoe Fluent Icons"
    iconFont.weight: bar?.iconFont?.weight ?? Font.Normal
    readonly property string edge: bar?.edge ?? "top"

    // Whether Bluetooth is on, and the names of the connected devices
    readonly property bool radioOn: monitor.radioOn
    readonly property list<string> names: monitor.connected.map(name => bluetooth.deviceAliases[name.trim()] ?? name)
    readonly property string text: format(showAlternate ? alternateLabel : label)

    function format(template: string): string {
        if (template === "")
            return ""
        const values = {
            device_name: names.length > 0 ? names.join(deviceSeparator) : noDeviceLabel,
            device_count: String(names.length)
        }
        const text = template.replace(/\{(\w+)\}/g, (match, key) => values[key] ?? match)
        return maxLength > 0 && text.length > maxLength ? text.slice(0, maxLength) + "..." : text
    }

    function batteryIcon(percent: int): string {
        const ceilings = [10, 30, 60, 90]
        const band = ceilings.findIndex(ceiling => percent <= ceiling)
        return batteryIcons[Math.min(band < 0 ? 4 : band, batteryIcons.length - 1)] ?? ""
    }

    function placePopup() {
        const start = mapToGlobal(0, 0)
        const gap = 6
        const margin = 8
        let px
        let py
        switch (edge) {
        case "left":
            px = start.x + width + gap
            py = start.y + (height - popup.height) / 2
            break
        case "right":
            px = start.x - popup.width - gap
            py = start.y + (height - popup.height) / 2
            break
        default:
            px = popupAlignment === "left" ? start.x
                : popupAlignment === "right" ? start.x + width - popup.width : start.x + (width - popup.width) / 2
            py = edge === "bottom" ? start.y - popup.height - gap : start.y + height + gap
            break
        }
        const screen = bluetooth.Screen
        px = Math.max(screen.virtualX + margin, Math.min(px, screen.virtualX + screen.width - popup.width - margin))
        py = Math.max(screen.virtualY + margin, Math.min(py, screen.virtualY + screen.desktopAvailableHeight - popup.height - margin))
        popup.x = Math.round(px)
        popup.y = Math.round(py)
    }

    function togglePopup() {
        if (popup.visible) {
            popup.close()
            return
        }
        popup.expanded = ""
        placePopup()
        popup.open()
    }

    function openSettings() {
        Qt.openUrlExternally("ms-settings:bluetooth")
        popup.close()
    }

    implicitWidth: row.implicitWidth
    implicitHeight: row.implicitHeight
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: !monitor.radioOn ? qsTr("Bluetooth, off")
        : names.length > 0 ? qsTr("Bluetooth, connected to %1").arg(names.join(", ")) : qsTr("Bluetooth, on")
    Accessible.onPressAction: togglePopup()
    Keys.onReturnPressed: togglePopup()
    Keys.onSpacePressed: togglePopup()

    Component.onDestruction: popup.hide()

    BluetoothMonitor {
        id: monitor

        watching: popup.visible
    }

    Connections {
        target: bluetooth.Window.window

        function onVisibleChanged() {
            if (!bluetooth.Window.window?.visible)
                popup.hide()
        }

        function onXChanged() {
            if (popup.visible)
                bluetooth.placePopup()
        }

        function onYChanged() {
            if (popup.visible)
                bluetooth.placePopup()
        }
    }

    // Keep the popup anchored when its height changes
    Connections {
        target: popup

        function onHeightChanged() {
            if (popup.visible)
                bluetooth.placePopup()
        }
    }

    component Glyph: Text {
        textFormat: Text.PlainText
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        font.family: bluetooth.iconFont.family
        font.weight: bluetooth.iconFont.weight
    }

    component SectionTitle: Text {
        leftPadding: 12
        topPadding: 6
        bottomPadding: 4
        textFormat: Text.PlainText
        color: Qt.alpha(popup.ink, 0.65)
        font.pixelSize: 12
    }

    component DeviceRow: Item {
        id: device

        required property string address
        required property string name
        required property string kind
        required property bool connected
        required property bool known
        required property int battery
        required property var profiles
        required property bool canConnect

        readonly property bool expanded: popup.expanded === address
        readonly property bool working: monitor.pending === address
        readonly property string statusText: !connected ? qsTr("Not connected")
            : profiles.length > 0 ? qsTr("Connected %1").arg(profiles.join(", ")) : qsTr("Connected")
        // Pairing and devices YASB cannot connect are left to Windows Settings
        readonly property bool inSettings: !known || !canConnect
        readonly property string action: {
            if (!known)
                return qsTr("Pair")
            if (!canConnect)
                return qsTr("Manage")
            if (working)
                return connected ? qsTr("Disconnecting") : qsTr("Connecting")
            return connected ? qsTr("Disconnect") : qsTr("Connect")
        }

        function act() {
            if (inSettings)
                bluetooth.openSettings()
            else if (connected)
                monitor.disconnectDevice(address)
            else
                monitor.connectDevice(address)
        }

        width: parent?.width ?? 0
        height: rows.implicitHeight
        Accessible.role: Accessible.ListItem
        Accessible.name: battery >= 0 ? `${name}, ${statusText}, ${battery}%` : `${name}, ${statusText}`

        Rectangle {
            anchors.fill: parent
            radius: 8
            color: Qt.alpha(popup.ink, device.expanded ? 0.03 : headerArea.containsMouse ? 0.06 : 0)
            border.width: device.expanded ? 1 : 0
            border.color: Qt.alpha(popup.ink, 0.04)
        }

        ColumnLayout {
            id: rows

            width: parent.width
            spacing: 0

            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 48

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    spacing: 12

                    Glyph {
                        Layout.preferredWidth: 20
                        Layout.preferredHeight: 20
                        text: bluetooth.deviceIcons[device.kind] ?? bluetooth.deviceIcons.generic ?? ""
                        color: popup.ink
                        font.pixelSize: 20
                    }

                    Column {
                        Layout.fillWidth: true

                        Text {
                            width: parent.width
                            text: device.name
                            textFormat: Text.PlainText
                            elide: Text.ElideRight
                            color: popup.ink
                            font.pixelSize: 13
                        }

                        Text {
                            width: parent.width
                            text: device.statusText
                            textFormat: Text.PlainText
                            elide: Text.ElideRight
                            color: Qt.alpha(popup.ink, 0.65)
                            font.pixelSize: 12
                        }
                    }

                    Text {
                        objectName: "battery"
                        visible: device.battery >= 0
                        text: `${device.battery}%`
                        color: Qt.alpha(popup.ink, 0.65)
                        font.pixelSize: 12
                    }

                    Glyph {
                        visible: device.battery >= 0
                        text: bluetooth.batteryIcon(device.battery)
                        color: popup.ink
                        font.pixelSize: 16
                    }
                }

                MouseArea {
                    id: headerArea

                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (!device.working)
                            popup.expanded = device.expanded ? "" : device.address
                    }
                }
            }

            Button {
                objectName: "action"
                Layout.alignment: Qt.AlignRight
                Layout.preferredWidth: 140
                Layout.rightMargin: 12
                Layout.bottomMargin: 10
                visible: device.expanded
                text: device.action
                highlighted: !device.connected && !device.inSettings
                enabled: !device.working && (device.inSettings || monitor.pending === "")
                onClicked: device.act()
            }
        }
    }

    Row {
        id: row

        height: parent.height
        spacing: 6

        Glyph {
            objectName: "icon"
            y: Math.round((parent.height - height) / 2)
            width: bluetooth.iconSize
            height: bluetooth.iconSize
            text: !bluetooth.radioOn ? bluetooth.offIcon : bluetooth.names.length > 0 ? bluetooth.connectedIcon : bluetooth.onIcon
            color: bluetooth.iconColor
            font.pixelSize: bluetooth.iconSize
        }

        Text {
            objectName: "label"
            anchors.verticalCenter: parent.verticalCenter
            visible: text !== ""
            text: bluetooth.text
            textFormat: Text.PlainText
            color: bluetooth.textColor
            font: bluetooth.font
        }
    }

    MouseArea {
        id: area

        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: mouse => {
            if (mouse.button === Qt.LeftButton)
                bluetooth.togglePopup()
            else
                bluetooth.showAlternate = !bluetooth.showAlternate
        }
    }

    ToolTip {
        objectName: "tooltip"
        popupType: Popup.Window
        visible: bluetooth.tooltip && area.containsMouse && !popup.visible
        delay: 400
        text: bluetooth.names.length > 0
            ? [qsTr("Connected devices"), ...bluetooth.names.map(name => `\u2022 ${name}`)].join("\n")
            : bluetooth.noDeviceLabel
        // Away from the bar's edge
        y: bluetooth.edge === "bottom" ? -implicitHeight - 6 : bluetooth.height + 6
    }

    BackdropPopup {
        id: popup

        property real reveal: 0
        // Address of the device whose button shows
        property string expanded: ""
        readonly property color ink: bluetooth.dark ? "#ffffff" : "#000000"

        objectName: "popup"
        title: "Bluetooth"
        width: bluetooth.popupWidth
        height: popupContent.implicitHeight + 16
        anchor: bluetooth
        backdropItem: surface
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: 180; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: 140; easing.type: Easing.InCubic }
        onVisibleChanged: {
            if (!visible)
                reveal = 0
        }

        Rectangle {
            id: surface

            anchors.fill: parent
            anchors.margins: 8
            radius: 8
            color: bluetooth.dark ? Qt.alpha("#202020", 0.85) : Qt.alpha("#F3F3F3", 0.85)
            border.width: 1
            border.color: bluetooth.dark ? "#3A3A3A" : "#D9D9D9"
            opacity: popup.reveal
            scale: 0.85 + popup.reveal * 0.15
            transformOrigin: bluetooth.edge === "bottom" ? Item.Bottom : Item.Top

            ColumnLayout {
                id: popupContent

                width: parent.width
                spacing: 0

                RowLayout {
                    Layout.fillWidth: true
                    Layout.leftMargin: 16
                    Layout.rightMargin: 10
                    Layout.topMargin: 6
                    Layout.bottomMargin: 6

                    Text {
                        Layout.fillWidth: true
                        text: qsTr("Bluetooth")
                        font.bold: true
                        color: popup.ink
                        font.pixelSize: 16
                    }

                    Switch {
                        id: power

                        objectName: "power"
                        checked: monitor.radioOn
                        Accessible.name: qsTr("Bluetooth")
                        onToggled: {
                            monitor.setRadio(checked)
                            checked = Qt.binding(() => monitor.radioOn)
                        }
                    }
                }

                LoadingLine {
                    Layout.fillWidth: true
                    running: monitor.busy || monitor.pending !== ""
                    trackColor: Qt.alpha(popup.ink, 0.1)
                }

                Text {
                    objectName: "error"
                    Layout.fillWidth: true
                    Layout.leftMargin: 16
                    Layout.rightMargin: 16
                    Layout.topMargin: 10
                    visible: monitor.error !== ""
                    text: monitor.error
                    textFormat: Text.PlainText
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                    color: bluetooth.errorColor
                    font.pixelSize: 12
                }

                Text {
                    objectName: "placeholder"
                    Layout.fillWidth: true
                    Layout.topMargin: 24
                    Layout.bottomMargin: 24
                    visible: !list.visible
                    text: !monitor.radioOn ? qsTr("Bluetooth is turned off")
                        : monitor.busy ? qsTr("Looking for devices...") : qsTr("No devices found")
                    horizontalAlignment: Text.AlignHCenter
                    color: Qt.alpha(popup.ink, 0.5)
                    font.pixelSize: 13
                }

                Flickable {
                    id: list

                    objectName: "devices"
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(contentHeight, bluetooth.maxListHeight)
                    Layout.margins: 6
                    visible: monitor.radioOn && monitor.devices.count + monitor.nearby.count > 0
                    clip: true
                    contentHeight: sections.implicitHeight
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar {}

                    Column {
                        id: sections

                        width: list.width
                        spacing: 2

                        SectionTitle {
                            visible: monitor.devices.count > 0
                            text: qsTr("Your devices")
                        }

                        Repeater {
                            objectName: "known"
                            model: monitor.devices
                            delegate: DeviceRow {}
                        }

                        SectionTitle {
                            visible: monitor.nearby.count > 0
                            text: qsTr("New devices")
                        }

                        Repeater {
                            objectName: "nearby"
                            model: monitor.nearby
                            delegate: DeviceRow {}
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.leftMargin: 1
                    Layout.rightMargin: 1
                    Layout.bottomMargin: 1
                    implicitHeight: 44
                    bottomLeftRadius: 7
                    bottomRightRadius: 7
                    color: Qt.alpha("#000000", bluetooth.dark ? 0.15 : 0.03)

                    Rectangle {
                        width: parent.width
                        height: 1
                        color: Qt.alpha(popup.ink, 0.1)
                    }

                    Text {
                        anchors.left: parent.left
                        anchors.leftMargin: 15
                        anchors.verticalCenter: parent.verticalCenter
                        text: qsTr("More Bluetooth settings")
                        color: settingsArea.containsMouse ? popup.ink : Qt.alpha(popup.ink, 0.65)
                        font.pixelSize: 12
                        Accessible.role: Accessible.Link
                        Accessible.name: text
                        Accessible.onPressAction: bluetooth.openSettings()

                        MouseArea {
                            id: settingsArea

                            anchors.fill: parent
                            anchors.margins: -8
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: bluetooth.openSettings()
                        }
                    }

                    Item {
                        objectName: "scan"
                        anchors.right: parent.right
                        anchors.rightMargin: 8
                        anchors.verticalCenter: parent.verticalCenter
                        width: 28
                        height: 28
                        enabled: monitor.radioOn && !monitor.busy
                        opacity: enabled ? 1 : 0.4
                        Accessible.role: Accessible.Button
                        Accessible.name: qsTr("Find devices")
                        Accessible.onPressAction: monitor.scan()
                        ToolTip.visible: scanArea.containsMouse
                        ToolTip.delay: 500
                        ToolTip.text: qsTr("Find devices")

                        Rectangle {
                            anchors.fill: parent
                            radius: 4
                            color: Qt.alpha(popup.ink, scanArea.containsMouse ? 0.1 : 0)
                        }

                        Glyph {
                            anchors.fill: parent
                            text: "\ue72c"
                            color: popup.ink
                            font.pixelSize: 14
                        }

                        MouseArea {
                            id: scanArea

                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: monitor.scan()
                        }
                    }
                }
            }
        }
    }
}
