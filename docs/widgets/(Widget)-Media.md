# Media Widget Options

| Option                                | Type      | Default                                                   | Description                                                        |
| -------------------------             | --------- | ---------                                                 | -------------------------------------                              |
| `label`                               | string    |                                                           | The main label format for the media widget.                        |
| `label_alt`                           | string    |                                                           | The alternative label format for the media widget.                 |
| `label_shadow`                        | boolean   | false                                                     | Whether to show a shadow effect on the label.                      |
| `max_field_size`                      | dict      |                                                           | Maximum field sizes for labels.                                    |
| `max_field_size.label`                | integer   | 20                                                        | Maximum size for the main label.                                   |
| `max_field_size.label_alt`            | integer   | 30                                                        | Maximum size for the alternative label.                            |
| `max_field_size.truncate_whole_label` | boolean   | false                                                     | Whether to truncate the whole label if it exceeds the maximum size.|
| `show_thumbnail`                      | boolean   | true                                                      | Whether to show the media thumbnail.                               |
| `controls_only`                       | boolean   | false                                                     | Whether to show only the media controls.                           |
| `controls_left`                       | boolean   | true                                                      | Whether to position the controls on the left.                      |
| `controls_hide`                       | boolean   | false                                                     | Whether to hide the media controls buttons                         |
| `hide_empty`                          | boolean   | true                                                      | Whether to hide the widget when there is no media information.     |
| `thumbnail_alpha`                     | integer   | 50                                                        | The alpha transparency value for the thumbnail.                    |
| `thumbnail_padding`                   | integer   | 8                                                         | The padding around the thumbnail.                                  |
| `thumbnail_corner_radius`             | integer   | 0                                                         | The corner radius for the thumbnail.                               |
| `symmetric_corner_radius`             | boolean   | false                                                     | Whether to use symmetric corner radius for the thumbnail.          |
| `thumbnail_edge_fade`                 | boolean   | false                                                     | Whether to apply an edge fade effect to the thumbnail.             |
| `icons`                               | dict      |                                                           | Icons for media controls.                                          |
| `icons.prev_track`                    | string    | `\uf048`                                                  | Icon for the previous track button.                                |
| `icons.next_track`                    | string    | `\uf051`                                                  | Icon for the next track button.                                    |
| `icons.play`                          | string    | `\uf04b`                                                  | Icon for the play button.                                          |
| `icons.pause`                         | string    | `\uf04c`                                                  | Icon for the pause button.                                         |
| `animation`                           | dict      | `{'enabled': True, 'type': 'fadeInOut', 'duration': 200}` | Animation settings for the widget.                                 |
| `container_padding`                   | dict      | `{'top': 0, 'left': 0, 'bottom': 0, 'right': 0}`          | Explicitly set padding inside widget container.                    |
| `container_shadow`                    | dict      | `None`                                                    | Container shadow options.                                          |
| `label_shadow`                        | dict      | `None`                                                    | Label shadow options.                                              |
| `media_menu`                          | dict      | `None`                                                    | Media menu popup.                                                  |
| `media_menu_icons`                    | dict      | `None`                                                    | Media menu icons for popup.                                        |
| `scrolling_label`                     | dict      | `None`                                                    | Widget label scrolling options                                     |

## Example Configuration

```yaml
media:
  type: "yasb.media.MediaWidget"
  options:
    label: "{title} - {artist}"
    label_alt: "{title}"
    hide_empty: true
    callbacks:
      on_left: "toggle_label"
      on_middle: "do_nothing"
      on_right: "do_nothing"
    max_field_size:
      label: 20
      label_alt: 30
    show_thumbnail: true
    controls_only: false
    controls_left: true
    controls_hide: false
    thumbnail_alpha: 80
    thumbnail_padding: 8
    thumbnail_corner_radius: 16
    scrolling_label:
      enabled: false
      update_interval_ms: 33
      style: "left"  # can be "left", "right", "bounce", "bounce-ease"
      separator: " | "
      label_padding: 1
      # Easing curve params: https://www.desmos.com/calculator/j7eamemxzi
      ease_slope: 20
      ease_pos: 0.8
      ease_min: 0.5
    icons:
      prev_track: "\ue892"
      next_track: "\ue893"
      play: "\ue768"
      pause: "\ue769"
    media_menu:
      blur: false
      round_corners: true
      round_corners_type: "normal"
      border_color: "system"
      alignment: "right"
      direction: "down"
      offset_top: 6
      offset_left: 0
      thumbnail_corner_radius: 8
      thumbnail_size: 120
      max_title_size: 80
      max_artist_size: 20
      show_source: true
    media_menu_icons:
      play: "\ue768"
      pause: "\ue769"
      prev_track: "\ue892"
      next_track: "\ue893"
    label_shadow:
      enabled: true
      color: "black"
      radius: 3
      offset: [ 1, 1 ]
```

## Available Callbacks
- `toggle_label`: Toggles the visibility of the label.
- `do_nothing`: A placeholder callback that does nothing when triggered.
- `toggle_play_pause`: Toggles between play and pause states.
- `toggle_media_menu`: Toggles the visibility of the media menu popup.


## Description of Options
- **label:** The format string for the media label. You can use placeholders like `{title}` and `{artist}` to dynamically insert media information.
- **label_alt:** The alternative format string for the media label. Useful for displaying additional media details.
- **label_shadow:** Whether to show a shadow effect on the label. This can enhance the visibility of the label against different backgrounds.
- **hide_empty:** Whether to hide the widget when there is no media information available.
- **callbacks:** A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, `on_right`. Available callbacks are `toggle_label`, `do_nothing`, and `toggle_play_pause`.
- **max_field_size:** Maximum field sizes for the labels.
  - **label:** Maximum size for the main label. If the label exceeds this size, it will be truncated.
  - **label_alt:** Maximum size for the alternative label. If the label exceeds this size, it will be truncated.
  - **truncate_whole_label:** Whether to truncate the whole label or separated `{title} {artist}` if it exceeds the maximum size. If set to false, only the part that exceeds the maximum size will be truncated.
- **show_thumbnail:** Whether to show the media thumbnail.
- **controls_only:** Whether to show only the media controls.
- **controls_left:** Whether to place the media controls on the left.
- **controls_hide:** Whether to hide the media controls buttons.
- **thumbnail_alpha:** The alpha (transparency) value for the media thumbnail.
- **thumbnail_padding:** The padding around the media thumbnail.
- **thumbnail_corner_radius:** The corner radius for the media thumbnail. Set to 0 for square corners.
- **symmetric_corner_radius:** Whether to use symmetric corner radius for the thumbnail. If set to true, the corner radius will be applied equally on all corners.
- **scrolling_label:** A dictionary specifying the scrolling label options for the widget.
  - **enabled:** Whether to enable the scrolling label.
  - **update_interval_ms:** The update interval for the scrolling label in milliseconds. Min 4 max 1000.
  - **style:** The style of the scrolling label. Can be `left`, `right`, `bounce`, or `bounce-ease`.
  - **separator:** The separator between repeating text in `left` or `rignt` scrolling style.
  - **label_padding:** The padding around the label in `bounce` and `bounce-ease` style. By default it's one character on each side.
  - **ease_slope:** The easing slope for the bounce effect. Easing curve params: https://www.desmos.com/calculator/j7eamemxzi
  - **ease_pos:** The easing curve position for the bounce effect.
  - **ease_min:** The minimum value for the bounce effect easing curve.
- **thumbnail_edge_fade:** Whether to apply an edge fade effect to the thumbnail. This can create a smoother transition between the thumbnail and the background.
- **icons:** Icons for the media controls.
- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.
- **container_padding**: Explicitly set padding inside widget container. Use this option to set padding inside the widget container. You can set padding for top, left, bottom and right sides of the widget container.
- **container_shadow:** Container shadow options.
- **label_shadow:** Label shadow options.
- **media_menu:** A dictionary specifying the media menu popup options. It contains keys for blur, round corners, border color, alignment, direction, offsets, thumbnail corner radius, thumbnail size, max title size, max artist size, and show source.
- **media_menu_icons:** Icons for the media menu popup. It contains keys for play, pause, previous track, and next track icons.


## Scrolling Label Notes
- The scrolling label uses `max_field_size` to limit its size.
- The scrolling label will disable `thumbnail_padding` option and `.media-widget .label { margin: ... }` should be used instead.

## Available Styles
```css
.media-widget {}
.media-widget .widget-container {}
.media-widget .label {}
.media-widget .label.alt {}
.media-widget .btn.play {}
.media-widget .btn.prev {}
.media-widget .btn.next {}
.media-widget .btn.disabled {}
```

## Example Style
```css
.media-widget {
    padding: 0;
    margin: 0;
}
.media-widget .label {
    color: #bac2db;
    background-color: rgba(24, 24, 37, 0.7);
    padding: 0px;
    padding-right: 4px;
    font-size: 12px;
}
.media-widget .btn {
    color: #989caa;
    padding: 0 4px;
    margin: 0;
    font-family: Segoe Fluent Icons;
    font-weight: 400;
}
.media-widget .btn:hover {
    color: #babfd3;
}
.media-widget .btn.play {
    font-size: 16px;
}
.media-widget .btn.disabled:hover,
.media-widget .btn.disabled {
    color: #4e525c;
    font-size: 12px;
    background-color: rgba(0, 0, 0, 0);
}
```

## Example Popup Style
```css
.media-menu {
    min-width: 420px;
    max-width: 420px;
    background-color: rgba(31, 39, 49, 0.5);
}
.media-menu .title,
.media-menu .artist,
.media-menu .source {
    font-size: 14px;
    font-weight: 600;
    margin-left: 10px;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}
.media-menu .artist {
    font-size: 13px;
    color: #6c7086;
    margin-top: 0px;
    margin-bottom: 8px;
}
.media-menu .source {
    font-size: 11px;
    color: #000;
    font-weight: normal;
    border-radius: 3px;
    background-color: #bac2de;
    padding: 2px 4px;

}
/* The source class name is the same as what you see in the media widget; just replace spaces with dashes and convert it to lowercase. 
Example: "Windows Media" becomes "windows-media" */
.media-menu .source.firefox {
    background-color: #ff583b;
    color: #ffffff;
}
.media-menu .source.spotify {
    background-color: #199143;
    color: #ffffff;
}
.media-menu .source.edge {
    background-color: #0078d4;
    color: #ffffff;
}
.media-menu .source.windows-media {
    background-color: #0078d4;
    color: #ffffff;
}

.media-menu .btn {
    font-family: "Segoe Fluent Icons";
    font-size: 14px;
    font-weight: 400;
    margin: 10px 2px 0px 2px;
    min-width: 40px;
    max-width: 40px;
    min-height: 40px;
    max-height: 40px;
    border-radius: 20px;
}
.media-menu .btn.prev {
    margin-left: 10px;
}
.media-menu .btn:hover {
    color: white;
    background-color: rgba(255, 255, 255, 0.1);
}
.media-menu .btn.play {
    background-color: rgba(255, 255, 255, 0.1);
    font-size: 20px
}
.media-menu .btn.disabled:hover,
.media-menu .btn.disabled {
    color: #4e525c;
    background-color: rgba(0, 0, 0, 0);
}

.media-menu .playback-time {
    font-size: 13px;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    color: #7f849c;
    margin-top: 20px;
    min-width: 100px;
}
.media-menu .progress-slider {
    height: 10px;
    margin: 5px 4px;
    border-radius: 3px;
}
.media-menu .progress-slider::groove {
    background: transparent;
    height: 2px;
    border-radius: 3px;
    background: rgba(255, 255, 255, 0.1);

}
.media-menu .progress-slider::groove:hover {
    background: transparent;
    height: 6px;
    border-radius: 3px;
    background: rgba(255, 255, 255, 0.2);
}
.media-menu .progress-slider::sub-page {
    background: white;
    border-radius: 3px;
    height: 4px;
}
```

> [!NOTE] 
> The style example above uses the Segoe Fluent Icons font for buttons, you can use any other icon font or custom icons as per your design requirements.
