"""StatusNotifierItem + DBusMenu over GDBus — no GTK3, no appindicator."""

from __future__ import annotations

import math
import os
from typing import Callable

import cairo
from gi.repository import Gio, GLib

from .store import Store

WATCHER = "org.kde.StatusNotifierWatcher"
SNI_PATH = "/StatusNotifierItem"
MENU_PATH = "/MenuBar"

SNI_XML = """
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category" type="s" access="read"/>
    <property name="Id" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="WindowId" type="i" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="IconPixmap" type="a(iiay)" access="read"/>
    <property name="OverlayIconName" type="s" access="read"/>
    <property name="OverlayIconPixmap" type="a(iiay)" access="read"/>
    <property name="AttentionIconName" type="s" access="read"/>
    <property name="AttentionIconPixmap" type="a(iiay)" access="read"/>
    <property name="AttentionMovieName" type="s" access="read"/>
    <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
    <property name="ItemIsMenu" type="b" access="read"/>
    <property name="Menu" type="o" access="read"/>
    <method name="ContextMenu"><arg name="x" type="i" direction="in"/><arg name="y" type="i" direction="in"/></method>
    <method name="Activate"><arg name="x" type="i" direction="in"/><arg name="y" type="i" direction="in"/></method>
    <method name="SecondaryActivate"><arg name="x" type="i" direction="in"/><arg name="y" type="i" direction="in"/></method>
    <method name="Scroll"><arg name="delta" type="i" direction="in"/><arg name="orientation" type="s" direction="in"/></method>
    <signal name="NewTitle"/>
    <signal name="NewIcon"/>
    <signal name="NewAttentionIcon"/>
    <signal name="NewOverlayIcon"/>
    <signal name="NewToolTip"/>
    <signal name="NewStatus"><arg name="status" type="s"/></signal>
  </interface>
</node>
"""

MENU_XML = """
<node>
  <interface name="com.canonical.dbusmenu">
    <property name="Version" type="u" access="read"/>
    <property name="TextDirection" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="IconThemePath" type="as" access="read"/>
    <method name="GetLayout">
      <arg name="parentId" type="i" direction="in"/>
      <arg name="recursionDepth" type="i" direction="in"/>
      <arg name="propertyNames" type="as" direction="in"/>
      <arg name="revision" type="u" direction="out"/>
      <arg name="layout" type="(ia{sv}av)" direction="out"/>
    </method>
    <method name="GetGroupProperties">
      <arg name="ids" type="ai" direction="in"/>
      <arg name="propertyNames" type="as" direction="in"/>
      <arg name="properties" type="a(ia{sv})" direction="out"/>
    </method>
    <method name="GetProperty">
      <arg name="id" type="i" direction="in"/>
      <arg name="name" type="s" direction="in"/>
      <arg name="value" type="v" direction="out"/>
    </method>
    <method name="Event">
      <arg name="id" type="i" direction="in"/>
      <arg name="eventId" type="s" direction="in"/>
      <arg name="data" type="v" direction="in"/>
      <arg name="timestamp" type="u" direction="in"/>
    </method>
    <method name="EventGroup">
      <arg name="events" type="a(isvu)" direction="in"/>
      <arg name="idErrors" type="ai" direction="out"/>
    </method>
    <method name="AboutToShow">
      <arg name="id" type="i" direction="in"/>
      <arg name="needUpdate" type="b" direction="out"/>
    </method>
    <method name="AboutToShowGroup">
      <arg name="ids" type="ai" direction="in"/>
      <arg name="updatesNeeded" type="ai" direction="out"/>
      <arg name="idErrors" type="ai" direction="out"/>
    </method>
    <signal name="ItemsPropertiesUpdated">
      <arg name="updatedProps" type="a(ia{sv})"/>
      <arg name="removedProps" type="a(ias)"/>
    </signal>
    <signal name="LayoutUpdated">
      <arg name="revision" type="u"/>
      <arg name="parent" type="i"/>
    </signal>
    <signal name="ItemActivationRequested">
      <arg name="id" type="i"/>
      <arg name="timestamp" type="u"/>
    </signal>
  </interface>
</node>
"""

ID_NEW, ID_CLEAR, ID_DELETE, ID_QUIT, ID_SEP_A, ID_SEP_B = 1, 2, 3, 4, 5, 6
SHELF_BASE = 100


def render_icon(size: int, color: str = "#ffffff") -> tuple[int, int, bytes]:
    """A tray glyph: an open tray with an item hovering above it. Returns SNI ARGB32 (network order)."""
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    ctx = cairo.Context(surface)
    s = size / 22.0
    ctx.scale(s, s)
    h = color.lstrip("#")
    ctx.set_source_rgb(*(int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)))
    ctx.set_line_width(2.0)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.move_to(3.5, 10)
    ctx.line_to(3.5, 17)
    ctx.line_to(18.5, 17)
    ctx.line_to(18.5, 10)
    ctx.stroke()
    ctx.move_to(3.5, 13)
    ctx.line_to(8, 13)
    ctx.move_to(14, 13)
    ctx.line_to(18.5, 13)
    ctx.stroke()
    ctx.arc(11, 5.5, 2.2, 0, 2 * math.pi)
    ctx.fill()
    surface.flush()

    raw = bytes(surface.get_data())
    stride = surface.get_stride()
    out = bytearray()
    for y in range(size):
        row = raw[y * stride : y * stride + size * 4]
        for x in range(size):
            b, g, r, a = row[x * 4 : x * 4 + 4]
            if a:
                r, g, b = (min(255, c * 255 // a) for c in (r, g, b))
            out += bytes((a, r, g, b))
    return size, size, bytes(out)


class Tray:
    def __init__(
        self,
        store: Store,
        on_activate: Callable[[], None],
        on_select_shelf: Callable[[str], None],
        on_new: Callable[[], None],
        on_clear: Callable[[], None],
        on_delete: Callable[[], None],
        on_quit: Callable[[], None],
        icon_color: str = "#ffffff",
    ):
        self.store = store
        self.on_activate = on_activate
        self.on_select_shelf = on_select_shelf
        self.on_new = on_new
        self.on_clear = on_clear
        self.on_delete = on_delete
        self.on_quit = on_quit
        self.revision = 1
        self.pixmaps = [render_icon(22, icon_color), render_icon(44, icon_color)]
        self.name = f"org.kde.StatusNotifierItem-{os.getpid()}-1"
        self.registered = False
        self.name_owned = False

        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        sni = Gio.DBusNodeInfo.new_for_xml(SNI_XML).interfaces[0]
        menu = Gio.DBusNodeInfo.new_for_xml(MENU_XML).interfaces[0]
        self.bus.register_object(SNI_PATH, sni, self._sni_call, self._sni_get, None)
        self.bus.register_object(MENU_PATH, menu, self._menu_call, self._menu_get, None)
        Gio.bus_own_name_on_connection(self.bus, self.name, Gio.BusNameOwnerFlags.NONE, self._on_name_acquired, None)
        Gio.bus_watch_name(Gio.BusType.SESSION, WATCHER, Gio.BusNameWatcherFlags.NONE, self._on_watcher_appeared, self._on_watcher_vanished)
        store.connect("changed", lambda *_: self.refresh())

    # ── registration ─────────────────────────────────────────────
    def _on_name_acquired(self, *_):
        self.name_owned = True
        self._register()

    def _on_watcher_appeared(self, *_):
        self.registered = False
        self._register()

    def _on_watcher_vanished(self, *_):
        self.registered = False

    def _register(self) -> None:
        if self.registered or not self.name_owned:
            return
        self.bus.call(
            WATCHER, "/StatusNotifierWatcher", WATCHER, "RegisterStatusNotifierItem",
            GLib.Variant("(s)", (self.name,)), None, Gio.DBusCallFlags.NONE, 2000, None, self._on_registered,
        )

    def _on_registered(self, bus, res):
        try:
            bus.call_finish(res)
            self.registered = True
        except GLib.Error:
            self.registered = False

    def refresh(self) -> None:
        self.revision += 1
        self.bus.emit_signal(None, SNI_PATH, "org.kde.StatusNotifierItem", "NewToolTip", None)
        self.bus.emit_signal(None, MENU_PATH, "com.canonical.dbusmenu", "LayoutUpdated", GLib.Variant("(ui)", (self.revision, 0)))

    # ── StatusNotifierItem ───────────────────────────────────────
    def _tooltip_text(self) -> str:
        shelf = self.store.active
        n = len(shelf.items)
        return f"{shelf.name} · {n} item" + ("" if n == 1 else "s")

    def _sni_get(self, conn, sender, path, iface, prop):
        values = {
            "Category": GLib.Variant("s", "ApplicationStatus"),
            "Id": GLib.Variant("s", "pluto"),
            "Title": GLib.Variant("s", "Pluto"),
            "Status": GLib.Variant("s", "Active"),
            "WindowId": GLib.Variant("i", 0),
            "IconName": GLib.Variant("s", ""),
            "IconPixmap": GLib.Variant("a(iiay)", self.pixmaps),
            "OverlayIconName": GLib.Variant("s", ""),
            "OverlayIconPixmap": GLib.Variant("a(iiay)", []),
            "AttentionIconName": GLib.Variant("s", ""),
            "AttentionIconPixmap": GLib.Variant("a(iiay)", []),
            "AttentionMovieName": GLib.Variant("s", ""),
            "ToolTip": GLib.Variant("(sa(iiay)ss)", ("", [], "Pluto", self._tooltip_text())),
            "ItemIsMenu": GLib.Variant("b", False),
            "Menu": GLib.Variant("o", MENU_PATH),
        }
        return values.get(prop)

    def _sni_call(self, conn, sender, path, iface, method, params, invocation):
        if method in ("Activate", "SecondaryActivate"):
            self.on_activate()
        invocation.return_value(None)

    # ── DBusMenu ─────────────────────────────────────────────────
    def _entries(self) -> list[tuple[int, dict]]:
        entries: list[tuple[int, dict]] = []
        for index, shelf in enumerate(self.store.shelves):
            label = f"{shelf.name.replace('_', '__')}   {len(shelf.items)}"
            entries.append((SHELF_BASE + index, {
                "label": GLib.Variant("s", label),
                "toggle-type": GLib.Variant("s", "radio"),
                "toggle-state": GLib.Variant("i", 1 if shelf.id == self.store.active_id else 0),
            }))
        entries.append((ID_SEP_A, {"type": GLib.Variant("s", "separator")}))
        entries.append((ID_NEW, {"label": GLib.Variant("s", "New shelf")}))
        entries.append((ID_CLEAR, {"label": GLib.Variant("s", "Clear shelf")}))
        entries.append((ID_DELETE, {"label": GLib.Variant("s", "Delete shelf")}))
        entries.append((ID_SEP_B, {"type": GLib.Variant("s", "separator")}))
        entries.append((ID_QUIT, {"label": GLib.Variant("s", "Quit")}))
        return entries

    def _layout(self):
        children = [GLib.Variant("(ia{sv}av)", (item_id, props, [])) for item_id, props in self._entries()]
        root_props = {"children-display": GLib.Variant("s", "submenu")}
        return (0, root_props, children)

    def _menu_get(self, conn, sender, path, iface, prop):
        return {
            "Version": GLib.Variant("u", 3),
            "TextDirection": GLib.Variant("s", "ltr"),
            "Status": GLib.Variant("s", "normal"),
            "IconThemePath": GLib.Variant("as", []),
        }.get(prop)

    def _menu_call(self, conn, sender, path, iface, method, params, invocation):
        if method == "GetLayout":
            invocation.return_value(GLib.Variant("(u(ia{sv}av))", (self.revision, self._layout())))
        elif method == "GetGroupProperties":
            wanted = set(params.unpack()[0])
            props = [(i, p) for i, p in self._entries() if not wanted or i in wanted]
            if not wanted or 0 in wanted:
                props.insert(0, (0, {"children-display": GLib.Variant("s", "submenu")}))
            invocation.return_value(GLib.Variant("(a(ia{sv}))", (props,)))
        elif method == "GetProperty":
            item_id, name = params.unpack()
            for i, p in self._entries():
                if i == item_id and name in p:
                    invocation.return_value(GLib.Variant("(v)", (p[name],)))
                    return
            invocation.return_dbus_error("org.freedesktop.DBus.Error.InvalidArgs", "no such property")
        elif method == "Event":
            item_id, event_id, _data, _ts = params.unpack()
            if event_id == "clicked":
                self._dispatch(item_id)
            invocation.return_value(None)
        elif method == "EventGroup":
            for item_id, event_id, _data, _ts in params.unpack()[0]:
                if event_id == "clicked":
                    self._dispatch(item_id)
            invocation.return_value(GLib.Variant("(ai)", ([],)))
        elif method == "AboutToShow":
            invocation.return_value(GLib.Variant("(b)", (False,)))
        elif method == "AboutToShowGroup":
            invocation.return_value(GLib.Variant("(aiai)", ([], [])))
        else:
            invocation.return_dbus_error("org.freedesktop.DBus.Error.UnknownMethod", method)

    def _dispatch(self, item_id: int) -> None:
        if item_id >= SHELF_BASE:
            index = item_id - SHELF_BASE
            if index < len(self.store.shelves):
                self.on_select_shelf(self.store.shelves[index].id)
        elif item_id == ID_NEW:
            self.on_new()
        elif item_id == ID_CLEAR:
            self.on_clear()
        elif item_id == ID_DELETE:
            self.on_delete()
        elif item_id == ID_QUIT:
            self.on_quit()
