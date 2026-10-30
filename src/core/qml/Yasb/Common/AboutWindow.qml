import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Window {
    id: window

    required property QtObject about

    readonly property string updateState: about.updateState

    title: qsTr("About YASB")
    flags: Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint | Qt.MSWindowsFixedSizeDialogHint
        | Qt.WindowStaysOnTopHint
    color: "transparent"
    width: 480
    height: layout.implicitHeight + 48

    Component.onCompleted: {
        x = screen.virtualX + (screen.width - width) / 2
        y = screen.virtualY + (screen.height - height) / 2
    }

    component Caption: Label {
        font.pixelSize: 12
        color: Qt.alpha(palette.windowText, 0.7)
        wrapMode: Text.Wrap
    }

    component LinkButton: Button {
        implicitWidth: implicitContentWidth + leftPadding + rightPadding
        flat: true
        leftPadding: 8
        rightPadding: 8
        palette.buttonText: system.accent

        SystemPalette {
            id: system
        }
    }

    component Card: Frame {
        id: card

        required property string heading
        property string description
        default property alias actions: row.data

        Layout.fillWidth: true

        RowLayout {
            id: row

            anchors.fill: parent
            spacing: 16

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

    component CardButton: Button {
        Layout.preferredWidth: 160
    }

    ColumnLayout {
        id: layout

        anchors.fill: parent
        anchors.margins: 24
        spacing: 4

        Image {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 8
            Layout.preferredWidth: 96
            Layout.preferredHeight: 96
            source: window.about.iconUrl
            sourceSize: Qt.size(96, 96)
        }

        Label {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 12
            text: "YASB Reborn"
            font.pixelSize: 28
            font.weight: Font.DemiBold
        }

        Label {
            Layout.fillWidth: true
            text: qsTr("A highly configurable status bar for Windows")
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
            color: Qt.alpha(palette.windowText, 0.7)
        }

        Caption {
            Layout.fillWidth: true
            Layout.topMargin: 4
            horizontalAlignment: Text.AlignHCenter
            textFormat: Text.RichText
            text: `${window.about.version}&nbsp;&nbsp;·&nbsp;&nbsp;<a href="${window.about.releaseUrl}" style="color: ${systemPalette.accent}; text-decoration: none">${window.about.releaseLabel}</a>`
            onLinkActivated: link => window.about.open(link)

            HoverHandler {
                cursorShape: parent.hoveredLink !== "" ? Qt.PointingHandCursor : Qt.ArrowCursor
            }
        }

        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 48
            Layout.bottomMargin: 20
            spacing: 4

            LinkButton {
                text: "GitHub"
                onClicked: window.about.open(window.about.githubUrl)
            }

            LinkButton {
                text: qsTr("Contributors")
                onClicked: window.about.open(window.about.githubUrl + "/graphs/contributors")
            }

            LinkButton {
                text: qsTr("Website")
                onClicked: window.about.open(window.about.siteUrl)
            }

            LinkButton {
                text: "Discord"
                onClicked: window.about.open("https://discord.gg/qkeunvBFgX")
            }

        }

        Card {
            heading: qsTr("Updates")
            description: {
                switch (window.updateState) {
                case "checking": return qsTr("Checking for updates...")
                case "available": return qsTr("A new version is ready to install")
                case "latest": return qsTr("You're on the latest version")
                case "failed": return qsTr("Couldn't check for updates")
                case "unsupported": return window.about.unsupportedReason
                default: return qsTr("Look for a newer version on GitHub")
                }
            }

            CardButton {
                text: window.updateState === "available" ? qsTr("Update") : qsTr("Check for updates")
                highlighted: window.updateState === "available"
                enabled: window.updateState !== "checking" && window.updateState !== "unsupported"
                onClicked: {
                    if (window.updateState === "available")
                        window.close()
                    window.about.checkForUpdates()
                }
            }
        }

        Card {
            heading: qsTr("Configuration")
            description: qsTr("Your config.yaml and widget files")

            CardButton {
                text: qsTr("Open folder")
                onClicked: window.about.openConfig()
            }
        }

        Card {
            heading: qsTr("Support the project")
            description: qsTr("YASB is free and open source")

            CardButton {
                text: "Buy me a coffee"
                onClicked: window.about.open("https://ko-fi.com/amnweb")
            }
        }

        Card {
            heading: qsTr("Documentation")
            description: qsTr("Read the official documentation")

            CardButton {
                text: "Open docs"
                onClicked: window.about.open(window.about.docSiteUrl)
            }
        }
    }

    SystemPalette {
        id: systemPalette
    }

    Shortcut {
        sequence: "Escape"
        onActivated: window.close()
    }
}
