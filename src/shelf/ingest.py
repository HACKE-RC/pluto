"""Turn a Gdk.Drop or Gdk.Clipboard into shelf items without ever blocking the main loop."""

from __future__ import annotations

import re
from typing import Callable
from urllib.parse import unquote, urlsplit

from gi.repository import Gdk, Gio, GLib

from .store import Item, Store

URI_LIST = "text/uri-list"
MOZ_URL = "text/x-moz-url"
IMAGE_MIMES = ("image/png", "image/jpeg", "image/webp", "image/gif")
TEXT_MIMES = ("text/plain;charset=utf-8", "text/plain", "UTF8_STRING")

ALL_MIMES = [URI_LIST, MOZ_URL, *IMAGE_MIMES, *TEXT_MIMES]
URL_RE = re.compile(r"^(https?|ftp)://\S+$")
READ_CHUNK = 256 * 1024

Done = Callable[[list[Item]], None]


def _read_all(stream: Gio.InputStream, done: Callable[[bytes], None]) -> None:
    chunks: list[bytes] = []

    def on_chunk(s, res):
        try:
            data = s.read_bytes_finish(res).get_data()
        except GLib.Error:
            data = b""
        if data:
            chunks.append(data)
            s.read_bytes_async(READ_CHUNK, GLib.PRIORITY_DEFAULT, None, on_chunk)
        else:
            s.close_async(GLib.PRIORITY_DEFAULT, None, lambda *_: None)
            done(b"".join(chunks))

    stream.read_bytes_async(READ_CHUNK, GLib.PRIORITY_DEFAULT, None, on_chunk)


def _read_mime(source, mime: str, done: Callable[[bytes | None], None]) -> None:
    """source is a Gdk.Drop or Gdk.Clipboard; both share read_async/read_finish."""
    timeout = GLib.timeout_add(4000, lambda: (done(None), False)[1])
    fired = [False]

    def finish(data):
        if fired[0]:
            return
        fired[0] = True
        GLib.source_remove(timeout)
        done(data)

    def on_ready(src, res):
        try:
            stream, _real = src.read_finish(res)
        except GLib.Error:
            finish(None)
            return
        _read_all(stream, finish)

    source.read_async([mime], GLib.PRIORITY_DEFAULT, None, on_ready)


def _decode_moz_url(data: bytes) -> tuple[str, str | None]:
    text = data.decode("utf-16-le" if len(data) > 1 and data[1] == 0 else "utf-8", "replace").lstrip("﻿")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return (lines[0] if lines else ""), (lines[1] if len(lines) > 1 else None)


def _parse_uri_list(data: bytes) -> list[str]:
    return [line.strip() for line in data.decode("utf-8", "replace").splitlines() if line.strip() and not line.startswith("#")]


def _ext_for(mime: str) -> str:
    return {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif"}.get(mime, "bin")


class Ingest:
    """Async pipeline: pick the richest representation the source offers and build items from it."""

    def __init__(self, store: Store, source, formats: Gdk.ContentFormats, done: Done):
        self.store = store
        self.source = source
        self.formats = formats
        self.done = done
        self.items: list[Item] = []

    def has(self, mime: str) -> bool:
        return self.formats.contain_mime_type(mime)

    def first(self, mimes) -> str | None:
        return next((m for m in mimes if self.has(m)), None)

    def start(self) -> None:
        if self.has(URI_LIST):
            _read_mime(self.source, URI_LIST, self._on_uri_list)
        elif self.first(IMAGE_MIMES):
            self._capture_image(origin=None, title=None)
        elif self.has(MOZ_URL):
            _read_mime(self.source, MOZ_URL, self._on_moz_url_only)
        elif self.first(TEXT_MIMES):
            _read_mime(self.source, self.first(TEXT_MIMES), self._on_text)
        else:
            self.done([])

    # ── branches ─────────────────────────────────────────────────
    def _on_uri_list(self, data: bytes | None) -> None:
        uris = _parse_uri_list(data or b"")
        remote = [u for u in uris if not u.startswith("file:")]
        for uri in uris:
            if uri.startswith("file:"):
                self.items.append(Item.file(unquote(urlsplit(uri).path)))
        if not remote:
            self.done(self.items)
            return
        # A remote URI plus image data means "image dragged from a browser": keep the pixels, remember the source.
        if self.first(IMAGE_MIMES):
            self._capture_image(origin=remote[0], title=None)
        elif self.has(MOZ_URL):
            _read_mime(self.source, MOZ_URL, lambda d: self._finish_links(remote, d))
        else:
            self._finish_links(remote, None)

    def _finish_links(self, remote: list[str], moz: bytes | None) -> None:
        title = _decode_moz_url(moz)[1] if moz else None
        for i, uri in enumerate(remote):
            self.items.append(Item.link(uri, title if i == 0 else None))
        self.done(self.items)

    def _on_moz_url_only(self, data: bytes | None) -> None:
        url, title = _decode_moz_url(data or b"")
        if url:
            self.items.append(Item.link(url, title))
        self.done(self.items)

    def _on_text(self, data: bytes | None) -> None:
        text = (data or b"").decode("utf-8", "replace").strip("\x00").strip()
        if text:
            self.items.append(Item.link(text) if URL_RE.match(text) else Item.text_snippet(text))
        self.done(self.items)

    def _capture_image(self, origin: str | None, title: str | None) -> None:
        mime = self.first(IMAGE_MIMES)

        def on_data(data: bytes | None):
            if data:
                path = self.store.new_blob_path(_ext_for(mime))
                path.write_bytes(data)
                self.items.append(Item.image(str(path), origin=origin))
            elif origin:
                self.items.append(Item.link(origin, title))
            self.done(self.items)

        _read_mime(self.source, mime, on_data)


def from_drop(store: Store, drop: Gdk.Drop, done: Done) -> None:
    Ingest(store, drop, drop.get_formats(), done).start()


def from_clipboard(store: Store, clipboard: Gdk.Clipboard, done: Done) -> None:
    Ingest(store, clipboard, clipboard.get_formats(), done).start()


def content_type(item: Item) -> str:
    if item.kind in ("file", "image") and item.path:
        ctype, _ = Gio.content_type_guess(item.path, None)
        return ctype
    return {"url": "text/html", "text": "text/plain"}.get(item.kind, "application/octet-stream")
