from __future__ import annotations

import json
import os
import sys
from urllib.parse import urlsplit

import cairo
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, GObject, Graphene, Gtk, Gtk4LayerShell as LS

from . import ingest
from .config import NAMESPACE, Config
from .store import FILE, IMAGE, TEXT, URL, Item, Store

THUMB = 30
EDGE_PAD = 12
DEBUG = bool(os.environ.get("PLUTO_DEBUG"))


def log(*parts) -> None:
    if DEBUG:
        print("pluto:", *parts, file=sys.stderr, flush=True)


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}".replace(".0 ", " ")
        n /= 1024
    return f"{n:.1f} TB"


def meta_for(item: Item) -> str:
    if item.missing:
        return "MISSING"
    if item.kind in (FILE, IMAGE):
        path = item.path or ""
        if os.path.isdir(path):
            try:
                n = len(os.listdir(path))
                return f"FOLDER · {n} ITEM" + ("" if n == 1 else "S")
            except OSError:
                return "FOLDER"
        ext = os.path.splitext(path)[1].lstrip(".").upper() or "FILE"
        try:
            return f"{ext} · {human_size(os.path.getsize(path))}"
        except OSError:
            return ext
    if item.kind == URL:
        return f"LINK · {urlsplit(item.url or '').netloc}"
    text = item.text or ""
    lines = text.count("\n") + 1
    return f"TEXT · {lines} LINES" if lines > 1 else f"TEXT · {len(text)} CHARS"


def content_for(items: list[Item]) -> Gdk.ContentProvider | None:
    files = [Gio.File.new_for_path(i.path) for i in items if i.kind in (FILE, IMAGE) and i.path and not i.missing]
    urls = [i for i in items if i.kind == URL and i.url]
    texts = [i.text for i in items if i.kind == TEXT and i.text]
    providers: list[Gdk.ContentProvider] = []
    images = [i for i in items if i.path and not i.missing and (i.kind == IMAGE or ingest.content_type(i).startswith("image/"))]
    if len(images) == 1 and len(items) == 1:
        try:
            providers.append(Gdk.ContentProvider.new_for_value(Gdk.Texture.new_from_filename(images[0].path)))
        except GLib.Error:
            pass
    if files:
        value = GObject.Value()
        value.init(Gdk.FileList)
        value.set_boxed(Gdk.FileList.new_from_list(files))
        providers.append(Gdk.ContentProvider.new_for_value(value))
        uri_list = "".join(f.get_uri() + "\r\n" for f in files)
        providers.append(Gdk.ContentProvider.new_for_bytes("text/uri-list", GLib.Bytes.new(uri_list.encode())))
    elif urls:
        providers.append(Gdk.ContentProvider.new_for_bytes("text/uri-list", GLib.Bytes.new("".join(u.url + "\r\n" for u in urls).encode())))
        moz = "\n".join(f"{u.url}\n{u.title or u.url}" for u in urls)
        providers.append(Gdk.ContentProvider.new_for_bytes("text/x-moz-url", GLib.Bytes.new(moz.encode("utf-16-le"))))
        providers.append(Gdk.ContentProvider.new_for_value("\n".join(u.url for u in urls)))
    if texts and not files:
        providers.append(Gdk.ContentProvider.new_for_value("\n\n".join(texts)))
    if not providers:
        return None
    return providers[0] if len(providers) == 1 else Gdk.ContentProvider.new_union(providers)


class ItemRow(Gtk.ListBoxRow):
    def __init__(self, item: Item, drawer: "Drawer"):
        super().__init__()
        self.item = item
        self.drawer = drawer
        if item.missing:
            self.add_css_class("missing")

        box = Gtk.Box(spacing=10)
        box.add_css_class("item")
        self.set_child(box)

        self.thumb = Gtk.Box(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER, hexpand=False)
        self.thumb.add_css_class("thumb")
        self.thumb.set_size_request(THUMB, THUMB)
        self.thumb.set_overflow(Gtk.Overflow.HIDDEN)
        box.append(self.thumb)

        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, valign=Gtk.Align.CENTER, spacing=1)
        name = Gtk.Label(label=item.name, xalign=0, ellipsize=3, single_line_mode=True)
        name.add_css_class("name")
        meta = Gtk.Label(label=meta_for(item), xalign=0, ellipsize=3, single_line_mode=True)
        meta.add_css_class("meta")
        labels.append(name)
        labels.append(meta)
        box.append(labels)

        remove = Gtk.Button(icon_name="window-close-symbolic", valign=Gtk.Align.CENTER, has_frame=False, tooltip_text="Remove")
        remove.add_css_class("remove")
        remove.connect("clicked", lambda *_: drawer.remove_items({item.id}))
        box.append(remove)

        self._set_icon()
        if item.kind == IMAGE or (item.kind == FILE and ingest.content_type(item).startswith("image/")):
            self._load_thumbnail()

        drag = Gtk.DragSource(actions=drawer.drag_out_actions())
        drag.connect("prepare", self._on_prepare)
        drag.connect("drag-begin", self._on_drag_begin)
        drag.connect("drag-end", lambda *_: drawer.on_drag_out_end())
        drag.connect("drag-cancel", lambda *_: False)
        self.add_controller(drag)

    def _set_icon(self) -> None:
        if self.item.kind == URL:
            gicon = Gio.ThemedIcon.new_from_names(["web-browser-symbolic", "insert-link-symbolic", "emblem-symbolic-link"])
        elif self.item.kind == TEXT:
            gicon = Gio.ThemedIcon.new_with_default_fallbacks("text-x-generic-symbolic")
        elif os.path.isdir(self.item.path or ""):
            gicon = Gio.ThemedIcon.new_with_default_fallbacks("folder-symbolic")
        else:
            gicon = Gio.content_type_get_symbolic_icon(ingest.content_type(self.item))
        image = Gtk.Image.new_from_gicon(gicon)
        image.set_pixel_size(15)
        self.thumb.append(image)

    def _load_thumbnail(self) -> None:
        gfile = Gio.File.new_for_path(self.item.path)
        scale = self.get_scale_factor() or 1
        px = THUMB * scale

        def on_pixbuf(_src, res):
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_stream_finish(res)
            except GLib.Error:
                return
            w, h = pixbuf.get_width(), pixbuf.get_height()
            side = min(w, h)
            square = pixbuf.new_subpixbuf((w - side) // 2, (h - side) // 2, side, side)
            image = Gtk.Image.new_from_paintable(Gdk.Texture.new_for_pixbuf(square))
            image.set_pixel_size(THUMB)
            image.add_css_class("picture")
            child = self.thumb.get_first_child()
            if child:
                self.thumb.remove(child)
            self.thumb.append(image)

        def on_stream(src, res):
            try:
                stream = src.read_finish(res)
            except GLib.Error:
                return
            # Scale so the shorter side is the thumbnail size, then crop the centre square.
            GdkPixbuf.Pixbuf.new_from_stream_at_scale_async(stream, px * 4, px, True, None, on_pixbuf)

        gfile.read_async(GLib.PRIORITY_LOW, None, on_stream)

    # ── drag out ─────────────────────────────────────────────────
    def _on_prepare(self, source: Gtk.DragSource, x: float, y: float):
        if not self.is_selected():
            self.drawer.listbox.unselect_all()
            self.drawer.listbox.select_row(self)
        items = self.drawer.selected_items()
        keep = bool(source.get_current_event_state() & Gdk.ModifierType.CONTROL_MASK)
        return self.drawer.begin_drag_out(items, keep, x, y, self)

    def _on_drag_begin(self, source: Gtk.DragSource, drag: Gdk.Drag) -> None:
        paintable = Gtk.WidgetPaintable.new(self)
        source.set_icon(paintable, int(self.drawer.drag_hot_x), int(self.drawer.drag_hot_y))
        self.drawer.attach_drag(drag)


class Slide(Gtk.Widget):
    """Slides its child in from the screen edge by translating it in snapshot(), so the content is laid
    out once and never reflows mid-animation (a Gtk.Revealer slide re-allocates every frame)."""

    def __init__(self, from_right: bool, duration_ms: int = 260):
        super().__init__()
        self.set_layout_manager(Gtk.BinLayout())
        self.set_overflow(Gtk.Overflow.HIDDEN)
        self.from_right = from_right
        self.duration = duration_ms * 1000
        self.child: Gtk.Widget | None = None
        self.progress = 0.0
        self.target = 0.0
        self._start_progress = 0.0
        self._start_time: int | None = None
        self._tick = 0

    def set_child(self, child: Gtk.Widget) -> None:
        self.child = child
        child.set_parent(self)
        child.set_child_visible(False)

    def do_dispose(self):
        if self.child:
            self.child.unparent()
            self.child = None
        Gtk.Widget.do_dispose(self)

    def set_reveal_child(self, reveal: bool) -> None:
        self.target = 1.0 if reveal else 0.0
        if reveal and self.child:
            self.child.set_child_visible(True)
        self._start_progress = self.progress
        self._start_time = None
        if not self._tick:
            self._tick = self.add_tick_callback(self._on_tick)

    def _on_tick(self, widget, clock) -> bool:
        now = clock.get_frame_time()
        if self._start_time is None:
            self._start_time = now
        t = min(1.0, (now - self._start_time) / self.duration)
        eased = 1 - (1 - t) ** 5
        self.progress = self._start_progress + (self.target - self._start_progress) * eased
        self.queue_draw()
        if t >= 1.0:
            self.progress = self.target
            if self.target == 0.0 and self.child:
                self.child.set_child_visible(False)
            self._tick = 0
            return False
        return True

    def do_snapshot(self, snapshot: Gtk.Snapshot) -> None:
        if not self.child or self.progress <= 0.0:
            return
        offset = (1.0 - self.progress) * 28.0 * (1 if self.from_right else -1)
        snapshot.save()
        snapshot.translate(Graphene.Point().init(offset, 0))
        snapshot.push_opacity(min(1.0, 0.25 + self.progress))
        self.snapshot_child(self.child, snapshot)
        snapshot.pop()
        snapshot.restore()


class Drawer(Gtk.Window):
    def __init__(self, app: Gtk.Application, store: Store, cfg: Config):
        super().__init__(application=app, title="Pluto", decorated=False)
        self.store = store
        self.cfg = cfg
        self.expanded = False
        self.dnd_active = False
        self.drag_out_items: list[Item] = []
        self.drag_out_keep = False
        self.drag_out_active = False
        self.drag_hot_x = self.drag_hot_y = 0.0
        self.popover_open = False
        self._collapse_source = 0
        self._last_dnd_motion = 0
        self._keyboard = False
        self.add_css_class("pluto")

        left = cfg.edge == "left"
        self.pinned = store.pinned
        self._panel_left: int | None = None
        self._panel_top: int | None = None
        LS.init_for_window(self)
        LS.set_namespace(self, NAMESPACE)
        LS.set_layer(self, LS.Layer.OVERLAY)
        for edge in (LS.Edge.LEFT, LS.Edge.RIGHT, LS.Edge.TOP, LS.Edge.BOTTOM):
            LS.set_anchor(self, edge, True)
        LS.set_exclusive_zone(self, 0)
        LS.set_keyboard_mode(self, LS.KeyboardMode.NONE)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, vexpand=True, hexpand=True)
        outer.add_css_class("outer")
        self.set_child(outer)
        self.revealer = Slide(from_right=not left, duration_ms=cfg.slide_ms)
        self.revealer.set_halign(Gtk.Align.START)
        self.revealer.set_valign(Gtk.Align.START)
        outer.append(self.revealer)
        self.panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.panel.add_css_class("panel")
        self.panel.set_size_request(cfg.width, -1)
        self.revealer.set_child(self.panel)

        self._build_panel()
        self._build_actions()
        self._install_controllers()
        self.store.connect("changed", lambda *_: self.refresh())
        self.connect("map", self._on_map)
        self.refresh()

    # ── construction ─────────────────────────────────────────────
    def _build_panel(self) -> None:
        header = Gtk.Box(spacing=8)
        header.add_css_class("header")
        self.title = Gtk.Label(xalign=0, hexpand=True, ellipsize=3)
        self.title.add_css_class("title")
        self.count = Gtk.Label(xalign=1)
        self.count.add_css_class("count")
        header.append(self.title)
        header.append(self.count)
        self.pin_button = Gtk.ToggleButton(icon_name="view-pin-symbolic", valign=Gtk.Align.CENTER, has_frame=False, tooltip_text="Pin: stay open")
        self.pin_button.add_css_class("close")
        self.pin_button.set_active(self.pinned)
        self.pin_button.connect("toggled", self._on_pin_toggled)
        header.append(self.pin_button)
        close = Gtk.Button(icon_name="window-close-symbolic", valign=Gtk.Align.CENTER, has_frame=False, tooltip_text="Close (Esc)")
        close.add_css_class("close")
        close.connect("clicked", lambda *_: self.collapse(force=True))
        header.append(close)
        self.panel.append(header)
        title_click = Gtk.GestureClick(button=1)
        title_click.connect("pressed", lambda g, n, x, y: self.rename_shelf() if n == 2 else None)
        self.title.add_controller(title_click)
        header.set_cursor_from_name("grab")
        move = Gtk.GestureDrag(button=1)
        move.connect("drag-begin", self._on_move_begin)
        move.connect("drag-update", self._on_move_update)
        move.connect("drag-end", self._on_move_end)
        header.add_controller(move)

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, transition_duration=150, vhomogeneous=False)
        self.panel.append(self.stack)

        empty = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, valign=Gtk.Align.CENTER)
        empty.add_css_class("empty")
        hint = Gtk.Label(label="drop anything here")
        hint.add_css_class("hint")
        sub = Gtk.Label(label="FILES · TEXT · LINKS · IMAGES")
        sub.add_css_class("sub")
        empty.append(hint)
        empty.append(sub)
        self.stack.add_named(empty, "empty")

        self.scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, propagate_natural_height=True)
        monitor = Gdk.Display.get_default().get_monitors().get_item(0)
        screen_h = monitor.get_geometry().height if monitor else 1000
        self.scroller.set_max_content_height(max(160, int(screen_h * self.cfg.max_height) - 120))
        self.listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.MULTIPLE, activate_on_single_click=False)
        self.listbox.add_css_class("items")
        self.listbox.connect("row-activated", lambda lb, row: self.open_items([row.item]))
        self.listbox.connect("selected-rows-changed", lambda lb: log("selection:", [r.item.name for r in lb.get_selected_rows()]))
        self.scroller.set_child(self.listbox)
        self.stack.add_named(self.scroller, "list")

        self.footer = Gtk.Box(spacing=8)
        self.footer.add_css_class("footer")
        grip = Gtk.Label(label="⋮⋮")
        grip.add_css_class("grip")
        self.footer_label = Gtk.Label(xalign=0, hexpand=True)
        self.footer.append(grip)
        self.footer.append(self.footer_label)
        self.panel.append(self.footer)
        drag_all = Gtk.DragSource(actions=self.drag_out_actions())
        drag_all.connect("prepare", self._prepare_drag_all)
        drag_all.connect("drag-begin", self._begin_drag_all)
        drag_all.connect("drag-end", lambda *_: self.on_drag_out_end())
        self.footer.add_controller(drag_all)

    def _build_actions(self) -> None:
        group = Gio.SimpleActionGroup()
        for name, cb in (
            ("open", lambda *_: self.open_items(self.selected_items())),
            ("reveal", lambda *_: self.reveal_items(self.selected_items())),
            ("copy", lambda *_: self.copy_items(self.selected_items())),
            ("remove", lambda *_: self.remove_items({i.id for i in self.selected_items()})),
            ("paste", lambda *_: self.paste()),
            ("select-all", lambda *_: self.listbox.select_all()),
            ("rename", lambda *_: self.rename_shelf()),
            ("new-shelf", lambda *_: self.store.new_shelf()),
            ("clear", lambda *_: self.store.clear()),
            ("delete-shelf", lambda *_: self.store.delete_shelf(self.store.active_id)),
            ("collapse", lambda *_: self.collapse(force=True)),
            ("quit", lambda *_: self.get_application().quit_safely()),
        ):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", cb)
            group.add_action(action)
        switch = Gio.SimpleAction.new("switch", GLib.VariantType.new("s"))
        switch.connect("activate", lambda a, v: self.store.set_active(v.get_string()))
        group.add_action(switch)
        self.insert_action_group("shelf", group)

    def _install_controllers(self) -> None:
        drop = Gtk.DropTargetAsync.new(Gdk.ContentFormats.new(ingest.ALL_MIMES), Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
        drop.connect("accept", lambda t, d: d.get_drag() is None)
        drop.connect("drag-enter", self._on_dnd_enter)
        drop.connect("drag-motion", self._on_dnd_motion)
        drop.connect("drag-leave", self._on_dnd_leave)
        drop.connect("drop", self._on_dnd_drop)
        self.add_controller(drop)

        motion = Gtk.EventControllerMotion()
        motion.connect("enter", lambda *_: self._cancel_collapse())
        motion.connect("leave", lambda *_: (self._set_keyboard(False), self._schedule_collapse(self.cfg.auto_collapse_ms)))
        self.add_controller(motion)

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)

        backdrop = Gtk.GestureClick(button=1)
        backdrop.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        backdrop.connect("pressed", self._on_backdrop_press)
        self.add_controller(backdrop)

        if DEBUG:
            legacy = Gtk.EventControllerLegacy()
            legacy.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
            legacy.connect("event", self._log_event)
            self.add_controller(legacy)

    _LOGGED_EVENTS = {
        Gdk.EventType.BUTTON_PRESS, Gdk.EventType.BUTTON_RELEASE, Gdk.EventType.ENTER_NOTIFY,
        Gdk.EventType.LEAVE_NOTIFY, Gdk.EventType.FOCUS_CHANGE, Gdk.EventType.GRAB_BROKEN, Gdk.EventType.KEY_PRESS,
    }

    def _log_event(self, controller, event) -> bool:
        if event is None:
            return False
        kind = event.get_event_type()
        if kind in self._LOGGED_EVENTS:
            ok, x, y = event.get_position()
            log("event", kind.value_nick, f"({int(x)},{int(y)})" if ok else "", "seq" if event.get_event_sequence() else "")
        return False

        menu = Gtk.GestureClick(button=3)
        menu.connect("pressed", self._on_context_press)
        self.panel.add_controller(menu)

    # ── layer-shell plumbing ─────────────────────────────────────
    def _on_map(self, *_):
        surface = self.get_surface()
        surface.connect("notify::width", lambda *_: self._apply_input_region())
        surface.connect("notify::height", lambda *_: self._apply_input_region())
        self._apply_input_region()
        if self.pinned:
            GLib.idle_add(lambda: (self.expand(), False)[1])

    def _apply_input_region(self) -> None:
        surface = self.get_surface()
        if surface is None:
            return
        w, h = surface.get_width(), surface.get_height()
        sw = min(self.cfg.strip_width, w)
        region = cairo.Region(cairo.RectangleInt(0 if self.cfg.edge == "left" else w - sw, 0, sw, h))
        if self.expanded and self._panel_left is not None:
            pw, ph = self._panel_size()
            region.union(cairo.RectangleInt(self._panel_left, self._panel_top, pw, ph))
            log("input region: strip + panel", (self._panel_left, self._panel_top, pw, ph))
        surface.set_input_region(region)

    # ── expand / collapse ────────────────────────────────────────
    def expand(self, y: float | None = None) -> None:
        self._cancel_collapse()
        if self.expanded:
            return
        self.expanded = True
        if self.store.panel_pos is not None:
            self._set_position(*self.store.panel_pos)
            self.revealer.set_reveal_child(True)
        elif y is not None:
            self._place_near(y)
            self.revealer.set_reveal_child(True)
        else:
            self._query_pointer(lambda py: (self._place_near(py), self.revealer.set_reveal_child(True)))

    def _panel_size(self) -> tuple[int, int]:
        _, h, _, _ = self.panel.measure(Gtk.Orientation.VERTICAL, self.cfg.width)
        return self.cfg.width, h

    def _set_position(self, left: float, top: float) -> None:
        sw, sh = self.get_width(), self.get_height()
        pw, ph = self._panel_size()
        self._panel_left = int(min(max(left, 0), max(0, sw - pw)))
        self._panel_top = int(min(max(top, 0), max(0, sh - ph)))
        self.revealer.set_margin_start(self._panel_left)
        self.revealer.set_margin_top(self._panel_top)
        self._apply_input_region()

    def _place_near(self, y: float | None) -> None:
        """Dock at the screen edge, centred on y (window coordinates)."""
        sw, sh = self.get_width(), self.get_height()
        pw, ph = self._panel_size()
        left = 0 if self.cfg.edge == "left" else sw - pw
        top = (sh - ph) / 2 if y is None else y - ph / 2
        self._set_position(left, top)

    def _pointer_window_pos(self, gesture) -> tuple[float, float] | None:
        # Offsets from the gesture are in the header's own coordinates, and the header moves with the panel,
        # so convert the current point to window coordinates before comparing against the start.
        ok, x, y = gesture.get_point(None)
        if not ok:
            return None
        ok2, pt = gesture.get_widget().compute_point(self, Graphene.Point().init(x, y))
        return (pt.x, pt.y) if ok2 else None

    def _on_move_begin(self, gesture, x, y) -> None:
        self._move_start = (self._panel_left or 0, self._panel_top or 0)
        self._move_start_ptr = self._pointer_window_pos(gesture)
        self._cancel_collapse()

    def _on_move_update(self, gesture, dx, dy) -> None:
        ptr = self._pointer_window_pos(gesture)
        if ptr is None or self._move_start_ptr is None:
            return
        self._set_position(self._move_start[0] + ptr[0] - self._move_start_ptr[0],
                           self._move_start[1] + ptr[1] - self._move_start_ptr[1])

    def _on_move_end(self, gesture, dx, dy) -> None:
        self.store.set_panel_pos((self._panel_left, self._panel_top))
        log("panel moved to", self._panel_left, self._panel_top)

    def _on_pin_toggled(self, button) -> None:
        self.pinned = button.get_active()
        self.store.set_pinned(self.pinned)
        if self.pinned:
            self._cancel_collapse()
        else:
            self._schedule_collapse(self.cfg.auto_collapse_ms)

    def _query_pointer(self, done) -> None:
        """Hyprland only: find the pointer so a hotkey/tray toggle opens the panel where the user is looking."""
        try:
            proc = Gio.Subprocess.new(["hyprctl", "-j", "--batch", "cursorpos;monitors"], Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE)
        except GLib.Error:
            done(None)
            return

        def finished(p, res):
            try:
                _, out, _ = p.communicate_utf8_finish(res)
                decoder = json.JSONDecoder()
                cursor, end = decoder.raw_decode(out.lstrip())
                monitors, _ = decoder.raw_decode(out.lstrip()[end:].lstrip())
                mon = next((m for m in monitors if m.get("focused")), monitors[0])
                surface_top = mon["y"] + mon["reserved"][1]
                done(cursor["y"] - surface_top)
            except (GLib.Error, ValueError, KeyError, IndexError, TypeError):
                done(None)

        proc.communicate_utf8_async(None, None, finished)

    def collapse(self, force: bool = False) -> None:
        self._cancel_collapse()
        if not self.expanded:
            return
        # A drag that left without a leave event (compositor quirk) must not pin the panel open forever.
        dnd_live = self.dnd_active and GLib.get_monotonic_time() - self._last_dnd_motion < 2_000_000
        if not force and (self.pinned or dnd_live or self.drag_out_active or self.popover_open):
            if not self.pinned:
                self._schedule_collapse(self.cfg.auto_collapse_ms)
            return
        log("collapse")
        self.expanded = False
        self.dnd_active = False
        self.remove_css_class("drop-hover")
        self.revealer.set_reveal_child(False)
        self._set_keyboard(False)
        self._apply_input_region()

    def _set_keyboard(self, wanted: bool) -> None:
        # Flipping to ON_DEMAND makes Hyprland grab keyboard focus on the next commit, so only do it
        # once the user has actually clicked inside the panel, and release it on collapse.
        if wanted != self._keyboard:
            self._keyboard = wanted
            LS.set_keyboard_mode(self, LS.KeyboardMode.ON_DEMAND if wanted else LS.KeyboardMode.NONE)

    def toggle(self) -> None:
        self.collapse(force=True) if self.expanded else self.expand()

    def _schedule_collapse(self, ms: int) -> None:
        self._cancel_collapse()
        if self.expanded:
            self._collapse_source = GLib.timeout_add(ms, self._collapse_timeout)

    def _collapse_timeout(self) -> bool:
        self._collapse_source = 0
        self.collapse()
        return False

    def _cancel_collapse(self) -> None:
        if self._collapse_source:
            GLib.source_remove(self._collapse_source)
            self._collapse_source = 0

    # ── drop in ──────────────────────────────────────────────────
    def _on_dnd_enter(self, target, drop: Gdk.Drop, x, y):
        if drop.get_drag() is not None:
            return 0
        self.dnd_active = True
        self._last_dnd_motion = GLib.get_monotonic_time()
        self.add_css_class("drop-hover")
        log("dnd enter", drop.get_formats().to_string())
        self.expand(y)
        return Gdk.DragAction.COPY

    def _on_dnd_motion(self, target, drop, x, y):
        self._last_dnd_motion = GLib.get_monotonic_time()
        return Gdk.DragAction.COPY

    def _on_dnd_leave(self, target, drop):
        self.dnd_active = False
        self.remove_css_class("drop-hover")
        self._schedule_collapse(max(self.cfg.auto_collapse_ms, 2500))

    def _on_dnd_drop(self, target, drop: Gdk.Drop, x, y):
        self.dnd_active = False
        self.remove_css_class("drop-hover")

        def done(items: list[Item]):
            drop.finish(Gdk.DragAction.COPY)
            log("dropped", [(i.kind, i.name) for i in items])
            self.add_items(items)
            self._schedule_collapse(self.cfg.linger_after_drop_ms)

        ingest.from_drop(self.store, drop, done)
        return True

    def paste(self) -> None:
        ingest.from_clipboard(self.store, self.get_clipboard(), self.add_items)

    def add_items(self, items: list[Item]) -> None:
        self.store.add_items(items)
        for item in items:
            if item.kind == URL and item.url and ingest.looks_like_image_url(item.url):
                ingest.download_image(self.store, item, lambda new, old=item: new and self.store.replace_item(old.id, new))

    # ── drag out ─────────────────────────────────────────────────
    def drag_out_actions(self) -> Gdk.DragAction:
        if self.cfg.drag_out_action == "move":
            return Gdk.DragAction.COPY | Gdk.DragAction.MOVE
        return Gdk.DragAction.COPY

    def begin_drag_out(self, items: list[Item], keep: bool, x: float, y: float, widget: Gtk.Widget):
        provider = content_for(items)
        if provider is None:
            return None
        self.drag_out_items = items
        self.drag_out_keep = keep
        self.drag_out_active = True
        self.drag_hot_x, self.drag_hot_y = x, y
        self._cancel_collapse()
        return provider

    def attach_drag(self, drag: Gdk.Drag) -> None:
        # Hyprland reports neither drop-performed nor a selected action; dnd-finished (vs cancel) is the success signal.
        drag.connect("drop-performed", lambda *_: self._on_drag_out_done("drop-performed"))
        drag.connect("dnd-finished", lambda *_: self._on_drag_out_done("dnd-finished"))
        drag.connect("cancel", lambda d, reason: log("drag cancel", reason))

    def _on_drag_out_done(self, signal: str) -> None:
        log(signal, "keep=", self.drag_out_keep, "items=", len(self.drag_out_items))
        if self.cfg.remove_on_drag_out and not self.drag_out_keep and self.drag_out_items:
            self.remove_items({i.id for i in self.drag_out_items})
            self.drag_out_items = []

    def on_drag_out_end(self) -> None:
        self.drag_out_active = False
        vanished = {i.id for i in self.drag_out_items if i.missing}
        log("drag-out end; vanished", len(vanished))
        self.drag_out_items = []
        if vanished:
            self.remove_items(vanished)
        self._schedule_collapse(self.cfg.auto_collapse_ms)

    def _prepare_drag_all(self, source, x, y):
        self.listbox.select_all()
        return self.begin_drag_out(list(self.store.active.items), bool(source.get_current_event_state() & Gdk.ModifierType.CONTROL_MASK), x, y, self.footer)

    def _begin_drag_all(self, source, drag):
        source.set_icon(Gtk.WidgetPaintable.new(self.panel), int(self.drag_hot_x), int(self.drag_hot_y) + 40)
        self.attach_drag(drag)

    # ── item operations ──────────────────────────────────────────
    def selected_items(self) -> list[Item]:
        return [row.item for row in self.listbox.get_selected_rows()]

    def remove_items(self, ids: set[str]) -> None:
        self.store.remove_items(ids)

    def open_items(self, items: list[Item]) -> None:
        for item in items:
            if item.kind in (FILE, IMAGE) and item.path:
                Gio.AppInfo.launch_default_for_uri_async(Gio.File.new_for_path(item.path).get_uri(), None, None, None)
            elif item.kind == URL and item.url:
                Gio.AppInfo.launch_default_for_uri_async(item.url, None, None, None)
            elif item.kind == TEXT:
                self.copy_items([item])

    def reveal_items(self, items: list[Item]) -> None:
        uris = [Gio.File.new_for_path(i.path).get_uri() for i in items if i.kind in (FILE, IMAGE) and i.path]
        if not uris:
            return
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        bus.call(
            "org.freedesktop.FileManager1", "/org/freedesktop/FileManager1", "org.freedesktop.FileManager1",
            "ShowItems", GLib.Variant("(ass)", (uris, "")), None, Gio.DBusCallFlags.NONE, 2000, None,
            lambda b, res: self._reveal_fallback(b, res, uris),
        )

    def _reveal_fallback(self, bus, res, uris):
        try:
            bus.call_finish(res)
        except GLib.Error:
            parent = Gio.File.new_for_uri(uris[0]).get_parent()
            if parent:
                Gio.AppInfo.launch_default_for_uri_async(parent.get_uri(), None, None, None)

    def copy_items(self, items: list[Item]) -> None:
        provider = content_for(items)
        if provider:
            self.get_clipboard().set_content(provider)

    # ── shelf-level UI ───────────────────────────────────────────
    def refresh(self) -> None:
        shelf = self.store.active
        self.title.set_text(shelf.name)
        n = len(shelf.items)
        self.count.set_text(f"{n} ITEM" + ("" if n == 1 else "S"))
        selected = {row.item.id for row in self.listbox.get_selected_rows()}
        while child := self.listbox.get_first_child():
            self.listbox.remove(child)
        for item in shelf.items:
            row = ItemRow(item, self)
            self.listbox.append(row)
            if item.id in selected:
                self.listbox.select_row(row)
        self.stack.set_visible_child_name("list" if n else "empty")
        self.footer.set_visible(n > 1)
        self.footer_label.set_text(f"drag all · {n}")
        if self.expanded and self._panel_left is not None:
            GLib.idle_add(lambda: (self._set_position(self._panel_left, self._panel_top), False)[1])

    def rename_shelf(self) -> None:
        popover = Gtk.Popover(has_arrow=False, position=Gtk.PositionType.BOTTOM)
        entry = Gtk.Entry(text=self.store.active.name, width_chars=22)
        entry.add_css_class("rename")
        popover.set_child(entry)
        popover.set_parent(self.title)
        self._track_popover(popover)

        def commit(*_):
            self.store.rename(self.store.active_id, entry.get_text())
            popover.popdown()

        entry.connect("activate", commit)
        popover.popup()
        entry.grab_focus()
        entry.select_region(0, -1)

    def _track_popover(self, popover: Gtk.Popover) -> None:
        self.popover_open = True

        def closed(*_):
            self.popover_open = False
            GLib.idle_add(lambda: (popover.unparent(), False)[1])
            self._schedule_collapse(self.cfg.auto_collapse_ms)

        popover.connect("closed", closed)

    def _on_context_press(self, gesture, n_press, x, y) -> None:
        picked = self.panel.pick(x, y, Gtk.PickFlags.DEFAULT)
        row = picked.get_ancestor(Gtk.ListBoxRow) if picked else None
        menu = Gio.Menu()
        if row is not None:
            if not row.is_selected():
                self.listbox.unselect_all()
                self.listbox.select_row(row)
            items = self.selected_items()
            section = Gio.Menu()
            section.append("Open", "shelf.open")
            if any(i.kind in (FILE, IMAGE) for i in items):
                section.append("Show in file manager", "shelf.reveal")
            section.append("Copy", "shelf.copy")
            menu.append_section(None, section)
            danger = Gio.Menu()
            danger.append("Remove", "shelf.remove")
            menu.append_section(None, danger)
        else:
            shelves = Gio.Menu()
            for shelf in self.store.shelves:
                mark = "● " if shelf.id == self.store.active_id else "○ "
                item = Gio.MenuItem.new(f"{mark}{shelf.name} · {len(shelf.items)}", None)
                item.set_action_and_target_value("shelf.switch", GLib.Variant.new_string(shelf.id))
                shelves.append_item(item)
            menu.append_section("SHELVES", shelves)
            section = Gio.Menu()
            section.append("New shelf", "shelf.new-shelf")
            section.append("Rename", "shelf.rename")
            section.append("Paste from clipboard", "shelf.paste")
            menu.append_section(None, section)
            danger = Gio.Menu()
            danger.append("Clear shelf", "shelf.clear")
            danger.append("Delete shelf", "shelf.delete-shelf")
            menu.append_section(None, danger)
            tail = Gio.Menu()
            tail.append("Quit", "shelf.quit")
            menu.append_section(None, tail)

        popover = Gtk.PopoverMenu.new_from_model(menu)
        popover.set_has_arrow(False)
        popover.set_parent(self.panel)
        popover.set_pointing_to(Gdk.Rectangle(int(x), int(y), 1, 1))
        popover.set_position(Gtk.PositionType.LEFT if self.cfg.edge == "right" else Gtk.PositionType.RIGHT)
        self._track_popover(popover)
        popover.popup()

    def _on_backdrop_press(self, gesture, n_press, x, y) -> None:
        picked = self.pick(x, y, Gtk.PickFlags.DEFAULT)
        if picked is None or not (picked == self.panel or picked.is_ancestor(self.panel)):
            return
        self._set_keyboard(True)
        if picked.get_ancestor(Gtk.ListBoxRow) is None and picked.get_ancestor(Gtk.Button) is None:
            self.listbox.unselect_all()

    def _on_key(self, controller, keyval, keycode, state) -> bool:
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        if keyval == Gdk.KEY_Escape:
            self.collapse(force=True)
        elif keyval in (Gdk.KEY_Delete, Gdk.KEY_BackSpace):
            self.remove_items({i.id for i in self.selected_items()})
        elif ctrl and keyval in (Gdk.KEY_a, Gdk.KEY_A):
            self.listbox.select_all()
        elif ctrl and keyval in (Gdk.KEY_v, Gdk.KEY_V):
            self.paste()
        elif ctrl and keyval in (Gdk.KEY_c, Gdk.KEY_C):
            self.copy_items(self.selected_items())
        elif keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self.open_items(self.selected_items())
        else:
            return False
        return True
