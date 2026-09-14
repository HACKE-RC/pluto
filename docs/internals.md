# How it works

Wayland does not let an application see the pointer, or a drag, until it is
over one of the application's own surfaces. That single rule shapes the whole
design.

## The edge strip

The shelf is one layer-shell surface covering the whole screen, mapped all the
time. Most of the time its input region is a 3 px strip on the edge, so it is
invisible and clicks go straight through it. A drag entering that strip is an
ordinary `wl_data_device.enter`. When that happens the daemon adds the panel's
rectangle to the input region and slides the panel in. Only the panel takes
input, so a pinned panel can sit over other windows without stealing their
clicks, and the panel can be dragged anywhere because moving it just moves the
input rectangle. The surface itself never changes size, so the compositor's
drag focus never has to move.

The panel is translated in from the edge in `snapshot()` rather than revealed
with a `Gtk.Revealer`. A revealer re-allocates its child every frame, which
makes labels re-ellipsize while the panel is moving. Translating a laid-out
widget avoids that.

## Things that bit us

These cost real time to find. If you build something similar, start here.

Hyprland picks *move* for every drop. A GTK4 drop target that only accepts
copy is refused without any error. Accept copy and move, then finish the drop
with copy so the source never deletes anything.

Never read a drop's pipe synchronously. The `receive` request only reaches the
compositor when the main loop turns, so a blocking read deadlocks both
applications and leaves the drag stuck until one of them dies.

Hyprland never emits `drop-performed` for the source and reports the selected
action as 0 even after a successful drop. `dnd-finished` is the only success
signal you get.

A completely transparent surface is never rendered by GTK. Without a frame,
GDK never sends the window geometry, and gtk4-layer-shell keeps asking the
compositor for its 200 px placeholder width. Hyprland re-sends `configure`
about ninety times a second forever, the main loop starves, and the panel
looks alive but ignores every click. The root widget has a 1 % background so
the surface always draws. Related: `resizable=False` on the window also breaks
full-height layer surfaces.

Loading gtk4-layer-shell with `ctypes.CDLL(..., RTLD_GLOBAL)` from Python
looks like it works but only intercepts part of libwayland. The daemon re-execs
itself with `LD_PRELOAD` instead.

Keyboard focus on layer surfaces is fiddly. Hyprland grants *on-demand* focus
only when you click the surface, so a panel opened by hotkey away from the
pointer would never see `Ctrl+V`. Deliberate opens (hotkey, shake, tray) therefore
request *exclusive* focus, which Hyprland grants at once; the panel lets go
again on a real pointer leave, on any click outside it (reported by the same
button binds the shake uses), on a key it does not handle, or after four
seconds untouched. Opens triggered by a drag never take the keyboard. Two
traps: switching exclusive to on-demand makes Hyprland drop focus entirely,
and the moment focus arrives GTK receives a bogus pointer enter/leave pair,
so crossings are only trusted when their coordinates fall inside the panel.

## Shake detection

Hyprland has no mouse gesture of its own, emits no pointer events over IPC or
to Lua scripts, and its input-capture protocol is an exclusive grab meant for
KVM software. So the daemon polls `cursorpos` on Hyprland's IPC socket, 40
times a second while the pointer moves and about 7 times a second when it is
still. That costs the compositor roughly 0.3 % of a core. Whether the left
button is down comes from two non-consuming binds that write to
`$XDG_RUNTIME_DIR/pluto-button`, which the daemon watches with inotify.

If you use Hyprland's Lua config manager, `hypr/pluto.lua` does the same
polling inside the compositor with `hl.timer` and `hl.get_cursor_pos()`.

## The tray

The tray icon is `org.kde.StatusNotifierItem` plus `com.canonical.dbusmenu`,
spoken directly over GDBus. No GTK3, no appindicator library. The icon is a
small pixmap drawn with cairo so it does not depend on the icon theme.

## Development

```sh
uv sync
PLUTO_DEBUG=1 uv run pluto         # drag/drop negotiation on stderr
uv run python tools/dnd_probe.py   # see what a source offers on drop
uv build                           # sdist + wheel in dist/
```

Releases: tag `vX.Y.Z` and push the tag; the GitHub workflow builds the
package and publishes `pluto-shelf` to PyPI through trusted publishing (set the
repository up as a trusted publisher on PyPI once, no API token needed).
