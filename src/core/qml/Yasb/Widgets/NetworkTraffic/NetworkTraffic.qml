pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Yasb
import Yasb.Bar
import Yasb.Common
import Yasb.Themes

Item {
    id: networkTraffic

    // Label placeholders: {download_speed} {upload_speed}, 0 below minimumDownloadRate and minimumUploadRate;
    // {session_downloaded} {session_uploaded} {session_time} while YASB runs; {today_downloaded} {today_uploaded},
    // {week_downloaded} {week_uploaded} and {month_downloaded} {month_uploaded} for the last 7 and 30 days, from
    // Windows' usage estimates; {network} {adapter} {ip}. Such as "↓ {download_speed}  ↑ {upload_speed}".
    // Right-click shows the alternate label.
    property string label: ""
    property string alternateLabel: "↓ {session_downloaded}  ↑ {session_uploaded}"
    required property BarBase bar
    readonly property Theme theme: bar.theme
    // "auto" follows the adapter Windows uses for internet; an adapter name, such as "Ethernet" or "Wi-Fi", watches that
    // adapter alone, even when another one carries the internet

    property string interfaceName: "auto"
    property int updateInterval: 1000
    property string speedUnit: "bits"
    property int decimals: 1
    // Bar-label thresholds in bytes per second; the popup always shows the measured rates
    property real minimumUploadRate: 1000
    property real minimumDownloadRate: 1000
    property bool hideWhenOffline: false
    property bool showInterfaceName: true
    property bool showInternetInfo: true
    property bool tooltip: true
    property string icon: "\ueda3"
    property int iconSize: theme.bar.iconFont.pixelSize
    property string hotkey: ""
    property string alternateHotkey: ""
    property string resetHotkey: ""
    property real labelWidth: 0
    property int labelAlignment: Text.AlignLeft
    property int popupWidth: 404
    property string popupAlignment: "center"
    property bool showAlternate: false
    readonly property string text: format(showAlternate ? alternateLabel : label)
    readonly property var stats: monitor.data
    readonly property var history: monitor.history
    readonly property bool loading: monitor.loading
    readonly property string error: monitor.error

    readonly property bool dark: theme.dark
    // Text on the bar takes the theme's colour, and labels the bar's font; parts set in font replace the bar's
    property color textColor: theme.colors.text
    property font font
    property font iconFont
    iconFont.family: theme.bar.iconFont.family
    iconFont.weight: theme.bar.iconFont.weight
    iconFont.variableAxes: theme.bar.iconFont.variableAxes
    // The download and upload graphs, and the internet status while there is internet
    property color downColor: dark ? "#62a8ff" : "#1269d8"
    property color upColor: dark ? "#b39aff" : "#8457ce"
    property color internetColor: dark ? "#8fd5a4" : "#237b45"
    // The chosen period's tab, and the card with the numbers of the pointed sample
    property color tabColor: dark ? "#414141" : "#ffffff"
    property color tabBorderColor: "#e0e0e0"
    property color detailColor: dark ? "#303030" : "#ffffff"
    property color detailBorderColor: dark ? "#555555" : "#d3d3d3"
    // The popup: the theme's, unless set here
    property color popupColor: theme.popup.background
    property color popupBorderColor: theme.popup.border
    property color popupTextColor: theme.colors.text
    property color popupSecondaryTextColor: theme.colors.textSecondary
    property real popupRadius: theme.popup.radius
    property real popupGap: theme.popup.gap
    // Text in the popup: the theme's font family, in this widget's sizes
    property font popupFont
    popupFont.family: theme.popup.font.family
    popupFont.pixelSize: 13
    property int popupOpenDuration: theme.popup.openDuration
    property int popupCloseDuration: theme.popup.closeDuration
    property color popupSecondaryBackgroundColor: theme.colors.backgroundSecondary
    property color popupDividerColor: theme.colors.divider
    property color popupTertiaryTextColor: theme.colors.textTertiary
    property color popupHoverColor: theme.colors.hover
    property font popupTitleFont
    popupTitleFont.family: theme.popup.font.family
    popupTitleFont.pixelSize: 16
    popupTitleFont.weight: Font.DemiBold
    property font popupSmallFont
    popupSmallFont.family: theme.popup.font.family
    popupSmallFont.pixelSize: 12
    // The connection's name and the history's heading, the date of the pointed day, each live rate, and the
    // total over the period
    property font popupStrongFont
    popupStrongFont.family: theme.popup.font.family
    popupStrongFont.pixelSize: 14
    popupStrongFont.weight: Font.DemiBold
    property font detailTitleFont
    detailTitleFont.family: theme.popup.font.family
    detailTitleFont.pixelSize: 13
    detailTitleFont.weight: Font.DemiBold
    property font rateFont
    rateFont.family: theme.popup.font.family
    rateFont.pixelSize: 20
    rateFont.weight: Font.DemiBold
    property font totalFont
    totalFont.family: theme.popup.font.family
    totalFont.pixelSize: 25
    totalFont.weight: Font.DemiBold
    // The glyphs of the history's buttons, and of the connection
    property int popupIconSize: 14
    property int connectionIconSize: 19
    readonly property string edge: bar.edge
    readonly property bool shown: !hideWhenOffline || monitor.data.connected

    function speed(bytesPerSecond: real, threshold: real): string {
        const bits = speedUnit !== "bytes"
        const base = bits ? 1000 : 1024
        const units = bits ? ["bps", "Kbps", "Mbps", "Gbps", "Tbps"] : ["B/s", "KiB/s", "MiB/s", "GiB/s", "TiB/s"]
        let value = bytesPerSecond < threshold ? 0 : Math.max(0, bytesPerSecond) * (bits ? 8 : 1)
        let unit = 0
        while (value >= base && unit < units.length - 1) {
            value /= base
            ++unit
        }
        return `${value === 0 ? "0" : value.toFixed(Math.max(0, Math.min(decimals, 3)))} ${units[unit]}`
    }

    function dataSize(bytes: real): string {
        const units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]
        let value = Math.max(0, bytes)
        let unit = 0
        while (value >= 1024 && unit < units.length - 1) {
            value /= 1024
            ++unit
        }
        return `${unit === 0 ? Math.floor(value) : value.toFixed(1)} ${units[unit]}`
    }

    // Today included, as the popup's 7 and 30 days tabs count them
    function usage(days: int, key: string): real {
        const start = new Date()
        start.setHours(0, 0, 0, 0)
        start.setDate(start.getDate() - (days - 1))
        return monitor.history.daily.filter(point => point.stamp >= start.getTime()).reduce((sum, point) => sum + point[key], 0)
    }

    function format(template: string): string {
        const data = monitor.data
        const today = monitor.history.hourly
        const values = {
            download_speed: speed(data.downloadRate, minimumDownloadRate),
            upload_speed: speed(data.uploadRate, minimumUploadRate),
            session_downloaded: dataSize(data.sessionDownloaded),
            session_uploaded: dataSize(data.sessionUploaded),
            session_time: duration(data.sessionSeconds),
            today_downloaded: dataSize(today.reduce((sum, point) => sum + point.downloaded, 0)),
            today_uploaded: dataSize(today.reduce((sum, point) => sum + point.uploaded, 0)),
            week_downloaded: dataSize(usage(7, "downloaded")),
            week_uploaded: dataSize(usage(7, "uploaded")),
            month_downloaded: dataSize(usage(30, "downloaded")),
            month_uploaded: dataSize(usage(30, "uploaded")),
            network: data.profileName,
            adapter: data.adapterName,
            ip: data.ipAddress
        }
        return template.replace(/\{(\w+)\}/g,
            (match, name) => Object.prototype.hasOwnProperty.call(values, name) ? values[name] : match)
    }

    function duration(seconds: real): string {
        const value = Math.max(0, Math.floor(seconds))
        const days = Math.floor(value / 86400)
        const hours = Math.floor(value / 3600) % 24
        const minutes = Math.floor(value / 60) % 60
        if (days > 0)
            return `${days}d ${hours}h`
        if (value >= 3600)
            return `${Math.floor(value / 3600)}h ${minutes}m`
        return value >= 60 ? `${Math.floor(value / 60)}m` : `${value}s`
    }

    function placePopup() {
        const start = mapToGlobal(0, 0)
        const screen = networkTraffic.Screen
        let px
        let py
        switch (edge) {
        case "left":
            px = start.x + width + popupGap
            py = start.y + (height - popup.height) / 2
            break
        case "right":
            px = start.x - popup.width - popupGap
            py = start.y + (height - popup.height) / 2
            break
        default:
            px = popupAlignment === "left" ? start.x
                : popupAlignment === "right" ? start.x + width - popup.width : start.x + (width - popup.width) / 2
            py = edge === "bottom" ? start.y - popup.height - popupGap : start.y + height + popupGap
            break
        }
        popup.x = Math.round(Math.max(screen.virtualX + 8, Math.min(px, screen.virtualX + screen.width - popup.width - 8)))
        popup.y = Math.round(Math.max(screen.virtualY + 8, Math.min(py, screen.virtualY + screen.desktopAvailableHeight - popup.height - 8)))
    }

    function togglePopup() {
        if (popup.visible)
            popup.close()
        else {
            placePopup()
            popup.open()
        }
    }

    function resetUsage() { monitor.reset() }
    function refresh() { monitor.refresh() }

    implicitWidth: shown ? row.implicitWidth : 0
    implicitHeight: shown ? row.implicitHeight : 0
    visible: shown
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: qsTr("Network traffic: %1").arg(labelText.text)
    Accessible.onPressAction: togglePopup()
    Keys.onReturnPressed: togglePopup()
    Keys.onSpacePressed: togglePopup()
    Component.onDestruction: popup.hide()

    NetworkTrafficMonitor {
        id: monitor
        objectName: "monitor"
        interfaceName: networkTraffic.interfaceName
        updateInterval: networkTraffic.updateInterval
    }

    Hotkey { keys: networkTraffic.hotkey; onActivated: networkTraffic.togglePopup() }
    Hotkey { keys: networkTraffic.alternateHotkey; onActivated: networkTraffic.showAlternate = !networkTraffic.showAlternate }
    Hotkey { keys: networkTraffic.resetHotkey; onActivated: monitor.reset() }

    Connections {
        target: networkTraffic.Window.window
        function onVisibleChanged() {
            if (!networkTraffic.Window.window?.visible)
                popup.hide()
        }
        function onXChanged() { if (popup.visible && !popup.pinned) networkTraffic.placePopup() }
        function onYChanged() { if (popup.visible && !popup.pinned) networkTraffic.placePopup() }
    }

    Row {
        id: row
        height: parent.height
        spacing: 4

        Text {
            anchors.verticalCenter: parent.verticalCenter
            visible: networkTraffic.icon !== ""
            text: networkTraffic.icon
            color: networkTraffic.textColor
            font.family: networkTraffic.iconFont.family
            font.weight: networkTraffic.iconFont.weight
            font.variableAxes: networkTraffic.iconFont.variableAxes
            font.pixelSize: networkTraffic.iconSize
        }
        Label {
            id: labelText
            objectName: "label"
            anchors.verticalCenter: parent.verticalCenter
            visible: text !== ""
            width: networkTraffic.labelWidth > 0 ? networkTraffic.labelWidth : implicitWidth
            text: networkTraffic.text
            textFormat: Text.PlainText
            horizontalAlignment: networkTraffic.labelAlignment
            elide: Text.ElideRight
            color: networkTraffic.textColor
            font: networkTraffic.font
        }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: event => {
            if (event.button === Qt.LeftButton)
                networkTraffic.togglePopup()
            else
                networkTraffic.showAlternate = !networkTraffic.showAlternate
        }
    }

    ToolTip {
        objectName: "tooltip"
        popupType: Popup.Window
        visible: networkTraffic.tooltip && mouse.containsMouse && !popup.visible
        delay: 400
        text: monitor.error || qsTr("Download: %1\nUpload: %2")
            .arg(networkTraffic.speed(monitor.data.downloadRate, 0)).arg(networkTraffic.speed(monitor.data.uploadRate, 0))
        y: networkTraffic.edge === "bottom" ? -implicitHeight - 6 : networkTraffic.height + 6
    }

    BackdropPopup {
        id: popup
        objectName: "menu"
        property real reveal: 0
        title: qsTr("Network Traffic")
        width: Math.max(324, networkTraffic.popupWidth)
        height: panel.implicitHeight
        anchor: networkTraffic
        font: networkTraffic.popupFont
        theme: networkTraffic.theme
        backdropItem: panel
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: networkTraffic.popupOpenDuration; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: networkTraffic.popupCloseDuration; easing.type: Easing.InCubic }
        onVisibleChanged: {
            if (!visible) {
                reveal = 0
                pinned = false
            }
        }

        Rectangle {
            id: panel
            objectName: "trafficContent"

            anchors.fill: parent
            opacity: popup.reveal
            scale: 0.85 + popup.reveal * 0.15
            transformOrigin: networkTraffic.edge === "bottom" ? Item.Bottom : networkTraffic.edge === "left" ? Item.Left
                : networkTraffic.edge === "right" ? Item.Right : Item.Top

            property int period: 1
            property int hoveredIndex: -1
            readonly property string downloadText: networkTraffic.speed(monitor.data.downloadRate, 0)
            readonly property string uploadText: networkTraffic.speed(monitor.data.uploadRate, 0)

            readonly property bool hasHistory: monitor.data.connected && !monitor.history.loading && points.length > 0
            readonly property var points: {
                if (period === 0)
                    return monitor.history.hourly
                const start = new Date()
                start.setHours(0, 0, 0, 0)
                start.setDate(start.getDate() - (period === 1 ? 6 : 29))
                return monitor.history.daily.filter(point => point.stamp >= start.getTime())
            }
            readonly property real totalDown: points.reduce((sum, point) => sum + point.downloaded, 0)
            readonly property real totalUp: points.reduce((sum, point) => sum + point.uploaded, 0)
            readonly property real maximum: {
                const value = Math.max(1, ...points.map(point => point.downloaded + point.uploaded))
                const unit = value >= 1024 * 1024 * 1024 ? 1024 * 1024 * 1024 : 1024 * 1024
                return Math.ceil(value / unit) * unit
            }

            implicitHeight: body.y + body.implicitHeight + 12 + footer.height + 1
            color: networkTraffic.popupColor
            radius: networkTraffic.popupRadius
            border.width: 1
            border.color: networkTraffic.popupBorderColor

            function size(bytes: real): string {
                const units = ["B", "KiB", "MiB", "GiB", "TiB"]
                let amount = Math.max(0, bytes)
                let index = 0
                while (amount >= 1024 && index < units.length - 1) {
                    amount /= 1024
                    ++index
                }
                return `${index === 0 ? Math.floor(amount) : amount.toFixed(amount < 10 ? 2 : 1)} ${units[index]}`
            }

            onPeriodChanged: hoveredIndex = -1

            component IconButton: ToolButton {
                id: action
                required property string glyph
                required property string description
                implicitWidth: 28
                implicitHeight: 28
                hoverEnabled: true
                Accessible.name: description
                ToolTip.visible: hovered
                ToolTip.text: description
                ToolTip.delay: 400
                contentItem: Text {
                    text: action.glyph
                    color: networkTraffic.popupTextColor
                    opacity: action.checked ? 1 : 0.6
                    font.family: networkTraffic.iconFont.family
                    font.weight: networkTraffic.iconFont.weight
                    font.variableAxes: networkTraffic.iconFont.variableAxes
                    font.pixelSize: networkTraffic.popupIconSize
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    color: action.hovered ? networkTraffic.popupHoverColor : "transparent"
                    radius: 4
                }
            }

            ColumnLayout {
                id: body
                x: 16; y: 14
                width: parent.width - 32
                spacing: 0

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    Text {
                        Layout.fillWidth: true
                        text: "Network traffic"
                        font: networkTraffic.popupTitleFont
                        color: networkTraffic.popupTextColor
                        MouseArea {
                            property point grab
                            anchors.fill: parent
                            enabled: popup.pinned
                            cursorShape: popup.pinned ? Qt.SizeAllCursor : Qt.ArrowCursor
                            onPressed: event => {
                                const point = mapToGlobal(event.x, event.y)
                                grab = Qt.point(popup.x - point.x, popup.y - point.y)
                            }
                            onPositionChanged: event => {
                                const point = mapToGlobal(event.x, event.y)
                                popup.x = point.x + grab.x
                                popup.y = point.y + grab.y
                            }
                        }
                    }
                    IconButton {
                        glyph: "\ue72c"
                        description: "Refresh usage history"
                        onClicked: monitor.refresh()
                    }
                    IconButton {
                        glyph: popup.pinned ? "\ue77a" : "\ue840"
                        description: popup.pinned ? "Unpin popup" : "Pin popup"
                        checkable: true
                        checked: popup.pinned
                        onClicked: popup.pinned = !popup.pinned
                    }
                }
                // The header's bottom line, across the whole popup
                Rectangle {
                    Layout.fillWidth: true
                    Layout.leftMargin: -16
                    Layout.rightMargin: -16
                    Layout.topMargin: 10
                    implicitHeight: 1
                    color: networkTraffic.popupDividerColor
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: 8
                    visible: networkTraffic.showInterfaceName || networkTraffic.showInternetInfo
                    spacing: 10
                    Rectangle {
                        implicitWidth: 36; implicitHeight: 36
                        radius: 7
                        color: Qt.alpha(networkTraffic.popupTextColor, 0.045)
                        Text {
                            anchors.centerIn: parent
                            text: monitor.data.isWifi ? "\ue701" : "\ue839"
                            color: networkTraffic.popupTextColor
                            opacity: monitor.data.connected ? 0.85 : 0.4
                            font.family: networkTraffic.iconFont.family
                            font.weight: networkTraffic.iconFont.weight
                            font.variableAxes: networkTraffic.iconFont.variableAxes
                            font.pixelSize: networkTraffic.connectionIconSize
                        }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 4
                        Text {
                            Layout.fillWidth: true
                            visible: networkTraffic.showInterfaceName
                            text: monitor.data.connected ? monitor.data.profileName : monitor.loading ? qsTr("Connecting...") : qsTr("Not connected")
                            color: networkTraffic.popupTextColor
                            elide: Text.ElideRight
                            font: networkTraffic.popupStrongFont
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            visible: networkTraffic.showInternetInfo
                            spacing: 4

                            Text {
                                objectName: "connection"
                                Layout.fillWidth: true
                                Layout.maximumWidth: implicitWidth
                                Layout.alignment: Qt.AlignBaseline
                                elide: Text.ElideRight
                                text: monitor.error || (monitor.data.connected
                                    ? [monitor.data.adapterName, monitor.data.ipAddress].filter(Boolean).join(" · ") + " ·"
                                    : monitor.loading ? qsTr("Reading network status...") : qsTr("No active network profile"))
                                color: networkTraffic.popupSecondaryTextColor
                                font: networkTraffic.popupFont
                            }

                            Text {
                                Layout.alignment: Qt.AlignBaseline
                                visible: monitor.data.connected && !monitor.error
                                text: monitor.data.internetAvailable === true
                                    ? qsTr("Internet") : monitor.data.internetAvailable === false ? qsTr("No internet") : qsTr("Unknown")
                                color: monitor.data.internetAvailable === true ? networkTraffic.internetColor : networkTraffic.popupSecondaryTextColor
                                font: networkTraffic.popupFont
                            }

                            Item { Layout.fillWidth: true }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: 16
                    spacing: 10
                    Repeater {
                        model: [
                            {title: qsTr("Download"), value: panel.downloadText},
                            {title: qsTr("Upload"), value: panel.uploadText}
                        ]
                        delegate: Rectangle {
                            id: rate
                            required property var modelData
                            Layout.fillWidth: true
                            implicitHeight: 70
                            radius: 6
                            color: Qt.alpha(networkTraffic.popupTextColor, 0.035)
                            Column {
                                anchors.fill: parent; anchors.margins: 12
                                spacing: 7
                                Text {
                                    text: rate.modelData.title
                                    color: networkTraffic.popupTertiaryTextColor
                                    font: networkTraffic.popupFont
                                }
                                Text {
                                    width: parent.width
                                    elide: Text.ElideRight
                                    text: monitor.data.connected ? rate.modelData.value : "—"
                                    color: networkTraffic.popupTextColor
                                    font: networkTraffic.rateFont
                                }
                            }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: 12
                    spacing: 6
                    Text {
                        Layout.fillWidth: true
                        text: "This session"
                        color: networkTraffic.popupSecondaryTextColor
                        font: networkTraffic.popupFont
                        ToolTip.visible: sessionHover.hovered
                        ToolTip.text: "Traffic measured while YASB is running"
                        HoverHandler { id: sessionHover }
                    }
                    Text {
                        text: monitor.data.connected ? `↓ ${panel.size(monitor.data.sessionDownloaded)}` : "—"
                        color: networkTraffic.popupTextColor
                        font: networkTraffic.popupFont
                    }
                    Text {
                        Layout.leftMargin: 4
                        text: monitor.data.connected ? `↑ ${panel.size(monitor.data.sessionUploaded)}` : "—"
                        color: networkTraffic.popupTextColor
                        font: networkTraffic.popupFont
                    }
                    Text {
                        Layout.leftMargin: 4
                        text: monitor.data.connected ? networkTraffic.duration(monitor.data.sessionSeconds) : "—"
                        color: networkTraffic.popupSecondaryTextColor
                        font: networkTraffic.popupSmallFont
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.topMargin: 17
                    Layout.bottomMargin: 15
                    implicitHeight: 1
                    color: networkTraffic.popupDividerColor
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Text {
                        Layout.fillWidth: true
                        text: "Usage history"
                        color: networkTraffic.popupTextColor
                        font: networkTraffic.popupStrongFont
                    }
                    Rectangle {
                        implicitWidth: tabs.implicitWidth + 4
                        implicitHeight: 28
                        radius: 5
                        color: Qt.alpha(networkTraffic.popupTextColor, 0.04)
                        Row {
                            id: tabs
                            x: 2; y: 2
                            Repeater {
                                model: ["Today", "7 days", "30 days"]
                                delegate: ToolButton {
                                    id: tab
                                    required property int index
                                    required property string modelData
                                    height: 24
                                    width: 58
                                    hoverEnabled: true
                                    Accessible.name: modelData
                                    checkable: true
                                    checked: panel.period === index
                                    onClicked: panel.period = index
                                    background: Rectangle {
                                        radius: 4
                                        color: tab.checked ? networkTraffic.tabColor
                                            : tab.hovered ? networkTraffic.popupHoverColor : "transparent"
                                        border.width: tab.checked && !networkTraffic.dark ? 1 : 0
                                        border.color: networkTraffic.tabBorderColor
                                    }
                                    contentItem: Text {
                                        text: tab.modelData
                                        color: tab.checked ? networkTraffic.popupTextColor : networkTraffic.popupSecondaryTextColor
                                        font: networkTraffic.popupSmallFont
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter
                                    }
                                }
                            }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: 16
                    spacing: 8
                    Column {
                        Layout.fillWidth: true
                        spacing: 4
                        Text {
                            text: panel.hasHistory ? panel.size(panel.totalDown + panel.totalUp) : "—"
                            color: networkTraffic.popupTextColor
                            font: networkTraffic.totalFont
                        }
                        Text {
                            text: panel.period === 0 ? "Total today" : `Total over ${panel.period === 1 ? 7 : 30} days`
                            color: networkTraffic.popupSecondaryTextColor
                            font: networkTraffic.popupSmallFont
                        }
                    }
                    Column {
                        spacing: 6
                        Repeater {
                            model: [
                                {label:"Download", value:panel.totalDown, color:networkTraffic.downColor},
                                {label:"Upload", value:panel.totalUp, color:networkTraffic.upColor}
                            ]
                            delegate: Row {
                                id: legend
                                required property var modelData
                                spacing: 6
                                Rectangle {
                                    width: 6; height: 6; radius: 2
                                    anchors.verticalCenter: parent.verticalCenter
                                    color: legend.modelData.color
                                }
                                Text {
                                    width: 61
                                    text: legend.modelData.label
                                    color: networkTraffic.popupSecondaryTextColor
                                    font: networkTraffic.popupSmallFont
                                }
                                Text {
                                    width: 72
                                    horizontalAlignment: Text.AlignRight
                                    text: panel.hasHistory ? panel.size(legend.modelData.value) : "—"
                                    color: networkTraffic.popupTextColor
                                    font: networkTraffic.popupFont
                                }
                            }
                        }
                    }
                }

                Item {
                    id: chart
                    objectName: "usageChart"
                    Layout.fillWidth: true
                    Layout.topMargin: 18
                    implicitHeight: 166

                    Item {
                        id: axis
                        visible: panel.hasHistory
                        width: Math.max(topTick.implicitWidth, middleTick.implicitWidth) + 8
                        height: 138
                        Text {
                            id: topTick
                            text: panel.size(panel.maximum)
                            color: networkTraffic.popupSecondaryTextColor
                            font: networkTraffic.popupSmallFont
                            y: -height / 2
                        }
                        Text {
                            id: middleTick
                            text: panel.size(panel.maximum / 2)
                            color: networkTraffic.popupSecondaryTextColor
                            font: networkTraffic.popupSmallFont
                            y: (parent.height - height) / 2
                        }
                        Text {
                            text: "0"
                            color: networkTraffic.popupSecondaryTextColor
                            font: networkTraffic.popupSmallFont
                            y: parent.height - height / 2
                        }
                    }

                    Item {
                        id: plot
                        x: axis.width; width: parent.width - axis.width
                        height: 138
                        visible: panel.hasHistory
                        Repeater {
                            model: 3
                            delegate: Rectangle {
                                required property int index
                                width: plot.width
                                height: 1
                                y: index * (plot.height - 1) / 2
                                color: Qt.alpha(networkTraffic.popupTextColor, 0.075)
                            }
                        }
                        Row {
                            anchors.fill: parent
                            Repeater {
                                model: panel.points
                                delegate: Item {
                                    id: bar
                                    required property var modelData
                                    required property int index
                                    readonly property real barWidth: Math.min(panel.period === 1 ? 25 : 8, width - 3)
                                    readonly property real downHeight: plot.height * modelData.downloaded / panel.maximum
                                    readonly property real upHeight: plot.height * modelData.uploaded / panel.maximum
                                    width: plot.width / panel.points.length
                                    height: plot.height
                                    Accessible.role: Accessible.StaticText
                                    Accessible.name: `${Qt.formatDateTime(new Date(modelData.stamp), panel.period === 0 ? "hh:mm" : "ddd, d MMM")}, downloaded ${panel.size(modelData.downloaded)}, uploaded ${panel.size(modelData.uploaded)}`
                                    Rectangle {
                                        anchors.fill: parent
                                        anchors.leftMargin: 1
                                        anchors.rightMargin: 1
                                        radius: 3
                                        color: Qt.alpha(networkTraffic.popupTextColor, 0.045)
                                        visible: panel.hoveredIndex === bar.index
                                    }
                                    Rectangle {
                                        width: bar.barWidth
                                        height: bar.downHeight
                                        x: Math.round((parent.width - width) / 2)
                                        y: parent.height - height
                                        radius: 2
                                        color: networkTraffic.downColor
                                        opacity: panel.hoveredIndex < 0 || panel.hoveredIndex === bar.index ? 0.92 : 0.5
                                    }
                                    Rectangle {
                                        width: bar.barWidth
                                        height: bar.upHeight
                                        x: Math.round((parent.width - width) / 2)
                                        y: parent.height - height - bar.downHeight - 1
                                        radius: 2
                                        color: networkTraffic.upColor
                                        opacity: panel.hoveredIndex < 0 || panel.hoveredIndex === bar.index ? 0.92 : 0.5
                                    }
                                    Text {
                                        x: Math.max(-bar.x, Math.min((bar.width - width) / 2, plot.width - bar.x - width))
                                        y: plot.height + 8
                                        text: panel.period === 0 ? Qt.formatTime(new Date(bar.modelData.stamp), "hh")
                                            : panel.period === 1 ? Qt.formatDate(new Date(bar.modelData.stamp), "ddd")
                                            : Qt.formatDate(new Date(bar.modelData.stamp), "d MMM")
                                        visible: panel.period === 1 || (panel.period === 0 ? bar.index % 6 === 0
                                            : bar.index === 0 || bar.index === 14 || bar.index === panel.points.length - 1)
                                        color: networkTraffic.popupSecondaryTextColor
                                        font: networkTraffic.popupSmallFont
                                    }
                                    HoverHandler {
                                        onHoveredChanged: {
                                            if (hovered)
                                                panel.hoveredIndex = bar.index
                                            else if (panel.hoveredIndex === bar.index)
                                                panel.hoveredIndex = -1
                                        }
                                    }
                                }
                            }
                        }

                        Rectangle {
                            id: detail
                            readonly property var point: panel.hoveredIndex >= 0 ? (panel.points[panel.hoveredIndex] ?? null) : null
                            visible: point !== null
                            z: 2
                            width: 190; height: 64
                            x: Math.max(0, Math.min(plot.width - width, (panel.hoveredIndex + 0.5) * plot.width / panel.points.length - width / 2))
                            y: 3
                            radius: 5
                            color: networkTraffic.detailColor
                            border.width: 1
                            border.color: networkTraffic.detailBorderColor
                            Column {
                                anchors.fill: parent; anchors.margins: 9
                                spacing: 4
                                Text {
                                    text: detail.point ? Qt.formatDateTime(new Date(detail.point.stamp), panel.period === 0 ? "ddd, d MMM · hh:mm" : "ddd, d MMM") : ""
                                    color: networkTraffic.popupTextColor
                                    font: networkTraffic.detailTitleFont
                                }
                                Text {
                                    text: detail.point ? `↓ ${panel.size(detail.point.downloaded)}   ↑ ${panel.size(detail.point.uploaded)}` : ""
                                    color: networkTraffic.popupSecondaryTextColor
                                    font: networkTraffic.popupSmallFont
                                }
                            }
                        }
                    }

                    Column {
                        anchors.centerIn: parent
                        width: parent.width - 16
                        spacing: 9
                        visible: !panel.hasHistory
                        BusyIndicator {
                            anchors.horizontalCenter: parent.horizontalCenter
                            width: 24; height: 24
                            visible: monitor.data.connected && monitor.history.loading
                            running: visible
                            palette.dark: networkTraffic.popupSecondaryTextColor
                        }
                        Text {
                            width: parent.width
                            text: !monitor.data.connected ? "Connect to a network to view usage"
                                : monitor.history.loading ? "Loading usage history..." : "Usage history is unavailable"
                            color: networkTraffic.popupSecondaryTextColor
                            horizontalAlignment: Text.AlignHCenter
                            font: networkTraffic.popupFont
                        }
                        Text {
                            width: parent.width
                            visible: monitor.data.connected && !monitor.history.loading
                            text: "Live speeds and session usage are still available."
                            color: networkTraffic.popupSecondaryTextColor
                            horizontalAlignment: Text.AlignHCenter
                            font: networkTraffic.popupSmallFont
                        }
                    }
                }

            }

            Rectangle {
                id: footer
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.margins: 1
                height: 40
                bottomLeftRadius: networkTraffic.popupRadius - 1
                bottomRightRadius: networkTraffic.popupRadius - 1
                color: networkTraffic.popupSecondaryBackgroundColor

                Rectangle {
                    width: parent.width
                    height: 1
                    color: networkTraffic.popupDividerColor
                }

                Text {
                    x: 16
                    anchors.verticalCenter: parent.verticalCenter
                    text: qsTr("Windows usage estimates")
                    color: networkTraffic.popupSecondaryTextColor
                    font: networkTraffic.popupSmallFont
                    HoverHandler { id: infoHover }
                    ToolTip.visible: infoHover.hovered
                    ToolTip.delay: 500
                    ToolTip.text: qsTr("Windows records usage periodically. Recent traffic may appear after a delay.")
                }

                Text {
                    objectName: "updated"
                    anchors.right: parent.right
                    anchors.rightMargin: 16
                    anchors.verticalCenter: parent.verticalCenter
                    visible: panel.hasHistory && text !== ""
                    text: monitor.history.updatedAt > 0
                        ? qsTr("Updated %1").arg(Qt.formatTime(new Date(monitor.history.updatedAt), "hh:mm")) : ""
                    color: networkTraffic.popupTertiaryTextColor
                    font: networkTraffic.popupSmallFont
                }
            }
        }
    }
}
