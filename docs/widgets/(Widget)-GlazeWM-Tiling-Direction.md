# GlazeWM Tiling Direction Widget
| Option               | Type   | Default                 | Description                                     |
|----------------------|--------|-------------------------|-------------------------------------------------|
| `horizontal_label`   | string | `'\udb81\udce1'`        | The label used for horizontal tiling direction. |
| `vertical_label`     | string | `'\udb81\udce2'`        | Optional label for populated workspaces.        |
| `glazewm_server_uri` | string | `'ws://localhost:6123'` | Optional GlazeWM server uri.                    |
| `container_shadow`   | dict   | `None`                  | Container shadow options.                       |
| `btn_shadow`         | dict   | `None`                  | Workspace button shadow options                 |

## Example Configuration

```yaml
glazewm_tiling_direction:
  type: "glazewm.tiling_direction.GlazewmTilingDirectionWidget"
  options:
    horizontal_label: "\udb81\udce1"
    vertical_label: "\udb81\udce2"
    btn_shadow:
      enabled: true
      color: "black"
      radius: 3
      offset: [ 1, 1 ]
```

## Description of Options
- **horizontal_label:** Label used for horizontal tiling direction.
- **vertical_label:** Label for vertical tiling direction.
- **glazewm_server_uri:** Optional GlazeWM server uri if it ever changes on GlazeWM side.
- **container_shadow:** Container shadow options.
- **btn_shadow:** Workspace button shadow options.

## Note on Shadows
`container_shadow` is applied to the container if it's not transparent.
If it is transparent, container shadows will be applied to the `btn` instead.
This can cause double shadows if you have `btn_shadow` already.
Apply the shadows only to the container that is actually visible.

## Style
```css
.glazewm-tiling-direction {} /*Style for widget.*/
.glazewm-tiling-direction .btn {} /*Style for tiling direction button.*/
```

## Example CSS
```css
.glazewm-tiling-direction {
    background-color: transparent;
    padding: 0;
    margin: 0;
}

.glazewm-tiling-direction .btn {
    font-size: 18px;
    width: 14px;
    padding: 0 4px 0 4px;
    color: #CDD6F4;
    border: none;
}

.glazewm-tiling-direction .btn:hover {
    background-color: #727272;
}
```
