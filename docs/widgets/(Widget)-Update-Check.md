# Update Check Widget

This widget checks for available updates using Windows Update and Winget.

> [!IMPORTANT]  
> Winget must be [installed](https://learn.microsoft.com/en-us/windows/package-manager/winget/) and configured to use this widget, otherwise it will not work. 

## Options

### Windows Update Options

| Option          | Type    | Default    | Description                                                  |
|-----------------|---------|------------|--------------------------------------------------------------|
| `enabled`       | boolean | `False`    | Enable Windows Update checking.                              |
| `label`         | string  | `'{count}'`| Format string for the widget label. `{count}` shows update count. |
| `interval`      | integer | `1440`     | Check interval in minutes (30 to 10080).                     |
| `exclude`       | list    | `[]`       | List of updates to exclude from checking.                    |

### Winget Update Options

| Option          | Type    | Default    | Description                                                  |
|-----------------|---------|------------|--------------------------------------------------------------|
| `enabled`       | boolean | `False`    | Enable Winget package update checking.                       |
| `label`         | string  | `'{count}'`| Format string for the widget label. `{count}` shows update count. |
| `interval`      | integer | `240`      | Check interval in minutes (10 to 10080).                     |
| `exclude`       | list    | `[]`       | List of packages to exclude from checking.                   |

## Example Configuration

```yaml
update_check:
  type: "yasb.update_check.UpdateCheckWidget"
  options:
    windows_update:
      enabled: True
      label: '<span>\uf0ab</span> {count}'
      interval: 60
      exclude: []
    winget_update:
      enabled: True
      label: '<span>\uf0ab</span> {count}'
      interval: 30
      exclude: []
```

## Available Styles

```css
.update-check-widget {}
.update-check-widget .widget-container {}
.update-check-widget .widget-container.winget {}
.update-check-widget .widget-container.windows {}
.update-check-widget .label {}
.update-check-widget .icon {}
```

## Example

```css
.update-check-widget {
    padding: 0 6px 0 6px;
}
.update-check-widget .icon {
    font-size: 14px;
}
.update-check-widget .widget-container.winget,
.update-check-widget .widget-container.windows {
    background: #eba0ac;
    margin: 6px 2px 6px 2px;
    border-radius: 8px;
    border: 2px solid #f38ba8;
}
.update-check-widget .widget-container.windows {
    background: #b4befe;
    margin: 6px 2px 6px 2px;
    border-radius: 8px;
    border: 2px solid #89b4fa;
}
.update-check-widget .widget-container.winget .icon,
.update-check-widget .widget-container.windows .icon {
    color: #1e1e2e;
    margin: 0 1px 0 6px;
}
.update-check-widget .widget-container.winget .label,
.update-check-widget .widget-container.windows .label {
    margin: 0 6px 0 1px;
    color: #1e1e2e;
    font-weight: 900;
    font-size: 14px;
} 
```
