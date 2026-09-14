"""`pluto update`: upgrade the package the same way it was installed, then restart the daemon."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from .config import APP_ID

DIST = "pluto-shelf"


def _installed_version() -> str:
    try:
        return version(DIST)
    except PackageNotFoundError:
        return "?"


def _upgrade_command() -> list[str]:
    prefix = str(Path(sys.prefix))
    if "/uv/tools/" in prefix:
        return ["uv", "tool", "upgrade", DIST]
    if "/pipx/venvs/" in prefix:
        return ["pipx", "upgrade", DIST]
    return [sys.executable, "-m", "pip", "install", "--upgrade", DIST]


def _daemon_running() -> bool:
    try:
        import gi

        gi.require_version("Gio", "2.0")
        from gi.repository import Gio, GLib

        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        reply = bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "NameHasOwner",
                              GLib.Variant("(s)", (APP_ID,)), None, Gio.DBusCallFlags.NONE, 2000, None)
        return bool(reply.unpack()[0])
    except Exception:  # noqa: BLE001
        return False


def run() -> int:
    before = _installed_version()
    cmd = _upgrade_command()
    print(f"pluto {before}; running: {' '.join(cmd)}")
    rc = subprocess.call(cmd)
    if rc != 0:
        return rc

    exe = shutil.which("pluto") or os.path.abspath(sys.argv[0])
    after = subprocess.run([exe, "--version"], capture_output=True, text=True).stdout.strip() or "?"
    print(f"now: {after}")

    if _daemon_running():
        subprocess.call([exe, "quit"])
        subprocess.Popen([exe], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        print("daemon restarted")
    return 0
