"""Оценка пригодности ответа для аудита."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from audit.config import (
    AuditConfig,
    ANTIBOT_STRONG_MARKERS,
    ANTIBOT_WEAK_MARKERS,
    JS_SHELL_MARKERS,
    MOJIBAKE_RE,
)
from audit.models import FetchResult, QualityResult
from audit.parser import visible_text
from audit.utils import truncate_evidence


def looks_like_mojibake(text: str) -> bool:
    """Типичная кракозябра при неверной декодировке UTF-8."""
    if not text or len(text) < 8:
        return False
    matches = MOJIBAKE_RE.findall(text)
    if not matches:
        return False
    bad_len = sum(len(m) for m in matches)
    return bad_len >= 8 and bad_len / len(text) >= 0.15


def _detect_antibot(
    html_lower: str, *, status: int | None, visible_len: int
) -> bool:
    if any(marker in html_lower for marker in ANTIBOT_STRONG_MARKERS):
        return True
    stressed = (status is not None and status >= 400) or visible_len < 400
    if stressed and any(marker in html_lower for marker in ANTIBOT_WEAK_MARKERS):
        return True
    return False


def _detect_js_shell(soup: BeautifulSoup, html_lower: str, visible_len: int, config: AuditConfig) -> bool:
    if visible_len >= config.min_visible_text_chars:
        return False
    if any(marker in html_lower for marker in JS_SHELL_MARKERS):
        return True
    scripts = soup.find_all("script")
    if len(scripts) >= 4 and visible_len < 150:
        return True
    if soup.find(id=re.compile(r"^(app|root|__next)$", re.I)) and visible_len < 200:
        return True
    body = soup.find("body")
    if body and len(scripts) >= 2:
        body_text = body.get_text(strip=True)
        if len(body_text) < 80:
            return True
    return False


def _add_reason(reasons: list[str], reason: str) -> None:
    if reason not in reasons:
        reasons.append(reason)


def assess_input_quality(fetch: FetchResult, config: AuditConfig | None = None) -> QualityResult:
    """
    Проверяет, пригоден ли ответ для полноценного аудита.
    Возвращает suitable, reasons (категории для отчёта), details (уточнения).
    """
    cfg = config or AuditConfig()
    reasons: list[str] = []
    details: list[str] = []

    if not fetch.get("ok"):
        _add_reason(reasons, "HTTP ошибка")
        if fetch.get("error"):
            details.append(f"Сеть: {fetch['error']}")
        return {"suitable": False, "reasons": reasons, "details": details}

    status = fetch.get("status_code")
    html = fetch.get("html") or ""
    html_stripped = html.strip()
    html_lower = html_stripped.lower()

    if status is not None and status >= 400:
        _add_reason(reasons, "HTTP ошибка")
        details.append(f"Код ответа: {status}")

    if len(html_stripped) < cfg.min_html_chars:
        _add_reason(reasons, "слишком мало контента")
        details.append(f"Размер HTML: {len(html_stripped)} символов")

    visible_len = 0
    if html_stripped:
        soup = BeautifulSoup(html_stripped, "html.parser")
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""
        visible = visible_text(BeautifulSoup(html_stripped, "html.parser"))
        visible_len = len(visible)

        if _detect_antibot(html_lower, status=status, visible_len=visible_len):
            _add_reason(reasons, "антибот-защита")

        if looks_like_mojibake(title) or looks_like_mojibake(visible[:800]):
            _add_reason(reasons, "некорректная кодировка")
            if title:
                details.append(f"Title (фрагмент): {truncate_evidence(title, 60)}")

        if visible_len < cfg.min_visible_text_chars:
            _add_reason(reasons, "слишком мало контента")
            if f"Видимый текст: ~{visible_len} символов" not in details:
                details.append(f"Видимый текст: ~{visible_len} символов")

        if _detect_js_shell(soup, html_lower, visible_len, cfg):
            _add_reason(reasons, "возможная JS-загрузка страницы")

    if not reasons and html_stripped:
        return {"suitable": True, "reasons": [], "details": []}

    if not reasons:
        _add_reason(reasons, "другая причина")
        details.append("Ответ получен, но не удалось извлечь содержимое для анализа")

    return {"suitable": False, "reasons": reasons, "details": details}
