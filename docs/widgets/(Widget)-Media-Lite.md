# Media Lite Widget Options

A vertical and minimal album-style media widget. Cover art and track info on the bar, with a popup player when you need the controls.

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `class_name` | string | `""` | Extra CSS class on the widget. |
| `show_thumbnail` | boolean | `true` | Show album art on the bar. |
| `show_title` | boolean | `true` | Show the track title on the bar. Missing values use `Unknown Title`. |
| `show_artist` | boolean | `true` | Show the artist under the title when SMTC provides one; hidden otherwise (title stays vertically centered). When `scrolling_label` is on, artist joins the title on one scrolling line. |
| `scrolling_label` | boolean | `false` | Scroll the bar text on one line (CSS class `label`). With title and artist both enabled: `Title - Artist`. Scroll style is fixed in the widget. |
| `image_size` | integer | `28` | Bar thumbnail size in pixels. |
| `thumbnail_corner_radius` | integer | `6` | Corner radius for the bar thumbnail. |
| `max_label_size` | integer | `20` | Max characters for **both** title and artist on the bar. |
| `tooltip` | boolean | `true` | Show tooltips on the bar (title + artist) and popup controls. |
| `media_menu` | dict | [See below](#media-menu-options) | Popup menu options. |
| `callbacks` | dict | [See below](#available-callbacks) | Mouse callbacks. |
| `keybindings` | list | `[]` | Optional hotkeys. |

## Example Configuration

```yaml
media_lite:
  type: "yasb.media_lite.MediaWidget"
  options:
    show_thumbnail: true
    show_title: true
    show_artist: true
    scrolling_label: false
    image_size: 28
    thumbnail_corner_radius: 6
    max_label_size: 20
    tooltip: true
    callbacks:
      on_left: "toggle_media_menu"
      on_middle: "do_nothing"
      on_right: "do_nothing"
    media_menu:
      blur: true
      artwork_background: true
      artwork_blur_radius: 24
      artwork_dim: 0.55
      round_corners: true
      round_corners_type: "normal"
      border_color: "System"
      alignment: "center"
      direction: "down"
      offset_top: 6
      offset_left: 0
      image_size: 160
      thumbnail_corner_radius: 12
      icons:
        play: "\ue768"
        pause: "\ue769"
        prev_track: "\ue892"
        next_track: "\ue893"
        shuffle: "\ue8b1"
        repeat: "\ue8ee"
        repeat_one: "\ue8ed"
        volume: "\ue767"
        mute: "\ue994"
```

## Media Menu Options

```yaml
media_menu:
  blur: true                    # Acrylic blur on the popup shell
  artwork_background: true      # Blurred album art behind popup content
  artwork_blur_radius: 24       # Gaussian blur radius for artwork background
  artwork_dim: 0.55             # 0 = opaque art, 1 = fully transparent (menu bg shows)
  round_corners: true
  round_corners_type: "normal"  # "normal" or "small" (Win11 only)
  border_color: "System"        # HEX, None, or "System"
  alignment: "right"            # "left", "center", or "right"
  direction: "down"             # "up" or "down"
  offset_top: 6
  offset_left: 0
  image_size: 160               # Popup hero artwork size
  thumbnail_corner_radius: 12
  icons:
    play: "\ue768"
    pause: "\ue769"
    prev_track: "\ue892"
    next_track: "\ue893"
    shuffle: "\ue8b1"           # Toggle shuffle (greyed when unsupported)
    repeat: "\ue8ee"            # Cycle off -> all -> one; tooltip shows state
    repeat_one: "\ue8ed"        # Shown when repeat one is active
    volume: "\ue767"            # Unmuted; hover = slider, click = mute
    mute: "\ue994"              # Muted; click = unmute
```

On the **bar**, a missing artist is hidden and the title is vertically centered beside the thumb; a missing title still shows as `Unknown Title`. On the **popup**, missing values use `Unknown Title` / `Unknown Artist` so the layout stays stable. Popup labels are single-line, centered, and auto-elided (no max length options).

> [!NOTE]
> Timeline and seeking only work if the player reports position and duration through the Windows media API. A lot of browsers and some apps don't, or they send junk values, so the seek slider can sit disabled, jump around, or not move at all. YASB just shows what the system gives us - if the source app doesn't expose a usable timeline, there isn't much we can do about it.

Source is a **16px app icon** (tooltip shows the app name). The volume icon **always stays in the layout**. When no app audio session is bound it gets class `unavailable` (dim via CSS). When bound: **hover** = vertical slider, **click** = mute/unmute, **wheel** = adjust level.

## Available Callbacks

| Callback | Description |
| --- | --- |
| `toggle_media_menu` | Open / close the media popup. |
| `toggle_play_pause` | Play or pause the current session. |
| `open_media_source` | Activate the source app. |
| `do_nothing` | No-op. |

## CSS Classes

```css
.media-lite-widget {}
.media-lite-widget .widget-container {}
.media-lite-widget .thumbnail {}
.media-lite-widget .text {}
.media-lite-widget .label {}
.media-lite-widget .title {}
.media-lite-widget .artist {}

.media-lite-menu {}
.media-lite-menu .header {}
.media-lite-menu .artwork-background {}
.media-lite-menu .thumbnail {}
.media-lite-menu .controls {}
.media-lite-menu .title {}
.media-lite-menu .artist {}
.media-lite-menu .source {}
.media-lite-menu .volume-hover {}
.media-lite-menu .volume-button {}
.media-lite-menu .volume-button.muted {}
.media-lite-menu .volume-button.unavailable {}
.media-lite-menu .volume-slider-popup {}
.media-lite-menu .volume-slider {}
.media-lite-menu .volume-slider::groove {}
.media-lite-menu .volume-slider::sub-page {}
.media-lite-menu .volume-slider::add-page {}
.media-lite-menu .btn {}
.media-lite-menu .btn.play {}
.media-lite-menu .btn.prev {}
.media-lite-menu .btn.next {}
.media-lite-menu .btn.shuffle {}
.media-lite-menu .btn.repeat {}
.media-lite-menu .btn.active {}   /* shuffle and repeat e.g .btn.repeat.active */
.media-lite-menu .btn.disabled {}
.media-lite-menu .media-timeline-container {}
.media-lite-menu .playback-time {}
.media-lite-menu .playback-time.current {}
.media-lite-menu .playback-time.total {}
.media-lite-menu .progress-slider {}
.media-lite-menu .progress-slider::groove {}
.media-lite-menu .progress-slider::sub-page {}
```

## Example CSS

```css
/* Bar */
.media-lite-widget {
    padding: 0;
    margin: 0;
}
.media-lite-widget .text {
    padding: 0;
}
.media-lite-widget .label {
    font-size: 12px;
    font-family: "Segoe UI";
    padding: 0 2px;
}
.media-lite-widget .title {
    font-size: 12px;
    font-weight: 600;
    font-family: "Segoe UI";
    padding: 0 2px;
}
.media-lite-widget .artist {
    font-size: 11px;
    color: #7f849c;
    font-family: "Segoe UI";
    padding: 0 2px;
}

/* Popup */
.media-lite-menu {
    min-width: 280px;
    max-width: 280px;
    background-color: rgba(32, 32, 32, 0.6);
} 
.media-lite-menu .header {
    padding: 16px 16px 0 16px;
}
.media-lite-menu .thumbnail {
    cursor: pointer;
}
.media-lite-menu .controls {
    padding: 32px 16px 32px 16px;
}
.media-lite-menu .title {
    font-size: 15px;
    font-weight: 600;
    font-family: "Segoe UI";
}
.media-lite-menu .artist {
    font-size: 12px;
    font-weight: 600;
    color: #a6adc8;
    font-family: "Segoe UI";
    margin-top: 4px;
    margin-bottom: 16px;
}
.media-lite-menu .source {
    min-width: 16px;
    min-height: 16px;
    padding: 0;
    background-color: transparent;
    cursor: pointer;
}
.media-lite-menu .volume-button {
    font-family: "Segoe Fluent Icons";
    font-size: 16px;
    min-width: 24px;
    min-height: 24px;
    color: #cdd6f4;
}
.media-lite-menu .volume-button.muted {
    color: #a0a0a0;
}
.media-lite-menu .volume-button.unavailable {
    color: #4e525c;
}
.media-lite-menu .volume-slider-popup {
    background-color: rgb(32, 32, 32);
    border: 1px solid rgb(54, 54, 54);
    border-radius: 10px;
    padding: 12px 8px;
}
.media-lite-menu .volume-slider {
    min-height: 120px;
    max-height: 120px;
}
.media-lite-menu .volume-slider::groove {
    background: rgba(255, 255, 255, 0.1);
    width: 3px;
    border-radius: 2px;
}
.media-lite-menu .volume-slider::sub-page {
    background: rgba(255, 255, 255, 0.1);
    border-radius: 2px;
}
.media-lite-menu .volume-slider::add-page {
    background: white;
    border-radius: 2px;
}
.media-lite-menu .btn {
    font-family: "Segoe Fluent Icons";
    font-size: 14px;
    font-weight: 400;
    margin: 4px 2px;
    min-width: 40px;
    max-width: 40px;
    min-height: 40px;
    max-height: 40px;
    border-radius: 20px;
    transition: background-color 0.08s, opacity 0.08s;
    opacity: 1;
    cursor: pointer;
}
.media-lite-menu .btn:clicked,
.media-lite-menu .btn:pressed {
    opacity: 0.5;
}
.media-lite-menu .btn:hover {
    color: white;
    background-color: rgba(255, 255, 255, 0.1);
}
.media-lite-menu .btn.play {
    background-color: rgba(255, 255, 255, 0.1);
    font-size: 20px;
}
.media-lite-menu .btn.play {
    background-color:  #ffffff;
    color: #000;
}
.media-lite-menu .btn.shuffle.active,
.media-lite-menu .btn.repeat.active{
    color: #05ec4a;
} 
.media-lite-menu .btn.disabled:hover,
.media-lite-menu .btn.disabled {
    color: #999;
    background-color: rgba(0, 0, 0, 0);
    opacity: 1;
    cursor:default;
}
.media-lite-menu .playback-time {
    font-size: 11px;
    font-family: "Segoe UI";
    color: #7f849c;
}
.media-lite-menu .progress-slider {
    height: 10px;
    margin: 2px 0;
    border-radius: 3px;
}
.media-lite-menu .progress-slider::groove {
    background: rgba(255, 255, 255, 0.1);
    height: 2px;
    border-radius: 3px;
}
.media-lite-menu .progress-slider::groove:hover {
    height: 6px;
    background: rgba(255, 255, 255, 0.2);
}
.media-lite-menu .progress-slider::sub-page {
    background: white;
    border-radius: 3px;
}
```

## Preview of the Media Lite Widget
![GitHub YASB Widget](assets/c69d10a8-5a41-4b0a-8ea1-797c8c0b70c1.png)