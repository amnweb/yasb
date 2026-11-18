pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Effects
import QtQuick.Templates as T
import Yasb
import Yasb.Bar
import Yasb.Themes

Item {
    id: powerMenu

    required property BarBase bar
    readonly property Theme theme: bar.theme
    // The glyph on the bar, drawn in iconFont and the text colour
    property string icon: "\ue7e8"
    property int iconSize: theme.bar.iconFont.pixelSize
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

    readonly property bool dark: theme.dark
    // The icon on the bar takes the theme's text colour unless the widget file sets it
    property color textColor: theme.colors.text
    // Text and icons on the full-screen menu, which is always over a darkened screen
    property color menuColor: "#ffffff"
    // Glyphs take the theme's icon font, each part unless the widget file sets it
    property font iconFont
    iconFont.family: theme.bar.iconFont.family
    iconFont.weight: theme.bar.iconFont.weight
    iconFont.variableAxes: theme.bar.iconFont.variableAxes
    // The popup: the theme's, unless set here
    // The user's name, email and account type, each button's glyph and text, and the uptime, in the theme's
    // popup font family
    property font userNameFont
    userNameFont.family: theme.popup.font.family
    userNameFont.pixelSize: 32
    userNameFont.weight: Font.DemiBold
    property font emailFont
    emailFont.family: theme.popup.font.family
    emailFont.pixelSize: 13
    emailFont.weight: Font.DemiBold
    property font accountTypeFont
    accountTypeFont.family: theme.popup.font.family
    accountTypeFont.pixelSize: 11
    accountTypeFont.weight: Font.DemiBold
    property int buttonIconSize: 24
    property font buttonFont
    buttonFont.family: theme.popup.font.family
    buttonFont.pixelSize: 13
    buttonFont.weight: Font.DemiBold
    property font uptimeFont
    uptimeFont.family: theme.popup.font.family
    uptimeFont.pixelSize: 12

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
        const screen = powerMenu.Screen
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
        text: powerMenu.icon
        color: powerMenu.textColor
        font.family: powerMenu.iconFont.family
        font.weight: powerMenu.iconFont.weight
        font.variableAxes: powerMenu.iconFont.variableAxes
        font.pixelSize: powerMenu.iconSize
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: powerMenu.open()
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
                powerMenu.opened = null
                destroy()
            }

            NumberAnimation {
                id: fadeIn

                target: window
                property: "reveal"
                to: 1
                duration: powerMenu.animationDuration
                easing.type: Easing.OutCubic
            }

            SequentialAnimation {
                id: fadeOut

                NumberAnimation {
                    target: window
                    property: "reveal"
                    to: 0
                    duration: powerMenu.animationDuration
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
                bar: powerMenu.Window.window
                item: shade
            }

            Rectangle {
                id: shade

                anchors.fill: parent
                color: Qt.alpha("#000000", powerMenu.dim)
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
                        visible: powerMenu.showUser
                        spacing: 6

                        Item {
                            id: avatar

                            anchors.horizontalCenter: parent.horizontalCenter
                            width: powerMenu.avatarSize
                            height: powerMenu.avatarSize

                            Rectangle {
                                anchors.fill: parent
                                radius: width / 2
                                color: Qt.alpha(powerMenu.menuColor, 0.1)
                                border.color: Qt.alpha(powerMenu.menuColor, 0.2)
                                visible: picture.status !== Image.Ready

                                Text {
                                    anchors.centerIn: parent
                                    text: "\ue77b"
                                    color: powerMenu.menuColor
                                    font.family: powerMenu.iconFont.family
                                    font.weight: powerMenu.iconFont.weight
                                    font.variableAxes: powerMenu.iconFont.variableAxes
                                    font.pixelSize: Math.round(powerMenu.avatarSize * 0.4)
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
                                    sourceSize: Qt.size(powerMenu.avatarSize * 2, powerMenu.avatarSize * 2)
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
                            color: powerMenu.menuColor
                            font: powerMenu.userNameFont
                        }

                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            visible: text !== ""
                            text: power.email
                            color: Qt.alpha(powerMenu.menuColor, 0.7)
                            font: powerMenu.emailFont
                        }

                        Rectangle {
                            anchors.horizontalCenter: parent.horizontalCenter
                            width: accountLabel.implicitWidth + 16
                            height: accountLabel.implicitHeight + 6
                            radius: height / 2
                            color: Qt.alpha(powerMenu.menuColor, 0.12)

                            Text {
                                id: accountLabel

                                anchors.centerIn: parent
                                text: power.accountType
                                color: Qt.alpha(powerMenu.menuColor, 0.85)
                                font: powerMenu.accountTypeFont
                            }
                        }
                    }

                    Row {
                        id: actions

                        anchors.horizontalCenter: parent.horizontalCenter
                        spacing: 16

                        Repeater {
                            model: powerMenu.buttons

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
                                        color: Qt.alpha(powerMenu.menuColor, button.pressed ? 0.24
                                            : button.hovered || button.visualFocus ? 0.18 : 0.08)
                                        border.width: button.visualFocus ? 2 : 1
                                        border.color: Qt.alpha(powerMenu.menuColor, button.visualFocus ? 0.28 : 0.014)

                                        Text {
                                            anchors.centerIn: parent
                                            text: button.modelData.icon ?? ""
                                            color: powerMenu.menuColor
                                            font.family: powerMenu.iconFont.family
                                            font.weight: powerMenu.iconFont.weight
                                            font.variableAxes: powerMenu.iconFont.variableAxes
                                            font.pixelSize: powerMenu.buttonIconSize
                                        }
                                    }

                                    Text {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        anchors.top: disc.bottom
                                        anchors.topMargin: 10
                                        text: button.text
                                        color: powerMenu.menuColor
                                        font: powerMenu.buttonFont
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
                    visible: powerMenu.showUptime
                    opacity: window.reveal
                    text: powerMenu.uptimeText(power.uptime)
                    color: Qt.alpha(powerMenu.menuColor, 0.7)
                    font: powerMenu.uptimeFont
                }
            }
        }
    }
}
