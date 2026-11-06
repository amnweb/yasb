pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Yasb
import Yasb.Common

Item {
    id: widget

    property Item bar: null
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
    property int iconSize: font.pixelSize + 1
    property bool tooltip: true
    property string keys: ""
    property string alternateKeys: ""
    property int popupWidth: 420
    property string popupAlignment: "center"
    property int maxListHeight: 360
    property color onlineColor: dark ? "#6CCB5F" : "#0F7B0F"
    property color offlineColor: dark ? "#FF99A4" : "#C42B1C"
    property color warningColor: dark ? "#FCE100" : "#9D5D00"

    readonly property bool dark: bar ? bar.dark : Qt.styleHints.colorScheme === Qt.ColorScheme.Dark
    readonly property string edge: bar?.edge ?? "top"
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

    onCheckSettingsChanged: Qt.callLater(widget.configureMonitor)
    Component.onCompleted: Qt.callLater(widget.configureMonitor)
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
        const screen = widget.Screen
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

    Hotkey { keys: widget.keys; onActivated: widget.togglePopup() }
    Hotkey { keys: widget.alternateKeys; onActivated: widget.showAlternate = !widget.showAlternate }

    Connections {
        target: widget.Window.window
        function onVisibleChanged() { if (!widget.Window.window?.visible) popup.hide() }
        function onXChanged() { if (popup.visible) widget.placePopup() }
        function onYChanged() { if (popup.visible) widget.placePopup() }
    }

    component StatusMark: Rectangle {
        property bool ring: false
        property color ink: widget.textColor
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
            visible: widget.icon !== ""
            text: widget.icon
            textFormat: Text.PlainText
            color: widget.offlineCount > 0 ? widget.offlineColor : widget.hasWarning ? widget.warningColor
                : widget.results.length ? widget.onlineColor : widget.textColor
            font.family: widget.iconFont.family
            font.weight: widget.iconFont.weight
            font.pixelSize: widget.iconSize
        }
        Text {
            objectName: "label"
            anchors.verticalCenter: parent.verticalCenter
            text: widget.labelText(widget.showAlternate ? widget.alternateLabel : widget.label)
            visible: text !== ""
            textFormat: Text.PlainText
            color: widget.textColor
            font: widget.font
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
        text: widget.summary || widget.placeholder
        y: widget.edge === "bottom" ? -implicitHeight - 6 : widget.height + 6
    }

    BackdropPopup {
        id: popup

        property real reveal: 0
        readonly property color ink: widget.dark ? "#ffffff" : "#000000"
        readonly property color secondary: Qt.alpha(ink, 0.786)
        readonly property color muted: Qt.alpha(ink, 0.544)
        readonly property color line: Qt.alpha(ink, 0.08)

        objectName: "menu"
        title: qsTr("Server Monitor")
        anchor: widget
        backdropItem: panel
        width: Math.min(Math.max(260, widget.popupWidth), widget.Screen.width - 16)
        height: Math.min(content.implicitHeight + 16, widget.Screen.desktopAvailableHeight - 24)
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: 180; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: 140; easing.type: Easing.InCubic }
        onVisibleChanged: {
            if (!visible)
                reveal = 0
        }
        onHeightChanged: { if (visible) widget.placePopup() }
        onWidthChanged: { if (visible) widget.placePopup() }

        Rectangle {
            id: panel
            anchors.fill: parent
            anchors.margins: 8
            radius: 8
            color: widget.dark ? Qt.alpha("#202020", 0.85) : Qt.alpha("#F3F3F3", 0.85)
            border.width: 1
            border.color: widget.dark ? "#3A3A3A" : "#D9D9D9"
            opacity: popup.reveal
            scale: 0.85 + popup.reveal * 0.15
            transformOrigin: widget.edge === "bottom" ? Item.Bottom : widget.edge === "left" ? Item.Left
                : widget.edge === "right" ? Item.Right : Item.Top
            clip: true

            component PopupText: Text {
                color: popup.ink
                font.pixelSize: 13
                textFormat: Text.PlainText
            }

            ColumnLayout {
                id: content
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
                        font.pixelSize: 14
                        font.weight: Font.DemiBold
                    }
                    PopupText {
                        objectName: "summary"
                        text: widget.summary
                        font.pixelSize: 12
                        color: popup.muted
                    }
                }

                LoadingLine {
                    Layout.fillWidth: true
                    running: monitor.loading
                    trackColor: popup.line
                }

                PopupText {
                    Layout.fillWidth: true
                    Layout.margins: 16
                    visible: !widget.results.length || !!monitor.error
                    text: widget.placeholder
                    wrapMode: Text.Wrap
                    font.pixelSize: 12
                    color: monitor.error ? widget.offlineColor : popup.secondary
                }

                Flickable {
                    id: list
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(contentHeight, widget.maxListHeight,
                        Math.max(80, widget.Screen.desktopAvailableHeight - 124))
                    visible: widget.results.length > 0
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
                            model: widget.results

                            delegate: ItemDelegate {
                                id: serverRow
                                required property var modelData
                                required property int index
                                readonly property bool offline: modelData.status === "Offline"
                                readonly property bool hasWarning: widget.warning(modelData)
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
                                Accessible.description: widget.details(modelData)
                                onClicked: Qt.openUrlExternally(modelData.url)

                                HoverHandler {
                                    enabled: serverRow.enabled
                                    cursorShape: Qt.PointingHandCursor
                                }

                                background: Rectangle {
                                    color: serverRow.hovered || serverRow.visualFocus
                                        ? Qt.alpha(popup.ink, 0.06) : "transparent"
                                }

                                Rectangle {
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.leftMargin: 16
                                    anchors.rightMargin: 16
                                    height: 1
                                    visible: serverRow.index > 0
                                    color: popup.line
                                }

                                contentItem: ColumnLayout {
                                    spacing: 3
                                    RowLayout {
                                        Layout.fillWidth: true
                                        PopupText {
                                            Layout.fillWidth: true
                                            text: serverRow.modelData.name
                                            font.weight: Font.DemiBold
                                            elide: Text.ElideRight
                                        }
                                        StatusMark {
                                            ring: serverRow.offline || serverRow.hasWarning
                                            ink: serverRow.offline ? widget.offlineColor
                                                : serverRow.hasWarning ? widget.warningColor : widget.onlineColor
                                        }
                                    }
                                    PopupText {
                                        Layout.fillWidth: true
                                        text: widget.details(serverRow.modelData)
                                        font.pixelSize: 12
                                        color: popup.secondary
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
                    bottomLeftRadius: 7
                    bottomRightRadius: 7
                    color: Qt.alpha("#000000", widget.dark ? 0.15 : 0.03)

                    Rectangle {
                        width: parent.width
                        height: 1
                        color: popup.line
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
                            onClicked: widget.refresh()
                            HoverHandler {
                                enabled: refreshButton.enabled
                                cursorShape: Qt.PointingHandCursor
                            }
                            contentItem: PopupText {
                                text: refreshButton.text
                                color: !refreshButton.enabled ? popup.muted
                                    : refreshButton.hovered || refreshButton.visualFocus ? popup.ink : popup.secondary
                                font.pixelSize: 12
                            }
                            background: Rectangle {
                                radius: 4
                                color: refreshButton.hovered || refreshButton.visualFocus
                                    ? Qt.alpha(popup.ink, 0.08) : "transparent"
                            }
                        }

                        PopupText {
                            objectName: "checked"
                            Layout.fillWidth: true
                            horizontalAlignment: Text.AlignRight
                            text: widget.checked ? qsTr("Checked at %1").arg(widget.checked) : ""
                            color: popup.muted
                            font.pixelSize: 12
                        }
                    }
                }
            }
        }
    }
}
