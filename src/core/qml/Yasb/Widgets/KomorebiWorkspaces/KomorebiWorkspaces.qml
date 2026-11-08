pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import Yasb
import Yasb.Bar

Item {
    id: root

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
    property color activeColor: root.dark ? Qt.alpha("#ffffff", 0.12) : Qt.alpha("#000000", 0.12)
    property color hoveredColor: root.dark ? Qt.alpha("#ffffff", 0.06) : Qt.alpha("#000000", 0.06)
    // How strongly workspaces without windows are dimmed
    property real emptyOpacity: 0.5
    // Space around each button's label and icons, in pixels
    property int horizontalPadding: 8
    property int verticalPadding: 4
    property int spacing: 4
    property BarBase bar: null

    component AppIcons: QtObject {
        // Show the icons of the windows in each workspace with windows, and in the one the monitor shows
        property bool enabledPopulated: false
        property bool enabledActive: false
        // In pixels
        property int size: 16
        // The most icons a workspace shows, 0 for all of them
        property int maxIcons: 0
        // Leaves out the label of a workspace that shows icons
        property bool hideLabel: false
        // One icon per app, and none for floating windows
        property bool hideDuplicates: false
        property bool hideFloating: true
    }

    property AppIcons appIcons: AppIcons {}

    readonly property QtObject model: workspaceModel
    readonly property bool dark: bar ? bar.dark : Application.styleHints.colorScheme === Qt.ColorScheme.Dark
    // Text on the bar takes the bar's colour and font, each part unless the widget file sets it
    property color textColor: bar?.textColor ?? (dark ? "#ffffff" : "#000000")
    property font font
    font.family: bar?.font.family ?? Application.font.family
    font.pixelSize: bar?.font.pixelSize ?? 13
    font.weight: bar?.font.weight ?? Font.Normal
    font.italic: bar?.font.italic ?? false
    font.letterSpacing: bar?.font.letterSpacing ?? 0
    font.capitalization: bar?.font.capitalization ?? Font.MixedCase
    font.variableAxes: bar?.font.variableAxes ?? ({})
    readonly property bool vertical: bar?.vertical ?? false
    readonly property bool shown: workspaceModel.connected || (!hideIfOffline && offlineLabel !== "")
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
        const offset = zeroBasedIndex ? 0 : 1
        const values = { name: "", index: workspace.index + offset, monitor_index: workspaceModel.monitorIndex + offset }
        const fill = template => template.replace(/\{(name|index|monitor_index)\}/g, (_, key) => values[key])
        values.name = workspace.name || fill(defaultName) || String(values.index)
        return fill(workspace.index === activeIndex ? activeLabel : workspace.populated ? populatedLabel : emptyLabel)
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
            if (!workspaceModel.connected || workspaceModel.workspaces[root.switchingTo]?.active)
                root.switchingTo = -1
        }
    }

    Timer {
        id: switchTimeout

        // komorebi didn't switch, so the workspace it shows is active again
        interval: 1500
        onTriggered: root.switchingTo = -1
    }

    KomorebiWorkspacesModel {
        id: workspaceModel

        screenName: root.bar?.screenName ?? ""
        appIcons: ({
            enabledPopulated: root.appIcons.enabledPopulated,
            enabledActive: root.appIcons.enabledActive,
            maxIcons: root.appIcons.maxIcons,
            hideDuplicates: root.appIcons.hideDuplicates,
            hideFloating: root.appIcons.hideFloating
        })
    }

    Text {
        id: offline

        objectName: "offline"
        anchors.verticalCenter: parent.verticalCenter
        visible: !workspaceModel.connected && root.shown
        text: root.offlineLabel
        textFormat: Text.PlainText
        color: root.textColor
        font: root.font
    }

    Flow {
        id: buttons

        anchors.verticalCenter: parent.verticalCenter
        flow: root.vertical ? Flow.TopToBottom : Flow.LeftToRight
        spacing: root.spacing
        visible: workspaceModel.connected

        Repeater {
            model: workspaceModel.workspaces

            delegate: AbstractButton {
                id: button

                required property var modelData
                readonly property bool active: modelData.index === root.activeIndex

                objectName: "workspace-" + modelData.index
                visible: !root.hideEmptyWorkspaces || active || modelData.populated
                horizontalPadding: root.horizontalPadding
                verticalPadding: root.verticalPadding
                hoverEnabled: true
                Accessible.name: root.label(modelData)
                onClicked: root.switchTo(modelData.index)

                HoverHandler {
                    cursorShape: Qt.PointingHandCursor
                }

                background: Rectangle {
                    radius: 4
                    color: button.active ? root.activeColor : button.hovered ? root.hoveredColor : "transparent"
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
                        font: root.font
                        opacity: button.active || button.modelData.populated ? 1 : root.emptyOpacity
                    }

                    Repeater {
                        model: button.modelData.icons

                        delegate: Image {
                            required property var modelData

                            objectName: "app-icon"
                            // The Repeater makes each icon before the Row takes it, and lets go of it first
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

        // The same padding as the buttons lines the text up with their labels
        Text {
            objectName: "float-override"
            leftPadding: root.horizontalPadding
            rightPadding: root.horizontalPadding
            topPadding: root.verticalPadding
            bottomPadding: root.verticalPadding
            visible: workspaceModel.floatOverride && root.activeWorkspace !== null && text !== ""
            text: root.floatOverrideLabel
            textFormat: Text.PlainText
            color: root.textColor
            font: root.font
        }

        Text {
            objectName: "layer"
            leftPadding: root.horizontalPadding
            rightPadding: root.horizontalPadding
            topPadding: root.verticalPadding
            bottomPadding: root.verticalPadding
            visible: root.showWorkspaceLayer && text !== ""
            text: root.activeWorkspace?.layer === "Tiling" ? root.tilingLabel
                : root.activeWorkspace?.layer === "Floating" ? root.floatingLabel : ""
            textFormat: Text.PlainText
            color: root.textColor
            font: root.font
        }
    }

    WheelHandler {
        enabled: root.enableScrollSwitching && workspaceModel.connected
        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
        onWheel: event => {
            // A touchpad scrolls in small steps, which add up to one workspace per mouse wheel notch
            root.scrolled += event.angleDelta.y || event.angleDelta.x
            if (Math.abs(root.scrolled) < 120)
                return
            const delta = root.reverseScrollDirection ? -root.scrolled : root.scrolled
            root.scrolled = 0
            // From the workspace shown as active, so each notch moves one on before komorebi has caught up.
            // Up goes to the previous workspace and down to the next, both wrapping around
            const count = workspaceModel.workspaces.length
            if (root.activeIndex >= 0)
                root.switchTo((root.activeIndex + (delta > 0 ? count - 1 : 1)) % count)
        }
    }
}
