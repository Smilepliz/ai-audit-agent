"""Генерация Markdown-отчёта."""

from __future__ import annotations

from datetime import datetime

from audit.config import VERSION, SITE_TYPE_LABELS, ECOMMERCE_CHECKLIST_GROUPS
from audit.utils import truncate_evidence


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

    # Технический SEO
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

    x_robots_tag = None
    if fetch.get("headers"):
        x_robots_tag = fetch["headers"].get("X-Robots-Tag") or fetch["headers"].get("x-robots-tag")
    if x_robots_tag:
        lines.append(f"- **X-Robots-Tag:** `{x_robots_tag}`")
    lines.append("")

    # Hreflang
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

    # Schema.org
    schema = analysis.get("schema")
    if schema:
        lines.append("## Структурированные данные (Schema.org)")
        lines.append("")
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

    # Изображения
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

    # Ecommerce чеклист
    checklist = analysis.get("ecommerce_checklist")
    if primary_key == "ecommerce" and checklist:
        lines.append("## Аудит интернет-магазина (главная)")
        lines.append("")
        lines.append(
            "_Проверка по видимой части главной страницы и ссылкам в её HTML; "
            "разделы могут быть на других страницах сайта._"
        )
        lines.append("")
        for group_name, items in ECOMMERCE_CHECKLIST_GROUPS:
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
