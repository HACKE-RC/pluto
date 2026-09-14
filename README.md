# shelf

A drop shelf for Wayland. Drag anything to the edge of the screen — a shelf slides
out, takes it, and keeps it until you drag it back out somewhere else. Files,
folders, text, links, images straight from the browser.

Built for Hyprland. Works on any compositor with `wlr-layer-shell` and a
StatusNotifier tray (waybar, quickshell, …).

![shelf](docs/shelf.png)

## Why

On a tiling compositor, moving something between two windows means juggling
workspaces while holding the mouse button. macOS has Dropover, Windows has
Dropshelf; Wayland had nothing native. `shelf` is that missing piece: an
invisible 3 px strip on the screen edge that turns into a panel the moment a
drag touches it, and stays out of the way otherwise.

## How it feels

- **Drag to the right edge.** The panel slides in at your pointer. Drop.
- **`Super+Shift+Z`** toggles the panel at the pointer — it works mid-drag too.
- **Shake the pointer** left-right while dragging something (Hyprland only) and
  the panel opens at the pointer, like Dropover. It closes again after a few
  seconds if nothing lands on it.
- **Drag things back out** one by one, multi-select with `Ctrl`/`Shift`-click, or
  grab the *drag all* handle at the bottom. Drag-outs are **copies** by default,
  so the originals and the shelf items stay put (`drag_out_action = "move"`
  lets the target move files instead; `remove_on_drag_out = true` makes items
  leave the shelf after a drag-out, `Ctrl`-drag keeps them either way).
- **Keep a shelf in the tray.** *New shelf* stashes the current one — with
  everything on it — behind the tray icon. Switch back any time; shelves survive
  restarts.
- `Ctrl+V` pastes the clipboard onto the shelf · `Ctrl+C` copies the selection ·
  `Enter` opens · `Delete` removes · `Esc` closes · right-click for the menu
  (rename, new shelf, switch, clear, delete).
- Files are held **by reference** — nothing is copied or moved until you drag it
  out. Images dragged from a browser are captured into
  `~/.local/share/shelf/blobs/`, so they stay even after the tab is gone.

## Install

Requirements: Python ≥ 3.12, GTK 4, gtk4-layer-shell, gobject-introspection,
cairo (PyGObject is built from PyPI against them).

```sh
# Arch
sudo pacman -S gtk4 gtk4-layer-shell gobject-introspection cairo

# from a clone
uv tool install .          # → ~/.local/bin/shelf
shelf install              # Hyprland rules + keybind + autostart
hyprctl reload
shelf                      # start it now (exec-once handles future logins)
```

`shelf install` writes `~/.config/hypr/shelf.conf` and adds one `source =` line
to `hyprland.conf`:

```ini
layerrule = blur on, match:namespace ^shelf$
layerrule = ignore_alpha 0.2, match:namespace ^shelf$
layerrule = no_anim on, match:namespace ^shelf$

bind = SUPER SHIFT, Z, exec, /home/you/.local/bin/shelf toggle
exec-once = /home/you/.local/bin/shelf

# left-button state so a shake only counts while something is grabbed
bindn = , mouse:272, exec, printf 1 > /run/user/1000/shelf-button
bindrn = , mouse:272, exec, printf 0 > /run/user/1000/shelf-button
```

The two mouse binds are *non-consuming* (`n`): clicks still reach whatever is
under the pointer; Hyprland just runs a 1 ms `printf` on press and release so
`shelf` knows whether the button is held.

Use `shelf install --bind 'SUPER, Z'` for a different key. Nothing else is
touched; delete `shelf.conf` and the `source` line to undo.

## CLI

| command | |
|---|---|
| `shelf` | start the daemon |
| `shelf toggle` / `show` / `hide` | control the panel (use from keybinds) |
| `shelf new` | start a new shelf, keep the current one in the tray |
| `shelf add ITEM…` | put files, folders, URLs or text on the shelf from a script |
| `shelf quit` | stop the daemon (waits for any drag in progress) |
| `shelf config` | write `~/.config/shelf/config.toml` with the defaults |

## Configuration

`~/.config/shelf/config.toml` — every key optional:

```toml
edge = "right"            # "right" or "left"
width = 320               # logical pixels
max_height = 0.7          # of the screen; the list scrolls beyond that
strip_width = 3           # the invisible edge trigger
opacity = 0.8             # panel alpha; pairs with the blur rule
radius = 6
font = "JetBrainsMono Nerd Font, JetBrains Mono, monospace"
font_size = 12
auto_collapse_ms = 1200   # after the pointer leaves
linger_after_drop_ms = 2500
remove_on_drag_out = false # true: dragging out removes the item (Ctrl-drag keeps it)
slide_ms = 180            # open/close animation
drag_out_action = "copy"  # or "move" (target decides; Hyprland prefers move)
shake = true              # shake-to-summon (Hyprland IPC); tune with
shake_requires_grab = true # only while the left button is held
shake_reversals = 4       #   reversals / travel (px per leg) / window_ms
shake_travel = 40
shake_window_ms = 600

[palette]                 # defaults are catppuccin mocha
bg = "#1e1e2e"  surface = "#313244"  fg = "#cdd6f4"  muted = "#6c7086"
dim = "#585b70" accent = "#89b4fa"   danger = "#f38ba8" border = "#45475a"
```

## How it works

Wayland gives a client no way to see a drag — or the pointer — until it is over
one of its own surfaces. `shelf` keeps one
full-height layer-shell surface mapped on the screen edge at all times, with its
**input region** shrunk to a 3 px strip. A drag entering the strip is a normal
`wl_data_device.enter`; the panel then widens the input region and slides in —
the surface never resizes mid-drag, so the compositor's drag focus never moves.

Other things learned along the way, in case you build something similar:

- Hyprland pre-selects *move* for every drop. A GTK4 drop target that only
  accepts *copy* is silently refused; accept both, then always `finish` with
  copy so the source never deletes anything.
- Never read a drop's pipe synchronously: the `receive` request is only flushed
  when the main loop turns, so a blocking read deadlocks both apps.
- The tray is `org.kde.StatusNotifierItem` + `com.canonical.dbusmenu` spoken
  directly over GDBus — no GTK3, no appindicator.
- Blur comes from the compositor (`layerrule = blur`); `ignore_alpha` keeps the
  transparent parts of the surface from being blurred.
- Shake detection polls `cursorpos` on Hyprland's IPC socket at 40 Hz from a
  thread (backing off while the pointer is still); the button state comes from
  two non-consuming Hyprland binds writing to `$XDG_RUNTIME_DIR/shelf-button`,
  watched with inotify. These are the only compositor-specific pieces;
  everything else is plain layer-shell and works elsewhere with `shake = false`. Hyprland has no mouse-gesture option and emits no pointer
  events over IPC or to Lua, and `hyprland_input_capture_v1` is an exclusive
  grab, so polling is the only client-side option. If you run the Lua config
  manager, `hypr/shelf.lua` does the same polling inside the compositor
  (`hl.timer` + `hl.get_cursor_pos()`); use it with `shake = false`.
- A fully transparent layer surface makes GTK skip rendering, and without a
  frame GDK never sends the window geometry gtk4-layer-shell sizes the surface
  from; the root widget keeps a 1 % background so the surface always draws.

## Development

```sh
uv sync
SHELF_DEBUG=1 uv run shelf      # logs drag/drop negotiation to stderr
uv run python tools/dnd_probe.py  # inspect what a source offers on drop
```

## License

MIT
