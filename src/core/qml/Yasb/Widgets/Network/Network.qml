pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Yasb
import Yasb.Bar
import Yasb.Common

Item {
    id: network

    // Label placeholders: {name}, {signal}, {ip}; {signal} and {ip} are empty without a value. An empty label shows
    // only the icon.
    property string label: ""
    property string alternateLabel: "{name}"
    // How often to read the signal bars of Wi-Fi without location access and of mobile, in ms (500 to 60000). With
    // location access, Windows reports each change of the exact Wi-Fi signal.
    property int signalInterval: 1000
    // Hide the widget while the internet goes through a cable
    property bool hideIfEthernet: false
    property int iconSize: 16
    // Wi-Fi and mobile signal glyphs, weakest first; the strongest forms a faint background.
    property list<string> wifiIcons: ["\ue872", "\ue873", "\ue874", "\ue701"]
    property list<string> mobileIcons: ["\ue86c", "\ue86d", "\ue86e", "\ue86f", "\ue870"]
    // Networks in the popup, with and without a password
    property list<string> securedIcons: ["\ue670", "\ue671", "\ue672", "\ue673"]
    property list<string> openIcons: ["\uec3c", "\uec3d", "\uec3e", "\uec3f"]
    property string ethernetIcon: "\ue839"
    // Other connections, such as a VPN adapter
    property string otherIcon: "\ue968"
    property string disconnectedIcon: "\uf384"
    // Shown small over the icon while the connection has no internet
    property string noInternetIcon: "\ue7ba"
    // Windows' caution colors, so the badge stands out from the icon
    property color noInternetColor: dark ? "#fce100" : "#9d5d00"
    property int popupWidth: 360
    // Popup alignment relative to the widget on a horizontal bar: left, right, or center.
    property string popupAlignment: "center"
    // Scroll the network list when it exceeds this height.
    property int maxListHeight: 320
    property color errorColor: dark ? "#ff99a4" : "#c42b1c"
    // Text for each Wi-Fi error code
    property var errorTexts: ({
            accessDenied: "Location services are turned off",
            scanFailed: "Could not search for networks",
            radioDenied: "Could not turn Wi-Fi on or off",
            connectFailed: "Could not connect",
            invalidCredential: "Wrong password",
            networkNotAvailable: "Network not available",
            timeout: "The connection timed out",
            accessRevoked: "Access to Wi-Fi was revoked",
            unsupportedAuthenticationProtocol: "This network's security is not supported"
        })

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
    // Glyphs take the family and weight of the bar's icon font unless the widget file sets them
    property font iconFont
    iconFont.family: bar?.iconFont?.family ?? "Segoe Fluent Icons"
    iconFont.weight: bar?.iconFont?.weight ?? Font.Normal
    readonly property string edge: bar?.edge ?? "top"

    // The connection Windows uses for internet; kind is wifi, ethernet, mobile, other or none.
    readonly property var primary: connections.primary
    readonly property bool ethernet: primary.kind === "ethernet"
    readonly property bool online: primary.connectivity === "internet"
    readonly property bool shown: !(hideIfEthernet && ethernet)
    readonly property string connectionName: {
        if (primary.kind === "wifi")
            return primary.ssid || primary.name
        const name = primary.name || primary.adapter
        // Windows shows the mobile network type after the operator, as in Orange (LTE).
        return primary.mobileType ? `${name} (${primary.mobileType})` : name
    }
    // Empty for Wi-Fi and mobile, which show their signal bars
    readonly property string connectionIcon: ethernet ? ethernetIcon : primary.kind === "none" ? disconnectedIcon
        : primary.kind === "wifi" || primary.kind === "mobile" ? "" : otherIcon
    readonly property list<string> signalIcons: primary.kind === "mobile" ? mobileIcons : wifiIcons
    readonly property string connectionStatus: {
        const status = primary.connectivity === "internet" ? "Connected"
            : primary.connectivity === "constrained" ? "Sign-in required" : "No internet"
        return primary.metered ? `${status}, metered` : status
    }
    readonly property string text: format(showAlternate ? alternateLabel : label)

    // Map strength from 0 to 100 to an index into a list of count glyphs, or -1 for none: with 4 glyphs, 25 is the
    // first, matching one of Windows' 4 Wi-Fi bars, and with 5 glyphs 20, one of its 5 mobile bars.
    function level(strength: int, count: int): int {
        return Math.max(-1, Math.min(count - 1, Math.ceil(strength * count / 100) - 1))
    }

    function format(template: string): string {
        const values = {
            name: primary.kind === "none" ? "Disconnected" : connectionName,
            signal: primary.signal >= 0 ? String(primary.signal) : "",
            ip: primary.ipAddress
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
        const screen = network.Screen
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
        // Expand the connected Wi-Fi network when opening the popup.
        popup.expanded = primary.kind === "wifi" ? primary.ssid : undefined
        placePopup()
        popup.open()
    }

    implicitWidth: shown ? row.implicitWidth : 0
    implicitHeight: shown ? row.implicitHeight : 0
    visible: shown
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: {
        if (primary.kind === "none")
            return "Not connected"
        const signal = primary.signal >= 0 ? `, ${primary.signal}%` : ""
        return `${connectionName}, ${connectionStatus}${signal}`
    }
    Accessible.onPressAction: togglePopup()
    Keys.onReturnPressed: togglePopup()
    Keys.onSpacePressed: togglePopup()

    Component.onDestruction: popup.hide()

    NetworkConnections {
        id: connections

        signalInterval: network.signalInterval
    }

    WifiNetworks {
        id: wifi

        watching: popup.visible
    }

    Connections {
        target: network.Window.window

        function onVisibleChanged() {
            if (!network.Window.window?.visible)
                popup.hide()
        }

        function onXChanged() {
            if (popup.visible)
                network.placePopup()
        }

        function onYChanged() {
            if (popup.visible)
                network.placePopup()
        }
    }

    // Keep the popup anchored when its height changes.
    Connections {
        target: popup

        function onHeightChanged() {
            if (popup.visible)
                network.placePopup()
        }
    }

    component Glyph: Text {
        textFormat: Text.PlainText
        font.family: network.iconFont.family
        font.weight: network.iconFont.weight
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }

    // Show signal strength as stacked glyphs, or show one status glyph, with an optional badge.
    component SignalIcon: Item {
        id: signal

        property list<string> icons
        property int strength: 0
        property string glyph: ""
        property string badge: ""
        property int size: 16
        property color color
        property color badgeColor: color

        implicitWidth: size
        implicitHeight: size

        Glyph {
            anchors.fill: parent
            text: signal.glyph || (signal.icons[signal.icons.length - 1] ?? "")
            color: signal.color
            opacity: signal.glyph ? 1 : 0.3
            font.pixelSize: signal.size
        }

        Glyph {
            anchors.fill: parent
            visible: !signal.glyph
            text: signal.icons[network.level(signal.strength, signal.icons.length)] ?? ""
            color: signal.color
            font.pixelSize: signal.size
        }

        Glyph {
            objectName: "badge"
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.rightMargin: -signal.size / 6
            anchors.bottomMargin: -signal.size / 6
            visible: signal.badge !== ""
            text: signal.badge
            color: signal.badgeColor
            font.pixelSize: Math.round(signal.size / 2)
        }
    }

    // A settings page link in the popup footer.
    component SettingsLink: Text {
        id: settingsLink

        required property string page

        color: linkArea.containsMouse ? popup.ink : Qt.alpha(popup.ink, 0.65)
        font.pixelSize: 12
        Accessible.role: Accessible.Link
        Accessible.name: text
        Accessible.onPressAction: linkArea.clicked(null)

        MouseArea {
            id: linkArea

            anchors.fill: parent
            anchors.margins: -8
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                Qt.openUrlExternally(settingsLink.page)
                popup.close()
            }
        }
    }

    Row {
        id: row

        height: parent.height
        spacing: 6

        SignalIcon {
            objectName: "icon"
            y: Math.round((parent.height - height) / 2)
            size: network.iconSize
            icons: network.signalIcons
            strength: network.primary.signal
            glyph: network.connectionIcon
            badge: network.primary.kind !== "none" && !network.online ? network.noInternetIcon : ""
            color: network.textColor
            badgeColor: network.noInternetColor
        }

        Text {
            objectName: "label"
            anchors.verticalCenter: parent.verticalCenter
            visible: text !== ""
            text: network.text
            textFormat: Text.PlainText
            color: network.textColor
            font: network.font
        }
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: mouse => {
            if (mouse.button === Qt.LeftButton)
                network.togglePopup()
            else
                network.showAlternate = !network.showAlternate
        }
    }

    BackdropPopup {
        id: popup

        property real reveal: 0
        // SSID whose controls are open; empty for a hidden network.
        property var expanded: undefined
        readonly property color ink: network.dark ? "#ffffff" : "#000000"

        objectName: "popup"
        title: "Network"
        width: network.popupWidth
        height: popupContent.implicitHeight + 16
        anchor: network
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
            color: network.dark ? Qt.alpha("#202020", 0.85) : Qt.alpha("#F3F3F3", 0.85)
            border.width: 1
            border.color: network.dark ? "#3A3A3A" : "#D9D9D9"
            opacity: popup.reveal
            scale: 0.85 + popup.reveal * 0.15
            transformOrigin: network.edge === "bottom" ? Item.Bottom : Item.Top

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
                    text: "Network"
                    color: popup.ink
                    font.pixelSize: 16
                    font.weight: Font.DemiBold
                }

                LoadingLine {
                    Layout.fillWidth: true
                    running: wifi.scanning || wifi.connecting
                    trackColor: Qt.alpha(popup.ink, 0.1)
                }

                // The internet connection when it is not Wi-Fi, such as Ethernet, mobile or a VPN, above the Wi-Fi
                // networks.
                RowLayout {
                    id: connectionRow

                    objectName: "connection"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 48
                    Layout.leftMargin: 18
                    Layout.rightMargin: 18
                    visible: network.primary.kind !== "wifi" && network.primary.kind !== "none"
                    spacing: 12
                    Accessible.role: Accessible.StaticText
                    Accessible.name: `${network.connectionName}, ${network.connectionStatus}`

                    SignalIcon {
                        size: 20
                        icons: network.signalIcons
                        strength: network.primary.signal
                        glyph: network.connectionIcon
                        color: popup.ink
                    }

                    Text {
                        Layout.fillWidth: true
                        text: network.connectionName
                        textFormat: Text.PlainText
                        elide: Text.ElideRight
                        color: popup.ink
                        font.pixelSize: 13
                    }

                    Column {
                        Text {
                            anchors.right: parent.right
                            text: network.connectionStatus
                            color: Qt.alpha(popup.ink, 0.65)
                            font.pixelSize: 12
                        }

                        Text {
                            anchors.right: parent.right
                            visible: text !== ""
                            text: network.primary.ipAddress
                            color: Qt.alpha(popup.ink, 0.5)
                            font.pixelSize: 12
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.topMargin: 8
                    Layout.bottomMargin: 8
                    Layout.leftMargin: 16
                    Layout.rightMargin: 16
                    implicitHeight: 1
                    visible: connectionRow.visible && wifi.available
                    color: Qt.alpha(popup.ink, 0.1)
                }

                // Wi-Fi heading with the switch, shown when the PC has a Wi-Fi adapter.
                RowLayout {
                    objectName: "wifiHeader"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 44
                    Layout.leftMargin: 18
                    Layout.rightMargin: 12
                    visible: wifi.available
                    spacing: 12

                    Glyph {
                        Layout.preferredWidth: 20
                        Layout.preferredHeight: 20
                        text: network.wifiIcons[network.wifiIcons.length - 1] ?? ""
                        color: popup.ink
                        opacity: wifi.enabled ? 1 : 0.5
                        font.pixelSize: 20
                    }

                    Column {
                        Layout.fillWidth: true

                        Text {
                            text: "Wi-Fi"
                            color: popup.ink
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                        }

                        Text {
                            visible: !wifi.enabled
                            text: "Off"
                            color: Qt.alpha(popup.ink, 0.65)
                            font.pixelSize: 12
                        }
                    }

                    Item {
                        Layout.preferredWidth: 28
                        Layout.preferredHeight: 28
                        visible: wifi.enabled
                        opacity: wifi.scanning ? 0.4 : 1
                        Accessible.role: Accessible.Button
                        Accessible.name: "Look for networks again"
                        Accessible.onPressAction: wifi.scan()
                        ToolTip.visible: refreshArea.containsMouse
                        ToolTip.delay: 500
                        ToolTip.text: "Refresh"

                        Rectangle {
                            anchors.fill: parent
                            radius: 4
                            color: Qt.alpha(popup.ink, refreshArea.containsMouse && !wifi.scanning ? 0.1 : 0)
                        }

                        Glyph {
                            anchors.fill: parent
                            text: "\ue72c"
                            color: popup.ink
                            font.pixelSize: 14
                        }

                        MouseArea {
                            id: refreshArea

                            anchors.fill: parent
                            hoverEnabled: true
                            enabled: !wifi.scanning
                            cursorShape: Qt.PointingHandCursor
                            onClicked: wifi.scan()
                        }
                    }

                    // Follows the radio; Windows confirms each change.
                    Switch {
                        objectName: "wifiSwitch"
                        checkable: false
                        checked: wifi.enabled
                        Accessible.name: "Wi-Fi"
                        onClicked: wifi.setEnabled(!wifi.enabled)
                    }
                }

                Text {
                    Layout.fillWidth: true
                    Layout.topMargin: 24
                    Layout.bottomMargin: 24
                    visible: wifi.available && wifi.enabled && list.count === 0 && wifi.error === ""
                    text: wifi.scanning ? "Looking for networks..." : "No networks found"
                    horizontalAlignment: Text.AlignHCenter
                    color: Qt.alpha(popup.ink, 0.5)
                    font.pixelSize: 13
                }

                ListView {
                    id: list

                    objectName: "networks"
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(contentHeight, network.maxListHeight)
                    Layout.margins: 6
                    visible: wifi.available && wifi.enabled && count > 0
                    clip: true
                    model: wifi.networks
                    spacing: 2
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar {}

                    delegate: Item {
                        id: wifiNetwork

                        required property int index
                        required property string ssid
                        required property bool hidden
                        required property int quality
                        required property bool secured
                        required property bool connected
                        required property bool known
                        required property bool autoConnect

                        readonly property bool expanded: popup.expanded === ssid
                        readonly property bool joining: wifi.connecting && wifi.connectingTo === ssid
                        // Saved networks use their profile to connect.
                        readonly property bool needsPassword: secured && !known && !connected
                        readonly property string name: hidden ? "Hidden network" : ssid
                        readonly property string ipAddress: connected && network.primary.kind === "wifi"
                            && network.primary.ssid === ssid ? network.primary.ipAddress : ""
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
                                wifi.disconnectNetwork()
                            else if (!ready || wifi.connecting)
                                return
                            else if (hidden)
                                wifi.connectHidden(ssidField.text, passwordField.text, autoBox.checked)
                            else
                                wifi.connectTo(ssid, needsPassword ? passwordField.text : "", autoBox.checked)
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
                            color: Qt.alpha(popup.ink, wifiNetwork.expanded ? 0.03 : headerArea.containsMouse ? 0.06 : 0)
                            border.width: wifiNetwork.expanded ? 1 : 0
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
                                        icons: wifiNetwork.secured ? network.securedIcons : network.openIcons
                                        strength: wifiNetwork.quality
                                        color: popup.ink
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: wifiNetwork.name
                                        textFormat: Text.PlainText
                                        elide: Text.ElideRight
                                        color: wifiNetwork.hidden ? Qt.alpha(popup.ink, 0.65) : popup.ink
                                        font.pixelSize: 13
                                    }

                                    Column {
                                        Text {
                                            anchors.right: parent.right
                                            text: wifiNetwork.statusText
                                            color: Qt.alpha(popup.ink, 0.65)
                                            font.pixelSize: 12
                                        }

                                        Text {
                                            anchors.right: parent.right
                                            text: wifiNetwork.ipAddress ? `${wifiNetwork.quality}%, ${wifiNetwork.ipAddress}`
                                                : `${wifiNetwork.quality}%`
                                            color: Qt.alpha(popup.ink, 0.5)
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
                                            networkMenu.show(wifiNetwork, wifiNetwork.ssid, wifiNetwork.known,
                                                wifiNetwork.autoConnect, mouse.x, mouse.y)
                                        else
                                            popup.expanded = wifiNetwork.expanded ? undefined : wifiNetwork.ssid
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
                                visible: wifiNetwork.expanded
                                spacing: 8

                                TextField {
                                    id: ssidField

                                    Layout.fillWidth: true
                                    visible: wifiNetwork.hidden && !wifiNetwork.connected
                                    placeholderText: "Network name"
                                    onAccepted: wifiNetwork.submit()
                                }

                                TextField {
                                    id: passwordField

                                    Layout.fillWidth: true
                                    visible: (wifiNetwork.needsPassword || wifiNetwork.hidden) && !wifiNetwork.connected
                                    placeholderText: "Password"
                                    echoMode: TextInput.Password
                                    onAccepted: wifiNetwork.submit()
                                }

                                CheckBox {
                                    id: autoBox

                                    visible: !wifiNetwork.connected
                                    text: "Connect automatically"
                                    checked: wifiNetwork.known ? wifiNetwork.autoConnect : true
                                }

                                Button {
                                    Layout.alignment: Qt.AlignRight
                                    Layout.preferredWidth: 140
                                    text: wifiNetwork.connected ? "Disconnect" : wifiNetwork.joining ? "Connecting..." : "Connect"
                                    highlighted: !wifiNetwork.connected
                                    enabled: wifiNetwork.connected || (wifiNetwork.ready && !wifi.connecting)
                                    onClicked: wifiNetwork.submit()
                                }
                            }
                        }
                    }
                }

                // A Wi-Fi error takes the place of the settings links, so nothing moves or is covered.
                Rectangle {
                    id: footer

                    readonly property bool showsError: wifi.available && wifi.error !== ""
                    readonly property string link: wifi.error === "accessDenied" ? "ms-settings:privacy-location" : ""

                    Layout.fillWidth: true
                    Layout.topMargin: 6
                    Layout.leftMargin: 1
                    Layout.rightMargin: 1
                    Layout.bottomMargin: 1
                    implicitHeight: 44
                    bottomLeftRadius: 7
                    bottomRightRadius: 7
                    color: Qt.alpha("#000000", network.dark ? 0.15 : 0.03)

                    Rectangle {
                        width: parent.width
                        height: 1
                        color: Qt.alpha(popup.ink, 0.1)
                    }

                    SettingsLink {
                        anchors.left: parent.left
                        anchors.leftMargin: 15
                        anchors.verticalCenter: parent.verticalCenter
                        visible: !footer.showsError
                        text: "Network settings"
                        page: "ms-settings:network-status"
                    }

                    // Windows opens the Wi-Fi page only on PCs with a Wi-Fi adapter.
                    SettingsLink {
                        anchors.right: parent.right
                        anchors.rightMargin: 15
                        anchors.verticalCenter: parent.verticalCenter
                        visible: !footer.showsError
                        text: wifi.available ? "Wi-Fi settings" : "Advanced network settings"
                        page: wifi.available ? "ms-settings:network-wifi" : "ms-settings:network-advancedsettings"
                    }

                    Text {
                        objectName: "error"
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.leftMargin: 15
                        anchors.rightMargin: 15
                        visible: footer.showsError
                        text: {
                            const message = network.errorTexts[wifi.error] ?? wifi.error
                            return footer.link ? `${message}. Open settings` : message
                        }
                        textFormat: Text.PlainText
                        wrapMode: Text.WordWrap
                        maximumLineCount: 2
                        elide: Text.ElideRight
                        horizontalAlignment: Text.AlignHCenter
                        color: network.errorColor
                        font.pixelSize: 12
                        font.underline: footer.link !== "" && errorArea.containsMouse
                        Accessible.role: footer.link ? Accessible.Link : Accessible.StaticText
                        Accessible.name: text
                        Accessible.onPressAction: errorArea.clicked(null)

                        MouseArea {
                            id: errorArea

                            anchors.fill: parent
                            enabled: footer.link !== ""
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                Qt.openUrlExternally(footer.link)
                                popup.close()
                            }
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
                    onTriggered: wifi.setAutoConnect(networkMenu.ssid, checked)
                }

                MenuItem {
                    text: "Forget"
                    enabled: networkMenu.known
                    onTriggered: wifi.forget(networkMenu.ssid)
                }
            }
        }
    }
}
