# Grouper Widget

| Option              | Type    | Default                                                   | Description                                                           |
|---------------------|---------|-----------------------------------------------------------|-----------------------------------------------------------------------|
| `class_name`              | string  | `'grouper'`                                               | The name identifier for the grouper widget instance.                 |
| `widgets`           | list    | `[]`                                                      | List of widget names to group together inside this container.        |
| `container_padding` | dict    | `{'top': 0, 'left': 0, 'bottom': 0, 'right': 0}`        | Explicitly set padding inside widget container.                      |
| `container_shadow`  | dict    | `None`                                                    | Container shadow options.                                             |

## Example Configuration

```yaml
systeminfo-grouper:
  type: "yasb.grouper.GrouperWidget"
  options:
    class_name: "systeminfo-grouper"
    widgets: [
      "memory",
      "disk",
      "battery"
    ]

glazewm-grouper:
  type: "yasb.grouper.GrouperWidget"
  options:
    class_name: "glazewm-grouper"
    widgets: [
      "glazewm_workspaces",
      "glazewm_binding_mode",
      "active_window"
    ]
```

## Note on usage

In the widgets config only add the grouper widget, not the widgets that are defined in the grouper widget. The widgets defined in the grouper widget will be displayed inside the grouper widget container. If you add them seperatly as well they will be displayed twice.

```yaml
widgets:
  left: [
      "glazewm-grouper",
  ]
  center: [
      "clock",
    ]
  right: [
      "systeminfo-grouper", # don't add the widgets here that are defined in the grouper widget, example: "memory", "disk", "battery" don't need to be added here
      "github",
      "weather",
      "power_menu",
  ]
```

## Description of Options

- **class_name:** A unique identifier for the grouper widget instance. This is used for CSS styling.
- **widgets:** A list of widget names that should be grouped together inside this container. The widgets are referenced by their configuration names defined elsewhere in the config file. The widgets will be displayed horizontally in the order specified.
- **container_padding:** Explicitly set padding inside widget container.
- **container_shadow:** Container shadow options.

## Style

```css
.grouper .container {} /* Style for the container holding grouped widgets */
```

## Example CSS

```css
.systeminfo-grouper .container { /* The name of the css class is the name given in the config */
    background-color: rgba(46, 52, 64, 0.8);
    border: 1px solid rgba(255, 255, 255, 0.1);
    margin: 4 0px;
    border-radius: 12px;
}

.glazewm-grouper .container {
    background-color: rgba(46, 52, 64, 0.8);
    border: 1px solid rgba(255, 255, 255, 0.1);
    margin: 4 0px;
    border-radius: 12px;
}
```