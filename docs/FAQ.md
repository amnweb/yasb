# Frequently Asked Questions

## Installation Issues

### Q: Why aren't the icons showing up correctly?
**A:** This usually means the status bar fonts are missing on your system. 
- You can fix this easily by running the **Setup Wizard** (delete your config files or run `yasbc reset` to open it), which can download and install both **JetBrains Mono Nerd Font** and **Segoe Fluent Icons** automatically.
- Alternatively, you can download and install them manually. The default setup recommends [JetBrains Mono Nerd Font](https://github.com/ryanoasis/nerd-fonts/releases/latest/download/JetBrainsMono.zip). 
- If you're on Windows 10, make sure you also install Segoe Fluent Icons from Microsoft.
- Remember to restart YASB after installing any new fonts so it can detect them.

### Q: Why doesn't the blur effect work?
**A:** Check these points:
- Windows 10/11 transparency effects are enabled in system settings
- The `blur_effect` is enabled in config.yaml
- Your GPU drivers are updated
- Windows composition is enabled

## Configuration Issues

### Q: Where are the configuration files located?
**A:** Default location: `C:/Users/{username}/.config/yasb/`
Required files:
- `config.yaml` - Main configuration
- `styles.css` - Visual styling

### Q: How to set custom configuration directory?
**A:** Set the `YASB_CONFIG_HOME` environment variable to the desired directory path.

### Q: YASB crashes after updating?
**A:** After updates:
- Check release notes for breaking changes
- Compare your config with the latest example config
- Backup your configs before updating

### Q: How to reset YASB settings?
**A:** You can delete the `config.yaml` and `styles.css` files from your configuration directory, or simply open a terminal and run the CLI command:
```bash
yasbc reset
```
On the next launch, YASB will automatically start the interactive **Setup Wizard** to help you reinstall fonts and set up your layouts and window managers again.

### Q: How to change the bar position?
**A:** Modify the `position` value in `config.yaml`:
- `top` - Top of the screen
- `bottom` - Bottom of the screen

### Q: How to check for updates?
**A:** There are three ways to check for and apply updates in YASB:
- **Automatic Background Checks:** If `update_check` is set to `true` in your `config.yaml`, YASB will periodically check for new versions in the background and show a Windows toast notification when an update is found.
- **System Tray Context Menu:** When an update is available, a red badge will appear on the YASB tray icon. Right-click the YASB icon in your system tray and select the **Update Available** option to open the visual update installer.
- **CLI Command:** You can manually run updates from your terminal by executing:
  ```bash
  yasbc update
  ```

### Q: How to change the bar size?
**A:** Adjust the bar `width` and `height` value in `config.yaml` to change the bar size.

### Q: How to troubleshoot issues or check logs for errors?
**A:** You can view logs and enable more detailed debug information to help troubleshoot issues:
- **Enable Debug Mode:** Set `debug: true` in your `config.yaml` to enable verbose logging. This is especially helpful for troubleshooting widget or application errors.
- **View Logs via CLI:** Run `yasbc log` in your terminal to stream real-time logs.
- **View Log File:** Check the `yasb.log` file located in your config directory (default: `C:/Users/{username}/.config/yasb/`).

### Q: How do I make YASB start automatically when Windows boots?
**A:** You can set YASB to run on startup in two ways:
- **System Tray Menu:** Right-click the YASB icon in your system tray (bottom-right of your screen) and toggle **Enable Autostart**.
- **CLI Commands:** Open a terminal and run `yasbc enable-autostart`. If you experience delayed startups or need it to run with admin rights, you can register it as a Windows Scheduled Task instead by running `yasbc enable-autostart --task`.


## Widget Issues

### Q: Weather widget not working?
**A:** Verify:
- Valid API key from [weatherapi.com](https://www.weatherapi.com)
- Correct `api_key` and `location` in settings
- Active internet connection

### Q: Missing applications in Taskbar widget?
**A:** Note:
- Only shows running applications with visible windows
- Check filter settings in `config.yaml`

## Performance Issues

### Q: High CPU usage?
**A:** Common causes:
- Low `update_interval` values
- Too many real-time widgets

### Q: Delayed startup?
**A:** Solutions:
- Use `yasbc enable-autostart --task` to create a scheduled task for YASB
- Check startup programs for conflicts

## Styling Issues

### Q: How to customize appearance?
**A:** Edit `styles.css`:
```css
.yasb-bar { /* Main bar */ }
.widget { /* All widgets */ }
.clock-widget { /* Specific widget */ }
```

### Q: CSS not working?
**A:** Limitations:
- Basic CSS properties supported
- No advanced CSS3 features
- Check syntax in styles.css
- Restart YASB after changes


## Getting Help

- Check the [Wiki](https://github.com/amnweb/yasb/wiki)
- Join [Discord](https://discord.gg/qkeunvBFgX)
- Open an [issue](https://github.com/amnweb/yasb/issues)