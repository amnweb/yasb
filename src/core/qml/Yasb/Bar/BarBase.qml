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

    property int padding: 8
    property int spacing: 8
    property color textColor: dark ? "white" : "black"
    property font font: Qt.font({ pixelSize: 13 })
    property real contentImplicitLength: longestContent()
    property list<string> slotNames: []
    property list<Item> slots: []

    // Opened by a right-click on the bar: null for no menu, or a Component of your own with the same properties
    property Component contextMenu: Component {
        BarMenu {}
    }
    property Window openedMenu: null

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

    ContextMenu.onRequested: position => base.openContextMenu(position)

    TapHandler {
        acceptedButtons: Qt.LeftButton | Qt.MiddleButton
        onTapped: base.openedMenu?.close()
    }

    Rectangle {
        id: surface

        anchors.fill: parent
        color: base.dark ? "#cc1e1e1e" : "#ccf3f3f3"
        border.width: 0
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
