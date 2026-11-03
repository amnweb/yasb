pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Yasb
import Yasb.Bar
import Yasb.Common

Item {
    id: wifi

    // Label placeholders: {wifi_name}, {wifi_strength}, {ip_addr}; empty shows only the icon.
    property string label: ""
    property string alternateLabel: "{wifi_name}"
    // Labels to use when connected by Ethernet.
    property string ethernetLabel: ""
    property string ethernetAlternateLabel: "{ip_addr}"
    property int updateInterval: 1000
    // Use exact WLAN quality instead of signal bars in 25-point steps.
    property bool exactStrength: false
    // Hide the widget while the internet goes through a cable
    property bool hideIfEthernet: false
    property int iconSize: 16
    // Signal glyphs, weakest first; the strongest forms a faint background.
    property string iconFont: Qt.fontFamilies().includes("Segoe Fluent Icons") ? "Segoe Fluent Icons" : "Segoe MDL2 Assets"
    property list<string> wifiIcons: ["", "", "", ""]
    // Networks in the popup, with and without a password
    property list<string> securedIcons: ["", "", "", ""]
    property list<string> openIcons: ["", "", "", ""]
    property string ethernetIcon: ""
    property string disconnectedIcon: ""
    property int popupWidth: 360
    // Popup alignment relative to the widget on a horizontal bar: left, right, or center.
    property string popupAlignment: "center"
    // Scroll the network list when it exceeds this height.
    property int maxListHeight: 320
    property color errorColor: dark ? "#ff99a4" : "#c42b1c"

    property BarBase bar: null

    property bool showAlternate: false

    readonly property bool dark: bar ? bar.dark : Application.styleHints.colorScheme === Qt.ColorScheme.Dark
    // Inherit the bar's text color and font unless overridden here.
    property color textColor: bar?.textColor ?? (dark ? "#ffffff" : "#000000")
    property font font
    font.family: bar?.font.family ?? Application.font.family
    font.pixelSize: bar?.font.pixelSize ?? 13
    font.weight: bar?.font.weight ?? Font.Normal
    font.italic: bar?.font.italic ?? false
    font.letterSpacing: bar?.font.letterSpacing ?? 0
    font.capitalization: bar?.font.capitalization ?? Font.MixedCase
    font.variableAxes: bar?.font.variableAxes ?? ({})
    readonly property string edge: bar?.edge ?? "top"

    // Connection kind: wifi, ethernet, or none.
    readonly property var status: monitor.status
    readonly property bool ethernet: status.kind === "ethernet"
    readonly property bool shown: !(hideIfEthernet && ethernet)
    readonly property string text: {
        if (ethernet)
            return format(showAlternate ? ethernetAlternateLabel : ethernetLabel)
        return format(showAlternate ? alternateLabel : label)
    }

    // Map strength to an icon index from 0 to 3.
    function level(strength: int): int {
        return Math.max(0, Math.min(3, Math.floor(strength / 25)))
    }

    function format(template: string): string {
        if (template === "")
            return ""
        const values = {
            wifi_name: status.name || "Disconnected",
            wifi_strength: status.strength >= 0 ? String(status.strength) : "N/A",
            ip_addr: status.ipAddress || "N/A"
        }
        return template.replace(/\{(\w+)\}/g, (match, key) => values[key] ?? match)
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
        const screen = wifi.Screen
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
        // Expand the connected network when opening the popup.
        popup.expanded = status.kind === "wifi" ? status.name : undefined
        placePopup()
        popup.open()
    }

    implicitWidth: shown ? row.implicitWidth : 0
    implicitHeight: shown ? row.implicitHeight : 0
    visible: shown
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: ethernet ? `Ethernet, ${status.name}` : status.kind === "wifi" ? `Wi-Fi, ${status.name}, ${status.strength}%`
        : "Not connected"
    Accessible.onPressAction: togglePopup()
    Keys.onReturnPressed: togglePopup()
    Keys.onSpacePressed: togglePopup()

    Component.onDestruction: popup.hide()

    WifiMonitor {
        id: monitor

        updateInterval: wifi.updateInterval
        exactStrength: wifi.exactStrength
        watching: popup.visible
    }

    Connections {
        target: wifi.Window.window

        function onVisibleChanged() {
            if (!wifi.Window.window?.visible)
                popup.hide()
        }

        function onXChanged() {
            if (popup.visible)
                wifi.placePopup()
        }

        function onYChanged() {
            if (popup.visible)
                wifi.placePopup()
        }
    }

    // Keep the popup anchored when its height changes.
    Connections {
        target: popup

        function onHeightChanged() {
            if (popup.visible)
                wifi.placePopup()
        }
    }

    component Glyph: Text {
        textFormat: Text.PlainText
        font.family: wifi.iconFont
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }

    // Show signal strength as stacked glyphs, or show one status glyph.
    component SignalIcon: Item {
        id: signal

        property list<string> icons
        property int strength: 0
        property string glyph: ""
        property int size: 16
        property color color

        implicitWidth: size
        implicitHeight: size

        Glyph {
            anchors.fill: parent
            text: signal.glyph || (signal.icons.length > 0 ? signal.icons[signal.icons.length - 1] : "")
            color: signal.color
            opacity: signal.glyph ? 1 : 0.3
            font.pixelSize: signal.size
        }

        Glyph {
            anchors.fill: parent
            visible: !signal.glyph
            text: signal.icons.length > 0 ? signal.icons[Math.min(wifi.level(signal.strength), signal.icons.length - 1)] : ""
            color: signal.color
            font.pixelSize: signal.size
        }
    }

    Row {
        id: row

        height: parent.height
        spacing: 6

        SignalIcon {
            objectName: "icon"
            y: Math.round((parent.height - height) / 2)
            size: wifi.iconSize
            icons: wifi.wifiIcons
            strength: wifi.status.strength
            glyph: wifi.ethernet ? wifi.ethernetIcon : wifi.status.kind === "none" ? wifi.disconnectedIcon : ""
            color: wifi.textColor
        }

        Text {
            objectName: "label"
            anchors.verticalCenter: parent.verticalCenter
            visible: text !== ""
            text: wifi.text
            textFormat: Text.PlainText
            color: wifi.textColor
            font: wifi.font
        }
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: mouse => {
            if (mouse.button === Qt.LeftButton)
                wifi.togglePopup()
            else
                wifi.showAlternate = !wifi.showAlternate
        }
    }

    BackdropPopup {
        id: popup

        property real reveal: 0
        // SSID whose controls are open; empty for a hidden network.
        property var expanded: undefined
        readonly property color ink: wifi.dark ? "#ffffff" : "#000000"

        objectName: "popup"
        title: "Wi-Fi"
        width: wifi.popupWidth
        height: popupContent.implicitHeight + 16
        anchor: wifi
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
            color: wifi.dark ? Qt.alpha("#202020", 0.85) : Qt.alpha("#F3F3F3", 0.85)
            border.width: 1
            border.color: wifi.dark ? "#3A3A3A" : "#D9D9D9"
            opacity: popup.reveal
            scale: 0.85 + popup.reveal * 0.15
            transformOrigin: wifi.edge === "bottom" ? Item.Bottom : Item.Top

            ColumnLayout {
                id: popupContent

                width: parent.width
                spacing: 0

                Text {
                    Layout.fillWidth: true
                    Layout.leftMargin: 16
                    Layout.rightMargin: 10
                    Layout.topMargin: 12
                    Layout.bottomMargin: 12
                    text: "<b>Wi-Fi</b> Networks"
                    textFormat: Text.StyledText
                    color: popup.ink
                    font.family: "Segoe UI"
                    font.pixelSize: 16
                }

                LoadingLine {
                    Layout.fillWidth: true
                    running: monitor.scanning || monitor.connecting
                    trackColor: Qt.alpha(popup.ink, 0.1)
                }

                // Show the Ethernet connection above available Wi-Fi networks.
                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 48
                    Layout.leftMargin: 18
                    Layout.rightMargin: 18
                    Layout.topMargin: 6
                    visible: wifi.ethernet
                    spacing: 12
                    Accessible.role: Accessible.StaticText
                    Accessible.name: `Ethernet, ${wifi.status.name}, connected`

                    Glyph {
                        Layout.preferredWidth: 20
                        Layout.preferredHeight: 20
                        text: wifi.ethernetIcon
                        color: popup.ink
                        font.pixelSize: 20
                    }

                    Text {
                        Layout.fillWidth: true
                        text: wifi.status.name || "Ethernet"
                        textFormat: Text.PlainText
                        elide: Text.ElideRight
                        color: popup.ink
                        font.family: "Segoe UI"
                        font.pixelSize: 13
                    }

                    Column {
                        Text {
                            anchors.right: parent.right
                            text: "Connected"
                            color: Qt.alpha(popup.ink, 0.65)
                            font.family: "Segoe UI"
                            font.pixelSize: 12
                        }

                        Text {
                            anchors.right: parent.right
                            visible: text !== ""
                            text: wifi.status.ipAddress
                            color: Qt.alpha(popup.ink, 0.5)
                            font.family: "Segoe UI"
                            font.pixelSize: 12
                        }
                    }
                }

                Text {
                    objectName: "error"
                    Layout.fillWidth: true
                    Layout.leftMargin: 16
                    Layout.rightMargin: 16
                    Layout.topMargin: 10
                    visible: monitor.error !== ""
                    text: monitor.errorLink ? `${monitor.error}. Open settings` : monitor.error
                    textFormat: Text.PlainText
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                    color: wifi.errorColor
                    font.family: "Segoe UI"
                    font.pixelSize: 12
                    font.underline: monitor.errorLink !== "" && errorArea.containsMouse
                    Accessible.role: monitor.errorLink ? Accessible.Link : Accessible.StaticText
                    Accessible.name: text
                    Accessible.onPressAction: errorArea.clicked(null)

                    MouseArea {
                        id: errorArea

                        anchors.fill: parent
                        enabled: monitor.errorLink !== ""
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            Qt.openUrlExternally(monitor.errorLink)
                            popup.close()
                        }
                    }
                }

                Text {
                    Layout.fillWidth: true
                    Layout.topMargin: 24
                    Layout.bottomMargin: 24
                    visible: list.count === 0 && monitor.error === ""
                    text: monitor.scanning ? "Looking for networks..." : "No networks found"
                    horizontalAlignment: Text.AlignHCenter
                    color: Qt.alpha(popup.ink, 0.5)
                    font.family: "Segoe UI"
                    font.pixelSize: 13
                }

                ListView {
                    id: list

                    objectName: "networks"
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(contentHeight, wifi.maxListHeight)
                    Layout.margins: 6
                    visible: count > 0
                    clip: true
                    model: monitor.networks
                    spacing: 2
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar {}

                    delegate: Item {
                        id: network

                        required property int index
                        required property string ssid
                        required property bool hidden
                        required property int quality
                        required property bool secured
                        required property bool connected
                        required property bool known
                        required property bool autoConnect

                        readonly property bool expanded: popup.expanded === ssid
                        readonly property bool joining: monitor.connecting && monitor.connectingTo === ssid
                        // Saved networks use their profile to connect.
                        readonly property bool needsPassword: secured && !known && !connected
                        readonly property string name: hidden ? "Hidden network" : ssid
                        readonly property bool ready: connected || ((!hidden || ssidField.text !== "")
                            && (!needsPassword || passwordField.text !== ""))
                        readonly property string statusText: {
                            if (joining)
                                return "Connecting..."
                            if (connected)
                                return secured ? "Connected, secured" : "Connected"
                            return secured ? "Secured" : "Open"
                        }

                        function submit() {
                            if (connected)
                                monitor.disconnectNetwork()
                            else if (!ready || monitor.connecting)
                                return
                            else if (hidden)
                                monitor.connectHidden(ssidField.text, passwordField.text, autoBox.checked)
                            else
                                monitor.connectTo(ssid, needsPassword ? passwordField.text : "", autoBox.checked)
                        }

                        width: ListView.view.width
                        height: rows.implicitHeight
                        Accessible.role: Accessible.ListItem
                        Accessible.name: `${name}, ${statusText}, ${quality}%`

                        onExpandedChanged: {
                            if (expanded && (ssidField.visible || passwordField.visible))
                                Qt.callLater(() => (ssidField.visible ? ssidField : passwordField).forceActiveFocus())
                        }
                        // Scroll expanded controls into view after layout.
                        onHeightChanged: {
                            if (expanded)
                                list.positionViewAtIndex(index, ListView.Contain)
                        }
                        onConnectedChanged: {
                            if (connected) {
                                ssidField.clear()
                                passwordField.clear()
                            }
                        }

                        Rectangle {
                            anchors.fill: parent
                            radius: 8
                            color: Qt.alpha(popup.ink, network.expanded ? 0.03 : headerArea.containsMouse ? 0.06 : 0)
                            border.width: network.expanded ? 1 : 0
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

                                    SignalIcon {
                                        size: 20
                                        icons: network.secured ? wifi.securedIcons : wifi.openIcons
                                        strength: network.quality
                                        color: popup.ink
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: network.name
                                        textFormat: Text.PlainText
                                        elide: Text.ElideRight
                                        color: network.hidden ? Qt.alpha(popup.ink, 0.65) : popup.ink
                                        font.family: "Segoe UI"
                                        font.pixelSize: 13
                                    }

                                    Column {
                                        Text {
                                            anchors.right: parent.right
                                            text: network.statusText
                                            color: Qt.alpha(popup.ink, 0.65)
                                            font.family: "Segoe UI"
                                            font.pixelSize: 12
                                        }

                                        Text {
                                            anchors.right: parent.right
                                            text: `${network.quality}%`
                                            color: Qt.alpha(popup.ink, 0.5)
                                            font.family: "Segoe UI"
                                            font.pixelSize: 12
                                        }
                                    }
                                }

                                MouseArea {
                                    id: headerArea

                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                                    onClicked: mouse => {
                                        if (mouse.button === Qt.RightButton)
                                            networkMenu.show(network, network.ssid, network.known, network.autoConnect,
                                                mouse.x, mouse.y)
                                        else
                                            popup.expanded = network.expanded ? undefined : network.ssid
                                    }
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.leftMargin: 44
                                Layout.rightMargin: 12
                                // Allow this layout to fill the available width.
                                Layout.maximumWidth: Number.POSITIVE_INFINITY
                                Layout.bottomMargin: 10
                                visible: network.expanded
                                spacing: 8

                                TextField {
                                    id: ssidField

                                    Layout.fillWidth: true
                                    visible: network.hidden && !network.connected
                                    placeholderText: "Network name"
                                    onAccepted: network.submit()
                                }

                                TextField {
                                    id: passwordField

                                    Layout.fillWidth: true
                                    visible: (network.needsPassword || network.hidden) && !network.connected
                                    placeholderText: "Password"
                                    echoMode: TextInput.Password
                                    onAccepted: network.submit()
                                }

                                CheckBox {
                                    id: autoBox

                                    visible: !network.connected
                                    text: "Connect automatically"
                                    checked: network.known ? network.autoConnect : true
                                }

                                Button {
                                    Layout.alignment: Qt.AlignRight
                                    Layout.preferredWidth: 140
                                    text: network.connected ? "Disconnect" : network.joining ? "Connecting..." : "Connect"
                                    highlighted: !network.connected
                                    enabled: network.connected || (network.ready && !monitor.connecting)
                                    onClicked: network.submit()
                                }
                            }
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
                    color: Qt.alpha("#000000", wifi.dark ? 0.15 : 0.03)

                    Rectangle {
                        width: parent.width
                        height: 1
                        color: Qt.alpha(popup.ink, 0.1)
                    }

                    Text {
                        anchors.left: parent.left
                        anchors.leftMargin: 15
                        anchors.verticalCenter: parent.verticalCenter
                        text: "More Wi-Fi settings"
                        color: settingsArea.containsMouse ? popup.ink : Qt.alpha(popup.ink, 0.65)
                        font.family: "Segoe UI"
                        font.pixelSize: 12
                        Accessible.role: Accessible.Link
                        Accessible.name: text
                        Accessible.onPressAction: settingsArea.clicked(null)

                        MouseArea {
                            id: settingsArea

                            anchors.fill: parent
                            anchors.margins: -8
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                Qt.openUrlExternally("ms-settings:network-wifi")
                                popup.close()
                            }
                        }
                    }

                    Item {
                        anchors.right: parent.right
                        anchors.rightMargin: 8
                        anchors.verticalCenter: parent.verticalCenter
                        width: 28
                        height: 28
                        opacity: monitor.scanning ? 0.4 : 1
                        Accessible.role: Accessible.Button
                        Accessible.name: "Look for networks again"
                        Accessible.onPressAction: monitor.scan()
                        ToolTip.visible: refreshArea.containsMouse
                        ToolTip.delay: 500
                        ToolTip.text: "Refresh"

                        Rectangle {
                            anchors.fill: parent
                            radius: 4
                            color: Qt.alpha(popup.ink, refreshArea.containsMouse && !monitor.scanning ? 0.1 : 0)
                        }

                        Glyph {
                            anchors.fill: parent
                            text: ""
                            color: popup.ink
                            font.pixelSize: 14
                        }

                        MouseArea {
                            id: refreshArea

                            anchors.fill: parent
                            hoverEnabled: true
                            enabled: !monitor.scanning
                            cursorShape: Qt.PointingHandCursor
                            onClicked: monitor.scan()
                        }
                    }
                }
            }

            // Right-click menu; only saved networks have editable settings.
            Menu {
                id: networkMenu

                property string ssid
                property bool known
                property bool autoConnect

                function show(target: Item, ssid: string, known: bool, autoConnect: bool, x: real, y: real) {
                    networkMenu.ssid = ssid
                    networkMenu.known = known
                    networkMenu.autoConnect = autoConnect
                    networkMenu.popup(target, x, y)
                }

                popupType: Popup.Item

                MenuItem {
                    text: "Connect automatically"
                    checkable: true
                    checked: networkMenu.autoConnect
                    enabled: networkMenu.known
                    onTriggered: monitor.setAutoConnect(networkMenu.ssid, checked)
                }

                MenuItem {
                    text: "Forget"
                    enabled: networkMenu.known
                    onTriggered: monitor.forget(networkMenu.ssid)
                }
            }
        }
    }
}
