import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Yasb
import Yasb.Common

Item {
    id: github

    property Item bar: null
    property alias token: monitor.token
    property alias updateInterval: monitor.updateInterval
    property alias maxNotifications: monitor.maxNotifications
    property alias onlyUnread: monitor.onlyUnread
    property alias reasonFilters: monitor.reasonFilters
    property alias showCommentCount: monitor.showCommentCount
    property bool hideEmpty: false
    property int popupWidth: 440
    property int popupHeight: 640
    readonly property bool dark: bar ? bar.dark : Qt.styleHints.colorScheme === Qt.ColorScheme.Dark
    readonly property color foreground: dark ? "#ebebeb" : "#24292f"
    readonly property color secondary: dark ? "#959da5" : "#656d76"
    readonly property color errorColor: dark ? "#ff9991" : "#b42318"
    readonly property string edge: bar?.edge ?? "top"
    property real now: Date.now()

    implicitWidth: label.implicitWidth
    implicitHeight: label.implicitHeight
    visible: !hideEmpty || monitor.needsSignIn || monitor.unreadCount > 0 || monitor.error !== ""
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: `GitHub, ${monitor.unreadCount} unread notifications`
    Accessible.onPressAction: togglePopup()
    Keys.onReturnPressed: togglePopup()
    Keys.onSpacePressed: togglePopup()

    function placePopup() {
        const start = mapToGlobal(0, 0)
        let px = edge === "left" ? start.x + width + 6
            : edge === "right" ? start.x - popup.width - 6 : start.x + (width - popup.width) / 2
        let py = edge === "top" ? start.y + height + 6
            : edge === "bottom" ? start.y - popup.height - 6 : start.y + (height - popup.height) / 2
        const screen = github.Screen
        px = Math.max(screen.virtualX + 8, Math.min(px, screen.virtualX + screen.width - popup.width - 8))
        py = Math.max(screen.virtualY + 8, Math.min(py, screen.virtualY + screen.desktopAvailableHeight - popup.height - 8))
        popup.x = Math.round(px)
        popup.y = Math.round(py)
    }

    function togglePopup() {
        if (popup.visible)
            popup.close()
        else {
            now = Date.now()
            placePopup()
            popup.open()
        }
    }

    function age(timestamp: string): string {
        const seconds = Math.max(0, (now - Date.parse(timestamp)) / 1000)
        if (!Number.isFinite(seconds)) return ""
        if (seconds < 60) return "now"
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m`
        if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`
        return `${Math.floor(seconds / 86400)}d`
    }

    Component.onDestruction: popup.hide()

    GitHubNotifications { id: monitor }

    Connections {
        target: github.Window.window
        function onVisibleChanged() {
            if (!github.Window.window?.visible)
                popup.hide()
        }
        function onXChanged() { if (popup.visible) github.placePopup() }
        function onYChanged() { if (popup.visible) github.placePopup() }
    }

    Timer {
        interval: 20000
        repeat: true
        running: popup.visible
        onTriggered: github.now = Date.now()
    }

    Row {
        id: label
        anchors.verticalCenter: parent.verticalCenter
        spacing: 6
        Image {
            source: Qt.resolvedUrl(github.dark ? "icons/github.svg" : "icons/github-dark.svg")
            width: 18; height: 18
            anchors.verticalCenter: parent.verticalCenter
            sourceSize: Qt.size(18, 18)
            opacity: monitor.needsSignIn ? 0.55 : 1
        }
        Text {
            text: monitor.unreadCount
            color: github.bar ? github.bar.textColor : github.foreground
            font.family: github.bar ? github.bar.font.family : Qt.application.font.family
            font.pixelSize: github.bar ? github.bar.font.pixelSize : 13
            anchors.verticalCenter: parent.verticalCenter
        }
    }

    MouseArea {
        id: button
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: mouse => {
            if (mouse.button === Qt.LeftButton) github.togglePopup()
            else monitor.refresh()
        }
    }

    BackdropPopup {
        id: popup
        property real reveal: 0
        readonly property bool needsSignIn: monitor.needsSignIn || monitor.authBusy
        title: "GitHub notifications"
        width: github.popupWidth
        height: Math.min(github.popupHeight, github.Screen.height - 24)
        anchor: github
        backdropItem: surface
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: 180; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: 140; easing.type: Easing.InCubic }
        onVisibleChanged: { if (!visible) reveal = 0 }

        Rectangle {
            id: surface
            anchors.fill: parent
            anchors.margins: 8
            radius: 10
            color: github.dark ? Qt.alpha("#222222", 0.75) : "#e8f7f7f7"
            border.width: 1
            border.color: github.dark ? "#33ffffff" : "#22000000"
            opacity: popup.reveal
            scale: 0.5 + popup.reveal * 0.5
            transformOrigin: github.edge === "bottom" ? Item.Bottom : Item.Top

            RowLayout {
                id: toolbar
                x: 12; y: 10
                width: parent.width - 24
                height: 32
                spacing: 2
                Button {
                    text: "All"
                    flat: true
                    checked: !monitor.onlyUnread
                    enabled: !popup.needsSignIn
                    onClicked: monitor.onlyUnread = false
                }
                Button {
                    text: `Unread${monitor.unreadCount ? ` ${monitor.unreadCount}` : ""}`
                    flat: true
                    checked: monitor.onlyUnread
                    enabled: !popup.needsSignIn
                    onClicked: monitor.onlyUnread = true
                }
                Item { Layout.fillWidth: true }
                ToolButton {
                    icon.source: Qt.resolvedUrl("icons/mark-read.svg")
                    icon.width: 18
                    icon.height: 18
                    enabled: monitor.unreadCount > 0 && !popup.needsSignIn
                    onClicked: monitor.markAllRead()
                    Accessible.name: "Mark all as read"
                }
                ToolButton {
                    icon.source: Qt.resolvedUrl("icons/refresh.svg")
                    icon.width: 18
                    icon.height: 18
                    enabled: !monitor.loading && !popup.needsSignIn
                    onClicked: monitor.refresh()
                    Accessible.name: "Refresh notifications"
                }
            }

            Text {
                id: refreshError
                x: 18
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 12
                width: parent.width - 36
                visible: monitor.error !== "" && !popup.needsSignIn && monitor.notifications.length > 0
                text: monitor.error
                textFormat: Text.PlainText
                wrapMode: Text.WordWrap
                maximumLineCount: 3
                elide: Text.ElideRight
                color: github.errorColor
                font.pixelSize: 12
            }

            ListView {
                id: list
                objectName: "notifications"
                x: 8; y: toolbar.y + toolbar.height + 6
                width: parent.width - 16
                height: (refreshError.visible ? refreshError.y : parent.height) - y - 8
                clip: true
                visible: !popup.needsSignIn
                model: monitor.notifications
                spacing: 2
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar {}
                delegate: Item {
                    id: row
                    required property var modelData
                    width: list.width
                    height: 74
                    Accessible.role: Accessible.Button
                    Accessible.name: `${modelData.statusLabel}: ${modelData.title}`
                    Accessible.onPressAction: { monitor.openNotification(modelData.id); popup.close() }
                    Rectangle {
                        anchors.fill: parent
                        radius: 6
                        color: github.foreground
                        opacity: rowMouse.containsMouse ? 0.07 : 0
                    }
                    Image {
                        x: 10; y: 11; width: 18; height: 18
                        sourceSize: Qt.size(18, 18)
                        source: Qt.resolvedUrl(`icons/${row.modelData.statusKey}.svg`)
                    }
                    Text {
                        id: subjectTitle
                        x: 38; y: 9; width: parent.width - 56
                        text: row.modelData.title
                        textFormat: Text.PlainText
                        color: github.foreground
                        font.pixelSize: 14
                        font.weight: row.modelData.unread ? Font.DemiBold : Font.Normal
                        wrapMode: Text.Wrap
                        maximumLineCount: 2
                        elide: Text.ElideRight
                    }
                    Text {
                        id: detailsText
                        x: 38; y: subjectTitle.y + subjectTitle.height + 3
                        width: timestampLabel.x - x - 8
                        text: row.modelData.details ?? ""
                        textFormat: Text.PlainText
                        color: github.secondary
                        font.pixelSize: 12
                        elide: Text.ElideRight
                    }
                    Text {
                        id: timestampLabel
                        anchors.right: parent.right; anchors.rightMargin: 12
                        y: detailsText.y
                        text: github.age(row.modelData.updated_at)
                        color: github.secondary
                        font.pixelSize: 12
                    }
                    Rectangle {
                        x: parent.width - 11; y: 16
                        width: 5; height: 5; radius: 3
                        visible: row.modelData.unread
                        color: "#58a6ff"
                    }
                    MouseArea {
                        id: rowMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: { monitor.openNotification(row.modelData.id); popup.close() }
                    }
                }
            }

            Column {
                anchors.centerIn: parent
                width: parent.width - 48
                spacing: 12
                visible: popup.needsSignIn
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: monitor.authCode ? monitor.authCode : monitor.authBusy ? "Connecting to GitHub…" : "Sign in to GitHub"
                    color: github.foreground
                    font.pixelSize: monitor.authCode ? 24 : 15
                    font.family: monitor.authCode ? "Consolas" : Qt.application.font.family
                }
                Text {
                    width: parent.width
                    text: monitor.authCode ? "Enter this code on GitHub to authorize YASB."
                        : monitor.error || "Connect your account to see notifications."
                    textFormat: Text.PlainText
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    color: github.secondary
                    font.pixelSize: 12
                }
                Row {
                    anchors.horizontalCenter: parent.horizontalCenter
                    spacing: 8
                    Button { text: "Sign in"; visible: !monitor.authBusy; onClicked: monitor.signIn() }
                    Button { text: "Copy code"; visible: monitor.authCode !== ""; onClicked: monitor.copyCode() }
                    Button { text: "Open GitHub"; visible: monitor.authCode !== ""; onClicked: monitor.openSignInPage() }
                    Button { text: "Cancel"; flat: true; visible: monitor.authBusy; onClicked: monitor.cancelSignIn() }
                }
            }

            Column {
                anchors.centerIn: parent
                width: parent.width - 48
                spacing: 12
                visible: !popup.needsSignIn && monitor.notifications.length === 0
                BusyIndicator {
                    anchors.horizontalCenter: parent.horizontalCenter
                    running: monitor.loading && visible
                    visible: monitor.loading
                    width: 28; height: 28
                }
                Text {
                    width: parent.width
                    text: monitor.loading ? "Fetching notifications…"
                        : monitor.error ? "Notifications could not be fetched."
                        : monitor.onlyUnread ? "No unread notifications" : "No notifications"
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    color: github.secondary
                    font.pixelSize: 13
                }
                Text {
                    width: parent.width
                    visible: monitor.error !== "" && !monitor.loading
                    text: monitor.error
                    textFormat: Text.PlainText
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    color: github.errorColor
                    font.pixelSize: 12
                }
            }
        }
    }
}
