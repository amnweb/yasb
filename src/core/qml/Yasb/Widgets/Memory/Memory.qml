import QtQuick
import QtQuick.Controls
import QtQuick.Controls.impl
import QtQuick.Layouts
import QtQuick.Shapes
import Yasb
import Yasb.Common

Item {
    id: memory

    property int updateInterval: 5000
    property color graphColor: "#0f6bff"
    // Square grid lines behind the graph
    property bool graphGrid: true
    // The SVG in front of the text, drawn in the text colour; "" for none
    property url icon: Qt.resolvedUrl("icons/memory.svg")
    property int iconSize: 16
    property Item bar: null

    property bool showAlternate: false
    property list<real> history: []

    readonly property bool dark: Qt.styleHints.colorScheme === Qt.ColorScheme.Dark
    // Text on the bar takes the bar's colour and font, each part unless the widget file sets it
    property color textColor: bar?.textColor ?? (dark ? "#ffffff" : "#000000")
    property font font
    font.family: bar?.font.family ?? Qt.application.font.family
    font.pixelSize: bar?.font.pixelSize ?? 13
    font.weight: bar?.font.weight ?? Font.Normal
    font.italic: bar?.font.italic ?? false
    font.letterSpacing: bar?.font.letterSpacing ?? 0
    font.capitalization: bar?.font.capitalization ?? Font.MixedCase
    font.variableAxes: bar?.font.variableAxes ?? ({})
    readonly property string edge: bar?.edge ?? "top"

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

    function popupSize(bytes: real): string {
        if (Math.abs(bytes) === 1)
            return "1 Byte"
        if (Math.abs(bytes) < 1024)
            return `${Math.trunc(bytes)} Bytes`
        const units = ["KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]
        let unit = 1024
        let index = 0
        while (index < units.length - 1 && Math.abs(bytes) >= unit * 1024) {
            unit *= 1024
            ++index
        }
        return `${(bytes / unit).toFixed(1)} ${units[index]}`
    }

    function size(bytes: real, suffix: string): string {
        if (Math.abs(bytes) < 1024)
            return `${Math.trunc(bytes)}B`
        const units = "KMGTPEZY"
        let unit = 1024
        let index = 0
        while (index < units.length - 1 && Math.abs(bytes) >= unit * 1024) {
            unit *= 1024
            ++index
        }
        return `${(bytes / unit).toFixed(1)}${units[index]}${suffix}`
    }

    function placePopup() {
        const start = mapToGlobal(0, 0)
        let px = edge === "left" ? start.x + width + 6
            : edge === "right" ? start.x - popup.width - 6 : start.x + (width - popup.width) / 2
        let py = edge === "top" ? start.y + height + 6
            : edge === "bottom" ? start.y - popup.height - 6 : start.y + (height - popup.height) / 2
        const screen = memory.Screen
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

    MemoryMonitor {
        id: monitor

        updateInterval: memory.updateInterval
        onDataChanged: memory.history = [...memory.history, monitor.data.virtual.percent].slice(-60)
    }

    Connections {
        target: memory.Window.window
        function onVisibleChanged() {
            if (!memory.Window.window?.visible)
                popup.hide()
        }
        function onXChanged() { if (popup.visible && !popup.pinned) memory.placePopup() }
        function onYChanged() { if (popup.visible && !popup.pinned) memory.placePopup() }
    }

    component SvgIcon: IconImage {
        sourceSize: Qt.size(width, height)
    }

    Row {
        id: row

        height: parent.height
        spacing: 4

        SvgIcon {
            y: Math.round((parent.height - height) / 2)
            width: memory.iconSize
            height: memory.iconSize
            visible: memory.icon.toString() !== ""
            source: memory.icon
            color: memory.textColor
        }

        Text {
            id: label

            objectName: "label"
            anchors.verticalCenter: parent.verticalCenter
            text: memory.showAlternate
                ? `${memory.size(monitor.data.virtual.free, "")}/${memory.size(monitor.data.virtual.total, "")}`
                : `${monitor.data.virtual.percent.toFixed(0)}%`
            color: memory.textColor
            font: memory.font
        }
    }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        cursorShape: Qt.PointingHandCursor
        onClicked: mouse => {
            if (mouse.button === Qt.LeftButton)
                memory.togglePopup()
            else
                memory.showAlternate = !memory.showAlternate
        }
    }

    BackdropPopup {
        id: popup
        property real reveal: 0
        readonly property color ink: memory.dark ? "#ffffff" : "#000000"
        readonly property var stats: {
            const data = monitor.data
            return [
                ["In use", memory.popupSize(data.virtual.used)],
                ["All memory", memory.popupSize(data.virtual.total)],
                ["Cached", memory.popupSize(data.cached_bytes)],
                ["Available", memory.popupSize(data.virtual.available)],
                ["Swap used", memory.popupSize(data.swap.used)],
                ["Utilization", `${data.virtual.percent.toFixed(0)}%`]
            ]
        }
        objectName: "menu"
        title: "Memory"
        width: 416
        height: content.implicitHeight + 16
        anchor: memory
        backdropItem: surface
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: 180; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: 140; easing.type: Easing.InCubic }
        onVisibleChanged: {
            if (!visible) {
                reveal = 0
                pinned = false
            }
        }

        Rectangle {
            id: surface
            anchors.fill: parent
            anchors.margins: 8
            radius: 8
            color: memory.dark ? Qt.alpha("#202020", 0.85) : Qt.alpha("#F3F3F3", 0.85)
            border.width: 1
            border.color: memory.dark ? Qt.alpha("#3A3A3A", 1) : Qt.alpha("#D9D9D9", 1)
            opacity: popup.reveal
            scale: 0.85 + popup.reveal * 0.15
            transformOrigin: memory.edge === "bottom" ? Item.Bottom : Item.Top

            ColumnLayout {
                id: content
                width: parent.width
                spacing: 0

                RowLayout {
                    Layout.fillWidth: true
                    Layout.leftMargin: 16
                    Layout.rightMargin: 10
                    Layout.topMargin: 12
                    Layout.bottomMargin: 12

                    Text {
                        Layout.fillWidth: true
                        text: "<b>Memory</b> Usage"
                        textFormat: Text.StyledText
                        color: popup.ink
                        font.family: "Segoe UI"
                        font.pixelSize: 16

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

                        SvgIcon {
                            anchors.centerIn: parent
                            width: 14
                            height: 14
                            source: Qt.resolvedUrl(popup.pinned ? "icons/pinned.svg" : "icons/pin.svg")
                            color: popup.ink
                            opacity: popup.pinned ? 1 : 0.6
                        }

                        MouseArea {
                            anchors.fill: parent
                            onClicked: popup.pinned = !popup.pinned
                        }
                    }
                }

                Text {
                    leftPadding: 14
                    bottomPadding: 4
                    text: "Utilization"
                    color: Qt.alpha(popup.ink, 0.5)
                    font.family: "Segoe UI"
                    font.pixelSize: 12
                }

                Item {
                    id: graph

                    readonly property var points: memory.history.map((value, index) => Qt.point(
                        memory.history.length > 1 ? index * width / (memory.history.length - 1) : width,
                        1 + (height - 2) * (1 - Math.max(0, Math.min(value, 100)) / 100)))
                    readonly property string line: memory.spline(points)
                    readonly property string grid: {
                        if (!memory.graphGrid || width <= 0 || height <= 0)
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
                            strokeColor: Qt.alpha(popup.ink, 0.05)
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
                                    color: Qt.alpha(memory.graphColor, 100 / 255)
                                }

                                GradientStop {
                                    position: 1
                                    color: Qt.alpha(memory.graphColor, 10 / 255)
                                }
                            }

                            PathSvg {
                                path: graph.line ? `M 0 ${graph.height} L ${graph.line.slice(2)} L ${graph.width} ${graph.height} Z` : ""
                            }
                        }

                        ShapePath {
                            fillColor: "transparent"
                            strokeColor: memory.graphColor
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
                            color: Qt.alpha(popup.ink, 0.03)
                            border.width: 1
                            border.color: Qt.alpha(popup.ink, 0.04)

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
                                    color: Qt.alpha(popup.ink, 0.65)
                                    font.family: "Segoe UI"
                                    font.pixelSize: 13
                                }

                                Text {
                                    Layout.fillWidth: true
                                    leftPadding: 4
                                    rightPadding: 4
                                    bottomPadding: 12
                                    horizontalAlignment: stat.alignment
                                    text: popup.stats[stat.index][1]
                                    color: popup.ink
                                    font.family: "Segoe UI"
                                    font.pixelSize: 20
                                    font.weight: Font.Bold
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
