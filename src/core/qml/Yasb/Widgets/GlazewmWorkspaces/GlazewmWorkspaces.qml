pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import Yasb
import Yasb.Bar

Item {
    id: root

    property string serverUri: "ws://localhost:6123"
    property bool monitorExclusive: true
    property string offlineLabel: "GlazeWM Offline"
    property bool hideIfOffline: false
    property string populatedLabel: ""
    property string emptyLabel: ""
    property string activePopulatedLabel: ""
    property string activeEmptyLabel: ""
    property string focusedPopulatedLabel: ""
    property string focusedEmptyLabel: ""
    property bool enableScrollSwitching: true
    property bool reverseScrollDirection: false
    property color focusedColor: root.dark ? Qt.alpha("#ffffff", 0.1) : Qt.alpha("#000000", 0.1)
    property color activeColor: root.dark ? Qt.alpha("#ffffff", 0.1) : Qt.alpha("#000000", 0.1)
    property color hoveredColor: root.dark ? Qt.alpha("#ffffff", 0.1) : Qt.alpha("#000000", 0.1)
    property int spacing: 2
    property BarBase bar: null

    component AppIcons: QtObject {
        property bool enabledPopulated: false
        property bool enabledActive: false
        property var enabledFocused: null
        property int size: 16
        property int maxIcons: 3
        property bool hideLabel: false
        property bool hideDuplicates: false
        property bool hideFloating: false
    }

    property AppIcons appIcons: AppIcons {}

    readonly property QtObject model: workspaceList
    readonly property bool dark: Application.styleHints.colorScheme === Qt.ColorScheme.Dark
    readonly property color textColor: bar ? bar.textColor : dark ? "white" : "black"
    readonly property bool vertical: bar?.vertical ?? false
    readonly property bool shown: workspaceList.connected || (!hideIfOffline && offlineLabel !== "")

    implicitWidth: !shown ? 0 : workspaceList.connected ? buttons.implicitWidth : offline.implicitWidth
    implicitHeight: !shown ? 0 : workspaceList.connected ? buttons.implicitHeight : offline.implicitHeight
    visible: shown

    function label(workspace: var): string {
        const fallback = workspace.displayName || workspace.name
        const labels = {
            populated: populatedLabel,
            empty: emptyLabel,
            active_populated: activePopulatedLabel,
            active_empty: activeEmptyLabel,
            focused_populated: focusedPopulatedLabel || activePopulatedLabel,
            focused_empty: focusedEmptyLabel || activeEmptyLabel
        }
        return (labels[workspace.status] || fallback)
            .replace(/\{(name|display_name)\}/g, (_, key) => key === "name" ? workspace.name : workspace.displayName)
    }

    function scroll(delta: int): void {
        if (enableScrollSwitching)
            workspaceList.switchWorkspace(reverseScrollDirection ? -delta : delta)
    }

    GlazewmWorkspaceList {
        id: workspaceList

        serverUri: root.serverUri
        screenName: root.bar?.screenName ?? ""
        monitorExclusive: root.monitorExclusive
        appIcons: ({
            enabledPopulated: root.appIcons.enabledPopulated,
            enabledActive: root.appIcons.enabledActive,
            enabledFocused: root.appIcons.enabledFocused,
            maxIcons: root.appIcons.maxIcons,
            hideDuplicates: root.appIcons.hideDuplicates,
            hideFloating: root.appIcons.hideFloating
        })
    }

    Text {
        id: offline

        objectName: "offline"
        anchors.verticalCenter: parent.verticalCenter
        visible: !workspaceList.connected && root.shown
        text: root.offlineLabel
        textFormat: Text.PlainText
        color: root.textColor
        font.family: root.bar ? root.bar.font.family : Application.font.family
        font.pixelSize: root.bar ? root.bar.font.pixelSize : 13
    }

    Flow {
        id: buttons

        anchors.verticalCenter: parent.verticalCenter
        flow: root.vertical ? Flow.TopToBottom : Flow.LeftToRight
        spacing: root.spacing
        visible: workspaceList.connected

        Repeater {
            model: workspaceList.workspaces

            delegate: Control {
                id: button

                required property var modelData
                readonly property string status: modelData.status
                readonly property bool populated: modelData.windowCount > 0
                readonly property bool focused: modelData.focused
                readonly property bool active: root.monitorExclusive && modelData.displayed

                objectName: "workspace-" + modelData.name
                leftPadding: 4
                rightPadding: 4
                topPadding: 4
                bottomPadding: 4
                Accessible.name: root.label(modelData)

                background: Rectangle {
                    radius: 4
                    color: {
                        if (button.focused) {
                            return root.focusedColor;
                        }
                        if (button.active) {
                            return root.activeColor;
                        }
                        if (button.hovered) {
                            return root.hoveredColor;
                        }
                        return "transparent";
                    }
                }

                MouseArea {
                    id: mouseArea
                    hoverEnabled: true
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: workspaceList.activateWorkspace(button.modelData.name)
                }

                contentItem: Row {
                    spacing: 4

                    Text {
                        objectName: "label"
                        anchors.verticalCenter: parent.verticalCenter
                        visible: !root.appIcons.hideLabel || button.modelData.icons.length === 0
                        text: root.label(button.modelData)
                        textFormat: Text.PlainText
                        color: root.textColor
                        opacity: button.populated || button.focused || button.active ? 1 : 0.5
                        font.family: root.bar ? root.bar.font.family : Application.font.family
                        font.pixelSize: root.bar ? root.bar.font.pixelSize : 13
                    }

                    Repeater {
                        model: button.modelData.icons

                        delegate: Image {
                            required property var modelData

                            objectName: "app-icon"
                            anchors.verticalCenter: parent?.verticalCenter
                            width: Math.max(1, root.appIcons.size)
                            height: width
                            sourceSize: Qt.size(width, height)
                            source: modelData.source
                        }
                    }
                }
            }
        }
    }

    WheelHandler {
        enabled: root.enableScrollSwitching && workspaceList.connected
        onWheel: event => {
            const delta = event.angleDelta.y || event.angleDelta.x
            if (delta !== 0) {
                root.scroll(delta)
                event.accepted = true
            }
        }
    }
}
