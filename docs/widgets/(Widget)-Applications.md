# Applications Widget Options

| Option     | Type   | Default | Description                                                                 |
|------------|--------|---------|-----------------------------------------------------------------------------|
| `label`   | string | {data}    | The label for the applications widget.                                      |
| `class_name` | string | `""` | The CSS class name for styling the widget. Optional.                        |
|  `image_icon_size` | int | `14` | The size of the icon in pixels if the icon is an image.                      |
| `app_list`  | list   | `[]`| Application list with command. |
| `container_padding`  | dict | `{'top': 0, 'left': 0, 'bottom': 0, 'right': 0}`      | Explicitly set padding inside widget container. |
| `animation`         | dict    | `{'enabled': True, 'type': 'fadeInOut', 'duration': 200}`               | Animation settings for the widget.                                          |
| `container_shadow`   | dict   | `None`                  | Container shadow options.                       |
| `label_shadow`         | dict   | `None`                  | Label shadow options.                 |

## Example Configuration

```yaml
apps:
  type: "yasb.applications.ApplicationsWidget"
  options:
    label: "{data}"
    app_list:
      - {icon: "\uf0a2", launch: "notification_center"} # launch notification center
      - {icon: "\ueb51", launch: "quick_settings"} # launch quick settings
      - {icon: "\uf422", launch: "search"} # launch search
      - {icon: "\uf489", launch: "wt"} # launch terminal
      - {icon: "C:\\Users\\marko\\icons\\vscode.png", launch: "C:\\Users\\Username\\AppData\\Local\\Programs\\Microsoft VS Code\\Code.exe"} # open vscode
      - {icon: "\udb81\udc4d",launch: "\"C:\\Program Files\\Mozilla Firefox\\firefox.exe\" -new-tab www.reddit.com"} # open reddit in new tab in firefox
      - {icon: "\udb81\udc4d",launch: "\"C:\\Program Files\\Mozilla Firefox\\firefox.exe\" -new-window www.reddit.com"} # open reddit in new window in firefox
      - {icon: "\udb81\udc4d",launch: "\"C:\\Program Files\\Mozilla Firefox\\firefox.exe\" -private-window www.reddit.com"} # open reddit in private window in firefox
    container_padding: 
      top: 0
      left: 8
      bottom: 0
      right: 8
    label_shadow:
      enabled: true
      color: "black"
      radius: 3
      offset: [ 1, 1 ]
```

## Description of Options
- **label:** The label for the applications widget.
- **class_name:** The CSS class name for styling the widget. Optional.
- **image_icon_size:** The size of the icon in pixels if the icon is an image.
- **app_list:** A list of applications to display. Each application should be a dictionary with [`icon`] and [`launch`] keys. As launch you can call `quick_settings`, `notification_center`, `search`, `widget`, `launcher (launcher will trigger ALT+SPACE)`.
- **container_padding**: Explicitly set padding inside widget container. Use this option to set padding inside the widget container. You can set padding for top, left, bottom and right sides of the widget container.
- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.
- **container_shadow:** Container shadow options.
- **label_shadow:** Label shadow options.

> [!NOTE]  
> If you use image as icon, you need to provide the full path to the image. Recommended to use small images.

## Example Style
```css
.apps-widget {}
.apps-widget .widget-container {}
.apps-widget .widget-container .label { /*icons*/ } 
```