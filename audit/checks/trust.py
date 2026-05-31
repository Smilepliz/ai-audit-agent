"""Проверки доверия: trust signals."""

from __future__ import annotations

from audit.models import Issue, make_issue


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


def check_trust_depth(trust: dict) -> list[Issue]:
    issues: list[Issue] = []
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


def run_trust_checks(analysis: dict) -> list[Issue]:
    return check_trust_depth(analysis.get("trust", {}))
