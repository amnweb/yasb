pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Controls.impl
import QtQuick.Layouts
import Yasb
import Yasb.Bar
import Yasb.Common
import Yasb.Themes

Item {
    id: github

    required property BarBase bar
    readonly property Theme theme: bar.theme
    // A personal access token; empty signs in from the popup instead. Environment.value("NAME") reads one from an
    // environment variable, such as one in YASB's .env file, to keep it out of this file
    property string token: ""
    // How often the notifications are fetched, in milliseconds, from 60000 to 3600000
    property int updateInterval: 300000
    // The most notifications fetched, up to 100
    property int maxNotifications: 50
    property bool onlyUnread: false
    // Only notifications for these reasons, such as ["mention", "review_requested"]; empty shows every reason
    property list<string> reasonFilters: []
    // Whether each issue and pull request shows its comment count, which takes a request more for each
    property bool showCommentCount: true
    property bool hideEmpty: false
    property int popupWidth: 424
    property int popupHeight: 624
    // The logo on the bar, drawn in the text colour; thicker when the icon font is bold
    property url icon: Qt.resolvedUrl(iconFont.weight >= Font.DemiBold ? "icons/github-bold.svg" : "icons/github.svg")
    property int iconSize: theme.bar.iconFont.pixelSize
    // Text on the bar takes the theme's colour, and labels the bar's font; parts set in font replace the bar's
    property color textColor: theme.colors.text
    // Glyphs take the theme's icon font, each part unless the widget file sets it
    property font iconFont
    iconFont.family: theme.bar.iconFont.family
    iconFont.weight: theme.bar.iconFont.weight
    iconFont.variableAxes: theme.bar.iconFont.variableAxes
    // The dot on the bar while there is something unread, and on each unread notification
    property color badgeColor: "#ff4545"
    property color unreadColor: "#58a6ff"
    // The popup: the theme's, unless set here
    property color popupColor: theme.popup.background
    property color popupBorderColor: theme.popup.border
    property real popupRadius: theme.popup.radius
    property real popupGap: theme.popup.gap
    // Text in the popup: the theme's font family, in this widget's sizes
    property font popupFont
    popupFont.family: theme.popup.font.family
    popupFont.pixelSize: 13
    property font popupSmallFont
    popupSmallFont.family: theme.popup.font.family
    popupSmallFont.pixelSize: 12
    property font popupTitleFont
    popupTitleFont.family: theme.popup.font.family
    popupTitleFont.pixelSize: 16
    popupTitleFont.weight: Font.DemiBold
    // The arrow of the link to GitHub
    property int footerIconSize: 10
    // Each notification's title, read and unread
    property font notificationFont
    notificationFont.family: theme.popup.font.family
    notificationFont.pixelSize: 14
    property font unreadNotificationFont
    unreadNotificationFont.family: theme.popup.font.family
    unreadNotificationFont.pixelSize: 14
    unreadNotificationFont.weight: Font.DemiBold
    // Signing in: the prompt, and the code to enter on GitHub
    property font signInFont
    signInFont.family: theme.popup.font.family
    signInFont.pixelSize: 15
    property font codeFont
    codeFont.family: "Consolas"
    codeFont.pixelSize: 24
    property int popupOpenDuration: theme.popup.openDuration
    property int popupCloseDuration: theme.popup.closeDuration
    property color popupTextColor: theme.colors.text
    property color popupSecondaryBackgroundColor: theme.colors.backgroundSecondary
    property color popupDividerColor: theme.colors.divider
    property color popupHoverColor: theme.colors.hover
    property color popupSelectedColor: theme.colors.selected
    readonly property bool dark: theme.dark
    property color popupSecondaryTextColor: theme.colors.textSecondary
    readonly property color errorColor: dark ? "#ff9991" : "#b42318"
    readonly property string edge: bar.edge
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
        let px = edge === "left" ? start.x + width + popupGap
            : edge === "right" ? start.x - popup.width - popupGap : start.x + (width - popup.width) / 2
        let py = edge === "top" ? start.y + height + popupGap
            : edge === "bottom" ? start.y - popup.height - popupGap : start.y + (height - popup.height) / 2
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

    GitHubNotifications {
        id: monitor

        token: github.token
        updateInterval: github.updateInterval
        maxNotifications: github.maxNotifications
        onlyUnread: github.onlyUnread
        reasonFilters: github.reasonFilters
        showCommentCount: github.showCommentCount
    }

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
            color: github.badgeColor
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
        color: checked || chipArea.containsMouse ? github.popupTextColor : github.popupSecondaryTextColor
        opacity: enabled ? 1 : 0.4
        font: github.popupSmallFont
        Accessible.role: Accessible.RadioButton
        Accessible.checked: checked
        Accessible.onPressAction: chip.clicked()

        Rectangle {
            anchors.fill: parent
            z: -1
            radius: height / 2
            color: chip.checked ? github.popupSelectedColor : chipArea.containsMouse ? github.popupHoverColor : "transparent"
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
            color: area.containsMouse ? github.popupHoverColor : button.checked ? github.popupSelectedColor : "transparent"
        }

        Text {
            anchors.centerIn: parent
            text: button.glyph
            color: github.popupTextColor
            opacity: button.checked || area.containsMouse ? 1 : 0.6
            font.family: github.iconFont.family
            font.weight: github.iconFont.weight
            font.variableAxes: github.iconFont.variableAxes
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
        height: Math.min(github.popupHeight, github.Screen.height - 40)
        anchor: github
        font: github.popupFont
        theme: github.theme
        backdropItem: surface
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: github.popupOpenDuration; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: github.popupCloseDuration; easing.type: Easing.InCubic }
        onVisibleChanged: { if (!visible) reveal = 0 }

        Rectangle {
            id: surface
            anchors.fill: parent
            radius: github.popupRadius
            color: github.popupColor
            border.width: 1
            border.color: github.popupBorderColor
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
                    color: github.popupTextColor
                    font: github.popupTitleFont
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
            // The header's bottom line
            Rectangle {
                id: headerLine
                y: toolbar.y + toolbar.height + 10
                width: parent.width
                height: 1
                color: github.popupDividerColor
            }

            Rectangle {
                id: footerLink
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.margins: 1
                height: 40
                bottomLeftRadius: github.popupRadius - 1
                bottomRightRadius: github.popupRadius - 1
                color: footerArea.containsMouse ? Qt.tint(github.popupSecondaryBackgroundColor, github.popupHoverColor) : github.popupSecondaryBackgroundColor
                Accessible.role: Accessible.Link
                Accessible.name: "Open notifications on GitHub"
                Accessible.onPressAction: {
                    Qt.openUrlExternally("https://github.com/notifications")
                    popup.close()
                }

                Rectangle {
                    width: parent.width
                    height: 1
                    color: github.popupDividerColor
                }

                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: 15
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Open notifications on GitHub"
                    color: footerArea.containsMouse ? github.popupTextColor : github.popupSecondaryTextColor
                    font: github.popupSmallFont
                }

                Text {
                    anchors.right: parent.right
                    anchors.rightMargin: 14
                    anchors.verticalCenter: parent.verticalCenter
                    text: "\ue76c"
                    color: github.popupTextColor
                    opacity: footerArea.containsMouse ? 1 : 0.75
                    font.family: github.iconFont.family
                    font.weight: github.iconFont.weight
                    font.variableAxes: github.iconFont.variableAxes
                    font.pixelSize: github.footerIconSize
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
                anchors.bottom: footerLink.top
                anchors.bottomMargin: 10
                width: parent.width - 36
                visible: monitor.error !== "" && !popup.needsSignIn && monitor.notifications.length > 0
                text: monitor.error
                textFormat: Text.PlainText
                wrapMode: Text.WordWrap
                maximumLineCount: 3
                elide: Text.ElideRight
                color: github.errorColor
                font: github.popupSmallFont
            }

            ListView {
                id: list
                objectName: "notifications"
                x: 8; y: headerLine.y + headerLine.height + 8
                width: parent.width - 16
                height: (refreshError.visible ? refreshError.y : footerLink.y) - y - 8
                clip: true
                visible: !popup.needsSignIn
                model: monitor.notifications
                spacing: 2
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar {}
                delegate: Item {
                    id: row
                    required property var modelData
                    // Closes the popup first: opening an unread notification marks it read, which replaces the list
                    // and destroys this row
                    function open() {
                        popup.close()
                        monitor.openNotification(modelData.id)
                    }
                    width: list.width
                    height: detailsText.y + detailsText.height + 10
                    Accessible.role: Accessible.Button
                    Accessible.name: `${modelData.statusLabel}: ${modelData.title}`
                    Accessible.onPressAction: open()
                    Rectangle {
                        anchors.fill: parent
                        radius: 6
                        color: github.popupTextColor
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
                        color: github.popupTextColor
                        font: row.modelData.unread ? github.unreadNotificationFont : github.notificationFont
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
                        color: github.popupSecondaryTextColor
                        font: github.popupSmallFont
                        elide: Text.ElideRight
                    }
                    Text {
                        id: timestampLabel
                        anchors.right: parent.right; anchors.rightMargin: 12
                        y: detailsText.y
                        text: github.age(row.modelData.updated_at)
                        color: github.popupSecondaryTextColor
                        font: github.popupSmallFont
                    }
                    Rectangle {
                        x: parent.width - 11; y: 16
                        width: 5; height: 5; radius: 3
                        visible: row.modelData.unread
                        color: github.unreadColor
                    }
                    MouseArea {
                        id: rowMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: row.open()
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
                    color: github.popupTextColor
                    font: monitor.authCode ? github.codeFont : github.signInFont
                }
                Text {
                    width: parent.width
                    text: monitor.authCode ? "Enter this code on GitHub to authorize YASB."
                        : monitor.error || "Connect your account to see notifications."
                    textFormat: Text.PlainText
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    color: github.popupSecondaryTextColor
                    font: github.popupSmallFont
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
                    color: github.popupSecondaryTextColor
                    font: github.popupFont
                }
                Text {
                    width: parent.width
                    visible: monitor.error !== "" && !monitor.loading
                    text: monitor.error
                    textFormat: Text.PlainText
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    color: github.errorColor
                    font: github.popupSmallFont
                }
            }
        }
    }
}
