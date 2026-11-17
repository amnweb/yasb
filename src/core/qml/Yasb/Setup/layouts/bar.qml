import QtQuick
import Yasb.Bar

// A bar across the whole screen edge. The widgets come from config.yaml; this file sets how the bar looks, for
// example its color, radius, border, padding or spacing.
Bar {
    id: bar

    color: theme.bar.background
    radius: 0
    padding: 12
    spacing: 12

    // A line along the side away from the screen: under a bar at the top, over a bar at the bottom
    Rectangle {
        parent: bar.background
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: bar.edge === "bottom" ? parent.top : undefined
        anchors.bottom: bar.edge === "bottom" ? undefined : parent.bottom
        height: 1
        color: bar.border.color
    }
}
