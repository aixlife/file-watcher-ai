#!/usr/bin/env python3
"""
File Watcher Dashboard - FastAPI 웹 대시보드
감시 폴더 설정, 규칙 관리, 실시간 로그, AI 규칙 생성
"""

import os
import sys
import json
import time
import shutil
import platform
import subprocess
import threading
from pathlib import Path
from datetime import datetime
from collections import deque

import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

# ─── 경로 설정 ───
BASE_DIR = Path(__file__).parent
RULES_PATH = BASE_DIR / "rules.yaml"
CONFIG_PATH = BASE_DIR / "config.json"
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# ─── 앱 상태 ───
activity_log = deque(maxlen=200)
watcher_process = None
watcher_running = False

app = FastAPI(title="File Watcher Dashboard")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


# ═══════════════════════════════════════
# Config (첫 실행 설정)
# ═══════════════════════════════════════

def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())
    return {}


def save_config(config: dict):
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2))


def is_setup_complete() -> bool:
    config = load_config()
    return config.get("setup_complete", False)


# ═══════════════════════════════════════
# Rules CRUD
# ═══════════════════════════════════════

def load_rules() -> dict:
    if not RULES_PATH.exists():
        return {"settings": {}, "rules": []}
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {"settings": {}, "rules": []}


def save_rules(data: dict):
    with open(RULES_PATH, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


# ═══════════════════════════════════════
# Watcher 프로세스 관리
# ═══════════════════════════════════════

def start_watcher():
    global watcher_process, watcher_running
    if watcher_running and watcher_process and watcher_process.poll() is None:
        return {"status": "already_running", "pid": watcher_process.pid}

    venv_python = BASE_DIR / ".venv" / "bin" / "python"
    if not venv_python.exists():
        venv_python = sys.executable

    log_file = LOGS_DIR / "watcher.log"
    with open(log_file, "a") as lf:
        watcher_process = subprocess.Popen(
            [str(venv_python), str(BASE_DIR / "watcher.py"), "--config", str(RULES_PATH)],
            stdout=lf,
            stderr=subprocess.STDOUT,
            cwd=str(BASE_DIR),
        )
    watcher_running = True
    add_log("system", "File Watcher 시작됨", f"PID: {watcher_process.pid}")
    return {"status": "started", "pid": watcher_process.pid}


def stop_watcher():
    global watcher_process, watcher_running
    if watcher_process and watcher_process.poll() is None:
        watcher_process.terminate()
        watcher_process.wait(timeout=5)
        add_log("system", "File Watcher 중지됨", "")
    watcher_running = False
    watcher_process = None
    return {"status": "stopped"}


def add_log(log_type: str, message: str, detail: str = ""):
    activity_log.appendleft({
        "time": datetime.now().strftime("%H:%M:%S"),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "type": log_type,
        "message": message,
        "detail": detail,
    })


# ═══════════════════════════════════════
# 환경 체크
# ═══════════════════════════════════════

def check_environment() -> dict:
    venv_exists = (BASE_DIR / ".venv").exists()
    venv_python = BASE_DIR / ".venv" / "bin" / "python"

    deps_ok = False
    if venv_exists and venv_python.exists():
        try:
            result = subprocess.run(
                [str(venv_python), "-c", "import watchdog, yaml; print('ok')"],
                capture_output=True, text=True, timeout=10,
            )
            deps_ok = result.stdout.strip() == "ok"
        except Exception:
            pass

    config = load_config()
    gemini_key = bool(os.environ.get("GEMINI_API_KEY") or config.get("gemini_api_key"))

    return {
        "os": platform.system(),
        "os_version": platform.mac_ver()[0] if platform.system() == "Darwin" else platform.version(),
        "python_version": platform.python_version(),
        "venv_exists": venv_exists,
        "dependencies_ok": deps_ok,
        "gemini_api_key": gemini_key,
        "rules_file_exists": RULES_PATH.exists(),
        "base_dir": str(BASE_DIR),
    }


# ═══════════════════════════════════════
# API 엔드포인트
# ═══════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def root():
    return (BASE_DIR / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/api/status")
async def get_status():
    running = watcher_process is not None and watcher_process.poll() is None
    config = load_config()
    rules_data = load_rules()
    return {
        "setup_complete": is_setup_complete(),
        "watcher_running": running,
        "watcher_pid": watcher_process.pid if running else None,
        "watch_directory": rules_data.get("settings", {}).get("watch_directory", "~/Downloads"),
        "rules_count": len(rules_data.get("rules", [])),
        "active_rules": len([r for r in rules_data.get("rules", []) if r.get("enabled", True)]),
        "config": config,
    }


@app.get("/api/environment")
async def get_environment():
    return check_environment()


@app.post("/api/setup")
async def complete_setup(request: Request):
    body = await request.json()
    watch_dir = body.get("watch_directory", "~/Downloads")

    # 규칙 파일의 watch_directory 업데이트
    rules_data = load_rules()
    if "settings" not in rules_data:
        rules_data["settings"] = {}
    rules_data["settings"]["watch_directory"] = watch_dir
    rules_data["settings"].setdefault("originals_directory", "_originals")
    rules_data["settings"].setdefault("processed_directory", "_processed")
    rules_data["settings"].setdefault("stability_seconds", 3)
    rules_data["settings"].setdefault("cooldown_seconds", 10)
    save_rules(rules_data)

    # 디렉토리 생성
    watch_path = Path(watch_dir).expanduser()
    (watch_path / "_originals").mkdir(parents=True, exist_ok=True)
    (watch_path / "_processed").mkdir(parents=True, exist_ok=True)

    # 설정 저장
    config = load_config()
    config["setup_complete"] = True
    config["watch_directory"] = watch_dir
    config["setup_date"] = datetime.now().isoformat()
    save_config(config)

    add_log("system", "초기 설정 완료", f"감시 폴더: {watch_dir}")
    return {"status": "ok"}


@app.post("/api/setup/install-deps")
async def install_deps():
    """가상환경 생성 및 의존성 설치."""
    venv_dir = BASE_DIR / ".venv"
    try:
        if not venv_dir.exists():
            subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True, timeout=30)

        pip = venv_dir / "bin" / "pip"
        result = subprocess.run(
            [str(pip), "install", "-r", str(BASE_DIR / "requirements.txt"), "-q"],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            return {"status": "error", "message": result.stderr}
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ── Watcher 제어 ──

@app.post("/api/watcher/start")
async def api_start_watcher():
    return start_watcher()


@app.post("/api/watcher/stop")
async def api_stop_watcher():
    return stop_watcher()


# ── 규칙 관리 ──

@app.get("/api/rules")
async def get_rules():
    data = load_rules()
    return {
        "settings": data.get("settings", {}),
        "rules": data.get("rules", []),
    }


@app.post("/api/rules")
async def add_rule(request: Request):
    rule = await request.json()
    data = load_rules()
    if "rules" not in data:
        data["rules"] = []

    # 중복 이름 체크
    existing = {r.get("name") for r in data["rules"]}
    if rule.get("name") in existing:
        rule["name"] = f"{rule['name']}-{len(data['rules']) + 1}"

    rule.setdefault("enabled", True)
    data["rules"].append(rule)
    save_rules(data)
    add_log("rule", f"규칙 추가: {rule['name']}", rule.get("description", ""))
    return {"status": "ok", "rule": rule}


@app.put("/api/rules/{index}")
async def update_rule(index: int, request: Request):
    rule = await request.json()
    data = load_rules()
    rules = data.get("rules", [])
    if index < 0 or index >= len(rules):
        raise HTTPException(404, "규칙을 찾을 수 없습니다")
    data["rules"][index] = rule
    save_rules(data)
    add_log("rule", f"규칙 수정: {rule.get('name', '')}", "")
    return {"status": "ok"}


@app.delete("/api/rules/{index}")
async def delete_rule(index: int):
    data = load_rules()
    rules = data.get("rules", [])
    if index < 0 or index >= len(rules):
        raise HTTPException(404, "규칙을 찾을 수 없습니다")
    removed = rules.pop(index)
    save_rules(data)
    add_log("rule", f"규칙 삭제: {removed.get('name', '')}", "")
    return {"status": "ok"}


@app.patch("/api/rules/{index}/toggle")
async def toggle_rule(index: int):
    data = load_rules()
    rules = data.get("rules", [])
    if index < 0 or index >= len(rules):
        raise HTTPException(404, "규칙을 찾을 수 없습니다")
    rules[index]["enabled"] = not rules[index].get("enabled", True)
    save_rules(data)
    status = "활성화" if rules[index]["enabled"] else "비활성화"
    add_log("rule", f"규칙 {status}: {rules[index].get('name', '')}", "")
    return {"status": "ok", "enabled": rules[index]["enabled"]}


# ── AI 규칙 생성 ──

@app.post("/api/rules/generate")
async def generate_rule(request: Request):
    body = await request.json()
    description = body.get("description", "")
    if not description:
        raise HTTPException(400, "규칙 설명을 입력하세요")

    config = load_config()
    api_key = os.environ.get("GEMINI_API_KEY") or config.get("gemini_api_key", "")
    if not api_key:
        raise HTTPException(400, "설정에서 Gemini API Key를 먼저 입력하세요")

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)

        model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        model = genai.GenerativeModel(model_name, system_instruction=AI_SYSTEM_PROMPT)

        prompt = f"{AI_EXAMPLES}\nNow convert:\nUser: {description}\nAssistant:"
        response = model.generate_content(prompt)
        text = response.text.strip()

        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        rule = json.loads(text)
        add_log("ai", f"AI 규칙 생성: {rule.get('name', '')}", description)
        return {"status": "ok", "rule": rule}
    except json.JSONDecodeError:
        raise HTTPException(500, "AI 응답을 파싱할 수 없습니다")
    except Exception as e:
        raise HTTPException(500, f"AI 오류: {str(e)}")


# ── AI 규칙 수정 ──

@app.post("/api/rules/{index}/ai-edit")
async def ai_edit_rule(index: int, request: Request):
    """기존 규칙을 자연어 지시로 AI가 수정."""
    body = await request.json()
    instruction = body.get("instruction", "")
    if not instruction:
        raise HTTPException(400, "수정 지시를 입력하세요")

    data = load_rules()
    rules = data.get("rules", [])
    if index < 0 or index >= len(rules):
        raise HTTPException(404, "규칙을 찾을 수 없습니다")

    current_rule = rules[index]
    config = load_config()
    api_key = os.environ.get("GEMINI_API_KEY") or config.get("gemini_api_key", "")
    if not api_key:
        raise HTTPException(400, "설정에서 Gemini API Key를 먼저 입력하세요")

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)

        model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        model = genai.GenerativeModel(model_name, system_instruction=AI_EDIT_PROMPT)

        prompt = f"""Current rule JSON:
{json.dumps(current_rule, ensure_ascii=False, indent=2)}

User instruction: {instruction}

Output the MODIFIED rule as ONE JSON object. Keep all unchanged fields as-is. Only modify what the user asked for."""

        response = model.generate_content(prompt)
        text = response.text.strip()

        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        modified_rule = json.loads(text)
        add_log("ai", f"AI 규칙 수정: {current_rule.get('name', '')}", instruction)
        return {"status": "ok", "rule": modified_rule, "original": current_rule}
    except json.JSONDecodeError:
        raise HTTPException(500, "AI 응답을 파싱할 수 없습니다")
    except Exception as e:
        raise HTTPException(500, f"AI 오류: {str(e)}")


# ── API Key 저장 ──

@app.get("/api/config")
async def get_config():
    config = load_config()
    # API 키는 마스킹해서 반환
    result = dict(config)
    if result.get("gemini_api_key"):
        key = result["gemini_api_key"]
        result["gemini_api_key_masked"] = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
    return result


@app.put("/api/config")
async def update_config(request: Request):
    body = await request.json()
    config = load_config()
    # 전달된 필드만 업데이트
    for key, value in body.items():
        if value is not None:
            config[key] = value
    save_config(config)
    add_log("system", "설정 저장됨", "")
    return {"status": "ok"}


# ── 활동 로그 ──

@app.get("/api/logs")
async def get_logs():
    # 파일 로그도 합쳐서 반환
    log_file = LOGS_DIR / "watcher.log"
    file_logs = []
    if log_file.exists():
        lines = log_file.read_text(encoding="utf-8", errors="ignore").strip().split("\n")
        for line in lines[-50:]:
            if line.strip():
                file_logs.append({"time": line[:8] if len(line) > 8 else "", "message": line, "type": "watcher"})

    return {
        "activity": list(activity_log),
        "watcher_logs": file_logs[-30:],
    }


@app.get("/api/settings")
async def get_settings():
    data = load_rules()
    return data.get("settings", {})


@app.put("/api/settings")
async def update_settings(request: Request):
    new_settings = await request.json()
    data = load_rules()
    data["settings"] = new_settings
    save_rules(data)
    add_log("system", "설정 변경됨", "")
    return {"status": "ok"}


@app.get("/api/folders")
async def list_folders(path: str = "~"):
    """폴더 탐색기 (셋업 위저드용)."""
    target = Path(path).expanduser()
    if not target.exists():
        return {"folders": [], "current": str(target)}

    folders = []
    try:
        for item in sorted(target.iterdir()):
            if item.is_dir() and not item.name.startswith("."):
                folders.append({
                    "name": item.name,
                    "path": str(item),
                })
    except PermissionError:
        pass

    return {
        "current": str(target),
        "parent": str(target.parent) if str(target) != "/" else None,
        "folders": folders[:50],
    }


# ═══════════════════════════════════════
# AI 프롬프트
# ═══════════════════════════════════════

AI_SYSTEM_PROMPT = """You are a file automation rule generator. Convert natural language into a JSON rule.

Available actions:
1. split_by_size - Split text files by size. Options: size_rules [{min_kb, parts}], default_parts, output_format, move_original
2. move_to_folder - Move file. Options: destination (path)

Trigger conditions:
- filename_contains: substring match
- filename_starts_with: prefix match
- extensions: [".pdf", ".txt"]

Output ONE JSON object:
{"name":"kebab-case","description":"한국어","enabled":true,"trigger":{...},"action":"handler_name","options":{...}}"""

AI_EDIT_PROMPT = """You are a file automation rule editor. You receive an existing rule as JSON and a user instruction to modify it.
Modify ONLY what the user asks. Keep everything else unchanged.
Output ONE JSON object with the full modified rule. No explanation, no markdown."""

AI_EXAMPLES = """Examples:
User: invoice PDF를 Documents/Invoices로 이동
Assistant: {"name":"invoice-to-documents","description":"invoice PDF를 Documents/Invoices로 이동","enabled":true,"trigger":{"filename_contains":"invoice","extensions":[".pdf"]},"action":"move_to_folder","options":{"destination":"~/Documents/Invoices/"}}

User: screenshot png, jpg는 Pictures/Screenshots로
Assistant: {"name":"screenshot-organize","description":"screenshot 이미지를 Pictures/Screenshots로 이동","enabled":true,"trigger":{"filename_starts_with":"screenshot","extensions":[".png",".jpg",".jpeg"]},"action":"move_to_folder","options":{"destination":"~/Pictures/Screenshots/"}}"""


# ═══════════════════════════════════════
# CLI 진입점
# ═══════════════════════════════════════

def cli():
    """CLI 진입점 — `file-watcher` 명령어로 실행."""
    import argparse
    import webbrowser
    import threading

    parser = argparse.ArgumentParser(description="File Watcher - AI 파일 자동화 도구")
    parser.add_argument("--port", type=int, default=8500, help="서버 포트 (기본: 8500)")
    parser.add_argument("--no-browser", action="store_true", help="브라우저 자동 열기 비활성화")
    parser.add_argument("--host", default="127.0.0.1", help="서버 호스트 (기본: 127.0.0.1)")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"
    print(f"╔══════════════════════════════════════╗")
    print(f"║   File Watcher Dashboard             ║")
    print(f"║   {url:<36} ║")
    print(f"╚══════════════════════════════════════╝")
    print(f"  Ctrl+C로 종료")

    if not args.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    cli()
