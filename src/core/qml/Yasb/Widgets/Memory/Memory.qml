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
    id: memory

    // Label placeholders: {virtual_mem_percent} and {swap_mem_percent} in %; sizes such as 8.0G: {virtual_mem_used}
    // {virtual_mem_free} (the same as {virtual_mem_avail}) {virtual_mem_total} {virtual_mem_cached} {swap_mem_used}
    // {swap_mem_free} {swap_mem_total}, and {virtual_mem_outof} for used / total. :.0f after a name sets the decimals,
    // as {virtual_mem_percent:.0f}. Right-click shows the alternate label.
    property string label: "{virtual_mem_percent:.0f}%"
    property string alternateLabel: "{virtual_mem_free}/{virtual_mem_total}"
    property int updateInterval: 5000
    property color graphColor: theme.colors.accent
    // Square grid lines behind the graph
    property bool graphGrid: true
    // The glyph in front of the text, drawn in iconFont and the text colour; "" for none
    property string icon: "\ueea0"
    property int iconSize: theme.bar.iconFont.pixelSize
    property int popupWidth: 400
    required property BarBase bar
    readonly property Theme theme: bar.theme

    property bool showAlternate: false
    readonly property string text: format(showAlternate ? alternateLabel : label)
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
        const sizes = {
            virtual_mem_used: data.virtual.used,
            virtual_mem_free: data.virtual.free,
            virtual_mem_avail: data.virtual.available,
            virtual_mem_total: data.virtual.total,
            virtual_mem_cached: data.cached_bytes,
            swap_mem_used: data.swap.used,
            swap_mem_free: data.swap.free,
            swap_mem_total: data.swap.total
        }
        const percents = { virtual_mem_percent: data.virtual.percent, swap_mem_percent: data.swap.percent }
        return template.replace(/\{((?:virtual|swap)_mem_\w+)(?::\.(\d+)f)?\}/g, (match, name, decimals) => {
            const places = decimals === undefined ? 1 : Number(decimals)
            if (sizes[name] !== undefined)
                return size(sizes[name], places)
            if (percents[name] !== undefined)
                return decimals === undefined ? String(percents[name]) : percents[name].toFixed(places)
            if (name === "virtual_mem_outof")
                return `${size(data.virtual.used, places)} / ${size(data.virtual.total, places)}`
            return match
        })
    }

    function placePopup() {
        const start = mapToGlobal(0, 0)
        let px = edge === "left" ? start.x + width + popupGap
            : edge === "right" ? start.x - popup.width - popupGap : start.x + (width - popup.width) / 2
        let py = edge === "top" ? start.y + height + popupGap
            : edge === "bottom" ? start.y - popup.height - popupGap : start.y + (height - popup.height) / 2
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

    Row {
        id: row

        height: parent.height
        spacing: 4

        Text {
            anchors.verticalCenter: parent.verticalCenter
            visible: memory.icon !== ""
            text: memory.icon
            color: memory.textColor
            font.family: memory.iconFont.family
            font.weight: memory.iconFont.weight
            font.variableAxes: memory.iconFont.variableAxes
            font.pixelSize: memory.iconSize
        }

        Label {
            objectName: "label"
            anchors.verticalCenter: parent.verticalCenter
            visible: text !== ""
            text: memory.text
            textFormat: Text.PlainText
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
        width: memory.popupWidth
        height: popupContent.implicitHeight
        anchor: memory
        font: memory.popupFont
        theme: memory.theme
        backdropItem: surface
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: memory.popupOpenDuration; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: memory.popupCloseDuration; easing.type: Easing.InCubic }
        onVisibleChanged: {
            if (!visible) {
                reveal = 0
                pinned = false
            }
        }

        Rectangle {
            id: surface
            anchors.fill: parent
            radius: memory.popupRadius
            color: memory.popupColor
            border.width: 1
            border.color: memory.popupBorderColor
            opacity: popup.reveal
            scale: 0.85 + popup.reveal * 0.15
            transformOrigin: memory.edge === "bottom" ? Item.Bottom : Item.Top

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
                        text: "Memory usage"
                        font: memory.popupTitleFont
                        color: memory.popupTextColor

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
                            color: memory.popupTextColor
                            opacity: popup.pinned ? 1 : 0.6
                            font.family: memory.iconFont.family
                            font.weight: memory.iconFont.weight
                            font.variableAxes: memory.iconFont.variableAxes
                            font.pixelSize: memory.popupIconSize
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
                    color: memory.popupDividerColor
                }

                Text {
                    leftPadding: 14
                    bottomPadding: 4
                    text: "Utilization"
                    color: memory.popupTertiaryTextColor
                    font: memory.popupSmallFont
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
                            strokeColor: Qt.alpha(memory.popupTextColor, 0.05)
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
                            color: memory.popupCardColor
                            border.width: 1
                            border.color: memory.popupCardBorderColor

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
                                    color: memory.popupSecondaryTextColor
                                    font: memory.popupFont
                                }

                                Text {
                                    Layout.fillWidth: true
                                    leftPadding: 4
                                    rightPadding: 4
                                    bottomPadding: 12
                                    horizontalAlignment: stat.alignment
                                    text: popup.stats[stat.index][1]
                                    color: memory.popupTextColor
                                    font: memory.valueFont
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
