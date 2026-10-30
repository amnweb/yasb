import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Frame {
    id: card

    required property string heading
    property string description
    default property alias actions: row.data

    RowLayout {
        id: row

        anchors.fill: parent
        spacing: 12

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2

            Label {
                Layout.fillWidth: true
                text: card.heading
                wrapMode: Text.Wrap
            }

            Caption {
                Layout.fillWidth: true
                visible: text !== ""
                text: card.description
            }
        }
    }
}
