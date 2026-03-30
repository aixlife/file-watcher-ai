"""
파일을 지정된 폴더로 이동하는 핸들러.
"""

import shutil
from pathlib import Path
from datetime import datetime


def execute(file_path: str, rule: dict, settings: dict) -> dict:
    file_path = Path(file_path)
    options = rule.get("options", {})
    destination = Path(options.get("destination", "~/Downloads/_sorted")).expanduser()
    destination.mkdir(parents=True, exist_ok=True)

    dest_file = destination / file_path.name

    # 이름 충돌 시 타임스탬프 추가
    if dest_file.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest_file = destination / f"{file_path.stem}_{timestamp}{file_path.suffix}"

    shutil.move(str(file_path), str(dest_file))

    return {
        "success": True,
        "message": f"이동 완료: {dest_file}",
        "moved_to": str(dest_file),
    }
