import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Window {
    id: window

    required property QtObject updater

    readonly property string changelogStyle: `
        body, p, li { font-family: 'Segoe UI'; font-size: 10pt; font-weight: 600; }
        h2, h3 { margin-top: 32px; margin-bottom: 8px; }
        a { color: ${system.accent}; text-decoration: none; }
        ul, ol, li, li > p { margin-left: 0px; padding-left: 0px; }
        li { margin-top: 6px; margin-bottom: 6px; }
        code { background-color: #000000; color: #ffffff; font-family: 'Consolas', monospace; }
        pre { background-color: #000000; color: #ffffff; font-family: 'Consolas', monospace; }
    `

    title: qsTr("Update Available")
    flags: Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint | Qt.WindowStaysOnTopHint
    color: "transparent"
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

    SystemPalette {
        id: system
    }

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

                TextArea {
                    id: notes

                    readOnly: true
                    selectByMouse: true
                    textFormat: TextEdit.RichText
                    wrapMode: TextEdit.Wrap
                    background: null
                    text: window.updater.changelog === "" ? ""
                        : `<html><head><style>${window.changelogStyle}</style></head><body>${window.updater.changelog}</body></html>`
                    onLinkActivated: link => window.updater.open(link)

                    HoverHandler {
                        cursorShape: parent.hoveredLink !== "" ? Qt.PointingHandCursor : Qt.IBeamCursor
                    }
                }
            }

            BusyIndicator {
                anchors.centerIn: parent
                running: window.updater.changelog === ""
            }
        }

        // Rich text only takes image sizes in pixels, so the updater fits the images to this width
        Binding {
            target: window.updater
            property: "textWidth"
            value: Math.floor(notes.width - notes.leftPadding - notes.rightPadding)
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
