# Cava Widget Configuration

> NOTE: This widget requires the `cava` version >= 0.10.4 to be installed on your system. You can install it using winget `winget install karlstav.cava` or from the [official repository](https://github.com/karlstav/cava/releases). Cava need to be accessible in the system path. YASB will create temporary configuration files for cava in the `%LOCALAPPDATA%\Yasb` directory.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `bar_height` | integer | 20 | The height of bars in pixels |
| `min_bar_height` | integer | 0 | The minimum height of bars in pixels |
| `bars_number` | integer | 10 | The number of bars (0-512). 0 sets it to auto |
| `output_bit_format` | string | "16bit" | Binary bit format, can be '8bit' (0-255) or '16bit' (0-65530) |
| `bar_spacing` | integer | 1 | Space between bars |
| `bar_width` | integer | 3 | Bars' width in number of characters |
| `sleep_timer` | integer | 0 | Seconds with no input before cava goes to sleep mode. 0 to disable |
| `sensitivity` | integer | 100 | Manual sensitivity in %. 200 means double height |
| `lower_cutoff_freq` | integer | 50 | Lower cutoff frequencies for lowest bars |
| `higher_cutoff_freq` | integer | 10000 | Higher cutoff frequencies for highest bars |
| `framerate` | integer | 60 | Accepts only non-negative values |
| `noise_reduction` | float | 0.77 | Noise reduction, 0-100. Higher = smoother but slower, lower = faster but noisier |
| `channels` | string | "stereo" | Visual channels. Can be 'stereo' or 'mono' |
| `mono_option` | string | "average" | Set mono to take input from 'left', 'right' or 'average' |
| `reverse` | integer | 0 | Set to 1 to display frequencies the other way around |
| `waveform` | integer | 0 | Show waveform instead of frequency spectrum, 1 = on, 0 = off |
| `monstercat` | integer | 0 | Disables or enables the so-called "Monstercat smoothing" with or without "waves". Set to 0 to disable. |
| `waves` | integer | 0 | Related to monstercat, 1 = on, 0 = off |
| `foreground` | string | "#ffffff" | Foreground color in hex format |
| `gradient` | integer | 1 | Gradient mode, 1 = on, 0 = off |
| `gradient_color_1` | string | "#74c7ec" | First gradient color in hex format |
| `gradient_color_2` | string | "#89b4fa" | Second gradient color in hex format |
| `gradient_color_3` | string | "#cba6f7" | Third gradient color in hex format |
| `hide_empty` | boolean | false | Hide widget when no audio is playing (requires `sleep_timer` to be enabled) |
| `container_padding` | object | {top: 0, left: 0, bottom: 0, right: 0} | Padding of the widget container |
| `callbacks`         | dict    | `{'on_left': 'do_nothing', 'on_middle': 'do_nothing', 'on_right': 'reload_cava'}` | Callbacks for mouse events on the widget. |

## Example Configuration

```yaml
  cava:
    type: "yasb.cava.CavaWidget"
    options:
      bar_height: 12
      min_bar_height: 0
      gradient: 1
      reverse: 0
      foreground: "#89b4fa"
      gradient_color_1: '#74c7ec'
      gradient_color_2: '#89b4fa'
      gradient_color_3: '#cba6f7'
      bars_number: 8
      bar_spacing: 2
      bar_width: 4
      hide_empty: true
      container_padding:
        top: 0
        left: 8
        bottom: 0
        right: 8
```

## Description of Options

- **bar_height**: The height of bars in pixels.
- **min_bar_height**: The minimum height of bars in pixels.
- **bars_number**: The number of bars to display. Can be between 0 and 512. 0 sets it to auto.
- **output_bit_format**: Binary bit format, can be '8bit' (0-255) or '16bit' (0-65530).
- **bar_spacing**: Space between bars in number of characters.
- **bar_width**: Bars' width in number of characters.
- **sleep_timer**: Seconds with no input before cava goes to sleep mode. 0 to disable.
- **sensitivity**: Manual sensitivity in %. 200 means double height.
- **lower_cutoff_freq**: Lower cutoff frequencies for lowest bars.
- **higher_cutoff_freq**: Higher cutoff frequencies for highest bars.
- **framerate**: Accepts only non-negative values.
- **noise_reduction**: Noise reduction, 0-100. Higher = smoother but slower, lower = faster but noisier.
- **channels**: Visual channels. Can be 'stereo' or 'mono'.
- **mono_option**: Set mono to take input from 'left', 'right' or 'average'.
- **reverse**: Set to 1 to display frequencies the other way around.
- **waveform**: Show waveform instead of frequency spectrum, 1 = on, 0 = off.
- **monstercat**: Disables or enables the so-called "Monstercat smoothing" with or without "waves". Set to 0 to disable.
- **waves**: Related to monstercat, 1 = on, 0 = off.
- **foreground**: Foreground color in hex format.
- **gradient**: Gradient mode, 1 = on, 0 = off.
- **gradient_color_1**: First gradient color in hex format.
- **gradient_color_2**: Second gradient color in hex format.
- **gradient_color_3**: Third gradient color in hex format.
- **hide_empty**: Hide widget when no audio is playing (requires `sleep_timer` to be enabled).
- **container_padding**: Explicitly set padding inside widget container.
- **callbacks**: A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, and `on_right`, and the values are the names of the callback functions.

More information on this option is documented in the [example config file](https://github.com/karlstav/cava/blob/master/example_files/config)

## Style
```css
.cava-widget {
    padding: 0;
    margin: 0;
}
.cava-widget .widget-container {}
```