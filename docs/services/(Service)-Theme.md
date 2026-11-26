# Windows theme

`import Yasb`

Whether Windows is in dark mode, with functions to switch it. Updates when Windows switches, from Settings or from
YASB.

## WindowsTheme

### Properties

#### dark : bool `read-only`

`true` when apps are in dark mode. `true` too when YASB can't read it.

### Functions

#### setDark(dark: bool)

Switches apps and the taskbar to dark or light mode together, as Windows Settings does.

#### toggle()

Switches to light mode when `dark`, otherwise to dark mode.

WindowsTheme has no signals.
