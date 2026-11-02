import QtQuick
import Yasb

Item {
    id: activeWindow

    property string label: "{win[title]}"
    property string alternateLabel: "[class_name='{win[class_name]}' exe='{win[process][name]}' hwnd={win[hwnd]}]"
    property string noWindowLabel: ""
    property bool showIcon: true
    property int iconSize: 16
    property int maxLength: 32
    property string ellipsis: "..."
    property bool monitorExclusive: false
    property var rewrite: []
    property list<string> ignoreTitles: []
    property list<string> ignoreClasses: []
    property list<string> ignoreProcesses: []
    property Item bar: null
    // Text on the bar takes the bar's colour and font, each part unless the widget file sets it
    property color textColor: bar?.textColor ?? (dark ? "#ffffff" : "#000000")
    property font font
    font.family: bar?.font.family ?? Qt.application.font.family
    font.pixelSize: bar?.font.pixelSize ?? 13
    font.weight: bar?.font.weight ?? Font.Normal
    font.italic: bar?.font.italic ?? false
    font.letterSpacing: bar?.font.letterSpacing ?? 0
    font.capitalization: bar?.font.capitalization ?? Font.MixedCase
    font.variableAxes: bar?.font.variableAxes ?? ({})

    readonly property alias tracker: tracker
    readonly property bool dark: Qt.styleHints.colorScheme === Qt.ColorScheme.Dark
    readonly property bool shown: tracker.hasWindow || noWindowLabel !== ""

    implicitWidth: shown ? row.implicitWidth : 0
    implicitHeight: shown ? row.implicitHeight : 0
    visible: shown

    ActiveWindowTracker {
        id: tracker

        screenName: activeWindow.bar?.screenName ?? ""
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
            visible: activeWindow.showIcon && tracker.icon !== ""
            source: tracker.icon
            width: activeWindow.iconSize
            height: activeWindow.iconSize
            sourceSize: Qt.size(activeWindow.iconSize, activeWindow.iconSize)
        }

        Text {
            objectName: "title"
            anchors.verticalCenter: parent.verticalCenter
            text: tracker.text
            textFormat: Text.PlainText
            color: activeWindow.textColor
            font: activeWindow.font
        }
    }

    MouseArea {
        anchors.fill: parent
        onClicked: tracker.toggleLabel()
    }
}
