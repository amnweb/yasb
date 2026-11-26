# Wallpapers

`import Yasb`

The images in your wallpaper folders and the one each screen shows, with functions to set a wallpaper, with a
transition if you like, and thumbnails of them. The folders are read on `refresh()`.

Two types:

- [WallpaperLibrary](#wallpaperlibrary): the images, and setting them.
- [WallpaperThumbnail](#wallpaperthumbnail): a small copy of one image, made in the background and kept.

## WallpaperLibrary

### Properties

#### folders : list&lt;string&gt;

Folders to look in, with their subfolders. Empty for the Pictures folder.

Default: `[]`

#### animation : string

The transition played over the desktop before `setWallpaper()` sets a wallpaper, for 0.8 seconds: `circle`,
`slide_top`, `diamond` or `split`. `""` for none. Any other name shows the new wallpaper at once, and sets it 0.8
seconds later. When the transition can't play, the wallpaper is set without it.

Default: `""`

#### images : list `read-only`

The images found by the last `refresh()`, in name order as Windows' `StrCmpLogicalW` sorts them. Each is an
object:

- `path` : string, the image's file.
- `name` : string, its file name without the extension.

Images are PNG, JPEG, GIF, BMP and TIFF files, and WebP on Windows builds that take it as a wallpaper.

#### scanning : bool `read-only`

`true` while the folders are read.

### Functions

#### refresh()

Reads the folders again, and which image each screen shows.

#### currentIndex(screenName: string) : int

Where the wallpaper of the screen with this name is in `images`. `-1` when it isn't one of them.

#### screenCount() : int

How many screens Windows takes a wallpaper for.

#### setWallpaper(path: string) : bool

Sets this image on every screen, after the `animation`. `false` while a transition still plays, and nothing is
set.

#### setWallpaperOn(path: string, screen: int) : bool

Sets this image on one screen, by its place in Windows' own order, from 0 to `screenCount()` − 1, without a
transition. `false` for another number, or while a transition still plays.

#### setRandomWallpaper()

Reads the folders again, then sets a random image on every screen, not the one picked at random last time.

### Signals

#### wallpaperSet(path: string)

Windows has taken this image as the wallpaper.

#### currentChanged()

`currentIndex()` can give another place now.

## WallpaperThumbnail

The image scaled to cover `size` and cropped around its centre. It is made off the GUI thread and kept in
`%LOCALAPPDATA%\YASB\wallpaper_thumbnails`, thumbnails older than 30 days, then the oldest beyond 100 MB, are
deleted after each `refresh()`.

### Properties

#### path : string

The image's file.

Default: `""`

#### size : size

Size of the thumbnail, in pixels.

Default: empty

#### source : url `read-only`

The thumbnail file. Empty until it is made, and when the image can't be read or `size` is empty.

WallpaperThumbnail has no functions or signals.

## Used by

YASB's own Wallpapers widget, listed in [Widgets](./Widgets).
