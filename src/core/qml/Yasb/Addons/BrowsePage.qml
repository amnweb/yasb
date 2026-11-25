pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// The addons of the chosen type, or what the search finds
Item {
    id: page

    required property AddonsState host
    // Cards come in one after another while this is set
    property bool arriving

    readonly property var shown: {
        const words = host.query.trim().toLowerCase()
        const found = host.addons.addons.filter(addon => words !== ""
            ? [addon.title, addon.id, addon.description, addon.author, addon.type]
                .some(field => field.toLowerCase().includes(words))
            : host.section === "all" || addon.type === host.section)
        return sort.currentIndex === 1 ? found.sort((a, b) => a.title.localeCompare(b.title)) : found
    }

    readonly property string heading: {
        if (host.searching)
            return qsTr("Results for “%1”").arg(host.query.trim())
        switch (host.section) {
        case "widget": return qsTr("Widgets")
        case "theme": return qsTr("Themes")
        case "layout": return qsTr("Layouts")
        case "config": return qsTr("Configs")
        default: return qsTr("All addons")
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 24
        anchors.rightMargin: 12
        anchors.topMargin: 16
        spacing: 12

        RowLayout {
            Layout.fillHeight: false
            Layout.rightMargin: 12
            spacing: 8

            Label {
                Layout.alignment: Qt.AlignVCenter
                Layout.fillWidth: true
                text: page.heading
                font.pixelSize: 20
                font.weight: Font.DemiBold
                elide: Text.ElideRight
            }

            ComboBox {
                id: sort

                Layout.alignment: Qt.AlignVCenter
                model: [qsTr("Newest"), qsTr("Name")]
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: !grid.visible

            BusyIndicator {
                anchors.centerIn: parent
                visible: running
                running: page.host.addons.state === "loading"
            }

            ColumnLayout {
                anchors.centerIn: parent
                width: Math.min(420, parent.width)
                visible: page.host.addons.state === "failed"
                spacing: 12

                Label {
                    Layout.fillWidth: true
                    text: qsTr("Couldn't reach %1").arg(page.host.addons.repository)
                    font.pixelSize: 16
                    font.weight: Font.DemiBold
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.Wrap
                }

                Label {
                    Layout.fillWidth: true
                    text: page.host.addons.error
                    color: page.host.secondaryText
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.Wrap
                }

                Button {
                    Layout.alignment: Qt.AlignHCenter
                    text: qsTr("Try again")
                    onClicked: page.host.addons.refresh()
                }
            }

            Label {
                anchors.centerIn: parent
                visible: page.host.addons.state === "ready" && page.shown.length === 0
                text: page.host.searching ? qsTr("No addons match your search.") : qsTr("No addons of this type yet.")
                color: page.host.secondaryText
            }
        }

        GridView {
            id: grid

            readonly property int columns: Math.max(1, Math.floor(width / 220))

            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: page.host.addons.state === "ready" && page.shown.length > 0
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            cellWidth: Math.floor(width / columns)
            cellHeight: cellWidth + 60
            model: page.shown
            ScrollBar.vertical: ScrollBar {}

            populate: Transition {
                id: arrival

                enabled: page.arriving

                SequentialAnimation {
                    PropertyAction {
                        property: "opacity"
                        value: 0
                    }

                    PropertyAction {
                        property: "rise"
                        value: 16
                    }

                    PauseAnimation {
                        duration: 80 + Math.min(arrival.ViewTransition.index, 11) * 30
                    }

                    ParallelAnimation {
                        NumberAnimation {
                            property: "opacity"
                            to: 1
                            duration: 250
                        }

                        NumberAnimation {
                            property: "rise"
                            to: 0
                            duration: 250
                            easing.type: Easing.BezierSpline
                            easing.bezierCurve: page.host.decelerate
                        }
                    }
                }
            }

            delegate: Item {
                id: cell

                required property var modelData
                property real rise

                width: grid.cellWidth
                height: grid.cellHeight

                AddonCard {
                    anchors.fill: parent
                    anchors.rightMargin: 12
                    anchors.bottomMargin: 12
                    transform: Translate {
                        y: cell.rise
                    }
                    host: page.host
                    addon: cell.modelData
                    offer: page.host.action(cell.modelData)
                    busy: page.host.addons.busy.includes(cell.modelData.id)
                    onClicked: page.host.shown = cell.modelData
                }
            }
        }
    }
}
