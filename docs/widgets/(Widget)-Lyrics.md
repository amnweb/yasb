# Lyrics Widget Options

A synchronized lyrics display widget that connects to active Windows media sessions and renders real-time lyrics directly in your status bar.

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `class_name` | string | `""` | Custom CSS class name for the widget container. |
| `max_width` | integer \| null | `null` | Maximum width in pixels if `fixed_width` is not specified. |
| `fixed_width` | integer \| null | `null` | Fixed width in pixels. Prevents status bar shifting as lines change length. |
| `line_transition` | string | `"slide_up"` | Line animation: `"none"`, `"slide_up"`, `"scale"`, `"wipe"`. |
| `font_scale` | float | `1.0` | Font scaling multiplier for status bar lyric text (0.5 to 3.0). |
| `visualizer` | string \| null | `null` | Visualizer style during instrumental breaks: `"bars"`, `"bars_mirrored"`, `"waves"`, `"waves_mirrored"`, `"notes"`, `"dots"`, `"none"`. |
| `visualizer_options` | dict | [See below](#visualizer-options) | Size, layout, smoothing and frequency range of the visualizer. |
| `sparkles` | boolean | `true` | Enables sparkles along the vocal sweep needle on beat transients. |
| `apply_accent_to` | string | `"effects"` | How accent colors apply: `"effects"` (particles/glow), `"all"` (text + effects), `"nothing"`. |
| `accent` | string | `"album_art"` | Palette source: `"album_art"` (cover art palette) or `"yasb"` (yasb accent color). |
| `beat_jump` | boolean | `true` | Enables word jump on beats. |
| `romanize_replace` | boolean | `false` | Replace non-Latin lyrics with phonetic romanization directly in the bar. |
| `hide_when_paused` | boolean \| number | `false` | Collapse widget when paused: `false` (never), `true` (5s delay), or number of seconds. |
| `hide_when_no_lyrics` | boolean | `false` | Collapse widget when no lyrics are found for current song. |
| `callbacks` | dict | [See below](#callbacks) | Mouse callbacks on the status bar widget. |
| `popup` | dict | [See below](#popup-options) | Floating multiline lyrics sheet dropdown popup settings. |


---

## Example Configuration

```yaml
lyrics:
  type: "yasb.lyrics.LyricsWidget"
  options:
    fixed_width: 320
    font_scale: 1.0
    line_transition: "scale"
    visualizer: "bars"
    sparkles: true
    apply_accent_to: "effects"
    accent: "yasb"
    beat_jump: true
    romanize_replace: false
    hide_when_paused: 5
    hide_when_no_lyrics: false
    popup:
      width: 420
      height: 520
      alignment: "center"
      direction: "down"
      offset_left: 0
      offset_top: 6
      font_scale: 1.0
      background_style: "ambient"
      romanize: true
    callbacks:
      on_left: "toggle_popup"
      on_right: "toggle_menu"
```

---

## Visualizer Options

Settings under `visualizer_options` apply to the instrumental-break visualizer (`bars`, `waves`, ...). Option names follow the [Cava widget](https://github.com/amnweb/yasb/wiki/(Widget)-Cava) where an equivalent exists. The beat effects (`beat_jump`, `sparkles`) are analysed separately from the displayed bars, so none of these options change how they react.

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `bars_number` | integer \| null | `null` | Number of bars (4 to 32); for waves, the number of points. `null` uses 10 bars / 14 wave points. |
| `bar_width` | float | `3.0` | Width of each bar in pixels (1 to 20). |
| `bar_spacing` | float | `2.0` | Gap between bars in pixels (0 to 30). Waves use 90% of `bar_width + bar_spacing` as the point spacing. |
| `bar_radius` | float | `1.5` | Corner radius of each bar in pixels (0 to 10). |
| `bar_height` | integer \| null | `null` | Maximum bar height in pixels (4 to 100). `null` follows the font height. |
| `min_bar_height` | integer \| null | `null` | Height of a silent bar in pixels (1 to 50). `null` follows the font height. Must be below `bar_height`. |
| `vertical_alignment` | string | `"middle"` | Where the visualizer sits in the widget: `"top"`, `"middle"` or `"bottom"`. Applies to `bars`, `waves`, `notes` and `dots`. At `"top"`, bars and waves are flipped so they hang from the top edge; notes and dots are not flipped. The mirrored styles (`bars_mirrored`, `waves_mirrored`) and `none` ignore this option and stay centred. |
| `layout` | string | `"linear"` | `"linear"` draws low to high. `"mirrored"` is symmetric about the vertical axis with the bass in the centre, like Cava's stereo mode. |
| `reverse` | boolean | `false` | Flips the order. In `"mirrored"` layout the bass moves to the outside edges. |
| `noise_reduction` | integer | `65` | Smoothing (0 to 100). Higher is smoother with a slower fall-off; lower is snappier. |
| `monstercat` | float | `1.0` | Spreads a peak into neighbouring bars (0 to 5). `0` turns it off. |
| `sensitivity` | integer | `100` | Trim on top of automatic gain, in percent (10 to 200). Above 100 the bars sit higher, below 100 they keep headroom. |
| `lower_cutoff_freq` | integer | `50` | Lowest frequency shown, in Hz (20 to 1000). |
| `higher_cutoff_freq` | integer | `10000` | Highest frequency shown, in Hz (1000 to 20000). Must be above `lower_cutoff_freq`. |
| `framerate` | integer | `60` | Visualizer update rate (15 to 120). Lower values reduce CPU use. |

With `layout: "mirrored"`, the full frequency range is drawn on each half, so `bars_number: 10` shows 5 bars per side. Both sides come from one mono mix of the audio.

Example, similar to a Cava widget in stereo mode:

```yaml
lyrics:
  type: "yasb.lyrics.LyricsWidget"
  options:
    visualizer: "bars"
    visualizer_options:
      layout: "mirrored"
      bars_number: 10
      bar_width: 2
      bar_spacing: 4
      bar_height: 15
      min_bar_height: 2
      lower_cutoff_freq: 60
      higher_cutoff_freq: 16000
      noise_reduction: 25
      monstercat: 0
```

---

## Popup Options

Options configured under `popup:`:

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `width` | integer | `420` | Width of the floating popup window (200 to 1200 px). |
| `height` | integer | `520` | Height of the floating popup window (200 to 1000 px, clamped to screen). |
| `alignment` | string | `"center"` | Alignment relative to parent bar button: `"center"`, `"left"`, `"right"`. |
| `direction` | string | `"down"` | Opening direction: `"down"` or `"up"`. |
| `offset_left` | integer | `0` | Horizontal pixel offset from button (negative = left, positive = right). |
| `offset_top` | integer | `6` | Vertical pixel offset from bar (positive = away from bar). |
| `font_scale` | float | `1.0` | Font scaling multiplier for sheet lyric lines (0.5 to 3.0). |
| `romanize` | boolean | `true` | Display phonetic romanized subtitle below non-Latin lyrics in the sheet. |
| `background_style` | string | `"ambient"` | Backdrop style: `"ambient"` (fluid blobs), `"blur"` (album blur), `"gradient"`, `"inherit"` (bar theme), `"black"`. |
| `progress_style` | string | `"line"` | Look of the progress bar in the info card: `"line"` (thin bar) or `"wave"` (One UI style). |

The top info card of the popup shows the cover art, title and artist, a progress bar with elapsed and total time, and previous, play/pause and next buttons. Click or drag the progress bar to seek (when the player allows seeking).

When there are no lyrics to show (not found, failed, or an instrumental track with no text), the popup shrinks to just the info card. `height` applies when lyrics are shown.

---

## Callbacks

The `callbacks` option maps mouse buttons (`on_left`, `on_middle`, `on_right`) to actions. All keys are optional, the values shown are the defaults.

```yaml
callbacks:
  on_left: "toggle_popup"
  on_middle: "do_nothing"
  on_right: "toggle_menu"
```

Available actions:

| Callback | Description |
| :--- | :--- |
| `toggle_popup` | Opens or closes the floating lyrics sheet popup. |
| `toggle_menu` | Opens the options / providers context menu. |
| `toggle_label` | Switches the bar text between live lyrics and the artist — title line. |
| `cycle_hit` | Advances to the next ranked lyrics match for the current track. |
| `copy_lyrics` | Copies the current active lyric line to the clipboard. |
| `do_nothing` | Disables callback for that mouse action. |

---

## CSS Classes

```css
/* Bar widget */
.lyrics-widget {}
.lyrics-widget.synced {}                  /* Line-synced or syllable-synced lyrics active */
.lyrics-widget.plain {}                   /* Static plain text lyrics displayed */
.lyrics-widget.searching {}               /* Searching lyric providers */
.lyrics-widget.not-found {}               /* No lyrics found for current track */
.lyrics-widget.paused {}                  /* Player paused */
.lyrics-widget.idle {}                    /* No media playing */
.lyrics-widget.break {}                   /* Instrumental / interlude break */
.lyrics-widget.instrumental {}            /* Instrumental break active */
.lyrics-widget .label {}                  /* Active lyric label on the bar */

/* Popup window root and container */
.lyrics-popup {}                          /* Main floating popup window */
.lyrics-popup .popup-container {}         /* Inner framed container */

/* Header track information & window buttons */
.lyrics-popup .popup-header {}            /* Top header card */
.lyrics-popup .header-artwork {}          /* Album art cover thumbnail */
.lyrics-popup .header-title {}            /* Track title */
.lyrics-popup .header-artist {}           /* Track artist */
.lyrics-popup .header-btn {}              /* Header icon buttons */
.lyrics-popup .header-btn.pin-btn {}      /* Pin popup button */
.lyrics-popup .header-btn.pin-btn.active {} /* Pin button when pinned */
.lyrics-popup .header-btn.close-btn {}    /* Close button */

/* Header transport controls and timeline */
.lyrics-popup .header-controls {}         /* Controls and progress area */
.lyrics-popup .progress-container {}      /* Timeline container */
.lyrics-popup .time-label {}              /* Elapsed and total duration labels */
.lyrics-popup .time-label.elapsed {}      /* Elapsed playback timestamp */
.lyrics-popup .time-label.total {}        /* Total track duration timestamp */
.lyrics-popup .progress-bar {}            /* Progress track bar / wave visualizer */
.lyrics-popup .media-btn {}               /* Transport buttons container & common style */
.lyrics-popup .media-btn.prev-btn {}      /* Previous track button */
.lyrics-popup .media-btn.play-btn {}      /* Play / pause button */
.lyrics-popup .media-btn.next-btn {}      /* Next track button */

/* Scrollable lyrics area */
.lyrics-popup .lyrics-scroll-area {}      /* Viewport area */
.lyrics-popup .lyrics-scroll-area QScrollBar:vertical {}
.lyrics-popup .lyrics-scroll-area QScrollBar::handle:vertical {}
.lyrics-popup .lyrics-scroll-area QScrollBar::handle:vertical:hover {}
.lyrics-popup .lyrics-scroll-area QScrollBar::add-line:vertical,
.lyrics-popup .lyrics-scroll-area QScrollBar::sub-line:vertical {}

/* Lyric rows and states */
.lyrics-popup .rows-container {}          /* Vertical list container of lyric rows */
.lyrics-popup .lyrics-row {}              /* Base row wrapper */
.lyrics-popup .lyrics-row:hover {}        /* Hovered lyric line */
.lyrics-popup .lyrics-row.row-active {}   /* Currently singing line */
.lyrics-popup .lyrics-row.row-upcoming {} /* Upcoming lines */
.lyrics-popup .lyrics-row.row-past {}     /* Past sung lines */
.lyrics-popup .lyrics-row.row-break {}    /* Instrumental interlude row */
.lyrics-popup .lyrics-row.row-break.active {}

/* Vocal lane classes */
.lyrics-popup .lyrics-row.lead {}         /* Primary vocalist line */
.lyrics-popup .lyrics-row.counter {}      /* Backing / counter vocal line */
.lyrics-popup .lyrics-row.duet {}         /* Duet line */

/* Lyric text elements */
.lyrics-popup .lyrics-row .row-main-text {}        /* Primary sung line text */
.lyrics-popup .lyrics-row .row-secondary-text {}   /* Backing / harmony vocals */
.lyrics-popup .lyrics-row .row-romanized-text {}   /* Pronunciation guide */
.lyrics-popup .lyrics-row .row-translation-text {} /* Translated lyrics */

/* Floating return/follow pill */
.lyrics-popup .follow-pill {}             /* "Jump to current lyric" pill button */
.lyrics-popup .follow-pill:hover {}

/* Status message screen */
.lyrics-popup .popup-message-frame {}     /* Frame shown when searching or no lyrics */
.lyrics-popup .message-icon {}            /* Status icon */
.lyrics-popup .message-text {}            /* Status message */
.lyrics-popup .retry-btn {}               /* Search retry button */
.lyrics-popup .retry-btn:hover {}

/* Popup footer */
.lyrics-popup .popup-footer {}            /* Bottom bar */
.lyrics-popup .footer-source {}           /* Lyrics provider credit (e.g. LrcLib) */
.lyrics-popup .footer-btn {}              /* Footer hit switch buttons */
.lyrics-popup .footer-btn.hit-btn {}
.lyrics-popup .footer-hit-count {}        /* Ranked result counter (e.g. 1/3) */
```

> [!NOTE]
>
> - **Progress Bar (`.progress-bar`)**: The canvas visualizer (thin line or One UI wave) is drawn dynamically using hardware-accelerated Qt painter with colors derived from the album palette.
> - **Play/Pause Button (`.media-btn.play-btn`)**: The circular play button dynamically highlights using the track's album accent color
> - **Active Pin Button (`.header-btn.pin-btn.active`)**: Dynamically adopts the album accent color when the popup is pinned.
> - **Follow Pill (`.follow-pill`)**: The floating "Jump to current lyric" pill button adopts the album accent color for high visibility.
>
> All other UI elements—including the widget bar, popup window container, header card, track typography, elapsed/total time labels (`.time-label`), previous/next transport buttons, scrollbars, lyric rows (`.row-active`, `.row-upcoming`, `.row-past`), pronunciation/translations, status screens, and footer—can be freely styled and customized via CSS.

## Example CSS

```css
/* ==========================================================================
   Lyrics Bar Widget
   ========================================================================== */

.lyrics-widget {
    background: transparent;
    padding: 0 8px;
}

.lyrics-widget .label {
    font-size: 13px;
    font-weight: 600;
    color: #cdd6f4;
}

.lyrics-widget.synced .label {
    color: #a6e3a1;
}

.lyrics-widget.break .label,
.lyrics-widget.instrumental .label {
    color: #fab387;
    font-style: italic;
}

.lyrics-widget.paused .label {
    color: #6c7086;
}

.lyrics-widget.searching .label {
    color: #89b4fa;
}

.lyrics-widget.not-found .label {
    color: #f38ba8;
}

/* ==========================================================================
   Lyrics Popup Window
   ========================================================================== */

.lyrics-popup {
    background-color: transparent;
}

.lyrics-popup .popup-container {
    background-color: rgba(24, 24, 37, 0.92);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
    padding: 12px;
}

/* Header card */
.lyrics-popup .popup-header {
    background-color: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 12px;
    padding: 10px;
    margin-bottom: 8px;
}

.lyrics-popup .header-artwork {
    border-radius: 8px;
}

.lyrics-popup .header-title {
    font-size: 14px;
    font-weight: 700;
    color: #cdd6f4;
    padding-left: 8px;
}

.lyrics-popup .header-artist {
    font-size: 12px;
    font-weight: 500;
    color: #a6adc8;
    padding-left: 8px;
}

.lyrics-popup .header-btn {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 4px;
}

.lyrics-popup .header-btn:hover {
    background: rgba(255, 255, 255, 0.12);
}

/* Note: When pinned, .header-btn.pin-btn dynamically highlights with the album art accent color */

/* Timeline & playback controls */
.lyrics-popup .header-controls {
    margin-top: 6px;
}

.lyrics-popup .time-label {
    font-size: 11px;
    color: #a6adc8;
    min-width: 34px;
}

/* Note: .progress-bar line and wave visualizers render dynamically from the album cover art */
.lyrics-popup .progress-bar {
    min-height: 20px;
}

.lyrics-popup .media-btn {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 15px;
    color: #ffffff;
}

.lyrics-popup .media-btn:hover {
    background: rgba(255, 255, 255, 0.14);
}

/* Note: .media-btn.play-btn is dynamically accented with the track's album art color */

/* Scroll area & scrollbar */
.lyrics-popup .lyrics-scroll-area {
    background: transparent;
    border: none;
}

.lyrics-popup .lyrics-scroll-area QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 4px 0;
}

.lyrics-popup .lyrics-scroll-area QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 0.18);
    border-radius: 3px;
    min-height: 24px;
}

.lyrics-popup .lyrics-scroll-area QScrollBar::handle:vertical:hover {
    background: rgba(255, 255, 255, 0.32);
}

.lyrics-popup .lyrics-scroll-area QScrollBar::add-line:vertical,
.lyrics-popup .lyrics-scroll-area QScrollBar::sub-line:vertical {
    height: 0px;
    background: transparent;
}

/* Lyric rows & typography */
.lyrics-popup .rows-container {
    background: transparent;
}

.lyrics-popup .lyrics-row {
    padding: 6px 12px;
    border-radius: 8px;
}

.lyrics-popup .lyrics-row:hover {
    background-color: rgba(255, 255, 255, 0.05);
}

.lyrics-popup .lyrics-row .row-main-text {
    font-size: 14px;
    color: #cdd6f4;
}

.lyrics-popup .lyrics-row.row-active .row-main-text {
    color: #ffffff;
    font-weight: 700;
}

.lyrics-popup .lyrics-row.row-upcoming .row-main-text {
    color: rgba(205, 214, 244, 0.65);
}

.lyrics-popup .lyrics-row.row-past .row-main-text {
    color: rgba(205, 214, 244, 0.35);
}

.lyrics-popup .lyrics-row .row-secondary-text {
    font-size: 12px;
    color: #89b4fa;
    font-style: italic;
}

.lyrics-popup .lyrics-row .row-romanized-text {
    font-size: 11px;
    color: #fab387;
}

.lyrics-popup .lyrics-row .row-translation-text {
    font-size: 11px;
    color: #a6adc8;
}

/* Note: .follow-pill background and text color are dynamically tinted by album art */
.lyrics-popup .follow-pill {
    font-size: 11px;
    font-weight: 700;
}

/* Status message frame */
.lyrics-popup .popup-message-frame {
    background: transparent;
}

.lyrics-popup .message-icon {
    font-size: 32px;
    color: #6c7086;
}

.lyrics-popup .message-text {
    font-size: 13px;
    color: #a6adc8;
}

.lyrics-popup .retry-btn {
    background-color: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 6px;
    color: #cdd6f4;
    padding: 6px 14px;
    font-size: 11px;
}

.lyrics-popup .retry-btn:hover {
    background-color: rgba(255, 255, 255, 0.16);
}

/* Footer frame */
.lyrics-popup .popup-footer {
    background-color: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 8px;
    padding: 4px 8px;
    margin-top: 6px;
}

.lyrics-popup .footer-source {
    font-size: 11px;
    color: #6c7086;
}

.lyrics-popup .footer-hit-count {
    font-size: 11px;
    color: #a6adc8;
}

.lyrics-popup .footer-btn {
    background: transparent;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 4px;
    color: #cdd6f4;
    font-size: 10px;
    font-weight: 700;
}

.lyrics-popup .footer-btn:hover {
    background: rgba(255, 255, 255, 0.10);
}
```
