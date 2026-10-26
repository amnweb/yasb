import QtQuick
import QtQuick.Shapes

Bar {
    id: root

    property real railHeight: 4
    property real edgeRadius: 0
    property ShapeGradient fillGradient: null

    readonly property real barLength: vertical ? height : width
    readonly property real barThickness: vertical ? width : height
    readonly property var islands: islandSpans()

    property Shape islandShape: Shape {
        parent: root
        z: -1
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer

        ShapePath {
            fillColor: root.color
            fillGradient: root.fillGradient
            strokeWidth: -1
            PathSvg { path: root.fillPath() }
        }

        ShapePath {
            fillColor: "transparent"
            strokeColor: root.border.color
            strokeWidth: root.border.width > 0 ? root.border.width : -1
            capStyle: ShapePath.FlatCap
            PathSvg { path: root.outline(root.border.width / 2) }
        }
    }

    // A widget that declares `property bool island: false` ends the island it is in, and the next widget
    // starts a new one
    function islandSpans(): var {
        const spans = []
        const outside = []
        for (const slot of slots) {
            if (!slot.visible)
                continue
            let origin = slot.contentStart
            for (let item = slot; item && item !== root; item = item.parent)
                origin += vertical ? item.y : item.x
            let run = null
            for (const widget of slot.content.children) {
                const size = vertical ? widget.height : widget.width
                if (!widget.visible || size <= 0)
                    continue
                const start = origin + (vertical ? widget.y : widget.x)
                if (widget.item?.island === false) {
                    outside.push(start, start + size)
                    if (run)
                        spans.push(run)
                    run = null
                } else if (run) {
                    run[1] = start + size
                } else {
                    run = [start, start + size]
                }
            }
            if (run)
                spans.push(run)
        }
        for (const span of spans)
            span.splice(0, 2, Math.round(span[0] - padding), Math.round(span[1] + padding))
        spans.sort((a, b) => a[0] - b[0])

        const merged = []
        for (const [start, end] of spans) {
            const from = Math.max(0, start)
            const to = Math.min(barLength, end)
            const last = merged[merged.length - 1]
            if (to <= from)
                continue
            if (last && from <= last[1])
                last[1] = Math.max(last[1], to)
            else
                merged.push([from, to])
        }
        if (merged.length > 0) {
            const first = merged[0]
            const last = merged[merged.length - 1]
            if (first[0] <= radius && !outside.some(edge => edge < first[0]))
                first[0] = 0
            if (last[1] >= barLength - radius && !outside.some(edge => edge > last[1]))
                last[1] = barLength
        }
        return merged
    }

    function railSize(): real {
        return Math.min(railHeight, barThickness)
    }

    function cornerLimit(): real {
        return Math.max(0, Math.min(radius, (barThickness - railSize()) / 2))
    }

    function fillets(index: int): var {
        const [start, end] = islands[index]
        const previous = index > 0 ? islands[index - 1][1] : 0
        const next = index + 1 < islands.length ? islands[index + 1][0] : barLength
        return [
            start > 0 ? Math.min(cornerLimit(), (start - previous) / 2) : 0,
            end < barLength ? Math.min(cornerLimit(), (next - end) / 2) : 0,
        ]
    }

    // Item coordinates of a point `along` the bar's length and `across` it, away from the screen edge
    function point(along: real, across: real): string {
        switch (edge) {
        case "bottom":
            return `${along} ${barThickness - across}`
        case "left":
            return `${across} ${along}`
        case "right":
            return `${barThickness - across} ${along}`
        default:
            return `${along} ${across}`
        }
    }

    // SVG path along the side of the shape away from the screen edge, from the far end of the bar back to
    // its start, moved `inset` into the shape. The edge curves hang outside the item, in the space the
    // window adds for them.
    function outline(inset: real): string {
        const mirrored = edge === "bottom" || edge === "left"
        const arc = (r, along, across, sweep) => r > 0
            ? `A ${r} ${r} 0 0 ${mirrored ? 1 - sweep : sweep} ${point(along, across)}`
            : `L ${point(along, across)}`
        const length = barLength
        const rail = railSize() - inset
        const bottom = barThickness - inset
        const last = islands.length - 1
        const path = []
        if (last < 0 || islands[last][1] < length) {
            path.push(`M ${point(length, rail)}`)
        } else if (edgeRadius > 0) {
            path.push(`M ${point(length + inset, barThickness + edgeRadius)}`)
            path.push(arc(edgeRadius + inset, length - edgeRadius, bottom, 0))
        } else {
            path.push(`M ${point(length, bottom)}`)
        }

        for (let index = last; index >= 0; --index) {
            const [start, end] = islands[index]
            const [before, after] = fillets(index)
            const corner = Math.max(0, Math.min(cornerLimit(), (end - start) / 2) - inset)
            if (end < length) {
                path.push(`L ${point(end + after, rail)}`)
                path.push(arc(after + inset, end - inset, rail + inset + after, 0))
                path.push(`L ${point(end - inset, bottom - corner)}`)
                path.push(arc(corner, end - inset - corner, bottom, 1))
            }
            if (start > 0) {
                path.push(`L ${point(start + inset + corner, bottom)}`)
                path.push(arc(corner, start + inset, bottom - corner, 1))
                path.push(`L ${point(start + inset, rail + inset + before)}`)
                path.push(arc(before + inset, start - before, rail, 0))
            } else if (edgeRadius > 0) {
                path.push(`L ${point(edgeRadius, bottom)}`)
                path.push(arc(edgeRadius + inset, -inset, barThickness + edgeRadius, 0))
            } else {
                path.push(`L ${point(0, bottom)}`)
            }
        }
        if (last < 0 || islands[0][0] > 0)
            path.push(`L ${point(0, rail)}`)
        return path.join(" ")
    }

    function fillPath(): string {
        return `${outline(0)} L ${point(0, 0)} L ${point(barLength, 0)} Z`
    }

    radius: 12
    background.visible: false

    Component.onCompleted: {
        if (gradient)
            console.warn("IslandBar does not use gradient, which only fills a Rectangle. Set fillGradient to a LinearGradient from QtQuick.Shapes instead.")
    }
}
