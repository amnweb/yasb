pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Yasb
import Yasb.Cloud

// The last page: startup options and the files Finish writes
SetupPage {
    id: page

    required property Setup setup
    required property Choices choices
    required property string error

    readonly property bool dark: Application.styleHints.colorScheme === Qt.Dark

    title: qsTr("You're all set")
    description: qsTr("Finish saves your choices and starts the bar.")

    InfoBar {
        Layout.fillWidth: true
        Layout.bottomMargin: 12
        visible: page.error !== ""
        severity: "warning"
        title: qsTr("Not saved")
        message: page.error
    }

    // Both need the installed yasb.exe
    Label {
        id: startup

        Layout.bottomMargin: 4
        visible: page.setup.canAutostart || page.setup.canCheckForUpdates
        text: qsTr("Startup")
        font.pixelSize: 14
        font.weight: Font.DemiBold
    }

    SettingCard {
        Layout.fillWidth: true
        visible: page.setup.canAutostart
        heading: qsTr("Start with Windows")
        description: qsTr("YASB starts when you sign in")

        Switch {
            checked: page.choices.autostart
            onToggled: page.choices.autostart = checked
        }
    }

    SettingCard {
        Layout.fillWidth: true
        visible: page.setup.canCheckForUpdates
        heading: qsTr("Check for updates")
        description: qsTr("Get a notification when a new version is available")

        Switch {
            checked: page.choices.updateCheck
            onToggled: page.choices.updateCheck = checked
        }
    }

    Label {
        Layout.topMargin: startup.visible ? 20 : 0
        text: qsTr("Your files")
        font.pixelSize: 14
        font.weight: Font.DemiBold
    }

    Caption {
        Layout.fillWidth: true
        Layout.bottomMargin: 4
        text: qsTr("Saved in %1. When you save a change to one, YASB applies it.").arg(page.setup.configFolder)
    }

    // Each side, as padding alone doesn't override the style's
    Frame {
        Layout.fillWidth: true
        leftPadding: 0
        rightPadding: 0
        topPadding: 0
        bottomPadding: 0

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            Repeater {
                model: [
                    {
                        glyph: "\uE713",
                        name: "config.yaml",
                        description: qsTr("YASB's settings, the theme to use, and your bar: its screens, edge, size, layout and widgets")
                    },
                    {
                        glyph: "\uE771",
                        name: `layouts/${page.choices.barStyle}.qml`,
                        description: qsTr("Your bar's look in QML: color, radius, border, padding and spacing, plus anything you add to it")
                    },
                    {
                        glyph: "\uE790",
                        name: `themes/${page.setup.themeName}.qml`,
                        description: qsTr("The colors and fonts of the bar and its widgets, and how popups and menus look and open")
                    }
                ]

                delegate: ColumnLayout {
                    id: file

                    required property var modelData
                    required property int index

                    Layout.fillWidth: true
                    spacing: 0

                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 1
                        visible: file.index > 0
                        color: page.dark ? Qt.alpha("#ffffff", 0.08) : Qt.alpha("#000000", 0.06)
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Layout.leftMargin: 16
                        Layout.rightMargin: 16
                        Layout.topMargin: 12
                        Layout.bottomMargin: 12
                        spacing: 12

                        Label {
                            text: file.modelData.glyph
                            font.family: "Segoe Fluent Icons"
                            font.pixelSize: 16
                            color: Qt.alpha(palette.windowText, 0.7)
                        }

                        Label {
                            Layout.preferredWidth: 140
                            text: file.modelData.name
                            elide: Text.ElideRight
                        }

                        Caption {
                            Layout.fillWidth: true
                            text: file.modelData.description
                        }
                    }
                }
            }
        }
    }
}
