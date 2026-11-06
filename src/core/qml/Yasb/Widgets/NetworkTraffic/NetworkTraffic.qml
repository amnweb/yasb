pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Yasb
import Yasb.Common

Item {
    id: widget

    property Item bar: null
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
    property int iconSize: 16
    property string keys: ""
    property string alternateKeys: ""
    property string resetKeys: ""
    property real labelWidth: 0
    property int labelAlignment: Text.AlignLeft
    property int popupWidth: 420
    property string popupAlignment: "center"
    property bool showAlternate: false
    //property string label: `↓ ${speed(monitor.data.downloadRate, minimumDownloadRate)}  ↑ ${speed(monitor.data.uploadRate, minimumUploadRate)}`
    property string label: ""
    property string alternateLabel: `↓ ${dataSize(monitor.data.sessionDownloaded)}  ↑ ${dataSize(monitor.data.sessionUploaded)}`
    readonly property var stats: monitor.data
    readonly property var history: monitor.history
    readonly property bool loading: monitor.loading
    readonly property string error: monitor.error

    readonly property bool dark: bar ? bar.dark : Qt.styleHints.colorScheme === Qt.ColorScheme.Dark
    property color textColor: bar?.textColor ?? (dark ? "#ffffff" : "#000000")
    property font font
    font.family: bar?.font.family ?? Qt.application.font.family
    font.pixelSize: bar?.font.pixelSize ?? 13
    font.weight: bar?.font.weight ?? Font.Normal
    font.italic: bar?.font.italic ?? false
    font.letterSpacing: bar?.font.letterSpacing ?? 0
    font.capitalization: bar?.font.capitalization ?? Font.MixedCase
    font.variableAxes: bar?.font.variableAxes ?? ({})
    property font iconFont
    iconFont.family: bar?.iconFont?.family ?? "Segoe Fluent Icons"
    iconFont.weight: bar?.iconFont?.weight ?? Font.Normal
    readonly property string edge: bar?.edge ?? "top"
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
        const screen = widget.Screen
        let px
        let py
        switch (edge) {
        case "left":
            px = start.x + width + 6
            py = start.y + (height - popup.height) / 2
            break
        case "right":
            px = start.x - popup.width - 6
            py = start.y + (height - popup.height) / 2
            break
        default:
            px = popupAlignment === "left" ? start.x
                : popupAlignment === "right" ? start.x + width - popup.width : start.x + (width - popup.width) / 2
            py = edge === "bottom" ? start.y - popup.height - 6 : start.y + height + 6
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
        interfaceName: widget.interfaceName
        updateInterval: widget.updateInterval
    }

    Hotkey { keys: widget.keys; onActivated: widget.togglePopup() }
    Hotkey { keys: widget.alternateKeys; onActivated: widget.showAlternate = !widget.showAlternate }
    Hotkey { keys: widget.resetKeys; onActivated: monitor.reset() }

    Connections {
        target: widget.Window.window
        function onVisibleChanged() {
            if (!widget.Window.window?.visible)
                popup.hide()
        }
        function onXChanged() { if (popup.visible && !popup.pinned) widget.placePopup() }
        function onYChanged() { if (popup.visible && !popup.pinned) widget.placePopup() }
    }

    Row {
        id: row
        height: parent.height
        spacing: 4

        Text {
            anchors.verticalCenter: parent.verticalCenter
            visible: widget.icon !== ""
            text: widget.icon
            color: widget.textColor
            font.family: widget.iconFont.family
            font.weight: widget.iconFont.weight
            font.pixelSize: widget.iconSize
        }
        Text {
            id: labelText
            objectName: "label"
            anchors.verticalCenter: parent.verticalCenter
            width: widget.labelWidth > 0 ? widget.labelWidth : implicitWidth
            text: widget.showAlternate ? widget.alternateLabel : widget.label
            horizontalAlignment: widget.labelAlignment
            elide: Text.ElideRight
            color: widget.textColor
            font: widget.font
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
                widget.togglePopup()
            else
                widget.showAlternate = !widget.showAlternate
        }
    }

    ToolTip {
        objectName: "tooltip"
        popupType: Popup.Window
        visible: widget.tooltip && mouse.containsMouse && !popup.visible
        delay: 400
        text: monitor.error || qsTr("Download: %1\nUpload: %2")
            .arg(widget.speed(monitor.data.downloadRate, 0)).arg(widget.speed(monitor.data.uploadRate, 0))
        y: widget.edge === "bottom" ? -implicitHeight - 6 : widget.height + 6
    }

    BackdropPopup {
        id: popup
        objectName: "menu"
        property real reveal: 0
        title: qsTr("Network Traffic")
        width: Math.max(340, widget.popupWidth)
        height: panel.implicitHeight + 16
        anchor: widget
        backdropItem: panel
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: 180; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: 140; easing.type: Easing.InCubic }
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
            anchors.margins: 8
            opacity: popup.reveal
            scale: 0.85 + popup.reveal * 0.15
            transformOrigin: widget.edge === "bottom" ? Item.Bottom : widget.edge === "left" ? Item.Left
                : widget.edge === "right" ? Item.Right : Item.Top

            property int period: 1
            property int hoveredIndex: -1
            readonly property string downloadText: widget.speed(monitor.data.downloadRate, 0)
            readonly property string uploadText: widget.speed(monitor.data.uploadRate, 0)

            readonly property color ink: widget.dark ? "#ffffff" : "#171717"
            readonly property color secondary: Qt.alpha(ink, 0.786)
            readonly property color muted: Qt.alpha(ink, 0.544)
            readonly property color line: Qt.alpha(ink, 0.08)
            readonly property color downColor: widget.dark ? "#62a8ff" : "#1269d8"
            readonly property color upColor: widget.dark ? "#b39aff" : "#8457ce"
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
            color: widget.dark ? Qt.alpha("#202020", 0.85) : Qt.alpha("#f3f3f3", 0.85)
            radius: 8
            border.width: 1
            border.color: widget.dark ? "#3a3a3a" : "#d9d9d9"

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
                    color: panel.ink
                    opacity: action.checked ? 1 : 0.6
                    font.family: widget.iconFont.family
                    font.weight: widget.iconFont.weight
                    font.pixelSize: 14
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    color: action.hovered ? Qt.alpha(panel.ink, 0.07) : "transparent"
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
                        text: "<b>Network</b> Traffic"
                        textFormat: Text.StyledText
                        color: panel.ink
                        font.family: widget.font.family
                        font.pixelSize: 16
                        MouseArea {
                            property point grab
                            anchors.fill: parent
                            enabled: popup.pinned
                            cursorShape: Qt.SizeAllCursor
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

                RowLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: 14
                    visible: widget.showInterfaceName || widget.showInternetInfo
                    spacing: 10
                    Rectangle {
                        implicitWidth: 36; implicitHeight: 36
                        radius: 7
                        color: Qt.alpha(panel.ink, 0.045)
                        Text {
                            anchors.centerIn: parent
                            text: monitor.data.isWifi ? "\ue701" : "\ue839"
                            color: panel.ink
                            opacity: monitor.data.connected ? 0.85 : 0.4
                            font.family: widget.iconFont.family
                            font.weight: widget.iconFont.weight
                            font.pixelSize: 19
                        }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 4
                        Text {
                            Layout.fillWidth: true
                            visible: widget.showInterfaceName
                            text: monitor.data.connected ? monitor.data.profileName : monitor.loading ? qsTr("Connecting...") : qsTr("Not connected")
                            color: panel.ink
                            elide: Text.ElideRight
                            font.family: widget.font.family
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            visible: widget.showInternetInfo
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
                                color: panel.secondary
                                font.family: widget.font.family
                                font.pixelSize: 13
                            }

                            Text {
                                Layout.alignment: Qt.AlignBaseline
                                visible: monitor.data.connected && !monitor.error
                                text: monitor.data.internetAvailable === true
                                    ? qsTr("Internet") : monitor.data.internetAvailable === false ? qsTr("No internet") : qsTr("Unknown")
                                color: monitor.data.internetAvailable === true ? (widget.dark ? "#8fd5a4" : "#237b45") : panel.secondary
                                font.family: widget.font.family
                                font.pixelSize: 13
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
                            color: Qt.alpha(panel.ink, 0.035)
                            Column {
                                anchors.fill: parent; anchors.margins: 12
                                spacing: 7
                                Text {
                                    text: rate.modelData.title
                                    color: panel.muted
                                    font.family: widget.font.family
                                    font.pixelSize: 13
                                }
                                Text {
                                    width: parent.width
                                    elide: Text.ElideRight
                                    text: monitor.data.connected ? rate.modelData.value : "—"
                                    color: panel.ink
                                    font.family: widget.font.family
                                    font.pixelSize: 20
                                    font.weight: Font.DemiBold
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
                        color: panel.secondary
                        font.family: widget.font.family
                        font.pixelSize: 13
                        ToolTip.visible: sessionHover.hovered
                        ToolTip.text: "Traffic measured while YASB is running"
                        HoverHandler { id: sessionHover }
                    }
                    Text {
                        text: monitor.data.connected ? `↓ ${panel.size(monitor.data.sessionDownloaded)}` : "—"
                        color: panel.ink
                        font.family: widget.font.family
                        font.pixelSize: 13
                    }
                    Text {
                        Layout.leftMargin: 4
                        text: monitor.data.connected ? `↑ ${panel.size(monitor.data.sessionUploaded)}` : "—"
                        color: panel.ink
                        font.family: widget.font.family
                        font.pixelSize: 13
                    }
                    Text {
                        Layout.leftMargin: 4
                        text: monitor.data.connected ? widget.duration(monitor.data.sessionSeconds) : "—"
                        color: panel.secondary
                        font.family: widget.font.family
                        font.pixelSize: 12
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.topMargin: 17
                    Layout.bottomMargin: 15
                    implicitHeight: 1
                    color: panel.line
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Text {
                        Layout.fillWidth: true
                        text: "Usage history"
                        color: panel.ink
                        font.family: widget.font.family
                        font.pixelSize: 14
                        font.weight: Font.DemiBold
                    }
                    Rectangle {
                        implicitWidth: tabs.implicitWidth + 4
                        implicitHeight: 28
                        radius: 5
                        color: Qt.alpha(panel.ink, 0.04)
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
                                        color: tab.checked ? (widget.dark ? "#414141" : "#ffffff")
                                            : tab.hovered ? Qt.alpha(panel.ink, 0.055) : "transparent"
                                        border.width: tab.checked && !widget.dark ? 1 : 0
                                        border.color: "#e0e0e0"
                                    }
                                    contentItem: Text {
                                        text: tab.modelData
                                        color: tab.checked ? panel.ink : panel.secondary
                                        font.family: widget.font.family
                                        font.pixelSize: 12
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
                            color: panel.ink
                            font.family: widget.font.family
                            font.pixelSize: 25
                            font.weight: Font.DemiBold
                        }
                        Text {
                            text: panel.period === 0 ? "Total today" : `Total over ${panel.period === 1 ? 7 : 30} days`
                            color: panel.secondary
                            font.family: widget.font.family
                            font.pixelSize: 12
                        }
                    }
                    Column {
                        spacing: 6
                        Repeater {
                            model: [
                                {label:"Download", value:panel.totalDown, color:panel.downColor},
                                {label:"Upload", value:panel.totalUp, color:panel.upColor}
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
                                    color: panel.secondary
                                    font.family: widget.font.family
                                    font.pixelSize: 12
                                }
                                Text {
                                    width: 72
                                    horizontalAlignment: Text.AlignRight
                                    text: panel.hasHistory ? panel.size(legend.modelData.value) : "—"
                                    color: panel.ink
                                    font.family: widget.font.family
                                    font.pixelSize: 13
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
                            color: panel.secondary
                            font.family: widget.font.family
                            font.pixelSize: 12
                            y: -height / 2
                        }
                        Text {
                            id: middleTick
                            text: panel.size(panel.maximum / 2)
                            color: panel.secondary
                            font.family: widget.font.family
                            font.pixelSize: 12
                            y: (parent.height - height) / 2
                        }
                        Text {
                            text: "0"
                            color: panel.secondary
                            font.family: widget.font.family
                            font.pixelSize: 12
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
                                color: Qt.alpha(panel.ink, 0.075)
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
                                        color: Qt.alpha(panel.ink, 0.045)
                                        visible: panel.hoveredIndex === bar.index
                                    }
                                    Rectangle {
                                        width: bar.barWidth
                                        height: bar.downHeight
                                        x: Math.round((parent.width - width) / 2)
                                        y: parent.height - height
                                        radius: 2
                                        color: panel.downColor
                                        opacity: panel.hoveredIndex < 0 || panel.hoveredIndex === bar.index ? 0.92 : 0.5
                                    }
                                    Rectangle {
                                        width: bar.barWidth
                                        height: bar.upHeight
                                        x: Math.round((parent.width - width) / 2)
                                        y: parent.height - height - bar.downHeight - 1
                                        radius: 2
                                        color: panel.upColor
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
                                        color: panel.secondary
                                        font.family: widget.font.family
                                        font.pixelSize: 12
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
                            color: widget.dark ? "#303030" : "#ffffff"
                            border.width: 1
                            border.color: widget.dark ? "#555555" : "#d3d3d3"
                            Column {
                                anchors.fill: parent; anchors.margins: 9
                                spacing: 4
                                Text {
                                    text: detail.point ? Qt.formatDateTime(new Date(detail.point.stamp), panel.period === 0 ? "ddd, d MMM · hh:mm" : "ddd, d MMM") : ""
                                    color: panel.ink
                                    font.family: widget.font.family
                                    font.pixelSize: 13
                                    font.weight: Font.DemiBold
                                }
                                Text {
                                    text: detail.point ? `↓ ${panel.size(detail.point.downloaded)}   ↑ ${panel.size(detail.point.uploaded)}` : ""
                                    color: panel.secondary
                                    font.family: widget.font.family
                                    font.pixelSize: 12
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
                            palette.dark: panel.secondary
                        }
                        Text {
                            width: parent.width
                            text: !monitor.data.connected ? "Connect to a network to view usage"
                                : monitor.history.loading ? "Loading usage history..." : "Usage history is unavailable"
                            color: panel.secondary
                            horizontalAlignment: Text.AlignHCenter
                            font.family: widget.font.family
                            font.pixelSize: 13
                        }
                        Text {
                            width: parent.width
                            visible: monitor.data.connected && !monitor.history.loading
                            text: "Live speeds and session usage are still available."
                            color: panel.secondary
                            horizontalAlignment: Text.AlignHCenter
                            font.family: widget.font.family
                            font.pixelSize: 12
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
                bottomLeftRadius: 7
                bottomRightRadius: 7
                color: Qt.alpha("#000000", widget.dark ? 0.15 : 0.03)

                Rectangle {
                    width: parent.width
                    height: 1
                    color: panel.line
                }

                Text {
                    x: 16
                    anchors.verticalCenter: parent.verticalCenter
                    text: qsTr("Windows usage estimates")
                    color: panel.secondary
                    font.family: widget.font.family
                    font.pixelSize: 12
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
                    color: panel.muted
                    font.family: widget.font.family
                    font.pixelSize: 12
                }
            }
        }
    }
}
