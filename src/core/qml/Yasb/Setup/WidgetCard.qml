import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Yasb.Cloud

// A widget on the bar, with a drag grip and a remove button
Frame {
    id: card

    required property string icon
    required property string title
    required property string description

    readonly property bool dragging: grip.active
    // In scene coordinates
    readonly property point dragPoint: grip.centroid.scenePosition

    signal removeRequested()
    // Ctrl+Up or Ctrl+Down: -1 up a row, 1 down
    signal moveRequested(int step)

    RowLayout {
        anchors.fill: parent
        spacing: 16

        Label {
            Layout.preferredWidth: 16
            text: "\uE700"
            font.family: "Segoe Fluent Icons"
            font.pixelSize: 16
            horizontalAlignment: Text.AlignHCenter
            color: Qt.alpha(palette.windowText, card.dragging || gripHover.hovered ? 1 : 0.45)
            Accessible.ignored: true

            HoverHandler {
                id: gripHover

                cursorShape: Qt.OpenHandCursor
            }

            DragHandler {
                id: grip

                // The page moves the row, not the handler
                target: null
                margin: 8
                cursorShape: Qt.ClosedHandCursor
            }
        }

        Label {
            Layout.preferredWidth: 24
            text: card.icon
            font.family: "Segoe Fluent Icons"
            font.pixelSize: 20
            horizontalAlignment: Text.AlignHCenter
            Accessible.ignored: true
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2

            Label {
                Layout.fillWidth: true
                text: card.title
                wrapMode: Text.Wrap
            }

            Caption {
                Layout.fillWidth: true
                text: card.description
            }
        }

        ToolButton {
            text: "\uE711"
            font.family: "Segoe Fluent Icons"
            font.pixelSize: 12
            Accessible.name: qsTr("Remove %1").arg(card.title)
            Accessible.description: qsTr("Ctrl+Up and Ctrl+Down move it")
            ToolTip.visible: hovered
            ToolTip.delay: 500
            ToolTip.text: qsTr("Remove")
            onClicked: card.removeRequested()
            Keys.onPressed: event => {
                if (event.modifiers !== Qt.ControlModifier || (event.key !== Qt.Key_Up && event.key !== Qt.Key_Down))
                    return
                card.moveRequested(event.key === Qt.Key_Up ? -1 : 1)
                event.accepted = true
            }
        }
    }
}
