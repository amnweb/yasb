# Themes

A theme sets the colors and fonts of the bar, its widgets, its popups and its right-click menus. It's a QML file with
[Theme](./(Type)-Theme) as its root. You only set what you want to change, and everything else keeps its default. The
setup created `themes\yasb.qml` in your config folder with every value filled in, so the quickest way to start is to
edit that file.

## Pick a theme

`theme` in `config.yaml` picks the theme of every bar, and a bar's own `theme` picks one for that bar only.
[Layouts and themes](./Configuration#layouts-and-themes) explains the names it takes. Without one, a bar uses YASB's
own theme.

## Write a theme

This theme changes the accent color, the bar's background in dark mode, and the font of the labels on the bar:

```qml
// %USERPROFILE%\.config\yasb\themes\mine.qml
import QtQuick
import Yasb.Themes

Theme {
    colors {
        accent: "#4CC2FF"
        background: dark ? "#1C1C1C" : "#F3F3F3"
    }

    bar {
        font.family: "Segoe UI Variable Text"
        font.pixelSize: 14
    }
}
```

Name it in `config.yaml` with `theme: mine`. The bars change as soon as you save the file. If a
theme has an error or its root isn't `Theme`, it isn't used. The bar falls back to the default theme and an alert shows
the error.

A theme has four groups. The [Theme](./(Type)-Theme) page lists every value in them, with its default:

- `colors`: text from the strongest to the weakest, backgrounds, cards, borders, dividers, the fills under the
  pointer, buttons, and the accent, success, warning and critical colors.
- `bar`: the bar's background and border, the font of the labels on it, and the font of widget icons.
- `popup`: the background, border, corners and gap of the popups widgets open, how long they take to open and close,
  and their fonts.
- `menu`: the right-click menus' background, border, corners, font, and how long they take to fade in.

## Light and dark

`dark` is `true` while Windows is in dark mode, and the theme follows when you switch. Write a value as
`dark ? A : B` to have `A` in dark mode and `B` in light mode. A plain value is the same in both.

## The accent color

`system.accent` is the accent color set in Windows. YASB's theme uses it as `colors.accent`, so your bar changes with
Windows. A color such as `"#4CC2FF"` replaces it.

## Fonts

Fonts are Qt fonts, set one property at a time, such as `font.family`, `font.pixelSize`, `font.weight`,
`font.letterSpacing` or `font.variableAxes`. Setting one property changes only that property, and the rest are kept.

`bar.iconFont` and `popup.iconFont` draw the widgets' icons, which are glyphs of Segoe Fluent Icons. A different icon
font shows different glyphs, or none, unless you also change the icons in each widget's options.

## How themes reach widgets

Each widget's options start from the theme: the CPU graph's color is the theme's `colors.accent`, and its popup's
background is `popup.background`. So the theme applies to every option you haven't set in your
[copy of a widget](./Widgets). A value set in your copy overrides the theme.

## Blur

With `backdrop: true` in `config.yaml`, the bar and its popups blur what's behind them, which needs Windows 11. The blur
only shows through a background you can see through, such as `Qt.alpha(colors.background, 0.85)` for 85% opaque. If you
turn on blur in the setup, it writes `yasb.qml` with backgrounds like that. Otherwise it uses plain `colors.background`.

## Share a theme

A theme can be an [addon](./Addons) that others install with one command. It goes in its own folder in `themes`, and
`config.yaml` names it by its id, such as `theme: amnweb.nord`.
