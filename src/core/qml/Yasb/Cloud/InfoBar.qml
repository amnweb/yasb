import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// A message inside a card, informational or warning
Rectangle {
    id: bar

    property string title
    property string message
    property string severity: "informational"

    readonly property bool dark: Application.styleHints.colorScheme === Qt.Dark
    readonly property bool warning: severity === "warning"

    implicitHeight: content.implicitHeight + 24
    radius: 4
    color: warning ? (dark ? "#433519" : "#fff4ce") : (dark ? "#08ffffff" : "#80f6f6f6")
    border.color: dark ? "#19000000" : "#0f000000"

    SystemPalette {
        id: system
    }

    RowLayout {
        id: content

        anchors.fill: parent
        anchors.margins: 12
        anchors.leftMargin: 16
        anchors.rightMargin: 16
        spacing: 12

        // On the first line of the text, which a long message wraps below
        Rectangle {
            Layout.alignment: Qt.AlignTop
            Layout.topMargin: Math.round((lineMetrics.height - height) / 2)
            Layout.preferredWidth: 16
            Layout.preferredHeight: 16
            radius: 8
            color: bar.warning ? (bar.dark ? "#fce100" : "#9d5d00") : system.accent

            Label {
                anchors.centerIn: parent
                text: bar.warning ? "!" : "i"
                color: bar.dark ? "black" : "white"
                font.pixelSize: 11
                font.weight: Font.Bold
            }
        }

        Label {
            id: messageLabel

            Layout.fillWidth: true
            text: `<b>${bar.title}</b>&nbsp;&nbsp;${bar.message}`
            textFormat: Text.StyledText
            wrapMode: Text.Wrap

            FontMetrics {
                id: lineMetrics

                font: messageLabel.font
            }
        }
    }
}
