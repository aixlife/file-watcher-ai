"""
파일을 크기에 따라 N등분하는 핸들러.
텍스트 파일을 줄 단위로 분할하여 .md 파일로 저장.
"""

import os
import math
from pathlib import Path
from datetime import datetime


def execute(file_path: str, rule: dict, settings: dict) -> dict:
    """
    파일을 크기 기반으로 분할.

    Returns:
        dict with keys: success, message, output_files, original_moved_to
    """
    file_path = Path(file_path)
    options = rule.get("options", {})
    size_rules = options.get("size_rules", [])
    default_parts = options.get("default_parts", 1)
    output_format = options.get("output_format", "md")
    move_original = options.get("move_original", True)

    # 파일 크기 확인 (KB)
    file_size_kb = file_path.stat().st_size / 1024

    # 크기 규칙에 따라 분할 수 결정 (큰 것부터 매칭)
    parts = default_parts
    for sr in sorted(size_rules, key=lambda x: x["min_kb"], reverse=True):
        if file_size_kb >= sr["min_kb"]:
            parts = sr["parts"]
            break

    if parts <= 1:
        return {
            "success": True,
            "message": f"파일 크기 {file_size_kb:.1f}KB - 분할 기준 미달, 이동만 수행",
            "output_files": [],
            "parts": 1,
        }

    # 파일 읽기
    content = _read_file(file_path)
    if content is None:
        return {"success": False, "message": f"파일 읽기 실패: {file_path}"}

    lines = content.splitlines(keepends=True)
    total_lines = len(lines)

    if total_lines < parts:
        parts = max(1, total_lines)

    # 줄 단위로 균등 분할
    chunk_size = math.ceil(total_lines / parts)
    chunks = []
    for i in range(parts):
        start = i * chunk_size
        end = min((i + 1) * chunk_size, total_lines)
        chunks.append(lines[start:end])

    # 출력 파일 생성
    watch_dir = Path(settings.get("watch_directory", "~/Downloads")).expanduser()
    processed_dir = watch_dir / settings.get("processed_directory", "_processed")
    processed_dir.mkdir(parents=True, exist_ok=True)

    stem = file_path.stem
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_files = []

    for idx, chunk in enumerate(chunks, 1):
        out_name = f"{stem}_part{idx}of{parts}_{timestamp}.{output_format}"
        out_path = processed_dir / out_name

        header = f"# {stem} - Part {idx}/{parts}\n\n"
        header += f"> Original: {file_path.name} | Size: {file_size_kb:.1f}KB | "
        header += f"Lines {sum(len(chunks[j]) for j in range(idx-1))+1}-"
        header += f"{sum(len(chunks[j]) for j in range(idx))}/{total_lines}\n\n---\n\n"

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(header)
            f.writelines(chunk)

        output_files.append(str(out_path))

    # 원본 이동
    original_moved_to = None
    if move_original:
        originals_dir = watch_dir / settings.get("originals_directory", "_originals")
        originals_dir.mkdir(parents=True, exist_ok=True)
        dest = originals_dir / f"{stem}_{timestamp}{file_path.suffix}"
        file_path.rename(dest)
        original_moved_to = str(dest)

    return {
        "success": True,
        "message": f"{file_size_kb:.1f}KB -> {parts}분할 완료",
        "output_files": output_files,
        "original_moved_to": original_moved_to,
        "parts": parts,
    }


def _read_file(file_path: Path):
    """여러 인코딩을 시도하여 파일 읽기."""
    for encoding in ["utf-8", "utf-8-sig", "cp949", "euc-kr", "latin-1"]:
        try:
            return file_path.read_text(encoding=encoding)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return None
