# Applications Widget Options

| Option     | Type   | Default | Description                                                                 |
|------------|--------|---------|-----------------------------------------------------------------------------|
| `label`   | string | {data}    | The label for the applications widget.                                      |
| `class_name` | string | `""` | The CSS class name for styling the widget. Optional.                        |
|  `image_icon_size` | int | `14` | The size of the icon in pixels if the icon is an image.                      |
| `app_list`  | list   | `[]`| Application list with command. |
| `tooltip`  | bool   | `True`| Enable or disable tooltips for application names. |
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
      - {icon: "\uf0a2", launch: "notification_center", name: "Notification Center"} # launch notification center
      - {icon: "\ueb51", launch: "quick_settings"} # launch quick settings
      - {icon: "\uf422", launch: "search"} # launch search
      - {icon: "\uf489", launch: "wt", name: "Windows Terminal"} # launch terminal
      - {icon: "C:\\Users\\marko\\icons\\vscode.png", launch: "C:\\Users\\Username\\AppData\\Local\\Programs\\Microsoft VS Code\\Code.exe"} # open vscode
      - {icon: "\udb81\udc4d",launch: "\"C:\\Program Files\\Mozilla Firefox\\firefox.exe\" -new-tab www.reddit.com"} # open reddit in new tab in firefox
      - {icon: "\udb81\udc4d",launch: "\"C:\\Program Files\\Mozilla Firefox\\firefox.exe\" -new-window www.reddit.com"} # open reddit in new window in firefox
      - {icon: "\udb81\udc4d",launch: "\"C:\\Program Files\\Mozilla Firefox\\firefox.exe\" -private-window www.reddit.com"} # open reddit in private window in firefox
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
- **app_list:** A list of applications to display in the widget. Each application can be specified as a string (the command to launch) or as a dictionary with the following keys:
  - **icon:** The icon for the application. This can be a Unicode character (e.g., `\uf0a2`), an image path (e.g., `C:\\path\\to\\icon.png`), or an icon name that can be resolved by the system.
  - **launch:** The command to launch the application. This can include arguments and should be properly quoted if necessary.
  - **name:** (Optional) The name of the application to display as a tooltip when hovering over the icon.
- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.
- **tooltip:** A boolean to enable or disable tooltips for application names.
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