import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// The app never asks for a password: signing in opens the browser and the app waits
Item {
    id: page

    required property QtObject cloud

    readonly property bool waiting: cloud.signInState === "waiting"

    ColumnLayout {
        anchors.centerIn: parent
        width: Math.min(page.width - 80, 420)
        spacing: 0

        Image {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 72
            Layout.preferredHeight: 72
            source: page.cloud.iconUrl
            sourceSize: Qt.size(72, 72)
        }

        Label {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 18
            text: "YASB Cloud"
            font.pixelSize: 28
            font.weight: Font.DemiBold
        }

        Label {
            Layout.fillWidth: true
            Layout.topMargin: 4
            text: page.waiting ? qsTr("Approve this device in the browser window that just opened.")
                : qsTr("Your bar setup, on every PC.")
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
            color: Qt.alpha(palette.windowText, 0.7)
        }

        Button {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 24
            Layout.preferredWidth: 200
            visible: !page.waiting
            enabled: page.cloud.signInState === "idle"
            highlighted: true
            text: enabled ? qsTr("Sign in") : qsTr("Opening browser...")
            onClicked: page.cloud.signIn()
        }

        ColumnLayout {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 24
            visible: page.waiting
            spacing: 10

            Label {
                Layout.alignment: Qt.AlignHCenter
                text: page.cloud.userCode
                font.family: Qt.fontFamilies().includes("Cascadia Mono") ? "Cascadia Mono" : "Consolas"
                font.pixelSize: 24
                font.letterSpacing: 2
            }

            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                spacing: 8

                BusyIndicator {
                    Layout.preferredWidth: 16
                    Layout.preferredHeight: 16
                    running: page.waiting
                }

                Label {
                    text: qsTr("Waiting for approval...")
                    color: Qt.alpha(palette.windowText, 0.7)
                }
            }

            LinkButton {
                Layout.alignment: Qt.AlignHCenter
                text: qsTr("Open the browser again")
                onClicked: page.cloud.reopenBrowser()
            }

            Button {
                Layout.alignment: Qt.AlignHCenter
                text: qsTr("Cancel")
                onClicked: page.cloud.cancelSignIn()
            }
        }
    }

    Caption {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 20
        visible: !page.waiting
        horizontalAlignment: Text.AlignHCenter
        textFormat: Text.RichText
        text: qsTr("By signing in, you agree to our %1 and %2.")
            .arg(`<a href="${page.cloud.termsUrl}" style="color: ${system.accent}; text-decoration: none">${qsTr("Terms of Service")}</a>`)
            .arg(`<a href="${page.cloud.privacyUrl}" style="color: ${system.accent}; text-decoration: none">${qsTr("Privacy Policy")}</a>`)
        onLinkActivated: link => page.cloud.openUrl(link)

        HoverHandler {
            cursorShape: parent.hoveredLink !== "" ? Qt.PointingHandCursor : Qt.ArrowCursor
        }
    }

    SystemPalette {
        id: system
    }
}
