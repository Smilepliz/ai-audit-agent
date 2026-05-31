"""Проверки конверсии: CTA, контакты."""

from __future__ import annotations

from audit.models import Issue, make_issue


def check_cta_quality(cta: dict) -> list[Issue]:
    issues: list[Issue] = []
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
                evidence=f"«{dup[:80]}»" if len(dup) > 80 else f"«{dup}»",
                category="conversion",
            )
        )

    return issues


def check_contacts(contacts: dict) -> list[Issue]:
    issues: list[Issue] = []
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


def run_conversion_checks(analysis: dict) -> list[Issue]:
    issues: list[Issue] = []
    issues.extend(check_cta_quality(analysis.get("cta", {})))
    issues.extend(check_contacts(analysis.get("contacts", {})))
    return issues
