pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Shapes
import Yasb
import Yasb.Bar
import Yasb.Themes

Item {
    id: audioVisualizer

    required property BarBase bar
    readonly property Theme theme: bar.theme
    // "auto" follows the Windows default output device, or a device's full name like "Speakers (Realtek(R) Audio)"
    property string source: "auto"
    // bars, dots or waves
    property string style: "bars"
    // Height of the drawing in pixels
    property int graphHeight: 30
    // 0 to 100: higher is smoother and slower
    property int smoothness: 90
    // 0 to 100. With autoGain it sets how hard the loudest bands push to the top, otherwise 50 is 1x and 100 is 2x
    property int sensitivity: 50
    // Levels quiet and loud music to look the same
    property bool autoGain: true
    // Most updates per second
    property int framerate: 30
    // Frequency range in Hz
    property int freqMin: 50
    property int freqMax: 12000
    // Hide while nothing plays, hideIdleAfter milliseconds after the audio stops
    property bool hideIdle: true
    property int hideIdleAfter: 2000
    // mono or stereo. monoChannel is what mono shows: average, left or right
    property string channels: "mono"
    property string monoChannel: "average"
    // Mono: high to low frequencies. Stereo: bass on the outside edges instead of the middle
    property bool reverse: false
    // Grow from the middle instead of the bottom
    property bool mirror: true
    // Fade at the ends in pixels: one number for both, or [left, right]
    property var edgeFade: 0
    // Bars style
    property int barCount: 12
    property int barWidth: 2
    property int barGap: 4
    // Dots style
    property int dotCount: 12
    property int dotSize: 2
    property int dotGap: 4
    // Waves style: its width in pixels
    property int waveWidth: 80

    readonly property bool dark: theme.dark
    // Takes the theme's text colour unless the widget file sets it
    property color color: audioVisualizer.theme.colors.text

    readonly property bool shown: !hideIdle || levels.playing
    readonly property var samples: levels.levels
    readonly property int count: style === "waves" ? Math.max(4, Math.min(128, Math.floor(waveWidth / 5))) : style === "dots" ? dotCount : barCount
    readonly property int graphWidth: style === "waves" ? waveWidth : style === "dots" ? dotCount * Math.max(2, dotSize + dotGap) : barCount * (barWidth + barGap)
    readonly property real fadeLeft: Math.max(0, Array.isArray(edgeFade) ? edgeFade[0] ?? 0 : edgeFade)
    readonly property real fadeRight: Math.max(0, Array.isArray(edgeFade) ? edgeFade[1] ?? 0 : edgeFade)

    // Bars and dots are placed in physical pixels, so every bar and gap keeps the same width at 125% or 150%
    readonly property real ratio: Screen.devicePixelRatio || 1
    readonly property int heightPx: Math.floor(graphHeight * ratio)

    implicitWidth: shown ? graphWidth : 0
    implicitHeight: shown ? graphHeight : 0
    visible: shown

    // How visible a column centred at x is, with the edge fade
    function fadeAt(x: real): real {
        let left = fadeLeft;
        let right = fadeRight;
        if (left > 0 && right > 0) {
            left = Math.min(left, graphWidth / 2);
            right = Math.min(right, graphWidth / 2);
        } else {
            left = Math.min(left, graphWidth);
            right = Math.min(right, graphWidth);
        }
        const ease = t => t * t * (3 - 2 * t);
        if (left > 0 && x <= left)
            return ease(Math.max(0, x / left));
        if (right > 0 && x >= graphWidth - right)
            return ease(Math.max(0, (graphWidth - x) / right));
        return 1;
    }

    function heightOf(level: real): int {
        return Math.max(1, Math.min(graphHeight, Math.round(Math.max(0, Math.min(1, level)) * graphHeight)));
    }

    AudioLevels {
        id: levels

        source: audioVisualizer.source
        bands: audioVisualizer.count
        stereo: audioVisualizer.channels === "stereo"
        monoChannel: audioVisualizer.monoChannel
        reverse: audioVisualizer.reverse
        sensitivity: audioVisualizer.sensitivity
        smoothness: audioVisualizer.smoothness
        autoGain: audioVisualizer.autoGain
        freqMin: audioVisualizer.freqMin
        freqMax: audioVisualizer.freqMax
        framerate: audioVisualizer.framerate
        idleAfter: audioVisualizer.hideIdleAfter
        running: audioVisualizer.visible
    }

    Item {
        id: graph

        y: Math.round((audioVisualizer.height - height) / 2)
        width: audioVisualizer.graphWidth
        height: audioVisualizer.graphHeight

        Repeater {
            model: audioVisualizer.style === "bars" ? audioVisualizer.count : 0

            Rectangle {
                required property int index
                readonly property int step: Math.round((audioVisualizer.barWidth + audioVisualizer.barGap) * audioVisualizer.ratio)
                readonly property int heightPx: Math.max(1, Math.round(audioVisualizer.heightOf(audioVisualizer.samples[index] ?? 0) * audioVisualizer.ratio))

                x: (Math.round(Math.floor(audioVisualizer.barGap / 2) * audioVisualizer.ratio) + index * step) / audioVisualizer.ratio
                y: (audioVisualizer.mirror ? Math.floor((audioVisualizer.heightPx - heightPx) / 2) : audioVisualizer.heightPx - heightPx) / audioVisualizer.ratio
                width: Math.max(1, Math.round(audioVisualizer.barWidth * audioVisualizer.ratio)) / audioVisualizer.ratio
                height: heightPx / audioVisualizer.ratio
                color: Qt.alpha(audioVisualizer.color, audioVisualizer.fadeAt(Math.floor(audioVisualizer.barGap / 2) + index * (audioVisualizer.barWidth + audioVisualizer.barGap) + audioVisualizer.barWidth / 2))
            }
        }

        Repeater {
            id: dotColumns

            // Dots stacked in one column, and the distance between them
            readonly property int pitch: audioVisualizer.dotSize + audioVisualizer.dotGap
            readonly property int slots: pitch > 0 ? Math.max(1, Math.floor((audioVisualizer.graphHeight - audioVisualizer.dotSize) / pitch) + 1) : 1
            readonly property int columnPitch: Math.max(pitch, Math.floor(audioVisualizer.graphWidth / Math.max(1, audioVisualizer.count)))

            model: audioVisualizer.style === "dots" ? audioVisualizer.count : 0

            Item {
                id: column

                required property int index
                readonly property int start: index * dotColumns.columnPitch + Math.floor((dotColumns.columnPitch - audioVisualizer.dotSize) / 2)
                readonly property int lit: Math.max(1, Math.min(dotColumns.slots, Math.round(Math.max(0, Math.min(1, audioVisualizer.samples[index] ?? 0)) * dotColumns.slots)))
                readonly property int first: audioVisualizer.mirror ? Math.floor((dotColumns.slots - lit) / 2) : 0
                readonly property int sizePx: Math.max(1, Math.round(audioVisualizer.dotSize * audioVisualizer.ratio))
                readonly property color dotColor: Qt.alpha(audioVisualizer.color, audioVisualizer.fadeAt(start + audioVisualizer.dotSize / 2))

                x: Math.round(Math.floor((dotColumns.columnPitch - audioVisualizer.dotSize) / 2) * audioVisualizer.ratio + index * Math.round(dotColumns.columnPitch * audioVisualizer.ratio)) / audioVisualizer.ratio
                height: audioVisualizer.graphHeight

                Repeater {
                    model: dotColumns.slots

                    Rectangle {
                        required property int index
                        readonly property int yPx: audioVisualizer.heightPx - column.sizePx - index * Math.max(1, Math.round(dotColumns.pitch * audioVisualizer.ratio))

                        visible: yPx >= 0 && index >= column.first && index < column.first + column.lit
                        y: yPx / audioVisualizer.ratio
                        width: column.sizePx / audioVisualizer.ratio
                        height: width
                        color: column.dotColor
                    }
                }
            }
        }

        Shape {
            visible: audioVisualizer.style === "waves"
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer

            ShapePath {
                strokeWidth: -1
                fillGradient: LinearGradient {
                    x1: 0
                    x2: audioVisualizer.graphWidth

                    // The edge fade
                    GradientStop {
                        position: 0
                        color: Qt.alpha(audioVisualizer.color, audioVisualizer.fadeLeft > 0 ? 0 : 1)
                    }
                    GradientStop {
                        position: Math.min(0.5, audioVisualizer.fadeLeft / audioVisualizer.graphWidth) / 2
                        color: Qt.alpha(audioVisualizer.color, audioVisualizer.fadeLeft > 0 ? 0.5 : 1)
                    }
                    GradientStop {
                        position: Math.min(0.5, audioVisualizer.fadeLeft / audioVisualizer.graphWidth)
                        color: audioVisualizer.color
                    }
                    GradientStop {
                        position: 1 - Math.min(0.5, audioVisualizer.fadeRight / audioVisualizer.graphWidth)
                        color: audioVisualizer.color
                    }
                    GradientStop {
                        position: 1 - Math.min(0.5, audioVisualizer.fadeRight / audioVisualizer.graphWidth) / 2
                        color: Qt.alpha(audioVisualizer.color, audioVisualizer.fadeRight > 0 ? 0.5 : 1)
                    }
                    GradientStop {
                        position: 1
                        color: Qt.alpha(audioVisualizer.color, audioVisualizer.fadeRight > 0 ? 0 : 1)
                    }
                }

                PathSvg {
                    path: audioVisualizer.style === "waves" ? wave.path(audioVisualizer.samples) : ""
                }
            }
        }
    }

    QtObject {
        id: wave

        // The outline through the samples as an SVG path, rising from the bottom or split around the middle
        function path(samples: var): string {
            const n = samples.length;
            if (n < 2)
                return "";
            const width = audioVisualizer.graphWidth;
            if (audioVisualizer.channels === "stereo" && n >= 4) {
                // The left channel has the larger half when the count is odd
                const middle = n - Math.floor(n / 2);
                return part(samples.slice(0, middle), 0, width / 2) + part(samples.slice(middle), width / 2, width / 2);
            }
            return part(samples, 0, width);
        }

        function part(samples: var, x0: real, width: real): string {
            const height = audioVisualizer.graphHeight;
            const centre = height / 2;
            const edges = sample => {
                const size = audioVisualizer.heightOf(sample);
                return audioVisualizer.mirror ? [centre - size / 2, centre + size / 2] : [height - size, height];
            };
            const step = width / samples.length;
            const xs = samples.map((_, i) => x0 + i * step + step / 2);
            const tops = samples.map(sample => edges(sample)[0]);
            const first = edges(samples[0]);
            const last = edges(samples[samples.length - 1]);
            let path = `M${x0} ${first[1]} L${x0} ${first[0]} ` + curve(xs, tops) + ` L${x0 + width} ${last[0]} L${x0 + width} ${last[1]}`;
            if (audioVisualizer.mirror)
                path += " " + curve(xs.slice().reverse(), samples.map(sample => edges(sample)[1]).reverse());
            return path + " Z ";
        }

        // Smooth through the points: each one is the control point of a curve between the midpoints around it
        function curve(xs: var, ys: var): string {
            let path = `L${xs[0]} ${ys[0]}`;
            for (let i = 1; i < xs.length; i++)
                path += ` Q${xs[i - 1]} ${ys[i - 1]} ${(xs[i - 1] + xs[i]) / 2} ${(ys[i - 1] + ys[i]) / 2}`;
            return path + ` L${xs[xs.length - 1]} ${ys[ys.length - 1]}`;
        }
    }
}
