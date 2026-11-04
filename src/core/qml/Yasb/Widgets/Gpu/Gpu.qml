import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Shapes
import Yasb
import Yasb.Common

Item {
    id: gpu

    property int updateInterval: 2000
    property int gpuIndex: 0
    property color graphColor: "#0f6bff"
    // Square grid lines behind the graph
    property bool graphGrid: true
    property color temperatureColor: "#ff6b35"
    // The glyph in front of the text, drawn in iconFont and the text colour; "" for none
    property string icon: "\uf211"
    property int iconSize: 16
    property Item bar: null

    property bool showAlternate: false
    property list<real> history: []
    property list<real> temperatures: []

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
    // Glyphs take the family and weight of the bar's icon font unless the widget file sets them
    property font iconFont
    iconFont.family: bar?.iconFont?.family ?? "Segoe Fluent Icons"
    iconFont.weight: bar?.iconFont?.weight ?? Font.Normal
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

    function memoryUsage(used: real, total: real): string {
        const units = ["Bytes", "KB", "MB", "GB", "TB", "PB"]
        let unit = 1
        let index = 0
        while (index < units.length - 1 && total >= unit * 1024) {
            unit *= 1024
            ++index
        }
        const digits = index === 0 ? 0 : 1
        return `${(used / unit).toFixed(digits)} / ${(total / unit).toFixed(digits)} ${units[index]}`
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
        const screen = gpu.Screen
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

    implicitWidth: monitor.available ? row.implicitWidth : 0
    implicitHeight: monitor.available ? row.implicitHeight : 0
    visible: monitor.available

    Component.onDestruction: popup.hide()

    GpuMonitor {
        id: monitor

        gpuIndex: gpu.gpuIndex
        updateInterval: gpu.updateInterval
        onDataChanged: {
            gpu.history = [...gpu.history, monitor.data.utilization].slice(-60)
            gpu.temperatures = [...gpu.temperatures, monitor.data.temp].slice(-60)
        }
    }

    Connections {
        target: gpu.Window.window
        function onVisibleChanged() {
            if (!gpu.Window.window?.visible)
                popup.hide()
        }
        function onXChanged() { if (popup.visible && !popup.pinned) gpu.placePopup() }
        function onYChanged() { if (popup.visible && !popup.pinned) gpu.placePopup() }
    }

    Row {
        id: row

        height: parent.height
        spacing: 4

        Text {
            anchors.verticalCenter: parent.verticalCenter
            visible: gpu.icon !== ""
            text: gpu.icon
            color: gpu.textColor
            font.family: gpu.iconFont.family
            font.weight: gpu.iconFont.weight
            font.pixelSize: gpu.iconSize
        }

        Text {
            id: label

            objectName: "label"
            anchors.verticalCenter: parent.verticalCenter
            text: gpu.showAlternate
                ? `${gpu.size(monitor.data.mem_used, "")}/${gpu.size(monitor.data.mem_total, "")}`
                : `${monitor.data.utilization.toFixed(0)}%`
            color: gpu.textColor
            font: gpu.font
        }
    }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        cursorShape: Qt.PointingHandCursor
        onClicked: mouse => {
            if (mouse.button === Qt.LeftButton)
                gpu.togglePopup()
            else
                gpu.showAlternate = !gpu.showAlternate
        }
    }

    BackdropPopup {
        id: popup
        property real reveal: 0
        readonly property color ink: gpu.dark ? "#ffffff" : "#000000"
        readonly property var stats: {
            const data = monitor.data
            const temperature = data.temp > 0
            const power = data.power_draw > 0
            const fan = data.fan_speed > 0 || temperature
            const shared = data.mem_shared_total > 0
            const cells = [
                ["Usage", `${data.utilization.toFixed(0)}%`],
                ["Memory", gpu.memoryUsage(data.mem_used, data.mem_total)]
            ]
            if (temperature || power)
                cells.push(temperature ? ["Temperature", `${data.temp}°C`] : null,
                    power ? ["Power draw", `${data.power_draw.toFixed(1)} W`] : null)
            if (fan || shared)
                cells.push(fan ? ["Fan speed", `${data.fan_speed}%`] : null,
                    shared ? ["Shared memory", gpu.memoryUsage(data.mem_shared_used, data.mem_shared_total)] : null)
            return cells
        }
        objectName: "menu"
        title: "GPU"
        width: 416
        height: content.implicitHeight + 16
        anchor: gpu
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
            color: gpu.dark ? Qt.alpha("#202020", 0.85) : Qt.alpha("#F3F3F3", 0.85)
            border.width: 1
            border.color: gpu.dark ? Qt.alpha("#3A3A3A", 1) : Qt.alpha("#D9D9D9", 1)
            opacity: popup.reveal
            scale: 0.85 + popup.reveal * 0.15
            transformOrigin: gpu.edge === "bottom" ? Item.Bottom : Item.Top

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
                        text: "<b>GPU</b> Usage"
                        textFormat: Text.StyledText
                        color: popup.ink
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

                        Text {
                            anchors.centerIn: parent
                            text: popup.pinned ? "\ue77a" : "\ue840"
                            color: popup.ink
                            opacity: popup.pinned ? 1 : 0.6
                            font.family: gpu.iconFont.family
                            font.weight: gpu.iconFont.weight
                            font.pixelSize: 14
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
                    font.pixelSize: 12
                }

                Item {
                    id: graph

                    readonly property var points: gpu.history.map((value, index) => Qt.point(
                        gpu.history.length > 1 ? index * width / (gpu.history.length - 1) : width,
                        1 + (height - 2) * (1 - Math.max(0, Math.min(value, 100)) / 100)))
                    readonly property string line: gpu.spline(points)
                    readonly property string grid: {
                        if (!gpu.graphGrid || width <= 0 || height <= 0)
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
                                    color: Qt.alpha(gpu.graphColor, 100 / 255)
                                }

                                GradientStop {
                                    position: 1
                                    color: Qt.alpha(gpu.graphColor, 10 / 255)
                                }
                            }

                            PathSvg {
                                path: graph.line ? `M 0 ${graph.height} L ${graph.line.slice(2)} L ${graph.width} ${graph.height} Z` : ""
                            }
                        }

                        ShapePath {
                            fillColor: "transparent"
                            strokeColor: gpu.graphColor
                            strokeWidth: 2
                            capStyle: ShapePath.FlatCap
                            joinStyle: ShapePath.BevelJoin

                            PathSvg {
                                path: graph.line
                            }
                        }
                    }
                }

                Text {
                    visible: monitor.data.temp > 0
                    topPadding: 12
                    leftPadding: 14
                    bottomPadding: 4
                    text: "Temperature"
                    color: Qt.alpha(popup.ink, 0.5)
                    font.pixelSize: 12
                }

                Item {
                    id: temperatureGraph

                    readonly property var points: gpu.temperatures.map((value, index) => Qt.point(
                        gpu.temperatures.length > 1 ? index * width / (gpu.temperatures.length - 1) : width,
                        1 + (height - 2) * (1 - Math.max(0, Math.min(value, 100)) / 100)))
                    readonly property string line: gpu.spline(points)
                    readonly property string grid: {
                        if (!gpu.graphGrid || width <= 0 || height <= 0)
                            return ""
                        const lines = [`M 0 0.5 L ${width} 0.5`, `M 0.5 0 L 0.5 ${height}`]
                        for (let y = height - 0.5; y > 0; y -= 16)
                            lines.push(`M 0 ${y} L ${width} ${y}`)
                        for (let x = width - 0.5; x > 0; x -= 16)
                            lines.push(`M ${x} 0 L ${x} ${height}`)
                        return lines.join(" ")
                    }

                    visible: monitor.data.temp > 0
                    Layout.fillWidth: true
                    Layout.preferredHeight: 64

                    Shape {
                        anchors.fill: parent
                        visible: temperatureGraph.grid !== ""

                        ShapePath {
                            fillColor: "transparent"
                            strokeColor: Qt.alpha(popup.ink, 0.05)
                            strokeWidth: 1

                            PathSvg {
                                path: temperatureGraph.grid
                            }
                        }
                    }

                    Shape {
                        anchors.fill: parent
                        preferredRendererType: Shape.CurveRenderer

                        ShapePath {
                            strokeWidth: -1
                            fillGradient: LinearGradient {
                                y2: temperatureGraph.height

                                GradientStop {
                                    position: 0
                                    color: Qt.alpha(gpu.temperatureColor, 100 / 255)
                                }

                                GradientStop {
                                    position: 1
                                    color: Qt.alpha(gpu.temperatureColor, 10 / 255)
                                }
                            }

                            PathSvg {
                                path: temperatureGraph.line ? `M 0 ${temperatureGraph.height} L ${temperatureGraph.line.slice(2)} L ${temperatureGraph.width} ${temperatureGraph.height} Z` : ""
                            }
                        }

                        ShapePath {
                            fillColor: "transparent"
                            strokeColor: gpu.temperatureColor
                            strokeWidth: 2
                            capStyle: ShapePath.FlatCap
                            joinStyle: ShapePath.BevelJoin

                            PathSvg {
                                path: temperatureGraph.line
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
                            readonly property var cell: popup.stats[index] ?? null

                            Layout.fillWidth: true
                            implicitHeight: values.implicitHeight + 16
                            opacity: cell ? 1 : 0
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
                                    text: stat.cell ? stat.cell[0] : ""
                                    color: Qt.alpha(popup.ink, 0.65)
                                    font.pixelSize: 13
                                }

                                Text {
                                    Layout.fillWidth: true
                                    leftPadding: 4
                                    rightPadding: 4
                                    bottomPadding: 12
                                    horizontalAlignment: stat.alignment
                                    text: stat.cell ? stat.cell[1] : ""
                                    elide: Text.ElideRight
                                    color: popup.ink
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
