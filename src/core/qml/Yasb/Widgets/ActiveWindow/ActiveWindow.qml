import QtQuick
import QtQuick.Controls
import Yasb
import Yasb.Bar
import Yasb.Themes

Item {
    id: activeWindow

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
    required property BarBase bar
    readonly property Theme theme: bar.theme
    // Text on the bar takes the theme's colour, and labels the bar's font; parts set in font replace the bar's
    property color textColor: theme.colors.text
    property font font

    readonly property alias tracker: windowTracker
    readonly property bool dark: theme.dark
    readonly property bool shown: windowTracker.hasWindow || noWindowLabel !== ""

    implicitWidth: shown ? row.implicitWidth : 0
    implicitHeight: shown ? row.implicitHeight : 0
    visible: shown

    ActiveWindowTracker {
        id: windowTracker

        screenName: activeWindow.bar.screenName
        monitorExclusive: activeWindow.monitorExclusive
        label: activeWindow.label
        alternateLabel: activeWindow.alternateLabel
        noWindowLabel: activeWindow.noWindowLabel
        maxLength: activeWindow.maxLength
        ellipsis: activeWindow.ellipsis
        rewrite: activeWindow.rewrite
        ignoreTitles: activeWindow.ignoreTitles
        ignoreClasses: activeWindow.ignoreClasses
        ignoreProcesses: activeWindow.ignoreProcesses
    }

    Row {
        id: row

        height: parent.height
        spacing: 6

        Image {
            y: Math.round((parent.height - height) / 2)
            visible: activeWindow.showIcon && windowTracker.icon !== ""
            source: windowTracker.icon
            width: activeWindow.iconSize
            height: activeWindow.iconSize
            sourceSize: Qt.size(activeWindow.iconSize, activeWindow.iconSize)
        }

        Label {
            objectName: "title"
            anchors.verticalCenter: parent.verticalCenter
            text: windowTracker.text
            textFormat: Text.PlainText
            color: activeWindow.textColor
            font: activeWindow.font
        }
    }

    MouseArea {
        anchors.fill: parent
        onClicked: windowTracker.toggleLabel()
    }
}
