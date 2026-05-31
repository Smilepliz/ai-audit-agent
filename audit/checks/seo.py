"""SEO-проверки: title, description, H1, canonical, hreflang."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from audit.config import VAGUE_H1, EMOJI_SPAM_RE, CITY_LIST_RE
from audit.models import Issue, make_issue
from audit.utils import truncate_evidence, significant_words, word_repeat_spam


def check_description_quality(description: str, title: str) -> list[Issue]:
    issues: list[Issue] = []

    if not description:
        issues.append(
            make_issue(
                "high",
                "Отсутствует meta description",
                "Добавьте description 120–160 символов: выгода + для кого + призыв.",
                category="seo",
            )
        )
        return issues

    n = len(description)
    ev = truncate_evidence(description)

    if n < 70:
        issues.append(
            make_issue(
                "medium",
                f"Meta description слишком короткий ({n} симв., норма 120–160)",
                "Раскройте выгоду, уточните аудиторию и добавьте мягкий CTA.",
                evidence=ev,
                category="seo",
            )
        )
    elif n > 200:
        issues.append(
            make_issue(
                "high",
                f"Meta description перегружен ({n} симв., норма до 160)",
                "Сократите до одной выгоды и одного действия; уберите списки городов и повторы.",
                evidence=ev,
                category="seo",
            )
        )
    elif n > 160:
        issues.append(
            make_issue(
                "medium",
                f"Meta description длиннее рекомендации ({n} симв., норма 120–160)",
                "В поиске текст обрежется — оставьте суть в первых 160 символах.",
                evidence=ev,
                category="seo",
            )
        )

    if EMOJI_SPAM_RE.search(description):
        issues.append(
            make_issue(
                "medium",
                "В description есть «шум» (эмодзи или множественные знаки)",
                "Уберите декоративные символы — сниппет должен выглядеть профессионально.",
                evidence=ev,
                category="seo",
            )
        )

    cities = CITY_LIST_RE.findall(description)
    if len(cities) >= 3 or (len(cities) >= 2 and n > 180):
        issues.append(
            make_issue(
                "medium",
                "Description похож на перечисление городов (SEO-переспам)",
                "Оставьте одно гео в title/description; остальные — на отдельных посадочных.",
                evidence=ev,
                category="seo",
            )
        )

    if title and description[:40].lower() == title[:40].lower():
        issues.append(
            make_issue(
                "low",
                "Description дублирует начало title",
                "Description должен дополнять title выгодой, а не повторять его.",
                evidence=ev,
                category="seo",
            )
        )

    return issues


def check_title_quality(title: str) -> list[Issue]:
    issues: list[Issue] = []

    if not title:
        issues.append(
            make_issue(
                "high",
                "Отсутствует тег title",
                "Добавьте title 30–60 символов: услуга + аудитория/гео + бренд.",
                category="seo",
            )
        )
        return issues

    n = len(title)
    ev = truncate_evidence(title)

    if n < 25:
        issues.append(
            make_issue(
                "medium",
                f"Title слишком короткий ({n} симв., норма 30–60)",
                "Добавьте: что предлагаете, для кого, город или нишу.",
                evidence=ev,
                category="seo",
            )
        )
    elif n > 70:
        issues.append(
            make_issue(
                "high",
                f"Title перегружен ({n} симв., норма до 60)",
                "Сократите до одной мысли; детали перенесите в description и H1.",
                evidence=ev,
                category="seo",
            )
        )
    elif n > 60:
        issues.append(
            make_issue(
                "medium",
                f"Title длиннее рекомендации ({n} симв., норма 30–60)",
                "В выдаче обрежется — оставьте ключевое в начале.",
                evidence=ev,
                category="seo",
            )
        )

    spam_word = word_repeat_spam(title)
    if spam_word:
        issues.append(
            make_issue(
                "medium",
                f"Повтор слова в title («{spam_word}» встречается 3+ раз)",
                "Уберите переспам — один title = одна услуга и один фокус.",
                evidence=ev,
                category="seo",
            )
        )

    separators = len(re.findall(r"[—|/,]", title))
    if separators >= 3:
        issues.append(
            make_issue(
                "medium",
                "Title перегружен перечислениями (много разделителей)",
                "Оставьте 1–2 смысловых блока: ниша + действие/гео.",
                evidence=ev,
                category="seo",
            )
        )

    return issues


def check_h1_offer_quality(h1_tags: list[str], title: str) -> list[Issue]:
    issues: list[Issue] = []

    if not h1_tags:
        issues.append(
            make_issue(
                "high",
                "Нет заголовка H1 на главной",
                "Добавьте один H1: что делаете, для кого, какой результат.",
                category="offer",
            )
        )
        return issues

    if len(h1_tags) > 1:
        issues.append(
            make_issue(
                "medium",
                f"Несколько H1 ({len(h1_tags)}) — размывается главный оффер",
                "Оставьте один H1 на первом экране, остальное — H2.",
                evidence=", ".join(h1_tags[:3]),
                category="offer",
            )
        )

    h1 = h1_tags[0]
    ev = truncate_evidence(h1)
    h1_low = h1.lower()

    if len(h1) < 15:
        issues.append(
            make_issue(
                "medium",
                f"H1 слишком короткий ({len(h1)} симв.) — оффер не раскрыт",
                "Добавьте нишу, результат или аудиторию: «Сайты под ключ для B2B в …».",
                evidence=ev,
                category="offer",
            )
        )
    elif len(h1) > 80:
        issues.append(
            make_issue(
                "low",
                f"H1 слишком длинный ({len(h1)} симв.)",
                "Сформулируйте оффер в 5–10 слов для быстрого сканирования.",
                evidence=ev,
                category="offer",
            )
        )

    vague_hit = next((p for p in VAGUE_H1 if p in h1_low), None)
    if vague_hit:
        issues.append(
            make_issue(
                "medium",
                "H1 слишком общий — непонятен конкретный оффер",
                "Замените общие формулировки на: продукт/услуга + аудитория + результат.",
                evidence=ev,
                category="offer",
            )
        )

    if title:
        overlap = significant_words(title) & significant_words(h1)
        if len(overlap) < 1 and not vague_hit:
            issues.append(
                make_issue(
                    "medium",
                    "H1 слабо связан с title — сообщения расходятся",
                    "Согласуйте title и H1: одна услуга, один клиент, один результат.",
                    evidence=f"Title: {truncate_evidence(title, 60)} | H1: {ev}",
                    category="offer",
                )
            )

    return issues


def run_seo_checks(analysis: dict) -> list[Issue]:
    issues: list[Issue] = []
    issues.extend(check_title_quality(analysis.get("title", "")))
    issues.extend(check_description_quality(analysis.get("description", ""), analysis.get("title", "")))
    issues.extend(check_h1_offer_quality(analysis.get("h1", []), analysis.get("title", "")))
    return issues


def check_canonical(soup: BeautifulSoup, final_url: str) -> dict:
    """Проверяет link rel="canonical": наличие, самоссылающийся ли."""
    result: dict = {
        "present": False,
        "href": None,
        "self_canonical": None,
        "differs_from_final": None,
    }
    canonical_tag = soup.find("link", rel=re.compile(r"^canonical$", re.I))
    if canonical_tag and canonical_tag.get("href"):
        href = canonical_tag["href"].strip()
        result["present"] = True
        result["href"] = href
        norm_href = href.rstrip("/")
        norm_final = final_url.rstrip("/")
        result["self_canonical"] = norm_href == norm_final
        result["differs_from_final"] = norm_href != norm_final
    return result


def check_hreflang(soup: BeautifulSoup) -> dict:
    """Проверяет hreflang-теги: link rel="alternate" hreflang="..."."""
    result: dict = {
        "present": False,
        "tags": [],
        "x_default": False,
        "languages": [],
    }
    for tag in soup.find_all("link", rel=re.compile(r"^alternate$", re.I), hreflang=True):
        href = tag.get("href", "").strip()
        hreflang = tag.get("hreflang", "").strip().lower()
        if href and hreflang:
            result["tags"].append({"hreflang": hreflang, "href": href})
            result["languages"].append(hreflang)
            if hreflang == "x-default":
                result["x_default"] = True
    result["present"] = bool(result["tags"])
    return result
