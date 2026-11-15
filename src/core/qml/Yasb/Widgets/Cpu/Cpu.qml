pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Shapes
import Yasb
import Yasb.Bar
import Yasb.Common
import Yasb.Themes

Item {
    id: cpu

    property int updateInterval: 2000
    property color graphColor: theme.colors.accent
    // Square grid lines behind the graph
    property bool graphGrid: true
    // The glyph in front of the text, drawn in iconFont and the text colour; "" for none
    property string icon: "\ueea1"
    property int iconSize: theme.bar.iconFont.pixelSize
    // Hotkey that opens the popup, such as "alt+shift+c"
    property string keys: ""
    property int popupWidth: 400
    required property BarBase bar
    readonly property Theme theme: bar.theme

    property bool showAlternate: false
    property list<real> history: []

    readonly property bool dark: theme.dark
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
    property int popupOpenDuration: theme.popup.openDuration
    property int popupCloseDuration: theme.popup.closeDuration
    property color popupDividerColor: theme.colors.divider
    property color popupSecondaryTextColor: theme.colors.textSecondary
    property color popupTertiaryTextColor: theme.colors.textTertiary
    property color popupCardColor: theme.colors.card
    property color popupCardBorderColor: theme.colors.cardBorder
    property font popupTitleFont
    popupTitleFont.family: theme.popup.font.family
    popupTitleFont.pixelSize: 16
    popupTitleFont.weight: Font.DemiBold
    // The pin glyph, and each stat's value under its name
    property int popupIconSize: 14
    property font valueFont
    valueFont.family: theme.popup.font.family
    valueFont.pixelSize: 20
    valueFont.weight: Font.Bold
    readonly property string edge: bar.edge

    function spline(points: var): string {
        if (points.length < 2)
            return ""
        let path = `M ${points[0].x} ${points[0].y}`
        const last = points.length - 1
        for (let index = 0; index < last; ++index) {
            const p0 = points[Math.max(0, index - 1)]
            const p1 = points[index]
            const p2 = points[index + 1]
            const p3 = points[Math.min(last, index + 2)]
            const low = Math.min(p1.y, p2.y)
            const high = Math.max(p1.y, p2.y)
            const y1 = Math.max(low, Math.min(p1.y + (p2.y - p0.y) * 0.2, high))
            const y2 = Math.max(low, Math.min(p2.y - (p3.y - p1.y) * 0.2, high))
            path += ` C ${p1.x + (p2.x - p0.x) * 0.2} ${y1} ${p2.x - (p3.x - p1.x) * 0.2} ${y2} ${p2.x} ${p2.y}`
        }
        return path
    }

    function placePopup() {
        const start = mapToGlobal(0, 0)
        let px = edge === "left" ? start.x + width + popupGap
            : edge === "right" ? start.x - popup.width - popupGap : start.x + (width - popup.width) / 2
        let py = edge === "top" ? start.y + height + popupGap
            : edge === "bottom" ? start.y - popup.height - popupGap : start.y + (height - popup.height) / 2
        const screen = cpu.Screen
        px = Math.max(screen.virtualX + 8, Math.min(px, screen.virtualX + screen.width - popup.width - 8))
        py = Math.max(screen.virtualY + 8, Math.min(py, screen.virtualY + screen.desktopAvailableHeight - popup.height - 8))
        popup.x = Math.round(px)
        popup.y = Math.round(py)
    }

    function togglePopup() {
        if (popup.visible)
            popup.close()
        else {
            placePopup()
            popup.open()
        }
    }

    implicitWidth: row.implicitWidth
    implicitHeight: row.implicitHeight

    Component.onDestruction: popup.hide()

    CpuMonitor {
        id: monitor

        updateInterval: cpu.updateInterval
        onDataChanged: cpu.history = [...cpu.history, monitor.data.percent.total].slice(-60)
    }

    Connections {
        target: cpu.Window.window
        function onVisibleChanged() {
            if (!cpu.Window.window?.visible)
                popup.hide()
        }
        function onXChanged() { if (popup.visible && !popup.pinned) cpu.placePopup() }
        function onYChanged() { if (popup.visible && !popup.pinned) cpu.placePopup() }
    }

    Row {
        id: row

        height: parent.height
        spacing: 4

        Text {
            anchors.verticalCenter: parent.verticalCenter
            visible: cpu.icon !== ""
            text: cpu.icon
            color: cpu.textColor
            font.family: cpu.iconFont.family
            font.weight: cpu.iconFont.weight
            font.variableAxes: cpu.iconFont.variableAxes
            font.pixelSize: cpu.iconSize
        }

        Label {
            id: label

            objectName: "label"
            anchors.verticalCenter: parent.verticalCenter
            text: cpu.showAlternate
                ? `CPU: ${monitor.data.percent.total}% | freq: ${monitor.data.freq.current.toFixed(2)} Mhz`
                : `${monitor.data.percent.total.toFixed(0)}%`
            color: cpu.textColor
            font: cpu.font
        }
    }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        cursorShape: Qt.PointingHandCursor
        onClicked: mouse => {
            if (mouse.button === Qt.LeftButton)
                cpu.togglePopup()
            else
                cpu.showAlternate = !cpu.showAlternate
        }
    }

    Hotkey {
        keys: cpu.keys
        onActivated: cpu.togglePopup()
    }

    BackdropPopup {
        id: popup
        property real reveal: 0
        readonly property var stats: {
            const data = monitor.data
            return [
                ["Usage", `${data.percent.total.toFixed(0)}%`],
                ["Frequency", `${data.freq.current.toFixed(0)} MHz`],
                ["Cores (P / L)", `${data.cores.physical} / ${data.cores.total}`],
                ["Max frequency", `${data.freq.max.toFixed(0)} MHz`]
            ]
        }
        objectName: "menu"
        title: "CPU"
        width: cpu.popupWidth
        height: popupContent.implicitHeight
        anchor: cpu
        font: cpu.popupFont
        theme: cpu.theme
        backdropItem: surface
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: cpu.popupOpenDuration; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: cpu.popupCloseDuration; easing.type: Easing.InCubic }
        onVisibleChanged: {
            if (!visible) {
                reveal = 0
                pinned = false
            }
        }

        Rectangle {
            id: surface
            anchors.fill: parent
            radius: cpu.popupRadius
            color: cpu.popupColor
            border.width: 1
            border.color: cpu.popupBorderColor
            opacity: popup.reveal
            scale: 0.85 + popup.reveal * 0.15
            transformOrigin: cpu.edge === "bottom" ? Item.Bottom : Item.Top

            ColumnLayout {
                id: popupContent
                width: parent.width
                spacing: 0

                RowLayout {
                    Layout.fillWidth: true
                    Layout.leftMargin: 16
                    Layout.rightMargin: 10
                    Layout.topMargin: 12
                    Layout.bottomMargin: 10

                    Text {
                        Layout.fillWidth: true
                        text: "CPU usage"
                        font: cpu.popupTitleFont
                        color: cpu.popupTextColor

                        MouseArea {
                            property point grab

                            anchors.fill: parent
                            enabled: popup.pinned
                            cursorShape: popup.pinned ? Qt.SizeAllCursor : Qt.ArrowCursor
                            onPressed: mouse => grab = Qt.point(popup.x - mapToGlobal(mouse.x, mouse.y).x,
                                popup.y - mapToGlobal(mouse.x, mouse.y).y)
                            onPositionChanged: mouse => {
                                const at = mapToGlobal(mouse.x, mouse.y)
                                popup.x = at.x + grab.x
                                popup.y = at.y + grab.y
                            }
                        }
                    }

                    Item {
                        implicitWidth: 28
                        implicitHeight: 28
                        Accessible.role: Accessible.Button
                        Accessible.name: popup.pinned ? "Unpin this window" : "Pin this window"
                        Accessible.onPressAction: popup.pinned = !popup.pinned

                        Text {
                            anchors.centerIn: parent
                            text: popup.pinned ? "\ue77a" : "\ue840"
                            color: cpu.popupTextColor
                            opacity: popup.pinned ? 1 : 0.6
                            font.family: cpu.iconFont.family
                            font.weight: cpu.iconFont.weight
                            font.variableAxes: cpu.iconFont.variableAxes
                            font.pixelSize: cpu.popupIconSize
                        }

                        MouseArea {
                            anchors.fill: parent
                            onClicked: popup.pinned = !popup.pinned
                        }
                    }
                }
                // The header's bottom line
                Rectangle {
                    Layout.fillWidth: true
                    Layout.bottomMargin: 8
                    implicitHeight: 1
                    color: cpu.popupDividerColor
                }

                Text {
                    leftPadding: 14
                    bottomPadding: 4
                    text: "Utilization"
                    color: cpu.popupTertiaryTextColor
                    font: cpu.popupSmallFont
                }

                Item {
                    id: graph

                    readonly property var points: cpu.history.map((value, index) => Qt.point(
                        cpu.history.length > 1 ? index * width / (cpu.history.length - 1) : width,
                        1 + (height - 2) * (1 - Math.max(0, Math.min(value, 100)) / 100)))
                    readonly property string line: cpu.spline(points)
                    readonly property string grid: {
                        if (!cpu.graphGrid || width <= 0 || height <= 0)
                            return ""
                        const lines = [`M 0 0.5 L ${width} 0.5`, `M 0.5 0 L 0.5 ${height}`]
                        for (let y = height - 0.5; y > 0; y -= 16)
                            lines.push(`M 0 ${y} L ${width} ${y}`)
                        for (let x = width - 0.5; x > 0; x -= 16)
                            lines.push(`M ${x} 0 L ${x} ${height}`)
                        return lines.join(" ")
                    }

                    Layout.fillWidth: true
                    Layout.preferredHeight: 64

                    Shape {
                        anchors.fill: parent
                        visible: graph.grid !== ""

                        ShapePath {
                            fillColor: "transparent"
                            strokeColor: Qt.alpha(cpu.popupTextColor, 0.05)
                            strokeWidth: 1

                            PathSvg {
                                path: graph.grid
                            }
                        }
                    }

                    Shape {
                        anchors.fill: parent
                        preferredRendererType: Shape.CurveRenderer

                        ShapePath {
                            strokeWidth: -1
                            fillGradient: LinearGradient {
                                y2: graph.height

                                GradientStop {
                                    position: 0
                                    color: Qt.alpha(cpu.graphColor, 100 / 255)
                                }

                                GradientStop {
                                    position: 1
                                    color: Qt.alpha(cpu.graphColor, 10 / 255)
                                }
                            }

                            PathSvg {
                                path: graph.line ? `M 0 ${graph.height} L ${graph.line.slice(2)} L ${graph.width} ${graph.height} Z` : ""
                            }
                        }

                        ShapePath {
                            fillColor: "transparent"
                            strokeColor: cpu.graphColor
                            strokeWidth: 2
                            capStyle: ShapePath.FlatCap
                            joinStyle: ShapePath.BevelJoin

                            PathSvg {
                                path: graph.line
                            }
                        }
                    }
                }

                GridLayout {
                    Layout.fillWidth: true
                    Layout.margins: 24
                    columns: 2
                    columnSpacing: 16
                    rowSpacing: 16
                    uniformCellWidths: true

                    Repeater {
                        model: popup.stats.length

                        delegate: Rectangle {
                            id: stat

                            required property int index
                            readonly property int alignment: index % 2 ? Text.AlignRight : Text.AlignLeft

                            Layout.fillWidth: true
                            implicitHeight: values.implicitHeight + 16
                            radius: 8
                            color: cpu.popupCardColor
                            border.width: 1
                            border.color: cpu.popupCardBorderColor

                            ColumnLayout {
                                id: values

                                x: 12
                                y: 8
                                width: parent.width - 24
                                spacing: 0

                                Text {
                                    Layout.fillWidth: true
                                    leftPadding: 4
                                    rightPadding: 4
                                    topPadding: 6
                                    bottomPadding: 2
                                    horizontalAlignment: stat.alignment
                                    text: popup.stats[stat.index][0]
                                    color: cpu.popupSecondaryTextColor
                                    font: cpu.popupFont
                                }

                                Text {
                                    Layout.fillWidth: true
                                    leftPadding: 4
                                    rightPadding: 4
                                    bottomPadding: 12
                                    horizontalAlignment: stat.alignment
                                    text: popup.stats[stat.index][1]
                                    color: cpu.popupTextColor
                                    font: cpu.valueFont
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
