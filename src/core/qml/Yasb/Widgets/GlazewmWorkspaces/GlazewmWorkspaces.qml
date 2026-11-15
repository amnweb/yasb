pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import Yasb
import Yasb.Bar
import Yasb.Themes

Item {
    id: glazewmWorkspaces

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
    property color focusedColor: glazewmWorkspaces.theme.colors.selected
    property color activeColor: glazewmWorkspaces.theme.colors.selected
    property color hoveredColor: glazewmWorkspaces.theme.colors.hover
    property int spacing: 2
    required property BarBase bar
    readonly property Theme theme: bar.theme

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
    readonly property bool dark: theme.dark
    // Text on the bar takes the theme's colour, and labels the bar's font; parts set in font replace the bar's
    property color textColor: theme.colors.text
    property font font
    readonly property bool vertical: bar.vertical
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

        serverUri: glazewmWorkspaces.serverUri
        screenName: glazewmWorkspaces.bar.screenName
        monitorExclusive: glazewmWorkspaces.monitorExclusive
        appIcons: ({
            enabledPopulated: glazewmWorkspaces.appIcons.enabledPopulated,
            enabledActive: glazewmWorkspaces.appIcons.enabledActive,
            enabledFocused: glazewmWorkspaces.appIcons.enabledFocused,
            maxIcons: glazewmWorkspaces.appIcons.maxIcons,
            hideDuplicates: glazewmWorkspaces.appIcons.hideDuplicates,
            hideFloating: glazewmWorkspaces.appIcons.hideFloating
        })
    }

    Label {
        id: offline

        objectName: "offline"
        anchors.verticalCenter: parent.verticalCenter
        visible: !workspaceList.connected && glazewmWorkspaces.shown
        text: glazewmWorkspaces.offlineLabel
        textFormat: Text.PlainText
        color: glazewmWorkspaces.textColor
        font: glazewmWorkspaces.font
    }

    Flow {
        id: buttons

        anchors.verticalCenter: parent.verticalCenter
        flow: glazewmWorkspaces.vertical ? Flow.TopToBottom : Flow.LeftToRight
        spacing: glazewmWorkspaces.spacing
        visible: workspaceList.connected

        Repeater {
            model: workspaceList.workspaces

            delegate: Control {
                id: button

                required property var modelData
                readonly property string status: modelData.status
                readonly property bool populated: modelData.windowCount > 0
                readonly property bool focused: modelData.focused
                readonly property bool active: glazewmWorkspaces.monitorExclusive && modelData.displayed

                objectName: "workspace-" + modelData.name
                leftPadding: 4
                rightPadding: 4
                topPadding: 4
                bottomPadding: 4
                Accessible.name: glazewmWorkspaces.label(modelData)

                background: Rectangle {
                    radius: 4
                    color: {
                        if (button.focused) {
                            return glazewmWorkspaces.focusedColor;
                        }
                        if (button.active) {
                            return glazewmWorkspaces.activeColor;
                        }
                        if (button.hovered) {
                            return glazewmWorkspaces.hoveredColor;
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

                    Label {
                        objectName: "label"
                        anchors.verticalCenter: parent.verticalCenter
                        visible: !glazewmWorkspaces.appIcons.hideLabel || button.modelData.icons.length === 0
                        text: glazewmWorkspaces.label(button.modelData)
                        textFormat: Text.PlainText
                        color: glazewmWorkspaces.textColor
                        font: glazewmWorkspaces.font
                        opacity: button.populated || button.focused || button.active ? 1 : 0.5
                    }

                    Repeater {
                        model: button.modelData.icons

                        delegate: Image {
                            required property var modelData

                            objectName: "app-icon"
                            anchors.verticalCenter: parent?.verticalCenter
                            width: Math.max(1, glazewmWorkspaces.appIcons.size)
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
        enabled: glazewmWorkspaces.enableScrollSwitching && workspaceList.connected
        onWheel: event => {
            const delta = event.angleDelta.y || event.angleDelta.x
            if (delta !== 0) {
                glazewmWorkspaces.scroll(delta)
                event.accepted = true
            }
        }
    }
}
