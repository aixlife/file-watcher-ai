#!/usr/bin/env python3
"""
File Watcher - 디렉토리 감시 및 규칙 기반 자동 처리
Usage: python watcher.py [--config rules.yaml] [--watch ~/Downloads]
"""

import os
import sys
import time
import logging
import argparse
import importlib
from pathlib import Path
from threading import Timer

import yaml
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# 로그 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("file-watcher")


class RuleEngine:
    """YAML 규칙을 로드하고 파일에 매칭되는 규칙을 찾는 엔진."""

    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.config = {}
        self.rules = []
        self.settings = {}
        self.reload()

    def reload(self):
        """규칙 파일 다시 로드 (핫 리로드 지원)."""
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f) or {}
        self.settings = self.config.get("settings", {})
        self.rules = [r for r in self.config.get("rules", []) if r.get("enabled", True)]
        log.info(f"규칙 로드 완료: {len(self.rules)}개 활성 규칙")

    def match(self, file_path: str) -> list[dict]:
        """파일에 매칭되는 모든 규칙 반환."""
        path = Path(file_path)
        name_lower = path.name.lower()
        ext = path.suffix.lower()
        matched = []

        for rule in self.rules:
            trigger = rule.get("trigger", {})

            # 파일명 키워드 체크
            if "filename_contains" in trigger:
                keyword = trigger["filename_contains"].lower()
                if keyword not in name_lower:
                    continue

            if "filename_starts_with" in trigger:
                prefix = trigger["filename_starts_with"].lower()
                if not name_lower.startswith(prefix):
                    continue

            # 확장자 체크
            if "extensions" in trigger:
                allowed = [e.lower() for e in trigger["extensions"]]
                if ext not in allowed:
                    continue

            matched.append(rule)

        return matched


class FileHandler(FileSystemEventHandler):
    """파일 생성/이동 이벤트를 감지하고 규칙에 따라 처리."""

    # 무시할 패턴 (임시 파일, 시스템 파일)
    IGNORE_PATTERNS = {
        ".crdownload",  # Chrome 다운로드 중
        ".part",        # Firefox 다운로드 중
        ".download",    # Safari 다운로드 중
        ".tmp",
        ".temp",
        ".DS_Store",
    }
    IGNORE_PREFIXES = (".", "~", "_originals", "_processed")

    def __init__(self, engine: RuleEngine):
        self.engine = engine
        self._pending: dict[str, Timer] = {}
        self._processed: dict[str, float] = {}

    def on_created(self, event):
        if event.is_directory:
            return
        self._schedule_check(event.src_path)

    def on_moved(self, event):
        """다운로드 완료 시 이름이 바뀌는 경우 (예: .crdownload -> .txt)."""
        if event.is_directory:
            return
        # 임시 확장자에서 정상 확장자로 변경된 경우
        src_ext = Path(event.src_path).suffix.lower()
        if src_ext in self.IGNORE_PATTERNS:
            self._schedule_check(event.dest_path)

    def _schedule_check(self, file_path: str):
        """파일 안정화 대기 후 처리 (다운로드 완료 확인)."""
        path = Path(file_path)

        # 무시할 파일 필터링
        if path.suffix.lower() in self.IGNORE_PATTERNS:
            return
        if any(path.name.startswith(p) for p in self.IGNORE_PREFIXES):
            return

        # 우리가 생성한 디렉토리 내부 파일은 무시
        watch_dir = Path(self.engine.settings.get("watch_directory", "~/Downloads")).expanduser()
        originals = watch_dir / self.engine.settings.get("originals_directory", "_originals")
        processed = watch_dir / self.engine.settings.get("processed_directory", "_processed")
        try:
            if path.is_relative_to(originals) or path.is_relative_to(processed):
                return
        except (ValueError, TypeError):
            pass

        # 쿨다운 체크
        cooldown = self.engine.settings.get("cooldown_seconds", 10)
        now = time.time()
        if file_path in self._processed:
            if now - self._processed[file_path] < cooldown:
                return

        # 기존 타이머 취소 후 새로 스케줄
        if file_path in self._pending:
            self._pending[file_path].cancel()

        stability = self.engine.settings.get("stability_seconds", 3)
        timer = Timer(stability, self._process_file, args=[file_path])
        timer.daemon = True
        timer.start()
        self._pending[file_path] = timer

    def _process_file(self, file_path: str):
        """규칙 매칭 및 핸들러 실행."""
        self._pending.pop(file_path, None)
        path = Path(file_path)

        if not path.exists():
            return

        # 파일 크기가 0이면 아직 쓰는 중일 수 있음
        if path.stat().st_size == 0:
            self._schedule_check(file_path)
            return

        # 규칙 매칭
        matched_rules = self.engine.match(file_path)
        if not matched_rules:
            return

        log.info(f"파일 감지: {path.name} ({path.stat().st_size / 1024:.1f}KB)")

        for rule in matched_rules:
            action = rule.get("action", "")
            log.info(f"  규칙 적용: [{rule['name']}] -> {action}")

            try:
                handler = importlib.import_module(f"handlers.{action}")
                result = handler.execute(file_path, rule, self.engine.settings)

                if result.get("success"):
                    log.info(f"  완료: {result.get('message', 'OK')}")
                    if result.get("output_files"):
                        for f in result["output_files"]:
                            log.info(f"    -> {Path(f).name}")
                    if result.get("original_moved_to"):
                        log.info(f"    원본 -> {Path(result['original_moved_to']).name}")
                else:
                    log.error(f"  실패: {result.get('message', 'Unknown error')}")
            except ModuleNotFoundError:
                log.error(f"  핸들러 없음: handlers/{action}.py")
            except Exception as e:
                log.error(f"  오류: {e}")

            self._processed[file_path] = time.time()
            # 파일이 이동/삭제되었으면 다음 규칙 스킵
            if not Path(file_path).exists():
                break


class ConfigReloader(FileSystemEventHandler):
    """rules.yaml 변경 시 자동 리로드."""

    def __init__(self, engine: RuleEngine):
        self.engine = engine

    def on_modified(self, event):
        if Path(event.src_path).name == self.engine.config_path.name:
            log.info("규칙 파일 변경 감지 - 리로드 중...")
            try:
                self.engine.reload()
            except Exception as e:
                log.error(f"규칙 리로드 실패: {e}")


def main():
    parser = argparse.ArgumentParser(description="File Watcher - 규칙 기반 파일 자동 처리")
    parser.add_argument(
        "--config",
        default=str(Path(__file__).parent / "rules.yaml"),
        help="규칙 설정 파일 경로",
    )
    parser.add_argument("--watch", help="감시할 디렉토리 (rules.yaml 설정보다 우선)")
    args = parser.parse_args()

    # 규칙 엔진 초기화
    engine = RuleEngine(args.config)

    # 감시 디렉토리 결정
    watch_dir = args.watch or engine.settings.get("watch_directory", "~/Downloads")
    watch_dir = str(Path(watch_dir).expanduser())

    if not Path(watch_dir).exists():
        log.error(f"디렉토리 없음: {watch_dir}")
        sys.exit(1)

    # 출력 디렉토리 생성
    watch_path = Path(watch_dir)
    (watch_path / engine.settings.get("originals_directory", "_originals")).mkdir(exist_ok=True)
    (watch_path / engine.settings.get("processed_directory", "_processed")).mkdir(exist_ok=True)

    # 파일 감시 시작
    file_handler = FileHandler(engine)
    config_handler = ConfigReloader(engine)

    observer = Observer()
    observer.schedule(file_handler, watch_dir, recursive=False)
    observer.schedule(config_handler, str(Path(args.config).parent), recursive=False)
    observer.start()

    log.info(f"File Watcher 시작")
    log.info(f"  감시 디렉토리: {watch_dir}")
    log.info(f"  규칙 파일: {args.config}")
    log.info(f"  활성 규칙: {len(engine.rules)}개")
    log.info(f"  Ctrl+C로 종료")
    log.info(f"---")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("종료 중...")
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
