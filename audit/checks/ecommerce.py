"""Ecommerce-сигналы и проверки."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from audit.config import AuditConfig
from audit.models import Issue, EcommerceIssue, make_ecommerce_issue


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
    """Presence-сигналы магазина на главной (без обхода других страниц)."""
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


def run_ecommerce_checks(signals: dict[str, bool]) -> list[Issue]:
    """Проверки магазина: только отсутствующие сигналы, формулировки — про главную."""
    issues: list[Issue] = []
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
