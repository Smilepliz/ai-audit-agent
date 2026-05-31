#!/usr/bin/env python3
"""Одноразовая миграция: reports/<domain>_<ts>.md -> reports/<domain>/<ts>.md."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

REPORTS_DIR = Path(__file__).resolve().parent / "reports"
OLD_NAME_RE = re.compile(r"^(.+)_(\d{8}_\d{6})\.md$")
ARCHIVE_NAME_RE = re.compile(r"^(\d{8}_\d{6})\.md$")


def parse_old_filename(path: Path) -> tuple[str, str] | None:
    match = OLD_NAME_RE.match(path.name)
    if not match:
        return None
    return match.group(1), match.group(2)


def files_equal(a: Path, b: Path) -> bool:
    return a.read_bytes() == b.read_bytes()


def list_root_legacy_files() -> list[Path]:
    if not REPORTS_DIR.is_dir():
        return []
    return sorted(REPORTS_DIR.glob("*.md"))


def list_domain_dirs() -> list[Path]:
    if not REPORTS_DIR.is_dir():
        return []
    return sorted(p for p in REPORTS_DIR.iterdir() if p.is_dir())


def list_archives(domain_dir: Path) -> list[tuple[str, Path]]:
    archives: list[tuple[str, Path]] = []
    for path in domain_dir.glob("*.md"):
        if path.name == "latest.md":
            continue
        match = ARCHIVE_NAME_RE.match(path.name)
        if match:
            archives.append((match.group(1), path))
    return archives


def newest_archive(domain_dir: Path) -> Path | None:
    archives = list_archives(domain_dir)
    if not archives:
        return None
    archives.sort(key=lambda x: x[0], reverse=True)
    return archives[0][1]


def plan_move(src: Path, apply: bool) -> str:
    parsed = parse_old_filename(src)
    if not parsed:
        return f"[SKIP] {src.name} — не формат <domain>_<YYYYMMDD_HHMMSS>.md"

    domain, ts = parsed
    dest_dir = REPORTS_DIR / domain
    dest = dest_dir / f"{ts}.md"

    if dest.exists():
        if files_equal(src, dest):
            if apply:
                src.unlink()
            return f"[DEDUP] {src.name} — идентичен {dest.relative_to(REPORTS_DIR.parent)}, удалён из корня"
        alt = dest_dir / f"{ts}_migrated.md"
        if alt.exists():
            return f"[ERROR] {src.name} — конфликт: {dest.name} и {alt.name} уже существуют"
        if apply:
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(alt))
        return f"[MOVE*] {src.name} -> {domain}/{alt.name} (конфликт с существующим архивом)"

    if apply:
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
    return f"[MOVE] {src.name} -> {domain}/{ts}.md"


def rebuild_latest(domain_dir: Path, apply: bool) -> str:
    newest = newest_archive(domain_dir)
    if not newest:
        return f"[LATEST SKIP] {domain_dir.name}/ — нет архивов"

    latest_path = domain_dir / "latest.md"

    if latest_path.exists() and files_equal(latest_path, newest):
        return f"[LATEST OK] {domain_dir.name}/latest.md уже = {newest.name}"

    if apply:
        latest_path.write_text(newest.read_text(encoding="utf-8"), encoding="utf-8")

    return f"[LATEST] {domain_dir.name}/latest.md <- {newest.name}"


def verify_reports_root() -> list[str]:
    errors: list[str] = []
    if not REPORTS_DIR.is_dir():
        return errors
    for path in REPORTS_DIR.glob("*.md"):
        errors.append(f"В корне остался файл: {path.name}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Миграция отчётов из корня reports/ в reports/<domain>/."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Выполнить перемещение и обновить latest.md (по умолчанию dry-run).",
    )
    args = parser.parse_args()
    apply = args.apply

    mode = "APPLY" if apply else "DRY-RUN"
    print(f"Режим: {mode}")
    print(f"Каталог: {REPORTS_DIR}\n")

    legacy = list_root_legacy_files()
    if not legacy:
        print("Файлов для миграции в корне reports/ не найдено.\n")
    else:
        print(f"Найдено в корне: {len(legacy)} файл(ов)\n")
        for src in legacy:
            print(plan_move(src, apply))

    print()
    domains = list_domain_dirs()
    if not domains:
        print("Папок доменов пока нет.\n")
    else:
        print("Пересборка latest.md:\n")
        for domain_dir in domains:
            print(rebuild_latest(domain_dir, apply))

    if apply:
        print()
        errors = verify_reports_root()
        if errors:
            print("Проверка:")
            for err in errors:
                print(f"  ! {err}")
            return 1
        print("Проверка: в корне reports/ нет .md — OK")

    print()
    if not apply:
        print("Это был dry-run. Для выполнения: python migrate_reports.py --apply")

    return 0


if __name__ == "__main__":
    sys.exit(main())
