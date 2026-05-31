"""HTTP-запросы, robots.txt, sitemap.xml."""

from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urlparse

import requests

from audit.config import AuditConfig
from audit.models import FetchResult


def fetch_page(url: str, config: AuditConfig | None = None) -> FetchResult:
    cfg = config or AuditConfig()
    started = datetime.now()
    try:
        response = requests.get(
            url,
            timeout=cfg.timeout,
            allow_redirects=True,
            headers={"User-Agent": cfg.user_agent},
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


def check_robots_txt(base_url: str, config: AuditConfig | None = None) -> dict:
    """Проверяет /robots.txt: наличие, Disallow, Sitemap (регистронезависимо)."""
    cfg = config or AuditConfig()
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
            timeout=cfg.timeout,
            allow_redirects=True,
            headers={"User-Agent": cfg.user_agent},
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


def check_sitemap(base_url: str, robots: dict, config: AuditConfig | None = None) -> dict:
    """Проверяет sitemap.xml: из robots.txt или стандартного пути."""
    cfg = config or AuditConfig()
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
                timeout=cfg.timeout,
                allow_redirects=True,
                headers={"User-Agent": cfg.user_agent},
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
