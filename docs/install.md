# Installing

You need Python 3.12 or newer, GTK 4, gtk4-layer-shell, gobject-introspection
and cairo. PyGObject itself is built from PyPI against those.

On Arch:

```sh
sudo pacman -S gtk4 gtk4-layer-shell gobject-introspection cairo
```

Then, from a clone of this repository:

```sh
uv tool install .      # puts `pluto` in ~/.local/bin
pluto install          # Hyprland rules, keybind, autostart
hyprctl reload
shelf                  # start it now; exec-once starts it on later logins
```

`pluto install` writes `~/.config/hypr/pluto.conf` and adds a single
`source = ~/.config/hypr/pluto.conf` line to your `hyprland.conf`. The snippet
looks like this:

```ini
layerrule = blur on, match:namespace ^pluto$
layerrule = ignore_alpha 0.2, match:namespace ^pluto$
layerrule = no_anim on, match:namespace ^pluto$

bind = SUPER SHIFT, Z, exec, /home/you/.local/bin/pluto toggle
exec-once = /home/you/.local/bin/pluto

bindn = , mouse:272, exec, printf 1 > /run/user/1000/pluto-button
bindrn = , mouse:272, exec, printf 0 > /run/user/1000/pluto-button
```

The two mouse binds tell the daemon whether the left button is held, so a
shake only counts while you are dragging something. They are non-consuming
(`n`): your clicks still go to whatever is under the pointer. Hyprland just
runs a tiny `printf` on every press and release.

Want a different key? `pluto install --bind 'SUPER, Z'`.

To undo, delete `~/.config/hypr/pluto.conf` and the `source` line. Nothing
else on the system is touched. Your shelves live in `~/.local/share/pluto/`.

## Other compositors

Everything except shake detection is plain layer-shell and D-Bus, so the panel
and the tray should work on sway, river, niri and similar. Set `shake = false`
in the config and add your own keybind for `pluto toggle`. You will not get the
blur without a compositor rule for it, so you may want to raise `opacity`.
