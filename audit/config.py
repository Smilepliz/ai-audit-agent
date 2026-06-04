"""Конфигурация и константы аудита."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AuditConfig:
    """Настройки аудита. Могут быть загружены из JSON/YAML."""

    user_agent: str = (
        "Mozilla/5.0 (compatible; SiteAuditBot/0.5; +https://example.com/bot)"
    )
    timeout: int = 15
    min_html_chars: int = 200
    min_visible_text_chars: int = 250
    classify_min_primary_score: int = 25
    classify_min_hits: int = 2
    classify_secondary_min_score: int = 25
    classify_secondary_gap_max: int = 25
    max_internal_links: int = 20
    reports_dir: str = "reports"

    deepseek_model: str = "deepseek-chat"
    deepseek_temperature: float = 0.3
    deepseek_max_tokens: int = 2000

    def load_from_file(self, path: str) -> None:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        raw: dict[str, Any] = {}
        if p.suffix in (".json",):
            raw = json.loads(p.read_text(encoding="utf-8"))
        else:
            raise ValueError(f"Unsupported config format: {p.suffix}")
        for key, value in raw.items():
            if hasattr(self, key):
                setattr(self, key, value)


# --- Константы (перенесены из audit.py) ---

VERSION = "0.6"

# Все отчёты только в reports/<domain>/ (latest.md + архивы), не в корне reports/.
REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"

# Сводка чеклиста ecommerce для отчёта (группа → ключи сигналов)
ECOMMERCE_CHECKLIST_GROUPS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
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

SITE_TYPE_LABELS = {
    "ecommerce": "Интернет-магазин",
    "services": "Сайт услуг",
    "corporate": "Корпоративный сайт",
    "saas": "SaaS / онлайн-сервис",
    "unknown": "Не удалось определить",
}

# (подстрока для поиска, вес, подпись в отчёте)
CLASSIFY_ECOMMERCE = (
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

CLASSIFY_SERVICES = (
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

CLASSIFY_CORPORATE = (
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

CLASSIFY_SAAS = (
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

# Явные страницы-challenge (достаточно одного маркера)
ANTIBOT_STRONG_MARKERS = (
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
ANTIBOT_WEAK_MARKERS = (
    "cloudflare",
    "attention required",
    "access denied",
    "captcha",
    "антибот",
)

JS_SHELL_MARKERS = (
    "enable javascript",
    "javascript is required",
    "requires javascript",
    "включите javascript",
    "для работы сайта включите javascript",
    "this site requires javascript",
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
MOJIBAKE_RE = re.compile(r"[ÐÑÂÃ][\wÐÑÂÃ]{2,}")
