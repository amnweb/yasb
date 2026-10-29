import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// The preview a provider gives for the selected result: text, a large icon, an image, or a form to edit
Item {
    id: preview

    property var content: ({})
    // Alt+P shows previews of providers that hide them
    property bool forced: false
    property bool dark: false
    property color secondary: "gray"

    readonly property string kind: content.kind ?? ""
    readonly property bool editing: kind === "edit" && (content.fields?.length ?? 0) > 0

    signal action(string id, var values)
    signal cancelled()

    visible: (kind === "text" && (content.text || content.icon) || kind === "image" && content.image_data || editing)
        && (content.shown || forced)

    onEditingChanged: {
        if (!editing)
            cancelled()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 10
        visible: !preview.editing

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: preview.kind === "text" && !!preview.content.text
            contentWidth: availableWidth

            Label {
                width: parent.width
                text: preview.content.text ?? ""
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
            }
        }

        Image {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: preview.kind === "text" && !preview.content.text && !!preview.content.icon
            source: preview.content.icon ?? ""
            sourceSize: Qt.size(96, 96)
            fillMode: Image.Pad
        }

        Image {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: preview.kind === "image"
            source: preview.content.image_data ?? ""
            fillMode: Image.PreserveAspectFit
            asynchronous: true
        }

        Label {
            Layout.fillWidth: true
            visible: text !== ""
            text: preview.content.title ?? ""
            textFormat: Text.PlainText
            wrapMode: Text.WrapAnywhere
            font.weight: Font.DemiBold
        }

        Label {
            Layout.fillWidth: true
            visible: text !== ""
            text: preview.content.subtitle ?? ""
            textFormat: Text.PlainText
            wrapMode: Text.WrapAnywhere
            color: preview.secondary
            font.pixelSize: 12
        }

        GridLayout {
            Layout.fillWidth: true
            visible: (preview.content.metadata?.length ?? 0) > 0
            columns: 2
            columnSpacing: 12
            rowSpacing: 2

            Repeater {
                model: preview.content.metadata ?? []

                delegate: Label {
                    required property string modelData
                    required property int index

                    Layout.fillWidth: index % 2 === 1
                    horizontalAlignment: index % 2 ? Text.AlignRight : Text.AlignLeft
                    text: modelData
                    textFormat: Text.PlainText
                    elide: Text.ElideLeft
                    color: preview.secondary
                    font.pixelSize: 12
                }
            }
        }
    }

    ColumnLayout {
        id: form

        anchors.fill: parent
        anchors.margins: 14
        spacing: 6
        visible: preview.editing

        Repeater {
            id: fields

            model: preview.editing ? preview.content.fields : []

            delegate: ColumnLayout {
                id: field

                required property var modelData
                readonly property bool multiline: modelData.type === "multiline"
                readonly property string value: multiline ? area.text : line.text

                Layout.fillWidth: true
                Layout.fillHeight: multiline
                spacing: 4

                Label {
                    visible: text !== ""
                    text: field.modelData.label ?? ""
                    font.weight: Font.DemiBold
                }

                TextField {
                    id: line

                    Layout.fillWidth: true
                    visible: !field.multiline
                    text: field.modelData.value ?? ""
                    placeholderText: field.modelData.placeholder ?? ""
                }

                ScrollView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: field.multiline

                    TextArea {
                        id: area

                        text: field.modelData.value ?? ""
                        placeholderText: field.modelData.placeholder ?? ""
                        wrapMode: TextEdit.Wrap
                    }
                }
            }
        }

        DialogButtonBox {
            Layout.fillWidth: true
            padding: 0
            background: null
            standardButtons: DialogButtonBox.Save | DialogButtonBox.Cancel

            onAccepted: {
                const values = {}
                for (let i = 0; i < fields.count; i++) {
                    const item = fields.itemAt(i)
                    values[item.modelData.id] = item.value
                }
                preview.action(preview.content.action ?? "save", values)
            }
            onRejected: preview.action("cancel", {})
        }
    }
}
