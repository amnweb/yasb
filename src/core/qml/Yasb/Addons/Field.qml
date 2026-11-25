import QtQuick
import QtQuick.Controls

// A text field with YASB's text menu in place of Qt's own
TextField {
    id: field

    ContextMenu.menu: null

    // A right-click opens the menu at the mouse cursor
    TapHandler {
        acceptedButtons: Qt.RightButton
        onPressedChanged: {
            if (pressed === (Application.styleHints.contextMenuTrigger === Qt.ContextMenuTrigger.Press))
                textMenu.popup()
        }
    }

    AddonsMenu {
        id: textMenu

        readonly property bool selected: field.selectedText.length > 0

        popupType: Popup.Window
        onAboutToShow: contentItem.Window.window?.raise()

        MenuItem {
            text: qsTr("Undo")
            icon.name: "edit-undo"
            enabled: field.canUndo
            onTriggered: field.undo()
        }
        MenuItem {
            text: qsTr("Redo")
            icon.name: "edit-redo"
            enabled: field.canRedo
            onTriggered: field.redo()
        }
        MenuSeparator {}
        MenuItem {
            text: qsTr("Cut")
            icon.name: "edit-cut"
            enabled: textMenu.selected
            onTriggered: field.cut()
        }
        MenuItem {
            text: qsTr("Copy")
            icon.name: "edit-copy"
            enabled: textMenu.selected
            onTriggered: field.copy()
        }
        MenuItem {
            text: qsTr("Paste")
            icon.name: "edit-paste"
            enabled: field.canPaste
            onTriggered: field.paste()
        }
        MenuItem {
            text: qsTr("Delete")
            icon.name: "edit-delete"
            enabled: textMenu.selected
            onTriggered: field.remove(field.selectionStart, field.selectionEnd)
        }
        MenuSeparator {}
        MenuItem {
            text: qsTr("Select All")
            icon.name: "edit-select-all"
            onTriggered: field.selectAll()
        }
    }
}
