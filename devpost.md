# Understudy -- Devpost Submission

## Project Title
Understudy -- AI that watches your desktop workflows and automates the mechanical parts

## Tagline
Your software's understudy: it learns the script, you stay the lead.

---

## Inspiration

Every professional software tool -- GIMP, FreeCAD, AutoCAD, Blender -- has hundreds of keyboard shortcuts and multi-step procedures that users perform mechanically. Subject isolation in GIMP alone requires 4 steps in the exact right order (feather, invert, alpha channel, clear). Get it wrong and you delete the subject instead of the background.

We asked: what if an AI agent could watch you work, recognize these patterns, and offer to execute the mechanical tail automatically?

## What it does

Understudy is a desktop AI agent that:

- **Observes** your workflow in real-time across any Windows application through three observation layers: window events (Layer 1), application scripting bridges (Layer 2), and screenshots (Layer 3)
- **Understands** what you're doing using Gemini 2.5 Flash with multimodal context (action history + screenshot + app-specific state)
- **Suggests** multi-step workflow automations via a floating overlay -- each suggestion is a batch of 2-6 mechanical steps
- **Executes** with one click: keyboard shortcuts, action search commands, or full Script-Fu programs directly inside the application

**Demo highlights:**
- GIMP subject isolation: 4-step workflow (feather > invert > alpha > clear) executed in one click
- FreeCAD view tour: 5-step inspection sequence (front > top > right > fit > perspective)
- GIMP Script-Fu bridge: Understudy writes and executes actual Script-Fu code inside GIMP -- auto-enhance, color correction, sharpening -- each as a single programmatic command

## How we built it

**Architecture:**

```
User works in any Windows app
         |
   [Layer 1: Win32 UI Events]     -- window titles, focus changes via ctypes
   [Layer 2: App Bridges]         -- GIMP Script-Fu TCP server (port 10008)
   [Layer 3: Screenshots]         -- mss capture, resized to 720x540 JPEG
         |
   [Gemini 2.5 Flash]            -- multimodal prediction (thinking_budget=0)
         |
   [PyQt6 Overlay]               -- always-on-top frameless widget
         |
   [Executor]                    -- pyautogui shortcuts / action search / Script-Fu
```

**Key technical decisions:**

1. **Three-layer observation** gives the agent progressively richer context without requiring accessibility APIs that break across apps
2. **App-specific knowledge contexts** (GIMP, FreeCAD, generic) with verified shortcut maps -- we discovered that LLM training data gives ~80% accuracy on version-specific shortcuts, so we manually verified every shortcut
3. **Script-Fu bridge** implements the GIMP Script-Fu server protocol (3-byte header: 'G' + 2-byte big-endian length) for direct programmatic control -- more reliable than keyboard simulation
4. **Execution validation** rejects hallucinated key sequences (>30 chars, comma-chained shortcuts, text-editing keys like Backspace/Home/End)
5. **Unified workflow format** -- every suggestion is a multi-step batch, not a single shortcut. This was a key design iteration: single-step suggestions felt like a shortcut reference card, not an AI agent.

**Tech stack:** Python 3.11, PyQt6, Google GenAI SDK, Gemini 2.5 Flash, pyautogui, mss, ctypes/win32gui, pynput

## Challenges we ran into

- **Script-Fu protocol was undocumented**: GIMP's Script-Fu server uses a binary protocol that differs between versions. We had to reverse-engineer the 3-byte send header and 4-byte response header through trial and error.
- **LLM shortcut hallucination**: Gemini confidently suggested FreeCAD shortcuts (D+1 through D+5 for display modes) that don't exist. We had to verify every shortcut against the actual installed version and add strict execution_data validation.
- **Execution order matters**: GIMP subject isolation requires inverting the selection BEFORE clearing. Without invert, you delete the subject instead of the background. We had to add explicit ordering rules to the prompt.
- **Cross-app focus management**: When FreeCAD's window title has a leading space (" AssemblyExample - FreeCAD"), naive string splitting breaks app detection. Required explicit pattern matching.

## Accomplishments that we're proud of

- **Script-Fu bridge**: Understudy doesn't just press keyboard shortcuts -- it writes actual programs and executes them inside GIMP. This is a fundamentally different level of automation.
- **App-agnostic design**: One agent instance handles GIMP, FreeCAD, and any Windows application. Context switches happen automatically based on window focus.
- **Sub-second predictions**: Gemini 2.5 Flash with thinking_budget=0 returns workflow suggestions in under 1 second.
- **Safety guardrails**: Execution validation rejects oversized shortcuts, text-editing sequences, and unverified commands before they reach the application.

## What we learned

The biggest insight: **for reliable UI automation, you need a discovery phase**. LLM training data gives orientation (~80% confidence) but only ~50% accuracy on version-specific details. Production deployment would need an app capability discovery step -- querying available functions (GIMP's `gimp-pdb-dump`), verifying shortcuts, and building a validated capability map before suggesting anything.

Apps with scripting bridges (Script-Fu, Python consoles) are fundamentally better automation targets than keyboard-only apps, because you can ask the app what it supports rather than guessing.

## What's next for Understudy

- **App capability discovery**: Auto-probe available functions/shortcuts on first connection
- **Workflow learning**: Track executed workflows across sessions and improve suggestions over time
- **More app bridges**: Blender Python console, AutoCAD LISP, VS Code extension API
- **Cloud deployment**: Move prediction to Cloud Run for shared workflow libraries across teams

## Built With

- gemini-2.5-flash
- google-genai-sdk
- google-cloud-run
- python
- pyqt6
- pyautogui
- gimp-script-fu

## Category

UI Navigator
