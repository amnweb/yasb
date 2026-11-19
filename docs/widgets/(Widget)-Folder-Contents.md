# Folder Contents Configuration

A pinned folder on the bar. Similar to launchpad. Formatted in a dropdown list for folder contents rather than applications. 

| Option          | Type    | Default                                                                 | Description                                                                 |
|-----------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `path`         | string  | Required                                | The folder contents to display when clicked |


## Callbacks

The `callbacks` option is not implemented - left click is hard-coded.

```yaml
callbacks:
  on_left: "show_menu"
```

Available actions:

- `show_menu` - Opens popup.

## Exec Options

The `exec_options` option is not configured.

## Example Configuration to get Downloads

```yaml
folder_contents:
  type: "yasb.folder_contents.FolderContentsWidget"
  options:
    path: "C:\\Users\\JDoe\\Downloads"
```

## Description of Options

- **label**: (Required) The format string.
- **path**: The folder path to be displayed on popup. Default is `"C:\\Temp"`.

## Example Style
```css
.folder-popup {}
.folder-popup .QLabel {}
.folder-popup .QLabel:hover {}
```
