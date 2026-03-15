# Understudy -- Architecture

```
+------------------------------------------------------------------+
|                    USER'S DESKTOP (Windows 11)                    |
|                                                                   |
|   +-------------+  +-------------+  +-------------+              |
|   |    GIMP     |  |   FreeCAD   |  |  Any App    |              |
|   +------+------+  +------+------+  +------+------+              |
|          |                |                |                      |
+----------|----------------|----------------|---------------------+
           |                |                |
           v                v                v
+------------------------------------------------------------------+
|                   OBSERVATION LAYERS                              |
|                                                                   |
|  Layer 1: Win32 UI Events (ctypes/win32gui)                      |
|    - Window title changes, focus tracking                        |
|    - App detection: GIMP / FreeCAD / generic                     |
|                                                                   |
|  Layer 2: App Scripting Bridges                                  |
|    - GIMP Script-Fu TCP server (port 10008)                      |
|    - Image state, selection, layers, tool info                   |
|    - Direct programmatic execution                               |
|                                                                   |
|  Layer 3: Screenshot Capture (mss)                               |
|    - 720x540 JPEG on each trigger                                |
|    - Visual grounding for Gemini                                 |
+---------------------------+--------------------------------------+
                            |
                            v
+------------------------------------------------------------------+
|                      TRIGGER ENGINE                               |
|                                                                   |
|  Idle detection (2s threshold) + Ctrl+Space manual trigger       |
|  Cooldown management (5s between predictions)                    |
+---------------------------+--------------------------------------+
                            |
              Context package: action log + screenshot
              + app knowledge + GIMP state (if connected)
                            |
                            v
+------------------------------------------------------------------+
|                   GEMINI 2.5 FLASH                                |
|                                                                   |
|  Google GenAI SDK  |  thinking_budget=0 (fast mode)              |
|                                                                   |
|  Input:  Action history + Screenshot + App context               |
|  Output: 2-3 workflow suggestions (JSON)                         |
|          Each workflow = 2-6 executable steps                    |
|                                                                   |
|  Execution validation:                                           |
|    - Reject shortcuts > 30 chars                                 |
|    - Reject comma-chained shortcuts                              |
|    - Reject text-editing keys (Backspace, Home, End)             |
+---------------------------+--------------------------------------+
                            |
                            v
+------------------------------------------------------------------+
|                    PYQT6 OVERLAY                                  |
|                                                                   |
|  +--------------------------------------------------+           |
|  | Understudy > GIMP            Analyzing...    [X] |           |
|  |                                                   |           |
|  | [1] Isolate subject with transparency  (4 steps)  |           |
|  | [2] Export as PNG with transparency    (1 step)   |           |
|  | [3] Add colored background layer      (3 steps)  |           |
|  |                                                   |           |
|  | [1-3] Run workflow  [Esc] Dismiss                 |           |
|  +--------------------------------------------------+           |
|                                                                   |
|  Always-on-top | Frameless | Draggable | Keyboard-driven        |
+---------------------------+--------------------------------------+
                            |
                     User clicks [1]
                            |
                            v
+------------------------------------------------------------------+
|                     EXECUTOR                                      |
|                                                                   |
|  Three execution modes (per step):                               |
|                                                                   |
|  "shortcut"      -> pyautogui.hotkey("ctrl","i")                 |
|  "menu_search"   -> Press '/' + type action name + Enter         |
|  "script_fu"     -> TCP send to GIMP Script-Fu server            |
|                                                                   |
|  Sequential execution with 0.5s delay between steps             |
|  Focus management: bring target app to foreground first          |
+------------------------------------------------------------------+
```

## Data Flow Summary

1. User works normally in any Windows application
2. Understudy observes via 3 layers (events + bridge + screenshot)
3. On idle (2s) or Ctrl+Space, context is sent to Gemini 2.5 Flash
4. Gemini returns 2-3 multi-step workflow suggestions
5. Suggestions validated (reject hallucinated shortcuts)
6. Overlay shows suggestions; user picks one with keyboard or click
7. Executor runs the workflow: shortcuts, menu search, or Script-Fu
8. Cycle repeats -- new suggestions appear based on updated context
