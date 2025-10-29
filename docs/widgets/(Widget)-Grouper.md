# Grouper Widget

| Option              | Type    | Default                                                   | Description                                                           |
|---------------------|---------|-----------------------------------------------------------|-----------------------------------------------------------------------|
| `class_name`        | string  | `'grouper'`                                               | The name identifier for the grouper widget instance.                 |
| `widgets`           | list    | `[]`                                                      | List of widget names to group together inside this container.        |
| `container_shadow`  | dict    | `None`                                                    | Container shadow options.                                             |
| `hide_empty`        | boolean | `False`                                                   | If true, the grouper widget will be hidden if all its child widgets are hidden. |
| `collapse_options`  | dict    | See below                                                 | Options for collapsible grouper functionality.                        |

### Collapse Options

| Option              | Type    | Default   | Description                                                           |
|---------------------|---------|-----------|-----------------------------------------------------------------------|
| `enabled`           | boolean | `True`    | Enable/disable collapse functionality.                                |
| `exclude_widgets`   | list    | `[]`      | List of widget names (from `widgets`) to exclude from collapsing. These widgets remain visible when collapsed. |
| `expanded_label`    | string  | `"\uf054"`| Icon/label shown when grouper is expande. |
| `collapsed_label`   | string  | `"\uf053"`| Icon/label shown when grouper is collapsed. |
| `label_position`    | string  | `"right"` | Position of collapse button: `"left"` or `"right"`.                   |

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

systeminfo-grouper:
  type: "yasb.grouper.GrouperWidget"
  options:
    class_name: "systeminfo-grouper"
    widgets: [
      "memory",
      "disk",
      "battery"
    ]
    collapse_options:
      enabled: true
      exclude_widgets: ["battery"]  # Battery widget stays visible when collapsed
      expanded_label: "\uf054"
      collapsed_label: "\uf053"
      label_position: "right"

glazewm-grouper:
  type: "yasb.grouper.GrouperWidget"
  options:
    class_name: "glazewm-grouper"
    widgets: [
      "glazewm_workspaces",
      "glazewm_binding_mode",
      "active_window"
    ]
    collapse_options:
      enabled: false  # Disable collapse functionality
```

## Note on usage

In the widgets config, only add the grouper widget, not the widgets that are defined in the grouper widget. The widgets defined in the grouper widget will be displayed inside the grouper widget container. If you add them separately as well, they will be displayed twice.

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
- **container_shadow:** Container shadow options for visual depth effect.
- **hide_empty:** If set to true, the grouper widget will automatically hide itself if all its child widgets are hidden.
- **collapse_options:** Configuration for collapsible grouper behavior:
  - **enabled:** When true, adds a collapse button to show/hide grouped widgets.
  - **exclude_widgets:** List of widget names (matching names in `widgets` list) that should remain visible even when collapsed. Useful for keeping important widgets always visible.
  - **expanded_label:** Icon or text displayed on the collapse button when the grouper is expanded.
  - **collapsed_label:** Icon or text displayed on the collapse button when the grouper is collapsed.
  - **label_position:** Where to place the collapse button relative to the grouped widgets (`"left"` or `"right"`).

## Style

```css
.grouper .container {} /* Style for the container holding grouped widgets */
.grouper .grouper-button {} /* Style for the collapse/expand button */
```

## Example CSS

```css
.systeminfo-grouper .container { /* The name of the css class is the name given in the config */
    background-color: rgba(46, 52, 64, 0.8);
    border: 1px solid rgba(255, 255, 255, 0.1);
    margin: 4 0px;
    border-radius: 12px;
}

.systeminfo-grouper .grouper-button {
    font-size: 12px;
    color: #ffffff;
    padding: 0 8px;
    background-color: transparent;
    border: none;
}

.systeminfo-grouper .grouper-button:hover {
    color: #88c0d0;
}

.glazewm-grouper .container {
    background-color: rgba(46, 52, 64, 0.8);
    border: 1px solid rgba(255, 255, 255, 0.1);
    margin: 4 0px;
    border-radius: 12px;
}
```