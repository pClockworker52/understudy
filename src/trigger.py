"""
Detects natural decision points where prediction is most useful.

Primary trigger: UI events stop for >1.5 seconds after a tool/focus change.
Fallback trigger: User presses Ctrl+Space.
"""

import time
import threading
from typing import Callable, Optional


class IdleTrigger:

    IDLE_THRESHOLD = 2.0    # seconds of inactivity after last event
    COOLDOWN = 5.0          # minimum seconds between triggers

    def __init__(self, on_trigger: Callable):
        self.on_trigger = on_trigger
        self._last_event_time = time.time()
        self._last_trigger_time = 0
        self._had_meaningful_event = False
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def notify_event(self, event_type: str):
        """Called by observer when UI event occurs."""
        self._last_event_time = time.time()
        if event_type in ("focus_change", "menu_click", "button_click", "window_title_change", "mouse_activity"):
            self._had_meaningful_event = True

    def reset_cooldown(self):
        """Call after executing a prediction to prevent immediate re-trigger."""
        self._last_trigger_time = time.time()
        self._had_meaningful_event = False

    def force_trigger(self):
        """Manual trigger from hotkey."""
        now = time.time()
        if now - self._last_trigger_time >= self.COOLDOWN:
            self._last_trigger_time = now
            self._had_meaningful_event = False
            self.on_trigger()

    def _monitor_loop(self):
        while self._running:
            now = time.time()
            idle_time = now - self._last_event_time
            cooldown_ok = (now - self._last_trigger_time) >= self.COOLDOWN

            if idle_time >= self.IDLE_THRESHOLD and self._had_meaningful_event and cooldown_ok:
                self._last_trigger_time = now
                self._had_meaningful_event = False
                self.on_trigger()

            time.sleep(0.2)
