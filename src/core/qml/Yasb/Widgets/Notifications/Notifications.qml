pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Effects
import QtQuick.Layouts
import Yasb
import Yasb.Bar
import Yasb.Common
import Yasb.Themes

Item {
    id: notifications

    required property BarBase bar
    readonly property Theme theme: bar.theme
    property bool hideEmpty: false
    property int popupWidth: 364
    // The popup grows with its notifications up to this height
    property int popupHeight: 544
    // The bell on the bar, drawn in iconFont and the text colour
    property int iconSize: theme.bar.iconFont.pixelSize

    readonly property bool dark: theme.dark
    // Text on the bar takes the theme's colour, and labels the bar's font; parts set in font replace the bar's
    property color textColor: theme.colors.text
    // Glyphs take the theme's icon font, each part unless the widget file sets it
    property font iconFont
    iconFont.family: theme.bar.iconFont.family
    iconFont.weight: theme.bar.iconFont.weight
    iconFont.variableAxes: theme.bar.iconFont.variableAxes
    // The dot on the bar while there are notifications
    property color badgeColor: "#ff4545"
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
    // The glyph when there are no notifications, and the arrow of the settings link
    property int emptyIconSize: 28
    property int footerIconSize: 10
    // Each app's name over its notifications; each notification's title, age and attribution
    property font appNameFont
    appNameFont.family: theme.popup.font.family
    appNameFont.pixelSize: 12
    appNameFont.weight: Font.DemiBold
    property font notificationTitleFont
    notificationTitleFont.family: theme.popup.font.family
    notificationTitleFont.pixelSize: 13
    notificationTitleFont.weight: Font.DemiBold
    property font timeFont
    timeFont.family: theme.popup.font.family
    timeFont.pixelSize: 11
    property font attributionFont
    attributionFont.family: theme.popup.font.family
    attributionFont.pixelSize: 11
    property int popupOpenDuration: theme.popup.openDuration
    property int popupCloseDuration: theme.popup.closeDuration
    property color popupSecondaryTextColor: theme.colors.textSecondary
    property color popupTextColor: theme.colors.text
    property color popupSecondaryBackgroundColor: theme.colors.backgroundSecondary
    property color popupDividerColor: theme.colors.divider
    property color popupHoverColor: theme.colors.hover
    property color popupSelectedColor: theme.colors.selected
    property color popupCardColor: theme.colors.card
    property color popupCardBorderColor: theme.colors.cardBorder
    readonly property string edge: bar.edge
    property real now: Date.now()
    readonly property var groups: {
        const groups = []
        const byApp = new Map()
        for (const item of center.notifications) {
            const key = `${item.appId}|${item.appName}`
            let group = byApp.get(key)
            if (!group) {
                group = { appId: item.appId, appName: item.appName, icon: item.icon, items: [] }
                byApp.set(key, group)
                groups.push(group)
            }
            group.items.push(item)
        }
        return groups
    }

    function age(time: real): string {
        const seconds = Math.max(0, (now - time) / 1000)
        if (seconds < 60) return "now"
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m`
        if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`
        return `${Math.floor(seconds / 86400)}d`
    }

    function placePopup() {
        const start = mapToGlobal(0, 0)
        let px = edge === "left" ? start.x + width + popupGap
            : edge === "right" ? start.x - popup.width - popupGap : start.x + (width - popup.width) / 2
        let py = edge === "top" ? start.y + height + popupGap
            : edge === "bottom" ? start.y - popup.height - popupGap : start.y + (height - popup.height) / 2
        const screen = notifications.Screen
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
            center.refresh()
            placePopup()
            popup.open()
        }
    }

    readonly property bool shown: !hideEmpty || center.notifications.length > 0

    implicitWidth: shown ? label.implicitWidth : 0
    implicitHeight: shown ? label.implicitHeight : 0
    visible: shown
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: `Notifications, ${center.notifications.length}`
    Accessible.onPressAction: togglePopup()
    Keys.onReturnPressed: togglePopup()
    Keys.onSpacePressed: togglePopup()

    Component.onDestruction: popup.hide()

    NotificationCenter { id: center }

    Connections {
        target: notifications.Window.window
        function onVisibleChanged() {
            if (!notifications.Window.window?.visible)
                popup.hide()
        }
        function onXChanged() { if (popup.visible) notifications.placePopup() }
        function onYChanged() { if (popup.visible) notifications.placePopup() }
    }

    // Keep the popup anchored when its height changes
    Connections {
        target: popup
        function onHeightChanged() { if (popup.visible) notifications.placePopup() }
    }

    Timer {
        interval: 30000
        repeat: true
        running: popup.visible
        onTriggered: notifications.now = Date.now()
    }

    Item {
        id: label
        y: Math.round((parent.height - height) / 2)
        implicitWidth: notifications.iconSize
        implicitHeight: notifications.iconSize

        Text {
            anchors.centerIn: parent
            text: center.doNotDisturb ? "\ue7ed" : "\uea8f"
            color: notifications.textColor
            font.family: notifications.iconFont.family
            font.weight: notifications.iconFont.weight
            font.variableAxes: notifications.iconFont.variableAxes
            font.pixelSize: notifications.iconSize
        }

        Rectangle {
            objectName: "dot"
            x: parent.width - 6
            y: -1
            width: 6
            height: 6
            radius: 3
            visible: center.notifications.length > 0
            color: notifications.badgeColor
        }
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: mouse => {
            if (mouse.button === Qt.LeftButton)
                notifications.togglePopup()
            else
                center.openNotificationCenter()
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
        Accessible.onPressAction: button.clicked()
        ToolTip.visible: area.containsMouse && tip !== ""
        ToolTip.delay: 500
        ToolTip.text: tip

        Rectangle {
            anchors.fill: parent
            radius: 4
            color: area.containsMouse ? notifications.popupHoverColor : button.checked ? notifications.popupSelectedColor : "transparent"
        }

        Text {
            anchors.centerIn: parent
            text: button.glyph
            color: notifications.popupTextColor
            opacity: button.checked || area.containsMouse ? 1 : 0.6
            font.family: notifications.iconFont.family
            font.weight: notifications.iconFont.weight
            font.variableAxes: notifications.iconFont.variableAxes
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
        readonly property real listHeight: notifications.groups.length > 0
            ? Math.min(column.implicitHeight, notifications.popupHeight - header.implicitHeight - footer.implicitHeight - 28) : 120
        title: "Notifications"
        width: notifications.popupWidth
        height: popupContent.implicitHeight
        anchor: notifications
        font: notifications.popupFont
        theme: notifications.theme
        backdropItem: surface
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: notifications.popupOpenDuration; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: notifications.popupCloseDuration; easing.type: Easing.InCubic }
        onVisibleChanged: { if (!visible) reveal = 0 }

        Rectangle {
            id: surface
            anchors.fill: parent
            radius: notifications.popupRadius
            color: notifications.popupColor
            border.width: 1
            border.color: notifications.popupBorderColor
            opacity: popup.reveal
            scale: 0.85 + popup.reveal * 0.15
            transformOrigin: notifications.edge === "bottom" ? Item.Bottom : Item.Top

            ColumnLayout {
                id: popupContent
                width: parent.width
                spacing: 0

                RowLayout {
                    id: header
                    Layout.fillWidth: true
                    Layout.leftMargin: 16
                    Layout.rightMargin: 10
                    Layout.topMargin: 12
                    Layout.bottomMargin: 10
                    spacing: 2

                    Text {
                        Layout.fillWidth: true
                        text: "Notifications"
                        color: notifications.popupTextColor
                        font: notifications.popupTitleFont
                    }
                    IconButton {
                        visible: center.doNotDisturbAvailable
                        glyph: "\ue7ed"
                        checked: center.doNotDisturb
                        tip: center.doNotDisturb ? "Do not disturb is on" : "Do not disturb"
                        onClicked: center.setDoNotDisturb(!center.doNotDisturb)
                        Accessible.name: center.doNotDisturb ? "Turn off do not disturb" : "Turn on do not disturb"
                    }
                    IconButton {
                        glyph: "\ue74d"
                        enabled: center.notifications.length > 0
                        tip: "Clear all"
                        onClicked: center.clearAll()
                        Accessible.name: "Clear all"
                    }
                }
                // The header's bottom line
                Rectangle {
                    Layout.fillWidth: true
                    Layout.bottomMargin: 8
                    implicitHeight: 1
                    color: notifications.popupDividerColor
                }

                Item {
                    Layout.fillWidth: true
                    Layout.leftMargin: 8
                    Layout.rightMargin: 8
                    Layout.preferredHeight: popup.listHeight

                    Column {
                        anchors.centerIn: parent
                        width: parent.width - 32
                        spacing: 10
                        visible: notifications.groups.length === 0
                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: "\uea8f"
                            color: notifications.popupSecondaryTextColor
                            font.family: notifications.iconFont.family
                            font.weight: notifications.iconFont.weight
                            font.variableAxes: notifications.iconFont.variableAxes
                            font.pixelSize: notifications.emptyIconSize
                        }
                        Text {
                            width: parent.width
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.WordWrap
                            text: center.allowed ? "No new notifications"
                                : "Notification access is turned off in Windows privacy settings"
                            color: notifications.popupSecondaryTextColor
                            font: notifications.popupFont
                        }
                    }

                    Flickable {
                        id: list
                        anchors.fill: parent
                        visible: notifications.groups.length > 0
                        contentHeight: column.implicitHeight
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.vertical: ScrollBar {}

                        Column {
                            id: column
                            width: list.width
                            spacing: 14

                            Repeater {
                                model: notifications.groups
                                delegate: Column {
                                    id: group
                                    required property var modelData
                                    width: column.width
                                    spacing: 6

                                    RowLayout {
                                        width: parent.width
                                        spacing: 8
                                        Image {
                                            Layout.leftMargin: 4
                                            Layout.preferredWidth: 16
                                            Layout.preferredHeight: 16
                                            visible: group.modelData.icon !== ""
                                            source: group.modelData.icon
                                            sourceSize: Qt.size(16, 16)
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: group.modelData.appName
                                            textFormat: Text.PlainText
                                            color: notifications.popupSecondaryTextColor
                                            font: notifications.appNameFont
                                            elide: Text.ElideRight
                                        }
                                        IconButton {
                                            visible: group.modelData.appId !== ""
                                            glyph: "\ue711"
                                            iconSize: 10
                                            tip: `Clear ${group.modelData.appName}`
                                            onClicked: center.clearApp(group.modelData.appId)
                                            Accessible.name: `Clear ${group.modelData.appName}`
                                        }
                                    }

                                    Repeater {
                                        model: group.modelData.items
                                        delegate: Rectangle {
                                            id: card
                                            required property var modelData
                                            width: group.width
                                            height: body.implicitHeight + 20
                                            radius: 8
                                            color: hover.hovered ? Qt.tint(notifications.popupCardColor, notifications.popupHoverColor) : notifications.popupCardColor
                                            border.width: 1
                                            border.color: notifications.popupCardBorderColor
                                            Accessible.role: Accessible.Button
                                            Accessible.name: `${modelData.title}. ${modelData.body}`
                                            Accessible.onPressAction: {
                                                center.activate(modelData.id)
                                                popup.close()
                                            }

                                            HoverHandler {
                                                id: hover
                                            }
                                            MouseArea {
                                                anchors.fill: parent
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: {
                                                    center.activate(card.modelData.id)
                                                    popup.close()
                                                }
                                            }

                                            ColumnLayout {
                                                id: body
                                                x: 10
                                                y: 10
                                                width: parent.width - 20
                                                spacing: 8

                                                Image {
                                                    Layout.fillWidth: true
                                                    Layout.preferredHeight: Math.round(width / 2)
                                                    visible: card.modelData.hero !== ""
                                                    source: card.modelData.hero
                                                    sourceSize.width: width * 2
                                                    fillMode: Image.PreserveAspectCrop
                                                    asynchronous: true
                                                    clip: true
                                                }

                                                RowLayout {
                                                    Layout.fillWidth: true
                                                    spacing: 10

                                                    Item {
                                                        Layout.preferredWidth: 36
                                                        Layout.preferredHeight: 36
                                                        Layout.alignment: Qt.AlignTop
                                                        visible: card.modelData.logo !== ""
                                                        Image {
                                                            id: logo
                                                            anchors.fill: parent
                                                            visible: !card.modelData.logoCircle
                                                            source: card.modelData.logo
                                                            sourceSize: Qt.size(72, 72)
                                                            fillMode: Image.PreserveAspectCrop
                                                            asynchronous: true
                                                        }
                                                        MultiEffect {
                                                            anchors.fill: parent
                                                            visible: card.modelData.logoCircle
                                                            source: logo
                                                            maskEnabled: true
                                                            maskSource: circle
                                                        }
                                                        Rectangle {
                                                            id: circle
                                                            anchors.fill: parent
                                                            radius: width / 2
                                                            visible: false
                                                            layer.enabled: true
                                                        }
                                                    }

                                                    ColumnLayout {
                                                        Layout.fillWidth: true
                                                        spacing: 2
                                                        RowLayout {
                                                            Layout.fillWidth: true
                                                            spacing: 6
                                                            Text {
                                                                Layout.fillWidth: true
                                                                text: card.modelData.title
                                                                textFormat: Text.PlainText
                                                                color: notifications.popupTextColor
                                                                font: notifications.notificationTitleFont
                                                                elide: Text.ElideRight
                                                            }
                                                            Item {
                                                                Layout.preferredWidth: 24
                                                                Layout.preferredHeight: 20
                                                                Text {
                                                                    anchors.right: parent.right
                                                                    anchors.verticalCenter: parent.verticalCenter
                                                                    visible: !hover.hovered
                                                                    text: notifications.age(card.modelData.time)
                                                                    color: notifications.popupSecondaryTextColor
                                                                    font: notifications.timeFont
                                                                }
                                                                IconButton {
                                                                    anchors.centerIn: parent
                                                                    implicitWidth: 22
                                                                    implicitHeight: 22
                                                                    visible: hover.hovered
                                                                    glyph: "\ue711"
                                                                    iconSize: 10
                                                                    onClicked: center.dismiss(card.modelData.id)
                                                                    Accessible.name: "Dismiss"
                                                                }
                                                            }
                                                        }
                                                        Text {
                                                            Layout.fillWidth: true
                                                            visible: text !== ""
                                                            text: card.modelData.body
                                                            textFormat: Text.PlainText
                                                            color: notifications.popupSecondaryTextColor
                                                            font: notifications.popupSmallFont
                                                            wrapMode: Text.Wrap
                                                            maximumLineCount: 4
                                                            elide: Text.ElideRight
                                                        }
                                                        Text {
                                                            Layout.fillWidth: true
                                                            visible: text !== ""
                                                            text: card.modelData.attribution
                                                            textFormat: Text.PlainText
                                                            color: notifications.popupSecondaryTextColor
                                                            font: notifications.attributionFont
                                                            elide: Text.ElideRight
                                                        }
                                                    }
                                                }

                                                Image {
                                                    Layout.fillWidth: true
                                                    Layout.preferredHeight: Math.min(160, implicitHeight * width / Math.max(1, implicitWidth))
                                                    visible: card.modelData.image !== ""
                                                    source: card.modelData.image
                                                    sourceSize.width: width * 2
                                                    fillMode: Image.PreserveAspectFit
                                                    horizontalAlignment: Image.AlignLeft
                                                    asynchronous: true
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    id: footer
                    Layout.fillWidth: true
                    Layout.topMargin: 8
                    Layout.leftMargin: 1
                    Layout.rightMargin: 1
                    Layout.bottomMargin: 1
                    implicitHeight: 40
                    bottomLeftRadius: notifications.popupRadius - 1
                    bottomRightRadius: notifications.popupRadius - 1
                    color: footerArea.containsMouse ? Qt.tint(notifications.popupSecondaryBackgroundColor, notifications.popupHoverColor) : notifications.popupSecondaryBackgroundColor
                    Accessible.role: Accessible.Button
                    Accessible.name: "Open Notification Center"
                    Accessible.onPressAction: {
                        center.openNotificationCenter()
                        popup.close()
                    }

                    Rectangle {
                        width: parent.width
                        height: 1
                        color: notifications.popupDividerColor
                    }

                    Text {
                        anchors.left: parent.left
                        anchors.leftMargin: 15
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Open Notification Center"
                        color: footerArea.containsMouse ? notifications.popupTextColor : notifications.popupSecondaryTextColor
                        font: notifications.popupSmallFont
                    }

                    Text {
                        anchors.right: parent.right
                        anchors.rightMargin: 14
                        anchors.verticalCenter: parent.verticalCenter
                        text: "\ue76c"
                        color: notifications.popupTextColor
                        opacity: footerArea.containsMouse ? 1 : 0.75
                        font.family: notifications.iconFont.family
                        font.weight: notifications.iconFont.weight
                        font.variableAxes: notifications.iconFont.variableAxes
                        font.pixelSize: notifications.footerIconSize
                    }

                    MouseArea {
                        id: footerArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            center.openNotificationCenter()
                            popup.close()
                        }
                    }
                }
            }
        }
    }
}
