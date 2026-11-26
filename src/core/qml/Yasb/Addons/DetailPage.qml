pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Yasb.Common

// One addon and its README
Item {
    id: page

    required property AddonsState host
    required property var addon

    readonly property bool ready: !!addon
    readonly property var row: ready ? host.installedRow(addon.id) : null
    readonly property bool busy: ready && host.addons.busy.includes(addon.id)
    // The installed version, or 0
    readonly property int installed: row !== null ? row.version : 0
    readonly property int latest: ready ? addon.version : 0
    // The installed version when the addon has it, or the latest
    readonly property int preset: ready && addon.versions.includes(installed) ? installed : latest
    // The version the menu picked, which the button installs
    property int chosen: preset
    readonly property list<string> gallery: ready ? (addon.cover ? [addon.cover] : []).concat(addon.previews) : []
    property string about
    property string changes
    property bool readmeLoading: false

    readonly property string backText: {
        if (host.searching)
            return qsTr("Search results")
        switch (host.section) {
        case "widget": return qsTr("Widgets")
        case "theme": return qsTr("Themes")
        case "layout": return qsTr("Layouts")
        case "config": return qsTr("Configs")
        case "installed": return qsTr("Installed")
        default: return qsTr("All addons")
        }
    }

    readonly property string usage: {
        if (!ready)
            return ""
        if (addon.type === "widget")
            return qsTr("Add %1 to a bar's widgets in %2").arg(addon.id).arg(host.addons.configFile)
        return qsTr("Set a bar's %1 to %2 in %3").arg(addon.type).arg(addon.id).arg(host.addons.configFile)
    }

    // A pick replaces the binding, so another addon or an install goes back to the preset
    function pickPreset() {
        chosen = Qt.binding(() => page.preset)
    }

    onInstalledChanged: pickPreset()
    onAddonChanged: {
        pickPreset()
        about = ""
        changes = ""
        if (addon) {
            readmeLoading = true
            host.addons.loadReadme(addon.id)
            flick.contentY = 0
        }
    }

    Connections {
        target: page.host.addons

        function onReadmeLoaded(id: string, about: string, changes: string) {
            if (!page.ready || id !== page.addon.id)
                return
            page.about = about
            page.changes = changes
            page.readmeLoading = false
        }
    }

    // A link that opens the browser
    component LinkButton: Button {
        id: link

        flat: true
        leftPadding: 8
        rightPadding: 8
        palette.buttonText: system.accent

        contentItem: RowLayout {
            spacing: 6

            Label {
                Layout.alignment: Qt.AlignVCenter
                text: link.text
                color: system.accent
            }

            Glyph {
                Layout.alignment: Qt.AlignVCenter
                text: "\uE8A7"
                font.pixelSize: 12
                color: system.accent
            }
        }
    }

    component Card: Rectangle {
        id: card

        required property string heading
        default property alias content: body.data

        Layout.fillWidth: true
        implicitHeight: body.implicitHeight + 32
        radius: 8
        color: page.host.cardFill
        border.color: page.host.cardStroke

        ColumnLayout {
            id: body

            anchors.fill: parent
            anchors.margins: 16
            spacing: 8

            Label {
                text: card.heading
                font.pixelSize: 14
                font.weight: Font.DemiBold
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.bottomMargin: 4
                implicitHeight: 1
                color: page.host.divider
            }
        }
    }

    SystemPalette {
        id: system
    }

    ImageViewer {
        id: viewer

        images: page.gallery
    }

    Flickable {
        id: flick

        anchors.fill: parent
        contentHeight: layout.implicitHeight + 40
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {}

        ColumnLayout {
            id: layout

            x: 24
            y: 16
            width: flick.width - 48
            spacing: 12
            visible: page.ready

            Button {
                id: back

                Layout.leftMargin: -10
                flat: true
                leftPadding: 10
                rightPadding: 10
                text: page.backText
                onClicked: page.host.shown = null

                contentItem: RowLayout {
                    spacing: 8

                    Glyph {
                        Layout.alignment: Qt.AlignVCenter
                        text: "\uE72B"
                    }

                    Label {
                        Layout.alignment: Qt.AlignVCenter
                        text: back.text
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 24

                RoundedImage {
                    Layout.alignment: Qt.AlignTop
                    Layout.preferredWidth: 200
                    Layout.preferredHeight: 200
                    radius: 8
                    source: page.ready ? page.addon.cover : ""
                    fill: page.host.subtleFill
                    glyph: "\uE91B"
                    glyphSize: 40
                    glyphColor: page.host.secondaryText
                }

                ColumnLayout {
                    Layout.alignment: Qt.AlignTop
                    Layout.fillWidth: true
                    spacing: 0

                    Label {
                        Layout.fillWidth: true
                        text: page.ready ? page.addon.title : ""
                        font.pixelSize: 28
                        font.weight: Font.DemiBold
                        lineHeight: 36
                        lineHeightMode: Text.FixedHeight
                        wrapMode: Text.Wrap
                    }

                    LinkButton {
                        Layout.leftMargin: -8
                        text: page.ready ? page.addon.author : ""
                        onClicked: page.host.addons.open(page.addon.authorUrl)
                    }

                    Label {
                        Layout.fillWidth: true
                        Layout.topMargin: 4
                        text: page.ready ? [
                            page.host.typeName(page.addon.type),
                            qsTr("Version %1").arg(page.addon.version),
                            qsTr("Released %1").arg(page.host.date(page.addon.released)),
                            ...(page.row !== null && page.row.version > 0
                                ? [qsTr("You have version %1").arg(page.row.version)] : [])
                        ].join("  ·  ") : ""
                        font.pixelSize: 12
                        color: page.host.secondaryText
                        wrapMode: Text.Wrap
                    }

                    Label {
                        Layout.fillWidth: true
                        Layout.topMargin: 12
                        text: page.ready ? page.addon.description : ""
                        wrapMode: Text.Wrap
                    }

                    RowLayout {
                        Layout.topMargin: 16
                        spacing: 8

                        Button {
                            readonly property bool current: page.installed > 0 && page.chosen === page.installed

                            Layout.preferredWidth: Math.max(136, implicitWidth)
                            text: page.busy ? qsTr("Working...")
                                : current ? qsTr("Installed")
                                : page.installed > 0 && page.chosen > page.installed ? qsTr("Update")
                                : qsTr("Install")
                            highlighted: !current
                            enabled: page.ready && !page.busy && !current && page.host.canStart(page.addon.type)
                            // 0 is the latest, which updates an installed addon the usual way
                            onClicked: page.host.actRequested(page.addon, page.chosen === page.latest ? 0 : page.chosen)
                        }

                        // Only picks the version the button installs
                        ComboBox {
                            id: versions

                            visible: page.ready && page.addon.versions.length > 1
                            enabled: !page.busy
                            implicitContentWidthPolicy: ComboBox.WidestText
                            model: page.ready ? page.addon.versions.map(version => qsTr("v%1").arg(version)) : []
                            currentIndex: page.ready ? page.addon.versions.indexOf(page.chosen) : -1
                            onActivated: index => {
                                page.chosen = page.addon.versions[index]
                                // A pick sets currentIndex itself, which drops the binding
                                currentIndex = Qt.binding(() => page.ready ? page.addon.versions.indexOf(page.chosen) : -1)
                            }
                        }

                        Button {
                            id: copyButton

                            visible: page.ready && page.addon.type !== "config"
                            text: copied.running ? qsTr("Copied") : qsTr("Copy id")
                            Layout.preferredWidth: Math.max(implicitWidth, copiedText.advanceWidth + leftPadding + rightPadding)
                            ToolTip.visible: hovered
                            ToolTip.delay: 500
                            ToolTip.text: page.usage
                            onClicked: {
                                page.host.addons.copy(page.addon.id)
                                copied.restart()
                            }

                            TextMetrics {
                                id: copiedText

                                font: copyButton.font
                                text: qsTr("Copied")
                            }

                            Timer {
                                id: copied

                                interval: 2000
                            }
                        }

                        LinkButton {
                            text: qsTr("View on GitHub")
                            onClicked: page.host.addons.open(page.addon.pageUrl)
                        }
                    }
                }
            }

            Card {
                visible: page.gallery.length > 0
                heading: qsTr("Images")

                Flow {
                    Layout.fillWidth: true
                    spacing: 8

                    Repeater {
                        model: page.gallery

                        delegate: RoundedImage {
                            id: thumb

                            required property string modelData
                            required property int index

                            width: 106
                            height: 106
                            source: modelData
                            fill: page.host.subtleFill

                            TapHandler {
                                onTapped: viewer.show(thumb.index)
                            }

                            HoverHandler {
                                cursorShape: Qt.PointingHandCursor
                            }
                        }
                    }
                }
            }

            BusyIndicator {
                Layout.alignment: Qt.AlignHCenter
                visible: running
                running: page.readmeLoading
            }

            Card {
                visible: page.about !== ""
                heading: qsTr("About")

                MarkdownView {
                    Layout.fillWidth: true
                    markdown: page.about
                }
            }

            Card {
                visible: page.changes !== ""
                heading: qsTr("Changes")

                MarkdownView {
                    Layout.fillWidth: true
                    markdown: page.changes
                }
            }
        }
    }
}
