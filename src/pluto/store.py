from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from gi.repository import GLib, GObject

from .config import BLOB_DIR, DATA_DIR, STATE_FILE

FILE, TEXT, URL, IMAGE = "file", "text", "url", "image"


@dataclass
class Item:
    id: str
    kind: str
    path: str | None = None
    text: str | None = None
    url: str | None = None
    title: str | None = None
    origin: str | None = None
    added: float = field(default_factory=time.time)

    @classmethod
    def file(cls, path: str) -> Item:
        return cls(id=uuid.uuid4().hex, kind=FILE, path=path)

    @classmethod
    def text_snippet(cls, text: str) -> Item:
        return cls(id=uuid.uuid4().hex, kind=TEXT, text=text)

    @classmethod
    def link(cls, url: str, title: str | None = None) -> Item:
        return cls(id=uuid.uuid4().hex, kind=URL, url=url, title=title or None)

    @classmethod
    def image(cls, path: str, origin: str | None = None) -> Item:
        return cls(id=uuid.uuid4().hex, kind=IMAGE, path=path, origin=origin)

    @property
    def name(self) -> str:
        if self.kind in (FILE, IMAGE):
            return os.path.basename(self.path or "") or self.path or "?"
        if self.kind == URL:
            if self.title:
                return self.title
            parts = urlsplit(self.url or "")
            return (parts.netloc + parts.path).rstrip("/") or self.url or "?"
        first = (self.text or "").strip().splitlines()
        return first[0] if first else "empty text"

    @property
    def missing(self) -> bool:
        return self.kind in (FILE, IMAGE) and not os.path.exists(self.path or "")

    def to_json(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}

    @classmethod
    def from_json(cls, data: dict) -> Item:
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class Shelf:
    id: str
    name: str
    items: list[Item] = field(default_factory=list)
    created: float = field(default_factory=time.time)

    def to_json(self) -> dict:
        return {"id": self.id, "name": self.name, "created": self.created, "items": [i.to_json() for i in self.items]}

    @classmethod
    def from_json(cls, data: dict) -> Shelf:
        return cls(
            id=data["id"],
            name=data.get("name") or "Shelf",
            created=data.get("created", time.time()),
            items=[Item.from_json(i) for i in data.get("items", [])],
        )


class Store(GObject.Object):
    __gsignals__ = {"changed": (GObject.SignalFlags.RUN_FIRST, None, ())}

    def __init__(self) -> None:
        super().__init__()
        self.shelves: list[Shelf] = []
        self.active_id: str = ""
        self.panel_pos: tuple[int, int] | None = None
        self.pinned = False
        self._save_source = 0
        self.load()

    # ── persistence ──────────────────────────────────────────────
    def load(self) -> None:
        try:
            data = json.loads(STATE_FILE.read_text())
            self.shelves = [Shelf.from_json(s) for s in data.get("shelves", [])]
            self.active_id = data.get("active", "")
            pos = data.get("panel_pos")
            self.panel_pos = (int(pos[0]), int(pos[1])) if pos else None
            self.pinned = bool(data.get("pinned", False))
        except (OSError, ValueError, KeyError):
            self.shelves = []
        if not self.shelves:
            self.shelves = [Shelf(id=uuid.uuid4().hex, name="Shelf 1")]
        if not any(s.id == self.active_id for s in self.shelves):
            self.active_id = self.shelves[0].id

    def save_now(self) -> None:
        if self._save_source:
            GLib.source_remove(self._save_source)
            self._save_source = 0
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"active": self.active_id, "panel_pos": list(self.panel_pos) if self.panel_pos else None, "pinned": self.pinned, "shelves": [s.to_json() for s in self.shelves]}, indent=1)
        tmp = STATE_FILE.with_suffix(".json.tmp")
        tmp.write_text(payload)
        os.replace(tmp, STATE_FILE)

    def _touch(self) -> None:
        self.emit("changed")
        if not self._save_source:
            self._save_source = GLib.timeout_add(300, self._flush)

    def _flush(self) -> bool:
        self._save_source = 0
        self.save_now()
        return False

    def set_panel_pos(self, pos: tuple[int, int] | None) -> None:
        self.panel_pos = pos
        self._save_later()

    def set_pinned(self, pinned: bool) -> None:
        self.pinned = pinned
        self._save_later()

    def _save_later(self) -> None:
        if not self._save_source:
            self._save_source = GLib.timeout_add(300, self._flush)

    # ── shelves ──────────────────────────────────────────────────
    @property
    def active(self) -> Shelf:
        return next(s for s in self.shelves if s.id == self.active_id)

    def get(self, shelf_id: str) -> Shelf | None:
        return next((s for s in self.shelves if s.id == shelf_id), None)

    def new_shelf(self, name: str | None = None) -> Shelf:
        n = 1
        names = {s.name for s in self.shelves}
        while f"Shelf {n}" in names:
            n += 1
        shelf = Shelf(id=uuid.uuid4().hex, name=name or f"Shelf {n}")
        self.shelves.append(shelf)
        self.active_id = shelf.id
        self._touch()
        return shelf

    def set_active(self, shelf_id: str) -> None:
        if self.get(shelf_id) and shelf_id != self.active_id:
            self.active_id = shelf_id
            self._touch()

    def rename(self, shelf_id: str, name: str) -> None:
        shelf = self.get(shelf_id)
        name = name.strip()
        if shelf and name and shelf.name != name:
            shelf.name = name
            self._touch()

    def delete_shelf(self, shelf_id: str) -> None:
        shelf = self.get(shelf_id)
        if not shelf:
            return
        self._discard_blobs(shelf.items)
        self.shelves = [s for s in self.shelves if s.id != shelf_id]
        if not self.shelves:
            self.shelves = [Shelf(id=uuid.uuid4().hex, name="Shelf 1")]
        if self.active_id == shelf_id:
            self.active_id = self.shelves[-1].id
        self._touch()

    # ── items ────────────────────────────────────────────────────
    def add_items(self, items: list[Item], shelf_id: str | None = None) -> None:
        if not items:
            return
        shelf = self.get(shelf_id) if shelf_id else self.active
        assert shelf is not None
        existing = {(i.kind, i.path, i.url, i.text) for i in shelf.items}
        for item in items:
            key = (item.kind, item.path, item.url, item.text)
            if key not in existing:
                shelf.items.append(item)
                existing.add(key)
        self._touch()

    def replace_item(self, item_id: str, new_item: Item) -> None:
        for shelf in self.shelves:
            for index, item in enumerate(shelf.items):
                if item.id == item_id:
                    new_item.id = item_id
                    shelf.items[index] = new_item
                    self._touch()
                    return

    def remove_items(self, ids: set[str], shelf_id: str | None = None) -> None:
        shelf = self.get(shelf_id) if shelf_id else self.active
        if not shelf or not ids:
            return
        gone = [i for i in shelf.items if i.id in ids]
        shelf.items = [i for i in shelf.items if i.id not in ids]
        self._discard_blobs(gone)
        self._touch()

    def clear(self, shelf_id: str | None = None) -> None:
        shelf = self.get(shelf_id) if shelf_id else self.active
        if shelf and shelf.items:
            self._discard_blobs(shelf.items)
            shelf.items = []
            self._touch()

    # ── captured content ─────────────────────────────────────────
    def new_blob_path(self, ext: str) -> Path:
        BLOB_DIR.mkdir(parents=True, exist_ok=True)
        return BLOB_DIR / f"{uuid.uuid4().hex}.{ext.lstrip('.')}"

    def _discard_blobs(self, items: list[Item]) -> None:
        for item in items:
            if item.kind == IMAGE and item.path and Path(item.path).parent == BLOB_DIR:
                try:
                    os.remove(item.path)
                except OSError:
                    pass
