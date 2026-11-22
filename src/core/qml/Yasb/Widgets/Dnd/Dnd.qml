import QtQuick
import QtQuick.Controls
import Yasb
import Yasb.Bar
import Yasb.Themes

Item {
    id: dnd

    component Settings: QtObject {
        required property Theme theme

        // The bar icon for each mode, drawn in iconFont and the mode's colour
        property int iconSize: theme.bar.iconFont.pixelSize
        property string offIcon: "\uf4bd"
        property string priorityIcon: "\uf4bd"
        property string alarmsIcon: "\ue7ed"
        // What a left click turns on: priority or alarms. A right click goes off, priority, alarms
        property string activeMode: "priority"
        // The mode when the pointer rests on the widget
        property bool tooltip: true
        property color textColor: theme.colors.text
        // The icon while do not disturb is off, priority only and alarms only
        property color offColor: textColor
        property color priorityColor: theme.colors.accent
        property color alarmsColor: theme.colors.accent
        // Glyphs take the theme's icon font, each part unless the widget file sets it
        property font iconFont
        iconFont.family: theme.bar.iconFont.family
        iconFont.weight: theme.bar.iconFont.weight
        iconFont.variableAxes: theme.bar.iconFont.variableAxes
    }

    required property BarBase bar
    readonly property Theme theme: bar.theme
    readonly property Settings settings: Settings {
        theme: dnd.theme
    }

    readonly property bool dark: theme.dark
    readonly property string edge: bar.edge
    // disabled, priority, alarms, or unknown where Windows has no do not disturb
    readonly property string status: service.status
    readonly property color iconColor: status === "priority" ? settings.priorityColor
        : status === "alarms" ? settings.alarmsColor : settings.offColor
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
    Accessible.onPressAction: service.toggle(settings.activeMode)
    Keys.onReturnPressed: service.toggle(settings.activeMode)
    Keys.onSpacePressed: service.toggle(settings.activeMode)

    DoNotDisturb { id: service }

    Text {
        id: icon
        objectName: "icon"
        anchors.verticalCenter: parent.verticalCenter
        text: dnd.status === "priority" ? dnd.settings.priorityIcon : dnd.status === "alarms" ? dnd.settings.alarmsIcon : dnd.settings.offIcon
        color: dnd.iconColor
        opacity: service.available ? 1 : 0.4
        font.family: dnd.settings.iconFont.family
        font.weight: dnd.settings.iconFont.weight
        font.variableAxes: dnd.settings.iconFont.variableAxes
        font.pixelSize: dnd.settings.iconSize
    }

    MouseArea {
        id: area
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: service.available ? Qt.PointingHandCursor : Qt.ArrowCursor
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: mouse => {
            if (mouse.button === Qt.LeftButton)
                service.toggle(dnd.settings.activeMode)
            else
                service.cycle()
        }
    }

    ToolTip {
        popupType: Popup.Window
        visible: dnd.settings.tooltip && area.containsMouse
        delay: 400
        text: dnd.description
        // Away from the bar's edge
        y: dnd.edge === "bottom" ? -implicitHeight - 6 : dnd.height + 6
    }
}
