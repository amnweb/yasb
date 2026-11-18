import Yasb.Bar

// A bar with rounded corners and a border all around; the gap to the screen edges is the bar's margin in
// config.yaml. The widgets come from config.yaml; this file sets how the bar looks, for example its color, radius,
// border, padding or spacing.
Bar {
    color: theme.bar.background
    border.width: 1
    border.color: theme.bar.border
    radius: 8
    padding: 12
    spacing: 12
}
