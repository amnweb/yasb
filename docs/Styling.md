## Style file    

Styling is done using the CSS file format and with a file named `styles.css`.

Valid directories for this file are `C:/Users/{username}/.config/yasb/` or path where YASB is Installed. A good starting point is the [default style](https://github.com/amnweb/yasb/blob/main/src/styles.css).

## Bar styling

The main YASB window can be styled with the following:
- `.yasb-bar`

## Widget Group Styling

Each widget group can be styled individually with the following:
- `.container-left`
- `.container-center`
- `.container-right`

## Generic Widget Style

A style with the `.widget` selector would affect all the widgets. In practice, you may prefer to use more specific `.*-widget` selectors.
Example how to target clock widget
```
.clock-widget {
	border-top-left-radius: 18px;
	border-bottom-left-radius: 18px;
}
```

## Per-output styling

The main YASB windows carry a class tag with the name of the output this window is shown on.

```
* { font-size: 13px;color: #cdd6f4; }
```

Example above will set the default font size and color of all elements unless overridden later on.


## Style Icons

Icons can be styled with the following:
- `.icon`

.icon class above will affect all icons inside the span tag in configuration file.
`label: "<span>\uf4bc</span> {virtual_mem_free}"`
You can specify different icon class in the configuration file as shown below.

```
label: "<span class=\"icon-1"\">\uf4bc</span> {virtual_mem_free}"
```

## Style Text

Text can be styled with the following:
- `.label`

## Widget Container Styling

Each icon and text is wrapped in a container. This container can be styled with the following:
- `.widget-container`

Example how to target widget container

``` 
.clock-widget .widget-container {
    background-color: #1e1e1e;
    border-radius: 10px;
}
.media-widget .widget-container {
    background-color: #1e1e1e;
    border-radius: 10px;
}
```

> **Note:**
> Keep the mind YASB is written in Python and styled with CSS is very limited. You can't use CSS3 or any other advanced CSS features.

