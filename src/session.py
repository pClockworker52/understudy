"""
Log all observed events for workflow learning.
Lightweight JSON format, one file per session.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass, field, asdict


@dataclass
class SessionLog:
    session_id: str
    application: str
    start_time: str
    events: List[Dict] = field(default_factory=list)
    predictions_offered: int = 0
    predictions_accepted: int = 0

    def add_event(self, event_type: str, details: Dict):
        self.events.append({
            "t": datetime.now().isoformat(),
            "type": event_type,
            **details
        })

    def save(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"session_{self.session_id}.json"
        with open(path, 'w') as f:
            json.dump(asdict(self), f, indent=2)

    def to_compact_text(self) -> str:
        """Summarize session for Gemini analysis."""
        lines = [f"Session: {self.application} | {len(self.events)} actions | "
                 f"Predictions: {self.predictions_accepted}/{self.predictions_offered} accepted"]
        for e in self.events:
            lines.append(f"  {e['type']}: {e.get('name', e.get('element_name', ''))}")
        return "\n".join(lines)
