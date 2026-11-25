pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// What is installed, with its updates
Item {
    id: page

    required property AddonsState host

    readonly property int updates: host.addons.installed.filter(row => row.update > 0).length

    function entry(id: string): var {
        return host.addons.addons.find(addon => addon.id === id) ?? null
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 24
        anchors.rightMargin: 24
        anchors.topMargin: 16
        anchors.bottomMargin: 24
        spacing: 12

        RowLayout {
            Layout.fillHeight: false
            spacing: 8

            Label {
                Layout.alignment: Qt.AlignVCenter
                text: qsTr("Installed")
                font.pixelSize: 20
                font.weight: Font.DemiBold
            }

            Label {
                Layout.alignment: Qt.AlignVCenter
                Layout.fillWidth: true
                Layout.leftMargin: 4
                text: page.updates > 0
                    ? qsTr("%1 installed · %2 with an update").arg(page.host.addons.installed.length).arg(page.updates)
                    : qsTr("%1 installed").arg(page.host.addons.installed.length)
                font.pixelSize: 12
                color: page.host.secondaryText
                elide: Text.ElideRight
            }

            Button {
                Layout.alignment: Qt.AlignVCenter
                text: qsTr("Install from a GitHub link...")
                onClicked: page.host.linkRequested()
            }

            Button {
                Layout.alignment: Qt.AlignVCenter
                text: qsTr("Update all")
                highlighted: true
                visible: page.host.addons.installed.some(row => row.update > 0 && row.type !== "config")
                enabled: !page.host.addons.configBusy
                onClicked: page.host.addons.updateAll()
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: !list.visible

            Label {
                anchors.centerIn: parent
                visible: page.host.addons.state !== "loading"
                text: qsTr("Nothing installed yet. Pick an addon in All, or install one from a GitHub link.")
                color: page.host.secondaryText
            }
        }

        ListView {
            id: list

            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: page.host.addons.installed.length > 0
            clip: true
            spacing: 4
            boundsBehavior: Flickable.StopAtBounds
            model: page.host.addons.installed
            ScrollBar.vertical: ScrollBar {}

            delegate: Rectangle {
                id: row

                required property var modelData

                readonly property var entry: page.entry(modelData.id)
                readonly property bool busy: page.host.addons.busy.includes(modelData.id)
                readonly property string details: [
                    modelData.id === modelData.title ? "" : modelData.id,
                    page.host.typeName(modelData.type),
                    modelData.version > 0 ? qsTr("Version %1").arg(modelData.version) : "",
                    modelData.source
                ].filter(part => part !== "").join("  ·  ")

                width: ListView.view.width
                implicitHeight: Math.max(68, content.implicitHeight + 24)
                radius: 4
                color: page.host.cardFill
                border.color: page.host.cardStroke

                RowLayout {
                    id: content

                    anchors.fill: parent
                    anchors.leftMargin: 16
                    anchors.rightMargin: 16
                    spacing: 16

                    RoundedImage {
                        Layout.alignment: Qt.AlignVCenter
                        Layout.preferredWidth: 32
                        Layout.preferredHeight: 32
                        source: row.entry !== null && row.entry.images.length > 0 ? row.entry.images[0] : ""
                        fill: page.host.subtleFill
                        glyph: row.modelData.type === "theme" ? "\uE790" : row.modelData.type === "layout" ? "\uE75A"
                            : row.modelData.type === "config" ? "\uE713" : "\uECA5"
                        glyphColor: page.host.secondaryText
                    }

                    ColumnLayout {
                        Layout.alignment: Qt.AlignVCenter
                        Layout.fillWidth: true
                        spacing: 0

                        Label {
                            Layout.fillWidth: true
                            text: row.modelData.title
                            elide: Text.ElideRight
                        }

                        Label {
                            Layout.fillWidth: true
                            text: row.details
                            font.pixelSize: 12
                            color: page.host.secondaryText
                            elide: Text.ElideRight
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            visible: row.modelData.external || row.modelData.problem !== ""
                            spacing: 6

                            Glyph {
                                Layout.alignment: Qt.AlignVCenter
                                text: "\uE7BA"
                                font.pixelSize: 12
                                color: page.host.cautionText
                            }

                            Label {
                                Layout.alignment: Qt.AlignVCenter
                                Layout.fillWidth: true
                                text: row.modelData.problem !== "" ? row.modelData.problem
                                    : qsTr("Installed from a GitHub link, not reviewed by YASB's developers")
                                font.pixelSize: 12
                                color: page.host.cautionText
                                elide: Text.ElideRight
                            }
                        }
                    }

                    Label {
                        Layout.alignment: Qt.AlignVCenter
                        Layout.maximumWidth: 260
                        visible: row.modelData.update === 0 && !row.busy
                        text: row.modelData.note === "up to date" || row.modelData.note === "" ? qsTr("Up to date")
                            : row.modelData.note
                        font.pixelSize: 12
                        color: page.host.secondaryText
                        elide: Text.ElideRight
                    }

                    Button {
                        Layout.alignment: Qt.AlignVCenter
                        visible: row.modelData.update > 0 || row.busy
                        text: row.busy ? qsTr("Working...") : qsTr("Update to v%1").arg(row.modelData.update)
                        highlighted: true
                        enabled: !row.busy && page.host.canStart(row.modelData.type)
                        onClicked: {
                            const data = row.modelData
                            if (data.type === "config")
                                page.host.actRequested(row.entry ?? { id: data.id, title: data.title, type: "config" }, 0)
                            else
                                page.host.addons.update(data.id)
                        }
                    }

                    Button {
                        Layout.alignment: Qt.AlignVCenter
                        implicitWidth: 32
                        implicitHeight: 32
                        padding: 0
                        flat: true
                        Accessible.name: qsTr("More")
                        ToolTip.visible: hovered
                        ToolTip.text: qsTr("More")
                        onClicked: menu.popup()

                        contentItem: Glyph {
                            text: "\uE712"
                        }

                        AddonsMenu {
                            id: menu

                            MenuItem {
                                text: qsTr("Open folder")
                                onTriggered: page.host.addons.openFolder(row.modelData.folder)
                            }

                            MenuItem {
                                text: qsTr("View details")
                                enabled: row.entry !== null
                                onTriggered: page.host.shown = row.entry
                            }
                        }
                    }
                }
            }
        }
    }
}
