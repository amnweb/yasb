import QtQuick
import QtQuick.Controls
import QtQuick.Controls.impl
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
    // The logo on the bar, drawn in the text colour; thicker when the icon font is bold
    property url icon: Qt.resolvedUrl(iconFont.weight >= Font.DemiBold ? "icons/github-bold.svg" : "icons/github.svg")
    property int iconSize: 16
    // Text on the bar takes the bar's colour and font, each part unless the widget file sets it
    property color textColor: bar?.textColor ?? foreground
    property font font
    font.family: bar?.font.family ?? Qt.application.font.family
    font.pixelSize: bar?.font.pixelSize ?? 13
    font.weight: bar?.font.weight ?? Font.Normal
    font.italic: bar?.font.italic ?? false
    font.letterSpacing: bar?.font.letterSpacing ?? 0
    font.capitalization: bar?.font.capitalization ?? Font.MixedCase
    font.variableAxes: bar?.font.variableAxes ?? ({})
    // Glyphs take the family and weight of the bar's icon font unless the widget file sets them
    property font iconFont
    iconFont.family: bar?.iconFont?.family ?? "Segoe Fluent Icons"
    iconFont.weight: bar?.iconFont?.weight ?? Font.Normal
    readonly property bool dark: bar ? bar.dark : Qt.styleHints.colorScheme === Qt.ColorScheme.Dark
    readonly property color foreground: dark ? "#ebebeb" : "#24292f"
    readonly property color secondary: dark ? "#959da5" : "#656d76"
    readonly property color errorColor: dark ? "#ff9991" : "#b42318"
    readonly property string edge: bar?.edge ?? "top"
    property real now: Date.now()

    readonly property bool shown: !hideEmpty || monitor.needsSignIn || monitor.unreadCount > 0 || monitor.error !== ""

    implicitWidth: shown ? label.implicitWidth : 0
    implicitHeight: shown ? label.implicitHeight : 0
    visible: shown
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

    component SvgIcon: IconImage {
        sourceSize: Qt.size(width, height)
    }

    Item {
        id: label
        y: Math.round((parent.height - height) / 2)
        implicitWidth: github.iconSize
        implicitHeight: github.iconSize

        SvgIcon {
            anchors.fill: parent
            source: github.icon
            color: github.textColor
            opacity: monitor.needsSignIn ? 0.55 : 1
        }

        Rectangle {
            x: parent.width - 5
            y: -1
            width: 6
            height: 6
            radius: 3
            visible: monitor.unreadCount > 0
            color: "#ff4545"
        }
    }

    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: mouse => {
            if (mouse.button === Qt.LeftButton) github.togglePopup()
            else monitor.refresh()
        }
    }

    component FilterChip: Text {
        id: chip

        property bool checked: false

        signal clicked

        leftPadding: 10
        rightPadding: 10
        topPadding: 4
        bottomPadding: 4
        color: checked || chipArea.containsMouse ? github.foreground : Qt.alpha(github.foreground, 0.65)
        opacity: enabled ? 1 : 0.4
        font.pixelSize: 12
        Accessible.role: Accessible.RadioButton
        Accessible.checked: checked
        Accessible.onPressAction: chip.clicked()

        Rectangle {
            anchors.fill: parent
            z: -1
            radius: height / 2
            color: Qt.alpha(github.foreground, chip.checked ? 0.1 : chipArea.containsMouse ? 0.05 : 0)
        }

        MouseArea {
            id: chipArea
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: chip.clicked()
        }
    }

    component IconButton: Item {
        id: button

        property string glyph
        property int iconSize: 14
        property bool checked: false
        property string tip

        signal clicked

        implicitWidth: iconSize + 12
        implicitHeight: iconSize + 12
        opacity: enabled ? 1 : 0.4
        Accessible.role: Accessible.Button
        Accessible.name: tip
        Accessible.onPressAction: button.clicked()
        ToolTip.visible: area.containsMouse && tip !== ""
        ToolTip.delay: 500
        ToolTip.text: tip

        Rectangle {
            anchors.fill: parent
            radius: 4
            color: Qt.alpha(github.foreground, area.containsMouse ? 0.08 : button.checked ? 0.06 : 0)
        }

        Text {
            anchors.centerIn: parent
            text: button.glyph
            color: github.foreground
            opacity: button.checked || area.containsMouse ? 1 : 0.6
            font.family: github.iconFont.family
            font.weight: github.iconFont.weight
            font.pixelSize: button.iconSize
        }

        MouseArea {
            id: area
            anchors.fill: parent
            hoverEnabled: true
            onClicked: button.clicked()
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
            radius: 8
            color: github.dark ? Qt.alpha("#202020", 0.85) : Qt.alpha("#F3F3F3", 0.85)
            border.width: 1
            border.color: github.dark ? Qt.alpha("#3A3A3A", 1) : Qt.alpha("#D9D9D9", 1)
            opacity: popup.reveal
            scale: 0.85 + popup.reveal * 0.15
            transformOrigin: github.edge === "bottom" ? Item.Bottom : Item.Top

            RowLayout {
                id: toolbar
                x: 16; y: 12
                width: parent.width - 26
                height: 26
                spacing: 2

                Text {
                    Layout.rightMargin: 10
                    text: "GitHub"
                    color: github.foreground
                    font.pixelSize: 16
                    font.weight: Font.Bold
                }
                FilterChip {
                    text: "All"
                    checked: !monitor.onlyUnread
                    enabled: !popup.needsSignIn
                    onClicked: monitor.onlyUnread = false
                    Accessible.name: "All notifications"
                }
                FilterChip {
                    text: `Unread${monitor.unreadCount ? ` ${monitor.unreadCount}` : ""}`
                    checked: monitor.onlyUnread
                    enabled: !popup.needsSignIn
                    onClicked: monitor.onlyUnread = true
                    Accessible.name: `Unread notifications, ${monitor.unreadCount}`
                }
                Item { Layout.fillWidth: true }
                IconButton {
                    glyph: "\ue73e"
                    tip: "Mark all as read"
                    enabled: monitor.unreadCount > 0 && !popup.needsSignIn
                    onClicked: monitor.markAllRead()
                }
                IconButton {
                    glyph: "\ue72c"
                    tip: "Refresh"
                    enabled: !monitor.loading && !popup.needsSignIn
                    onClicked: monitor.refresh()
                }
            }

            Rectangle {
                id: footer
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.margins: 1
                height: 40
                bottomLeftRadius: 7
                bottomRightRadius: 7
                color: Qt.alpha("#000000", (github.dark ? 0.15 : 0.03) + (footerArea.containsMouse ? 0.05 : 0))
                Accessible.role: Accessible.Link
                Accessible.name: "Open notifications on GitHub"
                Accessible.onPressAction: {
                    Qt.openUrlExternally("https://github.com/notifications")
                    popup.close()
                }

                Rectangle {
                    width: parent.width
                    height: 1
                    color: Qt.alpha(github.foreground, 0.08)
                }

                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: 15
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Open notifications on GitHub"
                    color: footerArea.containsMouse ? github.foreground : Qt.alpha(github.foreground, 0.75)
                    font.pixelSize: 12
                }

                Text {
                    anchors.right: parent.right
                    anchors.rightMargin: 14
                    anchors.verticalCenter: parent.verticalCenter
                    text: "\ue76c"
                    color: github.foreground
                    opacity: footerArea.containsMouse ? 1 : 0.75
                    font.family: github.iconFont.family
                    font.weight: github.iconFont.weight
                    font.pixelSize: 10
                }

                MouseArea {
                    id: footerArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        Qt.openUrlExternally("https://github.com/notifications")
                        popup.close()
                    }
                }
            }

            Text {
                id: refreshError
                x: 18
                anchors.bottom: footer.top
                anchors.bottomMargin: 10
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
                height: (refreshError.visible ? refreshError.y : footer.y) - y - 8
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
                    height: detailsText.y + detailsText.height + 10
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
                        x: 10; y: 11; width: 16; height: 16
                        sourceSize: Qt.size(16, 16)
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
                    text: monitor.authCode ? monitor.authCode : monitor.authBusy ? "Connecting to GitHub..." : "Sign in to GitHub"
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
                    text: monitor.loading ? "Fetching notifications..."
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
