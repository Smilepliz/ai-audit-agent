"""Извлечение данных из HTML через BeautifulSoup."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from audit.config import CTA_STRONG, CTA_WEAK, PHONE_RE, EMAIL_RE


def visible_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", text).lower()


def extract_links(soup: BeautifulSoup, base_url: str, max_links: int = 20) -> list[str]:
    base = urlparse(base_url)
    seen: set[str] = set()
    links: list[str] = []

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in ("http", "https"):
            continue
        if parsed.netloc != base.netloc:
            continue
        clean = absolute.split("#")[0].rstrip("/") or absolute
        if clean not in seen:
            seen.add(clean)
            links.append(clean)

    return links[:max_links]


def classify_cta_label(label: str) -> str:
    low = label.lower()
    if any(k in low for k in CTA_STRONG):
        return "strong"
    if any(k in low for k in CTA_WEAK):
        return "weak"
    return "other"


def is_likely_cta_element(el) -> bool:
    """Отсекаем длинные заголовки кейсов и статей."""
    label = el.get_text(strip=True)
    if not label or len(label) > 55:
        return False
    if el.name == "button":
        return True
    classes = " ".join(el.get("class", [])).lower()
    if re.search(r"btn|button|cta", classes):
        return True
    parent = el.parent
    for _ in range(2):
        if parent and parent.name == "button":
            return True
        parent = getattr(parent, "parent", None)
    return len(label) <= 40


def collect_ctas(soup: BeautifulSoup) -> dict:
    strong: list[str] = []
    weak: list[str] = []
    all_labels: list[str] = []
    seen: set[str] = set()

    for el in soup.find_all(["a", "button"]):
        if not is_likely_cta_element(el):
            continue
        label = el.get_text(strip=True)
        key = label.lower()
        if key in seen:
            continue
        seen.add(key)
        all_labels.append(label)
        kind = classify_cta_label(label)
        if kind == "strong":
            strong.append(label)
        elif kind == "weak":
            weak.append(label)

    duplicates: list[str] = []
    seen_dup: set[str] = set()
    for label in all_labels:
        half = len(label) // 2
        if half >= 8 and label[:half] == label[half : half * 2]:
            key = label[:half]
            if key not in seen_dup:
                seen_dup.add(key)
                duplicates.append(label)

    return {
        "strong": strong[:10],
        "weak": weak[:10],
        "all": all_labels[:15],
        "duplicates": duplicates[:5],
    }


def collect_contacts(soup: BeautifulSoup, text_lower: str) -> dict:
    has_tel_link = bool(soup.find("a", href=re.compile(r"^tel:", re.I)))
    has_mailto = bool(soup.find("a", href=re.compile(r"^mailto:", re.I)))
    phone_match = PHONE_RE.search(text_lower.replace(" ", "")) or PHONE_RE.search(
        soup.get_text()
    )
    email_match = EMAIL_RE.search(soup.get_text())

    contact_nav = False
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        label = a.get_text(strip=True).lower()
        if re.search(r"contact|контакт", href) or label in (
            "контакты",
            "контакт",
            "связаться",
            "contacts",
            "contact",
        ):
            contact_nav = True
            break

    return {
        "tel_link": has_tel_link,
        "mailto": has_mailto,
        "phone_visible": bool(phone_match),
        "email_visible": bool(email_match),
        "contact_nav": contact_nav,
        "phone_sample": phone_match.group(0) if phone_match else None,
        "email_sample": email_match.group(0) if email_match else None,
    }


def collect_trust_depth(soup: BeautifulSoup, text_lower: str) -> dict:
    signals = {
        "cases": False,
        "about": False,
        "privacy_link": False,
        "phone_or_legal": False,
    }

    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        label = a.get_text(strip=True).lower()
        if re.search(r"case|portfolio|портфолио|кейс|projects", href + " " + label):
            signals["cases"] = True
        if re.search(r"about|о-нас|о_нас|about-company|о компании|о нас", href + " " + label):
            signals["about"] = True
        if re.search(
            r"privacy|policy|personal|confidential|pd-|персональн|конфиденц",
            href + " " + label,
        ):
            signals["privacy_link"] = True

    if PHONE_RE.search(soup.get_text()) or re.search(
        r"\bинн\b|\bогрн\b", text_lower
    ):
        signals["phone_or_legal"] = True

    score = sum(1 for v in signals.values() if v)
    return {"signals": signals, "score": score, "max": 4}
