import QtQuick

BarBase {
    id: root

    property alias leftSlot: startItem
    property alias topSlot: startItem
    property alias centerSlot: centerItem
    property alias rightSlot: endItem
    property alias bottomSlot: endItem

    readonly property var lengths: sectionLengths((vertical ? height : width) - 2 * padding)

    // Stretching sections share the free space equally, but none gets shorter than its widgets
    function sectionLengths(available: real): var {
        const slots = [startItem, centerItem, endItem]
        const lengths = slots.map(slot => slot.contentLength)
        const flexible = slots.map((slot, index) => index)
            .filter(index => slots[index].stretch)
            .sort((a, b) => lengths[a] - lengths[b])
        let rest = available - slots.reduce((sum, slot, index) => sum + (slot.stretch ? 0 : lengths[index]), 0)
        while (flexible.length > 0) {
            const share = rest / flexible.length
            const longest = flexible[flexible.length - 1]
            if (lengths[longest] <= share) {
                flexible.forEach(index => lengths[index] = share)
                break
            }
            rest -= lengths[longest]
            flexible.pop()
        }
        return lengths
    }

    contentImplicitLength: startItem.contentLength + centerItem.contentLength + endItem.contentLength

    WidgetSlot {
        id: startItem

        objectName: `slot-${name}`
        name: root.vertical ? "top" : "left"
        bar: root
        alignment: root.vertical ? "top" : "left"
        width: root.vertical ? parent.width : root.lengths[0]
        height: root.vertical ? root.lengths[0] : parent.height
    }

    WidgetSlot {
        id: centerItem

        objectName: `slot-${name}`
        name: "center"
        bar: root
        alignment: "center"
        x: root.vertical ? 0 : startItem.x + startItem.width
        y: root.vertical ? startItem.y + startItem.height : 0
        width: root.vertical ? parent.width : root.lengths[1]
        height: root.vertical ? root.lengths[1] : parent.height
    }

    WidgetSlot {
        id: endItem

        objectName: `slot-${name}`
        name: root.vertical ? "bottom" : "right"
        bar: root
        alignment: root.vertical ? "bottom" : "right"
        x: root.vertical ? 0 : centerItem.x + centerItem.width
        y: root.vertical ? centerItem.y + centerItem.height : 0
        width: root.vertical ? parent.width : root.lengths[2]
        height: root.vertical ? root.lengths[2] : parent.height
    }
}
