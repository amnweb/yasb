import QtQuick
import QtQuick.Controls

Item {
    id: base

    required property var context

    readonly property bool dark: Qt.styleHints.colorScheme === Qt.ColorScheme.Dark
    readonly property string name: context.name
    readonly property string screenName: context.screenName
    readonly property string edge: context.edge
    readonly property bool vertical: edge === "left" || edge === "right"

    property alias background: surface
    property alias color: surface.color
    property alias gradient: surface.gradient
    property alias radius: surface.radius
    property alias border: surface.border
    // Where the backdrop blurs, as {x, y, width, height, radius} in the bar's coordinates
    property var backdropShapes: [{ x: 0, y: 0, width: width, height: height, radius: radius }]
    // A custom silhouette, including any edge overhang outside this item.
    property string backdropPath: ""

    property int padding: 8
    property int spacing: 8
    property color textColor: dark ? "#ffffff" : "#000000"
    property font font: Qt.font({ pixelSize: 13 })
    property real contentImplicitLength: longestContent()
    property list<string> slotNames: []
    property list<Item> slots: []

    // Opened by a right-click on the bar: null for no menu, or a Component of your own with the same properties
    property Component contextMenu: Component {
        BarMenu {}
    }
    property Window openedMenu: null
    // Whether the last press on the bar was on a widget. Windows asks for the menu after the button is let
    // go, when a widget that changed size on the click may no longer be under the mouse.
    property bool pressedOnWidget: false

    default property alias content: contentArea.data

    function longestContent(): real {
        let longest = 0
        for (let index = 0; index < contentArea.children.length; ++index) {
            const child = contentArea.children[index]
            longest = Math.max(longest, vertical ? child.implicitHeight : child.implicitWidth)
        }
        return longest
    }

    function addSlot(slot: Item) {
        slots = [...slots, slot]
        slotNames = [...slotNames, slot.name]
    }

    // Whether a point in the window is on one of the widgets
    function widgetAt(position: point): bool {
        for (const slot of slots) {
            for (const widget of slot.content.children) {
                if (widget.visible && widget.contains(widget.mapFromItem(null, position)))
                    return true
            }
        }
        return false
    }

    function openContextMenu(position: point) {
        openedMenu?.close()
        if (contextMenu)
            openedMenu = contextMenu.createObject(null, {
                bar: base,
                position: mapToGlobal(position),
                area: Qt.rect(Screen.virtualX, Screen.virtualY, Screen.width, Screen.height)
            })
    }

    implicitWidth: vertical ? 0 : 2 * padding + contentImplicitLength
    implicitHeight: vertical ? 2 * padding + contentImplicitLength : 0

    ContextMenu.onRequested: position => {
        if (!pressedOnWidget)
            base.openContextMenu(position)
        pressedOnWidget = false
    }

    // The bar window reports each press before its items get it
    Connections {
        target: base.Window.window
        ignoreUnknownSignals: true

        function onPressed(position: point) {
            base.pressedOnWidget = base.widgetAt(position)
        }
    }

    TapHandler {
        acceptedButtons: Qt.LeftButton | Qt.MiddleButton
        onTapped: base.openedMenu?.close()
    }

    Rectangle {
        id: surface

        anchors.fill: parent
        color: dark ? Qt.alpha("#202020", 0.85) : Qt.alpha("#F3F3F3", 0.85)
        border.width: 0
        border.color: dark ? Qt.alpha("#3A3A3A", 1) : Qt.alpha("#D9D9D9", 1)
    }

    Item {
        id: contentArea

        anchors.fill: parent
        anchors.leftMargin: base.vertical ? 0 : base.padding
        anchors.rightMargin: base.vertical ? 0 : base.padding
        anchors.topMargin: base.vertical ? base.padding : 0
        anchors.bottomMargin: base.vertical ? base.padding : 0
    }
}
