from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path

XDG_CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
XDG_DATA = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))

CONFIG_DIR = XDG_CONFIG / "shelf"
CONFIG_FILE = CONFIG_DIR / "config.toml"
DATA_DIR = XDG_DATA / "shelf"
STATE_FILE = DATA_DIR / "state.json"
BLOB_DIR = DATA_DIR / "blobs"

APP_ID = "io.shelf.Shelf"
NAMESPACE = "shelf"


@dataclass
class Palette:
    bg: str = "#1e1e2e"
    surface: str = "#313244"
    fg: str = "#cdd6f4"
    muted: str = "#6c7086"
    dim: str = "#585b70"
    accent: str = "#89b4fa"
    danger: str = "#f38ba8"
    border: str = "#45475a"


@dataclass
class Config:
    edge: str = "right"
    width: int = 320
    max_height: float = 0.7
    strip_width: int = 3
    opacity: float = 0.8
    radius: int = 6
    font: str = "JetBrainsMono Nerd Font, JetBrains Mono, monospace"
    font_size: int = 12
    auto_collapse_ms: int = 1200
    linger_after_drop_ms: int = 2500
    remove_on_drag_out: bool = True
    shake: bool = True
    shake_reversals: int = 3
    shake_travel: int = 25
    shake_window_ms: int = 500
    palette: Palette = field(default_factory=Palette)


DEFAULT_CONFIG_TOML = """\
# shelf configuration — every key is optional; these are the defaults.

edge = "right"            # screen edge the drawer lives on: "right" or "left"
width = 320               # drawer width in logical pixels
max_height = 0.7          # drawer grows with content up to this fraction of the screen
strip_width = 3           # width of the invisible edge strip that catches drags
opacity = 0.8             # panel background alpha (pairs with Hyprland blur)
radius = 6                # corner radius on the screen-facing side
font = "JetBrainsMono Nerd Font, JetBrains Mono, monospace"
font_size = 12
auto_collapse_ms = 1200   # collapse this long after the pointer leaves
linger_after_drop_ms = 2500
remove_on_drag_out = true # dragging an item out removes it (hold Ctrl to keep)
shake = true              # shake the pointer left-right to summon the panel (Hyprland only)
shake_reversals = 3       # direction changes needed within shake_window_ms
shake_travel = 25         # minimum pixels per leg of the shake
shake_window_ms = 500

[palette]
bg      = "#1e1e2e"
surface = "#313244"
fg      = "#cdd6f4"
muted   = "#6c7086"
dim     = "#585b70"
accent  = "#89b4fa"
danger  = "#f38ba8"
border  = "#45475a"
"""


def _apply(obj, data: dict) -> None:
    names = {f.name: f.type for f in fields(obj)}
    for key, value in data.items():
        if key in names and key != "palette":
            setattr(obj, key, value)


def load() -> Config:
    cfg = Config()
    if not CONFIG_FILE.exists():
        return cfg
    with CONFIG_FILE.open("rb") as fh:
        data = tomllib.load(fh)
    _apply(cfg, data)
    _apply(cfg.palette, data.get("palette", {}))
    if cfg.edge not in ("right", "left"):
        cfg.edge = "right"
    cfg.strip_width = max(1, int(cfg.strip_width))
    cfg.opacity = min(1.0, max(0.0, float(cfg.opacity)))
    return cfg


def write_default() -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(DEFAULT_CONFIG_TOML)
    return CONFIG_FILE
