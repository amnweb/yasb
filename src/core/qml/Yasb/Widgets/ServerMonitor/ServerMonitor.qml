pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Yasb
import Yasb.Bar
import Yasb.Common
import Yasb.Themes

Item {
    id: serverMonitor

    required property BarBase bar
    readonly property Theme theme: bar.theme
    // Accepts URL strings or entries such as { name: "Router", url: "http://192.168.1.1" }.
    property var servers: []
    // Seconds between checks and timeout per network operation.
    property int updateInterval: 300
    property int timeout: 5
    property bool sslCheck: true
    property bool sslVerify: true
    // Warn when fewer than this many days remain before certificate expiry.
    property int sslWarning: 30
    property bool notifyOffline: false
    property bool notifySsl: false
    property string label: ""
    property string alternateLabel: "{online}/{offline} of {total}"
    property bool showAlternate: false
    property string icon: "\uf760"
    property int iconSize: theme.bar.iconFont.pixelSize
    property bool tooltip: true
    property string hotkey: ""
    property string alternateHotkey: ""
    property int popupWidth: 404
    property string popupAlignment: "center"
    property int maxListHeight: 360
    property color onlineColor: serverMonitor.theme.colors.success
    property color offlineColor: serverMonitor.theme.colors.critical
    property color warningColor: serverMonitor.theme.colors.warning

    readonly property bool dark: theme.dark
    readonly property string edge: bar.edge
    // Text on the bar takes the theme's colour, and labels the bar's font; parts set in font replace the bar's
    property color textColor: theme.colors.text
    property font font
    property font iconFont
    iconFont.family: theme.bar.iconFont.family
    iconFont.weight: theme.bar.iconFont.weight
    iconFont.variableAxes: theme.bar.iconFont.variableAxes
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
    property font popupSmallFont
    popupSmallFont.family: theme.popup.font.family
    popupSmallFont.pixelSize: 12
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
    // Each server's name
    property font popupStrongFont
    popupStrongFont.family: theme.popup.font.family
    popupStrongFont.pixelSize: 13
    popupStrongFont.weight: Font.DemiBold

    readonly property var results: monitor.results
    readonly property int offlineCount: results.filter(server => server.status === "Offline").length
    readonly property int onlineCount: results.length - offlineCount
    readonly property bool hasWarning: results.some(server => warning(server))
    readonly property string summary: results.length > 0
        ? qsTr("%1 online · %2 offline").arg(onlineCount).arg(offlineCount) : ""
    readonly property string checked: {
        const at = monitor.updated
        if (!(at instanceof Date) || isNaN(at))
            return ""
        const time = Qt.formatTime(at, Qt.locale().timeFormat(Locale.ShortFormat))
        return at.toDateString() === new Date().toDateString() ? time
            : `${Qt.locale().dayName(at.getDay(), Locale.ShortFormat)} ${time}`
    }
    readonly property string placeholder: monitor.error || (monitor.loading ? qsTr("Checking servers...")
        : monitor.configured ? qsTr("Waiting for the first check...") : qsTr("No servers configured"))
    readonly property var checkSettings: [servers ?? [], sslVerify, sslCheck, timeout, updateInterval,
        sslWarning, notifyOffline, notifySsl]

    function configureMonitor() {
        monitor.configure(...checkSettings)
    }

    onCheckSettingsChanged: Qt.callLater(serverMonitor.configureMonitor)
    Component.onCompleted: Qt.callLater(serverMonitor.configureMonitor)
    Component.onDestruction: popup.hide()

    function warning(server: var): bool {
        return typeof server.ssl === "number" && server.ssl < sslWarning
    }

    function labelText(template: string): string {
        return template.replace(/\{online\}/g, String(onlineCount))
            .replace(/\{offline\}/g, String(offlineCount)).replace(/\{total\}/g, String(results.length))
    }

    function details(server: var): string {
        if (typeof server.response_code !== "number")
            return qsTr("Server is unreachable")
        const parts = [qsTr("%1 ms").arg(server.response_time), qsTr("HTTP %1").arg(server.response_code)]
        if (typeof server.ssl === "number") {
            parts.push(server.ssl < 0 ? qsTr("Certificate expired")
                : qsTr("Certificate expires in %n day(s)", "", server.ssl))
        }
        return parts.join(" · ")
    }

    function placePopup() {
        const start = mapToGlobal(0, 0)
        const screen = serverMonitor.Screen
        const gap = popupGap
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
        popup.x = Math.round(Math.max(screen.virtualX + margin,
            Math.min(px, screen.virtualX + screen.width - popup.width - margin)))
        popup.y = Math.round(Math.max(screen.virtualY + margin,
            Math.min(py, screen.virtualY + screen.desktopAvailableHeight - popup.height - margin)))
    }

    function togglePopup() {
        if (popup.visible)
            popup.close()
        else {
            placePopup()
            popup.open()
        }
    }

    function refresh() { monitor.refresh() }

    implicitWidth: barRow.implicitWidth
    implicitHeight: barRow.implicitHeight
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: summary ? qsTr("Server Monitor, %1").arg(summary) : qsTr("Server Monitor")
    Accessible.onPressAction: togglePopup()
    Keys.onReturnPressed: togglePopup()
    Keys.onSpacePressed: togglePopup()

    ServerChecks {
        id: monitor
        objectName: "monitor"
    }

    Hotkey { keys: serverMonitor.hotkey; onActivated: serverMonitor.togglePopup() }
    Hotkey { keys: serverMonitor.alternateHotkey; onActivated: serverMonitor.showAlternate = !serverMonitor.showAlternate }

    Connections {
        target: serverMonitor.Window.window
        function onVisibleChanged() { if (!serverMonitor.Window.window?.visible) popup.hide() }
        function onXChanged() { if (popup.visible) serverMonitor.placePopup() }
        function onYChanged() { if (popup.visible) serverMonitor.placePopup() }
    }

    component StatusMark: Rectangle {
        property bool ring: false
        property color ink: serverMonitor.textColor
        implicitWidth: 12
        implicitHeight: 12
        radius: width / 2
        color: ring ? "transparent" : ink
        border.color: ink
        border.width: ring ? 2 : 0
    }

    Row {
        id: barRow
        height: parent.height
        spacing: 6

        Text {
            objectName: "icon"
            anchors.verticalCenter: parent.verticalCenter
            visible: serverMonitor.icon !== ""
            text: serverMonitor.icon
            textFormat: Text.PlainText
            color: serverMonitor.offlineCount > 0 ? serverMonitor.offlineColor : serverMonitor.hasWarning ? serverMonitor.warningColor
                : serverMonitor.results.length ? serverMonitor.onlineColor : serverMonitor.textColor
            font.family: serverMonitor.iconFont.family
            font.weight: serverMonitor.iconFont.weight
            font.variableAxes: serverMonitor.iconFont.variableAxes
            font.pixelSize: serverMonitor.iconSize
        }
        Label {
            objectName: "label"
            anchors.verticalCenter: parent.verticalCenter
            text: serverMonitor.labelText(serverMonitor.showAlternate ? serverMonitor.alternateLabel : serverMonitor.label)
            visible: text !== ""
            textFormat: Text.PlainText
            color: serverMonitor.textColor
            font: serverMonitor.font
        }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        cursorShape: Qt.PointingHandCursor
        onClicked: event => {
            if (event.button === Qt.LeftButton)
                serverMonitor.togglePopup()
            else
                serverMonitor.showAlternate = !serverMonitor.showAlternate
        }
    }

    ToolTip {
        objectName: "tooltip"
        popupType: Popup.Window
        visible: serverMonitor.tooltip && mouse.containsMouse && !popup.visible
        delay: 400
        text: serverMonitor.summary || serverMonitor.placeholder
        y: serverMonitor.edge === "bottom" ? -implicitHeight - 6 : serverMonitor.height + 6
    }

    BackdropPopup {
        id: popup

        property real reveal: 0

        objectName: "menu"
        title: qsTr("Server Monitor")
        anchor: serverMonitor
        font: serverMonitor.popupFont
        theme: serverMonitor.theme
        backdropItem: panel
        width: Math.min(Math.max(244, serverMonitor.popupWidth), serverMonitor.Screen.width - 32)
        height: Math.min(popupContent.implicitHeight, serverMonitor.Screen.desktopAvailableHeight - 40)
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: serverMonitor.popupOpenDuration; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: serverMonitor.popupCloseDuration; easing.type: Easing.InCubic }
        onVisibleChanged: {
            if (!visible)
                reveal = 0
        }
        onHeightChanged: { if (visible) serverMonitor.placePopup() }
        onWidthChanged: { if (visible) serverMonitor.placePopup() }

        Rectangle {
            id: panel
            anchors.fill: parent
            radius: serverMonitor.popupRadius
            color: serverMonitor.popupColor
            border.width: 1
            border.color: serverMonitor.popupBorderColor
            opacity: popup.reveal
            scale: 0.85 + popup.reveal * 0.15
            transformOrigin: serverMonitor.edge === "bottom" ? Item.Bottom : serverMonitor.edge === "left" ? Item.Left
                : serverMonitor.edge === "right" ? Item.Right : Item.Top
            clip: true

            component PopupText: Text {
                color: serverMonitor.popupTextColor
                font: serverMonitor.popupFont
                textFormat: Text.PlainText
            }

            ColumnLayout {
                id: popupContent
                anchors.fill: parent
                spacing: 0

                RowLayout {
                    Layout.fillWidth: true
                    Layout.leftMargin: 16
                    Layout.rightMargin: 16
                    Layout.topMargin: 12
                    Layout.bottomMargin: 10
                    spacing: 8

                    PopupText {
                        Layout.fillWidth: true
                        text: qsTr("Server Monitor")
                        font: serverMonitor.popupTitleFont
                    }
                    PopupText {
                        objectName: "summary"
                        text: serverMonitor.summary
                        font: serverMonitor.popupSmallFont
                        color: serverMonitor.popupTertiaryTextColor
                    }
                }

                LoadingLine {
                    Layout.fillWidth: true
                    running: monitor.loading
                    trackColor: serverMonitor.popupDividerColor
                }

                PopupText {
                    Layout.fillWidth: true
                    Layout.margins: 16
                    visible: !serverMonitor.results.length || !!monitor.error
                    text: serverMonitor.placeholder
                    wrapMode: Text.Wrap
                    font: serverMonitor.popupSmallFont
                    color: monitor.error ? serverMonitor.offlineColor : serverMonitor.popupSecondaryTextColor
                }

                Flickable {
                    id: list
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(contentHeight, serverMonitor.maxListHeight,
                        Math.max(80, serverMonitor.Screen.desktopAvailableHeight - 124))
                    visible: serverMonitor.results.length > 0
                    clip: true
                    contentHeight: rows.implicitHeight
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar {}

                    Column {
                        id: rows
                        width: list.width
                        topPadding: 4
                        bottomPadding: 4

                        Repeater {
                            model: serverMonitor.results

                            delegate: ItemDelegate {
                                id: serverRow
                                required property var modelData
                                required property int index
                                readonly property bool offline: modelData.status === "Offline"
                                readonly property bool hasWarning: serverMonitor.warning(modelData)
                                readonly property string status: offline ? qsTr("Offline")
                                    : hasWarning ? qsTr("Online with certificate warning") : qsTr("Online")

                                objectName: "serverRow" + index
                                width: rows.width
                                padding: 10
                                leftPadding: 16
                                rightPadding: 16
                                hoverEnabled: true
                                enabled: /^https?:\/\//i.test(modelData.url)
                                Accessible.name: qsTr("%1, %2").arg(modelData.name).arg(status)
                                Accessible.description: serverMonitor.details(modelData)
                                onClicked: Qt.openUrlExternally(modelData.url)

                                HoverHandler {
                                    enabled: serverRow.enabled
                                    cursorShape: Qt.PointingHandCursor
                                }

                                background: Rectangle {
                                    color: serverRow.hovered || serverRow.visualFocus
                                        ? serverMonitor.popupHoverColor : "transparent"
                                }

                                Rectangle {
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.leftMargin: 16
                                    anchors.rightMargin: 16
                                    height: 1
                                    visible: serverRow.index > 0
                                    color: serverMonitor.popupDividerColor
                                }

                                contentItem: ColumnLayout {
                                    spacing: 3
                                    RowLayout {
                                        Layout.fillWidth: true
                                        PopupText {
                                            Layout.fillWidth: true
                                            text: serverRow.modelData.name
                                            font: serverMonitor.popupStrongFont
                                            elide: Text.ElideRight
                                        }
                                        StatusMark {
                                            ring: serverRow.offline || serverRow.hasWarning
                                            ink: serverRow.offline ? serverMonitor.offlineColor
                                                : serverRow.hasWarning ? serverMonitor.warningColor : serverMonitor.onlineColor
                                        }
                                    }
                                    PopupText {
                                        Layout.fillWidth: true
                                        text: serverMonitor.details(serverRow.modelData)
                                        font: serverMonitor.popupSmallFont
                                        color: serverMonitor.popupSecondaryTextColor
                                        wrapMode: Text.Wrap
                                    }
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
                    implicitHeight: 40
                    bottomLeftRadius: serverMonitor.popupRadius - 1
                    bottomRightRadius: serverMonitor.popupRadius - 1
                    color: serverMonitor.popupSecondaryBackgroundColor

                    Rectangle {
                        width: parent.width
                        height: 1
                        color: serverMonitor.popupDividerColor
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 8
                        anchors.rightMargin: 16
                        spacing: 8

                        Button {
                            id: refreshButton
                            objectName: "refresh"
                            text: qsTr("Refresh")
                            enabled: monitor.configured && !monitor.loading
                            hoverEnabled: true
                            leftPadding: 8
                            rightPadding: 8
                            onClicked: serverMonitor.refresh()
                            HoverHandler {
                                enabled: refreshButton.enabled
                                cursorShape: Qt.PointingHandCursor
                            }
                            contentItem: PopupText {
                                text: refreshButton.text
                                color: !refreshButton.enabled ? serverMonitor.popupTertiaryTextColor
                                    : refreshButton.hovered || refreshButton.visualFocus ? serverMonitor.popupTextColor : serverMonitor.popupSecondaryTextColor
                                font: serverMonitor.popupSmallFont
                            }
                            background: Rectangle {
                                radius: 4
                                color: refreshButton.hovered || refreshButton.visualFocus
                                    ? serverMonitor.popupHoverColor : "transparent"
                            }
                        }

                        PopupText {
                            objectName: "checked"
                            Layout.fillWidth: true
                            horizontalAlignment: Text.AlignRight
                            text: serverMonitor.checked ? qsTr("Checked at %1").arg(serverMonitor.checked) : ""
                            color: serverMonitor.popupTertiaryTextColor
                            font: serverMonitor.popupSmallFont
                        }
                    }
                }
            }
        }
    }
}
