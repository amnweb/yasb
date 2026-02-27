# Image/Gif Widget Configuration

| Option                  | Type    | Default                                      | Description                                                                 |
|-------------------------|---------|----------------------------------------------|-----------------------------------------------------------------------------|
| `label`                 | string  | ``                                     | The primary label format.                                                   |
| `label_alt`             | string  | `{file_path}` | The alternative label format.  
| `update_interval`       | integer | `5000`                                       | The interval in milliseconds to update the widget.                          |
| `file_path`       | string | ``                                       | Path to file. Can be : png, jpg, gif, webp                        |
| `speed`| integer | `100`                                      | Playback speed (percentage)                |
| `height`| integer | `24`                                      | Height of the image/gif inside the bar. Can act differently if **KeepAspectRatio** is **True** or **False**                |
| `width`      | integer    | `24` | Width of the image/gif inside the bar. Can act differently if **KeepAspectRatio** is **True** or **False**                                       |
| `keep_aspect_ratio`     | boolean    | `True` | Keep aspect ratio of current image/gif 
| `callbacks`             | dict    | `{on_left: 'toggle_label', on_middle: 'pause_gif', on_right: 'do_nothing'}` | Callback functions for different mouse button actions.                      |
| `animation`         | dict    | `{'enabled': True, 'type': 'fadeInOut', 'duration': 200}`               | Animation settings for the widget.                                          |
| `container_shadow`   | dict   | `None`                  | Container shadow options.                       |
| `label_shadow`         | dict   | `None`                  | Label shadow options.                 |

## Example Configuration
```yaml
gif:
    type: "yasb.image.ImageWidget"
    options:
      label: ""
      label_alt: "{file_path}"
      file_path: "C:\\Users\\stant\\Desktop\\your_file.gif"
      update_interval: 5000
      callbacks:
        on_left: "toggle_label"
        on_middle: "pause_gif"
        on_right: "do_nothing"
      speed: 100
      height: 24
      width: 24
      keep_aspect_ratio: True
```

## Description of Options

- **label**: The primary label format for the widget. You can use placeholders like `{file_path}`, `{speed}` or `{file_name}` here.
- **label_alt**: The alternative label format for the widget.
- **update_interval**: The interval in milliseconds to update the widget.
- **file_path**: A string that contain the path to the file. It can be : **png, jpg, gif, webp**
- **speed**: Playback speed. Only useful if current file is a gif or a webp. 100 = normal speed, 50 = half speed, 200 = x2 speed
- **height**: Height of the image/gif inside the bar. Can act differently if **KeepAspectRatio** is **True** or **False**
- **width**: Width of the image/gif inside the bar. Can act differently if **KeepAspectRatio** is **True** or **False**
- **keep_aspect_ratio**: A boolean indicating whether to keep current file aspect ratio when displayed.
- **callbacks**: A dictionary specifying the callbacks for mouse events. It contains:
    - **on_left**: The name of the callback function for left mouse button click.
    - **on_middle**: The name of the callback function for middle mouse button click.
    - **on_right**: The name of the callback function for right mouse button click.
- **animation**: A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.
- **container_shadow**: Container shadow options.
- **label_shadow**: Label shadow options.

## Example Style
```css
.image-gif-widget {}
.image-gif-widget .widget-container {}
.image-gif-widget .widget-container .label {}
.image-gif-widget .widget-container .label.alt {}
```