# File Watcher AI

AI 기반 파일 감시 자동화 도구. 규칙에 따라 파일을 자동으로 분할, 이동, 정리합니다.

**주요 기능:**
- 지정 폴더의 새 파일/다운로드 파일 실시간 감시
- 대용량 텍스트 파일(트랜스크립트 등) 크기별 자동 분할
- 파일명 패턴에 따라 자동 폴더 이동
- AI 규칙 생성 — 자연어로 설명하면 AI가 규칙을 만들어줌
- AI 규칙 수정 — 기존 규칙을 자연어로 수정 지시
- 웹 대시보드에서 규칙 관리 및 모니터링

**macOS, Windows, Linux** 모두 지원합니다.

## 빠른 시작

```bash
# 설치
pip install file-watcher-ai

# AI 기능 포함 설치 (Gemini)
pip install file-watcher-ai[ai]

# 실행
file-watcher
```

실행하면 `http://localhost:8500`에서 대시보드가 자동으로 열립니다.

## 소스에서 설치

```bash
git clone https://github.com/aixlife/file-watcher-ai.git
cd file-watcher-ai
pip install -e ".[ai]"
file-watcher
```

## 사용 방법

1. **첫 실행** — 셋업 위저드가 환경을 확인하고 감시할 폴더를 선택
2. **규칙 추가** — "AI 규칙 생성" 클릭 후 자연어로 원하는 규칙 설명
3. **감시 시작** — "시작" 클릭하면 백그라운드에서 폴더 감시
4. **자동 처리** — 규칙에 맞는 새 파일이 감지되면 자동 분할/이동/정리

### 기본 규칙: 트랜스크립트 분할기

파일명에 "transcript"이 포함된 파일을 크기에 따라 자동 분할:

| 파일 크기 | 분할 수 |
|----------|--------|
| 190KB 이상 | 5분할 |
| 150KB 이상 | 4분할 |
| 90KB 이상  | 3분할 |
| 40KB 이상  | 2분할 |

원본은 `_originals/`에 보관, 분할 파일은 `_processed/`에 저장됩니다.

## AI 규칙 예시

대시보드에서 "AI 규칙 생성"을 클릭하고 입력:

- `"invoice PDF가 들어오면 Documents/Invoices 폴더로 이동"`
- `"screenshot으로 시작하는 png, jpg를 Pictures/Screenshots로 이동"`
- `"report가 포함된 xlsx를 Reports 폴더로 이동"`

기존 규칙 수정은 규칙 카드의 "AI 수정" 클릭:

- `"확장자에 .pdf도 추가해줘"`
- `"분할 기준을 200KB 이상 6분할로 변경"`

## 설정

### Gemini API Key (AI 기능용)

1. [Google AI Studio](https://aistudio.google.com/apikey)에서 키 발급
2. 대시보드 **설정**에서 API Key 입력 후 저장
3. 또는 환경변수 설정: `export GEMINI_API_KEY=your-key`

### CLI 옵션

```bash
file-watcher                    # 기본: localhost:8500, 브라우저 자동 열기
file-watcher --port 9000        # 포트 변경
file-watcher --no-browser       # 브라우저 자동 열기 비활성화
file-watcher --host 0.0.0.0     # 모든 인터페이스에서 접속 허용
```

## 커스텀 핸들러 추가

`handlers/`에 새 Python 파일 생성:

```python
# handlers/my_action.py
def execute(file_path: str, rule: dict, settings: dict) -> dict:
    # 처리 로직
    return {"success": True, "message": "완료"}
```

규칙의 `action` 필드에 `my_action`으로 참조하면 됩니다.

## 기술 스택

- **백엔드:** FastAPI + Watchdog
- **프론트엔드:** Vanilla HTML/CSS/JS (빌드 불필요)
- **AI:** Google Gemini Flash (선택)
- **패키징:** pip / pyproject.toml

---

# English

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
