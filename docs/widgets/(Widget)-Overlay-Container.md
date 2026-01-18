# Overlay Container Widget Options

| Option          | Type    | Default                                                                 | Description                                                                 |
|-----------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `target`         | string  | `"full"`                | Target area for overlay: `"full"` (entire bar), `"left"`, `"center"`, `"right"` (bar sections), `"widget"` (specific widget), or `"custom"` (custom position) |
| `target_widget` | string  | `""`                | Name of specific widget to overlay (when `target: "widget"`) |
| `position` | string  | `"behind"`                | Z-order position: `"behind"` or `"above"` |
| `offset_x` | integer  | `0`                | Horizontal offset in pixels |
| `offset_y` | integer  | `0`                | Vertical offset in pixels |
| `width` | string/integer  | `"auto"`                | Width: `"auto"` (match target) or pixel value |
| `height` | string/integer  | `"auto"`                | Height: `"auto"` (match target) or pixel value |
| `opacity` | float  | `0.5`                | Overlay opacity (0.0-1.0) |
| `pass_through_clicks` | boolean  | `true`                | Allow mouse clicks to pass through overlay |
| `z_index` | integer  | `-1`                | Z-index: `-1` (behind), `0` (same level), `1` (front) |
| `child_widget_name` | string  | `""`                | Name of widget to display in overlay (optional if using background) |
| `show_toggle` | boolean  | `false`                | Show toggle button in bar |
| `toggle_label` | string  | `"\uf06e"`                | Toggle button icon/text |
| `auto_show` | boolean  | `true`                | Show overlay automatically on startup |
| `callbacks` | dict  | `{'on_left': 'toggle_overlay', 'on_middle': 'do_nothing', 'on_right': 'do_nothing'}`                | Callbacks for mouse events |
| `container_padding` | dict  | `{'top': 0, 'left': 0, 'bottom': 0, 'right': 0}`                | Padding for toggle container |
| `container_shadow` | dict  | See below                | Shadow effect for toggle container |
| `label_shadow` | dict  | See below                | Shadow effect for toggle label |
| `background_media` | dict  | See below                | Background media (image/GIF/video) options |
| `background_shader` | dict  | See below                | Background shader (GPU-accelerated) options |

## Shadow Options
| Option               | Type    | Default    | Description                                                  |
|----------------------|---------|------------|--------------------------------------------------------------|
| `enabled`            | bool    | `false`    | Enable shadow effect                                         |
| `color`              | string  | `"#000000"`| Shadow color (hex or named color)                            |
| `offset`             | list    | `[0, 0]`   | Shadow offset `[x, y]` in pixels                             |
| `radius`             | int     | `0`        | Shadow blur radius in pixels                                 |

## Background Media Options
| Option               | Type    | Default    | Description                                                  |
|----------------------|---------|------------|--------------------------------------------------------------|
| `enabled`            | bool    | `false`    | Enable background media                                      |
| `file`               | string  | `""`       | Full path to media file                                      |
| `type`               | string  | `"auto"`   | Media type: `"auto"`, `"image"`, `"animated"`, `"video"`     |
| `fit`                | string  | `"cover"`  | Fit mode: `"fill"`, `"contain"`, `"cover"`, `"stretch"`, `"center"`, `"tile"`, `"scale-down"` |
| `opacity`            | float   | `1.0`      | Media opacity (0.0-1.0)                                      |
| `loop`               | bool    | `true`     | Loop animated media/video                                    |
| `muted`              | bool    | `true`     | Mute video audio                                             |
| `playback_rate`      | float   | `1.0`      | Playback speed (0.1-5.0)                                     |
| `volume`             | float   | `1.0`      | Video volume (0.0-1.0)                                       |
| `offset_x`           | int     | `0`        | Widget position offset - moves entire media widget horizontally |
| `offset_y`           | int     | `0`        | Widget position offset - moves entire media widget vertically |
| `alignment`          | string  | `"center"` | Coarse positioning: `"top-left"`, `"top-center"`, `"top-right"`, `"center-left"`, `"center"`, `"center-right"`, `"bottom-left"`, `"bottom-center"`, `"bottom-right"` |
| `view_offset_x`      | int     | `0`        | Fine-tuning - shifts visible area horizontally (in pixels)   |
| `view_offset_y`      | int     | `0`        | Fine-tuning - shifts visible area vertically (in pixels)     |
| `css_class`          | string  | `""`       | Custom CSS class for styling (filters, borders, etc.)       |

**Supported Formats:**
- **Images**: PNG, JPG, JPEG, BMP, WEBP, SVG
- **Animated**: GIF, APNG, animated WEBP
- **Video**: MP4, AVI, MOV, WEBM, MKV, M4V, FLV

## Background Shader Options
| Option               | Type    | Default    | Description                                                  |
|----------------------|---------|------------|--------------------------------------------------------------|
| `enabled`            | bool    | `false`    | Enable GPU shader background (requires PyOpenGL)             |
| `preset`             | string  | `"plasma"` | Shader preset: `"plasma"`, `"wave"`, `"ripple"`, `"tunnel"`, `"mandelbrot"`, `"noise"`, `"gradient"`, `"custom"` |
| `custom_vertex_file` | string  | `""`       | Path to custom vertex shader (GLSL)                          |
| `custom_fragment_file`| string | `""`       | Path to custom fragment shader (GLSL)                        |
| `speed`              | float   | `1.0`      | Animation speed (0.1-10.0)                                   |
| `scale`              | float   | `1.0`      | Effect scale (0.1-10.0)                                      |
| `opacity`            | float   | `1.0`      | Shader opacity (0.0-1.0)                                     |
| `colors`             | list    | `[]`       | Custom colors for shader (hex strings)                       |

> [!NOTE]  
> Shader backgrounds require PyOpenGL: `pip install PyOpenGL`

> [!IMPORTANT]  
> Shader has priority over media - only one can be active at a time.

## Available Callbacks
- `toggle_overlay`: Toggle overlay visibility
- `do_nothing`: No action

## Example Configuration

### Basic: Cava Behind Media Widget
```yaml
bars:
  primary-bar:
    widgets:
      left: ["media", "media_overlay"]

widgets:
  media_overlay:
    type: "yasb.overlay_container.OverlayContainerWidget"
    options:
      target: "left"
      opacity: 0.3
      pass_through_clicks: true
      z_index: -1
      child_widget_name: "cava_background"
      auto_show: true

  cava_background:
    type: "yasb.cava.CavaWidget"
    options:
      bar_height: 32
      bar_type: "waves_mirrored"
      gradient: 1
      bars_number: 54
      framerate: 60
```

### Video Background with Custom Alignment
```yaml
widgets:
  video_overlay:
    type: "yasb.overlay_container.OverlayContainerWidget"
    options:
      target: "full"
      child_widget_name: ""
      opacity: 0.8
      pass_through_clicks: true
      z_index: -1
      background_media:
        enabled: true
        file: "C:/Users/YourName/Videos/background.mp4"
        type: "video"
        fit: "cover"
        opacity: 0.3
        loop: true
        muted: true
        alignment: "top-center"  # Show top part of video
        css_class: "my-video-bg"
```

### Image Background with Custom CSS
```yaml
widgets:
  image_overlay:
    type: "yasb.overlay_container.OverlayContainerWidget"
    options:
      target: "left"
      child_widget_name: "media"
      background_media:
        enabled: true
        file: "C:/Users/YourName/Pictures/background.png"
        type: "image"
        fit: "cover"
        opacity: 0.5
        alignment: "bottom-center"  # Show bottom part of tall image
        css_class: "custom-media-bg"
```

### Animated Shader Background
```yaml
widgets:
  shader_overlay:
    type: "yasb.overlay_container.OverlayContainerWidget"
    options:
      target: "full"
      child_widget_name: "cava_widget"
      opacity: 0.9
      pass_through_clicks: true
      z_index: -1
      background_shader:
        enabled: true
        preset: "plasma"
        speed: 1.5
        scale: 2.0
        opacity: 0.4
        colors: ["#00ffd2", "#f8ef02", "#ff003c"]
```

### Toggle Button with Shadows
```yaml
widgets:
  toggle_overlay:
    type: "yasb.overlay_container.OverlayContainerWidget"
    options:
      target: "left"
      child_widget_name: "cava_widget"
      show_toggle: true
      toggle_label: "\uf06e"
      auto_show: false
      container_shadow:
        enabled: true
        color: "#000000AA"
        offset: [2, 2]
        radius: 8
      label_shadow:
        enabled: true
        color: "#00ffd2"
        offset: [0, 0]
        radius: 10
```

### Target Specific Widget
```yaml
widgets:
  widget_overlay:
    type: "yasb.overlay_container.OverlayContainerWidget"
    options:
      target: "widget"
      target_widget: "media"
      child_widget_name: "cava_widget"
      opacity: 0.3
      pass_through_clicks: true
      z_index: -1
```

## Styling

The widget can be styled using CSS:

```css
/* Toggle button container */
.overlay-container-widget .toggle-container {
    background: transparent;
    padding: 0;
}

/* Toggle button */
.overlay-container-widget .toggle-button {
    color: #00ffd2;
    padding: 0px 4px;
    font-size: 14px;
}

.overlay-container-widget .toggle-button:hover {
    color: #f8ef02;
}

.overlay-container-widget .toggle-button.active {
    color: #ff003c;
}

/* Overlay panel */
.overlay-panel {
    background: transparent;
}

/* Child widget inside overlay */
.overlay-panel .cava-widget {
    background: transparent;
}

/* Background media with custom class */
.overlay-background-media.my-video-bg {
    border-radius: 8px;
    /* Add any custom styling */
}

.overlay-background-media.custom-media-bg {
    filter: blur(2px);
    /* Apply filters or transformations */
}
```

## Description of Options
- **target:** Target area for overlay. Use `"full"` for entire bar, `"left"/"center"/"right"` for bar sections, `"widget"` for specific widget, or `"custom"` for custom position.
- **target_widget:** Name of specific widget to overlay (only used when `target: "widget"`).
- **position:** Z-order position relative to bar widgets. Use `"behind"` to place overlay behind widgets or `"above"` to place it in front.
- **offset_x/offset_y:** Fine-tune overlay position with pixel offsets.
- **width/height:** Overlay dimensions. Use `"auto"` to match target size or specify pixel values.
- **opacity:** Overall overlay transparency. 0.0 is invisible, 1.0 is fully opaque. Recommended: 0.3-0.5 for backgrounds.
- **pass_through_clicks:** Critical for interactive widgets! Set to `true` when overlay covers clickable widgets to allow clicks to pass through.
- **z_index:** Fine control over stacking order. `-1` places behind widgets, `0` at same level, `1` in front.
- **child_widget_name:** Name of widget to display in overlay. Can be empty if using only background media/shader.
- **show_toggle:** Show a toggle button in the bar to show/hide the overlay.
- **toggle_label:** Icon or text for the toggle button (supports Font Awesome icons).
- **auto_show:** Automatically show overlay on startup. Set to `false` if you want manual control via toggle button.
- **callbacks:** Mouse event handlers. Default left click toggles overlay visibility.
- **container_padding:** Padding around toggle button container.
- **container_shadow:** Shadow effect for toggle button container. Useful for making button stand out.
- **label_shadow:** Shadow effect for toggle button label. Can create glow effects.
- **background_media:** Display images, GIFs, or videos as overlay background. Supports various fit modes and playback controls.
- **background_media.alignment:** Controls which part of the media is visible when it exceeds the overlay size. For example, `"top-center"` shows the top part of a tall image, while `"bottom-center"` shows the bottom part.
- **background_media.css_class:** Custom CSS class applied to the media widget for advanced styling via CSS (filters, transforms, borders, etc.).
- **background_shader:** GPU-accelerated animated backgrounds using GLSL shaders. Includes 7 presets or load custom shaders.

> [!NOTE]  
> When using Cava widget with `target: "full"`, bars_number is automatically limited to prevent lag (100 for waves_mirrored, 150 for waves).

## Available CSS Classes
```css
/* Toggle button container */
.overlay-container-widget .toggle-container { }

/* Toggle button */
.overlay-container-widget .toggle-button { }
.overlay-container-widget .toggle-button:hover { }
.overlay-container-widget .toggle-button.active { }

/* Overlay panel */
.overlay-panel { }

/* Background media (with optional custom class) */
.overlay-background-media { }
.overlay-background-media.your-custom-class { }

/* Child widget inside overlay (example with cava) */
.overlay-panel .cava-widget { }
.overlay-panel .cava-widget .widget-container { }
```

## Advanced Media Positioning

Beyond the `alignment` property for coarse positioning, you have **full control** over the visible area of media through the `view_offset_x` and `view_offset_y` properties.

### Fine Control: view_offset_x and view_offset_y

These properties allow pixel-perfect control over which part of the media is visible:

**Config:**
```yaml
background_media:
  file: "tall_image.png"
  fit: "cover"
  alignment: "top-center"  # Coarse positioning
  view_offset_x: -50       # Shift view 50px left
  view_offset_y: -100      # Shift view 100px up
```

### Workflow

1. **Use `alignment`** for initial positioning (e.g., `"top-center"`)
2. **Use `view_offset_x/y`** for precise pixel adjustments
3. **Use `css_class`** for visual styling (filters, borders, etc.)
4. **Iterate** by modifying values until desired result

### Example: Tall Image

**Scenario:** 1000px tall image, 32px bar, want to show the part at 300px from top.

**Config:**
```yaml
background_media:
  file: "tall_image.png"
  fit: "cover"
  alignment: "top-center"
  view_offset_y: -300      # Shift view 300px up
  css_class: "custom-media"
```

**CSS (optional for styling):**
```css
.overlay-background-media.custom-media {
    /* Visual filters */
    filter: blur(2px) brightness(0.8);
    
    /* Borders and shadows */
    border-radius: 8px;
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
}
```

### Difference between offset_x/y and view_offset_x/y

- **`offset_x/y`**: Moves the entire media widget (changes widget position)
- **`view_offset_x/y`**: Shifts the visible area within the media (changes which part is visible)

### Supported CSS Properties

```css
.overlay-background-media.my-class {
    /* Visual filters */
    filter: blur(3px) brightness(0.8) contrast(1.2) grayscale(30%);
    
    /* Borders and shadows */
    border-radius: 8px;
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
    
    /* Additional opacity */
    opacity: 0.8;
}
```

**Note:** Qt CSS (QSS) does not support `transform`, so use `view_offset_x/y` for precise positioning.

## Example Styling
```css
/* Toggle button container */
.overlay-container-widget .toggle-container {
    background: transparent;
    padding: 0;
}

/* Toggle button - normal state */
.overlay-container-widget .toggle-button {
    color: #00ffd2;
    padding: 0px 4px;
    font-size: 14px;
}

/* Toggle button - hover */
.overlay-container-widget .toggle-button:hover {
    color: #f8ef02;
}

/* Toggle button - active (overlay visible) */
.overlay-container-widget .toggle-button.active {
    color: #ff003c;
}

/* Overlay panel */
.overlay-panel {
    background: transparent;
}

/* Child widget inside overlay */
.overlay-panel .cava-widget {
    background: transparent;
    max-height: 32px;
}

.overlay-panel .cava-widget .widget-container {
    background: transparent;
}

/* Custom media styling */
.overlay-background-media.blurred {
    filter: blur(3px);
}

.overlay-background-media.rounded {
    border-radius: 12px;
}

.overlay-background-media.grayscale {
    filter: grayscale(100%);
}
```

## Troubleshooting

**Overlay doesn't appear:**
- Check `child_widget_name` is configured or background is enabled
- Verify `auto_show: true` or click toggle button
- Increase `opacity` to `1.0` for testing
- Check logs for errors

**Can't click underlying widgets:**
- Set `pass_through_clicks: true`
- Ensure `z_index: -1`

**Shader not working:**
- Install PyOpenGL: `pip install PyOpenGL`
- Check logs for OpenGL errors
- Verify GPU supports OpenGL 3.3+

**Video/GIF not playing:**
- Verify file path is correct and absolute
- Check file format is supported
- Ensure file is not corrupted
- Check logs for media loading errors

**Media alignment not working as expected:**
- Try different alignment values (`"top-center"`, `"bottom-center"`, etc.)
- Ensure `fit` mode is set appropriately (`"cover"` works best with alignment)
- Use `offset_x`/`offset_y` for fine-tuning after setting alignment
