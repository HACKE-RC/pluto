"""Shake-to-summon. Wayland hides the pointer from clients, so on Hyprland we poll its IPC socket for the cursor."""

from __future__ import annotations

import os
import socket
import threading
import time
from collections import deque
from typing import Callable

from gi.repository import GLib


def hypr_socket_path() -> str | None:
    sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if not sig or not runtime:
        return None
    path = os.path.join(runtime, "hypr", sig, ".socket.sock")
    return path if os.path.exists(path) else None


def cursor_pos(path: str) -> tuple[float, float] | None:
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            s.connect(path)
            s.sendall(b"cursorpos")
            data = s.recv(64).decode()
        x, y = data.split(",")
        return float(x), float(y)
    except (OSError, ValueError):
        return None


class ShakeDetector:
    """Fires when the pointer reverses horizontal direction `reversals` times within `window_ms`,
    each leg travelling at least `travel` logical pixels."""

    def __init__(self, on_shake: Callable[[float, float], None], *, interval_ms: int = 25, window_ms: int = 500,
                 travel: int = 25, reversals: int = 3, cooldown_ms: int = 1200):
        self.on_shake = on_shake
        self.interval = interval_ms / 1000
        self.window = window_ms / 1000
        self.travel = travel
        self.reversals = reversals
        self.cooldown = cooldown_ms / 1000
        self.samples: deque[tuple[float, float, float]] = deque()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> bool:
        path = hypr_socket_path()
        if not path:
            return False
        self._thread = threading.Thread(target=self._run, args=(path,), name="shelf-shake", daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop.set()

    def _run(self, path: str) -> None:
        last_fire = 0.0
        last_move = time.monotonic()
        last_pos: tuple[float, float] | None = None
        while True:
            # Back off to a slow poll once the pointer has been still for a while; a shake can't start without motion.
            idle = time.monotonic() - last_move > 1.5
            if self._stop.wait(self.interval * (6 if idle else 1)):
                return
            pos = cursor_pos(path)
            if pos is None:
                continue
            now = time.monotonic()
            if pos != last_pos:
                last_pos = pos
                last_move = now
            self.samples.append((now, *pos))
            while self.samples and now - self.samples[0][0] > self.window:
                self.samples.popleft()
            if now - last_fire > self.cooldown and self._is_shake():
                last_fire = now
                self.samples.clear()
                GLib.idle_add(self.on_shake, pos[0], pos[1])

    def _is_shake(self) -> bool:
        if len(self.samples) < 4:
            return False
        legs = 0
        direction = 0
        leg_start = self.samples[0][1]
        prev_x = leg_start
        for _, x, _ in self.samples:
            step = x - prev_x
            prev_x = x
            if step == 0:
                continue
            new_dir = 1 if step > 0 else -1
            if new_dir != direction:
                if direction != 0 and abs(x - step - leg_start) >= self.travel:
                    legs += 1
                direction = new_dir
                leg_start = x - step
        if direction != 0 and abs(prev_x - leg_start) >= self.travel:
            legs += 1
        return legs - 1 >= self.reversals
