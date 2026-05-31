"""Общие утилиты без зависимостей от других модулей аудита."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from audit.config import REPORTS_DIR


def normalize_url(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        raise ValueError("URL не может быть пустым")
    if not re.match(r"^https?://", raw, re.I):
        raw = "https://" + raw
    parsed = urlparse(raw)
    if not parsed.netloc:
        raise ValueError(f"Некорректный URL: {raw}")
    return raw


def domain_dir_name(url: str) -> str:
    host = urlparse(url).netloc.replace(":", "_") or "site"
    return re.sub(r"[^\w.\-]", "_", host)


def save_reports(url: str, content: str) -> tuple[Path, Path]:
    """Сохраняет отчёт только в reports/<domain>/: архив и latest.md."""
    domain_dir = REPORTS_DIR / domain_dir_name(url)
    domain_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = domain_dir / f"{ts}.md"
    latest_path = domain_dir / "latest.md"

    archive_path.write_text(content, encoding="utf-8")
    latest_path.write_text(content, encoding="utf-8")

    return archive_path, latest_path


def truncate_evidence(text: str, max_len: int = 120) -> str:
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def significant_words(text: str, min_len: int = 5) -> set[str]:
    words = re.findall(r"[a-zа-яё0-9]+", text.lower())
    return {w for w in words if len(w) >= min_len}


def word_repeat_spam(text: str) -> str | None:
    words = re.findall(r"[a-zа-яё]{4,}", text.lower())
    counts: dict[str, int] = {}
    for w in words:
        counts[w] = counts.get(w, 0) + 1
    for w, n in counts.items():
        if n >= 3:
            return w
    return None
