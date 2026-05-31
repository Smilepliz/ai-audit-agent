"""Типизированные модели данных (TypedDict) для результатов аудита."""

from __future__ import annotations

from typing import TypedDict


class FetchResult(TypedDict, total=False):
    ok: bool
    status_code: int | None
    final_url: str
    elapsed_ms: int
    html: str
    headers: dict
    error: str | None


class Issue(TypedDict, total=False):
    severity: str  # "high" | "medium" | "low"
    issue: str
    recommendation: str
    evidence: str
    category: str  # "seo" | "offer" | "conversion" | "trust" | "ecommerce"


class EcommerceIssue(Issue, total=False):
    why: str
    effect: str


class QualityResult(TypedDict, total=False):
    suitable: bool
    reasons: list[str]
    details: list[str]


class AnalysisResult(TypedDict, total=False):
    title: str
    description: str
    h1: list[str]
    h2: list[str]
    internal_links: list[str]
    cta: dict
    contacts: dict
    trust: dict
    site_type: dict
    issues: list[Issue]
    ecommerce_checklist: dict | None
    ecommerce_issues: list[Issue]
    canonical: dict | None
    schema: dict | None
    alt: dict | None
    hreflang: dict | None


def make_issue(
    severity: str,
    issue: str,
    recommendation: str,
    *,
    evidence: str | None = None,
    category: str | None = None,
) -> Issue:
    item: Issue = {
        "severity": severity,
        "issue": issue,
        "recommendation": recommendation,
    }
    if evidence:
        item["evidence"] = evidence
    if category:
        item["category"] = category
    return item


def make_ecommerce_issue(
    severity: str,
    issue: str,
    why: str,
    recommendation: str,
    effect: str,
) -> EcommerceIssue:
    return {
        "severity": severity,
        "issue": issue,
        "why": why,
        "recommendation": recommendation,
        "effect": effect,
        "category": "ecommerce",
    }
