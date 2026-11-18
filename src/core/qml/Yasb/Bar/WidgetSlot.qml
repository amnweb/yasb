pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls

Item {
    id: slot

    required property string name
    property string alignment: "left"
    property bool stretch: true
    property BarBase bar: null
    property int spacing: bar ? bar.spacing : 0

    readonly property bool vertical: bar ? bar.vertical : false
    readonly property Item content: vertical ? column : row
    readonly property real contentStart: vertical ? column.y : row.x
    readonly property real contentLength: vertical ? column.implicitHeight : row.implicitWidth
    readonly property real contentOffset: {
        const free = (vertical ? height : width) - contentLength
        if (alignment === "left" || alignment === "top")
            return 0
        if (alignment === "right" || alignment === "bottom")
            return free
        return Math.round(free / 2)
    }
    readonly property var widgets: bar ? bar.context.widgets[name] ?? [] : []

    function findBar(): BarBase {
        for (let item = parent; item; item = item.parent) {
            const found = item as BarBase
            if (found)
                return found
        }
        return null
    }

    implicitWidth: vertical ? (bar ? bar.width : 0) : contentLength
    implicitHeight: vertical ? contentLength : (bar ? bar.height : 0)

    Component.onCompleted: {
        if (!bar)
            bar = findBar()
        if (bar)
            bar.addSlot(slot)
        else
            console.warn(`WidgetSlot "${name}" is not inside a bar`)
    }

    Component {
        id: widget

        Loader {
            required property var modelData

            width: slot.vertical ? slot.width : Math.ceil(implicitWidth)
            height: slot.vertical ? Math.ceil(implicitHeight) : slot.height
            visible: status === Loader.Ready

            // Accepting the request keeps the bar's menu off widgets, a widget's own menu still opens first
            ContextMenu.onRequested: {}

            // Every widget is made with its bar already set, so it never runs without one
            Component.onCompleted: setSource(modelData.url, { bar: slot.bar })

            onStatusChanged: {
                if (status === Loader.Error)
                    console.warn(`Widget "${modelData.name}" failed to load from ${modelData.url}`)
            }
        }
    }

    Row {
        id: row

        x: slot.contentOffset
        height: slot.height
        spacing: slot.spacing

        Repeater {
            model: slot.vertical ? [] : slot.widgets
            delegate: widget
        }
    }

    Column {
        id: column

        y: slot.contentOffset
        width: slot.width
        spacing: slot.spacing

        Repeater {
            model: slot.vertical ? slot.widgets : []
            delegate: widget
        }
    }
}
