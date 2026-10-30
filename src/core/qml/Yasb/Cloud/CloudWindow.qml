import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Window {
    id: window

    required property QtObject cloud

    readonly property bool dark: Application.styleHints.colorScheme === Qt.Dark

    title: "YASB Cloud"
    color: "transparent"
    minimumWidth: 820
    minimumHeight: 480

    Component.onCompleted: {
        const saved = cloud.savedGeometry()
        if (saved.width > 0) {
            x = saved.x
            y = saved.y
            width = saved.width
            height = saved.height
            return
        }
        width = Math.min(1000, screen.desktopAvailableWidth)
        height = Math.min(700, screen.desktopAvailableHeight)
        x = screen.virtualX + (screen.width - width) / 2
        y = screen.virtualY + (screen.height - height) / 2
    }

    onClosing: {
        cloud.saveGeometry(x, y, width, height)
        cloud.shutdown()
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: ["loading", "connect", "backups", "settings"].indexOf(window.cloud.page)

            Item {
                BusyIndicator {
                    anchors.centerIn: parent
                    width: 48
                    height: 48
                    running: window.cloud.page === "loading"
                }
            }

            ConnectPage {
                cloud: window.cloud
            }

            BackupsPage {
                cloud: window.cloud
            }

            SettingsPage {
                cloud: window.cloud
            }
        }

        // Who is signed in, what the plan allows, and how much of it is used
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 48
            visible: window.cloud.page === "backups" || window.cloud.page === "settings"
            color: {
                switch (window.cloud.accountState) {
                case "critical": return window.dark ? "#442726" : "#fde7e9"
                case "caution": return window.dark ? "#433519" : "#fff4ce"
                default: return window.dark ? "#0dffffff" : "#ffffff"
                }
            }

            Rectangle {
                width: parent.width
                height: 1
                color: window.dark ? "#14ffffff" : "#0f000000"
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 20
                anchors.rightMargin: 16
                spacing: 10

                Caption {
                    Layout.fillWidth: true
                    text: window.cloud.accountDetails
                    elide: Text.ElideRight
                    wrapMode: Text.NoWrap
                }

                Caption {
                    text: window.cloud.accountEmail
                    wrapMode: Text.NoWrap
                }

                Button {
                    text: qsTr("Manage account")
                    onClicked: window.cloud.manageAccount()
                }

                Button {
                    text: qsTr("Sign out")
                    onClicked: window.cloud.signOut()
                }
            }
        }
    }

    Dialog {
        id: messageDialog

        property string message

        anchors.centerIn: Overlay.overlay
        width: Math.min(460, window.width - 48)
        modal: true
        standardButtons: Dialog.Ok

        Label {
            width: messageDialog.availableWidth
            text: messageDialog.message
            wrapMode: Text.Wrap
        }
    }

    Connections {
        target: window.cloud

        function onMessageRequested(title: string, message: string) {
            messageDialog.title = title
            messageDialog.message = message
            messageDialog.open()
        }
    }
}
