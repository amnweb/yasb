import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

Item {
    id: page

    required property QtObject cloud

    function confirm(title: string, message: string, action: string, accent: bool, accepted: var) {
        confirmDialog.title = title
        confirmDialog.message = message
        confirmDialog.action = action
        confirmDialog.accent = accent
        confirmDialog.acceptAction = accepted
        confirmDialog.open()
    }

    function showShareLink(url: string) {
        shareDialog.url = url
        shareDialog.open()
    }

    // Paging follows the scroll position, so a first page that fits on screen asks for the next one too
    function loadMoreIfNear() {
        if (list.contentHeight - list.contentY - list.height < 240)
            page.cloud.loadMore()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 12

        RowLayout {
            spacing: 8

            Label {
                Layout.fillWidth: true
                text: qsTr("Backups")
                font.pixelSize: 20
                font.weight: Font.DemiBold
            }

            BusyIndicator {
                Layout.preferredWidth: 20
                Layout.preferredHeight: 20
                visible: running
                running: page.cloud.busy
            }

            Button {
                text: page.cloud.busy && page.cloud.busyText !== "" ? page.cloud.busyText : qsTr("Backup Now")
                highlighted: true
                enabled: page.cloud.canWrite && !page.cloud.busy
                onClicked: noteDialog.ask(qsTr("Backup Note"),
                    qsTr("Enter an optional label or note for this snapshot (max 100 chars):"), "", qsTr("Backup"),
                    note => page.cloud.backup(note))
            }

            Button {
                implicitWidth: implicitContentWidth + leftPadding + rightPadding
                leftPadding: 12
                rightPadding: 12
                Accessible.name: qsTr("Settings")
                ToolTip.visible: hovered
                ToolTip.text: qsTr("Settings")
                contentItem: Glyph {
                    text: "\ue713"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                onClicked: page.cloud.openSettings()
            }
        }

        ListView {
            id: list

            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 4
            model: page.cloud.backups
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar {}

            onContentYChanged: page.loadMoreIfNear()
            onCountChanged: Qt.callLater(page.loadMoreIfNear)
            onHeightChanged: page.loadMoreIfNear()

            delegate: Frame {
                id: row

                required property string snapshotId
                required property string note
                required property string details
                required property string shareUrl
                required property bool pending

                width: ListView.view.width

                RowLayout {
                    anchors.fill: parent
                    spacing: 12

                    Glyph {
                        Layout.preferredWidth: 20
                        text: row.shareUrl !== "" ? "\ue72d" : "\uea18"
                        color: row.shareUrl !== "" ? system.accent : Qt.alpha(palette.windowText, 0.7)

                        HoverHandler {
                            id: markHover
                        }

                        ToolTip.visible: row.shareUrl !== "" && markHover.hovered
                        ToolTip.text: qsTr("Anyone with the link can download this backup")
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0

                        Label {
                            Layout.fillWidth: true
                            text: row.note
                            elide: Text.ElideRight
                        }

                        Caption {
                            Layout.fillWidth: true
                            text: row.details
                            elide: Text.ElideRight
                            wrapMode: Text.NoWrap
                        }
                    }

                    Button {
                        id: actionsButton

                        text: qsTr("Actions")
                        enabled: !row.pending
                        onClicked: actions.show(row.snapshotId, row.note, row.shareUrl, actionsButton)
                    }
                }
            }

            Label {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.margins: 12
                y: 12
                visible: list.count === 0 && page.cloud.emptyMessage !== ""
                text: page.cloud.emptyMessage
                wrapMode: Text.Wrap
            }
        }
    }

    SystemPalette {
        id: system
    }

    Menu {
        id: actions

        property string snapshotId
        property string note
        property string shareUrl

        function show(snapshotId: string, note: string, shareUrl: string, button: Item) {
            actions.snapshotId = snapshotId
            actions.note = note
            actions.shareUrl = shareUrl
            actions.popup(button, 0, button.height)
        }

        MenuItem {
            text: qsTr("Restore")
            onTriggered: page.confirm(qsTr("Restore this backup?"),
                qsTr("YASB will stop, your files will be replaced, and it will start again. "
                    + "A copy of your current configuration is saved first."),
                qsTr("Restore"), false, () => page.cloud.restore(actions.snapshotId))
        }

        MenuItem {
            text: qsTr("Save a copy")
            onTriggered: {
                folderDialog.snapshotId = actions.snapshotId
                folderDialog.open()
            }
        }

        MenuItem {
            visible: actions.shareUrl === ""
            height: visible ? implicitHeight : 0
            text: qsTr("Share publicly")
            onTriggered: page.confirm(qsTr("Share publicly?"),
                qsTr("Anyone with the link can download this backup. Your configuration is published as it is, "
                    + "including any API keys or tokens it contains.\n\n"
                    + "You can stop sharing at any time, which makes the link stop working."),
                qsTr("Share"), true, () => page.cloud.share(actions.snapshotId))
        }

        MenuItem {
            visible: actions.shareUrl !== ""
            height: visible ? implicitHeight : 0
            text: qsTr("Copy link")
            onTriggered: page.showShareLink(actions.shareUrl)
        }

        MenuItem {
            visible: actions.shareUrl !== ""
            height: visible ? implicitHeight : 0
            text: qsTr("Stop sharing")
            onTriggered: page.cloud.unshare(actions.snapshotId)
        }

        MenuItem {
            text: qsTr("Edit note")
            onTriggered: noteDialog.ask(qsTr("Edit Note"), qsTr("Rename this snapshot so you can recognise it later"),
                actions.note, qsTr("Save"), note => page.cloud.rename(actions.snapshotId, note))
        }

        MenuSeparator {}

        MenuItem {
            text: qsTr("Delete")
            onTriggered: page.confirm(qsTr("Delete this backup?"), qsTr("This cannot be undone."), qsTr("Delete"), false,
                () => page.cloud.delete(actions.snapshotId))
        }
    }

    FolderDialog {
        id: folderDialog

        property string snapshotId

        title: qsTr("Choose where to save this backup")
        onAccepted: page.cloud.saveCopy(snapshotId, selectedFolder)
    }

    Dialog {
        id: confirmDialog

        property string message
        property string action
        property bool accent
        property var acceptAction: null

        anchors.centerIn: Overlay.overlay
        width: Math.min(460, page.width - 48)
        modal: true

        Label {
            width: confirmDialog.availableWidth
            text: confirmDialog.message
            wrapMode: Text.Wrap
        }

        footer: DialogButtonBox {
            Button {
                text: confirmDialog.action
                highlighted: confirmDialog.accent
                DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole
            }

            Button {
                text: qsTr("Cancel")
                highlighted: !confirmDialog.accent
                DialogButtonBox.buttonRole: DialogButtonBox.RejectRole
            }
        }

        onAccepted: acceptAction?.()
    }

    Dialog {
        id: noteDialog

        property string message
        property string action
        property var acceptAction: null

        function ask(title: string, message: string, text: string, action: string, accepted: var) {
            noteDialog.title = title
            noteDialog.message = message
            noteDialog.action = action
            noteDialog.acceptAction = accepted
            noteField.text = text
            noteDialog.open()
            noteField.forceActiveFocus()
            noteField.selectAll()
        }

        anchors.centerIn: Overlay.overlay
        width: Math.min(460, page.width - 48)
        modal: true

        ColumnLayout {
            width: noteDialog.availableWidth
            spacing: 12

            Label {
                Layout.fillWidth: true
                text: noteDialog.message
                wrapMode: Text.Wrap
            }

            TextField {
                id: noteField

                Layout.fillWidth: true
                placeholderText: qsTr("e.g., My Custom Dark Theme Setup")
                maximumLength: page.cloud.noteMaxLength
                onAccepted: noteDialog.accept()
            }
        }

        footer: DialogButtonBox {
            Button {
                text: noteDialog.action
                highlighted: true
                DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole
            }

            Button {
                text: qsTr("Cancel")
                DialogButtonBox.buttonRole: DialogButtonBox.RejectRole
            }
        }

        onAccepted: acceptAction?.(noteField.text)
    }

    Dialog {
        id: shareDialog

        property string url

        anchors.centerIn: Overlay.overlay
        width: Math.min(460, page.width - 48)
        modal: true
        title: qsTr("Share link")

        ColumnLayout {
            width: shareDialog.availableWidth
            spacing: 12

            TextField {
                Layout.fillWidth: true
                text: shareDialog.url
                readOnly: true
                selectByMouse: true
            }

            Label {
                Layout.fillWidth: true
                text: qsTr("Anyone who has this link can download this backup.")
                wrapMode: Text.Wrap
            }
        }

        footer: DialogButtonBox {
            Button {
                text: qsTr("Copy link")
                highlighted: true
                DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole
            }

            Button {
                text: qsTr("Close")
                DialogButtonBox.buttonRole: DialogButtonBox.RejectRole
            }
        }

        onAccepted: page.cloud.copyText(url)
    }

    Connections {
        target: page.cloud

        function onShareLinkReady(url: string) {
            page.showShareLink(url)
        }
    }
}
