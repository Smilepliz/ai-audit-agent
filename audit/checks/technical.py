"""Технические проверки: schema.org, alt-атрибуты."""

from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

from audit.models import Issue


def check_schema_org(soup: BeautifulSoup) -> dict:
    """Проверяет структурированные данные: JSON-LD + Microdata (itemscope/itemtype).

    Ищет типы: Product, Organization, BreadcrumbList.
    """
    result: dict = {
        "has_json_ld": False,
        "has_microdata": False,
        "source": None,
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
        short_type = itemtype.rstrip("/").rsplit("/", 1)[-1]
        if short_type in ("Product", "Organization", "BreadcrumbList"):
            microdata_types_found.append(short_type)
            if short_type == "Product":
                result["product"] = True
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


def run_technical_checks(analysis: dict) -> list[Issue]:
    """Технические проверки — пока информационные, без Issue."""
    return []
