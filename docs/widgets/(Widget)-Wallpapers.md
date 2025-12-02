# Wallpapers Widget Options
| Option               | Type     | Default        | Description                                                                 |
|----------------------|----------|----------------|-----------------------------------------------------------------------------|
| `label`           | string   | `"{icon}"`     | The format string for the wallpaper widget label. |
| `tooltip`  | boolean  | `true`        | Whether to show the tooltip on hover. |
| `update_interval`  | integer  | 60        | The interval in seconds to update the wallpaper. Must be between 60 and 86400. |
| `change_automatically` | boolean | `false`       | Whether to automatically change the wallpaper. |
| `image_path`      | string/list   | `""`        | The path(s) to the folder(s) containing images for the wallpaper. Can be a single string or a list of strings. This field is required. |
| `gallery`         | object   | `{}`        | The gallery options for the wallpaper widget. |
| `run_after`       | list     | `[]`        | A list of functions to run after the wallpaper is updated. |
| `animation`         | dict    | `{'enabled': true, 'type': 'fadeInOut', 'duration': 200}`               | Animation settings for the widget.                                          |
| `container_shadow`   | dict   | `None`                  | Container shadow options.                       |
| `label_shadow`         | dict   | `None`                  | Label shadow options.                 |
| `callbacks`         | dict   | `{'on_left': 'toggle_gallery', 'on_middle': 'do_nothing', 'on_right': 'change_wallpaper'}`                  | Dictionary of callbacks to run when the widget is clicked.                 |

## Minimal Configuration
```yaml
wallpapers:
  type: "yasb.wallpapers.WallpapersWidget"
  options:
    label: "<span>\udb83\ude09</span>"
    # Example path to folder with images. Can be a single string or a list of strings.
    image_path: "C:\\Users\\{Username}\\Images" 
    gallery:
        enabled: true
        blur: true
        image_width: 220
        image_per_page: 6
        orientation: "portrait"
        show_buttons: false
        image_spacing: 8
        lazy_load: true
        lazy_load_fadein: 400
        image_corner_radius: 12
```

## Advanced Configuration
```yaml
wallpapers:
  type: "yasb.wallpapers.WallpapersWidget"
  options:
    label: "<span>\udb83\ude09</span>"
    # Example path to folder with images. Can be a single string or a list of strings.
    # image_path: "C:\\Users\\{Username}\\Images" 
    image_path: 
      - "C:\\Users\\{Username}\\Images"
      - "D:\\Wallpapers\\Nature"
    change_automatically: false # Automatically change wallpaper
    update_interval: 60 # If change_automatically is true, update interval in seconds
    gallery:
        enabled: true
        blur: true
        image_width: 220
        image_per_page: 6
        gallery_columns: 0 # 0 = auto, matches image_per_page for a single row
        horizontal_position: "center" # left/center/right placement on screen
        vertical_position: "center" # top/center/bottom placement
        position_offset: 0 # minimum gap (px) from screen edges - see below for advanced options
        respect_work_area: true # clamp to OS work area (avoids Windows taskbar)
        show_buttons: false
        orientation: "portrait"
        image_spacing: 8
        lazy_load: true
        lazy_load_fadein: 400
        image_corner_radius: 12
    run_after: # List of functions to run after wallpaper is updated
      - "wal -s -t -e -q -n -i {image}" # Example command to run after wallpaper is updated
      - "cmd.exe /c start /min pwsh ./yasb.ps1" # Example command to run after wallpaper is updated
    label_shadow:
      enabled: true
      color: "black"
      radius: 3
      offset: [ 1, 1 ]
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
- **gallery:** The gallery options for the wallpaper widget.
  - **enabled:** Whether to enable the gallery.
  - **blur:** Whether to blur the background when the gallery is open.
  - **image_width:** The width of the images in the gallery.
  - **image_per_page:** The number of images per page in the gallery.
    - **gallery_columns:** How many columns (images per row) the gallery grid uses. Set to `0` (the default) to auto-match `image_per_page` for a single row, or supply a value between 1 and 64 to lock the number of columns (the value is capped at `image_per_page`).
    - **horizontal_position:** Horizontal placement of the gallery window. `center` (default) keeps the existing behavior, `left` anchors the gallery to the active screen's left edge, and `right` aligns it to the right edge.
    - **vertical_position:** Vertical anchor for the gallery (`top`, `center`, or `bottom`).
    - **position_offset:** Controls margins from screen edges. Supports three formats:
      - **Single integer:** `position_offset: 20` - applies 20px margin to all edges (top, right, bottom, left)
      - **Two values:** `position_offset: [10, 20]` - applies 10px to top/bottom, 20px to left/right
      - **Four values:** `position_offset: [10, 20, 30, 40]` - applies margins in CSS order (top, right, bottom, left)
      - **Negative values:** Supported for extending beyond work area boundaries (e.g., `position_offset: [-10, 20]`)
    - **respect_work_area:** When `true`, the gallery respects Windows taskbars and other reserved OS areas (uses the screen's available/work area). If the gallery is too large to fit, it will be clipped without scrollbars. Set to `false` to allow the gallery to span the entire monitor.
  - **show_buttons:** Whether to show the navigation buttons in the gallery.
  - **orientation:** The orientation of the images in the gallery. Can be "portrait" or "landscape".
  - **image_spacing:** The spacing between images in the gallery.
  - **lazy_load:** Whether to lazy load images in the gallery.
  - **lazy_load_fadein:** The fade-in duration in milliseconds for lazy loaded images.
  - **image_corner_radius:** The corner radius of the images in the gallery. (Note: This is not same as the css border-radius property.)
- **run_after:** A list of functions to run after the wallpaper is updated.
- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.
- **container_shadow:** Container shadow options.
- **label_shadow:** Label shadow options.
- **callbacks:** A dictionary of callbacks to run when the widget is clicked. The keys are `on_left`, `on_middle`, and `on_right`. The values are the names of the callbacks to run. Default callbacks are `toggle_gallery`, `do_nothing`, and `change_wallpaper`.

> If gallery is enabled left mouse click on the widget will open the gallery and right mouse click will change the wallpaper and get random one. 

> Gallery options above fit screen for 1920x1080 resolution. You may need to adjust the values for other resolutions.

> [!NOTE]
> Wallpapers widget supports toggle visibility using the `toggle-widget wallpapers` command in the CLI. More information about the CLI commands can be found in the [CLI documentation](https://github.com/amnweb/yasb/wiki/CLI#toggle-widget-visibility).

## Example Style
```css
.wallpapers-widget {
    padding: 0 6px 0 6px;
}
.wallpapers-widget .widget-container {}
.wallpapers-gallery-window {
    background-color: rgba(85, 42, 240, 0.01);
    border: 0;
    margin: 16px
}
.wallpapers-gallery-buttons {
    background-color:rgba(255, 255, 255, 0);
    color: white;
    border: none;
    font-size: 14px;
    padding: 8px 0;
    border-radius: 8px;
    margin:0 8px 8px 8px;
    width: 200px;
}
.wallpapers-gallery-buttons:hover {
    background-color:rgba(255, 255, 255, 0.1)
}
.wallpapers-gallery-image {
    border: 4px solid transparent;
    border-radius: 16px;
}
.wallpapers-gallery-image:hover {
    border: 4px solid rgb(66, 68, 83);
}
.wallpapers-gallery-image.focused {
    border: 4px solid #89b4fa;
}
```

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