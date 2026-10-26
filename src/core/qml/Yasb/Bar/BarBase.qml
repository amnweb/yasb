import QtQuick

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

    implicitWidth: vertical ? 0 : 2 * padding + contentImplicitLength
    implicitHeight: vertical ? 2 * padding + contentImplicitLength : 0

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
