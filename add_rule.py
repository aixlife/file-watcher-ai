#!/usr/bin/env python3
"""
AI Rule Generator - 자연어로 규칙을 설명하면 YAML 규칙으로 변환하여 추가.

Usage:
    python add_rule.py "invoice PDF가 들어오면 Documents/Invoices 폴더로 이동"
    python add_rule.py "screenshot으로 시작하는 png, jpg 파일은 Pictures/Screenshots로 이동"
    python add_rule.py --list           # 현재 규칙 목록 보기
    python add_rule.py --disable 규칙명  # 규칙 비활성화
    python add_rule.py --enable 규칙명   # 규칙 활성화

Environment:
    GEMINI_API_KEY: Gemini API 키 (필수)
    GEMINI_MODEL: 사용할 모델 (기본: gemini-2.5-flash)
"""

import os
import sys
import json
import argparse
from pathlib import Path

import yaml

RULES_PATH = Path(__file__).parent / "rules.yaml"

SYSTEM_PROMPT = """You are a file automation rule generator. Convert the user's natural language description into a YAML rule for a file watcher system.

Available actions (handlers):
1. split_by_size - Split text files into parts based on file size
   Options: size_rules (list of {min_kb, parts}), default_parts, output_format, move_original
2. move_to_folder - Move file to a specified directory
   Options: destination (path)

Available trigger conditions:
- filename_contains: string (case-insensitive substring match)
- filename_starts_with: string (case-insensitive prefix match)
- extensions: list of extensions like [".pdf", ".txt"]

Output EXACTLY one JSON object (no markdown, no explanation) with these fields:
{
  "name": "kebab-case-rule-name",
  "description": "한국어 설명",
  "enabled": true,
  "trigger": { ... },
  "action": "handler_name",
  "options": { ... }
}

Use ~ for home directory in paths. Be precise with extensions and keywords."""

EXAMPLE_PAIRS = [
    {
        "input": "invoice PDF가 들어오면 Documents/Invoices 폴더로 이동",
        "output": {
            "name": "invoice-to-documents",
            "description": "invoice 키워드가 포함된 PDF를 Documents/Invoices로 이동",
            "enabled": True,
            "trigger": {"filename_contains": "invoice", "extensions": [".pdf"]},
            "action": "move_to_folder",
            "options": {"destination": "~/Documents/Invoices/"},
        },
    },
    {
        "input": "screenshot으로 시작하는 png, jpg는 Pictures/Screenshots로 이동",
        "output": {
            "name": "screenshot-organize",
            "description": "screenshot으로 시작하는 이미지를 Pictures/Screenshots로 이동",
            "enabled": True,
            "trigger": {
                "filename_starts_with": "screenshot",
                "extensions": [".png", ".jpg", ".jpeg"],
            },
            "action": "move_to_folder",
            "options": {"destination": "~/Pictures/Screenshots/"},
        },
    },
]


def load_rules() -> dict:
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_rules(config: dict):
    with open(RULES_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def list_rules():
    config = load_rules()
    rules = config.get("rules", [])
    if not rules:
        print("등록된 규칙이 없습니다.")
        return

    print(f"\n현재 규칙 ({len(rules)}개):")
    print("-" * 60)
    for i, rule in enumerate(rules, 1):
        status = "ON" if rule.get("enabled", True) else "OFF"
        name = rule.get("name", "unnamed")
        desc = rule.get("description", "")
        action = rule.get("action", "")
        print(f"  {i}. [{status}] {name}")
        print(f"     {desc}")
        print(f"     Action: {action}")
        trigger = rule.get("trigger", {})
        if "filename_contains" in trigger:
            print(f"     Keyword: *{trigger['filename_contains']}*")
        if "extensions" in trigger:
            print(f"     Extensions: {', '.join(trigger['extensions'])}")
        print()


def toggle_rule(name: str, enabled: bool):
    config = load_rules()
    rules = config.get("rules", [])
    found = False
    for rule in rules:
        if rule.get("name") == name:
            rule["enabled"] = enabled
            found = True
            break
    if found:
        save_rules(config)
        status = "활성화" if enabled else "비활성화"
        print(f"규칙 '{name}' {status} 완료")
    else:
        print(f"규칙 '{name}'을 찾을 수 없습니다.")
        print("현재 규칙:")
        for r in rules:
            print(f"  - {r.get('name')}")


def generate_rule_with_ai(description: str) -> dict | None:
    """Gemini API로 자연어 → YAML 규칙 변환."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("오류: GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")
        print("  export GEMINI_API_KEY='your-api-key'")
        sys.exit(1)

    try:
        import google.generativeai as genai
    except ImportError:
        print("오류: google-generativeai 패키지가 필요합니다.")
        print("  pip install google-generativeai")
        sys.exit(1)

    genai.configure(api_key=api_key)

    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    model = genai.GenerativeModel(
        model_name,
        system_instruction=SYSTEM_PROMPT,
    )

    # Few-shot 예시 구성
    examples = ""
    for ex in EXAMPLE_PAIRS:
        examples += f"\nUser: {ex['input']}\nAssistant: {json.dumps(ex['output'], ensure_ascii=False)}\n"

    prompt = f"""Here are examples of correct conversions:
{examples}
Now convert this description:
User: {description}
Assistant:"""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()

        # JSON 추출 (마크다운 코드블록 제거)
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        rule = json.loads(text)
        return rule
    except json.JSONDecodeError as e:
        print(f"AI 응답 파싱 실패: {e}")
        print(f"응답 원문: {response.text}")
        return None
    except Exception as e:
        print(f"AI API 오류: {e}")
        return None


def add_rule_interactive(description: str):
    """AI로 규칙을 생성하고 사용자 확인 후 추가."""
    print(f"\n입력: \"{description}\"")
    print("AI 규칙 생성 중...")

    rule = generate_rule_with_ai(description)
    if not rule:
        return

    print(f"\n생성된 규칙:")
    print("-" * 40)
    print(yaml.dump(rule, allow_unicode=True, default_flow_style=False))

    confirm = input("이 규칙을 추가하시겠습니까? (y/n): ").strip().lower()
    if confirm not in ("y", "yes", "ㅇ", "네"):
        print("취소되었습니다.")
        return

    # 규칙 추가
    config = load_rules()
    if "rules" not in config:
        config["rules"] = []

    # 중복 이름 체크
    existing_names = {r.get("name") for r in config["rules"]}
    if rule.get("name") in existing_names:
        rule["name"] = f"{rule['name']}-{len(config['rules']) + 1}"

    config["rules"].append(rule)
    save_rules(config)
    print(f"\n규칙 '{rule['name']}' 추가 완료!")
    print("(watcher가 실행 중이면 자동으로 리로드됩니다)")


def main():
    parser = argparse.ArgumentParser(description="AI 규칙 생성기")
    parser.add_argument("description", nargs="?", help="규칙 설명 (자연어)")
    parser.add_argument("--list", action="store_true", help="현재 규칙 목록")
    parser.add_argument("--enable", metavar="NAME", help="규칙 활성화")
    parser.add_argument("--disable", metavar="NAME", help="규칙 비활성화")
    args = parser.parse_args()

    if args.list:
        list_rules()
    elif args.enable:
        toggle_rule(args.enable, True)
    elif args.disable:
        toggle_rule(args.disable, False)
    elif args.description:
        add_rule_interactive(args.description)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
