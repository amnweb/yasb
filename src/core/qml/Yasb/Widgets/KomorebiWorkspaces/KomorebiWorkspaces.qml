pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import Yasb
import Yasb.Bar
import Yasb.Themes

Item {
    id: komorebiWorkspaces

    component AppIcons: QtObject {
        property bool enabledPopulated
        property bool enabledActive
        property int size
        property int maxIcons
        property bool hideLabel
        property bool hideDuplicates
        property bool hideFloating
    }

    component Settings: QtObject {
        required property Theme theme

        property string offlineLabel: "Komorebi Offline"
        property bool hideIfOffline: false
        // Button text for workspaces without windows, with windows, and the one the monitor shows.
        // Each can use {name}, {index} and {monitor_index}
        property string emptyLabel: "{index}"
        property string populatedLabel: "{index}"
        property string activeLabel: "{index}"
        // The {name} of a workspace komorebi has no name for. Can use {index} and {monitor_index}, empty for the index
        property string defaultName: ""
        // Counts {index} and {monitor_index} from 0 instead of 1
        property bool zeroBasedIndex: false
        property bool hideEmptyWorkspaces: false
        // Shown after the buttons while komorebi's float override is on, empty for never
        property string floatOverrideLabel: "Override Active"
        // Shows the layer of the workspace on this monitor after the buttons, Tiling or Floating
        property bool showWorkspaceLayer: false
        property string tilingLabel: "Tiling"
        property string floatingLabel: "Floating"
        // Scroll over the widget to switch workspaces: down for the next one, up for the previous one
        property bool enableScrollSwitching: false
        property bool reverseScrollDirection: false
        // The background of the workspace the monitor shows, and of a hovered one
        property color activeColor: theme.colors.selected
        property color hoveredColor: theme.colors.hover
        // How strongly workspaces without windows are dimmed
        property real emptyOpacity: 0.5
        // Space around each button's label and icons, in pixels
        property int horizontalPadding: 8
        property int verticalPadding: 4
        property int spacing: 4
        property AppIcons appIcons: AppIcons {
            // Show the icons of the windows in each workspace with windows, and in the one the monitor shows
            enabledPopulated: false
            enabledActive: false
            // In pixels
            size: 16
            // The most icons a workspace shows, 0 for all of them
            maxIcons: 0
            // Leaves out the label of a workspace that shows icons
            hideLabel: false
            // One icon per app, and none for floating windows
            hideDuplicates: false
            hideFloating: true
        }
        // Text on the bar takes the theme's colour, and labels the bar's font; parts set in font replace the bar's
        property color textColor: theme.colors.text
        property font font
    }

    required property BarBase bar
    readonly property Theme theme: bar.theme
    readonly property Settings settings: Settings {
        theme: komorebiWorkspaces.theme
    }

    readonly property QtObject model: workspaceModel
    readonly property bool dark: theme.dark
    readonly property bool vertical: bar.vertical
    readonly property bool shown: workspaceModel.connected || (!settings.hideIfOffline && settings.offlineLabel !== "")
    // The workspace clicked or scrolled to shows as active at once. komorebi reports the switch a moment later, and
    // until then the old workspace would still look active
    property int switchingTo: -1
    readonly property var activeWorkspace: workspaceModel.workspaces.find(
        workspace => switchingTo >= 0 ? workspace.index === switchingTo : workspace.active) ?? null
    readonly property int activeIndex: activeWorkspace?.index ?? -1
    property real scrolled: 0

    implicitWidth: !shown ? 0 : workspaceModel.connected ? buttons.implicitWidth : offline.implicitWidth
    implicitHeight: !shown ? 0 : workspaceModel.connected ? buttons.implicitHeight : offline.implicitHeight
    visible: shown

    function label(workspace: var): string {
        const offset = settings.zeroBasedIndex ? 0 : 1
        const values = { name: "", index: workspace.index + offset, monitor_index: workspaceModel.monitorIndex + offset }
        const fill = template => template.replace(/\{(name|index|monitor_index)\}/g, (_, key) => values[key])
        values.name = workspace.name || fill(settings.defaultName) || String(values.index)
        return fill(workspace.index === activeIndex ? settings.activeLabel : workspace.populated ? settings.populatedLabel : settings.emptyLabel)
    }

    function switchTo(index: int) {
        if (index === activeIndex)
            return
        switchingTo = index
        switchTimeout.restart()
        workspaceModel.activateWorkspace(index)
    }

    Connections {
        target: workspaceModel

        function onDataChanged() {
            if (!workspaceModel.connected || workspaceModel.workspaces[komorebiWorkspaces.switchingTo]?.active)
                komorebiWorkspaces.switchingTo = -1
        }
    }

    Timer {
        id: switchTimeout

        // komorebi didn't switch, so the workspace it shows is active again
        interval: 1500
        onTriggered: komorebiWorkspaces.switchingTo = -1
    }

    KomorebiWorkspacesModel {
        id: workspaceModel

        screenName: komorebiWorkspaces.bar.screenName
        appIcons: ({
            enabledPopulated: komorebiWorkspaces.settings.appIcons.enabledPopulated,
            enabledActive: komorebiWorkspaces.settings.appIcons.enabledActive,
            maxIcons: komorebiWorkspaces.settings.appIcons.maxIcons,
            hideDuplicates: komorebiWorkspaces.settings.appIcons.hideDuplicates,
            hideFloating: komorebiWorkspaces.settings.appIcons.hideFloating
        })
    }

    Label {
        id: offline

        objectName: "offline"
        anchors.verticalCenter: parent.verticalCenter
        visible: !workspaceModel.connected && komorebiWorkspaces.shown
        text: komorebiWorkspaces.settings.offlineLabel
        textFormat: Text.PlainText
        color: komorebiWorkspaces.settings.textColor
        font: komorebiWorkspaces.settings.font
    }

    Flow {
        id: buttons

        anchors.verticalCenter: parent.verticalCenter
        flow: komorebiWorkspaces.vertical ? Flow.TopToBottom : Flow.LeftToRight
        spacing: komorebiWorkspaces.settings.spacing
        visible: workspaceModel.connected

        Repeater {
            model: workspaceModel.workspaces

            delegate: AbstractButton {
                id: button

                required property var modelData
                readonly property bool active: modelData.index === komorebiWorkspaces.activeIndex

                objectName: "workspace-" + modelData.index
                visible: !komorebiWorkspaces.settings.hideEmptyWorkspaces || active || modelData.populated
                horizontalPadding: komorebiWorkspaces.settings.horizontalPadding
                verticalPadding: komorebiWorkspaces.settings.verticalPadding
                hoverEnabled: true
                Accessible.name: komorebiWorkspaces.label(modelData)
                onClicked: komorebiWorkspaces.switchTo(modelData.index)

                HoverHandler {
                    cursorShape: Qt.PointingHandCursor
                }

                background: Rectangle {
                    radius: 4
                    color: button.active ? komorebiWorkspaces.settings.activeColor : button.hovered ? komorebiWorkspaces.settings.hoveredColor : "transparent"
                }

                contentItem: Row {
                    spacing: 4

                    Label {
                        objectName: "label"
                        anchors.verticalCenter: parent.verticalCenter
                        visible: !komorebiWorkspaces.settings.appIcons.hideLabel || button.modelData.icons.length === 0
                        text: komorebiWorkspaces.label(button.modelData)
                        textFormat: Text.PlainText
                        color: komorebiWorkspaces.settings.textColor
                        font: komorebiWorkspaces.settings.font
                        opacity: button.active || button.modelData.populated ? 1 : komorebiWorkspaces.settings.emptyOpacity
                    }

                    Repeater {
                        model: button.modelData.icons

                        delegate: Image {
                            required property var modelData

                            objectName: "app-icon"
                            // The Repeater makes each icon before the Row takes it, and lets go of it first
                            anchors.verticalCenter: parent?.verticalCenter
                            width: Math.max(1, komorebiWorkspaces.settings.appIcons.size)
                            height: width
                            sourceSize: Qt.size(width, height)
                            source: modelData.source
                        }
                    }
                }
            }
        }

        // The same padding as the buttons lines the text up with their labels
        Label {
            objectName: "float-override"
            leftPadding: komorebiWorkspaces.settings.horizontalPadding
            rightPadding: komorebiWorkspaces.settings.horizontalPadding
            topPadding: komorebiWorkspaces.settings.verticalPadding
            bottomPadding: komorebiWorkspaces.settings.verticalPadding
            visible: workspaceModel.floatOverride && komorebiWorkspaces.activeWorkspace !== null && text !== ""
            text: komorebiWorkspaces.settings.floatOverrideLabel
            textFormat: Text.PlainText
            color: komorebiWorkspaces.settings.textColor
            font: komorebiWorkspaces.settings.font
        }

        Label {
            objectName: "layer"
            leftPadding: komorebiWorkspaces.settings.horizontalPadding
            rightPadding: komorebiWorkspaces.settings.horizontalPadding
            topPadding: komorebiWorkspaces.settings.verticalPadding
            bottomPadding: komorebiWorkspaces.settings.verticalPadding
            visible: komorebiWorkspaces.settings.showWorkspaceLayer && text !== ""
            text: komorebiWorkspaces.activeWorkspace?.layer === "Tiling" ? komorebiWorkspaces.settings.tilingLabel
                : komorebiWorkspaces.activeWorkspace?.layer === "Floating" ? komorebiWorkspaces.settings.floatingLabel : ""
            textFormat: Text.PlainText
            color: komorebiWorkspaces.settings.textColor
            font: komorebiWorkspaces.settings.font
        }
    }

    WheelHandler {
        enabled: komorebiWorkspaces.settings.enableScrollSwitching && workspaceModel.connected
        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
        onWheel: event => {
            // A touchpad scrolls in small steps, which add up to one workspace per mouse wheel notch
            komorebiWorkspaces.scrolled += event.angleDelta.y || event.angleDelta.x
            if (Math.abs(komorebiWorkspaces.scrolled) < 120)
                return
            const delta = komorebiWorkspaces.settings.reverseScrollDirection ? -komorebiWorkspaces.scrolled : komorebiWorkspaces.scrolled
            komorebiWorkspaces.scrolled = 0
            // From the workspace shown as active, so each notch moves one on before komorebi has caught up.
            // Up goes to the previous workspace and down to the next, both wrapping around
            const count = workspaceModel.workspaces.length
            if (komorebiWorkspaces.activeIndex >= 0)
                komorebiWorkspaces.switchTo((komorebiWorkspaces.activeIndex + (delta > 0 ? count - 1 : 1)) % count)
        }
    }
}
