# Installing

You need Python 3.12 or newer, GTK 4, gtk4-layer-shell, gobject-introspection
and cairo. PyGObject itself is built from PyPI against those.

On Arch:

```sh
sudo pacman -S gtk4 gtk4-layer-shell gobject-introspection cairo
```

Then, from a clone of this repository:

```sh
uv tool install .      # puts `shelf` in ~/.local/bin
shelf install          # Hyprland rules, keybind, autostart
hyprctl reload
shelf                  # start it now; exec-once starts it on later logins
```

`shelf install` writes `~/.config/hypr/shelf.conf` and adds a single
`source = ~/.config/hypr/shelf.conf` line to your `hyprland.conf`. The snippet
looks like this:

```ini
layerrule = blur on, match:namespace ^shelf$
layerrule = ignore_alpha 0.2, match:namespace ^shelf$
layerrule = no_anim on, match:namespace ^shelf$

bind = SUPER SHIFT, Z, exec, /home/you/.local/bin/shelf toggle
exec-once = /home/you/.local/bin/shelf

bindn = , mouse:272, exec, printf 1 > /run/user/1000/shelf-button
bindrn = , mouse:272, exec, printf 0 > /run/user/1000/shelf-button
```

The two mouse binds tell the daemon whether the left button is held, so a
shake only counts while you are dragging something. They are non-consuming
(`n`): your clicks still go to whatever is under the pointer. Hyprland just
runs a tiny `printf` on every press and release.

Want a different key? `shelf install --bind 'SUPER, Z'`.

To undo, delete `~/.config/hypr/shelf.conf` and the `source` line. Nothing
else on the system is touched. Your shelves live in `~/.local/share/shelf/`.

## Other compositors

Everything except shake detection is plain layer-shell and D-Bus, so the panel
and the tray should work on sway, river, niri and similar. Set `shake = false`
in the config and add your own keybind for `shelf toggle`. You will not get the
blur without a compositor rule for it, so you may want to raise `opacity`.
