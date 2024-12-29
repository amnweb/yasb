# Applications Widget Options
| Option     | Type   | Default | Description                                                                 |
|------------|--------|---------|-----------------------------------------------------------------------------|
| `label`   | string | {data}    | The label for the applications widget.                                      |
| `class_name` | string | `""` | The CSS class name for styling the widget. Optional.                        |
|  `image_icon_size` | int | `14` | The size of the icon in pixels if the icon is an image.                      |
| `app_list`  | list   | `[]`| Application list with command. |
| `container_padding`  | dict | `{'top': 0, 'left': 0, 'bottom': 0, 'right': 0}`      | Explicitly set padding inside widget container.

## Example Configuration

```yaml
apps:
  type: "yasb.applications.ApplicationsWidget"
  options:
    label: "{data}"
    app_list:
      - {icon: "\uf0a2", launch: "notification_center"}
      - {icon: "\ueb51", launch: "quick_settings"}
      - {icon: "\uf422", launch: "search"}
      - {icon: "\uf489", launch: "wt"}
      - {icon: "C:\\Users\\marko\\icons\\vscode.png", launch: "C:\\Users\\Username\\AppData\\Local\\Programs\\Microsoft VS Code\\Code.exe"}
    container_padding: 
      top: 0
      left: 8
      bottom: 0
      right: 8
```

## Description of Options
- **label:** The label for the applications widget.
- **class_name:** The CSS class name for styling the widget. Optional.
- **image_icon_size:** The size of the icon in pixels if the icon is an image.
- **app_list:** A list of applications to display. Each application should be a dictionary with [`icon`] and [`launch`] keys. As launch you can call `quick_settings`, `notification_center`, `search`, `widget`, `launcher (launcher will trigger ALT+SPACE)`.
- **container_padding:** Explicitly set padding inside widget container.

> [!NOTE]  
> If you use image as icon, you need to provide the full path to the image. Recommended to use small images.

## Example Style
```css
.apps-widget {}
.apps-widget .widget-container {}
.apps-widget .widget-container .label { /*icons*/ } 
```