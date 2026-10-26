import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Shapes
import Yasb

Item {
    id: cpu

    property int updateInterval: 1000
    property Item bar: null

    property bool showAlternate: false
    property list<real> history: []

    readonly property bool dark: Qt.styleHints.colorScheme === Qt.ColorScheme.Dark
    readonly property color textColor: bar ? bar.textColor : dark ? "white" : "black"
    readonly property string barEdge: bar?.edge ?? "top"

    function histogram(values: var, min: real, max: real): string {
        const icons = [..."▁▁▂▃▄▅▆▇█"]
        const last = icons.length - 1
        return values.map(value => icons[max === min ? 0
            : Math.min(Math.max(Math.trunc((value - min) / (max - min) * last), 0), last)]).join("")
    }

    function latest(count: int): var {
        const values = history.slice(-count)
        return [...Array(count - values.length).fill(0), ...values]
    }

    implicitWidth: label.implicitWidth
    implicitHeight: label.implicitHeight

    CpuMonitor {
        id: monitor

        updateInterval: cpu.updateInterval
        onDataChanged: cpu.history = [...cpu.history, monitor.data.percent.total].slice(-60)
    }

    Text {
        id: label

        objectName: "label"
        anchors.verticalCenter: parent.verticalCenter
        text: cpu.showAlternate
            ? ` CPU: ${monitor.data.percent.total}% | freq: ${monitor.data.freq.current.toFixed(2)} Mhz`
            : ` ${cpu.histogram(cpu.latest(10), 0, 100)}`
        color: cpu.textColor
        font.family: cpu.bar ? cpu.bar.font.family : Qt.application.font.family
        font.pixelSize: cpu.bar ? cpu.bar.font.pixelSize : 13
    }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: mouse => {
            if (mouse.button === Qt.LeftButton)
                cpu.showAlternate = !cpu.showAlternate
            else
                menu.visible ? menu.close() : menu.open()
        }
    }
    Hotkey {
        keys: "alt+w"
        onActivated: menu.visible ? menu.close() : menu.open()
    }
    Popup {
        id: menu

        readonly property color textColor: cpu.dark ? "white" : "black"
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
        popupType: Popup.Window
        padding: 12
        x: cpu.barEdge === "left" ? cpu.width + 8
            : cpu.barEdge === "right" ? -width - 8
            : Math.round((cpu.width - width) / 2)
        y: cpu.barEdge === "top" ? cpu.height + 8
            : cpu.barEdge === "bottom" ? -height - 8
            : Math.round((cpu.height - height) / 2)

        background: Rectangle {
            color: cpu.dark ? "#f21e1e1e" : "#f2f3f3f3"
            radius: 8
            border.width: 1
            border.color: cpu.dark ? "#33ffffff" : "#22000000"
        }

        contentItem: ColumnLayout {
            spacing: 8

            Text {
                text: "<b>CPU</b> Usage"
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

                readonly property var points: cpu.history.map((value, index) => Qt.point(
                    cpu.history.length > 1 ? index * width / (cpu.history.length - 1) : 0,
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
                                color: "#640a84ff"
                            }

                            GradientStop {
                                position: 1
                                color: "#0a0a84ff"
                            }
                        }

                        PathPolyline {
                            path: graph.points.length > 1
                                ? [Qt.point(0, graph.height), ...graph.points, Qt.point(graph.width, graph.height)] : []
                        }
                    }

                    ShapePath {
                        fillColor: "transparent"
                        strokeColor: "#0a84ff"
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
