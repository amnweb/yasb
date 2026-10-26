import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Shapes
import Yasb

Item {
    id: gpu

    property int updateInterval: 2000
    property int gpuIndex: 0
    property Item bar: null

    property bool showAlternate: false
    property list<real> history: []
    property list<real> temperatures: []

    readonly property bool dark: Qt.styleHints.colorScheme === Qt.ColorScheme.Dark
    readonly property color textColor: bar ? bar.textColor : dark ? "white" : "black"
    readonly property string barEdge: bar?.edge ?? "top"

    component Graph: Item {
        id: graph

        property list<real> values: []
        property color color: "#0a84ff"
        readonly property var points: values.map((value, index) => Qt.point(
            values.length > 1 ? index * width / (values.length - 1) : 0,
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
                        color: Qt.rgba(graph.color.r, graph.color.g, graph.color.b, 0.4)
                    }

                    GradientStop {
                        position: 1
                        color: Qt.rgba(graph.color.r, graph.color.g, graph.color.b, 0.04)
                    }
                }

                PathPolyline {
                    path: graph.points.length > 1
                        ? [Qt.point(0, graph.height), ...graph.points, Qt.point(graph.width, graph.height)] : []
                }
            }

            ShapePath {
                fillColor: "transparent"
                strokeColor: graph.color
                strokeWidth: 2

                PathPolyline {
                    path: graph.points
                }
            }
        }
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

    implicitWidth: monitor.available ? label.implicitWidth : 0
    implicitHeight: monitor.available ? label.implicitHeight : 0
    visible: monitor.available

    GpuMonitor {
        id: monitor

        gpuIndex: gpu.gpuIndex
        updateInterval: gpu.updateInterval
        onDataChanged: {
            gpu.history = [...gpu.history, monitor.data.utilization].slice(-60)
            gpu.temperatures = [...gpu.temperatures, monitor.data.temp].slice(-60)
        }
    }

    Text {
        id: label

        objectName: "label"
        anchors.verticalCenter: parent.verticalCenter
        text: gpu.showAlternate
            ? `${gpu.size(monitor.data.mem_used, "")}/${gpu.size(monitor.data.mem_total, "")}`
            : `${monitor.data.utilization}%`
        color: gpu.textColor
        font.family: gpu.bar ? gpu.bar.font.family : Qt.application.font.family
        font.pixelSize: gpu.bar ? gpu.bar.font.pixelSize : 13
    }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: mouse => {
            if (mouse.button === Qt.LeftButton)
                gpu.showAlternate = !gpu.showAlternate
            else
                menu.visible ? menu.close() : menu.open()
        }
    }

    Popup {
        id: menu

        readonly property color textColor: gpu.dark ? "white" : "black"
        readonly property var stats: {
            const data = monitor.data
            const rows = [
                ["Usage", `${data.utilization.toFixed(0)}%`],
                ["Memory", `${gpu.size(data.mem_used, "B")} / ${gpu.size(data.mem_total, "B")}`]
            ]
            if (data.temp > 0)
                rows.push(["Temperature", `${data.temp}°C`])
            if (data.power_draw > 0)
                rows.push(["Power draw", `${data.power_draw.toFixed(1)} W`])
            if (data.fan_speed > 0 || data.temp > 0)
                rows.push(["Fan speed", `${data.fan_speed}%`])
            if (data.mem_shared_total > 0)
                rows.push(["Shared memory", `${gpu.size(data.mem_shared_used, "B")} / ${gpu.size(data.mem_shared_total, "B")}`])
            return rows
        }

        objectName: "menu"
        popupType: Popup.Window
        padding: 12
        x: gpu.barEdge === "left" ? gpu.width + 8
            : gpu.barEdge === "right" ? -width - 8
            : Math.round((gpu.width - width) / 2)
        y: gpu.barEdge === "top" ? gpu.height + 8
            : gpu.barEdge === "bottom" ? -height - 8
            : Math.round((gpu.height - height) / 2)

        background: Rectangle {
            color: gpu.dark ? "#f21e1e1e" : "#f2f3f3f3"
            radius: 8
            border.width: 1
            border.color: gpu.dark ? "#33ffffff" : "#22000000"
        }

        contentItem: ColumnLayout {
            spacing: 8

            Text {
                text: "<b>GPU</b> Usage"
                textFormat: Text.StyledText
                color: menu.textColor
                font.pixelSize: 14
            }

            Text {
                text: monitor.data.name
                color: menu.textColor
                opacity: 0.6
                font.pixelSize: 11
            }

            Text {
                text: "Utilization"
                color: menu.textColor
                opacity: 0.6
                font.pixelSize: 11
            }

            Graph {
                values: gpu.history
            }

            Text {
                visible: monitor.data.temp > 0
                text: "Temperature"
                color: menu.textColor
                opacity: 0.6
                font.pixelSize: 11
            }

            Graph {
                visible: monitor.data.temp > 0
                values: gpu.temperatures
                color: "#ff9f0a"
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
