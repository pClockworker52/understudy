"""
Prediction engine with two modes:
  Mode A: Single-step -- predict next action
  Mode B: Workflow batch -- recognize pattern, offer mechanical tail

Key design: screenshot is grounding, action log is the real signal.
Token budget per prediction: ~200 (action log) + ~500 (app context) + 1 image.
"""

import json
import time
import io
from typing import List, Optional
from dataclasses import dataclass, field
from PIL import Image
import mss
from google import genai
from google.genai import types


@dataclass
class Prediction:
    action_name: str
    confidence: float
    execution_type: str     # "shortcut", "menu", "script_fu"
    execution_data: str     # the actual key combo, menu path, or Script-Fu command
    reasoning: str


@dataclass
class WorkflowBatch:
    """A sequence of mechanical steps the agent can execute."""
    workflow_name: str
    trigger_action: str         # The creative step that was just completed
    steps: List[Prediction]     # Ordered mechanical steps to execute
    confidence: float           # Overall confidence in the match


@dataclass
class PredictionResult:
    workflows: List[WorkflowBatch]
    context_summary: str
    latency_ms: int


PREDICT_PROMPT = """{app_context}

RECENT USER ACTIONS (most recent last):
{action_log}

{gimp_state}

{learned_workflows}

SCREENSHOT: [attached image showing current application state]

YOUR JOB: Suggest 2-3 WORKFLOWS the user likely needs next.

PREFER multi-step workflows (2-6 steps) that save the user real time.
If you cannot find meaningful multi-step workflows, you MAY suggest
single-step actions as fallback — but always prefer batches.

RULES:
- Look at the screenshot: what is the user trying to achieve?
- Each workflow = a batch of mechanical steps executed in sequence
- Steps must require NO user judgment (purely mechanical)
- Name each workflow clearly: "Isolate subject with transparency", "Export for web"
- Single-step fallbacks should still be useful (not just "Save" or "Undo")
- GIMP ISOLATION: If user has a selection, the correct order is:
  Feather > INVERT (Ctrl+I) > Add Alpha Channel > Clear (Delete).
  The user selected what they want to KEEP. You MUST invert to select the background before clearing!

EXECUTION_DATA LIMITS (STRICT - violations will crash the system):
- Each execution_data must be a SINGLE shortcut ("Ctrl+S") or a SINGLE search term ("Feather")
- MAX 4 keys per shortcut (e.g. "Ctrl+Shift+E" is fine)
- NEVER chain multiple shortcuts in one step. Use separate steps instead.
- NEVER generate text-editing sequences (Backspace, arrow keys, Home, End, typing text)
- NEVER try to manipulate dialog fields, filenames, or text inputs
- NEVER generate more than 20 characters in execution_data for shortcuts
- If an action requires typing into a dialog or editing text, it is NOT automatable — skip it

EXECUTION FORMAT:
Each step needs an execution_type and execution_data.

execution_type "shortcut" -- keyboard shortcuts
  - Use pyautogui format: "Ctrl+I", "Delete", "Ctrl+Shift+E"
  - ONLY use shortcuts that actually exist as defaults
  - For sequential keys (FreeCAD): "V+F" (pressed one after another)

execution_type "menu_search" -- action search dialog (if available)
  - execution_data is the ENGLISH action name
  - Examples: "Feather", "Add Alpha Channel", "Flatten Image"

execution_type "script_fu" -- Script-Fu commands (GIMP only, when bridge connected)
  - Valid Script-Fu/Scheme for GIMP's Script-Fu server
  - Script-Fu is POWERFUL: one step can do what 4+ menu_search steps would do
  - A workflow can be a SINGLE script_fu step that does everything at once
  - See the SCRIPT-FU WORKFLOW EXAMPLES in the app context for reference
  - Always end scripts with (gimp-displays-flush) so GIMP updates the canvas

{script_fu_availability}

{workflow_suppression}

Respond ONLY with valid JSON (no markdown fences):
{{
  "context_summary": "what user is working on",
  "workflows": [
    {{
      "name": "human-readable workflow name",
      "confidence": 0.0-1.0,
      "reasoning": "why this workflow is relevant now",
      "steps": [
        {{
          "action_name": "step name",
          "execution_type": "shortcut|menu_search|script_fu",
          "execution_data": "the command to execute"
        }}
      ]
    }}
  ]
}}"""


class Predictor:

    def __init__(self, client: genai.Client):
        self.client = client
        self.learned_workflows_text = ""

    def set_learned_workflows(self, analysis_json: str):
        """Load workflows discovered by the analyzer (Idea 2 feeds Idea 1)."""
        try:
            data = json.loads(analysis_json)
            workflows = data.get("workflows", [])
            if workflows:
                lines = ["LEARNED WORKFLOWS FROM PREVIOUS SESSIONS:"]
                for wf in workflows:
                    lines.append(f"  Workflow: {wf['name']}")
                    lines.append(f"  Trigger: {wf.get('trigger', 'unknown')}")
                    tail = wf.get('mechanical_tail', [])
                    if tail:
                        lines.append(f"  Mechanical tail: {' -> '.join(tail)}")
                    lines.append("")
                self.learned_workflows_text = "\n".join(lines)
        except (json.JSONDecodeError, KeyError):
            self.learned_workflows_text = ""

    def capture_screenshot(self) -> bytes:
        """Capture current screen as JPEG bytes."""
        with mss.mss() as sct:
            # TODO: detect which monitor GIMP is on (dual monitor setup)
            shot = sct.grab(sct.monitors[1])
            img = Image.frombytes('RGB', shot.size, shot.bgra, 'raw', 'BGRX')
            img = img.resize((720, 540), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=75)
            return buf.getvalue()

    def predict(
        self,
        action_log_text: str,
        app_context: str,
        gimp_state_text: str = "",
        screenshot_bytes: Optional[bytes] = None,
        script_fu_available: bool = False,
        last_executed_workflow: str = "",
        recently_executed: list = None,
    ) -> PredictionResult:
        """Generate predictions (both modes) from context + screenshot."""

        t0 = time.time()

        if screenshot_bytes is None:
            screenshot_bytes = self.capture_screenshot()

        if script_fu_available:
            sfu_text = "SCRIPT-FU BRIDGE: CONNECTED. You may use execution_type 'script_fu'."
        else:
            sfu_text = "SCRIPT-FU BRIDGE: NOT AVAILABLE. Use 'shortcut' or 'menu_search' only. Do NOT use 'script_fu'."

        suppress_parts = []
        if last_executed_workflow:
            suppress_parts.append(f"The workflow '{last_executed_workflow}' was JUST executed. Do NOT suggest it again. Set workflow_match to null.")
        if recently_executed:
            names = ", ".join(recently_executed[-5:])
            suppress_parts.append(f"These actions were ALREADY executed recently: [{names}]. Suggest DIFFERENT actions — what comes NEXT, not what was already done.")
        wf_suppress = "IMPORTANT: " + " ".join(suppress_parts) if suppress_parts else ""

        prompt = PREDICT_PROMPT.format(
            app_context=app_context,
            action_log=action_log_text or "[No recent actions]",
            gimp_state=f"GIMP STATE:\n{gimp_state_text}" if gimp_state_text else "",
            learned_workflows=self.learned_workflows_text or "[No learned workflows yet]",
            script_fu_availability=sfu_text,
            workflow_suppression=wf_suppress,
        )

        response = self.client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                prompt,
                types.Part.from_bytes(data=screenshot_bytes, mime_type='image/jpeg')
            ],
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0)
            )
        )

        latency_ms = int((time.time() - t0) * 1000)
        raw = response.text.strip()

        # Parse JSON (handle markdown fences)
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        try:
            data = json.loads(raw)

            workflows = []
            for wf in data.get("workflows", []):
                conf = float(wf.get("confidence", 0))
                if conf < 0.5:
                    continue
                steps = []
                for s in wf.get("steps", []):
                    ed = s.get("execution_data", "")
                    et = s.get("execution_type", "")
                    # Reject insane execution_data (hallucinated key sequences)
                    if et == "shortcut" and len(ed) > 30:
                        print(f"[predict] REJECTED oversized shortcut: {ed[:50]}...")
                        continue
                    if et == "shortcut" and ed.count(",") > 0:
                        print(f"[predict] REJECTED multi-shortcut chain: {ed[:50]}...")
                        continue
                    if any(bad in ed.lower() for bad in ["backspace", "home", "end", "arrow"]):
                        print(f"[predict] REJECTED text-editing keys: {ed[:50]}...")
                        continue
                    steps.append(Prediction(
                        action_name=s["action_name"],
                        confidence=conf,
                        execution_type=et,
                        execution_data=ed,
                        reasoning="workflow step",
                    ))
                if len(steps) >= 1:  # Prefer multi-step, allow single-step fallback
                    workflows.append(WorkflowBatch(
                        workflow_name=wf["name"],
                        trigger_action=wf.get("reasoning", ""),
                        steps=steps,
                        confidence=conf,
                    ))

            return PredictionResult(
                workflows=workflows,
                context_summary=data.get("context_summary", ""),
                latency_ms=latency_ms,
            )
        except (json.JSONDecodeError, KeyError) as e:
            print(f"[predict] Parse error: {e}")
            return PredictionResult(
                workflows=[],
                context_summary="parse error", latency_ms=latency_ms,
            )
