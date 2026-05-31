"""Оркестратор: собирает все модули вместе."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from audit.config import AuditConfig
from audit.parser import (
    visible_text,
    extract_links,
    collect_ctas,
    collect_contacts,
    collect_trust_depth,
)
from audit.checks.seo import check_canonical, check_hreflang
from audit.checks.technical import check_schema_org, check_alt_attributes
from audit.checks.ecommerce import collect_ecommerce_signals, run_ecommerce_checks
from audit.classifiers.site_type import classify_site_type
from audit.checks import run_all_checks


def analyze_html(html: str, url: str, config: AuditConfig | None = None) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    desc_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    description = (desc_tag.get("content") or "").strip() if desc_tag else ""

    h1_tags = [
        h.get_text(strip=True) for h in soup.find_all("h1") if h.get_text(strip=True)
    ]
    h2_tags = [
        h.get_text(strip=True) for h in soup.find_all("h2") if h.get_text(strip=True)
    ]

    text_lower = visible_text(BeautifulSoup(html, "html.parser"))
    internal_links = extract_links(soup, url)
    cta = collect_ctas(soup)
    contacts = collect_contacts(soup, text_lower)
    trust = collect_trust_depth(soup, text_lower)
    site_type = classify_site_type(
        title=title,
        description=description,
        h1_tags=h1_tags,
        text_lower=text_lower,
        internal_links=internal_links,
        cta=cta,
        trust=trust,
        config=config,
    )

    ecommerce_checklist = None
    ecommerce_issues: list[dict] = []
    if site_type.get("primary_type") == "ecommerce":
        ecommerce_checklist = collect_ecommerce_signals(
            soup, text_lower, internal_links, cta, contacts, trust
        )
        ecommerce_issues = run_ecommerce_checks(ecommerce_checklist)

    # Технические проверки
    canonical = check_canonical(soup, url)
    schema = check_schema_org(soup)
    alt = check_alt_attributes(soup)
    hreflang = check_hreflang(soup)

    analysis_dict = {
        "title": title,
        "description": description,
        "h1": h1_tags,
        "h2": h2_tags[:15],
        "internal_links": internal_links,
        "cta": cta,
        "contacts": contacts,
        "trust": trust,
        "site_type": site_type,
        "ecommerce_checklist": ecommerce_checklist,
        "ecommerce_issues": ecommerce_issues,
        "issues": [],
        "canonical": canonical,
        "schema": schema,
        "alt": alt,
        "hreflang": hreflang,
    }

    # Запускаем все проверки
    analysis_dict["issues"] = run_all_checks(analysis_dict)

    return analysis_dict
