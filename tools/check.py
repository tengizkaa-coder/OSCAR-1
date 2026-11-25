#!/usr/bin/env python3
"""Статические проверки собранного сайта: ссылки, картинки, canonical, robots, schema.org.

Запуск: python3 tools/check.py
Возвращает код 1, если найдены проблемы.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import site_config as CFG  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SKIP_PARTS = {".git", "tools"}
OLD_DOMAINS = ("alcohub-msk", "alkomoskva", "alcohub")
TEST_ALLOWED = {"404.html", "test.html"}

problems: list[str] = []


def report(path: Path, message: str) -> None:
    problems.append(f"{path.relative_to(ROOT).as_posix()}: {message}")


def pages() -> list[Path]:
    return sorted(p for p in ROOT.rglob("*.html") if not SKIP_PARTS & set(p.relative_to(ROOT).parts))


def check_page(path: Path) -> None:
    rel = path.relative_to(ROOT).as_posix()
    markup = path.read_text(encoding="utf-8")
    is_test = rel.startswith("test/")
    is_utility = rel in TEST_ALLOWED

    robots = re.search(r'<meta name="robots" content="([^"]+)"', markup)
    if not robots:
        report(path, "нет meta robots")
    elif is_test and "noindex" not in robots.group(1):
        report(path, "тестовая страница должна быть noindex")
    elif not is_test and not is_utility and "noindex" in robots.group(1):
        report(path, "рабочая страница закрыта от индексации")

    canonicals = re.findall(r'<link rel="canonical" href="([^"]+)"', markup)
    if is_test:
        if canonicals:
            report(path, "у тестовой страницы не должно быть canonical")
    elif not is_utility:
        expected = CFG.DOMAIN + "/" + rel.rsplit("index.html", 1)[0]
        if canonicals != [expected]:
            report(path, f"canonical {canonicals} вместо {expected}")

    title = re.search(r"<title>(.*?)</title>", markup, re.S)
    description = re.search(r'<meta name="description" content="([^"]*)"', markup)
    if not title or not title.group(1).strip():
        report(path, "нет title")
    if not is_utility:
        if not description:
            report(path, "нет description")
        elif not 60 <= len(description.group(1)) <= 200:
            report(path, f"длина description {len(description.group(1))} вне 60–200")
    if len(re.findall(r"<h1[ >]", markup)) != 1 and not is_utility:
        report(path, "должен быть ровно один h1")

    for bad in OLD_DOMAINS:
        if bad in markup:
            report(path, f"остался старый домен/путь: {bad}")
    if "site-previews" in markup:
        report(path, "осталась зависимость site-previews")

    for match in re.finditer(r'(?:href|src)="([^"]+)"', markup):
        url = match.group(1)
        if url.startswith(("tel:", "https://", "http://", "#", "mailto:", "data:", "//")):
            continue
        target = (path.parent / url.split("#")[0].split("?")[0]).resolve()
        if target.is_dir():
            target = target / "index.html"
        if not target.exists():
            report(path, f"битая ссылка: {url}")
        elif target.suffix == ".png" and target.stat().st_size < 1000:
            report(path, f"подозрительно маленькая картинка: {url}")

    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', markup, re.S):
        try:
            data = json.loads(block)
        except json.JSONDecodeError as exc:
            report(path, f"невалидный JSON-LD: {exc}")
            continue
        if data.get("@type") == "Product":
            if "price" in json.dumps(data.get("offers", {})):
                report(path, "в Offer не должно быть цены")
            for image in data.get("image", []):
                if not image.startswith(CFG.DOMAIN + "/"):
                    report(path, f"image в JSON-LD не абсолютный: {image}")
        if data.get("@type") == "Store" and CFG.STORE_ADDRESS is None and "address" in data:
            report(path, "адрес в Store, хотя он не подтверждён")

    phone_ok = CFG.PHONE_HREF in markup
    if not is_utility and not phone_ok:
        report(path, "нет ссылки на телефон")


def check_sitemap() -> None:
    sitemap = ROOT / "sitemap.xml"
    if not sitemap.exists():
        problems.append("sitemap.xml отсутствует")
        return
    text = sitemap.read_text(encoding="utf-8")
    urls = re.findall(r"<loc>([^<]+)</loc>", text)
    if "/test/" in text or "test.html" in text:
        problems.append("sitemap.xml содержит тестовые страницы")
    if len(urls) != len(set(urls)):
        problems.append("sitemap.xml содержит дубликаты")
    for url in urls:
        if not url.startswith(CFG.DOMAIN + "/"):
            problems.append(f"sitemap.xml: чужой домен {url}")
            continue
        path = url[len(CFG.DOMAIN) + 1:]
        if not (ROOT / path / "index.html").exists():
            problems.append(f"sitemap.xml: нет файла для {url}")
    if len(urls) != 56:
        problems.append(f"sitemap.xml: ожидалось 56 URL, найдено {len(urls)}")


def check_robots() -> None:
    robots = ROOT / "robots.txt"
    if not robots.exists():
        problems.append("robots.txt отсутствует")
        return
    text = robots.read_text(encoding="utf-8")
    if "Disallow: /test/" not in text:
        problems.append("robots.txt не закрывает /test/")
    if f"Sitemap: {CFG.DOMAIN}/sitemap.xml" not in text:
        problems.append("robots.txt без корректного Sitemap")


def check_cname() -> None:
    cname = ROOT / "CNAME"
    host = CFG.DOMAIN.split("://", 1)[-1]
    if not cname.exists():
        problems.append("CNAME отсутствует")
    elif cname.read_text(encoding="utf-8").strip() != host:
        problems.append("CNAME не совпадает с доменом")


def main() -> int:
    all_pages = pages()
    for path in all_pages:
        check_page(path)
    check_sitemap()
    check_robots()
    check_cname()

    working = [p for p in all_pages if not p.relative_to(ROOT).as_posix().startswith("test/")]
    test = [p for p in all_pages if p.relative_to(ROOT).as_posix().startswith("test/")]
    print(f"Страниц: {len(all_pages)} (рабочих {len(working)}, тестовых {len(test)})")
    if problems:
        print(f"Проблем: {len(problems)}")
        for item in problems[:60]:
            print(" -", item)
        return 1
    print("Проблем не найдено")
    return 0


if __name__ == "__main__":
    sys.exit(main())
