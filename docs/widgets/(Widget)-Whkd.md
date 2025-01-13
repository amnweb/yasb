# WHKD Widget Options

Whkd is a simple hotkey daemon for Windows that reacts to input events by executing commands. More information can be found [here](https://github.com/LGUG2Z/whkd).

| Option           | Type     | Default                        | Description                                                                 |
|------------------|----------|--------------------------------|-----------------------------------------------------------------------------|
| `label`          | string   | `"\uf11c"`                       | The string for the label button.  |
| `container_padding`  | dict | `{'top': 0, 'left': 0, 'bottom': 0, 'right': 0}`      | Explicitly set padding inside widget container.      |
| `animation`         | dict    | `{'enabled': True, 'type': 'fadeInOut', 'duration': 200}`               | Animation settings for the widget.                                          |


## Example Configuration

```yaml
whkd:
  type: "yasb.whkd.WhkdWidget"
  options:
    label: "<span>\uf11c</span>"
```
## Description of Options

- **label:** The string for the label button.
- **container_padding:** Explicitly set padding inside widget container.
- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.

## Example Style
```css
.whkd-widget {}
.whkd-widget .windget-container {}
.whkd-widget .label {}
.whkd-widget .icon {}
```