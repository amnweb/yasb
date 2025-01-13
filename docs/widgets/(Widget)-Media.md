# Media Widget Options

| Option                  | Type    | Default | Description                                                                 |
|-------------------------|---------|---------|-----------------------------------------------------------------------------|
| `label`                 | string  |         | The main label format for the media widget.                                 |
| `label_alt`             | string  |         | The alternative label format for the media widget.                          |
| `max_field_size`        | dict    |         | Maximum field sizes for labels.                                             |
| `max_field_size.label`  | integer | 20      | Maximum size for the main label.                                            |
| `max_field_size.label_alt` | integer | 30   | Maximum size for the alternative label.                                     |
| `show_thumbnail`        | boolean | true    | Whether to show the media thumbnail.                                        |
| `controls_only`         | boolean | false   | Whether to show only the media controls.                                    |
| `controls_left`         | boolean | true    | Whether to position the controls on the left.                               |
| `hide_empty`            | boolean | true    | Whether to hide the widget when there is no media information.              |
| `thumbnail_alpha`       | integer | 50      | The alpha transparency value for the thumbnail.                             |
| `thumbnail_padding`     | integer | 8       | The padding around the thumbnail.                                           |
| `thumbnail_corner_radius` | integer | 0     | The corner radius for the thumbnail.                                        |
| `icons`                 | dict    |         | Icons for media controls.                                                   |
| `icons.prev_track`      | string  | `\uf048`| Icon for the previous track button.                                         |
| `icons.next_track`      | string  | `\uf051`| Icon for the next track button.                                             |
| `icons.play`            | string  | `\uf04b`| Icon for the play button.                                                   |
| `icons.pause`           | string  | `\uf04c`| Icon for the pause button.                                                  |
| `animation`         | dict    | `{'enabled': True, 'type': 'fadeInOut', 'duration': 200}`               | Animation settings for the widget.                                          |
| `container_padding`  | dict | `{'top': 0, 'left': 0, 'bottom': 0, 'right': 0}`      | Explicitly set padding inside widget container. |
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
    thumbnail_alpha: 80
    thumbnail_padding: 8
    thumbnail_corner_radius: 16
    icons:
      prev_track: "\ue892"
      next_track: "\ue893"
      play: "\ue768"
      pause: "\ue769"
```

## Description of Options
- **label:** The format string for the media label. You can use placeholders like `{title}` and `{artist}` to dynamically insert media information.
- **label_alt:** The alternative format string for the media label. Useful for displaying additional media details.
- **hide_empty:** Whether to hide the widget when there is no media information available.
- **callbacks:** A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, `on_right`.
- **max_field_size:** Maximum field sizes for the labels.
- **show_thumbnail:** Whether to show the media thumbnail.
- **controls_only:** Whether to show only the media controls.
- **controls_left:** Whether to place the media controls on the left.
- **thumbnail_alpha:** The alpha (transparency) value for the media thumbnail.
- **thumbnail_padding:** The padding around the media thumbnail.
- **thumbnail_corner_radius:** The corner radius for the media thumbnail. Set to 0 for square corners.
- **icons:** Icons for the media controls.
- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.
- **container_padding**: Explicitly set padding inside widget container. Use this option to set padding inside the widget container. You can set padding for top, left, bottom and right sides of the widget container.

## Example Style
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