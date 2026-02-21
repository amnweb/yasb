# Update Check Widget

This widget checks for available updates using Windows Update, Winget, and Scoop.

> [!IMPORTANT]  
> - [Winget](https://learn.microsoft.com/en-us/windows/package-manager/winget/) must be installed and configured for Winget update checking to work.
> - [Scoop](https://scoop.sh/) must be installed and configured for Scoop update checking to work.
> - Each source can be enabled or disabled independently.

## Options

### Windows Update Options

| Option          | Type    | Default    | Description                                                  |
|-----------------|---------|------------|--------------------------------------------------------------|
| `enabled`       | boolean | `false`    | Enable Windows Update checking.                              |
| `label`         | string  | `'{count}'`| Format string for the widget label. `{count}` shows update count. |
| `tooltip`       | boolean | `true`     | Whether to show the tooltip on hover.                        |
| `interval`      | integer | `1440`     | Check interval in minutes (30 to 10080).                     |
| `exclude`       | list    | `[]`       | List of updates to exclude (matched against name).           |

### Winget Update Options

| Option          | Type    | Default    | Description                                                  |
|-----------------|---------|------------|--------------------------------------------------------------|
| `enabled`       | boolean | `false`    | Enable Winget package update checking.                       |
| `label`         | string  | `'{count}'`| Format string for the widget label. `{count}` shows update count. |
| `tooltip`       | boolean | `true`     | Whether to show the tooltip on hover.                        |
| `interval`      | integer | `240`      | Check interval in minutes (10 to 10080).                     |
| `exclude`       | list    | `[]`       | List of packages to exclude (matched against name and id).   |

### Scoop Update Options

| Option          | Type    | Default    | Description                                                  |
|-----------------|---------|------------|--------------------------------------------------------------|
| `enabled`       | boolean | `false`    | Enable Scoop package update checking.                        |
| `label`         | string  | `'{count}'`| Format string for the widget label. `{count}` shows update count. |
| `tooltip`       | boolean | `true`     | Whether to show the tooltip on hover.                        |
| `interval`      | integer | `240`      | Check interval in minutes (10 to 10080).                     |
| `exclude`       | list    | `[]`       | List of packages to exclude (matched against name).          |

## Widget Shadow Options
| Option          | Type    | Default    | Description                                                  |
|-----------------|---------|------------|--------------------------------------------------------------|
| `container_shadow`   | dict   | `None`                  | Container shadow options.                       |
| `label_shadow`         | dict   | `None`                  | Label shadow options.                 |


## Click Handlers
- **Left-click** on Winget container: opens a terminal to upgrade all detected Winget packages.
- **Left-click** on Scoop container: opens a terminal to upgrade all detected Scoop packages.
- **Left-click** on Windows Update container: opens Windows Update settings.
- **Right-click** on any container: forces a re-check for that source.

## Example Configuration

```yaml
update_check:
  type: "yasb.update_check.UpdateCheckWidget"
  options:
    windows_update:
      enabled: true
      label: "<span>\uf0ab</span> {count}"
      interval: 1440
      exclude: []
    winget_update:
      enabled: true
      label: "<span>\uf0ab</span> {count}"
      interval: 240
      exclude: ["Microsoft.Edge"]
    scoop_update:
      enabled: true
      label: "<span>\uf0ab</span> {count}"
      interval: 240
      exclude: []
    label_shadow:
      enabled: true
      color: "black"
      radius: 3
      offset: [ 1, 1 ]
```

## Available Styles

```css
.update-check-widget {}
.update-check-widget .widget-container {}
.update-check-widget .widget-container.winget {}
.update-check-widget .widget-container.scoop {}
.update-check-widget .widget-container.windows {}
.update-check-widget .widget-container.paired-left {}
.update-check-widget .widget-container.paired-right {}
.update-check-widget .label {}
.update-check-widget .icon {}
```

### State Classes

When two or more source containers are visible, each container gets positional classes based on its neighbors:

- `paired-left` - has a visible container to the left
- `paired-right` - has a visible container to the right

This allows you to add margin only on the side that faces another container, keeping outer edges untouched.

| Visible Sources | winget | scoop | windows |
|---|---|---|---|
| all 3 | `paired-right` | `paired-left paired-right` | `paired-left` |
| winget + windows | `paired-right` | - | `paired-left` |
| winget + scoop | `paired-right` | `paired-left` | - |
| scoop + windows | - | `paired-right` | `paired-left` |
| 1 only | (none) | (none) | (none) |

Example:

```css
.update-check-widget .widget-container.paired-left {
    margin-left: 4px;
}
.update-check-widget .widget-container.paired-right {
    margin-right: 4px;
}
```

## Example

```css
.update-check-widget {
    padding: 0 4px;
}
.update-check-widget .icon {
    font-size: 14px;
}
.update-check-widget .widget-container.winget,
.update-check-widget .widget-container.scoop,
.update-check-widget .widget-container.windows {
    background: #6549e6;
    margin: 6px 2px;
    border-radius: 4px;
    border: 1px solid #8267ff;
}
 
.update-check-widget .widget-container.paired-left {
    margin-left: 2px;
}
.update-check-widget .widget-container.paired-right {
    margin-right: 2px;
}
.update-check-widget .widget-container.windows {
    background: #3353e4;
    border: 1px solid #5574fc;
}
.update-check-widget .widget-container.scoop {
    background: #2b9e78;
    border: 1px solid #4ac59c;
}
.update-check-widget .widget-container.winget .icon,
.update-check-widget .widget-container.scoop .icon,
.update-check-widget .widget-container.windows .icon {
    color: #ffffff;
    margin: 0 1px 0 6px;
}
.update-check-widget .widget-container.winget .label,
.update-check-widget .widget-container.scoop .label,
.update-check-widget .widget-container.windows .label {
    margin: 0 6px 0 1px;
    color: #ffffff;
    font-weight: 600;
    font-size: 14px;
} 
```
