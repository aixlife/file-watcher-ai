# File Watcher AI

AI-powered file watcher that automatically processes files based on customizable rules.

**Key features:**
- Watch a directory for new/downloaded files
- Auto-split large text files (transcripts, etc.) by size
- Auto-move files to organized folders by filename patterns
- AI rule generation — describe a rule in natural language, AI creates it
- AI rule editing — modify existing rules with natural language instructions
- Web dashboard for rule management and monitoring

Works on **macOS, Windows, and Linux**.

## Quick Start

```bash
# Install
pip install file-watcher-ai

# Install with AI features (Gemini)
pip install file-watcher-ai[ai]

# Run
file-watcher
```

The dashboard opens automatically at `http://localhost:8500`.

## Install from Source

```bash
git clone https://github.com/aixlife/file-watcher-ai.git
cd file-watcher-ai
pip install -e ".[ai]"
file-watcher
```

## How It Works

1. **First run** — Setup wizard checks your environment and lets you pick a watch folder
2. **Add rules** — Click "AI Rule Generation", describe what you want in plain language
3. **Start watching** — Click "Start" and the watcher monitors your folder in the background
4. **Auto-process** — New files matching rules are automatically split/moved/organized

### Default Rule: Transcript Splitter

Files containing "transcript" in the name are auto-split based on size:

| File Size | Split Into |
|-----------|-----------|
| 190KB+    | 5 parts   |
| 150KB+    | 4 parts   |
| 90KB+     | 3 parts   |
| 40KB+     | 2 parts   |

Originals are preserved in `_originals/`, split files go to `_processed/`.

## AI Rule Examples

Click "AI Rule Generation" in the dashboard and type:

- `"invoice PDF를 Documents/Invoices로 이동"` (move invoice PDFs)
- `"screenshot으로 시작하는 png를 Pictures/Screenshots로"` (organize screenshots)
- `"report가 포함된 xlsx를 Reports 폴더로 이동"` (file Excel reports)

To modify an existing rule, click "AI Edit" on any rule card:

- `"확장자에 .pdf도 추가해줘"` (add .pdf extension)
- `"분할 기준을 200KB 이상 6분할로 변경"` (change split threshold)

## Configuration

### Gemini API Key (for AI features)

1. Get a key from [Google AI Studio](https://aistudio.google.com/apikey)
2. In the dashboard, click **Settings** and enter your API key
3. Or set the environment variable: `export GEMINI_API_KEY=your-key`

### CLI Options

```bash
file-watcher                    # Default: localhost:8500, auto-open browser
file-watcher --port 9000        # Custom port
file-watcher --no-browser       # Don't auto-open browser
file-watcher --host 0.0.0.0     # Listen on all interfaces
```

## Adding Custom Handlers

Create a new Python file in `handlers/`:

```python
# handlers/my_action.py
def execute(file_path: str, rule: dict, settings: dict) -> dict:
    # Your logic here
    return {"success": True, "message": "Done"}
```

Then reference it in a rule's `action` field as `my_action`.

## Tech Stack

- **Backend:** FastAPI + Watchdog
- **Frontend:** Vanilla HTML/CSS/JS (no build step)
- **AI:** Google Gemini Flash (optional)
- **Packaging:** pip/pyproject.toml

## License

MIT
