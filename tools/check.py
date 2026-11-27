#!/usr/bin/env python3
"""Проверка собранного сайта: обход ссылок по двум деревьям, SEO-теги, schema.org, sitemap.

Главное, что проверяется:
  • из рабочего дерева нельзя попасть в /test/, а из /test/ — в рабочее дерево;
  • все ссылки и картинки существуют (ни одного 404);
  • на каждой странице правильные title/description/H1/canonical/robots;
  • каталог, разделы и товары непустые и связаны между собой;
  • sitemap.xml содержит только рабочие 56 адресов, robots.txt закрывает /test/.

Запуск: python3 tools/check.py   (код возврата 1, если есть проблемы)
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import site_config as CFG  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PRODUCTS = json.loads((ROOT / "tools" / "data" / "products.json").read_text(encoding="utf-8"))
UTILITY = {"404.html", "test.html"}
EXPECTED_PAGES = 1 + 1 + len(CFG.CATEGORIES) + len(PRODUCTS) + 1 + len(CFG.DISTRICTS) + 1
problems: list[str] = []


def fail(path: Path | str, message: str) -> None:
    problems.append(f"{path}: {message}")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def local_links(markup: str):
    """(тег целиком, ссылка как в HTML, ссылка без якоря) для всех локальных href/src."""
    for tag in re.finditer(r'<(?:a|link|img|script|source|iframe)\b[^>]*>', markup):
        markup_tag = tag.group(0)
        for attribute in ("href", "src"):
            match = re.search(rf'{attribute}="([^"]+)"', markup_tag)
            if not match:
                continue
            raw = match.group(1)
            url = raw.split("#")[0].split("?")[0]
            if not url or url.startswith(("https://", "http://", "tel:", "mailto:", "data:", "//")):
                continue
            yield markup_tag, raw, url


def main() -> int:
    trees = {"": set(), "test/": set()}

    for tree in trees:
        start = (ROOT / tree / "index.html").resolve()
        queue, seen = [start], set()
        while queue:
            page = queue.pop()
            if page in seen:
                continue
            seen.add(page)
            trees[tree].add(page)
            markup = page.read_text(encoding="utf-8")
            is_test = bool(tree)
            page_rel = rel(page)
            page_dir_rel = page_rel.rsplit("index.html", 1)[0]

            for tag_markup, raw, url in local_links(markup):
                target = (page.parent / urllib.parse.unquote(url)).resolve()
                if url.endswith("/"):
                    target = target / "index.html"
                if not target.exists():
                    fail(page_rel, f"битая ссылка: {raw}")
                    continue
                target_rel = rel(target)
                is_page = url.endswith("/") or url.endswith(".html")
                if is_page:
                    marked = 'data-tree="production"' in tag_markup
                    if is_test and not target_rel.startswith("test/"):
                        if not marked:
                            fail(page_rel, f"ссылка уводит из /test/: {raw} → /{target_rel}")
                        continue  # осознанная ссылка на рабочий сайт, дальше не идём
                    if not is_test and target_rel.startswith("test/"):
                        fail(page_rel, f"рабочая страница ссылается на тест: {raw}")
                    if target.suffix == ".html" and target.name == "index.html":
                        queue.append(target)
                else:
                    if target_rel.endswith(".png") and target.stat().st_size < 1000:
                        fail(page_rel, f"подозрительно маленькая картинка: {raw}")

            # --- SEO-разметка страницы
            robots = re.search(r'<meta name="robots" content="([^"]+)"', markup)
            title = re.search(r"<title>(.*?)</title>", markup, re.S)
            description = re.search(r'<meta name="description" content="([^"]*)"', markup)
            canonical = re.findall(r'<link rel="canonical" href="([^"]+)"', markup)
            if not robots:
                fail(page_rel, "нет meta robots")
            elif is_test and "noindex" not in robots.group(1):
                fail(page_rel, "тестовая страница должна быть noindex")
            elif not is_test and "noindex" in robots.group(1):
                fail(page_rel, "рабочая страница закрыта от индексации")
            if not title or len(title.group(1)) < 15:
                fail(page_rel, "плохой title")
            if not description or not 60 <= len(description.group(1)) <= 200:
                length = len(description.group(1)) if description else 0
                fail(page_rel, f"description длиной {length} (нужно 60–200)")
            if len(re.findall(r"<h1[ >]", markup)) != 1:
                fail(page_rel, "должен быть ровно один h1")
            if is_test:
                if canonical:
                    fail(page_rel, "у тестовой страницы не должно быть canonical")
            else:
                expected = CFG.DOMAIN + "/" + page_dir_rel
                if canonical != [expected]:
                    fail(page_rel, f"canonical {canonical} вместо {expected}")
            for bad in ("alcohub-msk", "alkomoskva", "site-previews"):
                if bad in markup:
                    fail(page_rel, f"остался старый путь/домен: {bad}")
            if CFG.PHONE_HREF not in markup:
                fail(page_rel, "нет ссылки на телефон")
            if CFG.TELEGRAM_URL not in markup:
                fail(page_rel, "нет ссылки на Telegram-бота")
            if "₽" in markup or "руб." in markup:
                fail(page_rel, "на странице появилась цена — на сайте цен нет")
            if "gate.js" in markup or "data-blocked" in markup:
                fail(page_rel, "остался скрипт ограничения доступа")
            if "не публику" in markup.lower():
                fail(page_rel, "осталась формулировка «цены не публикуем»")
            if "noindex" in markup and not is_test:
                fail(page_rel, "noindex на рабочей странице")
            for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', markup, re.S):
                try:
                    data = json.loads(block)
                except json.JSONDecodeError as error:
                    fail(page_rel, f"невалидный JSON-LD: {error}")
                    continue
                if data.get("@type") == "Product":
                    if "price" in json.dumps(data.get("offers", {})):
                        fail(page_rel, "в Offer не должно быть цены")
                    for image in data.get("image", []):
                        if not image.startswith(CFG.DOMAIN + "/"):
                            fail(page_rel, f"image в JSON-LD не абсолютный: {image}")

    # --- содержимое каталога
    for tree in ("", "test/"):
        home = ((ROOT / tree / "index.html")).read_text(encoding="utf-8")
        cards = home.count('article class="product"')
        if cards < 20:
            fail(f"{tree or '/'}index.html", f"карточек на главной {cards}, мало (нужно от 20)")
        if len(re.findall(r'data-shelf(?![\w-])', home)) != 2:
            fail(f"{tree or '/'}index.html", "на главной должно быть две полки с товарами")
        if home.count('class="category-link"') != len(CFG.CATEGORIES):
            fail(f"{tree or '/'}index.html", "в полке категорий не все разделы")
        if home.count('class="souvenir-card"') != 1:
            fail(f"{tree or '/'}index.html", "нет блока про сувениры")
        if home.count('class="feature"') != 3:
            fail(f"{tree or '/'}index.html", "блок преимуществ должен состоять из трёх карточек")
        if home.count('class="hero-bottle') != 3:
            fail(f"{tree or '/'}index.html", "в герое должно быть 3 статичные бутылки")
        catalog = ((ROOT / tree / "catalog/index.html")).read_text(encoding="utf-8")
        if catalog.count('article class="product') != len(PRODUCTS):
            fail(f"{tree}catalog/index.html", "в каталоге не все товары")
        for cat in CFG.CATEGORIES:
            category = ((ROOT / tree / f"catalog/{cat}/index.html")).read_text(encoding="utf-8")
            expected = len([item for item in PRODUCTS if item[0] == cat])
            got = category.count('article class="product')
            if got != expected:
                fail(f"{tree}catalog/{cat}/index.html", f"карточек {got}, ожидалось {expected}")
            if category.count('class="seo-links"') == 0:
                fail(f"{tree}catalog/{cat}/index.html", "нет ссылок на другие разделы")

    if len(trees[""]) != EXPECTED_PAGES:
        fail("/", f"рабочих страниц {len(trees[''])} вместо {EXPECTED_PAGES}")
    if len(trees["test/"]) != EXPECTED_PAGES:
        fail("/test/", f"тестовых страниц {len(trees['test/'])} вместо {EXPECTED_PAGES}")

    # --- sitemap / robots / CNAME
    sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
    urls = re.findall(r"<loc>([^<]+)</loc>", sitemap)
    if len(urls) != EXPECTED_PAGES:
        fail("sitemap.xml", f"{len(urls)} URL вместо {EXPECTED_PAGES}")
    if len(set(urls)) != len(urls):
        fail("sitemap.xml", "есть дубликаты")
    if "/test/" in sitemap or "test.html" in sitemap:
        fail("sitemap.xml", "тестовые страницы в карте сайта")
    for url in urls:
        if not url.startswith(CFG.DOMAIN + "/"):
            fail("sitemap.xml", f"чужой домен: {url}")
            continue
        path = url[len(CFG.DOMAIN) + 1:]
        if not (ROOT / path / "index.html").exists():
            fail("sitemap.xml", f"нет файла для {url}")

    robots_txt = (ROOT / "robots.txt").read_text(encoding="utf-8")
    if "Disallow: /test/" not in robots_txt:
        fail("robots.txt", "не закрывает /test/")
    if f"Sitemap: {CFG.DOMAIN}/sitemap.xml" not in robots_txt:
        fail("robots.txt", "нет корректного Sitemap")

    host = CFG.DOMAIN.split("://", 1)[-1]
    if (ROOT / "CNAME").read_text(encoding="utf-8").strip() != host:
        fail("CNAME", f"должен содержать {host}")

    if problems:
        print(f"Проблем: {len(problems)}")
        for item in problems[:60]:
            print(" -", item)
        return 1
    print(f"Ок: {len(trees[''])} рабочих страниц, {len(trees['test/'])} тестовых, {len(urls)} URL в sitemap")
    print("Ссылки не выходят за пределы своих деревьев, битых путей нет")
    return 0


if __name__ == "__main__":
    sys.exit(main())
