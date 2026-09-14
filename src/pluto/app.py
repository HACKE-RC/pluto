from __future__ import annotations

import os

from gi.repository import Gio, GLib, Gtk

from . import config, ingest, style
from .config import APP_ID
from .drawer import Drawer
from .store import Item, Store
from .shake import ShakeDetector
from .tray import Tray

VERBS = ("toggle", "show", "hide", "new", "quit")
USAGE = """usage: pluto [command]

  (none)        start the daemon (or report that it is already running)
  toggle        open / close the drawer
  show          open the drawer
  hide          close the drawer
  new           start a new shelf (the current one is kept in the tray)
  add ITEM...   put files, folders, URLs or text on the active shelf
  quit          stop the daemon
  install       write Hyprland rules, keybind and autostart
  config        create ~/.config/pluto/config.toml with the defaults
"""


class ShelfApp(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.cfg: config.Config | None = None
        self.store: Store | None = None
        self.drawer: Drawer | None = None
        self.tray: Tray | None = None
        self.shake: ShakeDetector | None = None

    def do_startup(self) -> None:
        Gtk.Application.do_startup(self)
        self.cfg = config.load()
        style.install(self.cfg)
        self.store = Store()
        self.drawer = Drawer(self, self.store, self.cfg)
        self.tray = Tray(
            self.store,
            on_activate=self.drawer.toggle,
            on_select_shelf=self._select_shelf,
            on_new=self._new_shelf,
            on_clear=self.store.clear,
            on_delete=lambda: self.store.delete_shelf(self.store.active_id),
            on_quit=self.quit_safely,
            icon_color=self.cfg.palette.fg,
        )
        for verb in VERBS:
            action = Gio.SimpleAction.new(verb, None)
            action.connect("activate", self._on_verb, verb)
            self.add_action(action)
        self.drawer.present()
        if self.cfg.shake:
            self.shake = ShakeDetector(self._on_shake, window_ms=self.cfg.shake_window_ms, travel=self.cfg.shake_travel, reversals=self.cfg.shake_reversals, requires_grab=self.cfg.shake_requires_grab)
            self.shake.on_button = self.drawer.on_global_button
            self.shake.on_pointer = self.drawer.on_global_pointer
            self.shake.start()

    def _on_shake(self, x: float, y: float) -> bool:
        if not self.drawer.expanded:
            self.drawer.expand()
            self.drawer._schedule_collapse(3500)
        return False

    def do_activate(self) -> None:
        pass

    def do_command_line(self, cmdline: Gio.ApplicationCommandLine) -> int:
        args = cmdline.get_arguments()[1:]
        if not args:
            if cmdline.get_is_remote():
                cmdline.printerr_literal("pluto: already running\n")
            return 0
        verb = args[0]
        if verb in VERBS:
            self.activate_action(verb, None)
            return 0
        if verb == "add":
            cwd = cmdline.get_cwd() or "/"
            items = [self._item_from_arg(arg, cwd) for arg in args[1:]]
            self.drawer.add_items(items)
            self.drawer.expand()
            self.drawer._schedule_collapse(4000)
            return 0
        cmdline.printerr_literal(USAGE)
        return 2

    @staticmethod
    def _item_from_arg(arg: str, cwd: str) -> Item:
        if ingest.URL_RE.match(arg):
            return Item.link(arg)
        path = arg if os.path.isabs(arg) else os.path.join(cwd, arg)
        if os.path.exists(path):
            return Item.file(os.path.normpath(path))
        return Item.text_snippet(arg)

    def _on_verb(self, action, param, verb: str) -> None:
        if verb == "toggle":
            self.drawer.toggle()
        elif verb == "show":
            self.drawer.expand()
        elif verb == "hide":
            self.drawer.collapse(force=True)
        elif verb == "new":
            self._new_shelf()
        elif verb == "quit":
            self.quit_safely()

    def _select_shelf(self, shelf_id: str) -> None:
        self.store.set_active(shelf_id)
        self.drawer.expand()
        self.drawer._schedule_collapse(4000)

    def _new_shelf(self) -> None:
        self.store.new_shelf()
        self.drawer.expand()
        self.drawer._schedule_collapse(4000)

    def quit_safely(self) -> None:
        # Quitting mid-drag leaves the compositor's drag grab dangling; wait for it to end.
        if self.drawer.dnd_active or self.drawer.drag_out_active:
            GLib.timeout_add(500, lambda: (self.quit_safely(), False)[1])
            return
        self.store.save_now()
        self.quit()
