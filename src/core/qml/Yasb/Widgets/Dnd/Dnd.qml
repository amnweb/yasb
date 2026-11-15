import QtQuick
import QtQuick.Controls
import Yasb
import Yasb.Bar
import Yasb.Themes

Item {
    id: dnd

    required property BarBase bar
    readonly property Theme theme: bar.theme
    // The bar icon for each mode, drawn in iconFont and iconColor
    property int iconSize: theme.bar.iconFont.pixelSize
    property string offIcon: "\uf4bd"
    property string priorityIcon: "\uf4bd"
    property string alarmsIcon: "\ue7ed"
    // What a left click turns on: priority or alarms. A right click goes off, priority, alarms
    property string activeMode: "priority"
    // The mode when the pointer rests on the widget
    property bool tooltip: true

    readonly property bool dark: theme.dark
    property color textColor: theme.colors.text
    // The accent colour while do not disturb is on; by mode for example: status === "alarms" ? "#ff99a4" : textColor
    property color iconColor: status === "priority" || status === "alarms" ? theme.colors.accent : textColor
    // Glyphs take the theme's icon font, each part unless the widget file sets it
    property font iconFont
    iconFont.family: theme.bar.iconFont.family
    iconFont.weight: theme.bar.iconFont.weight
    iconFont.variableAxes: theme.bar.iconFont.variableAxes
    readonly property string edge: bar.edge
    // disabled, priority, alarms, or unknown where Windows has no do not disturb
    readonly property string status: service.status
    readonly property string description: {
        if (status === "priority")
            return qsTr("Do not disturb: priority only")
        if (status === "alarms")
            return qsTr("Do not disturb: alarms only")
        if (status === "disabled")
            return qsTr("Do not disturb: off")
        return qsTr("Do not disturb is not available")
    }

    implicitWidth: icon.implicitWidth
    implicitHeight: icon.implicitHeight
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: description
    Accessible.onPressAction: service.toggle(activeMode)
    Keys.onReturnPressed: service.toggle(activeMode)
    Keys.onSpacePressed: service.toggle(activeMode)

    DoNotDisturb { id: service }

    Text {
        id: icon
        objectName: "icon"
        anchors.verticalCenter: parent.verticalCenter
        text: dnd.status === "priority" ? dnd.priorityIcon : dnd.status === "alarms" ? dnd.alarmsIcon : dnd.offIcon
        color: dnd.iconColor
        opacity: service.available ? 1 : 0.4
        font.family: dnd.iconFont.family
        font.weight: dnd.iconFont.weight
        font.variableAxes: dnd.iconFont.variableAxes
        font.pixelSize: dnd.iconSize
    }

    MouseArea {
        id: area
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: service.available ? Qt.PointingHandCursor : Qt.ArrowCursor
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: mouse => {
            if (mouse.button === Qt.LeftButton)
                service.toggle(dnd.activeMode)
            else
                service.cycle()
        }
    }

    ToolTip {
        popupType: Popup.Window
        visible: dnd.tooltip && area.containsMouse
        delay: 400
        text: dnd.description
        // Away from the bar's edge
        y: dnd.edge === "bottom" ? -implicitHeight - 6 : dnd.height + 6
    }
}
