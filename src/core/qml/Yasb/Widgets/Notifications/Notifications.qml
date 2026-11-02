import QtQuick
import QtQuick.Controls
import QtQuick.Controls.impl
import QtQuick.Effects
import QtQuick.Layouts
import Yasb
import Yasb.Common

Item {
    id: notifications

    property Item bar: null
    property bool hideEmpty: false
    property int popupWidth: 380
    // The popup grows with its notifications up to this height
    property int popupHeight: 560
    // The bell on the bar, an SVG from icons/ in the text colour
    property int iconSize: 16

    readonly property bool dark: bar ? bar.dark : Qt.styleHints.colorScheme === Qt.ColorScheme.Dark
    // Text on the bar takes the bar's colour and font, each part unless the widget file sets it
    property color textColor: bar?.textColor ?? (dark ? "#ffffff" : "#000000")
    property font font
    font.family: bar?.font.family ?? Qt.application.font.family
    font.pixelSize: bar?.font.pixelSize ?? 13
    font.weight: bar?.font.weight ?? Font.Normal
    font.italic: bar?.font.italic ?? false
    font.letterSpacing: bar?.font.letterSpacing ?? 0
    font.capitalization: bar?.font.capitalization ?? Font.MixedCase
    font.variableAxes: bar?.font.variableAxes ?? ({})
    readonly property color foreground: dark ? "#ebebeb" : "#1f1f1f"
    readonly property color secondary: dark ? "#9d9d9d" : "#616161"
    readonly property string edge: bar?.edge ?? "top"
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
        let px = edge === "left" ? start.x + width + 6
            : edge === "right" ? start.x - popup.width - 6 : start.x + (width - popup.width) / 2
        let py = edge === "top" ? start.y + height + 6
            : edge === "bottom" ? start.y - popup.height - 6 : start.y + (height - popup.height) / 2
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

    Timer {
        interval: 30000
        repeat: true
        running: popup.visible
        onTriggered: notifications.now = Date.now()
    }

    component SvgIcon: IconImage {
        sourceSize: Qt.size(width, height)
    }

    Item {
        id: label
        y: Math.round((parent.height - height) / 2)
        implicitWidth: notifications.iconSize
        implicitHeight: notifications.iconSize

        SvgIcon {
            anchors.fill: parent
            source: Qt.resolvedUrl(center.doNotDisturb ? "icons/do-not-disturb.svg" : "icons/bell.svg")
            color: notifications.textColor
        }

        Rectangle {
            objectName: "dot"
            x: parent.width - 6
            y: -1
            width: 6
            height: 6
            radius: 3
            visible: center.notifications.length > 0
            color: "#ff4545"
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

        property url source
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
            color: Qt.alpha(notifications.foreground, area.containsMouse ? 0.08 : button.checked ? 0.06 : 0)
        }

        SvgIcon {
            anchors.centerIn: parent
            width: button.iconSize
            height: button.iconSize
            source: button.source
            color: notifications.foreground
            opacity: button.checked || area.containsMouse ? 1 : 0.6
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
            ? Math.min(column.implicitHeight, notifications.popupHeight - header.implicitHeight - footer.implicitHeight - 44) : 120
        title: "Notifications"
        width: notifications.popupWidth
        height: content.implicitHeight + 16
        anchor: notifications
        backdropItem: surface
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: 180; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: 140; easing.type: Easing.InCubic }
        onVisibleChanged: { if (!visible) reveal = 0 }

        Rectangle {
            id: surface
            anchors.fill: parent
            anchors.margins: 8
            radius: 8
            color: notifications.dark ? Qt.alpha("#202020", 0.85) : Qt.alpha("#F3F3F3", 0.85)
            border.width: 1
            border.color: notifications.dark ? Qt.alpha("#3A3A3A", 1) : Qt.alpha("#D9D9D9", 1)
            opacity: popup.reveal
            scale: 0.85 + popup.reveal * 0.15
            transformOrigin: notifications.edge === "bottom" ? Item.Bottom : Item.Top

            ColumnLayout {
                id: content
                width: parent.width
                spacing: 0

                RowLayout {
                    id: header
                    Layout.fillWidth: true
                    Layout.leftMargin: 16
                    Layout.rightMargin: 10
                    Layout.topMargin: 12
                    Layout.bottomMargin: 8
                    spacing: 2

                    Text {
                        Layout.fillWidth: true
                        text: "Notifications"
                        color: notifications.foreground
                        font.family: "Segoe UI"
                        font.pixelSize: 16
                        font.weight: Font.Bold
                    }
                    IconButton {
                        visible: center.doNotDisturbAvailable
                        source: Qt.resolvedUrl("icons/moon.svg")
                        checked: center.doNotDisturb
                        tip: center.doNotDisturb ? "Do not disturb is on" : "Do not disturb"
                        onClicked: center.setDoNotDisturb(!center.doNotDisturb)
                        Accessible.name: center.doNotDisturb ? "Turn off do not disturb" : "Turn on do not disturb"
                    }
                    IconButton {
                        source: Qt.resolvedUrl("icons/delete.svg")
                        enabled: center.notifications.length > 0
                        tip: "Clear all"
                        onClicked: center.clearAll()
                        Accessible.name: "Clear all"
                    }
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
                        SvgIcon {
                            anchors.horizontalCenter: parent.horizontalCenter
                            width: 28
                            height: 28
                            source: Qt.resolvedUrl("icons/bell.svg")
                            color: notifications.secondary
                        }
                        Text {
                            width: parent.width
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.WordWrap
                            text: center.allowed ? "No new notifications"
                                : "Notification access is turned off in Windows privacy settings"
                            color: notifications.secondary
                            font.family: "Segoe UI"
                            font.pixelSize: 13
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
                                            color: notifications.secondary
                                            font.family: "Segoe UI"
                                            font.pixelSize: 12
                                            font.weight: Font.DemiBold
                                            elide: Text.ElideRight
                                        }
                                        IconButton {
                                            visible: group.modelData.appId !== ""
                                            source: Qt.resolvedUrl("icons/dismiss.svg")
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
                                            color: Qt.alpha(notifications.foreground, hover.hovered ? 0.06 : 0.03)
                                            border.width: 1
                                            border.color: Qt.alpha(notifications.foreground, 0.04)
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
                                                                color: notifications.foreground
                                                                font.family: "Segoe UI"
                                                                font.pixelSize: 13
                                                                font.weight: Font.DemiBold
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
                                                                    color: notifications.secondary
                                                                    font.family: "Segoe UI"
                                                                    font.pixelSize: 11
                                                                }
                                                                IconButton {
                                                                    anchors.centerIn: parent
                                                                    implicitWidth: 22
                                                                    implicitHeight: 22
                                                                    visible: hover.hovered
                                                                    source: Qt.resolvedUrl("icons/dismiss.svg")
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
                                                            color: Qt.alpha(notifications.foreground, 0.85)
                                                            font.family: "Segoe UI"
                                                            font.pixelSize: 12
                                                            wrapMode: Text.Wrap
                                                            maximumLineCount: 4
                                                            elide: Text.ElideRight
                                                        }
                                                        Text {
                                                            Layout.fillWidth: true
                                                            visible: text !== ""
                                                            text: card.modelData.attribution
                                                            textFormat: Text.PlainText
                                                            color: notifications.secondary
                                                            font.family: "Segoe UI"
                                                            font.pixelSize: 11
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
                    bottomLeftRadius: 7
                    bottomRightRadius: 7
                    color: Qt.alpha("#000000", (notifications.dark ? 0.15 : 0.03) + (footerArea.containsMouse ? 0.05 : 0))
                    Accessible.role: Accessible.Button
                    Accessible.name: "Open Notification Center"
                    Accessible.onPressAction: {
                        center.openNotificationCenter()
                        popup.close()
                    }

                    Rectangle {
                        width: parent.width
                        height: 1
                        color: Qt.alpha(notifications.foreground, 0.08)
                    }

                    Text {
                        anchors.left: parent.left
                        anchors.leftMargin: 15
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Open Notification Center"
                        color: footerArea.containsMouse ? notifications.foreground : Qt.alpha(notifications.foreground, 0.75)
                        font.family: "Segoe UI"
                        font.pixelSize: 12
                    }

                    SvgIcon {
                        anchors.right: parent.right
                        anchors.rightMargin: 14
                        anchors.verticalCenter: parent.verticalCenter
                        width: 10
                        height: 10
                        source: Qt.resolvedUrl("icons/chevron-right.svg")
                        color: notifications.foreground
                        opacity: footerArea.containsMouse ? 1 : 0.75
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
