"""
Use Gemini to analyze session logs and generate USER.md.

Key insight: let Gemini find patterns rather than hand-coding n-gram
detection. Gemini is better at recognizing semantic workflows
("this sequence is image cropping") than counting string matches.
"""

import os
from google import genai
from google.genai import types
from pathlib import Path
from typing import List

ANALYSIS_PROMPT = """You are analyzing a user's session logs from a desktop application.
Your job is to identify workflow patterns, classify each step as creative or mechanical,
and find automation opportunities.

STEP CLASSIFICATION:
- "creative": Requires human judgment -- spatial decisions, artistic choices,
  parameter tuning, content creation. Examples: drawing selections, choosing colors,
  positioning elements, deciding crop boundaries. Agent should NEVER automate these.
- "mechanical": Deterministic follow-up that is always the same after a creative step.
  Examples: feather selection (same radius), invert selection, delete, export with
  same settings. Agent CAN automate these as a batch.

SESSION LOGS:
{session_data}

Respond with a structured JSON:
{{
  "workflows": [
    {{
      "name": "descriptive workflow name",
      "steps": [
        {{"action": "step description", "type": "creative|mechanical",
         "execution": "shortcut or script_fu command if mechanical"}}
      ],
      "frequency": "how often you see this pattern",
      "trigger": "what creative step signals the start of the mechanical tail",
      "mechanical_tail": ["list of mechanical steps that can be batched"],
      "automation_potential": "high/medium/low"
    }}
  ],
  "preferences": {{
    "most_used_tools": ["tool1", "tool2"],
    "working_style": "description of how this user works",
    "shortcuts_known": ["list of shortcuts user already uses"],
    "shortcuts_missed": ["shortcuts that would help but user doesn't seem to use"]
  }},
  "pain_points": [
    "observed struggle or inefficiency"
  ]
}}

Be specific and actionable. Reference actual events from the logs.
The creative/mechanical split is the most important part -- get it right."""


USER_MD_PROMPT = """Based on this analysis of a user's sessions, generate a USER.md file.
Make it practical, specific, and genuinely useful -- not generic filler.

ANALYSIS:
{analysis}

APPLICATION: {app_name}

Generate a Markdown document with these sections:
1. Summary (2-3 sentences about this user's working style)
2. Discovered Workflows (the repeated patterns, with steps marked as creative/mechanical)
3. Automatable Sequences (workflows where the agent can execute the mechanical tail
   after the user completes the creative step -- this is the key value proposition)
4. Efficiency Opportunities (shortcuts they're missing)
5. Observed Challenges (where they struggle)
6. Statistics (session count, action count, prediction acceptance rate)

For each automatable sequence, show it like this:
  "After you [creative step], the agent can run: [mechanical step 1] > [step 2] > [step 3]"

Write it as if a helpful colleague observed them working and wrote up notes.
Keep it under 600 words. Be direct, not fluffy."""


class SessionAnalyzer:

    def __init__(self, client: genai.Client):
        self.client = client

    def analyze_sessions(self, sessions: List['SessionLog']) -> str:
        """Analyze sessions and return structured analysis."""
        session_texts = [s.to_compact_text() for s in sessions[-5:]]  # Last 5 sessions
        session_data = "\n\n---\n\n".join(session_texts)

        response = self.client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[ANALYSIS_PROMPT.format(session_data=session_data)],
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0)
            )
        )
        return response.text

    def generate_user_md(self, analysis: str, app_name: str) -> str:
        """Generate USER.md from analysis."""
        response = self.client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[USER_MD_PROMPT.format(analysis=analysis, app_name=app_name)],
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0)
            )
        )
        return response.text

    def analyze_and_generate(self, sessions: List['SessionLog'], app_name: str, output_path: Path) -> str:
        """Full pipeline: analyze sessions > generate USER.md."""
        analysis = self.analyze_sessions(sessions)
        user_md = self.generate_user_md(analysis, app_name)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(user_md)
        return user_md
