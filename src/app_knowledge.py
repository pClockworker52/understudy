"""
Static application knowledge for grounding predictions.
Loaded once per detected app. Kept small (<500 tokens).

Philosophy: Gemini already knows app shortcuts from training data.
This context tells it things it DOESN'T know:
  - Which execution method to prefer (script_fu vs shortcut)
  - App-specific gotchas
  - Common workflow patterns to match against

Also contains console/server activation procedures for each app.
"""

import time
import socket
import pyautogui

pyautogui.FAILSAFE = True


# --- App Context (sent to Gemini) ---

GIMP_CONTEXT = """APPLICATION: GIMP (GNU Image Manipulation Program)
NOTE: This is a German-locale GIMP install. Menu names may be in German.

EXECUTION PREFERENCE: Use menu_search for most operations (types '/' to open
GIMP's action search, types the English action name, presses Enter). Use shortcuts
only for well-known defaults (Ctrl+I, Ctrl+Z, Delete, Ctrl+Shift+E).
If Script-Fu bridge is connected, prefer script_fu over everything.
Script-Fu is MORE POWERFUL than shortcuts — it can do multi-step operations in a single command.

SCRIPT-FU WORKFLOW EXAMPLES (use when bridge is connected):
  IMPORTANT: Only use functions verified for GIMP 2.10. Do NOT use script-fu-vignette,
  gimp-hue-saturation, gimp-color-balance, or gimp-context-get-tool.

  Subject isolation (one command does feather+invert+alpha+clear!):
    (let* ((image (car (gimp-image-list))) (drawable (car (gimp-image-get-active-drawable image)))) (gimp-selection-feather image 5) (gimp-selection-invert image) (gimp-layer-add-alpha drawable) (gimp-edit-clear drawable) (gimp-displays-flush))

  Add colored background layer behind isolated subject:
    (let* ((image (car (gimp-image-list))) (width (car (gimp-image-width image))) (height (car (gimp-image-height image))) (layer (car (gimp-layer-new image width height RGBA-IMAGE "Background" 100 LAYER-MODE-NORMAL)))) (gimp-image-insert-layer image layer 0 -1) (gimp-image-set-active-layer image layer) (gimp-context-set-foreground '(41 128 185)) (gimp-edit-fill layer FILL-FOREGROUND) (gimp-displays-flush))

  Auto enhance (curves + sharpen in one command):
    (let* ((image (car (gimp-image-list))) (drawable (car (gimp-image-get-active-drawable image)))) (gimp-curves-spline drawable HISTOGRAM-VALUE 10 #(0 0 64 50 128 140 192 215 255 255)) (plug-in-unsharp-mask RUN-NONINTERACTIVE image drawable 3.0 0.5 0) (gimp-displays-flush))

  Brightness + contrast adjustment:
    (let* ((image (car (gimp-image-list))) (drawable (car (gimp-image-get-active-drawable image)))) (gimp-brightness-contrast drawable 20 30) (gimp-displays-flush))

  Convert to black and white + sharpen:
    (let* ((image (car (gimp-image-list))) (drawable (car (gimp-image-get-active-drawable image)))) (gimp-drawable-desaturate drawable DESATURATE-LUMINOSITY) (plug-in-unsharp-mask RUN-NONINTERACTIVE image drawable 2.0 0.4 0) (gimp-displays-flush))

  Resize for web (scale to 800px wide + sharpen):
    (let* ((image (car (gimp-image-list))) (drawable (car (gimp-image-get-active-drawable image))) (ratio (/ 800.0 (car (gimp-image-width image)))) (new-h (inexact->exact (round (* ratio (car (gimp-image-height image))))))) (gimp-image-scale-full image 800 new-h INTERPOLATION-CUBIC) (plug-in-unsharp-mask RUN-NONINTERACTIVE image (car (gimp-image-get-active-drawable image)) 2.0 0.3 0) (gimp-displays-flush))

  Flatten and prepare for export:
    (let* ((image (car (gimp-image-list)))) (gimp-image-flatten image) (gimp-displays-flush))

COMMON WORKFLOWS (for workflow matching - use when Script-Fu is NOT connected):
  Subject isolation (user selected the SUBJECT with a selection tool):
    CORRECT ORDER: Feather > INVERT SELECTION (Ctrl+I) > Add Alpha Channel > Clear (Delete)
    WARNING: You MUST invert the selection! The user selected the subject they want to KEEP.
    Inverting selects the BACKGROUND, then Clear removes the background.
    If you skip Invert, you will DELETE THE SUBJECT instead of the background!

  Color correction: Colors > Levels or Curves > Export
  Resize for web: Image > Scale Image > Flatten Image > Export As
  Crop and export: Crop to selection > Flatten > Export As
  Sharpen and export: Unsharp Mask > Export As
  Batch color adjust: Brightness-Contrast > Hue-Saturation > Export As
  Remove background + new bg: Isolate subject > New Layer > Fill with color > Flatten > Export
  Prepare for print: Scale Image (300 DPI) > Flatten Image > Export As TIFF

POST-WORKFLOW IDEAS (suggest these AFTER a workflow completes):
  After subject isolation: "Export as PNG" (transparency!), "Add new background layer",
    "Apply drop shadow", "Flatten and export as JPG", "Scale for web"
  After color correction: "Export As", "Sharpen", "Compare with original (Undo/Redo)"
  After resize: "Sharpen (Unsharp Mask)", "Export As"
  General: "Flatten Image", "Export As PNG", "Scale Image"

GIMP GOTCHAS (things users get wrong):
  - "Save" only saves .xcf. Use "Export As" (Ctrl+Shift+E) for PNG/JPG
  - Must add alpha channel BEFORE clearing, or you get white not transparency
  - "Delete" key sends to edit-clear
  - Scale Layer != Scale Image -- users confuse these constantly
  - INVERT SELECTION (Ctrl+I) before clearing background -- otherwise you delete the subject!
"""

FREECAD_CONTEXT = """APPLICATION: FreeCAD (3D Parametric Modeler)

EXECUTION PREFERENCE: Use execution_type "shortcut" ONLY.
menu_search is NOT available for FreeCAD. Do NOT use execution_type "menu_search".

SEQUENTIAL SHORTCUTS: FreeCAD uses two-key sequences (press first key, release, press second).
Format these as "V+F" (the executor handles them as sequential presses).

VIEW SHORTCUTS (V + key):
  V+F = Fit All, V+S = Fit Selection, V+O = Orthographic, V+P = Perspective

STANDARD VIEWS (single number key):
  0 = Isometric, 1 = Front, 2 = Top, 3 = Right, 4 = Rear, 5 = Bottom, 6 = Left

OBJECT/GENERAL:
  Space = Toggle visibility of selected object (VERY useful for assemblies!)
  Ctrl+Z = Undo, Ctrl+Y = Redo, Ctrl+S = Save
  Ctrl+E = Export, Ctrl+I = Import, Ctrl+B = Box Zoom
  F2 = Rename selected item, Delete = Delete selected
  Ctrl+D = Set Appearance (color/transparency of selected object)
  Esc = Toggle navigation/edit mode

SAFETY: Do NOT automate Sketcher constraint shortcuts (H, V, C, E, etc.) — applying
constraints blindly can damage the model. Only automate VIEW, VISIBILITY, and EXPORT operations.

WORKFLOW EXAMPLES (safe for automation):
  "Complete view tour": 1 (front) + 3 (right) + 2 (top) + 0 (isometric) + V+F (fit all)
  "Inspect internals": Space (hide selected) + V+F (fit all) + V+P (perspective)
  "Focus on part": V+S (fit selection) + V+P (perspective)
  "Save and export": Ctrl+S (save) + Ctrl+E (export)
  "Change appearance": Ctrl+D (appearance dialog for color/transparency)
  "Compare views": V+O (orthographic) + 1 (front) ... then V+P (perspective) + 0 (isometric)
  "Quick inspection": 1 (front) + 2 (top) + 3 (right) + V+F (fit)
  "Hide and inspect": Space (hide) + 2 (top view) + V+F (fit) + V+P (perspective)

SCENE ANALYSIS: Look at the screenshot. Suggest workflows using the shortcuts above.
  - Assembly with many parts: "Hide outer parts" (Space + V+F) or "Inspect internals"
  - Model looks done: "Save and export" (Ctrl+S + Ctrl+E)
  - Need inspection: "View tour" (1, 3, 2, 0, V+F)
  - Single part selected: "Focus on part" (V+S + V+P)
  - Want to change look: "Change appearance" (Ctrl+D)
"""

GENERIC_CONTEXT = """APPLICATION: Windows Desktop Application

Use execution_type "shortcut" for all predictions.
Common shortcuts: Ctrl+S=Save, Ctrl+O=Open, Ctrl+Z=Undo, Ctrl+C=Copy, Ctrl+V=Paste
"""


def get_context_for_app(window_title: str) -> str:
    """Return appropriate context based on detected application."""
    title_lower = window_title.lower()
    if "gimp" in title_lower or "gnu image" in title_lower:
        return GIMP_CONTEXT
    if "freecad" in title_lower:
        return FREECAD_CONTEXT
    return GENERIC_CONTEXT


# --- Console/Server Activation ---

def _check_tcp_port(host: str, port: int, timeout: float = 0.5) -> bool:
    """Check if a TCP port is accepting connections."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False


def _wait_for_port(host: str, port: int, timeout: float = 5.0) -> bool:
    """Wait up to timeout seconds for a TCP port to become available."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _check_tcp_port(host, port):
            return True
        time.sleep(0.3)
    return False


def _wait_for_window(title_substring: str, timeout: float = 5.0) -> bool:
    """Wait for a window with the given title to appear. Returns True if found."""
    import ctypes
    import ctypes.wintypes

    deadline = time.time() + timeout
    while time.time() < deadline:
        found = [False]

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        def enum_cb(hwnd, lparam):
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
            if title_substring.lower() in buf.value.lower():
                if ctypes.windll.user32.IsWindowVisible(hwnd):
                    # Focus it
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
                    found[0] = True
                    return False
            return True

        ctypes.windll.user32.EnumWindows(enum_cb, 0)
        if found[0]:
            return True
        time.sleep(0.3)
    return False


def _activate_gimp_scriptfu(target_window: str = "GIMP") -> bool:
    """
    Start GIMP's Script-Fu server via the action search dialog.
    GIMP 2.10+ supports '/' to open searchable action menu.

    Returns True if server becomes available.
    """
    from executor import _find_and_focus_window

    # Already running?
    if _check_tcp_port("localhost", 10008):
        return True

    print("[app] Starting GIMP Script-Fu server via action search...")

    # Focus GIMP
    if not _find_and_focus_window(target_window):
        print("[app] Could not find GIMP window")
        return False

    time.sleep(0.5)

    try:
        # Open GIMP's action search with '/' key
        pyautogui.press('slash')
        time.sleep(0.8)

        # Type search term
        pyautogui.typewrite('Script-Fu Server', interval=0.04)
        time.sleep(0.8)

        # Select the first result (opens the settings dialog)
        pyautogui.press('enter')

        # Wait for the settings dialog window to actually appear
        # German GIMP: "Skript-Fu-Server-Einstellungen"
        # English GIMP: "Script-Fu Server" or similar
        print("[app] Waiting for Script-Fu server dialog...")
        dialog_found = _wait_for_window("Skript-Fu", timeout=4.0)
        if not dialog_found:
            dialog_found = _wait_for_window("Script-Fu", timeout=2.0)

        if dialog_found:
            print("[app] Dialog found and focused, pressing Enter to start server...")
            time.sleep(0.3)
            pyautogui.press('enter')
        else:
            print("[app] Dialog not found by title, pressing Enter anyway...")
            pyautogui.press('enter')

        # Wait for server to actually start listening
        print("[app] Waiting for Script-Fu server to start...")
        if _wait_for_port("localhost", 10008, timeout=5.0):
            print("[app] Script-Fu server started successfully!")
            return True

        # Retry: maybe a confirmation dialog appeared, refocus and press Enter
        print("[app] Port not responding, retrying...")
        if _wait_for_window("Skript-Fu", timeout=1.0) or _wait_for_window("Script-Fu", timeout=1.0):
            time.sleep(0.2)
            pyautogui.press('enter')
            if _wait_for_port("localhost", 10008, timeout=3.0):
                print("[app] Script-Fu server started successfully (after retry)!")
                return True

    except Exception as e:
        print(f"[app] Auto-start failed: {e}")

    print("[app] Could not auto-start Script-Fu server")
    print("[app] Please start manually: Filters > Script-Fu > Start Server")
    return False


# Registry of app activation procedures
APP_ACTIVATORS = {
    "gimp": {
        "name": "GIMP Script-Fu Server",
        "check": lambda: _check_tcp_port("localhost", 10008),
        "activate": _activate_gimp_scriptfu,
    },
    # Future apps:
    # "freecad": {
    #     "name": "FreeCAD Python Console",
    #     "check": lambda: _check_tcp_port("localhost", 12345),
    #     "activate": _activate_freecad_console,
    # },
}


def detect_and_activate(window_title: str) -> bool:
    """
    Detect which app is running and activate its console/server if needed.
    Returns True if the app's console is available.
    """
    title_lower = window_title.lower()

    for app_key, config in APP_ACTIVATORS.items():
        if app_key in title_lower:
            if config["check"]():
                return True
            print(f"[app] Detected {config['name']} not running, attempting to start...")
            return config["activate"]()

    return False
