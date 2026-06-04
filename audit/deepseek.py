"""Клиент DeepSeek API для AI-анализа аудита."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from typing import Any


@dataclass
class DeepSeekConfig:
    api_key: str = ""
    model: str = "deepseek-chat"
    temperature: float = 0.3
    max_tokens: int = 2000

    def __post_init__(self) -> None:
        if not self.api_key:
            self.api_key = os.environ.get("DEEPSEEK_API_KEY", "")


def build_prompt(analysis: dict, fetch: dict, cfg: Any) -> str:
    issues = analysis.get("issues", [])
    high = [i for i in issues if i.get("severity") == "high"]
    medium = [i for i in issues if i.get("severity") == "medium"]
    low = [i for i in issues if i.get("severity") == "low"]

    st = analysis.get("site_type", {})
    primary_label = st.get("primary_type", "unknown")

    trust = analysis.get("trust", {})
    trust_score = trust.get("score", 0)
    trust_max = trust.get("max", 0)
    signals = trust.get("signals", {})

    cta = analysis.get("cta", {})
    contacts = analysis.get("contacts", {})

    ecommerce_checklist = analysis.get("ecommerce_checklist") or {}

    lines = [
        "Ты — эксперт по коммерческому аудиту сайтов. Проанализируй результаты "
        "автоматической проверки и дай рекомендации.",
        "",
        "## Контекст аудита",
        f"- URL: {fetch.get('final_url', '?')}",
        f"- HTTP статус: {fetch.get('status_code', '?')}",
        f"- Время загрузки: {fetch.get('elapsed_ms', '?')} мс",
        f"- Тип сайта: {primary_label}",
        "",
        "## SEO-данные",
        f"- Title ({len(analysis.get('title', ''))} симв.): {analysis.get('title', '—')}",
        f"- Description ({len(analysis.get('description', ''))} симв.): {analysis.get('description', '—')[:200]}",
        f"- H1: {', '.join(analysis.get('h1', [])) or '—'}",
        "",
        "## Конверсия",
        f"- Сильные CTA: {', '.join(cta.get('strong', [])[:5]) or 'не найдены'}",
        f"- Слабые CTA: {', '.join(cta.get('weak', [])[:5]) or 'не найдены'}",
        f"- Телефон: {'да' if contacts.get('phone_visible') or contacts.get('tel_link') else 'нет'}",
        f"- Email: {'да' if contacts.get('email_visible') or contacts.get('mailto') else 'нет'}",
        f"- Страница контактов: {'да' if contacts.get('contact_nav') else 'нет'}",
        "",
        "## Сигналы доверия",
        f"- Оценка: {trust_score}/{trust_max}",
        f"- Кейсы: {'да' if signals.get('cases') else 'нет'}",
        f"- О компании: {'да' if signals.get('about') else 'нет'}",
        f"- Политика конфиденциальности: {'да' if signals.get('privacy_link') else 'нет'}",
        f"- Телефон/юр.данные: {'да' if signals.get('phone_or_legal') else 'нет'}",
        "",
        "## Найденные проблемы",
    ]

    if high:
        lines.append(f"### Критичные ({len(high)})")
        for i in high:
            cat = i.get("category", "")
            tag = f" [{cat}]" if cat else ""
            lines.append(f"- **{i['issue']}**{tag}")
            lines.append(f"  - {i['recommendation']}")

    if medium:
        lines.append(f"### Средние ({len(medium)})")
        for i in medium:
            cat = i.get("category", "")
            tag = f" [{cat}]" if cat else ""
            lines.append(f"- {i['issue']}{tag}")

    if low:
        lines.append(f"### Низкие ({len(low)})")
        for i in low:
            cat = i.get("category", "")
            tag = f" [{cat}]" if cat else ""
            lines.append(f"- {i['issue']}{tag}")

    if ecommerce_checklist:
        lines.append("")
        lines.append("## Ecommerce-сигналы")
        present = [k for k, v in ecommerce_checklist.items() if v]
        missing = [k for k, v in ecommerce_checklist.items() if not v]
        lines.append(f"- Присутствуют: {', '.join(present) if present else '—'}")
        lines.append(f"- Отсутствуют: {', '.join(missing) if missing else '—'}")

    lines.append("")
    lines.append(
        "## Инструкция\n"
        "На основе этих данных верни JSON со следующими полями:\n"
        "- overall_assessment: общая оценка сайта (2-3 предложения на русском)\n"
        "- top_issues: 3 неочевидные критические проблемы, которые не видны "
        "при поверхностном анализе (массив строк)\n"
        "- top_actions: 3 наиболее эффективных действия для улучшения "
        "(массив строк)\n"
        "- blind_spots: слепые зоны — аспекты, которые невозможно проверить "
        "автоматически по одной странице (массив строк, 2-3 пункта)\n"
        "\n"
        "Ответ должен быть только JSON, без дополнительного текста."
    )

    return "\n".join(lines)


def generate_recommendations(
    analysis: dict, fetch: dict, cfg: DeepSeekConfig
) -> dict | None:
    if not cfg.api_key:
        print(
            "DeepSeek: DEEPSEEK_API_KEY не задан (env или конфиг). "
            "AI-анализ пропущен.",
            file=sys.stderr,
        )
        return None

    try:
        from openai import OpenAI
    except ImportError:
        print(
            "DeepSeek: пакет openai не установлен. "
            "Выполни: pip install openai>=1.0.0",
            file=sys.stderr,
        )
        return None

    prompt = build_prompt(analysis, fetch, cfg)

    try:
        client = OpenAI(
            api_key=cfg.api_key,
            base_url="https://api.deepseek.com",
        )
        response = client.chat.completions.create(
            model=cfg.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        print(
            f"DeepSeek: ошибка вызова API — {exc}. AI-анализ пропущен.",
            file=sys.stderr,
        )
        return None

    raw = response.choices[0].message.content.strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        print(
            "DeepSeek: не удалось распарсить JSON-ответ. AI-анализ пропущен.",
            file=sys.stderr,
        )
        return None

    return {
        "overall_assessment": parsed.get("overall_assessment", ""),
        "top_issues": parsed.get("top_issues", []),
        "top_actions": parsed.get("top_actions", []),
        "blind_spots": parsed.get("blind_spots", []),
        "raw_response": raw,
    }
