import QtQuick
import QtQuick.Effects

// Picks a colour from any screen: a magnifying loupe follows the mouse and shows the live pixels under it.
// Left click picks, right click or Escape cancels.
QtObject {
    id: picker

    // The launcher's QuickLaunchSearch, which reads the screen's pixels
    required property QtObject quickLaunch
    readonly property int size: 11
    readonly property int cell: 12
    property bool active: false

    signal picked(string color)

    function start() {
        active = true
    }

    function stop() {
        active = false
    }

    property Instantiator windows: Instantiator {
        model: picker.active ? Qt.application.screens : []

        delegate: Window {
            id: window

            required property var modelData
            property var pixels: []
            property point cursor

            screen: modelData
            x: modelData.virtualX
            y: modelData.virtualY
            width: modelData.width
            height: modelData.height
            flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
            color: "transparent"

            Component.onCompleted: {
                picker.quickLaunch.excludeFromCapture(window)
                show()
            }

            MouseArea {
                anchors.fill: parent
                hoverEnabled: true
                acceptedButtons: Qt.LeftButton | Qt.RightButton
                cursorShape: Qt.BlankCursor

                onEntered: window.requestActivate()
                onExited: window.pixels = []
                onPositionChanged: mouse => {
                    window.cursor = Qt.point(mouse.x, mouse.y)
                    window.pixels = picker.quickLaunch.colorsAround(window.x + mouse.x, window.y + mouse.y, picker.size)
                }
                onPressed: mouse => {
                    const color = window.pixels[(picker.size * picker.size - 1) / 2]
                    if (mouse.button === Qt.LeftButton && color)
                        picker.picked(color)
                    // Stopping deletes this window and this handler with it, so it comes last
                    picker.stop()
                }
            }

            Shortcut {
                sequence: "Escape"
                onActivated: picker.stop()
            }

            Item {
                id: loupe

                readonly property int grid: picker.size * picker.cell
                readonly property color center: window.pixels[(picker.size * picker.size - 1) / 2] ?? "black"

                // Whole pixels, or every cell edge is smeared across two screen pixels
                x: Math.round(window.cursor.x - width / 2)
                y: Math.round(window.cursor.y - lens.height / 2)
                width: lens.width
                height: lens.height + 6 + pill.height
                visible: window.pixels.length > 0

                Item {
                    id: lens

                    width: loupe.grid + 8
                    height: width
                    layer.enabled: true
                    layer.effect: MultiEffect {
                        maskEnabled: true
                        maskSource: round
                        maskThresholdMin: 0.5
                        maskSpreadAtMin: 1.0
                    }

                    Rectangle {
                        anchors.fill: parent
                        color: Qt.rgba(1, 1, 1, 0.16)
                    }

                    Grid {
                        id: cells

                        x: 4
                        y: 4
                        columns: picker.size
                        spacing: 1

                        Repeater {
                            model: picker.size * picker.size

                            delegate: Rectangle {
                                required property int index

                                width: picker.cell - 1
                                height: picker.cell - 1
                                color: window.pixels[index] ?? "black"
                            }
                        }
                    }
                }

                Rectangle {
                    id: round

                    anchors.fill: lens
                    radius: width / 2
                    visible: false
                    layer.enabled: true
                }

                Rectangle {
                    anchors.fill: lens
                    radius: width / 2
                    color: "transparent"
                    border.width: 2.5
                    border.color: Qt.rgba(0.16, 0.16, 0.16, 0.86)
                }

                // Around the middle cell, the colour that a click picks
                Rectangle {
                    x: cells.x + (picker.size - 1) / 2 * picker.cell - 1
                    y: x
                    width: picker.cell + 1
                    height: picker.cell + 1
                    color: "transparent"
                    border.width: 2
                    border.color: loupe.center.hslLightness < 0.5 ? "white" : "black"
                }

                Rectangle {
                    id: pill

                    anchors.horizontalCenter: lens.horizontalCenter
                    anchors.top: lens.bottom
                    anchors.topMargin: 6
                    width: row.implicitWidth + 16
                    height: row.implicitHeight + 8
                    radius: height / 2
                    color: Qt.rgba(0.08, 0.08, 0.08, 0.82)

                    Row {
                        id: row

                        anchors.centerIn: parent
                        spacing: 6

                        Rectangle {
                            anchors.verticalCenter: parent.verticalCenter
                            width: 14
                            height: 14
                            radius: 7
                            color: loupe.center
                            border.width: 1
                            border.color: Qt.rgba(1, 1, 1, 0.4)
                        }

                        Text {
                            text: String(loupe.center).toUpperCase()
                            color: "white"
                            font.family: "Segoe UI"
                            font.pointSize: 9
                            font.bold: true
                        }
                    }
                }
            }
        }
    }
}
