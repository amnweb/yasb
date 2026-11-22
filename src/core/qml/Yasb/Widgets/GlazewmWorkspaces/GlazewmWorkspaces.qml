pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import Yasb
import Yasb.Bar
import Yasb.Themes

Item {
    id: glazewmWorkspaces

    component AppIcons: QtObject {
        property bool enabledPopulated
        property bool enabledActive
        property var enabledFocused
        property int size
        property int maxIcons
        property bool hideLabel
        property bool hideDuplicates
        property bool hideFloating
    }

    component Settings: QtObject {
        required property Theme theme

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
        property color focusedColor: theme.colors.selected
        property color activeColor: theme.colors.selected
        property color hoveredColor: theme.colors.hover
        property int spacing: 2
        property AppIcons appIcons: AppIcons {
            enabledPopulated: false
            enabledActive: false
            enabledFocused: null
            size: 16
            maxIcons: 3
            hideLabel: false
            hideDuplicates: false
            hideFloating: false
        }
        // Text on the bar takes the theme's colour, and labels the bar's font; parts set in font replace the bar's
        property color textColor: theme.colors.text
        property font font
    }

    required property BarBase bar
    readonly property Theme theme: bar.theme
    readonly property Settings settings: Settings {
        theme: glazewmWorkspaces.theme
    }

    readonly property QtObject model: workspaceList
    readonly property bool dark: theme.dark
    readonly property bool vertical: bar.vertical
    readonly property bool shown: workspaceList.connected || (!settings.hideIfOffline && settings.offlineLabel !== "")

    implicitWidth: !shown ? 0 : workspaceList.connected ? buttons.implicitWidth : offline.implicitWidth
    implicitHeight: !shown ? 0 : workspaceList.connected ? buttons.implicitHeight : offline.implicitHeight
    visible: shown

    function label(workspace: var): string {
        const fallback = workspace.displayName || workspace.name
        const labels = {
            populated: settings.populatedLabel,
            empty: settings.emptyLabel,
            active_populated: settings.activePopulatedLabel,
            active_empty: settings.activeEmptyLabel,
            focused_populated: settings.focusedPopulatedLabel || settings.activePopulatedLabel,
            focused_empty: settings.focusedEmptyLabel || settings.activeEmptyLabel
        }
        return (labels[workspace.status] || fallback)
            .replace(/\{(name|display_name)\}/g, (_, key) => key === "name" ? workspace.name : workspace.displayName)
    }

    function scroll(delta: int): void {
        if (settings.enableScrollSwitching)
            workspaceList.switchWorkspace(settings.reverseScrollDirection ? -delta : delta)
    }

    GlazewmWorkspaceList {
        id: workspaceList

        serverUri: glazewmWorkspaces.settings.serverUri
        screenName: glazewmWorkspaces.bar.screenName
        monitorExclusive: glazewmWorkspaces.settings.monitorExclusive
        appIcons: ({
            enabledPopulated: glazewmWorkspaces.settings.appIcons.enabledPopulated,
            enabledActive: glazewmWorkspaces.settings.appIcons.enabledActive,
            enabledFocused: glazewmWorkspaces.settings.appIcons.enabledFocused,
            maxIcons: glazewmWorkspaces.settings.appIcons.maxIcons,
            hideDuplicates: glazewmWorkspaces.settings.appIcons.hideDuplicates,
            hideFloating: glazewmWorkspaces.settings.appIcons.hideFloating
        })
    }

    Label {
        id: offline

        objectName: "offline"
        anchors.verticalCenter: parent.verticalCenter
        visible: !workspaceList.connected && glazewmWorkspaces.shown
        text: glazewmWorkspaces.settings.offlineLabel
        textFormat: Text.PlainText
        color: glazewmWorkspaces.settings.textColor
        font: glazewmWorkspaces.settings.font
    }

    Flow {
        id: buttons

        anchors.verticalCenter: parent.verticalCenter
        flow: glazewmWorkspaces.vertical ? Flow.TopToBottom : Flow.LeftToRight
        spacing: glazewmWorkspaces.settings.spacing
        visible: workspaceList.connected

        Repeater {
            model: workspaceList.workspaces

            delegate: Control {
                id: button

                required property var modelData
                readonly property string status: modelData.status
                readonly property bool populated: modelData.windowCount > 0
                readonly property bool focused: modelData.focused
                readonly property bool active: glazewmWorkspaces.settings.monitorExclusive && modelData.displayed

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
                            return glazewmWorkspaces.settings.focusedColor;
                        }
                        if (button.active) {
                            return glazewmWorkspaces.settings.activeColor;
                        }
                        if (button.hovered) {
                            return glazewmWorkspaces.settings.hoveredColor;
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
                        visible: !glazewmWorkspaces.settings.appIcons.hideLabel || button.modelData.icons.length === 0
                        text: glazewmWorkspaces.label(button.modelData)
                        textFormat: Text.PlainText
                        color: glazewmWorkspaces.settings.textColor
                        font: glazewmWorkspaces.settings.font
                        opacity: button.populated || button.focused || button.active ? 1 : 0.5
                    }

                    Repeater {
                        model: button.modelData.icons

                        delegate: Image {
                            required property var modelData

                            objectName: "app-icon"
                            anchors.verticalCenter: parent?.verticalCenter
                            width: Math.max(1, glazewmWorkspaces.settings.appIcons.size)
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
        enabled: glazewmWorkspaces.settings.enableScrollSwitching && workspaceList.connected
        onWheel: event => {
            const delta = event.angleDelta.y || event.angleDelta.x
            if (delta !== 0) {
                glazewmWorkspaces.scroll(delta)
                event.accepted = true
            }
        }
    }
}
