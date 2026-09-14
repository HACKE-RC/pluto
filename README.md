# shelf

A drop shelf for Wayland. Drag something to the edge of the screen, drop it on
the shelf that slides out, go find where it needs to go, then drag it back out.
Works with files, folders, text, links and images from the browser.

Built for Hyprland. Runs on any compositor that has `wlr-layer-shell` and a
tray that speaks StatusNotifierItem (waybar, quickshell and the like).

![shelf](docs/shelf.png)

## What it does

The shelf is invisible until you need it: a 3 px strip on the right edge of the
screen. Drag anything onto that strip and a panel slides in at your pointer.
Drop, and the item is parked there. Files and folders are kept by reference,
so nothing is copied or moved until you drag it somewhere. Images dragged out
of a browser are saved locally, so they survive closing the tab.

You can keep several shelves. Starting a new one puts the current one behind
the tray icon with everything still on it, and you can switch back whenever.
Shelves are saved to disk and come back after a restart.

## Usage

Open the panel in one of three ways:

- drag something to the right edge of the screen
- shake the mouse left and right while holding something
- press `Super+Shift+Z` (this also works mid-drag)

Drag items out one at a time, or select several with `Ctrl` or `Shift` and
drag them together. The "drag all" handle at the bottom takes everything at
once. Drag-outs copy by default, so the original file and the shelf item both
stay where they are.

Keys while the panel is open:

| key | |
|---|---|
| `Ctrl+V` | paste the clipboard onto the shelf |
| `Ctrl+C` | copy the selected items |
| `Enter` | open the selected items |
| `Delete` | remove them from the shelf |
| `Esc` | close the panel |

Right-click for the menu: rename, new shelf, switch shelf, clear, delete.
Double-click the shelf name to rename it. The `x` in the corner closes the panel.

From the command line:

```
shelf              start the daemon
shelf toggle       open or close the panel
shelf new          start a new shelf, keep the current one in the tray
shelf add FILE...  put files, folders, URLs or text on the shelf
shelf quit         stop the daemon
```

## More

- [Installing](docs/install.md)
- [Configuration](docs/configuration.md)
- [How it works, and what Wayland and Hyprland make awkward](docs/internals.md)

## License

MIT, see [LICENSE](LICENSE).
