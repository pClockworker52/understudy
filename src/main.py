"""
Main application. Wires together all components.
"""

import sys
import os
import threading
from pathlib import Path
from datetime import datetime
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal

from google import genai

from observer import UIObserver, UIEvent
from trigger import IdleTrigger
from gimp_bridge import GimpBridge
from app_knowledge import get_context_for_app
from session import SessionLog
from analyzer import SessionAnalyzer
from predictor import Predictor
from executor import Executor
from overlay import Overlay

# Window titles to ignore for trigger purposes
IGNORED_WINDOWS = {"understudy", "anaconda prompt", "skript-fu", "script-fu"}


class Assistant(QObject):
    predictions_ready = pyqtSignal(list)  # List[WorkflowBatch]
    status_update = pyqtSignal(str)

    def __init__(self, api_key: str, overlay: Overlay):
        super().__init__()

        self.overlay = overlay

        # Google GenAI client
        self.genai_client = genai.Client(api_key=api_key)

        # Components
        self.event_log = []
        self.observer = UIObserver(on_event=self._on_ui_event)
        self.trigger = IdleTrigger(on_trigger=self._on_trigger)

        # GIMP bridge (optional Layer 2)
        self.gimp = GimpBridge()
        self.gimp_available = self.gimp.is_connected()

        self.predictor = Predictor(self.genai_client)
        self.executor = Executor(gimp_bridge=self.gimp if self.gimp_available else None)
        self.analyzer = SessionAnalyzer(self.genai_client)

        # Session
        self.session = SessionLog(
            session_id=datetime.now().strftime("%Y%m%d_%H%M%S"),
            application="detecting...",
            start_time=datetime.now().isoformat(),
        )

        # State
        self.current_app_context = ""
        self.current_workflows = []
        self.last_batch_result = None
        self.last_executed_workflow = ""  # Prevent re-suggesting same workflow
        self.recently_executed = []  # Track last N executed action names
        self.detected_app = ""
        self._predicting = False  # Lock to prevent concurrent predictions
        self._executing = False   # Lock to prevent triggers during execution

    def start(self):
        self.observer.start()
        self.trigger.start()
        if self.gimp_available:
            self.status_update.emit("GIMP bridge connected")
            print("[main] GIMP Script-Fu bridge connected")
        else:
            self.status_update.emit("Observing (no GIMP bridge)")
            print("[main] No GIMP bridge - using Layer 1 + 3 only")

    def _try_passive_bridge(self):
        """Check if Script-Fu server is already running (no auto-start)."""
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.5)
            s.connect(("localhost", 10008))
            s.close()
            print("[main] Script-Fu port 10008 is open, testing bridge...")
            # Server is running, connect bridge
            self.gimp_available = self.gimp.is_connected()
            if self.gimp_available:
                self.executor.gimp = self.gimp
                self.status_update.emit("GIMP Script-Fu bridge connected!")
                print("[main] GIMP Script-Fu bridge connected!")
            else:
                print("[main] Port open but bridge query failed")
        except socket.timeout:
            pass  # Server not running
        except ConnectionRefusedError:
            pass  # Server not running
        except Exception as e:
            print(f"[main] Bridge check error: {e}")

    def stop(self):
        self.observer.stop()
        self.trigger.stop()
        self.session.save(Path.home() / ".understudy" / "sessions")

    def _on_ui_event(self, event: UIEvent):
        """Called on every UI Automation event."""
        # Ignore events from our own window
        if event.source_app and any(w in event.source_app.lower() for w in IGNORED_WINDOWS):
            return

        self.event_log.append(event)
        self.trigger.notify_event(event.event_type)
        if event.event_type != "mouse_activity":
            print(f"[event] {event.event_type}: {event.element_name}")

        self.session.add_event(event.event_type, {
            "name": event.element_name,
            "element_type": event.element_type,
        })

        if event.event_type == "window_title_change":
            ctx = get_context_for_app(event.source_app)
            if ctx != self.current_app_context:
                self.current_app_context = ctx
                self.detected_app = event.source_app
                self.session.application = event.source_app
                # Update executor target app + capabilities
                if "gimp" in event.source_app.lower() or "gnu image" in event.source_app.lower():
                    self.executor.target_app = "GIMP"
                    self.executor.menu_search_key = "slash"  # GIMP's '/' action search
                    # Passively check if Script-Fu server is already running
                    if not self.gimp_available:
                        self._try_passive_bridge()
                elif "freecad" in event.source_app.lower():
                    self.executor.target_app = "FreeCAD"
                    self.executor.menu_search_key = None  # No action search
                else:
                    self.executor.target_app = event.source_app
                    self.executor.menu_search_key = None

    def _on_trigger(self):
        """Called when idle trigger or hotkey fires."""
        # Don't fire while predictions are showing, predicting, or executing
        if self.overlay.HAS_PREDICTIONS:
            return
        if self._predicting:
            return
        if self._executing:
            return

        self._predicting = True
        print("[trigger] Idle trigger fired! Sending to Gemini...")
        self.status_update.emit("Analyzing...")

        # Re-check Script-Fu bridge on every trigger (user may have started it)
        if not self.gimp_available and "GIMP" in self.executor.target_app:
            self._try_passive_bridge()

        action_text = self.observer.get_recent_events_as_text(self.event_log)
        gimp_text = self.gimp.get_state_as_text() if self.gimp_available else ""
        last_wf = self.last_executed_workflow
        recent_exec = list(self.recently_executed)

        def _predict():
            try:
                result = self.predictor.predict(
                    action_log_text=action_text,
                    app_context=self.current_app_context,
                    gimp_state_text=gimp_text,
                    script_fu_available=self.gimp_available,
                    last_executed_workflow=last_wf,
                    recently_executed=recent_exec,
                )

                self.current_workflows = result.workflows
                self.session.predictions_offered += len(result.workflows)

                self.predictions_ready.emit(result.workflows)

                if result.workflows:
                    names = ", ".join(
                        f"{wf.workflow_name} ({len(wf.steps)})"
                        for wf in result.workflows
                    )
                    self.status_update.emit(
                        f"{len(result.workflows)} workflows ({result.latency_ms}ms)"
                    )
                    print(f"[predict] {len(result.workflows)} workflows: {names}")
                else:
                    self.status_update.emit("No workflows found")
                    print("[predict] No multi-step workflows found")
            except Exception as e:
                print(f"[predict] Error: {e}")
                self.status_update.emit("Prediction failed")
            finally:
                self._predicting = False

        threading.Thread(target=_predict, daemon=True).start()

    def execute_prediction(self, index: int):
        """User selected workflow N. Every card triggers batch execution."""
        wf_idx = index - 1
        if wf_idx < 0 or wf_idx >= len(self.current_workflows):
            return

        batch = self.current_workflows[wf_idx]
        print(f"[execute] Running workflow: {batch.workflow_name} ({len(batch.steps)} steps)")
        self.trigger.reset_cooldown()
        self.status_update.emit(f"Running: {batch.workflow_name}...")

        self._executing = True

        def _run_batch():
            try:
                result = self.executor.execute_batch(batch.steps)
                self.last_batch_result = result
            except Exception as e:
                print(f"[execute] Exception: {e}")
                self._executing = False
                return

            if result.success:
                self.session.predictions_accepted += 1
                self.session.add_event("workflow_executed", {
                    "name": batch.workflow_name,
                    "steps": result.steps_completed,
                })
                self.last_executed_workflow = batch.workflow_name
                for step in batch.steps[:result.steps_completed]:
                    self._track_executed(step.action_name)
                self.event_log.clear()
                self.status_update.emit(
                    f"{batch.workflow_name} done ({result.steps_completed} steps) [Ctrl+Z to undo]"
                )
                print(f"[execute] Batch completed: {result.steps_completed} steps")
            elif result.interrupted:
                self.status_update.emit(
                    f"Interrupted after {result.steps_completed}/{result.total_steps} steps"
                )
            else:
                self.status_update.emit(f"Failed: {result.error}")
                print(f"[execute] Batch failed: {result.error}")

            self._executing = False

        threading.Thread(target=_run_batch, daemon=True).start()

    def _track_executed(self, action_name: str):
        """Track recently executed actions for deduplication."""
        self.recently_executed.append(action_name)
        # Keep only last 10
        if len(self.recently_executed) > 10:
            self.recently_executed = self.recently_executed[-10:]

    def generate_user_md(self):
        """Generate USER.md from current session."""
        output_path = Path.home() / ".understudy" / "USER.md"
        sessions = [self.session]
        md = self.analyzer.analyze_and_generate(sessions, self.detected_app, output_path)
        self.status_update.emit(f"USER.md generated -> {output_path}")
        return md


def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: Set GEMINI_API_KEY environment variable")
        print("  PowerShell: $env:GEMINI_API_KEY = 'your-key-here'")
        sys.exit(1)

    os.environ["QT_LOGGING_RULES"] = "qt.qpa.window=false"
    app = QApplication(sys.argv)

    # Create components
    overlay = Overlay()
    assistant = Assistant(api_key, overlay)

    # Wire signals
    assistant.predictions_ready.connect(overlay.show_predictions)
    assistant.status_update.connect(overlay.set_status)
    overlay.prediction_selected.connect(assistant.execute_prediction)
    overlay.dismiss_requested.connect(overlay.clear_predictions)

    # Esc during batch execution -> interrupt
    overlay.dismiss_requested.connect(assistant.executor.interrupt)

    # Exit button
    overlay.exit_requested.connect(app.quit)

    # Global hotkey for manual trigger (Ctrl+Space)
    try:
        from pynput import keyboard
        def on_hotkey():
            assistant.trigger.force_trigger()
        hotkey_listener = keyboard.GlobalHotKeys({
            '<ctrl>+<space>': on_hotkey
        })
        hotkey_listener.start()
        print("[main] Ctrl+Space hotkey registered")
    except ImportError:
        print("[main] Warning: pynput not installed, Ctrl+Space hotkey disabled")

    # Start
    overlay.position_bottom_right()
    overlay.show()
    assistant.start()
    print("[main] Understudy started. Predictions appear after idle. Works with any Windows app.")

    # On exit, save session and generate USER.md
    def on_exit():
        assistant.stop()
        try:
            assistant.generate_user_md()
        except Exception as e:
            print(f"Could not generate USER.md: {e}")

    app.aboutToQuit.connect(on_exit)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
