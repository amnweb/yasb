pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Shapes
import Yasb
import Yasb.Bar
import Yasb.Themes

Item {
    id: audioVisualizer

    component Settings: QtObject {
        required property Theme theme

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
        // Takes the theme's text colour unless the widget file sets it
        property color color: theme.colors.text
    }

    required property BarBase bar
    readonly property Theme theme: bar.theme
    readonly property Settings settings: Settings {
        theme: audioVisualizer.theme
    }

    readonly property bool dark: theme.dark

    readonly property bool shown: !settings.hideIdle || levels.playing
    readonly property var samples: levels.levels
    readonly property int count: settings.style === "waves" ? Math.max(4, Math.min(128, Math.floor(settings.waveWidth / 5))) : settings.style === "dots" ? settings.dotCount : settings.barCount
    readonly property int graphWidth: settings.style === "waves" ? settings.waveWidth : settings.style === "dots" ? settings.dotCount * Math.max(2, settings.dotSize + settings.dotGap) : settings.barCount * (settings.barWidth + settings.barGap)
    readonly property real fadeLeft: Math.max(0, Array.isArray(settings.edgeFade) ? settings.edgeFade[0] ?? 0 : settings.edgeFade)
    readonly property real fadeRight: Math.max(0, Array.isArray(settings.edgeFade) ? settings.edgeFade[1] ?? 0 : settings.edgeFade)

    // Bars and dots are placed in physical pixels, so every bar and gap keeps the same width at 125% or 150%
    readonly property real ratio: Screen.devicePixelRatio || 1
    readonly property int heightPx: Math.floor(settings.graphHeight * ratio)

    implicitWidth: shown ? graphWidth : 0
    implicitHeight: shown ? settings.graphHeight : 0
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
        return Math.max(1, Math.min(settings.graphHeight, Math.round(Math.max(0, Math.min(1, level)) * settings.graphHeight)));
    }

    AudioLevels {
        id: levels

        source: audioVisualizer.settings.source
        bands: audioVisualizer.count
        stereo: audioVisualizer.settings.channels === "stereo"
        monoChannel: audioVisualizer.settings.monoChannel
        reverse: audioVisualizer.settings.reverse
        sensitivity: audioVisualizer.settings.sensitivity
        smoothness: audioVisualizer.settings.smoothness
        autoGain: audioVisualizer.settings.autoGain
        freqMin: audioVisualizer.settings.freqMin
        freqMax: audioVisualizer.settings.freqMax
        framerate: audioVisualizer.settings.framerate
        idleAfter: audioVisualizer.settings.hideIdleAfter
        running: audioVisualizer.visible
    }

    Item {
        id: graph

        y: Math.round((audioVisualizer.height - height) / 2)
        width: audioVisualizer.graphWidth
        height: audioVisualizer.settings.graphHeight

        Repeater {
            model: audioVisualizer.settings.style === "bars" ? audioVisualizer.count : 0

            Rectangle {
                required property int index
                readonly property int step: Math.round((audioVisualizer.settings.barWidth + audioVisualizer.settings.barGap) * audioVisualizer.ratio)
                readonly property int heightPx: Math.max(1, Math.round(audioVisualizer.heightOf(audioVisualizer.samples[index] ?? 0) * audioVisualizer.ratio))

                x: (Math.round(Math.floor(audioVisualizer.settings.barGap / 2) * audioVisualizer.ratio) + index * step) / audioVisualizer.ratio
                y: (audioVisualizer.settings.mirror ? Math.floor((audioVisualizer.heightPx - heightPx) / 2) : audioVisualizer.heightPx - heightPx) / audioVisualizer.ratio
                width: Math.max(1, Math.round(audioVisualizer.settings.barWidth * audioVisualizer.ratio)) / audioVisualizer.ratio
                height: heightPx / audioVisualizer.ratio
                color: Qt.alpha(audioVisualizer.settings.color, audioVisualizer.fadeAt(Math.floor(audioVisualizer.settings.barGap / 2) + index * (audioVisualizer.settings.barWidth + audioVisualizer.settings.barGap) + audioVisualizer.settings.barWidth / 2))
            }
        }

        Repeater {
            id: dotColumns

            // Dots stacked in one column, and the distance between them
            readonly property int pitch: audioVisualizer.settings.dotSize + audioVisualizer.settings.dotGap
            readonly property int slots: pitch > 0 ? Math.max(1, Math.floor((audioVisualizer.settings.graphHeight - audioVisualizer.settings.dotSize) / pitch) + 1) : 1
            readonly property int columnPitch: Math.max(pitch, Math.floor(audioVisualizer.graphWidth / Math.max(1, audioVisualizer.count)))

            model: audioVisualizer.settings.style === "dots" ? audioVisualizer.count : 0

            Item {
                id: column

                required property int index
                readonly property int start: index * dotColumns.columnPitch + Math.floor((dotColumns.columnPitch - audioVisualizer.settings.dotSize) / 2)
                readonly property int lit: Math.max(1, Math.min(dotColumns.slots, Math.round(Math.max(0, Math.min(1, audioVisualizer.samples[index] ?? 0)) * dotColumns.slots)))
                readonly property int first: audioVisualizer.settings.mirror ? Math.floor((dotColumns.slots - lit) / 2) : 0
                readonly property int sizePx: Math.max(1, Math.round(audioVisualizer.settings.dotSize * audioVisualizer.ratio))
                readonly property color dotColor: Qt.alpha(audioVisualizer.settings.color, audioVisualizer.fadeAt(start + audioVisualizer.settings.dotSize / 2))

                x: Math.round(Math.floor((dotColumns.columnPitch - audioVisualizer.settings.dotSize) / 2) * audioVisualizer.ratio + index * Math.round(dotColumns.columnPitch * audioVisualizer.ratio)) / audioVisualizer.ratio
                height: audioVisualizer.settings.graphHeight

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
            visible: audioVisualizer.settings.style === "waves"
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
                        color: Qt.alpha(audioVisualizer.settings.color, audioVisualizer.fadeLeft > 0 ? 0 : 1)
                    }
                    GradientStop {
                        position: Math.min(0.5, audioVisualizer.fadeLeft / audioVisualizer.graphWidth) / 2
                        color: Qt.alpha(audioVisualizer.settings.color, audioVisualizer.fadeLeft > 0 ? 0.5 : 1)
                    }
                    GradientStop {
                        position: Math.min(0.5, audioVisualizer.fadeLeft / audioVisualizer.graphWidth)
                        color: audioVisualizer.settings.color
                    }
                    GradientStop {
                        position: 1 - Math.min(0.5, audioVisualizer.fadeRight / audioVisualizer.graphWidth)
                        color: audioVisualizer.settings.color
                    }
                    GradientStop {
                        position: 1 - Math.min(0.5, audioVisualizer.fadeRight / audioVisualizer.graphWidth) / 2
                        color: Qt.alpha(audioVisualizer.settings.color, audioVisualizer.fadeRight > 0 ? 0.5 : 1)
                    }
                    GradientStop {
                        position: 1
                        color: Qt.alpha(audioVisualizer.settings.color, audioVisualizer.fadeRight > 0 ? 0 : 1)
                    }
                }

                PathSvg {
                    path: audioVisualizer.settings.style === "waves" ? wave.path(audioVisualizer.samples) : ""
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
            if (audioVisualizer.settings.channels === "stereo" && n >= 4) {
                // The left channel has the larger half when the count is odd
                const middle = n - Math.floor(n / 2);
                return part(samples.slice(0, middle), 0, width / 2) + part(samples.slice(middle), width / 2, width / 2);
            }
            return part(samples, 0, width);
        }

        function part(samples: var, x0: real, width: real): string {
            const height = audioVisualizer.settings.graphHeight;
            const centre = height / 2;
            const edges = sample => {
                const size = audioVisualizer.heightOf(sample);
                return audioVisualizer.settings.mirror ? [centre - size / 2, centre + size / 2] : [height - size, height];
            };
            const step = width / samples.length;
            const xs = samples.map((_, i) => x0 + i * step + step / 2);
            const tops = samples.map(sample => edges(sample)[0]);
            const first = edges(samples[0]);
            const last = edges(samples[samples.length - 1]);
            let path = `M${x0} ${first[1]} L${x0} ${first[0]} ` + curve(xs, tops) + ` L${x0 + width} ${last[0]} L${x0 + width} ${last[1]}`;
            if (audioVisualizer.settings.mirror)
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
