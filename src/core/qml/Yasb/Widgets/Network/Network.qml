pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Yasb
import Yasb.Bar
import Yasb.Common
import Yasb.Themes

Item {
    id: network

    component PopupIcons: QtObject {
        property string refresh
        property string wifi
        property list<string> secured
        property list<string> unsecured
    }

    component Settings: QtObject {
        required property Theme theme

        // Label placeholders: {name}, {signal}, {ip}; {signal} and {ip} are empty without a value. An empty label shows
        // only the icon.
        property string label: ""
        property string alternateLabel: "{name}"
        // How often to read the signal bars of Wi-Fi without location access and of mobile, in ms (500 to 60000). With
        // location access, Windows reports each change of the exact Wi-Fi signal.
        property int signalInterval: 1000
        // Hide the widget while the internet goes through a cable
        property bool hideIfEthernet: false
        property int iconSize: theme.bar.iconFont.pixelSize
        // Wi-Fi and mobile signal glyphs, weakest first; the strongest forms a faint background.
        property list<string> wifiIcons: ["\ue872", "\ue873", "\ue874", "\ue701"]
        property list<string> mobileIcons: ["\ue86c", "\ue86d", "\ue86e", "\ue86f", "\ue870"]
        property string ethernetIcon: "\ue839"
        // Other connections, such as a VPN adapter
        property string otherIcon: "\ue968"
        property string disconnectedIcon: "\uf384"
        // Shown small over the icon while the connection has no internet
        property string noInternetIcon: "\ue7ba"
        // Windows' caution colors, so the badge stands out from the icon
        property color noInternetColor: theme.colors.warning
        property int popupWidth: 344
        // Popup alignment relative to the widget on a horizontal bar: left, right, or center.
        property string popupAlignment: "center"
        // Scroll the network list when it exceeds this height.
        property int maxListHeight: 320
        property color errorColor: theme.colors.critical
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
        // Text on the bar takes the theme's colour, and labels the bar's font; parts set in font replace the bar's
        property color textColor: theme.colors.text
        property font font
        // Glyphs take the theme's icon font, each part unless the widget file sets it
        property font iconFont
        iconFont.family: theme.bar.iconFont.family
        iconFont.weight: theme.bar.iconFont.weight
        iconFont.variableAxes: theme.bar.iconFont.variableAxes
        // The popup: the theme's, unless set here
        property color popupColor: theme.popup.background
        property color popupBorderColor: theme.popup.border
        property color popupTextColor: theme.colors.text
        property real popupRadius: theme.popup.radius
        property real popupGap: theme.popup.gap
        // Text in the popup: the theme's font family, in this widget's sizes
        property font popupFont
        popupFont.family: theme.popup.font.family
        popupFont.pixelSize: 13
        property font popupSmallFont
        popupSmallFont.family: theme.popup.font.family
        popupSmallFont.pixelSize: 12
        property font popupTitleFont
        popupTitleFont.family: theme.popup.font.family
        popupTitleFont.pixelSize: 16
        popupTitleFont.weight: 600
        // The Wi-Fi heading
        property font popupStrongFont
        popupStrongFont.family: theme.popup.font.family
        popupStrongFont.pixelSize: 13
        popupStrongFont.weight: 600
        readonly property PopupIcons popupIcons: PopupIcons {
            refresh: "\ue72c"
            wifi: "\ue701"
            // Wi-Fi networks in the list, with and without a password, weakest signal first
            secured: ["\ue670", "\ue671", "\ue672", "\ue673"]
            unsecured: ["\uec3c", "\uec3d", "\uec3e", "\uec3f"]
        }
        property font popupIconFont
        popupIconFont.family: theme.popup.iconFont.family
        popupIconFont.weight: theme.popup.iconFont.weight
        popupIconFont.variableAxes: theme.popup.iconFont.variableAxes
        // The Wi-Fi glyph beside it, and the refresh glyph
        property int wifiIconSize: 20
        property int popupIconSize: 14
        property int popupOpenDuration: theme.popup.openDuration
        property int popupCloseDuration: theme.popup.closeDuration
        // The right-click menu on a network: the theme's, unless set here
        property int menuWidth: 200
        property color menuColor: theme.menu.background
        property color menuBorderColor: theme.menu.border
        property color menuTextColor: theme.colors.text
        property real menuRadius: theme.menu.radius
        property font menuFont: theme.menu.font
        // Milliseconds the right-click menu takes to fade in
        property int menuOpenDuration: theme.menu.openDuration
        // The icons in the text fields' right-click menu
        property int menuIconSize: 16
        property color popupSecondaryBackgroundColor: theme.colors.backgroundSecondary
        property color popupDividerColor: theme.colors.divider
        property color popupSecondaryTextColor: theme.colors.textSecondary
        property color popupTertiaryTextColor: theme.colors.textTertiary
        property color popupHoverColor: theme.colors.hover
        property color popupCardColor: theme.colors.card
        property color popupCardBorderColor: theme.colors.cardBorder
    }

    required property BarBase bar
    readonly property Theme theme: bar.theme
    readonly property Settings settings: Settings {
        theme: network.theme
    }

    property bool showAlternate: false

    readonly property bool dark: theme.dark
    readonly property string edge: bar.edge

    // The connection Windows uses for internet; kind is wifi, ethernet, mobile, other or none.
    readonly property var primary: connections.primary
    readonly property bool ethernet: primary.kind === "ethernet"
    readonly property bool online: primary.connectivity === "internet"
    readonly property bool shown: !(settings.hideIfEthernet && ethernet)
    readonly property string connectionName: {
        if (primary.kind === "wifi")
            return primary.ssid || primary.name
        const name = primary.name || primary.adapter
        // Windows shows the mobile network type after the operator, as in Orange (LTE).
        return primary.mobileType ? `${name} (${primary.mobileType})` : name
    }
    // Empty for Wi-Fi and mobile, which show their signal bars
    readonly property string connectionIcon: ethernet ? settings.ethernetIcon : primary.kind === "none" ? settings.disconnectedIcon
        : primary.kind === "wifi" || primary.kind === "mobile" ? "" : settings.otherIcon
    readonly property list<string> signalIcons: primary.kind === "mobile" ? settings.mobileIcons : settings.wifiIcons
    readonly property string connectionStatus: {
        const status = primary.connectivity === "internet" ? "Connected"
            : primary.connectivity === "constrained" ? "Sign-in required" : "No internet"
        return primary.metered ? `${status}, metered` : status
    }
    readonly property string text: format(showAlternate ? settings.alternateLabel : settings.label)

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
        const gap = settings.popupGap
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
            px = settings.popupAlignment === "left" ? start.x
                : settings.popupAlignment === "right" ? start.x + width - popup.width : start.x + (width - popup.width) / 2
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

        signalInterval: network.settings.signalInterval
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

    // An item of the text fields' right-click menu, its icon in menuIconSize
    component FieldMenuItem: MenuItem {
        icon.width: network.settings.menuIconSize
        icon.height: network.settings.menuIconSize
    }

    component Glyph: Text {
        textFormat: Text.PlainText
        font.family: network.settings.iconFont.family
        font.weight: network.settings.iconFont.weight
        font.variableAxes: network.settings.iconFont.variableAxes
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
        property font iconFont: network.settings.iconFont
        property color color
        property color badgeColor: color

        implicitWidth: size
        implicitHeight: size

        Glyph {
            anchors.fill: parent
            text: signal.glyph || (signal.icons[signal.icons.length - 1] ?? "")
            color: signal.color
            opacity: signal.glyph ? 1 : 0.3
            font.family: signal.iconFont.family
            font.weight: signal.iconFont.weight
            font.variableAxes: signal.iconFont.variableAxes
            font.pixelSize: signal.size
        }

        Glyph {
            anchors.fill: parent
            visible: !signal.glyph
            text: signal.icons[network.level(signal.strength, signal.icons.length)] ?? ""
            color: signal.color
            font.family: signal.iconFont.family
            font.weight: signal.iconFont.weight
            font.variableAxes: signal.iconFont.variableAxes
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
            font.family: signal.iconFont.family
            font.weight: signal.iconFont.weight
            font.variableAxes: signal.iconFont.variableAxes
            font.pixelSize: Math.round(signal.size / 2)
        }
    }

    // A settings page link in the popup footer.
    component SettingsLink: Text {
        id: settingsLink

        required property string page

        color: linkArea.containsMouse ? network.settings.popupTextColor : network.settings.popupSecondaryTextColor
        font: network.settings.popupSmallFont
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
            size: network.settings.iconSize
            icons: network.signalIcons
            strength: network.primary.signal
            glyph: network.connectionIcon
            badge: network.primary.kind !== "none" && !network.online ? network.settings.noInternetIcon : ""
            color: network.settings.textColor
            badgeColor: network.settings.noInternetColor
        }

        Label {
            objectName: "label"
            anchors.verticalCenter: parent.verticalCenter
            visible: text !== ""
            text: network.text
            textFormat: Text.PlainText
            color: network.settings.textColor
            font: network.settings.font
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

        objectName: "popup"
        title: "Network"
        width: network.settings.popupWidth
        height: popupContent.implicitHeight
        anchor: network
        font: network.settings.popupFont
        theme: network.theme
        backdropItem: surface
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: network.settings.popupOpenDuration; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: network.settings.popupCloseDuration; easing.type: Easing.InCubic }
        onVisibleChanged: {
            if (!visible)
                reveal = 0
        }

        Rectangle {
            id: surface

            anchors.fill: parent
            radius: network.settings.popupRadius
            color: network.settings.popupColor
            border.width: 1
            border.color: network.settings.popupBorderColor
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
                    Layout.bottomMargin: 10
                    text: "Network"
                    color: network.settings.popupTextColor
                    font: network.settings.popupTitleFont
                }

                LoadingLine {
                    Layout.fillWidth: true
                    running: wifi.scanning || wifi.connecting
                    trackColor: network.settings.popupDividerColor
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
                        color: network.settings.popupTextColor
                    }

                    Text {
                        Layout.fillWidth: true
                        text: network.connectionName
                        textFormat: Text.PlainText
                        elide: Text.ElideRight
                        color: network.settings.popupTextColor
                        font: network.settings.popupFont
                    }

                    Column {
                        Text {
                            anchors.right: parent.right
                            text: network.connectionStatus
                            color: network.settings.popupSecondaryTextColor
                            font: network.settings.popupSmallFont
                        }

                        Text {
                            anchors.right: parent.right
                            visible: text !== ""
                            text: network.primary.ipAddress
                            color: network.settings.popupTertiaryTextColor
                            font: network.settings.popupSmallFont
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
                    color: network.settings.popupDividerColor
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
                        text: network.settings.popupIcons.wifi
                        color: network.settings.popupTextColor
                        opacity: wifi.enabled ? 1 : 0.5
                        font.family: network.settings.popupIconFont.family
                        font.weight: network.settings.popupIconFont.weight
                        font.variableAxes: network.settings.popupIconFont.variableAxes
                        font.pixelSize: network.settings.wifiIconSize
                    }

                    Column {
                        Layout.fillWidth: true

                        Text {
                            text: "Wi-Fi"
                            color: network.settings.popupTextColor
                            font: network.settings.popupStrongFont
                        }

                        Text {
                            visible: !wifi.enabled
                            text: "Off"
                            color: network.settings.popupSecondaryTextColor
                            font: network.settings.popupSmallFont
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
                            color: refreshArea.containsMouse && !wifi.scanning ? network.settings.popupHoverColor : "transparent"
                        }

                        Glyph {
                            anchors.fill: parent
                            text: network.settings.popupIcons.refresh
                            color: network.settings.popupTextColor
                            font.family: network.settings.popupIconFont.family
                            font.weight: network.settings.popupIconFont.weight
                            font.variableAxes: network.settings.popupIconFont.variableAxes
                            font.pixelSize: network.settings.popupIconSize
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
                    color: network.settings.popupTertiaryTextColor
                    font: network.settings.popupFont
                }

                ListView {
                    id: list

                    objectName: "networks"
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(contentHeight, network.settings.maxListHeight)
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
                            color: wifiNetwork.expanded ? network.settings.popupCardColor : headerArea.containsMouse ? network.settings.popupHoverColor : "transparent"
                            border.width: wifiNetwork.expanded ? 1 : 0
                            border.color: network.settings.popupCardBorderColor
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
                                        icons: wifiNetwork.secured ? network.settings.popupIcons.secured : network.settings.popupIcons.unsecured
                                        iconFont: network.settings.popupIconFont
                                        strength: wifiNetwork.quality
                                        color: network.settings.popupTextColor
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: wifiNetwork.name
                                        textFormat: Text.PlainText
                                        elide: Text.ElideRight
                                        color: wifiNetwork.hidden ? network.settings.popupSecondaryTextColor : network.settings.popupTextColor
                                        font: network.settings.popupFont
                                    }

                                    Column {
                                        Text {
                                            anchors.right: parent.right
                                            text: wifiNetwork.statusText
                                            color: network.settings.popupSecondaryTextColor
                                            font: network.settings.popupSmallFont
                                        }

                                        Text {
                                            anchors.right: parent.right
                                            text: wifiNetwork.ipAddress ? `${wifiNetwork.quality}%, ${wifiNetwork.ipAddress}`
                                                : `${wifiNetwork.quality}%`
                                            color: network.settings.popupTertiaryTextColor
                                            font: network.settings.popupSmallFont
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

                                    // Qt's own text menu is replaced by fieldMenu, which the right button opens
                                    ContextMenu.menu: null

                                    // A right-click opens the menu at the mouse cursor, on press or release as Windows sets it
                                    TapHandler {
                                        acceptedButtons: Qt.RightButton
                                        onPressedChanged: {
                                            if (pressed === (Application.styleHints.contextMenuTrigger === Qt.ContextMenuTrigger.Press))
                                                fieldMenu.popup(ssidField)
                                        }
                                    }

                                    Layout.fillWidth: true
                                    visible: wifiNetwork.hidden && !wifiNetwork.connected
                                    placeholderText: "Network name"
                                    onAccepted: wifiNetwork.submit()
                                }

                                TextField {
                                    id: passwordField

                                    // Qt's own text menu is replaced by fieldMenu, which the right button opens
                                    ContextMenu.menu: null

                                    // A right-click opens the menu at the mouse cursor, on press or release as Windows sets it
                                    TapHandler {
                                        acceptedButtons: Qt.RightButton
                                        onPressedChanged: {
                                            if (pressed === (Application.styleHints.contextMenuTrigger === Qt.ContextMenuTrigger.Press))
                                                fieldMenu.popup(passwordField)
                                        }
                                    }

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
                    bottomLeftRadius: network.settings.popupRadius - 1
                    bottomRightRadius: network.settings.popupRadius - 1
                    color: network.settings.popupSecondaryBackgroundColor

                    Rectangle {
                        width: parent.width
                        height: 1
                        color: network.settings.popupDividerColor
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
                            const message = network.settings.errorTexts[wifi.error] ?? wifi.error
                            return footer.link ? `${message}. Open settings` : message
                        }
                        textFormat: Text.PlainText
                        wrapMode: Text.WordWrap
                        maximumLineCount: 2
                        elide: Text.ElideRight
                        horizontalAlignment: Text.AlignHCenter
                        color: network.settings.errorColor
                        font.family: network.settings.popupSmallFont.family
                        font.pixelSize: network.settings.popupSmallFont.pixelSize
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
            // The text fields' right-click menu: Qt's editing items and icons in the menu's look, acting on the field that
            // opened it
            Menu {
                id: fieldMenu

                readonly property TextField editor: parent as TextField
                readonly property bool editable: !(editor?.readOnly ?? true)
                readonly property bool selected: (editor?.selectedText.length ?? 0) > 0

                // A window of its own, so it opens where clicked even past the popup's edges
                popupType: Popup.Window
                // Its window is made once and reused, and Windows shows it again where it was, under the popup raised
                // since; raising it before it shows keeps it in front
                onAboutToShow: contentItem.Window.window?.raise()
                // Fades in when it opens, in place of the style's growing from a third of its height
                enter: Transition {
                    NumberAnimation { property: "opacity"; from: 0; to: 1; duration: network.settings.menuOpenDuration; easing.type: Easing.OutCubic }
                }
                topInset: 0
                leftInset: 0
                rightInset: 0
                bottomInset: 0
                font: network.settings.menuFont
                // Active and inactive only, so disabled controls keep the style's dimmed colours
                palette.active.text: network.settings.menuTextColor
                palette.inactive.text: network.settings.menuTextColor

                background: Rectangle {
                    implicitWidth: network.settings.menuWidth
                    radius: network.settings.menuRadius
                    color: network.settings.menuColor
                    border.color: network.settings.menuBorderColor
                }

                FieldMenuItem {
                    text: qsTr("Undo")
                    icon.name: "edit-undo"
                    enabled: fieldMenu.editor?.canUndo ?? false
                    onTriggered: fieldMenu.editor.undo()
                }
                FieldMenuItem {
                    text: qsTr("Redo")
                    icon.name: "edit-redo"
                    enabled: fieldMenu.editor?.canRedo ?? false
                    onTriggered: fieldMenu.editor.redo()
                }
                MenuSeparator {}
                FieldMenuItem {
                    text: qsTr("Cut")
                    icon.name: "edit-cut"
                    enabled: fieldMenu.editable && fieldMenu.selected
                    onTriggered: fieldMenu.editor.cut()
                }
                FieldMenuItem {
                    text: qsTr("Copy")
                    icon.name: "edit-copy"
                    enabled: fieldMenu.selected
                    onTriggered: fieldMenu.editor.copy()
                }
                FieldMenuItem {
                    text: qsTr("Paste")
                    icon.name: "edit-paste"
                    enabled: fieldMenu.editable && (fieldMenu.editor?.canPaste ?? false)
                    onTriggered: fieldMenu.editor.paste()
                }
                FieldMenuItem {
                    text: qsTr("Delete")
                    icon.name: "edit-delete"
                    enabled: fieldMenu.editable && fieldMenu.selected
                    onTriggered: fieldMenu.editor.remove(fieldMenu.editor.selectionStart, fieldMenu.editor.selectionEnd)
                }
                MenuSeparator {}
                FieldMenuItem {
                    text: qsTr("Select All")
                    icon.name: "edit-select-all"
                    onTriggered: fieldMenu.editor.selectAll()
                }
            }

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
                // Fades in when it opens, in place of the style's growing from a third of its height
                enter: Transition {
                    NumberAnimation { property: "opacity"; from: 0; to: 1; duration: network.settings.menuOpenDuration; easing.type: Easing.OutCubic }
                }
                topInset: 0
                leftInset: 0
                rightInset: 0
                bottomInset: 0
                font: network.settings.menuFont
                // Active and inactive only, so disabled controls keep the style's dimmed colours
                palette.active.text: network.settings.menuTextColor
                palette.inactive.text: network.settings.menuTextColor

                background: Rectangle {
                    implicitWidth: network.settings.menuWidth
                    radius: network.settings.menuRadius
                    color: network.settings.menuColor
                    border.color: network.settings.menuBorderColor
                }

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
