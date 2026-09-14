from __future__ import annotations

from gi.repository import Gdk, Gtk

from .config import Config


def rgba(hex_color: str, alpha: float = 1.0) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {alpha:.3f})"


def build_css(cfg: Config) -> str:
    p = cfg.palette
    radius = f"{cfg.radius}px"
    border_side = ""
    return f"""
    * {{
        font-family: {cfg.font};
        font-size: {cfg.font_size}px;
        outline-style: none;
        -gtk-icon-style: symbolic;
    }}
    window.pluto {{
        background-color: transparent;
        color: {p.fg};
    }}
    /* Not quite transparent on purpose: GTK skips rendering an empty surface, and without a frame
       GDK never sends the window geometry that gtk4-layer-shell needs to size the layer. */
    .outer {{
        background-color: rgba(0, 0, 0, 0.01);
    }}
    .panel {{
        background-color: {rgba(p.bg, cfg.opacity)};
        border: 1px solid {rgba(p.border, 0.9)};
        {border_side}
        border-radius: {radius};
        transition: border-color 150ms ease-out;
    }}
    .drop-hover .panel {{
        border-color: {rgba(p.accent, 0.9)};
    }}

    .header {{
        padding: 12px 14px 8px 14px;
    }}
    .title {{
        color: {p.fg};
        font-weight: 600;
        letter-spacing: 0.02em;
    }}
    .count {{
        color: {p.muted};
        font-size: {cfg.font_size - 1}px;
        letter-spacing: 0.08em;
    }}
    .close {{
        color: {p.muted};
        background: transparent;
        border: none;
        padding: 2px;
        margin-left: 4px;
        min-width: 18px;
        min-height: 18px;
        border-radius: 3px;
        transition: color 120ms ease-out, background-color 120ms ease-out;
    }}
    .close:hover {{
        color: {p.fg};
        background-color: {rgba(p.fg, 0.08)};
    }}
    .close:checked {{
        color: {p.accent};
        background-color: {rgba(p.accent, 0.14)};
    }}
    .eyebrow {{
        color: {p.muted};
        font-size: {cfg.font_size - 2}px;
        letter-spacing: 0.14em;
    }}

    .empty {{
        margin: 4px 14px 14px 14px;
        padding: 26px 16px;
        border: 1px dashed {rgba(p.dim, 0.9)};
        border-radius: 4px;
        transition: border-color 150ms ease-out, background-color 150ms ease-out;
    }}
    .empty .hint {{
        color: {p.muted};
    }}
    .empty .sub {{
        color: {p.dim};
        font-size: {cfg.font_size - 2}px;
        letter-spacing: 0.1em;
    }}
    .drop-hover .empty {{
        border-color: {rgba(p.accent, 0.9)};
        background-color: {rgba(p.accent, 0.06)};
    }}
    .drop-hover .empty .hint {{
        color: {p.accent};
    }}

    scrolledwindow {{
        background: transparent;
    }}
    scrollbar {{
        background: transparent;
        border: none;
    }}
    scrollbar slider {{
        min-width: 3px;
        min-height: 24px;
        border: none;
        border-radius: 0;
        background-color: {rgba(p.fg, 0.18)};
        margin: 2px 1px;
    }}
    scrollbar slider:hover {{
        background-color: {rgba(p.fg, 0.32)};
    }}

    list.items {{
        background: transparent;
        padding: 0 8px;
    }}
    list.items > row {{
        padding: 0;
        margin: 1px 0;
        border-radius: 4px;
        background: transparent;
        transition: background-color 120ms ease-out, box-shadow 120ms ease-out;
    }}
    list.items > row:hover {{
        background-color: {rgba(p.fg, 0.05)};
    }}
    list.items > row:selected {{
        background-color: {rgba(p.accent, 0.14)};
        box-shadow: inset 2px 0 0 {p.accent};
    }}
    list.items > row.missing .name {{
        color: {p.muted};
        text-decoration: line-through;
    }}
    .item {{
        padding: 6px 8px;
    }}
    .thumb {{
        min-width: 30px;
        min-height: 30px;
        border-radius: 3px;
        background-color: {rgba(p.fg, 0.05)};
        color: {rgba(p.fg, 0.7)};
    }}
    .thumb image.picture {{
        border-radius: 3px;
        -gtk-icon-style: regular;
    }}
    .name {{
        color: {p.fg};
    }}
    .meta {{
        color: {p.muted};
        font-size: {cfg.font_size - 2}px;
        letter-spacing: 0.06em;
    }}
    .remove {{
        color: {p.muted};
        background: transparent;
        border: none;
        padding: 2px;
        min-width: 18px;
        min-height: 18px;
        border-radius: 3px;
        opacity: 0;
        transition: opacity 120ms ease-out, background-color 120ms ease-out;
    }}
    list.items > row:hover .remove, list.items > row:selected .remove {{
        opacity: 1;
    }}
    .remove:hover {{
        color: {p.danger};
        background-color: {rgba(p.danger, 0.12)};
    }}

    .footer {{
        margin: 6px 14px 12px 14px;
        padding: 7px 10px;
        border-radius: 4px;
        border: 1px solid {rgba(p.border, 0.7)};
        color: {p.muted};
        transition: background-color 120ms ease-out, color 120ms ease-out, border-color 120ms ease-out;
    }}
    .footer:hover {{
        background-color: {rgba(p.fg, 0.05)};
        border-color: {rgba(p.fg, 0.2)};
        color: {p.fg};
    }}
    .footer .grip {{
        color: {p.dim};
        letter-spacing: -0.2em;
    }}
    .footer-sep {{
        background-color: {rgba(p.border, 0.9)};
        min-width: 1px;
        min-height: 14px;
        margin: 0 6px;
    }}
    .footer-action {{
        color: {p.muted};
        background: transparent;
        border: none;
        padding: 0 4px;
        min-height: 0;
        font-size: {cfg.font_size - 2}px;
        letter-spacing: 0.06em;
        transition: color 120ms ease-out;
    }}
    .footer-action:hover {{
        color: {p.danger};
    }}

    popover.menu > contents, popover > contents {{
        background-color: {rgba(p.bg, 0.97)};
        border: 1px solid {rgba(p.border, 0.9)};
        border-radius: 6px;
        padding: 4px;
        color: {p.fg};
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
    }}
    popover > arrow {{
        background: transparent;
        border: none;
    }}
    popover.menu modelbutton {{
        padding: 5px 10px;
        border-radius: 3px;
        min-height: 0;
        color: {p.fg};
    }}
    popover.menu modelbutton:hover {{
        background-color: {rgba(p.fg, 0.08)};
    }}
    popover.menu modelbutton.destructive, popover.menu modelbutton.destructive:hover {{
        color: {p.danger};
    }}
    popover.menu separator {{
        background-color: {rgba(p.border, 0.8)};
        margin: 4px 6px;
        min-height: 1px;
    }}
    popover.menu label.heading {{
        color: {p.muted};
        font-size: {cfg.font_size - 2}px;
        letter-spacing: 0.14em;
        padding: 4px 10px;
    }}

    popover.preview > contents {{
        padding: 10px 12px 6px 12px;
    }}
    .preview-text {{
        color: {p.fg};
        font-size: {cfg.font_size - 1}px;
    }}
    .preview-text selection {{
        background-color: {rgba(p.accent, 0.3)};
    }}
    .chip {{
        color: {p.muted};
        background-color: {rgba(p.fg, 0.04)};
        border: 1px solid {rgba(p.border, 0.9)};
        border-radius: 4px;
        padding: 3px 10px;
        min-height: 0;
        font-size: {cfg.font_size - 2}px;
        letter-spacing: 0.06em;
        transition: color 120ms ease-out, background-color 120ms ease-out, border-color 120ms ease-out;
    }}
    .chip:hover {{
        color: {p.fg};
        background-color: {rgba(p.fg, 0.08)};
        border-color: {rgba(p.fg, 0.25)};
    }}
    .chip:active {{
        background-color: {rgba(p.accent, 0.18)};
        border-color: {rgba(p.accent, 0.6)};
    }}
    entry.rename {{
        background-color: {rgba(p.fg, 0.05)};
        border: 1px solid {rgba(p.border, 0.9)};
        border-radius: 3px;
        padding: 4px 8px;
        color: {p.fg};
        caret-color: {p.accent};
        min-height: 0;
    }}
    entry.rename:focus {{
        border-color: {rgba(p.accent, 0.9)};
    }}
    entry.rename selection {{
        background-color: {rgba(p.accent, 0.3)};
        color: {p.fg};
    }}
    """


def install(cfg: Config) -> None:
    provider = Gtk.CssProvider()
    provider.load_from_string(build_css(cfg))
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_USER
    )
