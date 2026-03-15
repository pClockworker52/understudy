# Understudy

*Your software's understudy -- it learns the script, you stay the lead.*

An AI-powered UI automation agent that observes your workflow in any Windows application, learns your repetitive patterns, and automates the mechanical steps -- so you can focus on the creative work.

**Competition:** Gemini Live Agent Challenge (Devpost)
**Category:** UI Navigator

## How It Works

1. **Observes** your actions via Windows UI Automation (works on any app)
2. **Enriches** context with app-specific queries (e.g., GIMP undo stack via Script-Fu)
3. **Learns** your workflow patterns using Gemini AI (creative vs. mechanical classification)
4. **Predicts** your next action and offers to automate mechanical step sequences

## Architecture

- **Layer 1 (Universal):** UI Automation event capture via pywinauto
- **Layer 2 (App-Specific):** GIMP Script-Fu bridge for tool/selection/undo state
- **Layer 3 (Visual):** Screenshot capture on trigger for Gemini grounding
- **Cloud:** Gemini 2.5-Flash via GenAI SDK on Cloud Run + Vertex AI

## Setup

### Prerequisites

- Windows 10/11
- Python 3.11+ (Anaconda recommended)
- GIMP 2.10+ (for app-specific features)
- Google Cloud project with Vertex AI enabled

### Install

```bash
pip install -r requirements.txt
```

### Configure

```powershell
$env:GEMINI_API_KEY = "your-api-key-here"
```

For GIMP integration, start the Script-Fu server:
GIMP > Filters > Script-Fu > Start Server (port 10008)

### Run

```bash
python src/main.py
```

### Cloud Deployment

```bash
cd cloud
chmod +x deploy.sh
./deploy.sh
```

## Testing

**Minimum test** (any Windows app):
1. Set your `GEMINI_API_KEY`
2. Run `python src/main.py`
3. Open any application and work for ~2 seconds
4. The overlay appears with context-aware suggestions

**Full test** (GIMP integration):
1. Open GIMP with any image
2. Make a selection with the Free Select tool
3. Understudy suggests subject isolation workflow
4. Optional: Filters > Script-Fu > Start Server for programmatic control

## Usage

1. Launch Understudy (`python src/main.py`)
2. Work normally in GIMP or any Windows app
3. When you pause (idle >1.5s), the agent analyzes your context
4. A floating overlay shows predicted next actions
5. Press [1]-[4] to execute a suggestion, or [Esc] to dismiss
6. After a session, a USER.md file is generated with your discovered workflows

## Tech Stack

| Component | Technology |
|-----------|-----------|
| UI Observation | pywinauto (UIAutomation backend) |
| App Enrichment | GIMP Script-Fu TCP server |
| Screenshots | mss + Pillow |
| AI Model | Gemini 2.5-Flash (thinking_budget=0) |
| Cloud | Google Cloud Run + Vertex AI |
| SDK | Google GenAI SDK |
| Overlay UI | PyQt6 |
| Execution | GIMP Script-Fu (primary) + pyautogui (fallback) |

## License

MIT
