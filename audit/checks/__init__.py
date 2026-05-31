"""Регистр всех проверок."""

from __future__ import annotations

from audit.models import Issue
from audit.checks.seo import run_seo_checks
from audit.checks.conversion import run_conversion_checks
from audit.checks.trust import run_trust_checks
from audit.checks.technical import run_technical_checks
from audit.checks.ecommerce import run_ecommerce_checks


def _severity_key(issue: Issue) -> tuple:
    order = {"high": 0, "medium": 1, "low": 2}
    return (order.get(issue["severity"], 9), issue.get("category", ""))


def _sort_issues(issues: list[Issue]) -> list[Issue]:
    issues.sort(key=_severity_key)
    return issues


def run_all_checks(analysis: dict) -> list[Issue]:
    issues: list[Issue] = []
    issues.extend(run_seo_checks(analysis))
    issues.extend(run_conversion_checks(analysis))
    issues.extend(run_trust_checks(analysis))
    issues.extend(run_technical_checks(analysis))
    if analysis.get("site_type", {}).get("primary_type") == "ecommerce":
        ecommerce_issues = analysis.get("ecommerce_issues", [])
        issues.extend(ecommerce_issues)
    return _sort_issues(issues)
