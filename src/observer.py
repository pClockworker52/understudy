"""
Universal Windows UI observation via UI Automation.
Works on any Win32/UIA application -- no app-specific code.

Uses win32gui for reliable foreground window detection (works with GTK apps
like GIMP that don't expose UIA focus well), plus mouse position tracking
as a fallback activity signal.
"""

import threading
import time
import ctypes
from dataclasses import dataclass, field
from typing import List, Callable, Optional
from datetime import datetime


@dataclass
class UIEvent:
    timestamp: str
    event_type: str       # "focus_change", "menu_click", "button_click", "window_title_change", "mouse_activity"
    source_app: str       # Window title of source
    element_name: str     # Name of UI element
    element_type: str     # "MenuItem", "Button", "ToolBar", etc.
    details: dict = field(default_factory=dict)


# Win32 API for reliable foreground window detection
user32 = ctypes.windll.user32


def _get_foreground_title() -> str:
    """Get foreground window title using win32 API (works with GTK/GIMP)."""
    hwnd = user32.GetForegroundWindow()
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def _get_cursor_pos() -> tuple:
    """Get current cursor position."""
    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
    pt = POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return (pt.x, pt.y)


class UIObserver:
    """
    Polls foreground window and cursor for changes.

    Uses win32gui directly instead of pywinauto for the main loop,
    since GTK apps (like GIMP) don't expose UIA focus changes reliably.
    Falls back to mouse movement detection as an activity signal.
    """

    POLL_INTERVAL = 0.3   # seconds
    MOUSE_MOVE_THRESHOLD = 20  # pixels -- ignore tiny jitter

    def __init__(self, on_event: Callable[[UIEvent], None]):
        self.on_event = on_event
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_window_title = ""
        self._last_mouse_pos = (0, 0)
        self._last_mouse_event_time = 0

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def _poll_loop(self):
        while self._running:
            try:
                title = _get_foreground_title()

                # Detect window title change
                if title and title != self._last_window_title:
                    self.on_event(UIEvent(
                        timestamp=datetime.now().isoformat(),
                        event_type="window_title_change",
                        source_app=title,
                        element_name=title,
                        element_type="Window",
                        details={"previous": self._last_window_title}
                    ))
                    self._last_window_title = title

                # Detect significant mouse movement as activity signal
                pos = _get_cursor_pos()
                dx = abs(pos[0] - self._last_mouse_pos[0])
                dy = abs(pos[1] - self._last_mouse_pos[1])
                now = time.time()

                if (dx + dy) > self.MOUSE_MOVE_THRESHOLD:
                    self._last_mouse_pos = pos
                    # Rate-limit mouse events to max 1 per second
                    if now - self._last_mouse_event_time > 1.0:
                        self._last_mouse_event_time = now
                        self.on_event(UIEvent(
                            timestamp=datetime.now().isoformat(),
                            event_type="mouse_activity",
                            source_app=title or self._last_window_title,
                            element_name=f"cursor at ({pos[0]}, {pos[1]})",
                            element_type="Mouse",
                        ))

            except Exception:
                pass  # Window query can fail during transitions

            time.sleep(self.POLL_INTERVAL)

    def get_recent_events_as_text(self, events: List[UIEvent], limit: int = 15) -> str:
        """Format recent events as compact text for Gemini context."""
        recent = events[-limit:]
        lines = []
        for e in recent:
            if e.event_type == "window_title_change":
                lines.append(f"[Window] {e.element_name}")
            elif e.event_type == "focus_change":
                lines.append(f"[Focus] {e.element_type}: {e.element_name}")
            elif e.event_type == "menu_click":
                lines.append(f"[Menu] {e.element_name}")
            elif e.event_type == "button_click":
                lines.append(f"[Button] {e.element_name}")
            elif e.event_type == "mouse_activity":
                lines.append(f"[Mouse] {e.element_name}")
            else:
                lines.append(f"[{e.event_type}] {e.element_name}")
        return "\n".join(lines)


if __name__ == "__main__":
    # Standalone test: print events for 30 seconds
    def print_event(event):
        print(f"  {event.event_type}: {event.element_name} ({event.element_type}) in '{event.source_app}'")

    obs = UIObserver(on_event=print_event)
    print("Observing UI events for 30 seconds... Switch windows and click around.")
    obs.start()
    try:
        time.sleep(30)
    except KeyboardInterrupt:
        pass
    obs.stop()
    print("Done.")
