# Configuration

`config.yaml` in your [config folder](./Getting-Started#your-config-folder) holds YASB's settings and your bars: the
screens each bar is on, its edge, size and place, the layout and theme it uses, and its widgets. This page covers every
key. A widget's content and look are set in the widget's own file (see [Widgets](./Widgets)).

## An example

```yaml
watch: true
debug: false
update_check: true
theme: yasb
bars:
  yasb-bar:
    layout: floating
    screens:
      - "*"
    edge: top
    thickness: 40
    margin:
      top: 6
      left: 6
      right: 6
    reserve_space: true
    backdrop: true
    widgets:
      left:
        - ActiveWindow
      center:
        - Clock
      right:
        - Cpu
        - Memory
        - Volume
```

YASB validates the whole file when it reads it. Unknown keys and invalid values are errors, and YASB shows an alert
listing each one. If the file has errors at startup, YASB doesn't start. If you save a file with errors while YASB is
running, it keeps the previous config.

## Settings

| Key | Value | Default | What it does |
| --- | --- | --- | --- |
| `watch` | `true` or `false` | `true` | Applies your changes when you save `config.yaml`, a widget, or the layout or theme it names. See [how YASB picks up your changes](./Getting-Started#how-yasb-picks-up-your-changes). |
| `debug` | `true` or `false` | `false` | Writes more detail to `yasb.log`. |
| `update_check` | `true` or `false` | `true` | Shows a notification when a new version of YASB is out. |
| `theme` | a theme | YASB's own theme | The theme of every bar that doesn't name its own. See [Themes](./Themes). |
| `bars` | bars by name | one bar, `yasb-bar`, with no widgets | Your bars. You choose the names. |

## Bars

Each bar under `bars` takes these keys. Leave one out and it keeps its default.

| Key | Value | Default | What it does |
| --- | --- | --- | --- |
| `enabled` | `true` or `false` | `true` | `false` keeps the bar in the file but doesn't show it. |
| `layout` | a layout | YASB's own bar | The bar's look. See [Layouts](./Layouts). |
| `theme` | a theme | the `theme` above | The colors and fonts of this bar and its widgets. See [Themes](./Themes). |
| `screens` | a list of screens | `["*"]` | The screens that get this bar. See [Screens](#screens). |
| `edge` | `top`, `bottom`, `left` or `right` | `top` | The screen edge the bar sits on. |
| `align` | `left`, `center` or `right`. On a `left` or `right` edge: `top`, `center` or `bottom`. | `center` | Where a bar shorter than its edge sits along it. |
| `length` | pixels, a percentage such as `"50%"`, or `"auto"` | `"100%"` | How long the bar is along its edge. A percentage is of the whole edge. `"auto"` makes it as long as its widgets, except on an [IslandBar](./(Type)-IslandBar) layout, which always runs the whole edge. It's never longer than the edge minus the margins. |
| `thickness` | pixels | `40` | How tall the bar is, or how wide on a `left` or `right` edge. |
| `margin` | `top`, `left`, `bottom` and `right`, in pixels | `0` each | The gap between the bar and the screen's edges. |
| `reserve_space` | `true` or `false` | `false` | Maximized windows stop at the bar instead of covering it. The reserved space is the bar's `thickness` plus its margins on both sides. It has no effect while the bar auto-hides. |
| `always_on_top` | `true` or `false` | `false` | The bar stays above other windows. |
| `hide_on_fullscreen` | `true` or `false` | `false` | The bar hides while a game or video fills the screen. It needs `always_on_top: true`. |
| `auto_hide` | `never`, `always` or `maximized` | `never` | `always`: the bar slides away until the pointer touches its screen edge. `maximized`: the bar slides away while a window is maximized on its screen, unless `reserve_space` is `true`. |
| `backdrop` | `true` or `false` | `false` | Blurs what's behind the bar. It needs Windows 11, and a bar color you can see through, as YASB's theme has. |
| `animation` | `type` and `duration` | `type: slide`, `duration: 200` | How the bar shows and hides: `type` is `slide`, `fade` or `none`, and `duration` is in milliseconds. |
| `widgets` | widgets by slot | none | The widgets in the bar. See [Widgets in a bar](#widgets-in-a-bar). |

### Layouts and themes

`layout` and `theme` take a name, which YASB looks for in your `layouts` or `themes` folder:

- A name such as `floating` is `layouts\floating.qml`.
- An addon's id such as `amnweb.nord` is the addon's own folder, `themes\amnweb.nord`.
- A path that ends in `.qml`, such as `my\bar.qml`, is that file, relative to your config folder.
- `default` is YASB's own bar or theme, the same as leaving the key out.

A bar whose layout or theme is missing or has an error gets YASB's own, and YASB shows an alert that says why.

## Screens

`screens` lists the screens that get the bar:

- `"*"`: every screen that no other bar names.
- `"**"`: every screen, even one another bar names.
- `primary`: your main screen.
- A screen's name, as `yasbc monitor-information` shows it after `Name:`.

`"*"` and `"**"` only work as the list's only entry. Listed with other screens, they're treated as a screen name, which
matches no screen, so they're skipped. `primary` and screen names can be listed together.

A bar has one window on each of its screens. A named screen that isn't connected is skipped, and `yasb.log` says so.
When you connect or disconnect a screen, YASB restarts and places the bars again. This puts one bar on the main screen
and a smaller one on every other screen:

```yaml
bars:
  main:
    screens:
      - primary
    widgets:
      right:
        - Clock
  others:
    screens:
      - "*"
    thickness: 32
    widgets:
      center:
        - Clock
```

## Widgets in a bar

`widgets` maps each slot of the bar to its widgets, in the order they show. The layout decides the slots. YASB's layouts
have `left`, `center` and `right` on a bar at the top or bottom, and `top`, `center` and `bottom` on a bar at the left
or right. A layout can add slots of its own, as [Layouts](./Layouts) shows. A slot's name starts with a letter and has
only letters, digits, `-` and `_`. Widgets in a slot the layout doesn't have aren't shown, and `yasb.log` notes it.

A widget's name is one of:

- YASB's own widget, such as `Clock`. [Widgets](./Widgets) lists them all.
- A widget of your own, in `widgets\Name\Name.qml` in your config folder.
- A widget addon, by its id, such as `amnweb.clock`. See [Addons](./Addons).

Names are case-insensitive. When YASB can't find a widget, it shows an alert that names it and leaves it out.

## Environment variables

`$env:NAME` anywhere in a value becomes the value of the environment variable `NAME`, or nothing when it isn't
set. YASB reads the variables from Windows and from the `.env` file in your config folder:

```yaml
bars:
  yasb-bar:
    screens:
      - $env:YASB_SCREEN
```
