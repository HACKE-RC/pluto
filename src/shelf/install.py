from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from .config import BUTTON_FILE, NAMESPACE, XDG_CONFIG, write_default

HYPR_DIR = XDG_CONFIG / "hypr"
HYPR_MAIN = HYPR_DIR / "hyprland.conf"
HYPR_SNIPPET = HYPR_DIR / "shelf.conf"
SOURCE_LINE = "source = ~/.config/hypr/shelf.conf"


def snippet(exe: str, bind: str) -> str:
    return f"""\
# shelf — drop shelf for Wayland. Managed by `shelf install`; edit freely.
layerrule = blur on, match:namespace ^{NAMESPACE}$
layerrule = ignore_alpha 0.2, match:namespace ^{NAMESPACE}$
layerrule = no_anim on, match:namespace ^{NAMESPACE}$

bind = {bind}, exec, {exe} toggle
exec-once = {exe}

# Left-button state so a shake only counts while something is grabbed.
# Non-consuming: clicks still reach the app under the pointer.
bindn = , mouse:272, exec, printf 1 > {BUTTON_FILE}
bindrn = , mouse:272, exec, printf 0 > {BUTTON_FILE}
"""


def run(args: list[str]) -> int:
    bind = "SUPER SHIFT, Z"
    if args[:1] == ["--bind"] and len(args) > 1:
        bind = args[1]
    elif args:
        print("usage: shelf install [--bind 'SUPER SHIFT, Z']", file=sys.stderr)
        return 2

    exe = shutil.which("shelf") or os.path.abspath(sys.argv[0])
    HYPR_DIR.mkdir(parents=True, exist_ok=True)
    HYPR_SNIPPET.write_text(snippet(exe, bind))
    print(f"wrote {HYPR_SNIPPET}")

    main_text = HYPR_MAIN.read_text() if HYPR_MAIN.exists() else ""
    if SOURCE_LINE not in main_text:
        with HYPR_MAIN.open("a") as fh:
            fh.write(("" if main_text.endswith("\n") or not main_text else "\n") + f"\n{SOURCE_LINE}\n")
        print(f"added '{SOURCE_LINE}' to {HYPR_MAIN}")
    else:
        print(f"{HYPR_MAIN} already sources the snippet")

    print(f"config: {write_default()}")
    print("\nnext: hyprctl reload   (then drag something to the screen edge, or press", bind.replace(", ", "+") + ")")
    return 0
