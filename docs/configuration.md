# Configuration

`shelf config` writes `~/.config/shelf/config.toml` with the defaults. Every
key is optional; leave out what you do not want to change. The daemon reads the
file at startup, so restart it (`shelf quit && shelf`) after editing.

```toml
edge = "right"            # "right" or "left"
width = 320               # logical pixels
max_height = 0.7          # of the screen height; the list scrolls past this
strip_width = 3           # the invisible edge strip that catches drags
opacity = 0.8             # panel background alpha; pairs with the blur rule
radius = 6                # corner radius on the side facing the screen
font = "JetBrainsMono Nerd Font, JetBrains Mono, monospace"
font_size = 12
slide_ms = 180            # open/close animation

auto_collapse_ms = 1200   # close this long after the pointer leaves
linger_after_drop_ms = 2500

drag_out_action = "copy"  # "copy": targets always copy
                          # "move": the target may move the file; the shelf item then points nowhere
remove_on_drag_out = false # true: items leave the shelf after a drag-out (Ctrl-drag keeps them)

shake = true              # shake to summon (Hyprland only)
shake_requires_grab = true # only while the left button is held
shake_reversals = 4       # direction changes needed
shake_travel = 40         # minimum pixels per leg
shake_window_ms = 600     # the whole shake has to fit in this

[palette]                 # defaults are catppuccin mocha
bg      = "#1e1e2e"
surface = "#313244"
fg      = "#cdd6f4"
muted   = "#6c7086"
dim     = "#585b70"
accent  = "#89b4fa"
danger  = "#f38ba8"
border  = "#45475a"
```

A few notes:

The shake defaults are deliberately on the stiff side. If it never fires for
you, drop `shake_reversals` to 3. If it fires when you did not mean it, raise
`shake_travel`.

`drag_out_action = "move"` offers the move action too. Hyprland picks move
whenever it is offered, so Thunar and friends will move the file, and the item
on the shelf will show as MISSING afterwards. Copy is the safer default.

`SHELF_DEBUG=1 shelf` logs drag and drop negotiation to stderr, which is the
first thing to look at when a drop does nothing.
