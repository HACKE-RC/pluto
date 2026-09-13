"""shelf — a drop shelf for Wayland."""

from __future__ import annotations

import ctypes
import sys

__version__ = "0.1.0"


def _preload_layer_shell() -> None:
    # gtk4-layer-shell must be in the global symbol scope before GTK pulls in libwayland-client.
    for name in ("libgtk4-layer-shell.so.0", "libgtk4-layer-shell.so"):
        try:
            ctypes.CDLL(name, mode=ctypes.RTLD_GLOBAL)
            return
        except OSError:
            continue
    sys.stderr.write("shelf: gtk4-layer-shell is not installed (libgtk4-layer-shell.so not found)\n")
    sys.exit(1)


def main() -> int:
    args = sys.argv[1:]
    if args[:1] == ["install"]:
        from .install import run

        return run(args[1:])
    if args[:1] == ["config"]:
        from .config import write_default

        print(write_default())
        return 0
    if args[:1] in (["-h"], ["--help"], ["help"]):
        from .app import USAGE

        print(USAGE, end="")
        return 0
    if args[:1] in (["-V"], ["--version"]):
        print(f"shelf {__version__}")
        return 0

    _preload_layer_shell()
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    gi.require_version("GdkPixbuf", "2.0")
    gi.require_version("Gtk4LayerShell", "1.0")

    from .app import ShelfApp

    return ShelfApp().run(sys.argv)
