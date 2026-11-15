pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Effects
import Yasb

// Picks a colour from any screen: a magnifying loupe follows the mouse and shows the live pixels under it.
// Left click picks, right click or Escape cancels.
QtObject {
    id: picker

    // The quick launch's search, which reads the screen's colours
    required property QuickLaunchSearch launcherSearch
    // The look of the lens and its label, from the quick launch's properties
    required property color frameColor
    required property color labelColor
    required property color textColor
    required property font font
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
        model: picker.active ? Application.screens : []

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
                picker.launcherSearch.excludeFromCapture(window)
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
                    window.pixels = picker.launcherSearch.colorsAround(window.x + mouse.x, window.y + mouse.y, picker.size)
                }
                onPressed: mouse => {
                    const color = window.pixels[(picker.size * picker.size - 1) / 2]
                    if (mouse.button === Qt.LeftButton && color)
                        picker.picked(color)
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
                readonly property color center: window.pixels[(picker.size * picker.size - 1) / 2] ?? "#000000"

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

                    // Solid, so the lines between the cells don't show the screen under the lens
                    Rectangle {
                        anchors.fill: parent
                        color: Qt.alpha(picker.frameColor, 1)
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
                                color: window.pixels[index] ?? "#000000"
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
                    border.color: picker.frameColor
                }

                Rectangle {
                    x: cells.x + (picker.size - 1) / 2 * picker.cell - 1
                    y: x
                    width: picker.cell + 1
                    height: picker.cell + 1
                    color: "transparent"
                    border.width: 2
                    border.color: loupe.center.hslLightness < 0.5 ? "#ffffff" : "#000000"
                }

                Rectangle {
                    id: pill

                    anchors.horizontalCenter: lens.horizontalCenter
                    anchors.top: lens.bottom
                    anchors.topMargin: 6
                    width: row.implicitWidth + 16
                    height: row.implicitHeight + 8
                    radius: height / 2
                    color: picker.labelColor

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
                            border.color: picker.frameColor
                        }

                        Text {
                            text: String(loupe.center).toUpperCase()
                            color: picker.textColor
                            font: picker.font
                        }
                    }
                }
            }
        }
    }
}
