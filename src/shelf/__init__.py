"""shelf — a drop shelf for Wayland."""

from __future__ import annotations

import sys

__version__ = "0.1.0"


def _ensure_layer_shell_preloaded() -> None:
    """gtk4-layer-shell must interpose libwayland-client before GTK loads it. dlopen(RTLD_GLOBAL) from Python is not
    reliable for that (some hooks are missed and the layer surface ends up in a resize loop), so re-exec with LD_PRELOAD."""
    import ctypes.util
    import os

    if os.environ.get("SHELF_PRELOADED") == "1":
        return
    lib = ctypes.util.find_library("gtk4-layer-shell")
    if not lib:
        sys.stderr.write("shelf: gtk4-layer-shell is not installed (libgtk4-layer-shell.so not found)\n")
        sys.exit(1)
    env = dict(os.environ)
    env["LD_PRELOAD"] = " ".join(filter(None, [lib, env.get("LD_PRELOAD")]))
    env["SHELF_PRELOADED"] = "1"
    os.execve(sys.executable, [sys.executable, *sys.argv], env)


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

    _ensure_layer_shell_preloaded()
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    gi.require_version("GdkPixbuf", "2.0")
    gi.require_version("Gtk4LayerShell", "1.0")

    from .app import ShelfApp

    return ShelfApp().run(sys.argv)
