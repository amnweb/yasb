pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Yasb
import Yasb.Common

Item {
    id: widget

    property Item bar: null
    // Both labels can use {active_plan}.
    property string label: "{active_plan}"
    property string alternateLabel: qsTr("Power Plan")
    property bool showAlternate: false
    property string icon: "\ue945"
    property int iconSize: font.pixelSize + 1
    property bool tooltip: true
    property string keys: ""
    property string alternateKeys: ""
    property int popupWidth: 300
    property string popupAlignment: "center"
    property int maxListHeight: 320

    readonly property bool dark: bar ? bar.dark : Qt.styleHints.colorScheme === Qt.ColorScheme.Dark
    readonly property string edge: bar?.edge ?? "top"
    readonly property string activePlan: PowerPlans.plans.find(plan => plan.id === PowerPlans.activeId)?.name ?? ""
    property color textColor: bar?.textColor ?? (dark ? "#ffffff" : "#000000")
    property color errorColor: dark ? "#FF99A4" : "#C42B1C"
    property font font
    font.family: bar?.font.family ?? Qt.application.font.family
    font.pixelSize: bar?.font.pixelSize ?? 13
    font.weight: bar?.font.weight ?? Font.Normal
    font.italic: bar?.font.italic ?? false
    font.letterSpacing: bar?.font.letterSpacing ?? 0
    font.capitalization: bar?.font.capitalization ?? Font.MixedCase
    font.variableAxes: bar?.font.variableAxes ?? ({})
    property font iconFont
    iconFont.family: bar?.iconFont?.family ?? "Segoe Fluent Icons"
    iconFont.weight: bar?.iconFont?.weight ?? Font.Normal

    function placePopup() {
        const start = mapToGlobal(0, 0)
        const screen = widget.Screen
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

    Hotkey { keys: widget.keys; onActivated: widget.togglePopup() }
    Hotkey { keys: widget.alternateKeys; onActivated: widget.showAlternate = !widget.showAlternate }

    Connections {
        target: widget.Window.window
        function onVisibleChanged() { if (!widget.Window.window?.visible) popup.hide() }
        function onXChanged() { if (popup.visible) widget.placePopup() }
        function onYChanged() { if (popup.visible) widget.placePopup() }
    }

    component Glyph: Text {
        textFormat: Text.PlainText
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        font.family: widget.iconFont.family
        font.weight: widget.iconFont.weight
    }

    Row {
        id: barRow
        height: parent.height
        spacing: 6

        Glyph {
            objectName: "icon"
            anchors.verticalCenter: parent.verticalCenter
            visible: text !== ""
            text: widget.icon
            color: widget.textColor
            font.pixelSize: widget.iconSize
        }

        Text {
            objectName: "label"
            anchors.verticalCenter: parent.verticalCenter
            visible: text !== ""
            text: (widget.showAlternate ? widget.alternateLabel : widget.label)
                .replace(/\{active_plan\}/g, () => widget.activePlan)
            textFormat: Text.PlainText
            color: widget.textColor
            font: widget.font
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
                widget.togglePopup()
            else
                widget.showAlternate = !widget.showAlternate
        }
    }

    ToolTip {
        objectName: "tooltip"
        popupType: Popup.Window
        visible: widget.tooltip && area.containsMouse && !popup.visible
        delay: 400
        text: widget.Accessible.name
        y: widget.edge === "bottom" ? -implicitHeight - 6 : widget.height + 6
    }

    BackdropPopup {
        id: popup

        property real reveal: 0
        readonly property color ink: widget.dark ? "#ffffff" : "#000000"
        readonly property color secondary: Qt.alpha(ink, 0.786)
        readonly property color line: Qt.alpha(ink, 0.08)

        objectName: "popup"
        title: qsTr("Power Plans")
        width: Math.min(widget.popupWidth, widget.Screen.width - 16)
        height: Math.min(content.implicitHeight + 16, widget.Screen.desktopAvailableHeight - 24)
        anchor: widget
        backdropItem: surface
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: 180; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: 140; easing.type: Easing.InCubic }
        onVisibleChanged: {
            if (!visible)
                reveal = 0
        }

        Rectangle {
            id: surface
            anchors.fill: parent
            anchors.margins: 8
            radius: 8
            color: widget.dark ? Qt.alpha("#202020", 0.85) : Qt.alpha("#F3F3F3", 0.85)
            border.width: 1
            border.color: widget.dark ? "#3A3A3A" : "#D9D9D9"
            opacity: popup.reveal
            scale: 0.85 + popup.reveal * 0.15
            transformOrigin: widget.edge === "bottom" ? Item.Bottom : widget.edge === "left" ? Item.Left
                : widget.edge === "right" ? Item.Right : Item.Top
            clip: true

            ColumnLayout {
                id: content
                anchors.fill: parent
                spacing: 0

                Text {
                    Layout.fillWidth: true
                    Layout.leftMargin: 16
                    Layout.rightMargin: 16
                    Layout.topMargin: 12
                    Layout.bottomMargin: 10
                    text: popup.title
                    textFormat: Text.PlainText
                    color: popup.ink
                    font.pixelSize: 14
                    font.weight: Font.DemiBold
                }

                LoadingLine {
                    Layout.fillWidth: true
                    running: PowerPlans.loading
                    trackColor: popup.line
                }

                Text {
                    objectName: "notice"
                    Layout.fillWidth: true
                    Layout.margins: 16
                    visible: PowerPlans.error !== "" || PowerPlans.plans.length === 0
                    text: PowerPlans.error || (PowerPlans.loading ? qsTr("Reading power plans…") : qsTr("No power plans found"))
                    textFormat: Text.PlainText
                    wrapMode: Text.Wrap
                    color: PowerPlans.error ? widget.errorColor : popup.secondary
                    font.pixelSize: 12
                }

                Flickable {
                    id: list
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(contentHeight, widget.maxListHeight)
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
                                    color: Qt.alpha(popup.ink, planRow.hovered || planRow.visualFocus ? 0.1
                                        : planRow.selected ? 0.06 : 0)
                                }

                                contentItem: RowLayout {
                                    spacing: 8

                                    Text {
                                        Layout.fillWidth: true
                                        text: planRow.modelData.name
                                        textFormat: Text.PlainText
                                        elide: Text.ElideRight
                                        color: popup.ink
                                        font.pixelSize: 13
                                    }

                                    Glyph {
                                        Layout.preferredWidth: 16
                                        text: "\ue73e"
                                        opacity: planRow.selected ? 1 : 0
                                        color: popup.ink
                                        font.pixelSize: 14
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
        function onWidthChanged() { if (popup.visible) widget.placePopup() }
        function onHeightChanged() { if (popup.visible) widget.placePopup() }
    }
}
