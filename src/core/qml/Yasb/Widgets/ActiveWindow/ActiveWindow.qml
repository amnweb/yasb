import QtQuick
import QtQuick.Controls
import Yasb
import Yasb.Bar
import Yasb.Themes

Item {
    id: activeWindow

    component Settings: QtObject {
        required property Theme theme

        property string label: "{win[title]}"
        property string alternateLabel: "[class_name='{win[class_name]}' exe='{win[process][name]}' hwnd={win[hwnd]}]"
        property string noWindowLabel: ""
        property bool showIcon: true
        property int iconSize: theme.bar.iconFont.pixelSize
        property int maxLength: 32
        property string ellipsis: "..."
        property bool monitorExclusive: false
        property var rewrite: []
        property list<string> ignoreTitles: []
        property list<string> ignoreClasses: []
        property list<string> ignoreProcesses: []
        // Text on the bar takes the theme's colour, and labels the bar's font; parts set in font replace the bar's
        property color textColor: theme.colors.text
        property font font
    }

    required property BarBase bar
    readonly property Theme theme: bar.theme
    readonly property Settings settings: Settings {
        theme: activeWindow.theme
    }

    readonly property alias tracker: windowTracker
    readonly property bool dark: theme.dark
    readonly property bool shown: windowTracker.hasWindow || settings.noWindowLabel !== ""

    implicitWidth: shown ? row.implicitWidth : 0
    implicitHeight: shown ? row.implicitHeight : 0
    visible: shown

    ActiveWindowTracker {
        id: windowTracker

        screenName: activeWindow.bar.screenName
        monitorExclusive: activeWindow.settings.monitorExclusive
        label: activeWindow.settings.label
        alternateLabel: activeWindow.settings.alternateLabel
        noWindowLabel: activeWindow.settings.noWindowLabel
        maxLength: activeWindow.settings.maxLength
        ellipsis: activeWindow.settings.ellipsis
        rewrite: activeWindow.settings.rewrite
        ignoreTitles: activeWindow.settings.ignoreTitles
        ignoreClasses: activeWindow.settings.ignoreClasses
        ignoreProcesses: activeWindow.settings.ignoreProcesses
    }

    Row {
        id: row

        height: parent.height
        spacing: 6

        Image {
            y: Math.round((parent.height - height) / 2)
            visible: activeWindow.settings.showIcon && windowTracker.icon !== ""
            source: windowTracker.icon
            width: activeWindow.settings.iconSize
            height: activeWindow.settings.iconSize
            sourceSize: Qt.size(activeWindow.settings.iconSize, activeWindow.settings.iconSize)
        }

        Label {
            objectName: "title"
            anchors.verticalCenter: parent.verticalCenter
            text: windowTracker.text
            textFormat: Text.PlainText
            color: activeWindow.settings.textColor
            font: activeWindow.settings.font
        }
    }

    MouseArea {
        anchors.fill: parent
        onClicked: windowTracker.toggleLabel()
    }
}
