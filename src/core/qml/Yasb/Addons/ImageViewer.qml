pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls

// The addon's images at full size
Popup {
    id: viewer

    property list<string> images
    property int index
    readonly property string current: images.length > index ? images[index] : ""

    function show(at: int) {
        index = at
        open()
    }

    function step(by: int) {
        index = (index + by + images.length) % images.length
    }

    parent: Overlay.overlay
    x: 0
    y: 0
    width: parent?.width ?? 0
    height: parent?.height ?? 0
    modal: true
    padding: 0
    background: Rectangle {
        color: Qt.alpha("#000000", 0.85)
    }

    contentItem: Item {
        focus: true
        Keys.onLeftPressed: viewer.step(-1)
        Keys.onRightPressed: viewer.step(1)
        Keys.onEscapePressed: viewer.close()

        TapHandler {
            onTapped: viewer.close()
        }

        Image {
            id: full

            anchors.centerIn: parent
            width: Math.min(implicitWidth, parent.width - 160)
            height: Math.min(implicitHeight, parent.height - 112)
            source: viewer.current
            fillMode: Image.PreserveAspectFit
            asynchronous: true

            TapHandler {}
        }

        BusyIndicator {
            anchors.centerIn: parent
            running: full.status === Image.Loading
        }

        Button {
            anchors.top: parent.top
            anchors.right: parent.right
            anchors.margins: 16
            flat: true
            contentItem: Glyph {
                text: "\uE8BB"
                color: "#ffffff"
            }
            onClicked: viewer.close()
        }

        Button {
            anchors.left: parent.left
            anchors.leftMargin: 24
            anchors.verticalCenter: parent.verticalCenter
            visible: viewer.images.length > 1
            flat: true
            contentItem: Glyph {
                text: "\uE76B"
                color: "#ffffff"
            }
            onClicked: viewer.step(-1)
        }

        Button {
            anchors.right: parent.right
            anchors.rightMargin: 24
            anchors.verticalCenter: parent.verticalCenter
            visible: viewer.images.length > 1
            flat: true
            contentItem: Glyph {
                text: "\uE76C"
                color: "#ffffff"
            }
            onClicked: viewer.step(1)
        }

        Label {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 24
            visible: viewer.images.length > 1
            text: qsTr("%1 of %2").arg(viewer.index + 1).arg(viewer.images.length)
            color: "#ffffff"
        }
    }
}
