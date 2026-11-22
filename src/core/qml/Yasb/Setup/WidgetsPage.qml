pragma ComponentBehavior: Bound

import QtQml.Models
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Yasb.Cloud

// The widgets on the bar, by position
SetupPage {
    id: page

    required property Choices choices

    // While a widget is dragged
    property point pointer
    property real scrollSpeed: 0

    // Moves the dragged widget to the row under the pointer, and scrolls near an edge
    function follow(point: point): void {
        pointer = point
        const edge = 48
        const y = scrollBar.mapFromItem(null, point).y
        const depth = y < edge ? y - edge : y > scrollBar.height - edge ? y - scrollBar.height + edge : 0
        // Pixels a second
        scrollSpeed = Math.max(-edge, Math.min(edge, depth)) * 12
        // Never above row 0, the first header
        const target = list.indexAt(list.width / 2, list.contentItem.mapFromItem(null, point).y)
        if (target >= 1 && target !== list.dragged) {
            choices.moveWidget(list.dragged, target)
            list.dragged = target
        }
    }

    title: qsTr("Widgets")
    description: qsTr("Each side of the bar shows its widgets in this order, from left to right. Drag a widget by its grip to move it. Each widget's options are in its own file, which you can change later.")

    ListView {
        id: list

        // The row of the widget being dragged, or -1
        property int dragged: -1

        Layout.fillWidth: true
        Layout.preferredHeight: contentHeight
        // The page scrolls, not the list
        interactive: false
        spacing: 4
        model: page.choices.widgets

        add: Transition {
            NumberAnimation {
                property: "opacity"
                from: 0
                to: 1
                duration: 150
            }
        }

        remove: Transition {
            NumberAnimation {
                property: "opacity"
                to: 0
                duration: 150
            }
        }

        move: Transition {
            NumberAnimation {
                property: "y"
                duration: 150
                easing.type: Easing.OutCubic
            }
        }

        displaced: Transition {
            NumberAnimation {
                property: "y"
                duration: 150
                easing.type: Easing.OutCubic
            }
        }

        delegate: DelegateChooser {
            role: "header"

            DelegateChoice {
                roleValue: true

                Item {
                    id: header

                    required property int index
                    required property string name
                    required property string title

                    width: ListView.view.width
                    implicitHeight: headerRow.implicitHeight + (index === 0 ? 0 : 16) + 4

                    RowLayout {
                        id: headerRow

                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: 4

                        Label {
                            Layout.fillWidth: true
                            text: header.title
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                        }

                        Button {
                            text: qsTr("Add widgets")
                            onClicked: addDialog.show(header.name)
                        }
                    }
                }
            }

            DelegateChoice {
                roleValue: false

                WidgetCard {
                    required property int index

                    width: ListView.view.width
                    z: dragging ? 1 : 0
                    onDraggingChanged: {
                        list.dragged = dragging ? index : -1
                        if (!dragging)
                            page.scrollSpeed = 0
                    }
                    onDragPointChanged: {
                        if (dragging)
                            page.follow(dragPoint)
                    }
                    onRemoveRequested: page.choices.widgets.remove(index, 1)
                    onMoveRequested: step => page.choices.moveWidget(index, index + step)
                }
            }
        }
    }

    // Scrolls while a dragged widget is near an edge
    FrameAnimation {
        running: list.dragged >= 0 && page.scrollSpeed !== 0
        onTriggered: {
            const bar = page.scrollBar
            const step = page.scrollSpeed * frameTime * bar.size / bar.height
            bar.position = Math.max(0, Math.min(1 - bar.size, bar.position + step))
            page.follow(page.pointer)
        }
    }

    Dialog {
        id: addDialog

        // left, center or right
        property string position
        readonly property ListModel candidates: ListModel {}
        property int checkedCount: 0
        // Lower case, matched against each widget's name and description
        property string query: ""
        readonly property int matchCount: {
            let found = 0
            for (let index = 0; index < candidates.count; index++) {
                const candidate = candidates.get(index)
                if (matches(candidate.title, candidate.description))
                    found++
            }
            return found
        }

        function matches(title: string, description: string): bool {
            return query === "" || title.toLowerCase().includes(query) || description.toLowerCase().includes(query)
        }

        function show(at: string): void {
            position = at
            checkedCount = 0
            search.clear()
            candidates.clear()
            for (const { name, title, description, icon } of page.choices.available())
                candidates.append({ name, title, description, glyph: icon, picked: false })
            candidateList.positionViewAtBeginning()
            open()
            search.forceActiveFocus()
        }

        // The matches may sit above where the list was scrolled to
        onQueryChanged: candidateList.positionViewAtBeginning()

        parent: Overlay.overlay
        anchors.centerIn: parent
        width: 520
        modal: true
        popupType: Popup.Item
        title: {
            switch (position) {
            case "left": return qsTr("Add widgets on the left")
            case "center": return qsTr("Add widgets in the center")
            default: return qsTr("Add widgets on the right")
            }
        }
        header: Label {
            text: addDialog.title
            font.pixelSize: 16
            font.bold: true
            leftPadding: 24
            rightPadding: 0
            topPadding: 12
            bottomPadding: 0
        }
        // The default button is drawn in the accent color
        footer: DialogButtonBox {
            defaultButton: add

            Button {
                id: add

                text: qsTr("Add")
                enabled: addDialog.checkedCount > 0
                DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole
            }

            Button {
                text: qsTr("Cancel")
                DialogButtonBox.buttonRole: DialogButtonBox.RejectRole
            }
        }

        onAccepted: {
            for (let index = 0; index < candidates.count; index++) {
                const candidate = candidates.get(index)
                if (candidate.picked)
                    page.choices.addWidget(position, candidate.name)
            }
        }

        ColumnLayout {
            anchors.fill: parent
            spacing: 12

            TextField {
                id: search

                Layout.fillWidth: true
                visible: addDialog.candidates.count > 0
                placeholderText: qsTr("Search widgets")
                onTextChanged: addDialog.query = text.trim().toLowerCase()
            }

            Caption {
                Layout.fillWidth: true
                text: addDialog.candidates.count === 0 ? qsTr("Every widget the setup offers is on the bar.")
                    : addDialog.matchCount === 0 ? qsTr("No widgets match.")
                    : qsTr("They go after the widgets already there.")
            }

            ListView {
                id: candidateList

                // Measured with every row shown, so the dialog keeps its size while a search hides rows
                property real fullHeight: 0

                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(fullHeight, 300)
                clip: true
                model: addDialog.candidates
                ScrollBar.vertical: ScrollBar {}
                onContentHeightChanged: {
                    if (addDialog.query === "")
                        fullHeight = contentHeight
                }

                delegate: CheckDelegate {
                    id: candidate

                    required property int index
                    required property string title
                    required property string description
                    required property string glyph
                    required property bool picked
                    // Not visible, which also changes with the dialog's own visibility
                    readonly property bool matched: addDialog.matches(title, description)

                    width: ListView.view.width
                    height: matched ? implicitHeight : 0
                    visible: matched
                    // For the screen reader; the row below draws it
                    text: title
                    // From the model, so a recreated row keeps its check
                    checked: picked
                    onToggled: {
                        addDialog.candidates.setProperty(index, "picked", checked)
                        addDialog.checkedCount += checked ? 1 : -1
                    }

                    contentItem: RowLayout {
                        spacing: 14

                        Label {
                            Layout.preferredWidth: 20
                            text: candidate.glyph
                            font.family: "Segoe Fluent Icons"
                            font.pixelSize: 16
                            horizontalAlignment: Text.AlignHCenter
                            Accessible.ignored: true
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.rightMargin: candidate.indicator.width + candidate.spacing
                            spacing: 0

                            Label {
                                Layout.fillWidth: true
                                text: candidate.title
                                elide: Text.ElideRight
                            }

                            Caption {
                                Layout.fillWidth: true
                                text: candidate.description
                                elide: Text.ElideRight
                                wrapMode: Text.NoWrap
                            }
                        }
                    }
                }
            }
        }
    }
}
