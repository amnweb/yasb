# Notifier

`import Yasb` · a singleton: use it by its name, without creating it

Windows toasts and sounds for widgets.

Guide: [Writing widgets](./Writing-Widgets)

## Example

A widget that reminds you to take a break every 25 minutes, with a toast and YASB's notification sound:

```qml
// %USERPROFILE%\.config\yasb\widgets\Pomodoro\Pomodoro.qml
import QtQuick
import Yasb
import Yasb.Bar

Item {
    // The bar the widget is in; YASB sets it
    required property BarBase bar

    Timer {
        interval: 25 * 60 * 1000
        running: true
        repeat: true
        onTriggered: {
            Notifier.toast("Pomodoro", "Time for a break")
            Notifier.playSound()
        }
    }
}
```

To play a WAV file of your own beside the widget, give its URL: `Notifier.playSound(Qt.resolvedUrl("ding.wav"))`.

## Notifier

### Functions

#### toast(title: string, message: string)

Shows a Windows toast with this title and message, under YASB's name and icon. When Windows can't show it, the
error goes to the log.

#### playSound()

Plays YASB's notification sound.

#### playSound(source: string)

Plays a WAV file, given as a path or a file URL. A file that doesn't exist plays nothing, and logs a warning.

#### stopSound()

Stops the sound that is playing.

Notifier has no properties or signals.

## Used by

No YASB widget uses it.
