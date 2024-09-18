# Wallpapers Widget Options
| Option               | Type     | Default        | Description                                                                 |
|----------------------|----------|----------------|-----------------------------------------------------------------------------|
| `label`           | string   | `"{icon}"`     | The format string for the wallpaper widget label. You can use placeholders like `{icon}` to dynamically insert icon information. |
| `update_interval`  | integer  | 60        | The interval in seconds to update the wallpaper. Must be between 60 and 86400. |
| `change_automatically` | boolean | `False`       | Whether to automatically change the wallpaper. |
| `image_path`      | string   | `""`        | The path to the folder containing images for the wallpaper. This field is required. |

## Example Configuration

```yaml
wallpapers:
  type: "yasb.wallpapers.WallpapersWidget"
  options:
    label: "{icon}"
    image_path: "C:\\Users\\{Username}\\Images" # Example path to folder with images
    change_automatically: false # Automatically change wallpaper
    update_interval: 60 # If change_automatically is true, update interval in seconds
```

## Description of Options
- **label:** The format string for the wallpaper widget label. You can use placeholders like `{icon}` to dynamically insert icon information.
- **update_interval:** The interval in seconds to update the wallpaper. Must be between 60 and 86400.
- **change_automatically:** Whether to automatically change the wallpaper.
- **image_path:** The path to the folder containing images for the wallpaper. This field is required.