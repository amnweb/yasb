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
    id: gpu

    component PopupIcons: QtObject {
        property string pin
        property string unpin
    }

    component Settings: QtObject {
        required property Theme theme

        // Label placeholders: {info[utilization]} in %, sizes such as 8.0G: {info[mem_used]} {info[mem_free]}
        // {info[mem_total]} {info[mem_shared_used]} {info[mem_shared_total]}, {info[temp]} in °C, {info[fan_speed]} in %,
        // {info[power_draw]} in W, {info[name]} and {info[index]}. :.0f after a name sets the decimals, as
        // {info[utilization]:.0f}. Right-click shows the alternate label.
        property string label: "{info[utilization]:.0f}%"
        property string alternateLabel: "{info[mem_used]}/{info[mem_total]}"
        property int updateInterval: 2000
        property int gpuIndex: 0
        property color graphColor: theme.colors.accent
        // Square grid lines behind the graph
        property bool graphGrid: true
        property color temperatureColor: "#ff6b35"
        // The glyph in front of the text, drawn in iconFont and the text colour; "" for none
        property string icon: "\uf211"
        property int iconSize: theme.bar.iconFont.pixelSize
        property int popupWidth: 400
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
        popupTitleFont.weight: 600
        readonly property PopupIcons popupIcons: PopupIcons {
            pin: "\ue840"
            unpin: "\ue77a"
        }
        property font popupIconFont
        popupIconFont.family: theme.popup.iconFont.family
        popupIconFont.weight: theme.popup.iconFont.weight
        popupIconFont.variableAxes: theme.popup.iconFont.variableAxes
        // The pin glyph, and each stat's value under its name
        property int popupIconSize: 14
        property font valueFont
        valueFont.family: theme.popup.font.family
        valueFont.pixelSize: 20
        valueFont.weight: 700
    }

    required property BarBase bar
    readonly property Theme theme: bar.theme
    readonly property Settings settings: Settings {
        theme: gpu.theme
    }

    property bool showAlternate: false
    readonly property string text: format(showAlternate ? settings.alternateLabel : settings.label)
    property list<real> history: []
    property list<real> temperatures: []

    readonly property bool dark: theme.dark
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

    function size(bytes: real, decimals: int): string {
        if (Math.abs(bytes) < 1024)
            return `${Math.trunc(bytes)}B`
        const units = "KMGTPEZY"
        let unit = 1024
        let index = 0
        while (index < units.length - 1 && Math.abs(bytes) >= unit * 1024) {
            unit *= 1024
            ++index
        }
        return `${(bytes / unit).toFixed(decimals)}${units[index]}`
    }

    function format(template: string): string {
        const data = monitor.data
        const sizes = ["mem_used", "mem_free", "mem_total", "mem_shared_used", "mem_shared_total"]
        return template.replace(/\{info\[(\w+)\](?::\.(\d+)f)?\}/g, (match, key, decimals) => {
            if (!Object.prototype.hasOwnProperty.call(data, key))
                return match
            const value = data[key]
            if (sizes.includes(key))
                return size(value, decimals === undefined ? 1 : Number(decimals))
            if (typeof value === "number" && decimals !== undefined)
                return value.toFixed(Number(decimals))
            return String(value)
        })
    }

    function placePopup() {
        const start = mapToGlobal(0, 0)
        let px = edge === "left" ? start.x + width + settings.popupGap
            : edge === "right" ? start.x - popup.width - settings.popupGap : start.x + (width - popup.width) / 2
        let py = edge === "top" ? start.y + height + settings.popupGap
            : edge === "bottom" ? start.y - popup.height - settings.popupGap : start.y + (height - popup.height) / 2
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

        gpuIndex: gpu.settings.gpuIndex
        updateInterval: gpu.settings.updateInterval
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

    // Keep the popup anchored when its height changes
    Connections {
        target: popup
        function onHeightChanged() { if (popup.visible && !popup.pinned) gpu.placePopup() }
    }

    Row {
        id: row

        height: parent.height
        spacing: 4

        Text {
            anchors.verticalCenter: parent.verticalCenter
            visible: gpu.settings.icon !== ""
            text: gpu.settings.icon
            color: gpu.settings.textColor
            font.family: gpu.settings.iconFont.family
            font.weight: gpu.settings.iconFont.weight
            font.variableAxes: gpu.settings.iconFont.variableAxes
            font.pixelSize: gpu.settings.iconSize
        }

        Label {
            objectName: "label"
            anchors.verticalCenter: parent.verticalCenter
            visible: text !== ""
            text: gpu.text
            textFormat: Text.PlainText
            color: gpu.settings.textColor
            font: gpu.settings.font
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
        width: gpu.settings.popupWidth
        height: popupContent.implicitHeight
        anchor: gpu
        font: gpu.settings.popupFont
        theme: gpu.theme
        backdropItem: surface
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: gpu.settings.popupOpenDuration; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: gpu.settings.popupCloseDuration; easing.type: Easing.InCubic }
        onVisibleChanged: {
            if (!visible) {
                reveal = 0
                pinned = false
            }
        }

        Rectangle {
            id: surface
            anchors.fill: parent
            radius: gpu.settings.popupRadius
            color: gpu.settings.popupColor
            border.width: 1
            border.color: gpu.settings.popupBorderColor
            opacity: popup.reveal
            scale: 0.85 + popup.reveal * 0.15
            transformOrigin: gpu.edge === "bottom" ? Item.Bottom : Item.Top

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
                        text: "GPU usage"
                        font: gpu.settings.popupTitleFont
                        color: gpu.settings.popupTextColor

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
                            text: popup.pinned ? gpu.settings.popupIcons.unpin : gpu.settings.popupIcons.pin
                            color: gpu.settings.popupTextColor
                            opacity: popup.pinned ? 1 : 0.6
                            font.family: gpu.settings.popupIconFont.family
                            font.weight: gpu.settings.popupIconFont.weight
                            font.variableAxes: gpu.settings.popupIconFont.variableAxes
                            font.pixelSize: gpu.settings.popupIconSize
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
                    color: gpu.settings.popupDividerColor
                }

                Text {
                    leftPadding: 14
                    bottomPadding: 4
                    text: "Utilization"
                    color: gpu.settings.popupTertiaryTextColor
                    font: gpu.settings.popupSmallFont
                }

                Item {
                    id: graph

                    readonly property var points: gpu.history.map((value, index) => Qt.point(
                        gpu.history.length > 1 ? index * width / (gpu.history.length - 1) : width,
                        1 + (height - 2) * (1 - Math.max(0, Math.min(value, 100)) / 100)))
                    readonly property string line: gpu.spline(points)
                    readonly property string grid: {
                        if (!gpu.settings.graphGrid || width <= 0 || height <= 0)
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
                            strokeColor: Qt.alpha(gpu.settings.popupTextColor, 0.05)
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
                                    color: Qt.alpha(gpu.settings.graphColor, 100 / 255)
                                }

                                GradientStop {
                                    position: 1
                                    color: Qt.alpha(gpu.settings.graphColor, 10 / 255)
                                }
                            }

                            PathSvg {
                                path: graph.line ? `M 0 ${graph.height} L ${graph.line.slice(2)} L ${graph.width} ${graph.height} Z` : ""
                            }
                        }

                        ShapePath {
                            fillColor: "transparent"
                            strokeColor: gpu.settings.graphColor
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
                    color: gpu.settings.popupTertiaryTextColor
                    font: gpu.settings.popupSmallFont
                }

                Item {
                    id: temperatureGraph

                    readonly property var points: gpu.temperatures.map((value, index) => Qt.point(
                        gpu.temperatures.length > 1 ? index * width / (gpu.temperatures.length - 1) : width,
                        1 + (height - 2) * (1 - Math.max(0, Math.min(value, 100)) / 100)))
                    readonly property string line: gpu.spline(points)
                    readonly property string grid: {
                        if (!gpu.settings.graphGrid || width <= 0 || height <= 0)
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
                            strokeColor: Qt.alpha(gpu.settings.popupTextColor, 0.05)
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
                                    color: Qt.alpha(gpu.settings.temperatureColor, 100 / 255)
                                }

                                GradientStop {
                                    position: 1
                                    color: Qt.alpha(gpu.settings.temperatureColor, 10 / 255)
                                }
                            }

                            PathSvg {
                                path: temperatureGraph.line ? `M 0 ${temperatureGraph.height} L ${temperatureGraph.line.slice(2)} L ${temperatureGraph.width} ${temperatureGraph.height} Z` : ""
                            }
                        }

                        ShapePath {
                            fillColor: "transparent"
                            strokeColor: gpu.settings.temperatureColor
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
                            color: gpu.settings.popupCardColor
                            border.width: 1
                            border.color: gpu.settings.popupCardBorderColor

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
                                    color: gpu.settings.popupSecondaryTextColor
                                    font: gpu.settings.popupFont
                                }

                                Text {
                                    Layout.fillWidth: true
                                    leftPadding: 4
                                    rightPadding: 4
                                    bottomPadding: 12
                                    horizontalAlignment: stat.alignment
                                    text: stat.cell ? stat.cell[1] : ""
                                    elide: Text.ElideRight
                                    color: gpu.settings.popupTextColor
                                    font: gpu.settings.valueFont
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
