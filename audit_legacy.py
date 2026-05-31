#!/usr/bin/env python3
"""MVP v0.4: аудит главной, тип сайта, проверки для интернет-магазина."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (compatible; SiteAuditBot/0.4; +https://example.com/bot)"
)
TIMEOUT = 15
# Все отчёты только в reports/<domain>/ (latest.md + архивы), не в корне reports/.
REPORTS_DIR = Path(__file__).resolve().parent / "reports"
VERSION = "0.5"

# Сводка чеклиста ecommerce для отчёта (группа → ключи сигналов)
_ECOMMERCE_CHECKLIST_GROUPS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    (
        "Каталог",
        (("catalog", "Каталог"), ("categories", "Категории товаров")),
    ),
    (
        "Карточки товаров",
        (
            ("product_cards", "Товарные карточки"),
            ("prices", "Цены"),
            ("buy_buttons", "Кнопки «Купить» / «В корзину»"),
        ),
    ),
    (
        "Корзина и оформление",
        (("cart", "Корзина"), ("checkout", "Оформление заказа")),
    ),
    (
        "Доставка и оплата",
        (("delivery", "Доставка"), ("payment", "Оплата")),
    ),
    (
        "Поиск и фильтры",
        (("search", "Поиск по товарам"), ("filters", "Фильтры / сортировка")),
    ),
    (
        "Доверие для магазина",
        (
            ("returns", "Возврат / обмен"),
            ("contacts", "Контакты"),
            ("phone", "Телефон"),
            ("privacy", "Политика конфиденциальности"),
            ("reviews", "Отзывы"),
        ),
    ),
)

# Пороги качества HTML для анализа
_MIN_HTML_CHARS = 200
_MIN_VISIBLE_TEXT_CHARS = 250

SITE_TYPE_LABELS = {
    "ecommerce": "Интернет-магазин",
    "services": "Сайт услуг",
    "corporate": "Корпоративный сайт",
    "saas": "SaaS / онлайн-сервис",
    "unknown": "Не удалось определить",
}

# (подстрока для поиска, вес, подпись в отчёте)
_CLASSIFY_ECOMMERCE = (
    ("корзин", 8, "корзина"),
    ("cart", 8, "cart / корзина"),
    ("basket", 6, "basket"),
    ("каталог", 9, "каталог"),
    ("catalog", 8, "catalog"),
    ("/shop", 7, "раздел shop"),
    ("товар", 7, "товары"),
    ("product", 6, "products"),
    ("купить", 7, "купить"),
    ("buy now", 6, "buy"),
    ("доставк", 6, "доставка"),
    ("оплат", 6, "оплата"),
    ("checkout", 7, "checkout"),
    ("в корзину", 8, "в корзину"),
    ("add to cart", 8, "add to cart"),
    ("фильтр", 5, "фильтры"),
    ("filter", 5, "filter"),
)

_CLASSIFY_SERVICES = (
    ("услуг", 9, "услуги"),
    ("services", 7, "services"),
    ("заявк", 8, "заявка"),
    ("кейс", 8, "кейсы"),
    ("портфолио", 8, "портфолио"),
    ("portfolio", 7, "portfolio"),
    ("консультац", 7, "консультация"),
    ("прайс", 6, "прайс"),
    ("price list", 5, "price list"),
    ("этап работ", 6, "этапы работы"),
    ("как мы работаем", 6, "как мы работаем"),
    ("направления", 5, "направления"),
)

_CLASSIFY_CORPORATE = (
    ("о компании", 9, "о компании"),
    ("about us", 7, "about"),
    ("about-company", 7, "about (url)"),
    ("карьер", 8, "карьера"),
    ("careers", 7, "careers"),
    ("ваканс", 7, "вакансии"),
    ("пресс", 7, "пресс-центр"),
    ("инвестор", 8, "инвесторам"),
    ("shareholders", 6, "shareholders"),
    ("миссия", 6, "миссия"),
    ("ценност", 5, "ценности"),
    ("холдинг", 6, "холдинг"),
    ("группа компан", 5, "группа компаний"),
)

_CLASSIFY_SAAS = (
    ("тариф", 9, "тарифы"),
    ("pricing", 9, "pricing"),
    ("/plans", 7, "plans"),
    ("подписк", 7, "подписка"),
    ("free trial", 8, "free trial"),
    ("пробный период", 8, "пробный период"),
    ("демо", 7, "демо"),
    (" demo", 6, "demo"),
    ("sign up", 8, "sign up"),
    ("signup", 8, "signup"),
    ("регистрац", 8, "регистрация"),
    ("личный кабинет", 8, "личный кабинет"),
    ("dashboard", 7, "dashboard"),
    ("get started", 7, "get started"),
    (" api", 6, "API"),
    ("интеграц", 5, "интеграции"),
    ("onboarding", 6, "onboarding"),
)

_CLASSIFY_MIN_PRIMARY_SCORE = 25
_CLASSIFY_MIN_HITS = 2
_CLASSIFY_SECONDARY_MIN_SCORE = 25
_CLASSIFY_SECONDARY_GAP_MAX = 25

CTA_STRONG = (
    "заказать",
    "купить",
    "оставить заявку",
    "связаться",
    "получить",
    "записаться",
    "консультац",
    "бесплатн",
    "попробовать",
    "оформить",
    "заявк",
    "расчёт",
    "расчет",
    "позвонить",
    "написать",
    "sign up",
    "signup",
    "get started",
    "book",
    "buy",
    "order",
    "request a",
    "get a quote",
    "contact us",
    "call us",
)

CTA_WEAK = (
    "подробнее",
    "узнать больше",
    "узнать подробнее",
    "читать",
    "далее",
    "перейти",
    "смотреть",
    "все услуги",
    "все кейсы",
    "ещё",
    "еще",
    "read more",
    "learn more",
    "see more",
    "view all",
    "details",
)

VAGUE_H1 = (
    "решения для бизнеса",
    "решения для вашего бизнеса",
    "задачи бизнеса",
    "качественн",
    "инновац",
    "лидер рынка",
    "полный спектр",
    "комплексн",
    "добро пожаловать",
    "welcome",
    "мы —",
    "мы -",
    "лучшие",
    "надежный партнер",
    "надёжный партнер",
    "профессиональный подход",
    "эффективные решения",
    "современные решения",
    "digital",
    "диджитал",
)

PHONE_RE = re.compile(
    r"(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}"
    r"|\+7\s?\d{10}"
)
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
EMOJI_SPAM_RE = re.compile(r"[⭐★✓✔🔥💥]{2,}|!{3,}")
CITY_LIST_RE = re.compile(
    r"(?:москв|санкт-петербург|спб|нижн|казан|новосиб|екатеринб|иванов|"
    r"ярослав|владимир|краснодар|ростов|самар|воронеж|тула|калуг)",
    re.I,
)


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


def make_issue(
    severity: str,
    issue: str,
    recommendation: str,
    *,
    evidence: str | None = None,
    category: str | None = None,
) -> dict:
    item: dict = {
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
) -> dict:
    return {
        "severity": severity,
        "issue": issue,
        "why": why,
        "recommendation": recommendation,
        "effect": effect,
        "category": "ecommerce",
    }


def fetch_page(url: str) -> dict:
    started = datetime.now()
    try:
        response = requests.get(
            url,
            timeout=TIMEOUT,
            allow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
        elapsed_ms = int(
            (datetime.now() - started).total_seconds() * 1000
        )
        return {
            "ok": True,
            "status_code": response.status_code,
            "final_url": response.url,
            "elapsed_ms": elapsed_ms,
            "html": response.text,
            "headers": dict(response.headers),
            "error": None,
        }
    except requests.RequestException as exc:
        elapsed_ms = int(
            (datetime.now() - started).total_seconds() * 1000
        )
        return {
            "ok": False,
            "status_code": None,
            "final_url": url,
            "elapsed_ms": elapsed_ms,
            "html": "",
            "error": str(exc),
        }


def check_robots_txt(base_url: str) -> dict:
    """Проверяет /robots.txt: наличие, Disallow, Sitemap (регистронезависимо)."""
    parsed = urlparse(base_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    result: dict = {
        "url": robots_url,
        "status": None,
        "exists": False,
        "disallows": [],
        "sitemaps": [],
        "error": None,
    }
    try:
        resp = requests.get(
            robots_url,
            timeout=TIMEOUT,
            allow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
        result["status"] = resp.status_code
        if resp.status_code == 200:
            result["exists"] = True
            for line in resp.text.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if ":" not in line:
                    continue
                key, _, value = line.partition(":")
                key = key.strip().lower()
                value = value.strip()
                if key == "disallow":
                    result["disallows"].append(value)
                elif key == "sitemap" and value:
                    result["sitemaps"].append(value)
    except requests.RequestException as exc:
        result["error"] = str(exc)
    return result


def check_sitemap(base_url: str, robots: dict) -> dict:
    """Проверяет sitemap.xml: из robots.txt или стандартного пути."""
    parsed = urlparse(base_url)
    result: dict = {
        "url": None,
        "status": None,
        "exists": False,
        "url_count": None,
        "source": "not_found",
        "error": None,
    }

    candidates: list[str] = []
    if robots.get("sitemaps"):
        candidates = robots["sitemaps"][:1]
    else:
        candidates.append(f"{parsed.scheme}://{parsed.netloc}/sitemap.xml")

    for sitemap_url in candidates:
        result["url"] = sitemap_url
        try:
            resp = requests.get(
                sitemap_url,
                timeout=TIMEOUT,
                allow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            )
            result["status"] = resp.status_code
            if resp.status_code == 200:
                result["exists"] = True
                result["source"] = "robots.txt" if robots.get("sitemaps") else "standard_path"
                url_count = len(re.findall(r"<url>", resp.text, re.I))
                result["url_count"] = url_count
                break
        except requests.RequestException as exc:
            result["error"] = str(exc)
            break

    return result


# Явные страницы-challenge (достаточно одного маркера)
_ANTIBOT_STRONG_MARKERS = (
    "cf-browser-verification",
    "cf-challenge",
    "checking your browser",
    "challenge-platform",
    "just a moment...",
    "please complete the security check",
    "__cf_chl",
    "подтвердите, что вы не робот",
    "проверка браузера",
    "ddos-guard",
    "bot detection",
)

# Слабые маркеры (CDN в исходнике) — только вместе с малым контентом или HTTP-ошибкой
_ANTIBOT_WEAK_MARKERS = (
    "cloudflare",
    "attention required",
    "access denied",
    "captcha",
    "антибот",
)

_JS_SHELL_MARKERS = (
    "enable javascript",
    "javascript is required",
    "requires javascript",
    "включите javascript",
    "для работы сайта включите javascript",
    "this site requires javascript",
)

_MOJIBAKE_RE = re.compile(r"[ÐÑÂÃ][\wÐÑÂÃ]{2,}")


def looks_like_mojibake(text: str) -> bool:
    """Типичная кракозябра при неверной декодировке UTF-8."""
    if not text or len(text) < 8:
        return False
    matches = _MOJIBAKE_RE.findall(text)
    if not matches:
        return False
    bad_len = sum(len(m) for m in matches)
    return bad_len >= 8 and bad_len / len(text) >= 0.15


def _detect_antibot(
    html_lower: str, *, status: int | None, visible_len: int
) -> bool:
    if any(marker in html_lower for marker in _ANTIBOT_STRONG_MARKERS):
        return True
    stressed = (status is not None and status >= 400) or visible_len < 400
    if stressed and any(marker in html_lower for marker in _ANTIBOT_WEAK_MARKERS):
        return True
    return False


def _detect_js_shell(soup: BeautifulSoup, html_lower: str, visible_len: int) -> bool:
    if visible_len >= _MIN_VISIBLE_TEXT_CHARS:
        return False
    if any(marker in html_lower for marker in _JS_SHELL_MARKERS):
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


def assess_input_quality(fetch: dict) -> dict:
    """
    Проверяет, пригоден ли ответ для полноценного аудита.
    Возвращает suitable, reasons (категории для отчёта), details (уточнения).
    """
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

    if len(html_stripped) < _MIN_HTML_CHARS:
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

        if visible_len < _MIN_VISIBLE_TEXT_CHARS:
            _add_reason(reasons, "слишком мало контента")
            if f"Видимый текст: ~{visible_len} символов" not in details:
                details.append(f"Видимый текст: ~{visible_len} символов")

        if _detect_js_shell(soup, html_lower, visible_len):
            _add_reason(reasons, "возможная JS-загрузка страницы")

    if not reasons and html_stripped:
        return {"suitable": True, "reasons": [], "details": []}

    if not reasons:
        _add_reason(reasons, "другая причина")
        details.append("Ответ получен, но не удалось извлечь содержимое для анализа")

    return {"suitable": False, "reasons": reasons, "details": details}


def visible_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", text).lower()


def extract_links(soup: BeautifulSoup, base_url: str) -> list[str]:
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

    return links[:20]


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


def check_description_quality(description: str, title: str) -> list[dict]:
    issues: list[dict] = []

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


def check_title_quality(title: str) -> list[dict]:
    issues: list[dict] = []

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


def check_h1_offer_quality(h1_tags: list[str], title: str) -> list[dict]:
    issues: list[dict] = []

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


def check_cta_quality(cta: dict) -> list[dict]:
    issues: list[dict] = []
    strong, weak = cta["strong"], cta["weak"]

    if not strong and not weak:
        issues.append(
            make_issue(
                "high",
                "На главной нет заметных CTA",
                "Добавьте кнопку с действием: «Оставить заявку», «Получить расчёт», «Заказать консультацию».",
                category="conversion",
            )
        )
    elif not strong and weak:
        issues.append(
            make_issue(
                "high",
                "Только слабые CTA («подробнее», «узнать больше») — низкая конверсия",
                "Добавьте сильный CTA с конкретным действием рядом с оффером на первом экране.",
                evidence="; ".join(f"«{w}»" for w in weak[:3]),
                category="conversion",
            )
        )
    elif len(strong) == 1 and len(weak) >= 3:
        issues.append(
            make_issue(
                "medium",
                "Много слабых CTA конкурируют с одним сильным",
                "Оставьте один главный CTA на первом экране; вторичные ссылки сделайте менее заметными.",
                evidence=f"Сильный: «{strong[0]}»; слабые: {len(weak)}",
                category="conversion",
            )
        )

    action_ctas = strong + weak
    if len(action_ctas) > 6:
        issues.append(
            make_issue(
                "medium",
                f"Слишком много кнопок с призывом ({len(action_ctas)}) — расфокус",
                "На первом экране оставьте 1 основной и 1 вторичный CTA.",
                category="conversion",
            )
        )

    for dup in cta["duplicates"][:3]:
        issues.append(
            make_issue(
                "low",
                "Дублирование текста на кнопке CTA",
                "Исправьте вёрстку кнопки — повтор текста снижает доверие.",
                evidence=f"«{truncate_evidence(dup, 80)}»",
                category="conversion",
            )
        )

    return issues


def check_contacts(contacts: dict) -> list[dict]:
    issues: list[dict] = []
    has_phone = contacts["tel_link"] or contacts["phone_visible"]
    has_email = contacts["mailto"] or contacts["email_visible"]
    has_contact_path = contacts["contact_nav"]

    if not has_phone and not has_email and not has_contact_path:
        issues.append(
            make_issue(
                "high",
                "На главной нет быстрого доступа к контактам",
                "Добавьте телефон или email в шапку/первый экран и ссылку «Контакты» в меню.",
                category="conversion",
            )
        )
    elif not has_phone and not has_email and has_contact_path:
        issues.append(
            make_issue(
                "medium",
                "Контакты только через отдельную страницу",
                "Вынесите телефон или мессенджер в шапку — часть клиентов не дойдёт до /contacts.",
                category="conversion",
            )
        )
    elif has_contact_path and not has_phone:
        issues.append(
            make_issue(
                "low",
                "Телефон не виден на главной (есть страница контактов)",
                "Добавьте кликабельный номер в шапку для горячих лидов.",
                category="conversion",
            )
        )

    return issues


def check_trust_depth(trust: dict) -> list[dict]:
    issues: list[dict] = []
    s = trust["signals"]
    score = trust["score"]

    if score < 2:
        issues.append(
            make_issue(
                "high",
                f"Слабая социальная доказуемость (trust {score}/4)",
                "Добавьте: кейсы, страницу «О компании», политику конфиденциальности, телефон/реквизиты.",
                evidence=_trust_evidence(s),
                category="trust",
            )
        )
    elif score == 2:
        issues.append(
            make_issue(
                "medium",
                f"Trust-сигналы поверхностные (trust {score}/4)",
                "Усильте доверие: реальные кейсы с цифрами, отзывы, юр.данные, ссылка на политику в футере.",
                evidence=_trust_evidence(s),
                category="trust",
            )
        )
    elif score == 3 and not s["phone_or_legal"]:
        issues.append(
            make_issue(
                "low",
                "Нет телефона или юр.реквизитов на главной",
                "Добавьте ИНН/телефон в футер — повышает доверие для B2B и услуг.",
                evidence=_trust_evidence(s),
                category="trust",
            )
        )

    if s["cases"] and not s["about"]:
        issues.append(
            make_issue(
                "low",
                "Есть кейсы, но нет явной страницы «О компании»",
                "Добавьте блок о команде/опыте — клиенты покупают у людей, не только у портфолио.",
                category="trust",
            )
        )

    if not s["privacy_link"]:
        issues.append(
            make_issue(
                "medium",
                "Нет кликабельной ссылки на политику конфиденциальности",
                "Добавьте ссылку в футер (требование для форм и рекламы).",
                category="trust",
            )
        )

    return issues


def _trust_evidence(signals: dict) -> str:
    labels = {
        "cases": "кейсы",
        "about": "о компании",
        "privacy_link": "политика",
        "phone_or_legal": "тел/юр.",
    }
    present = [labels[k] for k, v in signals.items() if v]
    missing = [labels[k] for k, v in signals.items() if not v]
    parts = []
    if present:
        parts.append("есть: " + ", ".join(present))
    if missing:
        parts.append("нет: " + ", ".join(missing))
    return "; ".join(parts)


def check_canonical(soup: BeautifulSoup, final_url: str) -> dict:
    """Проверяет link rel=\"canonical\": наличие, самоссылающийся ли."""
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
        # Нормализуем для сравнения
        norm_href = href.rstrip("/")
        norm_final = final_url.rstrip("/")
        result["self_canonical"] = norm_href == norm_final
        result["differs_from_final"] = norm_href != norm_final
    return result


def check_hreflang(soup: BeautifulSoup) -> dict:
    """Проверяет hreflang-теги: link rel=\"alternate\" hreflang=\"...\"."""
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


def check_schema_org(soup: BeautifulSoup) -> dict:
    """Проверяет структурированные данные: JSON-LD + Microdata (itemscope/itemtype).

    Ищет типы: Product, Organization, BreadcrumbList.
    """
    result: dict = {
        "has_json_ld": False,
        "has_microdata": False,
        "source": None,  # "json_ld", "microdata", "both", None
        "product": False,
        "organization": False,
        "breadcrumb_list": False,
        "has_offer_price": False,
        "types_found": [],
        "errors": [],
    }

    # --- 1. JSON-LD ---
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
        except json.JSONDecodeError as exc:
            result["errors"].append(f"invalid JSON: {exc}")
            continue

        # Может быть список @graph или одиночный объект
        items = data if isinstance(data, list) else [data]
        if "@graph" in data:
            items = data["@graph"]

        for item in items:
            if not isinstance(item, dict):
                continue
            type_val = item.get("@type", "")
            if isinstance(type_val, list):
                types = type_val
            else:
                types = [type_val]

            for t in types:
                t_str = str(t)
                result["types_found"].append(t_str)
                if t_str == "Product":
                    result["product"] = True
                    # Проверяем наличие Offer с ценой внутри Product
                    offers = item.get("offers") or item.get("aggregateOffer") or {}
                    if isinstance(offers, dict):
                        if offers.get("price") or offers.get("highPrice") or offers.get("lowPrice"):
                            result["has_offer_price"] = True
                    elif isinstance(offers, list):
                        for offer in offers:
                            if isinstance(offer, dict) and (offer.get("price") or offer.get("highPrice")):
                                result["has_offer_price"] = True
                                break
                elif t_str == "Organization":
                    result["organization"] = True
                elif t_str == "BreadcrumbList":
                    result["breadcrumb_list"] = True

    result["has_json_ld"] = bool(result["types_found"])

    # --- 2. Microdata (itemscope + itemtype) ---
    microdata_types_found: list[str] = []
    for tag in soup.find_all(itemscope=True):
        itemtype = tag.get("itemtype", "")
        if not itemtype:
            continue
        # itemtype обычно вида "http://schema.org/Product"
        short_type = itemtype.rstrip("/").rsplit("/", 1)[-1]
        if short_type in ("Product", "Organization", "BreadcrumbList"):
            microdata_types_found.append(short_type)
            if short_type == "Product":
                result["product"] = True
                # Ищем цену через itemprop="price" внутри Product
                price_tag = tag.find(itemprop=re.compile(r"^price$", re.I))
                if price_tag:
                    price_val = price_tag.get("content") or price_tag.get_text(strip=True)
                    if price_val:
                        result["has_offer_price"] = True
            elif short_type == "Organization":
                result["organization"] = True
            elif short_type == "BreadcrumbList":
                result["breadcrumb_list"] = True

    if microdata_types_found:
        result["has_microdata"] = True
        result["types_found"].extend(microdata_types_found)

    # Определяем источник
    if result["has_json_ld"] and result["has_microdata"]:
        result["source"] = "both"
    elif result["has_json_ld"]:
        result["source"] = "json_ld"
    elif result["has_microdata"]:
        result["source"] = "microdata"

    return result


def check_alt_attributes(soup: BeautifulSoup) -> dict:
    """Проверяет alt-атрибуты у изображений."""
    images = soup.find_all("img")
    total = len(images)
    no_alt = 0
    empty_alt = 0
    ok_alt = 0
    alt_counter: dict[str, int] = {}

    for img in images:
        if "alt" not in img.attrs:
            no_alt += 1
        elif img["alt"] == "":
            empty_alt += 1
        else:
            ok_alt += 1
            alt_text = img["alt"].strip().lower()
            if alt_text:
                alt_counter[alt_text] = alt_counter.get(alt_text, 0) + 1

    no_alt_pct = round(100 * no_alt / total, 1) if total else 0.0
    empty_alt_pct = round(100 * empty_alt / total, 1) if total else 0.0
    problematic_pct = round(100 * (no_alt + empty_alt) / total, 1) if total else 0.0

    duplicate_alts = [alt for alt, cnt in alt_counter.items() if cnt >= 3]

    return {
        "total_images": total,
        "no_alt": no_alt,
        "empty_alt": empty_alt,
        "ok_alt": ok_alt,
        "no_alt_pct": no_alt_pct,
        "empty_alt_pct": empty_alt_pct,
        "problematic_pct": problematic_pct,
        "duplicate_alts": duplicate_alts[:5],
    }


def run_quality_checks(
    *,
    title: str,
    description: str,
    h1_tags: list[str],
    cta: dict,
    contacts: dict,
    trust: dict,
) -> list[dict]:
    issues: list[dict] = []
    issues.extend(check_description_quality(description, title))
    issues.extend(check_title_quality(title))
    issues.extend(check_h1_offer_quality(h1_tags, title))
    issues.extend(check_cta_quality(cta))
    issues.extend(check_contacts(contacts))
    issues.extend(check_trust_depth(trust))

    severity_order = {"high": 0, "medium": 1, "low": 2}
    issues.sort(key=lambda x: (severity_order.get(x["severity"], 9), x.get("category", "")))
    return issues


_PRICE_ON_PAGE_RE = re.compile(
    r"\d+[\s,.]?\d*\s*(?:₽|руб\.?|р\.|rub)", re.I
)


def _ecommerce_search_blob(
    text_lower: str, internal_links: list[str], soup: BeautifulSoup
) -> str:
    parts = [text_lower, " ".join(internal_links).lower()]
    for a in soup.find_all("a", href=True):
        parts.append(a.get_text(strip=True).lower())
        parts.append(a["href"].lower())
    return " ".join(parts)


def collect_ecommerce_signals(
    soup: BeautifulSoup,
    text_lower: str,
    internal_links: list[str],
    cta: dict,
    contacts: dict,
    trust: dict,
) -> dict[str, bool]:
    """Presence-сигналы магазина на главной (без обхода других страниц).

    v0.5.2: добавлено детектирование Microdata (itemscope/itemtype/itemprop).
    """
    blob = _ecommerce_search_blob(text_lower, internal_links, soup)
    cta_blob = " ".join(cta.get("all", [])).lower()
    html_snippet = str(soup)[:80000].lower()

    catalog = bool(
        re.search(r"каталог|catalog|/shop|/store|магазин|товар", blob)
    )
    categories = bool(
        re.search(r"категори|category|/category|разделы каталог", blob)
    ) or sum(
        1 for link in internal_links if re.search(r"categor|cat/|/cat-", link, re.I)
    ) >= 2

    # --- Microdata-сигналы (v0.5.2) ---
    microdata_product = bool(soup.find(itemtype=re.compile(r"schema\.org/Product", re.I)))
    microdata_price = bool(soup.find(itemprop=re.compile(r"^price$", re.I)))
    microdata_review = bool(
        soup.find(itemtype=re.compile(r"schema\.org/Review", re.I))
        or soup.find(itemprop=re.compile(r"^review$", re.I))
    )

    product_cards = bool(
        soup.find(class_=re.compile(r"product", re.I))
        or soup.find(attrs={"data-product": True})
        or re.search(r"product-card|product_item|товарная карточка", blob)
        or microdata_product
    )
    prices = len(_PRICE_ON_PAGE_RE.findall(text_lower)) >= 2 or bool(
        re.search(r'class=["\'][^"\']*price|item-price|product-price', html_snippet)
    ) or microdata_price
    buy_buttons = any(
        k in cta_blob + blob for k in ("купить", "в корзину", "add to cart", "buy now")
    )

    cart = bool(re.search(r"корзин|/cart|basket", blob))
    checkout = bool(
        re.search(r"оформлен|checkout|/order|заказ оформ|оформить заказ", blob)
    )

    delivery = bool(
        re.search(r"доставк|shipping|курьер|самовывоз|почтой|pickup", blob)
    )
    payment = bool(
        re.search(r"оплат|payment|картой|visa|mastercard|сбп|наличн", blob)
    )

    search = bool(
        soup.find("input", attrs={"type": re.compile(r"search", re.I)})
        or re.search(r"type=[\"']search[\"']|поиск по|search products", blob)
    )
    filters = bool(re.search(r"фильтр|filter|сортиров|sort by|сортировать", blob))

    returns = bool(re.search(r"возврат|обмен|return policy|refund", blob))
    contacts_ok = bool(
        contacts.get("contact_nav")
        or contacts.get("phone_visible")
        or contacts.get("email_visible")
        or contacts.get("mailto")
    )
    phone = bool(contacts.get("phone_visible") or contacts.get("tel_link"))
    privacy = bool(trust.get("signals", {}).get("privacy_link"))
    reviews = bool(
        re.search(r"отзыв|review|рейтинг|rating|★|⭐", blob)
        or microdata_review
    )

    return {
        "catalog": catalog,
        "categories": categories,
        "product_cards": product_cards,
        "prices": prices,
        "buy_buttons": buy_buttons,
        "cart": cart,
        "checkout": checkout,
        "delivery": delivery,
        "payment": payment,
        "search": search,
        "filters": filters,
        "returns": returns,
        "contacts": contacts_ok,
        "phone": phone,
        "privacy": privacy,
        "reviews": reviews,
    }


def run_ecommerce_checks(signals: dict[str, bool]) -> list[dict]:
    """Проверки магазина: только отсутствующие сигналы, формулировки — про главную."""
    issues: list[dict] = []
    _hp = "На главной странице (в доступных данных)"

    checks: tuple[tuple[str, str, str, str, str, str], ...] = (
        (
            "catalog",
            "high",
            f"{_hp} не найден явный раздел или ссылка на каталог товаров",
            "Покупатель должен сразу понять, где смотреть ассортимент; без каталога в меню или на первом экране растёт отказ.",
            "Добавьте на главную заметную ссылку «Каталог» / «Магазин» в шапку или первый экран.",
            "Упростится навигация к товарам и снизится доля уходов с главной.",
        ),
        (
            "categories",
            "medium",
            f"{_hp} не найдены явные категории товаров",
            "Категории помогают быстро сузить выбор; на главной они задают структуру ассортимента.",
            "Покажите на главной блок категорий или выпадающий список разделов каталога.",
            "Пользователь быстрее найдёт нужный тип товара без лишних кликов.",
        ),
        (
            "product_cards",
            "high",
            f"{_hp} не найдены явные товарные карточки",
            "Карточки на главной демонстрируют ассортимент и цену; без них страница не выглядит как магазин.",
            "Добавьте блок «Хиты», «Новинки» или витрину с названием, фото и ценой товара.",
            "Выше вовлечённость и переходы в каталог с первого экрана.",
        ),
        (
            "prices",
            "high",
            f"{_hp} не найдены явные цены у товаров",
            "Цена — ключевой фактор решения о покупке; её отсутствие на видимой части главной снижает доверие.",
            "Выведите цену на карточках товаров на главной (и валюту: ₽ / руб.).",
            "Меньше сомнений перед добавлением в корзину.",
        ),
        (
            "buy_buttons",
            "high",
            f"{_hp} не найдены кнопки «Купить» / «В корзину»",
            "Явное действие покупки на главной ускоряет конверсию с витрины и акций.",
            "Добавьте кнопки «В корзину» / «Купить» на товарные блоки главной.",
            "Больше добавлений в корзину с первого визита.",
        ),
        (
            "cart",
            "high",
            f"{_hp} не найдена ссылка или иконка корзины",
            "Корзина в шапке — привычный ориентир; без неё пользователь не видит, как завершить покупку.",
            "Добавьте иконку/ссылку «Корзина» в шапку сайта (видимую на главной).",
            "Понятнее путь к оформлению заказа.",
        ),
        (
            "checkout",
            "medium",
            f"{_hp} не найдена ссылка на оформление заказа",
            "Даже при корзине важно показать, что оформление доступно — это снижает тревогу перед покупкой.",
            "Добавьте в меню или футер ссылку «Оформить заказ» / «Checkout» (если есть корзина).",
            "Меньше брошенных корзин из-за неясного следующего шага.",
        ),
        (
            "delivery",
            "medium",
            f"{_hp} не найден явный блок или ссылка про доставку",
            "Условия доставки влияют на решение; на главной достаточно краткой ссылки или тезиса.",
            "Добавьте в шапку, футер или первый экран ссылку «Доставка» с ключевыми условиями.",
            "Меньше вопросов в поддержку и выше доверие к заказу.",
        ),
        (
            "payment",
            "medium",
            f"{_hp} не найден явный блок или ссылка про оплату",
            "Способы оплаты снимают возражения; на главной часто достаточно иконок или ссылки «Оплата».",
            "Укажите на главной (футер/блок доверия) принимаемые способы оплаты или ссылку на раздел.",
            "Снижение страха перед первой покупкой.",
        ),
        (
            "search",
            "medium",
            f"{_hp} не найден поиск по товарам",
            "Поиск важен при широком ассортименте; на главной поле поиска — ожидаемый элемент магазина.",
            "Добавьте поле «Поиск» в шапку главной страницы.",
            "Быстрее нахождение нужного товара, выше конверсия у целевых визитов.",
        ),
        (
            "filters",
            "low",
            f"{_hp} не найдены фильтры или сортировка",
            "На главной фильтры реже обязательны, но сортировка/фильтр в витрине упрощает выбор.",
            "Если на главной есть список товаров — добавьте базовую сортировку (цена, новизна).",
            "Удобнее выбор из витрины без ухода в глубину каталога.",
        ),
        (
            "returns",
            "medium",
            f"{_hp} не найдена информация о возврате или обмене",
            "Условия возврата повышают доверие к магазину, особенно для новых покупателей.",
            "Добавьте в футер ссылку «Возврат и обмен» или краткий тезис на главной.",
            "Меньше сомнений перед первым заказом.",
        ),
        (
            "contacts",
            "high",
            f"{_hp} не найдены явные контакты",
            "Контакты на главной нужны для вопросов по заказу и доверия к продавцу.",
            "Добавьте в шапку или футер ссылку «Контакты» и/или email.",
            "Проще связаться с магазином до покупки.",
        ),
        (
            "phone",
            "high",
            f"{_hp} не найден телефон для связи",
            "Телефон часто используют для уточнения наличия и доставки перед оплатой.",
            "Разместите кликабельный телефон в шапке или футере главной.",
            "Больше доверия и обращений от готовых купить.",
        ),
        (
            "privacy",
            "medium",
            f"{_hp} не найдена ссылка на политику конфиденциальности",
            "Политика ожидается при сборе данных в формах и оформлении заказа.",
            "Добавьте ссылку «Политика конфиденциальности» в футер (видимый на главной).",
            "Соответствие ожиданиям пользователей и требованиям к формам.",
        ),
        (
            "reviews",
            "medium",
            f"{_hp} не найдены отзывы или рейтинг",
            "Социальное доказательство на главной усиливает доверие к товарам и магазину.",
            "Добавьте блок отзывов, рейтинг или ссылку «Отзывы» на видимой части главной.",
            "Выше конверсия за счёт снижения сомнений в качестве.",
        ),
    )

    for key, severity, issue, why, recommendation, effect in checks:
        if key == "filters" and not signals.get("catalog") and not signals.get("product_cards"):
            continue
        if key == "checkout" and not signals.get("cart"):
            continue
        if not signals.get(key):
            issues.append(
                make_ecommerce_issue(severity, issue, why, recommendation, effect)
            )

    severity_order = {"high": 0, "medium": 1, "low": 2}
    issues.sort(key=lambda x: severity_order.get(x["severity"], 9))
    return issues


def _sort_issues(issues: list[dict]) -> list[dict]:
    severity_order = {"high": 0, "medium": 1, "low": 2}
    issues.sort(key=lambda x: (severity_order.get(x["severity"], 9), x.get("category", "")))
    return issues


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
) -> dict:
    """Эвристическая классификация типа сайта по главной странице."""
    h1_blob = " ".join(h1_tags).lower()
    links_blob = " ".join(internal_links).lower()
    cta_blob = " ".join(cta.get("all", [])).lower()
    haystack = " ".join(
        (title, description, h1_blob, text_lower, cta_blob)
    ).lower()

    type_signals = {
        "ecommerce": _CLASSIFY_ECOMMERCE,
        "services": _CLASSIFY_SERVICES,
        "corporate": _CLASSIFY_CORPORATE,
        "saas": _CLASSIFY_SAAS,
    }

    ranked: list[tuple[str, int, list[str]]] = []
    for site_type, signals in type_signals.items():
        extra = _classify_extra_hits(site_type, trust=trust, cta=cta)
        score, hits = _classify_score_type(signals, haystack, links_blob, extra)
        ranked.append((site_type, score, hits))

    ranked.sort(key=lambda x: x[1], reverse=True)
    primary_type, primary_score, primary_hits = ranked[0]

    if (
        primary_score < _CLASSIFY_MIN_PRIMARY_SCORE
        or len(primary_hits) < _CLASSIFY_MIN_HITS
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
            sec_score >= _CLASSIFY_SECONDARY_MIN_SCORE
            and len(sec_hits) >= _CLASSIFY_MIN_HITS
            and primary_score - sec_score <= _CLASSIFY_SECONDARY_GAP_MAX
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


def analyze_html(html: str, url: str) -> dict:
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
    )
    issues = run_quality_checks(
        title=title,
        description=description,
        h1_tags=h1_tags,
        cta=cta,
        contacts=contacts,
        trust=trust,
    )

    ecommerce_checklist = None
    ecommerce_issues: list[dict] = []
    if site_type.get("primary_type") == "ecommerce":
        ecommerce_checklist = collect_ecommerce_signals(
            soup, text_lower, internal_links, cta, contacts, trust
        )
        ecommerce_issues = run_ecommerce_checks(ecommerce_checklist)
        issues = _sort_issues(issues + ecommerce_issues)

    # Новые проверки v0.5
    canonical = check_canonical(soup, url)
    schema = check_schema_org(soup)
    alt = check_alt_attributes(soup)
    hreflang = check_hreflang(soup)

    return {
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
        "issues": issues,
        "canonical": canonical,
        "schema": schema,
        "alt": alt,
        "hreflang": hreflang,
    }


def build_insufficient_data_report(
    url: str, fetch: dict, quality: dict
) -> str:
    """Отчёт, когда входные данные не пригодны для аудита."""
    lines: list[str] = []
    lines.append(f"# Аудит сайта (v{VERSION})")
    lines.append("")
    lines.append(f"- **Исходный URL:** {url}")
    lines.append(f"- **Итоговый URL:** {fetch.get('final_url', url)}")
    if fetch.get("status_code") is not None:
        lines.append(f"- **HTTP статус:** {fetch['status_code']}")
    lines.append(f"- **Время ответа:** {fetch.get('elapsed_ms', '—')} мс")
    lines.append(
        f"- **Дата проверки:** {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    lines.append("")
    lines.append("## Статус анализа")
    lines.append("")
    lines.append("**Статус анализа:** недостаточно данных")
    lines.append("")
    lines.append("**Причина:**")
    for reason in quality.get("reasons", ["другая причина"]):
        lines.append(f"- {reason}")
    for detail in quality.get("details", []):
        lines.append(f"- _{detail}_")
    lines.append("")
    lines.append("## Рекомендация")
    lines.append("")
    lines.append(
        "Для корректного анализа может потребоваться браузерный режим "
        "(Playwright) или ручная проверка."
    )
    lines.append("")
    lines.append("---")
    lines.append(
        f"*Отчёт v{VERSION}: полноценный аудит не выполнялся — "
        "недостаточно данных с главной страницы.*"
    )
    return "\n".join(lines)


def build_report(
    url: str,
    fetch: dict,
    analysis: dict | None,
    quality: dict | None = None,
    robots: dict | None = None,
    sitemap: dict | None = None,
) -> str:
    lines: list[str] = []
    lines.append(f"# Аудит сайта (v{VERSION})")
    lines.append("")
    lines.append(f"- **Исходный URL:** {url}")
    lines.append(f"- **Итоговый URL:** {fetch.get('final_url', url)}")
    if fetch.get("status_code") is not None:
        lines.append(f"- **HTTP статус:** {fetch['status_code']}")
    lines.append(f"- **Время ответа:** {fetch.get('elapsed_ms', '—')} мс")
    lines.append(
        f"- **Дата проверки:** {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    lines.append("")

    if quality and not quality.get("suitable", True):
        return build_insufficient_data_report(url, fetch, quality)

    if not fetch.get("ok"):
        lines.append("## Ошибка загрузки")
        lines.append("")
        lines.append(
            f"Не удалось загрузить страницу: {fetch.get('error', 'неизвестная ошибка')}"
        )
        return "\n".join(lines)

    if not analysis:
        return "\n".join(lines)

    high = sum(1 for i in analysis["issues"] if i["severity"] == "high")
    medium = sum(1 for i in analysis["issues"] if i["severity"] == "medium")
    low = sum(1 for i in analysis["issues"] if i["severity"] == "low")

    lines.append("## Краткое резюме")
    lines.append("")
    lines.append(f"- Критичных: **{high}** | Средних: **{medium}** | Низких: **{low}**")
    lines.append(
        f"- Trust-оценка: **{analysis['trust']['score']}/{analysis['trust']['max']}**"
    )
    lines.append("")

    st = analysis.get("site_type", {})
    lines.append("## Тип сайта")
    lines.append("")
    primary_key = st.get("primary_type", "unknown")
    primary_label = SITE_TYPE_LABELS.get(primary_key, primary_key)
    primary_score = st.get("primary_score", 0)
    lines.append(f"- **Основной тип:** {primary_label} (**{primary_score}%**)")
    if st.get("secondary_type"):
        sec_key = st["secondary_type"]
        sec_label = SITE_TYPE_LABELS.get(sec_key, sec_key)
        lines.append(
            f"- **Вторичный тип:** {sec_label} (**{st.get('secondary_score', 0)}%**) "
            "— только для контекста"
        )
    if st.get("primary_hits"):
        lines.append(
            "- **Признаки (основной):** " + ", ".join(st["primary_hits"][:12])
        )
    if st.get("secondary_hits"):
        lines.append(
            "- **Признаки (вторичный):** " + ", ".join(st["secondary_hits"][:8])
        )
    lines.append("")

    # --- v0.5: Технический SEO ---
    lines.append("## Технический SEO")
    lines.append("")
    if robots:
        if robots.get("exists"):
            dis_count = len(robots["disallows"])
            sitemap_sources = ", ".join(robots["sitemaps"]) if robots["sitemaps"] else "не указаны"
            lines.append(f"- **robots.txt:** ✅ найден ({dis_count} Disallow, Sitemap: {sitemap_sources})")
        else:
            status = robots.get("status")
            status_info = f" (HTTP {status})" if status else ""
            lines.append(f"- **robots.txt:** ❌ не найден{status_info}")
    if sitemap:
        if sitemap.get("exists"):
            url_count = sitemap.get("url_count", "?")
            source = "robots.txt" if sitemap.get("source") == "robots.txt" else "стандартный путь"
            lines.append(f"- **sitemap.xml:** ✅ доступен (~{url_count} URL, источник: {source})")
        else:
            status = sitemap.get("status")
            status_info = f" (HTTP {status})" if status else ""
            lines.append(f"- **sitemap.xml:** ❌ не найден{status_info}")

    canonical = analysis.get("canonical")
    if canonical:
        if canonical.get("present"):
            self_c = canonical.get("self_canonical")
            if self_c:
                lines.append("- **canonical:** ✅ указан, самоссылающийся")
            else:
                lines.append(f"- **canonical:** ⚠️ указан, но ведёт на `{canonical.get('href', '?')}`")
        else:
            lines.append("- **canonical:** ❌ не указан")
    # --- v0.5.2: X-Robots-Tag из HTTP-заголовков ---
    x_robots_tag = None
    if fetch.get("headers"):
        x_robots_tag = fetch["headers"].get("X-Robots-Tag") or fetch["headers"].get("x-robots-tag")
    if x_robots_tag:
        lines.append(f"- **X-Robots-Tag:** `{x_robots_tag}`")
    lines.append("")

    # --- v0.5: hreflang ---
    hreflang = analysis.get("hreflang")
    if hreflang:
        lines.append("## Hreflang (языковые версии)")
        lines.append("")
        if hreflang.get("present"):
            langs = ", ".join(hreflang["languages"])
            lines.append(f"- **hreflang:** ✅ найден ({len(hreflang['tags'])} тегов, языки: {langs})")
            if hreflang.get("x_default"):
                lines.append("- **x-default:** ✅ указан")
            else:
                lines.append("- **x-default:** ❌ не указан (рекомендуется для главной)")
        else:
            lines.append("- **hreflang:** ❌ не найден")
        lines.append("")

    # --- v0.5: Структурированные данные (Schema.org) ---
    schema = analysis.get("schema")
    if schema:
        lines.append("## Структурированные данные (Schema.org)")
        lines.append("")
        # Источник
        source_labels = {
            "json_ld": "JSON-LD",
            "microdata": "Microdata",
            "both": "JSON-LD + Microdata",
        }
        src_label = source_labels.get(schema.get("source"), "не обнаружена")
        lines.append(f"- **Формат:** {src_label}")
        lines.append(f"- **JSON-LD:** {'✅ найден' if schema.get('has_json_ld') else '❌ не найден'}")
        lines.append(f"- **Microdata:** {'✅ найдена' if schema.get('has_microdata') else '❌ не найдена'}")
        if schema.get("has_json_ld") or schema.get("has_microdata"):
            lines.append(f"- **Product:** {'✅' if schema.get('product') else '❌'} найден")
            lines.append(f"- **Organization:** {'✅' if schema.get('organization') else '❌'} найден")
            lines.append(f"- **BreadcrumbList:** {'✅' if schema.get('breadcrumb_list') else '❌'} найден")
            lines.append(f"- **Offer / Price:** {'✅' if schema.get('has_offer_price') else '❌'} цена в разметке")
            if schema.get("types_found"):
                lines.append(f"- **Все типы:** {', '.join(schema['types_found'][:10])}")
            if schema.get("errors"):
                for err in schema["errors"][:3]:
                    lines.append(f"- ⚠️ Ошибка: {err}")
        lines.append("")

    # --- v0.5: Изображения ---
    alt = analysis.get("alt")
    if alt:
        lines.append("## Изображения")
        lines.append("")
        lines.append(f"- **Всего `<img>`:** {alt.get('total_images', 0)}")
        if alt.get("total_images", 0) > 0:
            no_alt = alt.get("no_alt", 0)
            no_alt_pct = alt.get("no_alt_pct", 0.0)
            empty_alt = alt.get("empty_alt", 0)
            problematic_pct = alt.get("problematic_pct", 0.0)
            severity = "HIGH" if problematic_pct >= 30 else ("MEDIUM" if problematic_pct >= 10 else "LOW")
            lines.append(f"- Без alt: **{no_alt} ({no_alt_pct}%)** — {severity}")
            if empty_alt:
                lines.append(f"- Пустые alt (допустимо): {empty_alt}")
            if alt.get("duplicate_alts"):
                dups = "; ".join(f"«{a}»" for a in alt["duplicate_alts"][:3])
                lines.append(f"- Дублирующиеся alt: {dups}")
        lines.append("")

    checklist = analysis.get("ecommerce_checklist")
    if primary_key == "ecommerce" and checklist:
        lines.append("## Аудит интернет-магазина (главная)")
        lines.append("")
        lines.append(
            "_Проверка по видимой части главной страницы и ссылкам в её HTML; "
            "разделы могут быть на других страницах сайта._"
        )
        lines.append("")
        for group_name, items in _ECOMMERCE_CHECKLIST_GROUPS:
            lines.append(f"**{group_name}**")
            for sig_key, label in items:
                mark = "да" if checklist.get(sig_key) else "нет"
                lines.append(f"- {label}: **{mark}**")
            lines.append("")

        eco_issues = analysis.get("ecommerce_issues") or []
        lines.append("## Проблемы интернет-магазина")
        lines.append("")
        if eco_issues:
            for idx, item in enumerate(eco_issues, 1):
                sev = item["severity"].upper()
                lines.append(f"{idx}. **[{sev}] [ecommerce]** {item['issue']}")
                lines.append(f"   - Почему важно: {item['why']}")
                lines.append(f"   - Что исправить: {item['recommendation']}")
                lines.append(f"   - Ожидаемый эффект: {item['effect']}")
        else:
            lines.append(
                "По главной странице не выявлено явных пробелов в базовых элементах магазина."
            )
        lines.append("")

    general_issues = [
        i for i in analysis["issues"] if i.get("category") != "ecommerce"
    ]

    lines.append("## SEO и оффер")
    lines.append("")
    desc = analysis["description"]
    lines.append(
        f"- **Title** ({len(analysis['title'])} симв.): {analysis['title'] or '—'}"
    )
    lines.append(
        f"- **Description** ({len(desc)} симв.): {truncate_evidence(desc, 200) or '—'}"
    )
    lines.append(f"- **H1:** {', '.join(analysis['h1']) if analysis['h1'] else '—'}")
    lines.append("")

    lines.append("## Конверсия")
    lines.append("")
    cta = analysis["cta"]
    if cta["strong"]:
        lines.append("**Сильные CTA:** " + ", ".join(f"«{c}»" for c in cta["strong"][:5]))
    else:
        lines.append("**Сильные CTA:** не найдены")
    if cta["weak"]:
        lines.append("**Слабые CTA:** " + ", ".join(f"«{c}»" for c in cta["weak"][:5]))
    lines.append("")

    c = analysis["contacts"]
    contact_parts = []
    if c["phone_visible"] or c["tel_link"]:
        contact_parts.append("телефон")
    if c["email_visible"] or c["mailto"]:
        contact_parts.append("email")
    if c["contact_nav"]:
        contact_parts.append("страница контактов")
    lines.append(
        "**Контакты на главной:** "
        + (", ".join(contact_parts) if contact_parts else "не обнаружены")
    )
    if c.get("phone_sample"):
        lines.append(f"- Телефон: `{c['phone_sample']}`")
    if c.get("email_sample"):
        lines.append(f"- Email: `{c['email_sample']}`")
    lines.append("")

    lines.append("## Доверие")
    lines.append("")
    s = analysis["trust"]["signals"]
    for key, label in (
        ("cases", "Кейсы / портфолио"),
        ("about", "О компании"),
        ("privacy_link", "Политика конфиденциальности"),
        ("phone_or_legal", "Телефон / юр.данные"),
    ):
        mark = "да" if s[key] else "нет"
        lines.append(f"- {label}: **{mark}**")
    lines.append("")

    lines.append("## Ключевые проблемы")
    lines.append("")
    if general_issues:
        for idx, item in enumerate(general_issues[:8], 1):
            sev = item["severity"].upper()
            cat = item.get("category", "")
            prefix = f"[{sev}]" + (f" [{cat}]" if cat else "")
            lines.append(f"{idx}. **{prefix}** {item['issue']}")
            if item.get("evidence"):
                lines.append(f"   - Пример: {item['evidence']}")
            lines.append(f"   - Рекомендация: {item['recommendation']}")
    else:
        lines.append("Существенных общих проблем по коммерческим эвристикам не найдено.")
    lines.append("")

    lines.append("## Что сделать в первую очередь")
    lines.append("")
    priority = [
        i for i in general_issues if i["severity"] in ("high", "medium")
    ][:7]
    if priority:
        for idx, item in enumerate(priority, 1):
            lines.append(f"{idx}. {item['recommendation']}")
    else:
        lines.append("1. Протестируйте первый экран и главный CTA на конверсию.")
        lines.append("2. Следующий шаг — технический аудит (скорость, alt, формы).")
    lines.append("")

    lines.append("---")
    footer = (
        f"*Отчёт v{VERSION}: главная страница; тип сайта — эвристика по главной; "
        "оценка качества оффера, конверсии и доверия."
    )
    if primary_key == "ecommerce":
        footer += " Для интернет-магазина — доп. проверки по видимой части главной.*"
    else:
        footer += "*"
    lines.append(footer)

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=f"Коммерческий аудит сайта (v{VERSION}): главная, Markdown-отчёт."
    )
    parser.add_argument("url", help="URL сайта, например https://example.com")
    args = parser.parse_args()

    try:
        url = normalize_url(args.url)
    except ValueError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1

    print(f"Аудит: {url}")
    fetch = fetch_page(url)
    quality = assess_input_quality(fetch)

    # v0.5: проверка robots.txt и sitemap.xml
    robots = check_robots_txt(url)
    sitemap = check_sitemap(url, robots)

    analysis = None
    if fetch.get("ok") and fetch.get("html") and quality.get("suitable"):
        analysis = analyze_html(fetch["html"], fetch["final_url"])

    report = build_report(url, fetch, analysis, quality, robots=robots, sitemap=sitemap)

    archive_path, latest_path = save_reports(url, report)
    print(f"Отчёт: {latest_path}")
    print(f"Архив: {archive_path}")
    return 0 if fetch["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
