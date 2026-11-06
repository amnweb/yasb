pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Yasb
import Yasb.Bar
import Yasb.Common

Item {
    id: root

    property BarBase bar: null
    // Label placeholders: {lang[language_code]} {lang[iso_language_code]} {lang[country_code]} {lang[full_name]}
    // {lang[native_country_name]} {lang[native_lang_name]} {lang[layout_name]} {lang[full_layout_name]}
    // {lang[layout_country_name]}. Right-click to show the alternate label.
    property string label: "{lang[language_code]}-{lang[country_code]}"
    property string alternateLabel: "{lang[full_name]}"
    // Milliseconds between reads of the language and caps lock
    property int updateInterval: 1000
    // Icon glyph before the text, using iconFont. Empty hides it.
    property string icon: "\ue765"
    property int iconSize: 16
    // Label and icon color while Caps Lock is on.
    property color capsLockColor: textColor
    property int popupWidth: 300
    // Popup alignment relative to the widget on a horizontal bar: left, right, or center.
    property string popupAlignment: "center"
    // Use layoutIcon for each layout, or its language code when false.
    property bool showLayoutIcon: true
    property string layoutIcon: "\ue765"

    property bool showAlternate: false

    readonly property bool dark: bar ? bar.dark : Application.styleHints.colorScheme === Qt.ColorScheme.Dark
    // Inherit the bar's text color and font unless overridden here.
    property color textColor: bar?.textColor ?? (dark ? "#ffffff" : "#000000")
    property font font
    font.family: bar?.font.family ?? Application.font.family
    font.pixelSize: bar?.font.pixelSize ?? 13
    font.weight: bar?.font.weight ?? Font.Normal
    font.italic: bar?.font.italic ?? false
    font.letterSpacing: bar?.font.letterSpacing ?? 0
    font.capitalization: bar?.font.capitalization ?? Font.MixedCase
    font.variableAxes: bar?.font.variableAxes ?? ({})
    // Inherit icon font family and weight from the bar unless overridden.
    property font iconFont
    iconFont.family: bar?.iconFont.family ?? "Segoe Fluent Icons"
    iconFont.weight: bar?.iconFont.weight ?? Font.Normal
    readonly property color foreground: dark ? "#ebebeb" : "#1f1f1f"
    readonly property color accent: dark ? "#60cdff" : "#005fb8"
    readonly property string edge: bar?.edge ?? "top"

    readonly property var lang: keyboard.language
    readonly property color labelColor: keyboard.capsLock ? capsLockColor : textColor
    readonly property string text: format(showAlternate ? alternateLabel : label)

    function format(template: string): string {
        return template.replace(/\{lang\[(\w+)\]\}/g, (match, key) => lang[key] ?? match)
    }

    function placePopup() {
        const start = mapToGlobal(0, 0)
        const gap = 6
        const margin = 8
        let px
        let py
        switch (edge) {
        case "left":
            px = start.x + width + gap
            py = start.y + (height - popup.height) / 2
            break
        case "right":
            px = start.x - popup.width - gap
            py = start.y + (height - popup.height) / 2
            break
        default:
            px = popupAlignment === "left" ? start.x
                : popupAlignment === "right" ? start.x + width - popup.width : start.x + (width - popup.width) / 2
            py = edge === "bottom" ? start.y - popup.height - gap : start.y + height + gap
            break
        }
        const screen = root.Screen
        px = Math.max(screen.virtualX + margin, Math.min(px, screen.virtualX + screen.width - popup.width - margin))
        py = Math.max(screen.virtualY + margin, Math.min(py, screen.virtualY + screen.desktopAvailableHeight - popup.height - margin))
        popup.x = Math.round(px)
        popup.y = Math.round(py)
    }

    function togglePopup() {
        if (popup.visible)
            popup.close()
        else {
            // Remember the target window before the popup takes focus.
            keyboard.rememberWindow()
            keyboard.refresh()
            placePopup()
            popup.open()
        }
    }

    function choose(id: string) {
        popup.close()
        keyboard.activate(id)
    }

    implicitWidth: row.implicitWidth
    implicitHeight: row.implicitHeight
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: `Input language ${lang.full_name ?? ""}${keyboard.capsLock ? ", caps lock on" : ""}`
    Accessible.onPressAction: togglePopup()
    Keys.onReturnPressed: togglePopup()
    Keys.onSpacePressed: togglePopup()

    Component.onDestruction: popup.hide()

    KeyboardLanguage {
        id: keyboard

        updateInterval: root.updateInterval
    }

    Connections {
        target: root.Window.window
        function onVisibleChanged() {
            if (!root.Window.window?.visible)
                popup.hide()
        }
        function onXChanged() { if (popup.visible) root.placePopup() }
        function onYChanged() { if (popup.visible) root.placePopup() }
    }

    Connections {
        target: popup
        function onHeightChanged() { if (popup.visible) root.placePopup() }
    }

    Row {
        id: row

        height: parent.height
        spacing: 4

        Text {
            objectName: "icon"
            anchors.verticalCenter: parent.verticalCenter
            visible: root.icon !== ""
            text: root.icon
            color: root.labelColor
            font.family: root.iconFont.family
            font.weight: root.iconFont.weight
            font.pixelSize: root.iconSize
        }

        Text {
            objectName: "label"
            anchors.verticalCenter: parent.verticalCenter
            visible: text !== ""
            text: root.text
            textFormat: Text.PlainText
            color: root.labelColor
            font: root.font
        }
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: mouse => {
            if (mouse.button === Qt.LeftButton)
                root.togglePopup()
            else
                root.showAlternate = !root.showAlternate
        }
    }

    BackdropPopup {
        id: popup
        property real reveal: 0
        objectName: "popup"
        title: "Keyboard layouts"
        width: root.popupWidth
        height: column.implicitHeight + 16
        anchor: root
        backdropItem: surface
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: 180; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: 140; easing.type: Easing.InCubic }
        onVisibleChanged: { if (!visible) reveal = 0 }

        Rectangle {
            id: surface
            anchors.fill: parent
            anchors.margins: 8
            radius: 8
            color: root.dark ? Qt.alpha("#202020", 0.85) : Qt.alpha("#F3F3F3", 0.85)
            border.width: 1
            border.color: root.dark ? "#3A3A3A" : "#D9D9D9"
            opacity: popup.reveal
            scale: 0.85 + popup.reveal * 0.15
            transformOrigin: root.edge === "bottom" ? Item.Bottom : Item.Top

            ColumnLayout {
                id: column
                width: parent.width
                spacing: 0

                Text {
                    Layout.fillWidth: true
                    Layout.leftMargin: 16
                    Layout.rightMargin: 16
                    Layout.topMargin: 12
                    Layout.bottomMargin: 8
                    text: "<b>Keyboard</b> Layouts"
                    textFormat: Text.StyledText
                    color: root.foreground
                    font.pixelSize: 16
                }

                Text {
                    Layout.fillWidth: true
                    Layout.leftMargin: 16
                    Layout.bottomMargin: 8
                    visible: keyboard.layouts.length === 0
                    text: "No keyboard layouts"
                    color: Qt.alpha(root.foreground, 0.6)
                    font.pixelSize: 13
                }

                Column {
                    Layout.fillWidth: true
                    Layout.leftMargin: 8
                    Layout.rightMargin: 8
                    Layout.bottomMargin: 8
                    spacing: 2

                    Repeater {
                        model: keyboard.layouts
                        delegate: Rectangle {
                            id: item

                            required property var modelData

                            objectName: "layout"
                            width: parent.width
                            height: 52
                            radius: 4
                            color: Qt.alpha(root.foreground, modelData.current ? 0.06 : itemArea.containsMouse ? 0.04 : 0)
                            Accessible.role: Accessible.RadioButton
                            Accessible.name: `${modelData.name}, ${modelData.layout}`
                            Accessible.checked: modelData.current
                            Accessible.onPressAction: root.choose(modelData.id)

                            // The current layout's mark, as in Windows' own menu
                            Rectangle {
                                anchors.verticalCenter: parent.verticalCenter
                                width: 3
                                height: 16
                                radius: 1.5
                                visible: item.modelData.current
                                color: root.accent
                            }

                            Text {
                                x: 14
                                width: 36
                                anchors.verticalCenter: parent.verticalCenter
                                text: root.showLayoutIcon ? root.layoutIcon : item.modelData.code
                                textFormat: Text.PlainText
                                color: root.foreground
                                opacity: item.modelData.current ? 1 : 0.75
                                font.family: root.showLayoutIcon ? root.iconFont.family : root.font.family
                                font.weight: root.showLayoutIcon ? root.iconFont.weight : Font.DemiBold
                                font.pixelSize: root.showLayoutIcon ? 18 : 12
                            }

                            Column {
                                x: 56
                                width: parent.width - 66
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 2

                                Text {
                                    width: parent.width
                                    text: item.modelData.name
                                    textFormat: Text.PlainText
                                    elide: Text.ElideRight
                                    color: root.foreground
                                    font.pixelSize: 13
                                }

                                Text {
                                    width: parent.width
                                    text: item.modelData.layout
                                    textFormat: Text.PlainText
                                    elide: Text.ElideRight
                                    color: Qt.alpha(root.foreground, 0.65)
                                    font.pixelSize: 12
                                }
                            }

                            MouseArea {
                                id: itemArea
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.choose(item.modelData.id)
                            }
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.leftMargin: 1
                    Layout.rightMargin: 1
                    Layout.bottomMargin: 1
                    implicitHeight: 40
                    bottomLeftRadius: 7
                    bottomRightRadius: 7
                    color: Qt.alpha("#000000", (root.dark ? 0.15 : 0.03) + (footerArea.containsMouse ? 0.05 : 0))
                    Accessible.role: Accessible.Link
                    Accessible.name: "More keyboard settings"
                    Accessible.onPressAction: {
                        Qt.openUrlExternally("ms-settings:regionlanguage")
                        popup.close()
                    }

                    Rectangle {
                        width: parent.width
                        height: 1
                        color: Qt.alpha(root.foreground, 0.08)
                    }

                    Text {
                        anchors.left: parent.left
                        anchors.leftMargin: 15
                        anchors.verticalCenter: parent.verticalCenter
                        text: "More keyboard settings"
                        color: footerArea.containsMouse ? root.foreground : Qt.alpha(root.foreground, 0.75)
                        font.pixelSize: 12
                    }

                    Text {
                        anchors.right: parent.right
                        anchors.rightMargin: 14
                        anchors.verticalCenter: parent.verticalCenter
                        text: ""
                        color: root.foreground
                        opacity: footerArea.containsMouse ? 1 : 0.75
                        font.family: root.iconFont.family
                        font.weight: root.iconFont.weight
                        font.pixelSize: 10
                    }

                    MouseArea {
                        id: footerArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            Qt.openUrlExternally("ms-settings:regionlanguage")
                            popup.close()
                        }
                    }
                }
            }
        }
    }
}
