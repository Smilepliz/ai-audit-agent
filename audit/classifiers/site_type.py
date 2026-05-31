"""Классификация типа сайта."""

from __future__ import annotations

from audit.config import (
    AuditConfig,
    CLASSIFY_ECOMMERCE,
    CLASSIFY_SERVICES,
    CLASSIFY_CORPORATE,
    CLASSIFY_SAAS,
)


def _classify_score_type(
    signals: tuple[tuple[str, int, str], ...],
    haystack: str,
    links_blob: str,
    extra_hits: list[tuple[str, int]],
) -> tuple[int, list[str]]:
    """Считает score типа и список сработавших признаков."""
    hits: list[str] = []
    raw = 0
    max_weight = sum(w for _, w, _ in signals) + sum(w for _, w in extra_hits)
    used: set[str] = set()

    for needle, weight, label in signals:
        if needle in haystack or needle in links_blob:
            if label not in used:
                used.add(label)
                raw += weight
                hits.append(label)

    for label, weight in extra_hits:
        if label not in used:
            used.add(label)
            raw += weight
            hits.append(label)

    score = round(100 * raw / max_weight) if max_weight else 0
    return score, hits


def _classify_extra_hits(
    site_type: str,
    *,
    trust: dict,
    cta: dict,
) -> list[tuple[str, int]]:
    extra: list[tuple[str, int]] = []
    signals = trust.get("signals", {})

    if site_type == "services":
        if signals.get("cases"):
            extra.append(("кейсы / портфолио (trust)", 9))
        cta_blob = " ".join(cta.get("strong", [])).lower()
        if any(k in cta_blob for k in ("заявк", "консультац", "заказать", "расчёт", "расчет")):
            extra.append(("сильный CTA услуг", 7))

    if site_type == "corporate":
        if signals.get("about"):
            extra.append(("о компании (trust)", 9))

    if site_type == "saas":
        cta_blob = " ".join(
            cta.get("strong", []) + cta.get("all", [])
        ).lower()
        if any(
            k in cta_blob
            for k in ("попробовать", "trial", "sign up", "signup", "get started", "бесплатн")
        ):
            extra.append(("CTA SaaS", 7))

    return extra


def classify_site_type(
    *,
    title: str,
    description: str,
    h1_tags: list[str],
    text_lower: str,
    internal_links: list[str],
    cta: dict,
    trust: dict,
    config: AuditConfig | None = None,
) -> dict:
    """Эвристическая классификация типа сайта по главной странице."""
    cfg = config or AuditConfig()
    h1_blob = " ".join(h1_tags).lower()
    links_blob = " ".join(internal_links).lower()
    cta_blob = " ".join(cta.get("all", [])).lower()
    haystack = " ".join(
        (title, description, h1_blob, text_lower, cta_blob)
    ).lower()

    type_signals = {
        "ecommerce": CLASSIFY_ECOMMERCE,
        "services": CLASSIFY_SERVICES,
        "corporate": CLASSIFY_CORPORATE,
        "saas": CLASSIFY_SAAS,
    }

    ranked: list[tuple[str, int, list[str]]] = []
    for site_type, signals in type_signals.items():
        extra = _classify_extra_hits(site_type, trust=trust, cta=cta)
        score, hits = _classify_score_type(signals, haystack, links_blob, extra)
        ranked.append((site_type, score, hits))

    ranked.sort(key=lambda x: x[1], reverse=True)
    primary_type, primary_score, primary_hits = ranked[0]

    if (
        primary_score < cfg.classify_min_primary_score
        or len(primary_hits) < cfg.classify_min_hits
    ):
        return {
            "primary_type": "unknown",
            "primary_score": 0,
            "primary_hits": primary_hits if primary_hits else ["недостаточно признаков"],
            "secondary_type": None,
            "secondary_score": None,
            "secondary_hits": None,
        }

    secondary_type = None
    secondary_score = None
    secondary_hits = None
    if len(ranked) > 1:
        sec_type, sec_score, sec_hits = ranked[1]
        if (
            sec_score >= cfg.classify_secondary_min_score
            and len(sec_hits) >= cfg.classify_min_hits
            and primary_score - sec_score <= cfg.classify_secondary_gap_max
        ):
            secondary_type = sec_type
            secondary_score = sec_score
            secondary_hits = sec_hits

    return {
        "primary_type": primary_type,
        "primary_score": primary_score,
        "primary_hits": primary_hits,
        "secondary_type": secondary_type,
        "secondary_score": secondary_score,
        "secondary_hits": secondary_hits,
    }
