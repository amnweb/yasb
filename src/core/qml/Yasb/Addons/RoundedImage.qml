pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Effects

// An image with rounded corners, and a glyph until it loads
Item {
    id: root

    property alias source: image.source
    property real radius: 4
    property bool roundBottom: true
    property string glyph
    property int glyphSize: 16
    property color fill
    property color glyphColor

    Rectangle {
        anchors.fill: parent
        topLeftRadius: root.radius
        topRightRadius: root.radius
        bottomLeftRadius: root.roundBottom ? root.radius : 0
        bottomRightRadius: root.roundBottom ? root.radius : 0
        color: root.fill

        Glyph {
            anchors.centerIn: parent
            visible: image.status !== Image.Ready
            text: root.glyph
            font.pixelSize: root.glyphSize
            color: root.glyphColor
        }
    }

    Item {
        id: picture

        anchors.fill: parent
        visible: image.status === Image.Ready
        layer.enabled: picture.visible
        layer.effect: MultiEffect {
            maskEnabled: true
            maskSource: mask
            maskThresholdMin: 0.5
            maskSpreadAtMin: 1
        }

        Image {
            id: image

            anchors.fill: parent
            // No sourceSize: tied to the size, every resize would download the image again
            fillMode: Image.PreserveAspectCrop
            mipmap: true
            asynchronous: true
        }
    }

    Rectangle {
        id: mask

        anchors.fill: parent
        topLeftRadius: root.radius
        topRightRadius: root.radius
        bottomLeftRadius: root.roundBottom ? root.radius : 0
        bottomRightRadius: root.roundBottom ? root.radius : 0
        visible: false
        layer.enabled: true
    }
}
