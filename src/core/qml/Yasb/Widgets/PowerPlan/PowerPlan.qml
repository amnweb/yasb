pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Yasb
import Yasb.Bar
import Yasb.Common
import Yasb.Themes

Item {
    id: powerPlan

    required property BarBase bar
    readonly property Theme theme: bar.theme
    // Both labels can use {active_plan}.
    property string label: "{active_plan}"
    property string alternateLabel: qsTr("Power Plan")
    property bool showAlternate: false
    property string icon: "\ue945"
    property int iconSize: theme.bar.iconFont.pixelSize
    property bool tooltip: true
    property string hotkey: ""
    property string alternateHotkey: ""
    property int popupWidth: 284
    property string popupAlignment: "center"
    property int maxListHeight: 320

    readonly property bool dark: theme.dark
    readonly property string edge: bar.edge
    readonly property string activePlan: PowerPlans.plans.find(plan => plan.id === PowerPlans.activeId)?.name ?? ""
    // Text on the bar takes the theme's colour, and labels the bar's font; parts set in font replace the bar's
    property color textColor: theme.colors.text
    property font font
    property color errorColor: powerPlan.theme.colors.critical
    property font iconFont
    iconFont.family: theme.bar.iconFont.family
    iconFont.weight: theme.bar.iconFont.weight
    iconFont.variableAxes: theme.bar.iconFont.variableAxes
    // The popup: the theme's, unless set here
    property color popupColor: theme.popup.background
    property color popupBorderColor: theme.popup.border
    property color popupTextColor: theme.colors.text
    property color popupSecondaryTextColor: theme.colors.textSecondary
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
    property color popupDividerColor: theme.colors.divider
    property color popupHoverColor: theme.colors.hover
    property color popupSelectedColor: theme.colors.selected
    property font popupTitleFont
    popupTitleFont.family: theme.popup.font.family
    popupTitleFont.pixelSize: 16
    popupTitleFont.weight: Font.DemiBold
    // The mark on the plan in use
    property int checkIconSize: 14

    function placePopup() {
        const start = mapToGlobal(0, 0)
        const screen = powerPlan.Screen
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
        popup.x = Math.round(Math.max(screen.virtualX + margin,
            Math.min(px, screen.virtualX + screen.width - popup.width - margin)))
        popup.y = Math.round(Math.max(screen.virtualY + margin,
            Math.min(py, screen.virtualY + screen.desktopAvailableHeight - popup.height - margin)))
    }

    function togglePopup() {
        if (popup.visible) {
            popup.close()
            return
        }
        if (!PowerPlans.loading)
            PowerPlans.refresh()
        placePopup()
        popup.open()
    }

    implicitWidth: barRow.implicitWidth
    implicitHeight: barRow.implicitHeight
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: activePlan ? qsTr("Power plan, %1").arg(activePlan) : qsTr("Power plan")
    Accessible.onPressAction: togglePopup()
    Keys.onReturnPressed: togglePopup()
    Keys.onSpacePressed: togglePopup()
    Component.onDestruction: popup.hide()

    Hotkey { keys: powerPlan.hotkey; onActivated: powerPlan.togglePopup() }
    Hotkey { keys: powerPlan.alternateHotkey; onActivated: powerPlan.showAlternate = !powerPlan.showAlternate }

    Connections {
        target: powerPlan.Window.window
        function onVisibleChanged() { if (!powerPlan.Window.window?.visible) popup.hide() }
        function onXChanged() { if (popup.visible) powerPlan.placePopup() }
        function onYChanged() { if (popup.visible) powerPlan.placePopup() }
    }

    component Glyph: Text {
        textFormat: Text.PlainText
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        font.family: powerPlan.iconFont.family
        font.weight: powerPlan.iconFont.weight
        font.variableAxes: powerPlan.iconFont.variableAxes
    }

    Row {
        id: barRow
        height: parent.height
        spacing: 6

        Glyph {
            objectName: "icon"
            anchors.verticalCenter: parent.verticalCenter
            visible: text !== ""
            text: powerPlan.icon
            color: powerPlan.textColor
            font.pixelSize: powerPlan.iconSize
        }

        Label {
            objectName: "label"
            anchors.verticalCenter: parent.verticalCenter
            visible: text !== ""
            text: (powerPlan.showAlternate ? powerPlan.alternateLabel : powerPlan.label)
                .replace(/\{active_plan\}/g, () => powerPlan.activePlan)
            textFormat: Text.PlainText
            color: powerPlan.textColor
            font: powerPlan.font
        }
    }

    MouseArea {
        id: area
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: mouse => {
            if (mouse.button === Qt.LeftButton)
                powerPlan.togglePopup()
            else
                powerPlan.showAlternate = !powerPlan.showAlternate
        }
    }

    ToolTip {
        objectName: "tooltip"
        popupType: Popup.Window
        visible: powerPlan.tooltip && area.containsMouse && !popup.visible
        delay: 400
        text: powerPlan.Accessible.name
        y: powerPlan.edge === "bottom" ? -implicitHeight - 6 : powerPlan.height + 6
    }

    BackdropPopup {
        id: popup

        property real reveal: 0

        objectName: "popup"
        title: qsTr("Power Plans")
        width: Math.min(powerPlan.popupWidth, powerPlan.Screen.width - 32)
        height: Math.min(popupContent.implicitHeight, powerPlan.Screen.desktopAvailableHeight - 40)
        anchor: powerPlan
        font: powerPlan.popupFont
        theme: powerPlan.theme
        backdropItem: surface
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: powerPlan.popupOpenDuration; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: powerPlan.popupCloseDuration; easing.type: Easing.InCubic }
        onVisibleChanged: {
            if (!visible)
                reveal = 0
        }

        Rectangle {
            id: surface
            anchors.fill: parent
            radius: powerPlan.popupRadius
            color: powerPlan.popupColor
            border.width: 1
            border.color: powerPlan.popupBorderColor
            opacity: popup.reveal
            scale: 0.85 + popup.reveal * 0.15
            transformOrigin: powerPlan.edge === "bottom" ? Item.Bottom : powerPlan.edge === "left" ? Item.Left
                : powerPlan.edge === "right" ? Item.Right : Item.Top
            clip: true

            ColumnLayout {
                id: popupContent
                anchors.fill: parent
                spacing: 0

                Text {
                    Layout.fillWidth: true
                    Layout.leftMargin: 16
                    Layout.rightMargin: 16
                    Layout.topMargin: 12
                    Layout.bottomMargin: 10
                    text: popup.title
                    font: powerPlan.popupTitleFont
                    textFormat: Text.PlainText
                    color: powerPlan.popupTextColor
                }

                LoadingLine {
                    Layout.fillWidth: true
                    running: PowerPlans.loading
                    trackColor: powerPlan.popupDividerColor
                }

                Text {
                    objectName: "notice"
                    Layout.fillWidth: true
                    Layout.margins: 16
                    visible: PowerPlans.error !== "" || PowerPlans.plans.length === 0
                    text: PowerPlans.error || (PowerPlans.loading ? qsTr("Reading power plans...") : qsTr("No power plans found"))
                    textFormat: Text.PlainText
                    wrapMode: Text.Wrap
                    color: PowerPlans.error ? powerPlan.errorColor : powerPlan.popupSecondaryTextColor
                    font: powerPlan.popupSmallFont
                }

                Flickable {
                    id: list
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(contentHeight, powerPlan.maxListHeight)
                    visible: PowerPlans.plans.length > 0
                    clip: true
                    contentHeight: rows.implicitHeight
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar {}

                    Column {
                        id: rows
                        width: list.width
                        topPadding: 6
                        bottomPadding: 6
                        spacing: 2

                        Repeater {
                            model: PowerPlans.plans

                            delegate: ItemDelegate {
                                id: planRow
                                required property var modelData
                                readonly property bool selected: modelData.id === PowerPlans.activeId

                                objectName: "plan-" + modelData.id
                                x: 8
                                width: rows.width - 16
                                padding: 8
                                hoverEnabled: true
                                Accessible.role: Accessible.RadioButton
                                Accessible.name: modelData.name
                                Accessible.checkable: true
                                Accessible.checked: selected
                                onClicked: PowerPlans.selectPlan(modelData.id)

                                HoverHandler {
                                    enabled: planRow.enabled
                                    cursorShape: Qt.PointingHandCursor
                                }

                                background: Rectangle {
                                    radius: 6
                                    color: planRow.hovered || planRow.visualFocus ? powerPlan.popupHoverColor
                                        : planRow.selected ? powerPlan.popupSelectedColor : "transparent"
                                }

                                contentItem: RowLayout {
                                    spacing: 8

                                    Text {
                                        Layout.fillWidth: true
                                        text: planRow.modelData.name
                                        textFormat: Text.PlainText
                                        elide: Text.ElideRight
                                        color: powerPlan.popupTextColor
                                        font: powerPlan.popupFont
                                    }

                                    Glyph {
                                        Layout.preferredWidth: 16
                                        text: "\ue73e"
                                        opacity: planRow.selected ? 1 : 0
                                        color: powerPlan.popupTextColor
                                        font.pixelSize: powerPlan.checkIconSize
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    Connections {
        target: popup
        function onWidthChanged() { if (popup.visible) powerPlan.placePopup() }
        function onHeightChanged() { if (popup.visible) powerPlan.placePopup() }
    }
}
