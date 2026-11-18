pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Yasb
import Yasb.Bar
import Yasb.Common
import Yasb.Themes

Item {
    // Not language: the id would hide KeyboardLanguage's language property
    id: languageWidget

    required property BarBase bar
    readonly property Theme theme: bar.theme
    // Label placeholders: {lang[language_code]} {lang[iso_language_code]} {lang[country_code]} {lang[full_name]}
    // {lang[native_country_name]} {lang[native_lang_name]} {lang[layout_name]} {lang[full_layout_name]}
    // {lang[layout_country_name]}. Right-click to show the alternate label.
    property string label: "{lang[language_code]}-{lang[country_code]}"
    property string alternateLabel: "{lang[full_name]}"
    // Milliseconds between reads of the language and caps lock
    property int updateInterval: 1000
    // Icon glyph before the text, using iconFont. Empty hides it.
    property string icon: "\ue765"
    property int iconSize: theme.bar.iconFont.pixelSize
    // Label and icon color while Caps Lock is on.
    property color capsLockColor: textColor
    property int popupWidth: 284
    // Popup alignment relative to the widget on a horizontal bar: left, right, or center.
    property string popupAlignment: "center"
    // Use layoutIcon for each layout, or its language code when false.
    property bool showLayoutIcon: true
    property string layoutIcon: "\ue765"

    property bool showAlternate: false

    readonly property bool dark: theme.dark
    // Text on the bar takes the theme's colour, and labels the bar's font; parts set in font replace the bar's
    property color textColor: theme.colors.text
    property font font
    // Glyphs take the theme's icon font, each part unless the widget file sets it
    property font iconFont
    iconFont.family: theme.bar.iconFont.family
    iconFont.weight: theme.bar.iconFont.weight
    iconFont.variableAxes: theme.bar.iconFont.variableAxes
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
    property int popupOpenDuration: theme.popup.openDuration
    property int popupCloseDuration: theme.popup.closeDuration
    property color accentColor: theme.colors.accent
    property color popupTextColor: theme.colors.text
    property color popupSecondaryBackgroundColor: theme.colors.backgroundSecondary
    property color popupDividerColor: theme.colors.divider
    property color popupSecondaryTextColor: theme.colors.textSecondary
    property color popupHoverColor: theme.colors.hover
    property color popupSelectedColor: theme.colors.selected
    property font popupTitleFont
    popupTitleFont.family: theme.popup.font.family
    popupTitleFont.pixelSize: 16
    popupTitleFont.weight: Font.DemiBold
    // Each layout's glyph, or its code such as EN when showLayoutIcon is off, and the arrow of the settings link
    property int layoutIconSize: 18
    property font codeFont
    codeFont.family: theme.popup.font.family
    codeFont.pixelSize: 12
    codeFont.weight: Font.DemiBold
    property int footerIconSize: 10
    readonly property string edge: bar.edge

    readonly property var lang: keyboard.language
    readonly property color labelColor: keyboard.capsLock ? capsLockColor : textColor
    readonly property string text: format(showAlternate ? alternateLabel : label)

    function format(template: string): string {
        return template.replace(/\{lang\[(\w+)\]\}/g, (match, key) => lang[key] ?? match)
    }

    function placePopup() {
        const start = mapToGlobal(0, 0)
        const gap = popupGap
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
        const screen = languageWidget.Screen
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

        updateInterval: languageWidget.updateInterval
    }

    Connections {
        target: languageWidget.Window.window
        function onVisibleChanged() {
            if (!languageWidget.Window.window?.visible)
                popup.hide()
        }
        function onXChanged() { if (popup.visible) languageWidget.placePopup() }
        function onYChanged() { if (popup.visible) languageWidget.placePopup() }
    }

    Connections {
        target: popup
        function onHeightChanged() { if (popup.visible) languageWidget.placePopup() }
    }

    Row {
        id: row

        height: parent.height
        spacing: 4

        Text {
            objectName: "icon"
            anchors.verticalCenter: parent.verticalCenter
            visible: languageWidget.icon !== ""
            text: languageWidget.icon
            color: languageWidget.labelColor
            font.family: languageWidget.iconFont.family
            font.weight: languageWidget.iconFont.weight
            font.variableAxes: languageWidget.iconFont.variableAxes
            font.pixelSize: languageWidget.iconSize
        }

        Label {
            objectName: "label"
            anchors.verticalCenter: parent.verticalCenter
            visible: text !== ""
            text: languageWidget.text
            textFormat: Text.PlainText
            color: languageWidget.labelColor
            font: languageWidget.font
        }
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: mouse => {
            if (mouse.button === Qt.LeftButton)
                languageWidget.togglePopup()
            else
                languageWidget.showAlternate = !languageWidget.showAlternate
        }
    }

    BackdropPopup {
        id: popup
        property real reveal: 0
        objectName: "popup"
        title: "Keyboard layouts"
        width: languageWidget.popupWidth
        height: column.implicitHeight
        anchor: languageWidget
        font: languageWidget.popupFont
        theme: languageWidget.theme
        backdropItem: surface
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: languageWidget.popupOpenDuration; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: languageWidget.popupCloseDuration; easing.type: Easing.InCubic }
        onVisibleChanged: { if (!visible) reveal = 0 }

        Rectangle {
            id: surface
            anchors.fill: parent
            radius: languageWidget.popupRadius
            color: languageWidget.popupColor
            border.width: 1
            border.color: languageWidget.popupBorderColor
            opacity: popup.reveal
            scale: 0.85 + popup.reveal * 0.15
            transformOrigin: languageWidget.edge === "bottom" ? Item.Bottom : Item.Top

            ColumnLayout {
                id: column
                width: parent.width
                spacing: 0

                Text {
                    Layout.fillWidth: true
                    Layout.leftMargin: 16
                    Layout.rightMargin: 16
                    Layout.topMargin: 12
                    Layout.bottomMargin: 10
                    text: "Keyboard layouts"
                    font: languageWidget.popupTitleFont
                    color: languageWidget.popupTextColor
                }
                // The header's bottom line
                Rectangle {
                    Layout.fillWidth: true
                    Layout.bottomMargin: 8
                    implicitHeight: 1
                    color: languageWidget.popupDividerColor
                }

                Text {
                    Layout.fillWidth: true
                    Layout.leftMargin: 16
                    Layout.bottomMargin: 8
                    visible: keyboard.layouts.length === 0
                    text: "No keyboard layouts"
                    color: languageWidget.popupSecondaryTextColor
                    font: languageWidget.popupFont
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
                            color: modelData.current ? languageWidget.popupSelectedColor : itemArea.containsMouse ? languageWidget.popupHoverColor : "transparent"
                            Accessible.role: Accessible.RadioButton
                            Accessible.name: `${modelData.name}, ${modelData.layout}`
                            Accessible.checked: modelData.current
                            Accessible.onPressAction: languageWidget.choose(modelData.id)

                            // The current layout's mark, as in Windows' own menu
                            Rectangle {
                                anchors.verticalCenter: parent.verticalCenter
                                width: 3
                                height: 16
                                radius: 1.5
                                visible: item.modelData.current
                                color: languageWidget.accentColor
                            }

                            Text {
                                x: 14
                                width: 36
                                anchors.verticalCenter: parent.verticalCenter
                                text: languageWidget.showLayoutIcon ? languageWidget.layoutIcon : item.modelData.code
                                textFormat: Text.PlainText
                                color: languageWidget.popupTextColor
                                opacity: item.modelData.current ? 1 : 0.75
                                font.family: languageWidget.showLayoutIcon ? languageWidget.iconFont.family : languageWidget.codeFont.family
                                font.weight: languageWidget.showLayoutIcon ? languageWidget.iconFont.weight : languageWidget.codeFont.weight
                                font.pixelSize: languageWidget.showLayoutIcon ? languageWidget.layoutIconSize : languageWidget.codeFont.pixelSize
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
                                    color: languageWidget.popupTextColor
                                    font: languageWidget.popupFont
                                }

                                Text {
                                    width: parent.width
                                    text: item.modelData.layout
                                    textFormat: Text.PlainText
                                    elide: Text.ElideRight
                                    color: languageWidget.popupSecondaryTextColor
                                    font: languageWidget.popupSmallFont
                                }
                            }

                            MouseArea {
                                id: itemArea
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: languageWidget.choose(item.modelData.id)
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
                    bottomLeftRadius: languageWidget.popupRadius - 1
                    bottomRightRadius: languageWidget.popupRadius - 1
                    color: footerArea.containsMouse ? Qt.tint(languageWidget.popupSecondaryBackgroundColor, languageWidget.popupHoverColor) : languageWidget.popupSecondaryBackgroundColor
                    Accessible.role: Accessible.Link
                    Accessible.name: "More keyboard settings"
                    Accessible.onPressAction: {
                        Qt.openUrlExternally("ms-settings:regionlanguage")
                        popup.close()
                    }

                    Rectangle {
                        width: parent.width
                        height: 1
                        color: languageWidget.popupDividerColor
                    }

                    Text {
                        anchors.left: parent.left
                        anchors.leftMargin: 15
                        anchors.verticalCenter: parent.verticalCenter
                        text: "More keyboard settings"
                        color: footerArea.containsMouse ? languageWidget.popupTextColor : languageWidget.popupSecondaryTextColor
                        font: languageWidget.popupSmallFont
                    }

                    Text {
                        anchors.right: parent.right
                        anchors.rightMargin: 14
                        anchors.verticalCenter: parent.verticalCenter
                        text: "\ue76c"
                        color: languageWidget.popupTextColor
                        opacity: footerArea.containsMouse ? 1 : 0.75
                        font.family: languageWidget.iconFont.family
                        font.weight: languageWidget.iconFont.weight
                        font.variableAxes: languageWidget.iconFont.variableAxes
                        font.pixelSize: languageWidget.footerIconSize
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
