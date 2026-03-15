# Understudy -- Architecture

```mermaid
flowchart TB
    subgraph Desktop["User's Desktop (Windows 11)"]
        GIMP["GIMP"]
        FreeCAD["FreeCAD"]
        AnyApp["Any Windows App"]
    end

    subgraph Observe["Observation Layers"]
        L1["Layer 1: Win32 UI Events\n(ctypes/win32gui)\nWindow titles, focus, app detection"]
        L2["Layer 2: App Scripting Bridges\nGIMP Script-Fu TCP (port 10008)\nImage state, selection, layers"]
        L3["Layer 3: Screenshot Capture\n(mss) 720x540 JPEG\nVisual grounding for Gemini"]
    end

    Trigger["Trigger Engine\nIdle detection (2s) | Ctrl+Space\nCooldown 5s between predictions"]

    subgraph Gemini["Gemini 2.5 Flash"]
        Input["Input: Action log + Screenshot\n+ App context + GIMP state"]
        Output["Output: 2-3 Workflow suggestions\nEach = 2-6 executable steps"]
        Validate["Validation: Reject hallucinated\nshortcuts, text-editing keys,\noversized execution_data"]
    end

    subgraph Overlay["PyQt6 Overlay (always-on-top)"]
        Card1["[1] Isolate subject (4 steps)"]
        Card2["[2] Export as PNG (1 step)"]
        Card3["[3] Add background (3 steps)"]
    end

    subgraph Executor["Executor"]
        Shortcut["shortcut → pyautogui.hotkey()"]
        MenuSearch["menu_search → '/' + action name + Enter"]
        ScriptFu["script_fu → TCP to GIMP Script-Fu server"]
    end

    GIMP --> L1 & L2 & L3
    FreeCAD --> L1 & L3
    AnyApp --> L1 & L3

    L1 & L2 & L3 --> Trigger
    Trigger --> Input
    Input --> Output
    Output --> Validate
    Validate --> Card1 & Card2 & Card3

    Card1 --> Shortcut & MenuSearch & ScriptFu
    Card2 --> Shortcut & MenuSearch & ScriptFu
    Card3 --> Shortcut & MenuSearch & ScriptFu

    Shortcut --> Desktop
    MenuSearch --> Desktop
    ScriptFu --> Desktop

    style Gemini fill:#1a73e8,color:#fff
    style Observe fill:#34a853,color:#fff
    style Overlay fill:#191919,color:#e0e0e0
    style Desktop fill:#f5f5f5,color:#333
    style Executor fill:#ea4335,color:#fff
```

## Data Flow

1. User works normally in any Windows application
2. Understudy observes via 3 layers (events + bridge + screenshot)
3. On idle (2s) or Ctrl+Space, context is sent to Gemini 2.5 Flash
4. Gemini returns 2-3 multi-step workflow suggestions
5. Suggestions validated (reject hallucinated shortcuts)
6. Overlay shows suggestions; user picks one with keyboard or click
7. Executor runs the workflow: shortcuts, menu search, or Script-Fu
8. Cycle repeats -- new suggestions appear based on updated context
