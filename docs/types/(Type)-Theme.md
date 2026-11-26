# Theme

`import Yasb.Themes` · inherits [QtObject](https://doc.qt.io/qt-6/qml-qtqml-qtobject.html)

The colors, fonts and shapes the bar and its widgets share. A theme file's root is Theme, and it sets only what it
changes: everything else keeps the default listed here.

Guide: [Themes](./Themes)

## Example

This theme changes the accent and critical colors, rounds the popups more and opens them faster, and makes the
right-click menus' text larger:

```qml
// %USERPROFILE%\.config\yasb\themes\mine.qml
import QtQuick
import Yasb.Themes

Theme {
    colors {
        accent: "#4CC2FF"
        critical: dark ? "#FF99A4" : "#C42B1C"
    }

    popup {
        radius: 12
        openDuration: 120
    }

    menu {
        font.pixelSize: 14
    }
}
```

```yaml
theme: mine
```

A widget reads its bar's theme as `bar.theme`, and a layout as `theme`:

```qml
Label {
    text: "CPU"
    color: root.bar.theme.colors.textSecondary
}
```

## Theme

`colors`, `bar`, `popup` and `menu` are groups. You can't replace a group, but you set the values inside it, as the
example does. Inside a theme file, `dark` and `system` are read by their names alone.

### Properties

#### dark : bool `read-only`

`true` while Windows is in dark mode, and it changes when you switch. Write a value as `dark ? A : B` to have `A` in dark mode and `B` in light mode.

#### system : [SystemPalette](https://doc.qt.io/qt-6/qml-qtquick-systempalette.html) `read-only`

Windows' own colors. `system.accent` is the accent color set in Windows.

#### colors : Colors `read-only`

See [Colors](#colors).

#### bar : Bar `read-only`

See [Bar](#bar).

#### popup : Popup `read-only`

See [Popup](#popup).

#### menu : Menu `read-only`

See [Menu](#menu).

Theme has no functions or signals.

## Colors

`text` to `textDisabled` go from the strongest text to the weakest.

### Properties

#### text : color

The strongest text, such as labels and titles.

Default: `dark ? "#FFFFFF" : Qt.alpha("#000000", 0.894)`

#### textSecondary : color

Text a step weaker than `text`.

Default: `dark ? Qt.alpha("#FFFFFF", 0.773) : Qt.alpha("#000000", 0.62)`

#### textTertiary : color

Text a step weaker than `textSecondary`.

Default: `dark ? Qt.alpha("#FFFFFF", 0.53) : Qt.alpha("#000000", 0.447)`

#### textDisabled : color

The weakest text, for what can't be used.

Default: `dark ? Qt.alpha("#FFFFFF", 0.365) : Qt.alpha("#000000", 0.36)`

#### textOnAccent : color

Text and icons on an `accent` fill.

Default: `dark ? "#000000" : "#FFFFFF"`

#### background : color

The base the bar and popups start from.

Default: `dark ? "#202020" : "#F3F3F3"`

#### backgroundSecondary : color

An area a step darker, laid over `background`.

Default: `dark ? Qt.alpha("#000000", 0.1) : Qt.alpha("#000000", 0.024)`

#### card : color

Boxes that hold a group of things.

Default: `dark ? Qt.alpha("#FFFFFF", 0.05) : Qt.alpha("#FFFFFF", 0.7)`

#### cardBorder : color

The outline of a `card`.

Default: `dark ? Qt.alpha("#000000", 0.1) : Qt.alpha("#000000", 0.06)`

#### border : color

The outer edges of the bar, popups and menus.

Default: `dark ? "#3A3A3A" : "#D9D9D9"`

#### divider : color

Lines between the parts of a popup, such as under its header.

Default: `dark ? Qt.alpha("#FFFFFF", 0.08) : Qt.alpha("#000000", 0.06)`

#### hover : color

A fill laid over any background, under the pointer.

Default: `dark ? Qt.alpha("#FFFFFF", 0.06) : Qt.alpha("#000000", 0.035)`

#### pressed : color

A fill laid over any background, while pressed.

Default: `dark ? Qt.alpha("#FFFFFF", 0.04) : Qt.alpha("#000000", 0.024)`

#### selected : color

A fill laid over any background, behind the selected or current item.

Default: `dark ? Qt.alpha("#FFFFFF", 0.06) : Qt.alpha("#000000", 0.035)`

#### control : color

A button's fill at rest.

Default: `dark ? Qt.alpha("#FFFFFF", 0.06) : Qt.alpha("#FFFFFF", 0.7)`

#### controlHover : color

A button's fill under the pointer.

Default: `dark ? Qt.alpha("#FFFFFF", 0.08) : Qt.alpha("#F9F9F9", 0.5)`

#### controlPressed : color

A button's fill while pressed.

Default: `dark ? Qt.alpha("#FFFFFF", 0.03) : Qt.alpha("#F9F9F9", 0.3)`

#### controlBorder : color

A button's outline.

Default: `dark ? Qt.alpha("#FFFFFF", 0.07) : Qt.alpha("#000000", 0.06)`

#### smoke : color

Laid over a popup's content to set it back behind something opened on top, such as a group.

Default: `Qt.alpha("#000000", 0.3)`

#### accent : color

The accent color.

Default: `system.accent`, the accent color set in Windows

#### success : color

Default: `dark ? "#6CCB5F" : "#0F7B0F"`

#### warning : color

Default: `dark ? "#FCE100" : "#9D5D00"`

#### critical : color

Default: `dark ? "#FF99A4" : "#C42B1C"`

## Bar

The bar itself, and the labels and icons of the widgets on it.

### Properties

#### background : color

The bar's fill, unless a layout sets its own `color`.

Default: `Qt.alpha(colors.background, 0.85)`

#### border : color

The bar's outline. It shows only where a layout gives the border a width.

Default: `colors.border`

#### font : [font](https://doc.qt.io/qt-6/qml-font.html)

The widgets' labels on the bar. Every `Label` in a widget takes it, each part the widget doesn't set itself.

Default: `family` `"Segoe UI"`, `pixelSize` `13`

#### iconFont : [font](https://doc.qt.io/qt-6/qml-font.html)

The widgets' icons on the bar and in popups, a widget's `iconSize` sets their size on the bar.

Default: `family` `"Segoe Fluent Icons"`, `pixelSize` `16`

## Popup

The popups that widgets open.

### Properties

#### background : color

Default: `Qt.alpha(colors.background, 0.85)`

#### border : color

Default: `colors.border`

#### radius : real

Default: `8`

#### gap : real

The space between the bar and the popup.

Default: `8`

#### openDuration : int

Milliseconds a popup takes to open.

Default: `180`

#### closeDuration : int

Milliseconds a popup takes to close.

Default: `140`

#### font : [font](https://doc.qt.io/qt-6/qml-font.html)

Only its family is used: each widget sets the sizes and weights of its own popup text.

Default: `family` `"Segoe UI"`

#### iconFont : [font](https://doc.qt.io/qt-6/qml-font.html)

Icons in popups, each widget sets their sizes.

Default: `family` `"Segoe Fluent Icons"`

## Menu

The right-click menus.

### Properties

#### background : color

Default: `dark ? "#2C2C2C" : "#F9F9F9"`

#### border : color

Default: `colors.border`

#### radius : real

Default: `8`

#### font : [font](https://doc.qt.io/qt-6/qml-font.html)

Default: `family` `"Segoe UI"`, `pixelSize` `13`

#### openDuration : int

Milliseconds a menu takes to fade in.

Default: `150`

## Used by

Every bar, YASB's bar menu, and the options of YASB's own widgets, which start from the theme's values.
