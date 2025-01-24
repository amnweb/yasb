# GlazeWM Tiling Direction Widget
| Option               | Type   | Default                 | Description                                     |
|----------------------|--------|-------------------------|-------------------------------------------------|
| `horizontal_label`   | string | `'\udb81\udce1'`        | The label used for horizontal tiling direction. |
| `vertical_label`     | string | `'\udb81\udce2'`        | Optional label for populated workspaces.        |
| `glazewm_server_uri` | string | `'ws://localhost:6123'` | Optional GlazeWM server uri.                    |

## Example Configuration

```yaml
glazewm_tiling_direction:
  type: "glazewm.tiling_direction.GlazewmTilingDirectionWidget"
  options:
    horizontal_label: "\udb81\udce1"
    vertical_label: "\udb81\udce2"
```

## Description of Options
- **horizontal_label:** Label used for horizontal tiling direction.
- **vertical_label:** Label for vertical tiling direction.
- **glazewm_server_uri:** Optional GlazeWM server uri if it ever changes on GlazeWM side.

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
