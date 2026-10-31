import QtQuick
import QtQuick.Controls
import Yasb

Item {
    id: workspaces

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
    property color focusedColor: workspaces.dark ? Qt.alpha("#ffffff", 0.1) : Qt.alpha("#000000", 0.1)
    property color activeColor: workspaces.dark ? Qt.alpha("#ffffff", 0.1) : Qt.alpha("#000000", 0.1)
    property color hoveredColor: workspaces.dark ? Qt.alpha("#ffffff", 0.1) : Qt.alpha("#000000", 0.1)
    property int spacing: 2
    property Item bar: null

    property QtObject appIcons: QtObject {
        property bool enabledPopulated: false
        property bool enabledActive: false
        property var enabledFocused: null
        property int size: 16
        property int maxIcons: 3
        property bool hideLabel: false
        property bool hideDuplicates: false
        property bool hideFloating: false
    }

    readonly property QtObject model: workspaceModel
    readonly property bool dark: Qt.styleHints.colorScheme === Qt.ColorScheme.Dark
    readonly property color textColor: bar ? bar.textColor : dark ? "white" : "black"
    readonly property bool vertical: bar?.vertical ?? false
    readonly property bool shown: workspaceModel.connected || (!hideIfOffline && offlineLabel !== "")

    implicitWidth: !shown ? 0 : workspaceModel.connected ? buttons.implicitWidth : offline.implicitWidth
    implicitHeight: !shown ? 0 : workspaceModel.connected ? buttons.implicitHeight : offline.implicitHeight
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
            workspaceModel.switchWorkspace(reverseScrollDirection ? -delta : delta)
    }

    GlazewmWorkspacesModel {
        id: workspaceModel

        serverUri: workspaces.serverUri
        screenName: workspaces.bar?.screenName ?? ""
        monitorExclusive: workspaces.monitorExclusive
        appIcons: ({
            enabledPopulated: workspaces.appIcons.enabledPopulated,
            enabledActive: workspaces.appIcons.enabledActive,
            enabledFocused: workspaces.appIcons.enabledFocused,
            maxIcons: workspaces.appIcons.maxIcons,
            hideDuplicates: workspaces.appIcons.hideDuplicates,
            hideFloating: workspaces.appIcons.hideFloating
        })
    }

    Text {
        id: offline

        objectName: "offline"
        anchors.verticalCenter: parent.verticalCenter
        visible: !workspaceModel.connected && workspaces.shown
        text: workspaces.offlineLabel
        textFormat: Text.PlainText
        color: workspaces.textColor
        font.family: workspaces.bar ? workspaces.bar.font.family : Qt.application.font.family
        font.pixelSize: workspaces.bar ? workspaces.bar.font.pixelSize : 13
    }

    Flow {
        id: buttons

        anchors.verticalCenter: parent.verticalCenter
        flow: workspaces.vertical ? Flow.TopToBottom : Flow.LeftToRight
        spacing: workspaces.spacing
        visible: workspaceModel.connected

        Repeater {
            model: workspaceModel.workspaces

            delegate: Control {
                id: button

                required property var modelData
                readonly property string status: modelData.status
                readonly property bool populated: modelData.windowCount > 0
                readonly property bool focused: modelData.focused
                readonly property bool active: workspaces.monitorExclusive && modelData.displayed

                objectName: "workspace-" + modelData.name
                leftPadding: 4
                rightPadding: 4
                topPadding: 4
                bottomPadding: 4
                Accessible.name: workspaces.label(modelData)

                background: Rectangle {
                    radius: 4
                    color: {
                        if (button.focused) {
                            return focusedColor;
                        }
                        if (button.active) {
                            return activeColor;
                        }
                        if (button.hovered) {
                            return hoveredColor;
                        }
                        return "transparent";
                    }
                }

                MouseArea {
                    id: mouseArea
                    hoverEnabled: true
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: workspaceModel.activateWorkspace(modelData.name)
                }

                contentItem: Row {
                    spacing: 4

                    Text {
                        objectName: "label"
                        anchors.verticalCenter: parent.verticalCenter
                        visible: !workspaces.appIcons.hideLabel || button.modelData.icons.length === 0
                        text: workspaces.label(button.modelData)
                        textFormat: Text.PlainText
                        color: workspaces.textColor
                        opacity: button.populated || button.focused || button.active ? 1 : 0.5
                        font.family: workspaces.bar ? workspaces.bar.font.family : Qt.application.font.family
                        font.pixelSize: workspaces.bar ? workspaces.bar.font.pixelSize : 13
                    }

                    Repeater {
                        model: button.modelData.icons

                        delegate: Image {
                            required property var modelData

                            objectName: "app-icon"
                            anchors.verticalCenter: parent.verticalCenter
                            width: Math.max(1, workspaces.appIcons.size)
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
        enabled: workspaces.enableScrollSwitching && workspaceModel.connected
        onWheel: event => {
            const delta = event.angleDelta.y || event.angleDelta.x
            if (delta !== 0) {
                workspaces.scroll(delta)
                event.accepted = true
            }
        }
    }
}
