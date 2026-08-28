# Wallpapers Widget Options

Change your desktop wallpaper from the bar. Click the widget to open a gallery of your images, then double click one to set it.

| Option               | Type     | Default        | Description                                                                 |
|----------------------|----------|----------------|-----------------------------------------------------------------------------|
| `label`           | string   | `"{icon}"`     | The format string for the wallpaper widget label. |
| `tooltip`  | boolean  | `true`        | Whether to show the tooltip on hover. |
| `update_interval`  | integer  | 60        | The interval in seconds to update the wallpaper. Must be between 60 and 86400. |
| `change_automatically` | boolean | `false`       | Whether to automatically change the wallpaper. |
| `image_path`      | string/list   | `""`        | The path(s) to the folder(s) containing images for the wallpaper. Can be a single string or a list of strings. This field is required. |
| `engine`          | object   | `{}`        | The wallpaper transition engine options. |
| `gallery`         | object   | `{}`        | The gallery options for the wallpaper widget. |
| `run_after`       | list     | `[]`        | A list of commands to run after the wallpaper is changed. |
| `keybindings`     | list     | `[]`        | Hotkeys that open the gallery without clicking the widget. |
| `callbacks`         | dict   | `{'on_left': 'toggle_gallery', 'on_middle': 'do_nothing', 'on_right': 'change_wallpaper'}`                  | Dictionary of callbacks to run when the widget is clicked.                 |

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
      - "wal -s -t -e -q -n -i {image}" # {image} is replaced with the new wallpaper path
      - "cmd.exe /c start /min pwsh ./yasb.ps1"
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
  - **type:** How the wallpapers are shown. `default`, `magnified`, `strip` or `slide`. See [Gallery types](#gallery-types).
  - **image_width:** The width of each thumbnail, in pixels.
  - **orientation:** The shape of the thumbnails, `landscape` or `portrait`.
  - **image_corner_radius:** The corner radius of the thumbnails. (Note: This is not the same as the css border-radius property.)
  - **accent_color:** The colour of the selection border. `auto` (default) follows the Windows accent colour, or give a hex value such as `"#89b4fa"`. `slide` ignores this.
- **run_after:** A list of commands to run after the wallpaper is changed. `{image}` is replaced with the path of the new wallpaper.
- **keybindings:** Hotkeys that open the gallery. Each entry takes `keys`, `action` (`toggle_gallery`) and `screen`. `screen` can be `active` (default), `cursor` or `primary`.
- **callbacks:** A dictionary of callbacks to run when the widget is clicked. The keys are `on_left`, `on_middle`, and `on_right`. The values are the names of the callbacks to run. Default callbacks are `toggle_gallery`, `do_nothing`, and `change_wallpaper`.


## Transition engine

The engine draws its animation into the window Windows uses to paint the desktop wallpaper. That window only exists while Windows animations are turned on.

If you turn off **Settings > Accessibility > Visual effects > Animation effects**, Windows stops creating that window. The engine has nothing to draw into, so it skips the animation and the wallpaper changes instantly. The same setting also removes the short fade Windows plays when the wallpaper changes. You cannot keep one and lose the other, they both come from the same place.

### Known issues

**Flashing on large images.** The engine runs its animation first, then sets the wallpaper. Windows tears down the engine window as part of applying it, and then plays its own fade from the old image to the new one. With a large image that fade lands after the engine window is already gone, so you see a flash of the old wallpaper before the new one settles.

It shows up around 4K and above, and not on every change. Smaller images are applied fast enough that the engine window is usually still covering the screen. There is no fix for it right now, it is how Windows applies the wallpaper. Turning off `engine.enabled`, or turning off Windows animation effects, both avoid it.


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

# Using Pywal with Wallpapers
You can use [pywal](https://github.com/eylles/pywal16) to change the colors of `YASB` by generating them from your wallpaper. You can also switch wallpapers directly with pywal.

## Installation
1. Install [ImageMagick](https://imagemagick.org/) either through their website or winget if you want to use the default `wal` backend:
```powershell
winget install ImageMagick.ImageMagick
```
2. Install [pywal](https://github.com/eylles/pywal16) via pip
```powershell
pip install pywal16
```
After this, you should be ready to use Pywal.

## Usage
Run `wal` and point it to either a directory `wal -i "path/to/dir"` or an image `wal -i "/path/to/img.jpg"` and that's all. `wal` will change your wallpaper for you.

- For more information, please visit pywal's [getting started page](https://github.com/eylles/pywal16/wiki/Getting-Started)

wal stores the color schemes in `C:\Users\YOURUSERNAME\.cache\wal\` and your wal templates must be stored in `C:\Users\YOURUSERNAME\.config\wal\templates\`

- Check the official documentation for creating a template file [here](https://github.com/eylles/pywal16/wiki/User-Template-Files)

For usage in `YASB` there are several methods you can try:

1. Using a Powershell script to append the colors generated on top of `style.css`

```powershell
# Load the generated colors from wal, typically located at $HOME\.cache\wal\colors.json
$colorsPath = "$HOME\.cache\wal\colors.json"
# Convert the JSON colors to a PowerShell object
$colors = Get-Content -Raw -Path $colorsPath | ConvertFrom-Json
# Generate the @variables{} section
$variablesSection = @"
:root{
    --backgroundcol: $($colors.special.background);
    --foregroundcol: $($colors.special.foreground);
    --cursorcol: $($colors.special.cursor);
    --colors0: $($colors.colors.color0);
    --colors1: $($colors.colors.color1);
    --colors2: $($colors.colors.color2);
    --colors3: $($colors.colors.color3);
    --colors4: $($colors.colors.color4);
    --colors5: $($colors.colors.color5);
    --colors6: $($colors.colors.color6);
    --colors7: $($colors.colors.color7);
    --colors8: $($colors.colors.color8);
    --colors9: $($colors.colors.color9);
    --colors10: $($colors.colors.color10);
    --colors11: $($colors.colors.color11);
    --colors12: $($colors.colors.color12);
    --colors13: $($colors.colors.color13);
    --colors14: $($colors.colors.color14);
    --colors15: $($colors.colors.color15);
}
"@
# Read the existing styles.css file, typically located at $HOME\.config\yasb\styles.css
$stylesPath = "$HOME\.config\yasb\styles.css"
$stylesContent = Get-Content -Raw -Path $stylesPath
# Check if :root{} section exists, if so replace it, otherwise prepend it
if ($stylesContent -match ":root\{[\s\S]*?\}") {
    # Replace the existing :root{} section
    $newStylesContent = $stylesContent -replace ":root\{[\s\S]*?\}", $variablesSection
} else {
    # Prepend the new :root{} section
    $newStylesContent = "$variablesSection`n$stylesContent"
}
# Trim trailing whitespace from the content
$newStylesContent = $newStylesContent.TrimEnd()
# Write the updated content back to styles.css
$newStylesContent | Set-Content -Path $stylesPath   
```

2. Using the `@import` function in `style.css` to import colors generated from pywal. **REQUIRES RESTART OF YASB EVERY TIME COLOR IS CHANGED!**

```css
/* Colors for YASB */
:root{

    /* Special */
    --backgroundcol: #0d0c13;
    --foregroundcol: #c2c2c4;
    --cursorcol: #c2c2c4;

    /* Colors */
    --colors0: #0d0c13;
    --colors1: #544e7f;
    --colors2: #69567f;
    --colors3: #7c607c;
    --colors4: #80516e;
    --colors5: #834457;
    --colors6: #937d82;
    --colors7: #908d97;
    --colors8: #59596c;
    --colors9: #7069aa;
    --colors10: #8c73aa;
    --colors11: #a680a6;
    --colors12: #ab6c93;
    --colors13: #af5b75;
    --colors14: #c5a7ae;
    --colors15: #c2c2c4;
}
```

 Which you can then import and use the colors as variables like this:
 ```css
@import url('../../.cache/wal/colors.css');
* {
    color: var(--foregroundcol);
    font-weight: 500;
}
```

3. Making the entire style.css a template:

```css
* {{
    font-size: 12px;
    color: {foreground};
    font-weight: 500;
    font-family: "Cascadia Mono";
    margin: 0;
    padding: 0;
}}
.yasb-bar {{
    padding: 0;
    margin: 0;
}}
.widget {{
    background-color: {color1};
    padding: 0 8px;
    margin: 0;
}}
.widget .label {{
    padding: 1px 2px 1px 2px;
}}
.widget .label.alt {{
    padding: 1px 8px 1px 8px;
}}
.active-window-widget {{
    border-radius: 18px;
    margin-left: 8px
}}
.container-left,
.container-center,
.container-right {{
    margin: 0;
    padding: 0;
}}

.clock-widget {{
    border-top-left-radius: 18px;
    border-bottom-left-radius: 18px;
}}


.komorebi-active-layout {{
    border-top-right-radius: 18px;
    border-bottom-right-radius: 18px;
    padding: 0 4px 0 0;
}}

.komorebi-active-layout .label {{
    font-weight: 600;
    padding: 2px 0 0 0;
}}
.wifi-widget {{
    padding: 0 4px 0 4px;
    border-top-left-radius: 18px;
    border-bottom-left-radius: 18px;
}}

.apps-widget .widget-container,
.komorebi-workspaces .widget-container,
.wifi-widget .widget-container,
.komorebi-active-layout .widget-container {{
    background-color: {color9};
    margin: 4px 0px 4px 0;
    border-radius: 14px;
}}
.apps-widget {{
    padding: 0 4px 0 2px;
    border-top-right-radius: 18px;
    border-bottom-right-radius: 18px;
}}
.komorebi-workspaces .ws-btn {{
    font-size: 16px;
    background-color: transparent;
    margin: 0 4px 0 4px;
    color: {color14};
    border: none;
}}
.komorebi-workspaces .ws-btn.populated {{
    color: #a0c3ee;
}}
.komorebi-workspaces .ws-btn:hover,
.komorebi-workspaces .ws-btn.populated:hover,
.komorebi-workspaces .ws-btn.active {{
    color: #c2daf7;
}}

.apps-widget .label {{
    font-size: 14px;
    padding: 0 2px;
}}
.apps-widget .label:hover {{
    color: #fff;
}}

/*POWER MENU WIDGET*/
.uptime {{
    font-size: 14px;
    margin-bottom: 10px;
    color: #ffffff;
    font-weight: 600;
    font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
}}
.power-menu-widget .label {{
    color: #f38ba8;
    font-size: 13px;
}}
.power-menu-popup {{
    background-color: rgba(24, 24, 37, 0.9);
    border-radius: 12px;
    border: 4px solid rgb(41, 42, 58);
}}
.power-menu-popup .button {{
    padding: 0;
    width: 240px;
    height: 120px;
    border-radius: 8px;
    background-color: rgb(41, 42, 58);
    font-family: "SegoeUI";
    color: white;
    border: 1px solid rgba(255, 255, 255, 0.1);
    margin: 8px;
}}
.power-menu-popup .button.hover {{
    background-color: rgb(55, 56, 75);
    border: 1px solid rgb(55, 56, 75);
}}
.power-menu-popup .button .label {{
    margin-bottom: 8px;
    font-size: 16px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.95);
    font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
}}
.power-menu-popup .button .icon {{
    font-size: 48px;
    padding-top: 8px;
    color: rgba(255, 255, 255, 0.25);
}}
.power-menu-popup .button.cancel .icon {{
    color: rgba(243, 139, 168, 0.55);
}}
.power-menu-popup .button.cancel .label {{
    color: rgba(243, 139, 168, 0.95);
}}
.power-menu-popup .button.shutdown .icon {{
    color: rgba(137, 180, 250, 0.55);
}}
.power-menu-popup .button.shutdown .label {{
    color: rgba(137, 180, 250, 0.95);
}}

/* ICONS */
.icon {{
    font-size: 16px;
}}
.volume-widget .icon {{
    color: #89b4fa;
    margin: 1px 2px 0 0;
}}
.cpu-widget .icon,
.memory-widget .icon {{
    font-size: 14px;
    color: #cba6f7;
    margin: 0 2px 1px 0;
}}
.memory-widget .icon {{
    color: #a6c9f7;
}}
.wifi-widget .icon {{
    color: #43d8d8;
    padding: 0 7px;
    margin: 0;
}}

/* WEATHER WIDGET */
.weather-widget .icon {{
    font-size: 16px;
    margin: 0 2px 1px 0;
}}
.weather-widget .icon.sunnyDay {{
    color: rgb(221, 210, 107);
}}
.weather-widget .icon.clearNight {{
    color: rgb(107, 189, 221);
    font-size: 22px;
    margin: 1px 2px 0px 0;
}}

/* MEDIA WIDGET */
.media-widget {{
    padding: 0;
    padding-left: 6px;
    margin: 0;
    border-radius: 18px;
    margin-right: 8px;
}}
.media-widget .label {{
    background-color: rgba(0, 0, 0, 0.0);
}}
.media-widget .btn {{
    color: #acb2c9;
    padding: 0;
    font-size: 18px;
}}
.media-widget .btn:hover {{
    color: #89b4fa;
}}
.media-widget .btn.play {{
    font-size: 24px;
}}
.media-widget .btn.prev {{
    padding: 0 4px 0 4px;
}}
.media-widget .btn.next {{
    padding: 0 4px 0 4px;
}}
.media-widget .btn.disabled:hover,
.media-widget .btn.disabled {{
    color: #4e525c;
}}

/* GITHUB WIDGET */
.github-widget {{
    padding: 0 4px;
}}
.github-widget .icon {{
    font-size: 14px;
    color: #cdd6f4
}}
.github-widget .icon.new-notification {{
    color: #f38ba8;
}}
/* TASBAR WIDGET */
.taskbar-widget {{
    padding: 0;
    margin: 0;
}}
.taskbar-widget .app-icon {{
    padding: 0 6px;
}}
```

This solution requires that you copy/paste the file generated in `.cache/wal/` to `.config/yasb/`. Another thing to note is that if you want to change something in your style.css you have to make a template again.

## Backends

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
