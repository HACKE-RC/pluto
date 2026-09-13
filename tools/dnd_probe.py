import sys
import tempfile
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gdk, Gio, GLib, GObject, Gtk, Gtk4LayerShell as LS  # noqa: E402

MODE = sys.argv[1] if len(sys.argv) > 1 else "layer"
MIMES = ["text/uri-list", "text/x-moz-url", "text/plain;charset=utf-8", "text/plain", "text/html", "image/png"]


def log(*a):
    print(*a, flush=True)


class Spike(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="dev.rc.shelf.spike")

    def do_activate(self):
        win = Gtk.Window(application=self, title="shelf-spike", default_width=260, default_height=520)
        if MODE == "layer":
            LS.init_for_window(win)
            LS.set_layer(win, LS.Layer.OVERLAY)
            LS.set_anchor(win, LS.Edge.RIGHT, True)
            LS.set_margin(win, LS.Edge.RIGHT, 20)
            LS.set_keyboard_mode(win, LS.KeyboardMode.NONE)
            LS.set_namespace(win, "shelf")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)
        win.set_child(box)

        # Zone A: plain GTK DropTarget (GTK does the mime negotiation itself).
        a = Gtk.Label(label=f"[{MODE}] A: simple DropTarget\n(files / text / images)", vexpand=True)
        a.add_css_class("title-3")
        box.append(a)
        st = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
        st.set_gtypes([Gdk.FileList, Gdk.Texture, GObject.TYPE_STRING])
        st.connect("accept", lambda t, d: (log("A accept", d.get_formats().to_string(), "actions=", d.get_actions()), True)[1])
        st.connect("enter", lambda t, x, y: (log("A enter"), Gdk.DragAction.COPY)[1])
        st.connect("drop", self.on_simple_drop)
        a.add_controller(st)

        # Zone B: async target, reads raw mimes sequentially.
        b = Gtk.Label(label="B: async raw-mime target", vexpand=True)
        b.add_css_class("title-3")
        box.append(b)
        dt = Gtk.DropTargetAsync.new(Gdk.ContentFormats.new(MIMES), Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
        dt.connect("accept", lambda t, d: (log("B accept", d.get_formats().to_string(), "actions=", d.get_actions()), True)[1])
        dt.connect("drag-enter", lambda t, d, x, y: (log("B enter"), Gdk.DragAction.COPY)[1])
        dt.connect("drag-motion", lambda t, d, x, y: Gdk.DragAction.COPY)
        dt.connect("drop", self.on_async_drop)
        b.add_controller(dt)

        tmp = Path(tempfile.gettempdir()) / "shelf-spike-dragme.txt"
        tmp.write_text("dragged out of shelf spike\n")
        drag_lbl = Gtk.Label(label=f"DRAG ME OUT\n{tmp.name}", vexpand=True)
        drag_lbl.add_css_class("title-3")
        box.append(drag_lbl)
        ds = Gtk.DragSource(actions=Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
        f = Gio.File.new_for_path(str(tmp))
        ds.set_content(Gdk.ContentProvider.new_union([
            Gdk.ContentProvider.new_for_value(f),
            Gdk.ContentProvider.new_for_bytes("text/uri-list", GLib.Bytes.new((f.get_uri() + "\r\n").encode())),
        ]))
        ds.connect("drag-begin", lambda s, d: log("OUT begin actions=", d.get_actions()))
        ds.connect("drag-end", lambda s, d, ok: log("OUT end delete_data=", ok, "selected=", d.get_selected_action()))
        ds.connect("drag-cancel", lambda s, d, r: (log("OUT cancel reason=", r), False)[1])
        drag_lbl.add_controller(ds)

        win.present()
        log("ready mode=", MODE)

    def on_simple_drop(self, target, value, x, y):
        if isinstance(value, Gdk.FileList):
            msg = "FileList: " + ", ".join(f.get_basename() for f in value.get_files())
            log("A drop FileList:", [f.get_path() or f.get_uri() for f in value.get_files()])
        elif isinstance(value, Gdk.Texture):
            msg = f"Texture {value.get_width()}x{value.get_height()}"
            log("A drop Texture:", value.get_width(), "x", value.get_height())
        else:
            msg = "str: " + str(value)[:60]
            log("A drop str:", repr(value)[:300])
        target.get_widget().set_label(f"A GOT\n{msg}")
        return True

    def on_async_drop(self, target, drop, x, y):
        fmts = drop.get_formats()
        mimes = [m for m in MIMES if fmts.contain_mime_type(m)]
        log("B drop actions=", drop.get_actions(), "mimes=", mimes)
        if not mimes:
            drop.finish(0)
            return False
        # Always COPY: a shelf must never make the source delete its file.
        action = Gdk.DragAction.COPY
        queue = list(mimes)
        got = []

        def read_next():
            if not queue:
                drop.finish(action)
                log("B finished", action)
                target.get_widget().set_label("B GOT\n" + "\n".join(got)[:200])
                return
            m = queue.pop(0)
            tid = GLib.timeout_add(3000, lambda: (log(f"  {m} TIMEOUT"), read_next(), False)[2])

            def cb(d, res):
                try:
                    stream, real = d.read_finish(res)
                except Exception as e:  # noqa: BLE001
                    GLib.source_remove(tid)
                    log(f"  {m} read failed: {e}")
                    read_next()
                    return

                def bytes_cb(s, r):
                    GLib.source_remove(tid)
                    try:
                        data = s.read_bytes_finish(r).get_data()
                        log(f"  {m} ({real}) ->", data[:300])
                        got.append(f"{m}: {len(data)}B {data[:40]!r}")
                    except Exception as e:  # noqa: BLE001
                        log(f"  {m} bytes failed: {e}")
                    read_next()

                stream.read_bytes_async(1 << 20, GLib.PRIORITY_DEFAULT, None, bytes_cb)

            drop.read_async([m], GLib.PRIORITY_DEFAULT, None, cb)

        read_next()
        return True


Spike().run(None)
