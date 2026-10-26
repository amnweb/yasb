import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Shapes
import Yasb

Item {
    id: memory

    property int updateInterval: 5000
    property Item bar: null

    property bool showAlternate: false
    property list<real> history: []

    readonly property bool dark: Qt.styleHints.colorScheme === Qt.ColorScheme.Dark
    readonly property color textColor: bar ? bar.textColor : dark ? "white" : "black"
    readonly property string barEdge: bar?.edge ?? "top"

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

    implicitWidth: label.implicitWidth
    implicitHeight: label.implicitHeight

    MemoryMonitor {
        id: monitor

        updateInterval: memory.updateInterval
        onDataChanged: memory.history = [...memory.history, monitor.data.virtual.percent].slice(-60)
    }

    Text {
        id: label

        objectName: "label"
        anchors.verticalCenter: parent.verticalCenter
        text: memory.showAlternate
            ? ` VIRT: ${monitor.data.virtual.percent}% SWAP: ${monitor.data.swap.percent}%`
            : ` ${memory.size(monitor.data.virtual.free, "")}/${memory.size(monitor.data.virtual.total, "")}`
        color: memory.textColor
        font.family: memory.bar ? memory.bar.font.family : Qt.application.font.family
        font.pixelSize: memory.bar ? memory.bar.font.pixelSize : 13
    }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: mouse => {
            if (mouse.button === Qt.LeftButton)
                memory.showAlternate = !memory.showAlternate
            else
                menu.visible ? menu.close() : menu.open()
        }
    }

    Popup {
        id: menu

        readonly property color textColor: memory.dark ? "white" : "black"
        readonly property var stats: {
            const data = monitor.data
            return [
                ["In use", memory.size(data.virtual.used, "B")],
                ["All memory", memory.size(data.virtual.total, "B")],
                ["Cached", memory.size(data.cached_bytes, "B")],
                ["Available", memory.size(data.virtual.available, "B")],
                ["Swap used", memory.size(data.swap.used, "B")],
                ["Utilization", `${data.virtual.percent.toFixed(0)}%`]
            ]
        }

        objectName: "menu"
        popupType: Popup.Window
        padding: 12
        x: memory.barEdge === "left" ? memory.width + 8
            : memory.barEdge === "right" ? -width - 8
            : Math.round((memory.width - width) / 2)
        y: memory.barEdge === "top" ? memory.height + 8
            : memory.barEdge === "bottom" ? -height - 8
            : Math.round((memory.height - height) / 2)

        background: Rectangle {
            color: memory.dark ? "#f21e1e1e" : "#f2f3f3f3"
            radius: 8
            border.width: 1
            border.color: memory.dark ? "#33ffffff" : "#22000000"
        }

        contentItem: ColumnLayout {
            spacing: 8

            Text {
                text: "<b>Memory</b> Usage"
                textFormat: Text.StyledText
                color: menu.textColor
                font.pixelSize: 14
            }

            Text {
                text: "Utilization"
                color: menu.textColor
                opacity: 0.6
                font.pixelSize: 11
            }

            Item {
                id: graph

                readonly property var points: memory.history.map((value, index) => Qt.point(
                    memory.history.length > 1 ? index * width / (memory.history.length - 1) : 0,
                    1 + (height - 2) * (1 - Math.max(0, Math.min(value, 100)) / 100)))

                Layout.preferredWidth: 280
                Layout.preferredHeight: 80

                Shape {
                    anchors.fill: parent
                    preferredRendererType: Shape.CurveRenderer

                    ShapePath {
                        strokeWidth: -1
                        fillGradient: LinearGradient {
                            y2: graph.height

                            GradientStop {
                                position: 0
                                color: "#64bf5af2"
                            }

                            GradientStop {
                                position: 1
                                color: "#0abf5af2"
                            }
                        }

                        PathPolyline {
                            path: graph.points.length > 1
                                ? [Qt.point(0, graph.height), ...graph.points, Qt.point(graph.width, graph.height)] : []
                        }
                    }

                    ShapePath {
                        fillColor: "transparent"
                        strokeColor: "#bf5af2"
                        strokeWidth: 2

                        PathPolyline {
                            path: graph.points
                        }
                    }
                }
            }

            GridLayout {
                columns: 2
                columnSpacing: 24
                rowSpacing: 8

                Repeater {
                    model: menu.stats.length

                    delegate: ColumnLayout {
                        id: stat

                        required property int index

                        spacing: 2

                        Text {
                            text: menu.stats[stat.index][0]
                            color: menu.textColor
                            opacity: 0.6
                            font.pixelSize: 11
                        }

                        Text {
                            text: menu.stats[stat.index][1]
                            color: menu.textColor
                            font.pixelSize: 14
                        }
                    }
                }
            }
        }
    }
}
