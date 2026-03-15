"""
Execute predictions in target application.
Supports single-step and batch (workflow) execution.
GIMP Script-Fu preferred, pyautogui as fallback.
"""

import time
import ctypes
import pyautogui
from typing import List
from dataclasses import dataclass

pyautogui.FAILSAFE = True   # Move mouse to corner to abort
pyautogui.PAUSE = 0.1

user32 = ctypes.windll.user32


def _find_and_focus_window(title_substring: str) -> bool:
    """Find a window by partial title and bring it to foreground."""
    import ctypes.wintypes

    result = [None]

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    def enum_callback(hwnd, lparam):
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        if title_substring.lower() in buf.value.lower():
            if user32.IsWindowVisible(hwnd):
                result[0] = hwnd
                return False  # Stop enumeration
        return True

    user32.EnumWindows(enum_callback, 0)

    if result[0]:
        user32.SetForegroundWindow(result[0])
        time.sleep(0.15)  # Wait for window to come to front
        return True
    return False


@dataclass
class BatchResult:
    success: bool
    steps_completed: int
    total_steps: int
    interrupted: bool = False
    error: str = ""


GIMP_KEY_FIXES = {
    "delete": "Delete",           # GIMP does handle Delete for clearing
    "ctrl+shift+f": "Ctrl+Shift+F",  # Normalize casing
}


class Executor:

    BATCH_STEP_DELAY = 0.5   # seconds between batch steps (let GIMP process)

    def __init__(self, gimp_bridge=None, target_app: str = "GIMP"):
        self.gimp = gimp_bridge
        self.target_app = target_app
        self.menu_search_key = "slash"  # GIMP default; None = not available
        self._interrupted = False

    def interrupt(self):
        """Signal to stop batch execution. Called from UI thread."""
        self._interrupted = True

    def _ensure_target_focused(self):
        """Bring the target application to foreground before executing."""
        _find_and_focus_window(self.target_app)

    # --- Single-step execution (Mode A) ---

    def execute(self, prediction) -> bool:
        """Execute a single prediction. Returns True on success."""
        self._interrupted = False

        print(f"[executor] {prediction.action_name}: type={prediction.execution_type}, data={prediction.execution_data}")

        # Safety: reject absurdly long execution_data (hallucinated key sequences)
        if prediction.execution_type == "shortcut" and len(prediction.execution_data) > 30:
            print(f"[executor] REJECTED: execution_data too long ({len(prediction.execution_data)} chars)")
            return False

        if prediction.execution_type == "script_fu" and self.gimp:
            return self.gimp.execute(prediction.execution_data)

        if prediction.execution_type == "script_fu" and not self.gimp:
            print(f"[executor] WARNING: script_fu requested but bridge not connected, skipping")
            return False

        if prediction.execution_type == "menu_search":
            self._ensure_target_focused()
            return self._do_menu_search(prediction.execution_data)

        if prediction.execution_type == "shortcut":
            if not prediction.execution_data or prediction.execution_data.strip() == "":
                print(f"[executor] Guidance only (no automation): {prediction.action_name}")
                return True  # Guidance shown, counts as "success"
            self._ensure_target_focused()
            return self._do_shortcut(prediction.execution_data)

        return False

    # --- Batch execution (Mode B) ---

    def execute_batch(self, steps: List) -> BatchResult:
        """
        Execute a sequence of mechanical steps.
        Can be interrupted between steps (not mid-step).
        """
        self._interrupted = False
        self._ensure_target_focused()
        completed = 0

        for i, step in enumerate(steps):
            if self._interrupted:
                return BatchResult(
                    success=False,
                    steps_completed=completed,
                    total_steps=len(steps),
                    interrupted=True,
                )

            success = self.execute(step)
            if not success:
                return BatchResult(
                    success=False,
                    steps_completed=completed,
                    total_steps=len(steps),
                    error=f"Step {i+1} failed: {step.action_name}",
                )

            completed += 1

            if i < len(steps) - 1:
                time.sleep(self.BATCH_STEP_DELAY)

        return BatchResult(
            success=True,
            steps_completed=completed,
            total_steps=len(steps),
        )

    # --- Undo support ---

    def undo(self, count: int = 1) -> int:
        """Undo N actions. Returns how many were undone."""
        self._ensure_target_focused()
        undone = 0
        for _ in range(count):
            if self._do_shortcut("Ctrl+Z"):
                undone += 1
                time.sleep(0.1)
        return undone

    def undo_batch(self, batch_result: BatchResult) -> bool:
        """Undo all steps of a completed batch."""
        undone = self.undo(batch_result.steps_completed)
        return undone == batch_result.steps_completed

    # --- Low-level execution ---

    def _do_menu_search(self, search_term: str) -> bool:
        """Execute an action via the app's action search dialog (e.g., GIMP's '/')."""
        if self.menu_search_key is None:
            print(f"[executor] menu_search not available for {self.target_app}, skipping: {search_term}")
            return False
        try:
            pyautogui.press(self.menu_search_key)
            time.sleep(0.5)
            pyautogui.typewrite(search_term, interval=0.03)
            time.sleep(0.5)
            pyautogui.press('enter')
            time.sleep(0.3)
            return True
        except Exception as e:
            print(f"[executor] menu_search failed: {e}")
            return False

    def _do_shortcut(self, keys: str) -> bool:
        """Execute keyboard shortcut via pyautogui.
        Supports both held combos (Ctrl+I) and sequential keys (V+F for FreeCAD).
        """
        try:
            parts = keys.replace("+", " ").split()
            modifier_keys = {"ctrl", "shift", "alt"}
            key_map = {"ctrl": "ctrl", "shift": "shift", "alt": "alt",
                       "escape": "escape", "enter": "enter"}
            mapped = [key_map.get(p.lower(), p.lower()) for p in parts]

            # Check if this is a sequential shortcut (no modifiers, multiple keys)
            has_modifiers = any(k in modifier_keys for k in mapped)
            if not has_modifiers and len(mapped) > 1:
                # Sequential: press each key separately (e.g., V then F in FreeCAD)
                for key in mapped:
                    pyautogui.press(key)
                    time.sleep(0.25)
            else:
                # Standard combo: hold modifiers + press key (e.g., Ctrl+I)
                pyautogui.hotkey(*mapped)
            return True
        except Exception:
            return False
