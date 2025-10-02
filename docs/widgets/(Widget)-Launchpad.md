# Launchpad Widget

The Launchpad widget provides a customizable application launcher grid, similar to macOS Launchpad. It allows you to quickly launch, add, edit, or remove applications from a visually organized popup. Launchpad supports drag-and-drop functionality, search, and context menus for managing your applications. It supports UWP apps, executables, and URLs, making it a versatile tool for accessing your favorite programs.

## Options

| Option                | Type     | Default                | Description                                                                 |
|-----------------------|----------|------------------------|-----------------------------------------------------------------------------|
| `label`               | string   | `'<span>\udb85\udcde</span>'`| The label/icon for the widget on the bar.                                   |
| `search_placeholder`  | string   | `"Search applications..."`     | Placeholder text for the search field.                                      |
| `app_icon_size`       | int      | `64`                   | Size of application icons in pixels.                                        |
| `window`              | dict     | `{fullscreen: false, width: 800, height: 600, overlay_block: true}`                | Popup window size and fullscreen options.                                   |
| `window_style`        | dict     | `{enable_blur: true, round_corners: true, round_corners_type: "normal", border_color: "system"}`                | Popup window styling (blur, corners, border, etc).                          |
| `window_animation`    | dict     | `{fade_in_duration: 400, fade_out_duration: 400}`                | Animation settings for showing/hiding the popup.                            |
| `animation`           | dict     | `{enabled: true, type: "fadeInOut", duration: 200}`                | Widget animation settings.                                                  |
| `callbacks`           | dict     | `{on_left: "toggle_launchpad", on_right: "do_nothing", on_middle: "do_nothing"}` | Mouse event callbacks.      |
| `label_shadow`        | dict     | `None`                 | Label shadow options.                                                       |
| `container_shadow`    | dict     | `None`                 | Container shadow options.                                                   |
| `app_title_shadow`    | dict     | `None`                 | Shadow options for app titles.                                              |
| `app_icon_shadow`     | dict     | `None`                 | Shadow options for app icons.                                               |
| `shortcuts`           | dict     | `{add_app: "Ctrl+N", edit_app: "F2", show_context_menu: "Shift+F10", delete_app: "Delete"}` | Keyboard shortcuts for popup actions. |

## Example Configuration

```yaml
launchpad:
  type: "yasb.launchpad.LaunchpadWidget"
  options:
    label: "<span>\udb85\udcde</span>"
    search_placeholder: "Search apps..."
    app_icon_size: 48
    window:
      fullscreen: false
      width: 800
      height: 600
      overlay_block: true
    window_style:
      enable_blur: true
      round_corners: true
      round_corners_type: "normal"
      border_color: "system"
    window_animation:
      fade_in_duration: 200
      fade_out_duration: 200
    callbacks:
      on_left: "toggle_launchpad"
    app_title_shadow:
      enabled: true
      color: "#00000090"
      offset: [1, 1]
      radius: 2
    app_icon_shadow:
      enabled: true
      color: "#00000090"
      offset: [0, 2]
      radius: 8
```

## Shortcuts

You can customize keyboard shortcuts for common actions in the Launchpad popup using the `shortcuts` option.  
The following shortcuts are available by default:

| Shortcut Name         | Default Key      | Action                                      |
|-----------------------|------------------|---------------------------------------------|
| `add_app`             | `Ctrl+N`         | Add a new application                       |
| `edit_app`            | `F2`             | Edit the currently selected application     |
| `show_context_menu`   | `Shift+F10`      | Show the context menu for the popup         |
| `delete_app`          | `Delete`         | Delete the currently selected application   |

You can override these in your configuration, for example:

```yaml
launchpad:
  type: "yasb.launchpad.LaunchpadWidget"
  options:
    shortcuts:
      add_app: "Ctrl+N"
      edit_app: "F2"
      show_context_menu: "Shift+F10"
      delete_app: "Delete"
```

## Description of Options

- **label:** The label/icon for the widget on the bar.
- **search_placeholder:** Placeholder text for the search field in the popup.
- **app_icon_size:** Size of application icons in pixels.
- **label_shadow:** Shadow options for the label.
- **container_shadow:** Shadow options for the widget container.
- **window:** Popup window size and fullscreen options.
  - ***fullscreen:*** Whether the popup should be fullscreen.
  - ***width:*** Width of the popup window.
  - ***height:*** Height of the popup window.
  - ***overlay_block:*** Whether the popup should block interaction with the main window.
- **window_style:** Popup window styling (blur, round corners, border, etc).
  - ***enable_blur:*** Whether to enable background blur for the popup.
  - ***round_corners:*** Whether to round the corners of the popup window.
  - ***round_corners_type:*** Type of corner rounding ("normal" or "small").
  - ***border_color:*** Color of the popup window border (can be "system" HEX or None).
- **window_animation:** Animation settings for showing/hiding the popup.
  - ***fade_in_duration:*** Duration of the fade-in animation in milliseconds.
  - ***fade_out_duration:*** Duration of the fade-out animation in milliseconds.
- **animation:** Widget label animation settings.
  - ***enabled:*** Whether animations are enabled.
  - ***type:*** Type of animation ("fadeInOut").
  - ***duration:*** Duration of the animation in milliseconds.
- **callbacks:** Mouse event callbacks (`on_left`, `on_middle`, `on_right`).
- **app_title_shadow:** Shadow options for app titles.
  - ***enabled:*** Whether to enable shadow for app titles.
  - ***color:*** Color of the shadow (HEX, HEX with alpha or name).
  - ***offset:*** Offset of the shadow in pixels (x, y).
  - ***radius:*** Radius of the shadow blur.
- **app_icon_shadow:** Shadow options for app icons.
  - ***enabled:*** Whether to enable shadow for app icons.
  - ***color:*** Color of the shadow (HEX, HEX with alpha or name).
  - ***offset:*** Offset of the shadow in pixels (x, y).
  - ***radius:*** Radius of the shadow blur.
- **label_shadow**: Shadow options for the widget label.
  - ***enabled:*** Whether to enable shadow for the label.
  - ***color:*** Color of the shadow (HEX, HEX with alpha or name).
  - ***offset:*** Offset of the shadow in pixels (x, y).
  - ***radius:*** Radius of the shadow blur.
- **container_shadow**: Shadow options for the widget container.
  - ***enabled:*** Whether to enable shadow for the container.
  - ***color:*** Color of the shadow (HEX, HEX with alpha or name).
  - ***offset:*** Offset of the shadow in pixels (x, y).
  - ***radius:*** Radius of the shadow blur.
- **shortcuts**: Keyboard shortcuts for common actions in the Launchpad popup.
  - **Ctrl+N**: Open the "Add New App" dialog.
  - **F2**: Edit the currently focused/selected app.
  - **Delete**: Delete the currently focused/selected app (with confirmation).
  - **Shift+F10**: Open the context menu for additional actions.

## Widget Description
The Launchpad widget is a powerful and user-friendly application launcher designed for quick access to your favorite programs, scripts, files, or web links. Inspired by the macOS Launchpad, it presents your apps in a visually organized grid popup, complete with search, drag-and-drop reordering, and context menu actions. All your launchpad app entries and their icons are safely stored in your configuration directory, making it easy to back up, migrate, or edit your app list manually if needed

**Key Features:**
- **App Grid:** Displays your applications as icons with titles in a grid layout.
- **Quick Launch:** Click any icon to instantly launch the associated executable, script, or open a URL in your default browser.
- **Search:** Filter your apps in real-time using the search bar.
- **Drag & Drop:** Drag and drop shortcut icons or executables into the grid to add them to your launchpad. Reorder apps by dragging them around.
- **Context Menu:** Right-click any app for options to edit, delete, or change the order of your apps (A-Z, Z-A, recent, oldest).
- **Add/Edit Apps:** Easily add new apps or edit existing ones, including setting a custom icon and title.
- **Customizable Appearance:** Supports custom icon sizes, window blur, rounded corners, shadows, and more via configuration.
- **Keyboard Navigation:** Navigate the grid and launch apps using arrow keys and Enter.
- **Animations:** Smooth fade-in and fade-out animations for the popup window.

> **Note:**
> The Launchpad widget supports autocomplete for application names when adding or editing apps. In most cases, the icon will be extracted automatically for executables and shortcuts. However, for some applications (especially certain UWP apps or unusual shortcuts), icon extraction may not always succeed. If this happens, you can manually select an icon file.

> [!IMPORTANT]  
> Launchpad widget uses the `QMenu` for the context menu, which supports various styles. You can customize the appearance of the menu using CSS styles. For more information on styling, refer to the [Context Menu Styling](https://github.com/amnweb/yasb/wiki/Styling#context-menu-styling
If you want to use different styles for the context menu, you can target the `.launchpad .context-menu` class to customize the appearance of the Launchpad widget menu.

## Example Style

```css
/* Widget style */
.launchpad-widget {
    padding: 0 6px 0 6px;
}
.launchpad-widget .label {}
.launchpad-widget .icon {
    font-size: 16px;
    color: #89b4fa;
}

/* Launchpad context menu style */
.launchpad .context-menu {
    background-color: #202020;
    border: none;
    border-radius: 6px;
    padding: 4px 0px;
    font-family: 'Segoe UI';
    font-size: 12px;
    color: #FFFFFF;
    font-weight: 600
}
.launchpad .context-menu::item {
    background-color: transparent;
    padding: 6px 12px;
    margin: 2px 6px;
    border-radius: 4px;
    min-width: 100px;
}
.launchpad .context-menu::item:selected {
    background-color: #3a3a3a;
    color: #FFFFFF;
}
.launchpad .context-menu::item:pressed {
    background-color: #3A3A3A;
}
.launchpad .context-menu::separator {
    height: 1px;
    background-color: #404040;
    margin: 4px 8px;
}
.launchpad .context-menu::item:disabled {
    color: #666666;
    background-color: transparent;
}

/* Launchpad App dialog style */
.launchpad .app-dialog {
    font-family: 'Segoe UI';
    background-color: #202020;
}
.launchpad .app-dialog .buttons-container {
    background-color: #171717;
    margin-top: 16px;
    border-top: 1px solid #000;
    max-height: 80px;
    min-height: 80px;
    padding: 0 20px 0 20px;
}
.launchpad .app-dialog .message {
    color: #FFFFFF;
    font-family: 'Segoe UI';
    font-size: 12px;
    font-weight: 600;
    padding: 10px 0
}
.launchpad .app-dialog .title-field,
.launchpad .app-dialog .path-field,
.launchpad .app-dialog .icon-field {
    background-color: #181818;
    border: 1px solid #303030;
    border-radius: 4px;
    padding: 0 6px;
    font-family: 'Segoe UI';
    font-size: 12px;
    font-weight: 600;
    color: #FFFFFF;
    margin: 10px 0px 5px 0;
    min-height: 30px;
}
.launchpad .app-dialog .title-field:focus,
.launchpad .app-dialog .path-field:focus,
.launchpad .app-dialog .icon-field:focus {
    border-bottom-color: #4cc2ff;
}
.launchpad .app-dialog .button {
    background-color: #2d2d2d;
    border: none;
    border-radius: 4px;
    font-family: 'Segoe UI';
    font-size: 12px;
    font-weight: 600;
    color: #FFFFFF;
    min-width: 80px;
    padding: 0 6px;
    margin: 10px 0 5px 6px;
    min-height: 28px;
    outline: none;
}
.launchpad .app-dialog .buttons-container .button {
    margin: 10px 0 5px 0px;
    font-size: 13px;
}
.launchpad .app-dialog .button:focus {
    border: 2px solid #adadad;
}
.launchpad .app-dialog .button:focus,
.launchpad .app-dialog .button:hover {
    background-color: #4A4A4A;
}
.launchpad .app-dialog .button:pressed {
    background-color: #3A3A3A;
}
.launchpad .app-dialog .button.add,
.launchpad .app-dialog .button.save {
    background-color: #0078D4;
}
.launchpad .app-dialog .button.add:focus,
.launchpad .app-dialog .button.save:focus,
.launchpad .app-dialog .button.add:hover,
.launchpad .app-dialog .button.save:hover {
    background-color: #0066B2;
}
.launchpad .app-dialog .button.add:pressed,
.launchpad .app-dialog .button.save:pressed {
    background-color: #00509E;
}
.launchpad .app-dialog .button.delete {
    background-color: #bd2d14;
}
.launchpad .app-dialog .button.delete:focus,
.launchpad .app-dialog .button.delete:hover {
    background-color: #b30f00;
}
.launchpad .app-dialog .button.delete:pressed {
    background-color: #a00b00;
}
.launchpad .app-dialog .warning-message {
    background-color: #2b0b0e;
    border: 1px solid #5a303c;
    border-radius: 4px;
    color: #cc9b9f;
    font-family: 'Segoe UI';
    font-size: 12px;
    font-weight: 600;
    padding: 8px 12px;
    margin: 4px 0px;
}
/* Launchpad popup style */
.launchpad .drop-overlay {
    background-color: rgba(24, 25, 27, 0.8);
    border:4px dashed #3c80ff;
}
.launchpad .drop-overlay .text {
    color: #ffffff;
    font-family: 'Segoe UI';
    font-size: 64px;
    font-weight: 600;
    text-transform: uppercase;
}
.launchpad .launchpad-container {
    background-color: rgba(24, 25, 27, 0.8);
}
.launchpad .search-container {
    border-bottom: 1px solid rgba(255, 255, 255, 0.15);
    background-color:rgba(0, 0, 0, 0.3);
    min-height: 80px;
    margin: 0;
    padding: 0
}
.launchpad .search-input {
    max-width: 400px;
    padding: 8px 12px;
    font-size: 14px;
    min-height: 24px;
    max-height: 24px;
    font-family: 'Segoe UI';
    border-radius: 20px;
    border: 2px solid rgb(53, 54, 56);
    background-color: rgba(0, 0, 0, 0.507);
    color: #a6adc8;
}
.launchpad .search-input:focus  {
    border: 2px solid rgb(22, 114, 190);
    background-color: rgba(255, 255, 255, 0.05);
}
.launchpad .launchpad-scroll-area {
    background-color: transparent;
    border: none;
}
.launchpad .app-icon {
    background-color: rgba(102, 10, 10, 0);
    border-radius: 12px;
    border: 2px solid rgba(112, 76, 32, 0);
    padding-top: 10px;
    margin: 24px 6px 6px 6px;
    max-width: 110px;
    min-width: 110px;
    min-height: 110px;
    max-height: 110px; 
}
.launchpad .app-icon:focus {
    border: 2px solid #89b4fa;
    background-color: rgba(255, 255, 255, 0.06);
}
.launchpad .app-icon:hover {
    border: 2px solid #89b4fa;
    background-color: rgba(255, 255, 255, 0.13);
}
.launchpad .app-icon .title {
    color: #a6adc8;
    font-family: 'Segoe UI';
    font-size: 14px;
    margin-top: 2px;
    font-weight: 600
}
/* App icon .launchpad .app-icon or URL icon .launchpad .app-icon.url */
.launchpad .app-icon.url .title{
    color: #52f1d2;
}
.launchpad .app-icon .icon {
    padding: 0;
    margin: 0
}
```
> [!NOTE]
> Launchpad widget supports toggle visibility using the `toggle-widget launchpad` command in the CLI. More information about the CLI commands can be found in the [CLI documentation](https://github.com/amnweb/yasb/wiki/CLI#toggle-widget-visibility).

## Preview

![Launchpad Widget Preview](assets/cf6e095b-804e2221-a7a8-a36b-44bde9433392.png)