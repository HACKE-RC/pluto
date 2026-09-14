# pluto

A place to put things while you're moving them. Drag something to the screen
edge, drop it, go where it needs to go, drag it back out. Works with files,
links, text and images from the browser.

## Why

macOS has Dropover and Yoink for this, Windows has Dropshelf, and I could not find anything on Wayland that
felt right. So this is an invisible 3 px strip on the screen edge that turns
into a shelf when a drag touches it, plus a shake gesture for when the edge is
too far away.

## What it does

The shelf takes files, folders, text, links and images. Files and folders are
kept by reference, so nothing is copied or moved until you drag it somewhere.
Images dragged out of a browser are saved to `~/.local/share/pluto/blobs/`,
so they are still there after you close the tab.

Drag items back out one at a time, select several with `Ctrl` or `Shift`, or
grab the `⋮⋮` handle at the bottom to take everything in one go. Drag-outs copy
by default, so the original file and the shelf item both stay put.

You can drag the panel by its header to put it anywhere on the screen, and pin
it so it stays open while you work in other windows. Clicks outside the panel
still go to whatever is under them.

You can keep more than one shelf. Starting a new one parks the current one
behind the tray icon with everything still on it, and you can switch back any
time. Shelves are saved to disk and come back after a restart.

## Install

System libraries first (GTK 4, gtk4-layer-shell, gobject-introspection, cairo):

```sh
sudo pacman -S gtk4 gtk4-layer-shell gobject-introspection cairo                                # Arch
sudo apt install libgtk-4-dev libgtk4-layer-shell-dev libgirepository-2.0-dev libcairo2-dev      # Debian, Ubuntu
sudo dnf install gtk4-devel gtk4-layer-shell-devel gobject-introspection-devel cairo-devel       # Fedora
```

Then the tool, whichever way you prefer:

```sh
uv tool install pluto-shelf                            # from PyPI
pipx install pluto-shelf                               # same thing with pipx
uv tool install git+https://github.com/HACKE-RC/pluto  # latest from GitHub
```

Then the Hyprland side:

```sh
pluto install
hyprctl reload
pluto
```

`pluto install` writes `~/.config/hypr/pluto.conf` and adds one `source` line
to your `hyprland.conf`. The snippet has the blur rules for the panel, the
`Super+Shift+Z` bind, autostart, and two non-consuming mouse binds the shake
gesture uses to know whether the button is held. For a different key, run
`pluto install --bind 'SUPER, Z'`. Undoing it means deleting `pluto.conf` and
that one line.

## Controls

Open the panel by dragging something onto the right edge of the screen, by
shaking the mouse left and right while holding something, or with
`Super+Shift+Z` (works mid-drag too).

Inside the panel:

| | |
|---|---|
| drag the header | move the panel |
| pin icon | keep it open |
| double-click the name | rename the shelf |
| right-click | menu: switch shelf, new shelf, rename, clear, delete |
| `⋮⋮` in the footer | drag every item at once |
| `delete all` in the footer | empty the shelf |

Keys, while the panel has focus:

| | |
|---|---|
| `Ctrl+V` | paste the clipboard onto the shelf |
| `Ctrl+C` | copy the selected items |
| `Ctrl+A` | select everything |
| `Enter` | open the selected items |
| `Delete` | remove them from the shelf |
| `Esc` | close the panel |

## Command line

```
pluto              start the daemon
pluto toggle       open or close the panel
pluto show         open it
pluto hide         close it
pluto new          start a new shelf and keep the current one in the tray
pluto add ITEM...  put files, folders, URLs or text on the shelf from a script
pluto quit         stop the daemon
pluto update       upgrade to the latest release and restart the daemon
pluto config       write ~/.config/pluto/config.toml with the defaults
```

## Configuration

`pluto config` writes `~/.config/pluto/config.toml`. Every key is optional
and the default colors are catppuccin mocha. Edge, size, animation, drag-out
behaviour and shake sensitivity are all in there; the full list is in
[docs/configuration.md](docs/configuration.md).

## More

- [docs/install.md](docs/install.md): other compositors, undoing the install
- [docs/configuration.md](docs/configuration.md): every option
- [docs/internals.md](docs/internals.md): how it works, and the Wayland and Hyprland traps found on the way

## License

MIT, see [LICENSE](LICENSE).
