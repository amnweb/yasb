import QtQuick
import QtQuick.Effects
import QtQuick.Templates as T
import Yasb

Item {
    id: menu

    property Item bar: null
    // The glyph on the bar, drawn in iconFont and the text colour
    property string icon: "\ue7e8"
    property int iconSize: 16
    // The buttons, in order, each with a glyph from iconFont. Actions: lock, signout, sleep, hibernate, restart, shutdown, force_restart, force_shutdown
    property var buttons: [
        { action: "lock", label: qsTr("Lock"), icon: "\ue72e" },
        { action: "signout", label: qsTr("Sign out"), icon: "\uf3b1" },
        { action: "sleep", label: qsTr("Sleep"), icon: "\ue708" },
        { action: "restart", label: qsTr("Restart"), icon: "\ue777" },
        { action: "shutdown", label: qsTr("Shut down"), icon: "\ue7e8" }
    ]
    // Your picture, name, email and account type above the buttons
    property bool showUser: true
    property int avatarSize: 96
    property bool showUptime: true
    // How dark the screen gets behind the menu, 0 to 1; it is also blurred when the bar has a backdrop
    property real dim: 0.4
    // Fade in and out, in milliseconds
    property int animationDuration: 200

    readonly property bool dark: bar ? bar.dark : Qt.styleHints.colorScheme === Qt.ColorScheme.Dark
    // The icon on the bar takes the bar's text colour unless the widget file sets it
    property color textColor: bar?.textColor ?? (dark ? "#ffffff" : "#000000")
    // Text and icons on the full-screen menu, which is always over a darkened screen
    property color menuColor: "#ffffff"
    property font font
    font.family: bar?.font.family ?? Qt.application.font.family
    font.pixelSize: bar?.font.pixelSize ?? 13
    // Glyphs take the family and weight of the bar's icon font unless the widget file sets them
    property font iconFont
    iconFont.family: bar?.iconFont?.family ?? "Segoe Fluent Icons"
    iconFont.weight: bar?.iconFont?.weight ?? Font.Normal

    // Held so the garbage collector doesn't destroy the open menu
    property Window opened: null

    implicitWidth: iconSize
    implicitHeight: iconSize
    Accessible.role: Accessible.Button
    Accessible.name: qsTr("Power menu")
    Accessible.onPressAction: open()

    function open() {
        if (opened)
            return
        const screen = menu.Screen
        opened = overlay.createObject(null, {
            area: Qt.rect(screen.virtualX, screen.virtualY, screen.width, screen.height)
        })
    }

    function uptimeText(seconds: int): string {
        const days = Math.floor(seconds / 86400)
        const hours = Math.floor(seconds % 86400 / 3600)
        const minutes = Math.floor(seconds % 3600 / 60)
        if (days > 0)
            return qsTr("Up %1 d %2 h").arg(days).arg(hours)
        if (hours > 0)
            return qsTr("Up %1 h %2 min").arg(hours).arg(minutes)
        return qsTr("Up %1 min").arg(minutes)
    }

    PowerSession {
        id: power
    }

    Text {
        anchors.centerIn: parent
        text: menu.icon
        color: menu.textColor
        font.family: menu.iconFont.family
        font.weight: menu.iconFont.weight
        font.pixelSize: menu.iconSize
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: menu.open()
    }

    Component {
        id: overlay

        Window {
            id: window

            required property rect area
            property real reveal: 0
            // The action to run once the menu has faded out, "" to only close
            property string pending: ""

            function dismiss(action: string) {
                if (fadeOut.running)
                    return
                pending = action
                fadeIn.stop()
                fadeOut.start()
            }

            flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
            color: "transparent"
            x: area.x
            y: area.y
            width: area.width
            height: area.height

            Component.onCompleted: {
                power.refresh()
                visible = true
                requestActivate()
                fadeIn.start()
            }

            onActiveChanged: {
                if (!active)
                    dismiss("")
            }

            onVisibleChanged: {
                if (visible)
                    return
                // Cleared now, the window itself is deleted later, so the menu can open again straight away
                menu.opened = null
                destroy()
            }

            NumberAnimation {
                id: fadeIn

                target: window
                property: "reveal"
                to: 1
                duration: menu.animationDuration
                easing.type: Easing.OutCubic
            }

            SequentialAnimation {
                id: fadeOut

                NumberAnimation {
                    target: window
                    property: "reveal"
                    to: 0
                    duration: menu.animationDuration
                    easing.type: Easing.InCubic
                }

                ScriptAction {
                    script: {
                        const action = window.pending
                        window.close()
                        if (action)
                            power.run(action)
                    }
                }
            }

            // Blurred behind when the bar has a backdrop, like the bar's popups, and fading with the menu
            Backdrop {
                bar: menu.Window.window
                item: shade
            }

            Rectangle {
                id: shade

                anchors.fill: parent
                color: Qt.alpha("#000000", menu.dim)
                opacity: window.reveal
            }

            // A click anywhere but a button closes the menu
            MouseArea {
                anchors.fill: parent
                onClicked: window.dismiss("")
            }

            FocusScope {
                anchors.fill: parent
                focus: true
                Keys.onEscapePressed: window.dismiss("")

                Column {
                    anchors.centerIn: parent
                    spacing: 48
                    opacity: window.reveal
                    scale: 0.86 + 0.14 * window.reveal

                    Column {
                        anchors.horizontalCenter: parent.horizontalCenter
                        visible: menu.showUser
                        spacing: 6

                        Item {
                            id: avatar

                            anchors.horizontalCenter: parent.horizontalCenter
                            width: menu.avatarSize
                            height: menu.avatarSize

                            Rectangle {
                                anchors.fill: parent
                                radius: width / 2
                                color: Qt.alpha(menu.menuColor, 0.1)
                                border.color: Qt.alpha(menu.menuColor, 0.2)
                                visible: picture.status !== Image.Ready

                                Text {
                                    anchors.centerIn: parent
                                    text: "\ue77b"
                                    color: menu.menuColor
                                    font.family: menu.iconFont.family
                                    font.weight: menu.iconFont.weight
                                    font.pixelSize: Math.round(menu.avatarSize * 0.4)
                                }
                            }

                            Item {
                                anchors.fill: parent
                                visible: picture.status === Image.Ready
                                layer.enabled: visible
                                layer.effect: MultiEffect {
                                    maskEnabled: true
                                    maskSource: circle
                                    maskThresholdMin: 0.5
                                    maskSpreadAtMin: 1
                                }

                                Image {
                                    id: picture

                                    anchors.fill: parent
                                    source: power.avatar
                                    sourceSize: Qt.size(menu.avatarSize * 2, menu.avatarSize * 2)
                                    fillMode: Image.PreserveAspectCrop
                                    asynchronous: true
                                }

                                Rectangle {
                                    id: circle

                                    anchors.fill: parent
                                    radius: width / 2
                                    visible: false
                                    layer.enabled: true
                                }
                            }
                        }

                        Item {
                            width: 1
                            height: 8
                        }

                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: power.userName
                            color: menu.menuColor
                            font.family: menu.font.family
                            font.pixelSize: 32
                            font.weight: Font.DemiBold
                        }

                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            visible: text !== ""
                            text: power.email
                            color: Qt.alpha(menu.menuColor, 0.7)
                            font.weight: Font.DemiBold
                            font.family: menu.font.family
                            font.pixelSize: 13
                        }

                        Rectangle {
                            anchors.horizontalCenter: parent.horizontalCenter
                            width: accountLabel.implicitWidth + 16
                            height: accountLabel.implicitHeight + 6
                            radius: height / 2
                            color: Qt.alpha(menu.menuColor, 0.12)

                            Text {
                                id: accountLabel

                                anchors.centerIn: parent
                                text: power.accountType
                                color: Qt.alpha(menu.menuColor, 0.85)
                                font.family: menu.font.family
                                font.weight: Font.DemiBold
                                font.pixelSize: 11
                            }
                        }
                    }

                    Row {
                        id: actions

                        anchors.horizontalCenter: parent.horizontalCenter
                        spacing: 16

                        Repeater {
                            model: menu.buttons

                            T.AbstractButton {
                                id: button

                                required property var modelData
                                required property int index

                                objectName: `power-${modelData.action}`
                                width: 88
                                height: 100
                                focus: index === 0
                                text: modelData.label ?? modelData.action
                                Accessible.name: text
                                onClicked: window.dismiss(modelData.action)
                                Keys.onReturnPressed: clicked()
                                Keys.onEnterPressed: clicked()
                                Keys.onRightPressed: nextItemInFocusChain(true)?.forceActiveFocus(Qt.TabFocusReason)
                                Keys.onLeftPressed: nextItemInFocusChain(false)?.forceActiveFocus(Qt.BacktabFocusReason)

                                contentItem: Item {
                                    Rectangle {
                                        id: disc

                                        anchors.horizontalCenter: parent.horizontalCenter
                                        width: 88
                                        height: 88
                                        radius: 44
                                        color: Qt.alpha(menu.menuColor, button.pressed ? 0.24
                                            : button.hovered || button.visualFocus ? 0.18 : 0.08)
                                        border.width: button.visualFocus ? 2 : 1
                                        border.color: Qt.alpha(menu.menuColor, button.visualFocus ? 0.28 : 0.014)

                                        Text {
                                            anchors.centerIn: parent
                                            text: button.modelData.icon ?? ""
                                            color: menu.menuColor
                                            font.family: menu.iconFont.family
                                            font.weight: menu.iconFont.weight
                                            font.pixelSize: 24
                                        }
                                    }

                                    Text {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        anchors.top: disc.bottom
                                        anchors.topMargin: 10
                                        text: button.text
                                        color: menu.menuColor
                                        font.family: menu.font.family
                                        font.pixelSize: 13
                                        font.weight: Font.DemiBold
                                    }
                                }
                            }
                        }
                    }
                }

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 48
                    visible: menu.showUptime
                    opacity: window.reveal
                    text: menu.uptimeText(power.uptime)
                    color: Qt.alpha(menu.menuColor, 0.7)
                    font.family: menu.font.family
                    font.pixelSize: 12
                }
            }
        }
    }
}
