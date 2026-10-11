# Wallpapers Widget Options

Change your desktop wallpaper from the bar. Click the widget to open a gallery of your images, then double click one to set it.

| Option               | Type     | Default        | Description                                                                 |
|----------------------|----------|----------------|-----------------------------------------------------------------------------|
| `label`           | string   | `"{icon}"`     | The format string for the wallpaper widget label. |
| `tooltip`  | boolean  | `true`        | Whether to show the tooltip on hover. |
| `update_interval`  | integer  | 60        | The interval in seconds to update the wallpaper. Must be between 60 and 86400. |
| `change_automatically` | boolean | `false`       | Whether to automatically change the wallpaper. |
| `image_path`      | string/list   | Required    | The path(s) to the folder(s) containing images for the wallpaper. Can be a single string or a list of strings. This field is required. |
| `engine`          | object   | `{}`        | The wallpaper transition engine options. |
| `gallery`         | object   | `{}`        | The gallery options for the wallpaper widget. |
| `run_after`       | list     | `[]`        | A list of commands to run after the wallpaper is changed. |
| `keybindings`     | list     | `[]`        | Hotkeys that open the gallery without clicking the widget. |
| `callbacks`         | dict   | [See below](#callbacks) | Dictionary of callbacks to run when the widget is clicked.                 |

## Callbacks

The `callbacks` option maps mouse buttons (`on_left`, `on_middle`, `on_right`) to actions. All keys are optional, the values shown are the defaults.

```yaml
callbacks:
  on_left: "toggle_gallery"
  on_middle: "do_nothing"
  on_right: "change_wallpaper"
```

Available actions:

- `toggle_gallery` - Open or close the wallpaper gallery.
- `change_wallpaper` - Change the wallpaper to another image from `image_path`.
- `do_nothing` - Do nothing.
- `exec <command>` - Run a command, for example `exec cmd.exe /c start ms-settings:network`.

## Minimal Configuration
```yaml
wallpapers:
  type: "yasb.wallpapers.WallpapersWidget"
  options:
    label: "<span>\ue7aa</span>"
    # Example path to folder with images. Can be a single string or a list of strings.
    image_path: "C:\\Users\\{Username}\\Images" 
    gallery:
      image_width: 220
      image_corner_radius: 8
```

## Advanced Configuration
```yaml
wallpapers:
  type: "yasb.wallpapers.WallpapersWidget"
  options:
    label: "<span>\ue7aa</span>"
    # Example path to folder with images. Can be a single string or a list of strings.
    # image_path: "C:\\Users\\{Username}\\Images" 
    image_path: 
      - "C:\\Users\\{Username}\\Images"
      - "D:\\Wallpapers\\Nature"
    change_automatically: false # Automatically change wallpaper
    update_interval: 60 # If change_automatically is true, update interval in seconds
    engine:
      enabled: true
      animation: "circle" # circle/slide_top/diamond/split
    gallery:
      type: "default" # default/magnified/strip/slide - see "Gallery types" below
      image_width: 220
      orientation: "portrait" # landscape/portrait
      image_corner_radius: 12
      accent_color: "auto" # the Windows accent, or a hex such as "#89b4fa", currently used for images border
    keybindings:
      - keys: "ctrl+alt+w"
        action: "toggle_gallery"
        screen: "cursor" # active/cursor/primary
    # Note: do not use run_after: command if you don't know what it does
    run_after: # List of commands to run after wallpaper is changed
      - "wal -s -t -e -q -n -i {image}" # {image} is auto replaced with the new wallpaper path
    callbacks:
      on_left: "toggle_gallery"
      on_middle: "do_nothing"
      on_right: "change_wallpaper"
```

## Description of Options
- **label:** The format string for the wallpaper widget label.
- **update_interval:** The interval in seconds to update the wallpaper. Must be between 60 and 86400.
- **tooltip:** Whether to show the tooltip on hover.
- **change_automatically:** Whether to automatically change the wallpaper.
- **image_path:** The path(s) to the folder(s) containing images for the wallpaper. Can be a single string or a list of strings. This field is required.
- **engine:** YASB wallpaper transition engine options. Experimental and subject to change.
  - **enabled:** Whether to enable the transition engine animations when changing wallpapers.
  - **animation:** The animation style used when transitioning between wallpapers. Supported values: `circle`, `slide_top`, `diamond`, `split`. Default is `circle`.
- **gallery:** The gallery options for the wallpaper widget.
  - **type:** (default `default`) How the wallpapers are shown. `default`, `magnified`, `strip` or `slide`. See [Gallery types](#gallery-types).
  - **image_width:** The width of each thumbnail, in pixels (32-640). Default `100`.
  - **orientation:** The shape of the thumbnails, `landscape` (default) or `portrait`.
  - **image_corner_radius:** The corner radius of the thumbnails (0-50). Default `0`. (Note: This is not the same as the css border-radius property.)
  - **accent_color:** The colour of the selection border. `auto` (default) follows the Windows accent colour, or give a hex value such as `"#89b4fa"`. `slide` ignores this.
- **run_after:** A list of commands to run after the wallpaper is changed. `{image}` is replaced with the path of the new wallpaper.
- **keybindings:** Hotkeys that open the gallery. Each entry takes `keys`, `action` (`toggle_gallery`) and `screen`. `screen` can be `active` (default), `cursor` or `primary`.
- **callbacks:** Mouse event callbacks. See [Callbacks](#callbacks).


## Transition engine

The engine draws its animation into the window Windows uses to paint the desktop wallpaper. That window only exists while Windows animations are turned on.

If you turn off **Settings > Accessibility > Visual effects > Animation effects**, Windows stops creating that window. The engine has nothing to draw into, so it skips the animation and the wallpaper changes instantly. The same setting also removes the short fade Windows plays when the wallpaper changes. You cannot keep one and lose the other, they both come from the same place.

### Known issues

**Flashing on large images.** The engine runs its animation first, then sets the wallpaper. Windows tears down the engine window as part of applying it, and then plays its own fade from the old image to the new one. With a large image that fade lands after the engine window is already gone, so you see a flash of the old wallpaper before the new one settles.

It shows up around 4K and above, and not on every change. Smaller images are applied fast enough that the engine window is usually still covering the screen. There is no fix for it right now, it is how Windows applies the wallpaper. Turning off `engine.enabled`, or turning off Windows animation effects, both avoid it.

**Animation not working** Animation is not working if you have **Settings > Accessibility > Visual effects > Animation effects** turned off.

## Gallery types

The gallery opens as a single row across the middle of the screen. Your desktop stays visible around it. Set `gallery.type`:

| Type | Looks like |
|------|------------|
| `default` | Thumbnails at a fixed size, with a border on the selected one. |
| `magnified` | A tight row. The selected thumbnail grows and pushes its neighbours aside. |
| `strip` | Thumbnails tile edge to edge with leaning edges. The selected one stays bright, the rest are darkened. |
| `slide` | Upright thumbnails that shrink and fade towards the edges. |

```yaml
wallpapers:
  type: "yasb.wallpapers.WallpapersWidget"
  options:
    image_path: "C:\\Users\\amnw\\Pictures\\Wallpapers"
    gallery:
      type: "strip"
      image_width: 220
      orientation: "portrait"
      image_corner_radius: 8
      accent_color: "auto"
```

### Controls

| Input | Action |
|-------|--------|
| Left / Right | Move the selection |
| Page Up / Page Down | Select the last thumbnail visible on the left / right |
| Home / End | First / last wallpaper |
| Enter | Set the selected wallpaper |
| Escape | Close |
| Mouse wheel | Move the selection |
| Double click | Set the wallpaper under the cursor |
| Right click | Menu to set the wallpaper on one screen or all screens |

Single clicking does nothing, so double click and right click always act on the wallpaper you pointed at.

The row slides rather than paging, so Page Up and Page Down do not replace everything on screen. They move the selection to the thumbnail at the far edge of the row, which is about 6 wallpapers on a 1920px screen with `image_width: 220`, and more on a wider screen or with smaller thumbnails.

Clicking outside the gallery closes it.

The gallery opens on the wallpaper currently set on the screen it opens on, so with a different wallpaper per screen, each screen starts on its own. Wallpapers are listed by name, in the same order as File Explorer.

Thumbnails are cached in `%LOCALAPPDATA%\YASB\wallpaper_thumbnails`, so reopening the gallery does not decode every image again. The cache is kept under 100 MB, and thumbnails older than 30 days are removed. It is safe to delete the folder at any time.


## Example Style
```css
.wallpapers-widget {
    padding: 0 6px 0 6px;
}
.wallpapers-widget .widget-container {}
.wallpapers-widget .widget-container .label {}
.wallpapers-widget .widget-container .icon {
    font-size: 16px;
    font-weight: 400;
    font-family: "Segoe Fluent Icons"
}
```

The gallery is not styled with CSS. Use `image_width`, `image_corner_radius` and `accent_color` instead.

If your stylesheet has `.wallpapers-gallery-window`, `.wallpapers-gallery-image` or `.wallpapers-gallery-buttons`, they no longer do anything and can be removed.

## Using Pywal with Wallpapers
You can use [pywal](https://github.com/eylles/pywal16) to change the colors of `YASB` by generating them from your wallpaper. You can also switch wallpapers directly with pywal.

### Installation
1. Install [ImageMagick](https://imagemagick.org/) either through their website or winget if you want to use the default `wal` backend:
```powershell
winget install ImageMagick.ImageMagick
```
2. Install [pywal](https://github.com/eylles/pywal16) via pip
```powershell
pip install pywal16
```
After this, you should be ready to use Pywal.

### Usage
Run `wal` and point it to either a directory `wal -i "path/to/dir"` or an image `wal -i "/path/to/img.jpg"` and that's all. `wal` will change your wallpaper for you.

- For more information, please visit pywal's [getting started page](https://github.com/eylles/pywal16/wiki/Getting-Started)

wal stores the color schemes in `C:\Users\YOURUSERNAME\.cache\wal\` and your wal templates must be stored in `C:\Users\YOURUSERNAME\.config\wal\templates\`

- Check the official documentation for creating a template file [here](https://github.com/eylles/pywal16/wiki/User-Template-Files)

### Using the colors in YASB
wal generates `colors.css` in `C:\Users\YOURUSERNAME\.cache\wal\`. Import it at the top of your `styles.css` and use the colors as CSS variables:

```css
@import "../../.cache/wal/colors.css";

.yasb-bar {
    background-color: var(--background);
}
* {
    color: var(--foreground);
}
.widget {
    background-color: var(--color1);
}
```

The path is relative to the folder that contains `styles.css` (by default `C:\Users\YOURUSERNAME\.config\yasb\`), so `../../.cache/wal/colors.css` points to `.cache\wal\colors.css` in your user folder. An absolute path works too.

wal's default `colors.css` defines `--background`, `--foreground`, `--cursor` and `--color0` to `--color15`. Open the generated file to see the exact variable names, they differ if you use your own template.

When `watch_stylesheet` is enabled (the default), YASB also watches imported files. When `wal` writes a new `colors.css` the bar reloads its styles automatically, no restart is needed.

### Backends

`pywal` supports several color backends from which you can choose from:

- [colorz](https://github.com/metakirby5/colorz)

`pip install colorz`
- [colorthief](https://github.com/fengsp/color-thief-py)

`pip install colorthief`
- [haishoku](https://github.com/LanceGin/haishoku)

`pip install haishoku`
- [schemer2](https://github.com/thefryscorer/schemer2) (requires [Go](https://golang.org/doc/install))

`go install github.com/thefryscorer/schemer2@latest`

You can then use the `--backend [backend]` flag to use a specific backend.
