import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: page

    required property QtObject cloud

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 12

        RowLayout {
            Label {
                Layout.fillWidth: true
                text: qsTr("Settings")
                font.pixelSize: 20
                font.weight: Font.DemiBold
            }

            Button {
                implicitWidth: implicitContentWidth + leftPadding + rightPadding
                leftPadding: 12
                rightPadding: 12
                Accessible.name: qsTr("Back")
                ToolTip.visible: hovered
                ToolTip.text: qsTr("Back")
                contentItem: Glyph {
                    text: "\ue72b"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                onClicked: page.cloud.closeSettings()
            }
        }

        ScrollView {
            id: scroll

            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: availableWidth

            ColumnLayout {
                width: scroll.availableWidth
                spacing: 4

                Frame {
                    Layout.fillWidth: true

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 10

                        RowLayout {
                            spacing: 8

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 2

                                Label {
                                    text: qsTr("Excluded files")
                                }

                                Caption {
                                    Layout.fillWidth: true
                                    text: qsTr("Files and folders left out of every backup")
                                }
                            }

                            Button {
                                text: qsTr("Preview")
                                onClicked: page.cloud.previewExcluded()
                            }

                            Button {
                                text: qsTr("Add rule")
                                highlighted: true
                                onClicked: {
                                    ruleField.text = ""
                                    ruleDialog.open()
                                    ruleField.forceActiveFocus()
                                }
                            }
                        }

                        Caption {
                            Layout.fillWidth: true
                            text: qsTr("Logs, caches and temporary files are already excluded. %1 are always kept.")
                                .arg(page.cloud.alwaysKept)
                        }

                        LinkButton {
                            Layout.leftMargin: -leftPadding
                            text: qsTr("Learn more")
                            onClicked: page.cloud.openDocs()
                        }

                        InfoBar {
                            Layout.fillWidth: true
                            visible: page.cloud.infoSeverity !== ""
                            title: page.cloud.infoTitle
                            message: page.cloud.infoMessage
                            severity: page.cloud.infoSeverity
                        }

                        Caption {
                            visible: page.cloud.excludeRules.length === 0
                            text: qsTr("No patterns yet")
                        }

                        Repeater {
                            model: page.cloud.excludeRules

                            Frame {
                                id: rule

                                required property string modelData

                                Layout.fillWidth: true
                                topPadding: 6
                                bottomPadding: 6

                                RowLayout {
                                    anchors.fill: parent

                                    Label {
                                        Layout.fillWidth: true
                                        text: rule.modelData
                                        elide: Text.ElideRight
                                    }

                                    Button {
                                        text: qsTr("Remove")
                                        onClicked: page.cloud.removeRule(rule.modelData)
                                    }
                                }
                            }
                        }
                    }
                }

                SettingCard {
                    Layout.fillWidth: true
                    heading: qsTr("Automatic backup")
                    // A switch that will not move says nothing about why, so this names the reason and its limit
                    description: page.cloud.canWrite ? qsTr("Back up your configuration shortly after you change it")
                        : qsTr("Needs an active subscription. Your exclude rules are kept either way.")

                    Switch {
                        text: checked ? qsTr("On") : qsTr("Off")
                        checked: page.cloud.autoBackup
                        enabled: page.cloud.canWrite
                        onToggled: {
                            page.cloud.setAutoBackup(checked)
                            checked = Qt.binding(() => page.cloud.autoBackup)
                        }
                    }
                }

                SettingCard {
                    Layout.fillWidth: true
                    heading: qsTr("Detailed logging")
                    description: qsTr("Record everything the app does, not only problems. Turn on before reporting a bug.")

                    Switch {
                        text: checked ? qsTr("On") : qsTr("Off")
                        checked: page.cloud.debugLogging
                        onToggled: {
                            page.cloud.setDebugLogging(checked)
                            checked = Qt.binding(() => page.cloud.debugLogging)
                        }
                    }
                }

                SettingCard {
                    Layout.fillWidth: true
                    heading: qsTr("Log file")
                    description: page.cloud.logFile

                    Button {
                        text: qsTr("Open")
                        onClicked: page.cloud.openLogFolder()
                    }
                }
            }
        }
    }

    Dialog {
        id: ruleDialog

        anchors.centerIn: Overlay.overlay
        width: Math.min(460, page.width - 48)
        modal: true
        title: qsTr("Add Rule")

        ColumnLayout {
            width: ruleDialog.availableWidth
            spacing: 12

            Label {
                Layout.fillWidth: true
                text: qsTr("Files matching this pattern are left out of every backup:")
                wrapMode: Text.Wrap
            }

            TextField {
                id: ruleField

                Layout.fillWidth: true
                placeholderText: qsTr("e.g., *.env  or  secrets/*")
                onAccepted: ruleDialog.accept()
            }
        }

        footer: DialogButtonBox {
            Button {
                text: qsTr("Add")
                highlighted: true
                DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole
            }

            Button {
                text: qsTr("Cancel")
                DialogButtonBox.buttonRole: DialogButtonBox.RejectRole
            }
        }

        onAccepted: page.cloud.addRule(ruleField.text)
    }
}
