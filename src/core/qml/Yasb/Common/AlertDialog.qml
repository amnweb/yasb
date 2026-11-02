import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// An alert in a window of its own, with optional details the user can show and copy
Window {
    id: dialog

    property string heading
    property string message
    property string details
    property bool detailsShown: false

    title: "YASB"
    flags: Qt.Tool | Qt.WindowStaysOnTopHint
    color: "transparent"
    width: 520
    height: layout.implicitHeight

    Component.onCompleted: {
        x = screen.virtualX + (screen.width - width) / 2
        y = screen.virtualY + (screen.height - height) / 2
    }

    DragHandler {
        target: null
        onActiveChanged: if (active) dialog.startSystemMove()
    }

    ColumnLayout {
        id: layout

        anchors.fill: parent
        spacing: 0

        ColumnLayout {
            Layout.fillWidth: true
            Layout.margins: 24
            spacing: 12

            Label {
                Layout.fillWidth: true
                text: dialog.heading
                visible: text !== ""
                wrapMode: Text.Wrap
                font.pixelSize: 18
                font.weight: Font.DemiBold
                Layout.bottomMargin: 8
            }

            Label {
                Layout.fillWidth: true
                text: dialog.message
                wrapMode: Text.Wrap
            }

            ScrollView {
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(detailsArea.implicitHeight, 240)
                visible: dialog.detailsShown

                TextArea {
                    id: detailsArea

                    text: dialog.details
                    font.pixelSize: 13
                    readOnly: true
                    selectByMouse: true
                    wrapMode: TextEdit.Wrap
                    font.family: "Consolas"
                }
            }
        }

        DialogButtonBox {
            Layout.fillWidth: true
            standardButtons: DialogButtonBox.Ok

            // The box clears the highlight of its buttons while it builds them
            Component.onCompleted: standardButton(DialogButtonBox.Ok).highlighted = true
            onAccepted: dialog.close()

            Button {
                visible: dialog.details !== ""
                text: dialog.detailsShown ? qsTr("Hide details") : qsTr("Show details")
                DialogButtonBox.buttonRole: DialogButtonBox.ActionRole
                onClicked: dialog.detailsShown = !dialog.detailsShown
            }

            Button {
                visible: dialog.details !== ""
                text: qsTr("Copy details")
                DialogButtonBox.buttonRole: DialogButtonBox.ActionRole
                onClicked: {
                    detailsArea.selectAll()
                    detailsArea.copy()
                    detailsArea.deselect()
                }
            }
        }
    }

    Shortcut {
        sequence: "Escape"
        onActivated: dialog.close()
    }
}
