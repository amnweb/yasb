import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Templates as T
import Yasb.Cloud

// A setup page: title, description and scrolling content
Item {
    id: page

    property string title
    property string description
    default property alias content: column.data
    // For the widgets page, which scrolls while a widget is dragged to an edge
    readonly property T.ScrollBar scrollBar: scroll.ScrollBar.vertical

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        // Room for Back and Next
        anchors.bottomMargin: 72
        spacing: 4

        Label {
            Layout.fillWidth: true
            text: page.title
            font.pixelSize: 24
            font.weight: Font.DemiBold
        }

        Caption {
            Layout.fillWidth: true
            text: page.description
            font.pixelSize: 13
        }

        ScrollView {
            id: scroll

            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.topMargin: 16
            contentWidth: availableWidth
            // Hidden so it never covers the content; the wheel still scrolls
            ScrollBar.vertical.policy: ScrollBar.AlwaysOff

            ColumnLayout {
                id: column

                width: scroll.availableWidth
                spacing: 4
            }
        }
    }
}
