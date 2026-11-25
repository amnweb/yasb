import QtQuick
import QtQuick.Controls
import Yasb

TextArea {
    id: view

    property string markdown

    readonly property bool dark: Application.styleHints.colorScheme === Qt.Dark
    property color lineColor: dark ? Qt.alpha("#ffffff", 0.0837) : Qt.alpha("#000000", 0.0803)
    property color quoteColor: dark ? Qt.alpha("#ffffff", 0.786) : Qt.alpha("#000000", 0.6063)
    property color accentColor: system.accent
    property color successColor: dark ? "#6ccb5f" : "#0f7b0f"
    property color cautionColor: dark ? "#fce100" : "#9d5d00"
    property color criticalColor: dark ? "#ff99a4" : "#c42b1c"
    // The alert boxes
    property color strokeColor: dark ? Qt.alpha("#000000", 0.1) : Qt.alpha("#000000", 0.0578)
    property color infoFill: dark ? Qt.alpha("#ffffff", 0.0326) : Qt.alpha("#f6f6f6", 0.5)
    property color successFill: dark ? "#393d1b" : "#dff6dd"
    property color cautionFill: dark ? "#433519" : "#fff4ce"
    property color criticalFill: dark ? "#442726" : "#fde7e9"

    function show() {
        Markdown.show(textDocument, markdown, {
            line: lineColor,
            quote: quoteColor,
            accent: accentColor,
            success: successColor,
            caution: cautionColor,
            critical: criticalColor,
            stroke: strokeColor,
            infoFill: infoFill,
            successFill: successFill,
            cautionFill: cautionFill,
            criticalFill: criticalFill
        })
        // Else a ScrollView scrolls to the end, where new text leaves the cursor
        cursorPosition = 0
    }

    // The style sets each side apart
    topPadding: 0
    bottomPadding: 0
    leftPadding: 0
    rightPadding: 0
    readOnly: true
    selectByMouse: true
    wrapMode: TextEdit.Wrap
    background: null
    onMarkdownChanged: show()
    onDarkChanged: show()
    // Images load after the text
    onContentHeightChanged: Markdown.fitImages(textDocument, width)
    onWidthChanged: Markdown.fitImages(textDocument, width)
    onLinkActivated: link => Markdown.open(link)
    ContextMenu.menu: null

    TapHandler {
        acceptedButtons: Qt.RightButton
        onPressedChanged: {
            if (pressed === (Application.styleHints.contextMenuTrigger === Qt.ContextMenuTrigger.Press))
                textMenu.popup()
        }
    }

    Menu {
        id: textMenu

        popupType: Popup.Window
        onAboutToShow: contentItem.Window.window?.raise()
        enter: Transition {
            NumberAnimation {
                property: "opacity"
                from: 0
                to: 1
                duration: 150
                easing.type: Easing.OutCubic
            }
        }

        MenuItem {
            text: qsTr("Copy")
            icon.name: "edit-copy"
            enabled: view.selectedText !== ""
            onTriggered: view.copy()
        }
        MenuItem {
            text: qsTr("Select All")
            icon.name: "edit-select-all"
            onTriggered: view.selectAll()
        }
    }

    SystemPalette {
        id: system
    }

    HoverHandler {
        cursorShape: view.hoveredLink !== "" ? Qt.PointingHandCursor : Qt.IBeamCursor
    }
}
