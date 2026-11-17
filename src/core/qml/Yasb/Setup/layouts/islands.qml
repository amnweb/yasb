import Yasb.Bar

// A thin rail along the screen edge, with each group of widgets on its own island, outlined on the side away from
// the screen. The widgets come from config.yaml; this file sets how the bar looks, for example railHeight,
// edgeRadius, color or border.
IslandBar {
    color: theme.bar.background
    border.width: 1
    border.color: theme.bar.border
    railHeight: 1
    radius: 16
    edgeRadius: 16
    padding: 12
    spacing: 10
}
