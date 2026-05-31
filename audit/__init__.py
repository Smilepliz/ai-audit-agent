#!/usr/bin/env python3
"""SiteAuditBot — коммерческий аудит сайтов."""

from __future__ import annotations

import argparse
import sys

from audit.config import AuditConfig
from audit.utils import normalize_url, save_reports
from audit.fetcher import fetch_page, check_robots_txt, check_sitemap
from audit.quality import assess_input_quality
from audit.analyze import analyze_html
from audit.reporter import build_report

VERSION = "0.5"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=f"Коммерческий аудит сайта (v{VERSION}): главная, Markdown-отчёт."
    )
    parser.add_argument("url", help="URL сайта, например https://example.com")
    parser.add_argument(
        "--config",
        help="Путь к YAML/JSON конфигу (опционально)",
        default=None,
    )
    args = parser.parse_args()

    config = AuditConfig()
    if args.config:
        config.load_from_file(args.config)

    try:
        url = normalize_url(args.url)
    except ValueError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1

    print(f"Аудит: {url}")
    fetch = fetch_page(url, config)
    quality = assess_input_quality(fetch, config)

    robots = check_robots_txt(url, config)
    sitemap = check_sitemap(url, robots, config)

    analysis = None
    if fetch.get("ok") and fetch.get("html") and quality.get("suitable"):
        analysis = analyze_html(fetch["html"], fetch["final_url"], config)

    report = build_report(url, fetch, analysis, quality, robots=robots, sitemap=sitemap)

    archive_path, latest_path = save_reports(url, report)
    print(f"Отчёт: {latest_path}")
    print(f"Архив: {archive_path}")
    return 0 if fetch["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
