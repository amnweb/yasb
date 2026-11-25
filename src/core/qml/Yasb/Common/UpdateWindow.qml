import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Yasb

Window {
    id: window

    required property Updater updater

    // Set when Windows draws Mica behind the window, from Windows 11 22H2 on; until then it has the style's colour
    property bool mica: false

    title: qsTr("Update Available")
    flags: Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint | Qt.WindowStaysOnTopHint
    color: mica ? "transparent" : palette.window
    width: 900
    height: 640
    minimumWidth: 900
    minimumHeight: 640

    Component.onCompleted: {
        x = screen.virtualX + (screen.width - width) / 2
        y = screen.virtualY + (screen.height - height) / 2
        updater.loadChangelog()
    }
    onClosing: updater.cancel()

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 18
        spacing: 12

        Label {
            Layout.fillWidth: true
            text: window.updater.heading
            elide: Text.ElideRight
            font.pixelSize: 20
            font.weight: Font.DemiBold
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            ScrollView {
                anchors.fill: parent
                // The text wraps to the view, so its width never follows the text
                contentWidth: availableWidth

                MarkdownView {
                    markdown: window.updater.changelog
                }
            }

            BusyIndicator {
                anchors.centerIn: parent
                running: window.updater.changelog === ""
            }
        }

        ProgressBar {
            Layout.fillWidth: true
            visible: window.updater.state !== "ready"
            from: 0
            to: 100
            value: window.updater.progress
            indeterminate: window.updater.progress < 0
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Label {
                Layout.fillWidth: true
                text: window.updater.status
                elide: Text.ElideRight
                font.pixelSize: 12
                opacity: 0.7
            }

            Button {
                text: {
                    switch (window.updater.state) {
                    case "downloading": return qsTr("Downloading...")
                    case "installing": return qsTr("Launching installer...")
                    default: return qsTr("Download and Install")
                    }
                }
                enabled: window.updater.state === "ready"
                highlighted: true
                onClicked: window.updater.download()
            }

            Button {
                text: window.updater.state === "downloading" ? qsTr("Cancel") : qsTr("Close")
                enabled: window.updater.state !== "installing"
                onClicked: window.updater.state === "downloading" ? window.updater.cancel() : window.close()
            }
        }
    }

    Shortcut {
        sequence: "Escape"
        onActivated: window.close()
    }
}
