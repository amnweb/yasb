# Language Widget Options
| Option           | Type     | Default                        | Description                                                                 |
|------------------|----------|--------------------------------|-----------------------------------------------------------------------------|
| `label`          | string   | `"{lang[language_code]}-{lang[country_code]}"`              | The format string for the label. |
| `label_alt`      | string   | `"{lang[full_name]}"`               | The alternative format string for the label. Useful for displaying the full language name. |
| `update_interval`| integer  | `5`                            | The interval in seconds to update the language information. Must be between 1 and 3600. |
| `callbacks`      | dict     | `{ 'on_left': 'toggle_label', 'on_middle': 'do_nothing', 'on_right': 'do_nothing' }` | The dictionary of callback functions for different mouse actions. |
| `animation`         | dict    | `{'enabled': True, 'type': 'fadeInOut', 'duration': 200}`               | Animation settings for the widget.                                          |
| `container_padding`  | dict | `{'top': 0, 'left': 0, 'bottom': 0, 'right': 0}`      | Explicitly set padding inside widget container.                            |
## Example Configuration

```yaml
language:
  type: "yasb.language.LanguageWidget"
  options:
    label: "{lang[language_code]}-{lang[country_code]}"
    label_alt: "{lang[full_name]}"
    update_interval: 5
    callbacks:
      on_left: "toggle_label"
      on_middle: "do_nothing"
      on_right: "do_nothing"
```

## Description of Options
- **label:** The format string for the label. You can use placeholders like `{lang[language_code]}`, `{lang[country_code]}`, `{lang[full_name]}`, `{lang[native_country_name]}`, `{lang[native_lang_name]}`, `{lang[layout_name]}`, `{lang[full_layout_name]}`, `{lang[layout_country_name]}`.
- **label_alt:** The alternative format string for the label. Useful for displaying the full language name.
- **update_interval:** The interval in seconds to update the language information. Must be between 1 and 3600.
- **callbacks:** A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, and `on_right`, and the values are the names of the callback functions.
- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.
- **container_padding**: Explicitly set padding inside widget container. Use this option to set padding inside the widget container. You can set padding for top, left, bottom and right sides of the widget container.

## Example Style
```css
.language-widget {}
.language-widget .widget-container {}
.language-widget .label {}
.language-widget .label.alt {}
.language-widget .icon {}
```