#!/usr/bin/env python3
"""Сборка статического сайта «АЛКО НОЧЬ» для домена из tools/site_config.py.

Что создаётся:
  index.html, catalog/, delivery/, faq/            — рабочие страницы (index, follow)
  test/                                           — полный миррор с noindex (открыт всем)
  sitemap.xml, robots.txt, CNAME, 404.html, test.html

Запуск:
  python3 tools/build.py                 # домен из tools/site_config.py
  python3 tools/build.py --domain https://example.ru
"""
from __future__ import annotations

import argparse
import datetime
import html
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import site_config as CFG  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PRODUCTS = json.loads((ROOT / "tools" / "data" / "products.json").read_text(encoding="utf-8"))
HOME_TEMPLATE = (ROOT / "tools" / "templates" / "home_body.html").read_text(encoding="utf-8")
GENERATED = ["index.html", "test.html", "404.html", "sitemap.xml", "robots.txt", "CNAME",
             "catalog", "delivery", "faq", "test"]


def E(value) -> str:
    return html.escape(str(value), quote=True)


def slug(item) -> str:
    return Path(item[3]).stem


def product_path(item) -> str:
    return f"catalog/product/{slug(item)}/"


def absolute(path: str) -> str:
    return f"{CFG.DOMAIN}/{path}"


def localize(markup: str, prefix: str) -> str:
    """Prefix every relative href/src so pages also work inside /test/ and project subpaths."""
    if not prefix:
        return markup
    pattern = re.compile(r'(?P<attr>\b(?:href|src|poster|action)=")(?!https?:|tel:|mailto:|sms:|data:|#|//)(?P<url>[^"]*)"')
    return pattern.sub(lambda m: f'{m["attr"]}{prefix}{m["url"]}"', markup)


# --------------------------------------------------------------------------- schema.org
def ld_website() -> dict:
    return {"@context": "https://schema.org", "@type": "WebSite",
            "@id": absolute("#website"), "name": CFG.BRAND, "url": absolute(""),
            "inLanguage": "ru-RU", "publisher": {"@id": absolute("#store")}}


def ld_store() -> dict:
    data = {
        "@context": "https://schema.org",
        "@type": "Store",
        "@id": absolute("#store"),
        "name": CFG.BRAND,
        "url": absolute(""),
        "image": absolute("assets/icons/icon-512.png"),
        "logo": absolute("assets/icons/icon-512.png"),
        "telephone": CFG.PHONE_E164,
        "sameAs": [CFG.TELEGRAM_URL],
        "areaServed": CFG.STORE_AREA,
        "openingHoursSpecification": [{
            "@type": "OpeningHoursSpecification",
            "dayOfWeek": CFG.STORE_HOURS["days"],
            "opens": CFG.STORE_HOURS["opens"],
            "closes": CFG.STORE_HOURS["closes"],
        }],
        "hasOfferCatalog": {
            "@type": "OfferCatalog",
            "name": "Каталог напитков",
            "itemListElement": [
                {"@type": "OfferCatalog", "name": label, "url": absolute(f"catalog/{cat}/")}
                for cat, (label, _) in CFG.CATEGORIES.items()
            ],
        },
    }
    if CFG.STORE_ADDRESS:
        data["address"] = {"@type": "PostalAddress", **CFG.STORE_ADDRESS}
    return data


def ld_breadcrumbs(items) -> dict:
    """items: [(name, path or None)] — path None means the current page."""
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i, "name": name,
             **({"item": absolute(path)} if path is not None else {})}
            for i, (name, path) in enumerate(items, start=1)
        ],
    }


def ld_item_list(name, items) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": name,
        "numberOfItems": len(items),
        "itemListElement": [
            {"@type": "ListItem", "position": i, "name": item[1], "url": absolute(product_path(item))}
            for i, item in enumerate(items, start=1)
        ],
    }


def ld_product(item) -> dict:
    category, name, volume, image = item
    label = CFG.CATEGORIES[category][0]
    return {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": name,
        "url": absolute(product_path(item)),
        "image": [absolute(image)],
        "description": f"{name}, {volume}: в наличии. Цену и условия доставки уточняйте по телефону.",
        "category": label,
        "additionalProperty": [{"@type": "PropertyValue", "name": "Объём", "value": volume}],
        "offers": {
            "@type": "Offer",
            "url": absolute(product_path(item)),
            "availability": "https://schema.org/InStock",
            "seller": {"@id": absolute("#store")},
        },
    }


def ld_faq() -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in CFG.FAQ
        ],
    }


def ld_collection(name, description, path) -> dict:
    return {"@context": "https://schema.org", "@type": "CollectionPage",
            "name": name, "description": description, "url": absolute(path),
            "isPartOf": {"@id": absolute("#website")}, "inLanguage": "ru-RU"}


# --------------------------------------------------------------------------- layout
NAV = ('<a href="index.html">Главная</a><a href="catalog/">Каталог</a>'
       '<a href="delivery/">Доставка</a><a href="faq/">Вопросы</a>'
       f'<a href="{CFG.TELEGRAM_URL}">Telegram-бот</a>')


def header() -> str:
    return (f'<header class="header expanded-header"><a class="brand" href="index.html"><img src="logo.svg" alt="">'
            f'<span>{E(CFG.BRAND)}<small>{E(CFG.TAGLINE)}</small></span></a>'
            f'<nav class="navigation" aria-label="Навигация">{NAV}</nav>'
            '<button class="basket-open" type="button" aria-haspopup="dialog">Корзина <span class="basket-count">0</span></button></header>')


def footer() -> str:
    return (f'<footer class="expanded-footer"><div><strong>{E(CFG.BRAND)}</strong><p>{E(CFG.TAGLINE)}</p></div>'
            f'<div><a href="{CFG.PHONE_HREF}">{E(CFG.PHONE_HUMAN)}</a>'
            f'<p><a href="{CFG.TELEGRAM_URL}">Telegram-бот</a></p>'
            f'<p>{E(CFG.DISCLAIMER)} · {E(CFG.AGE)}</p></div></footer>')


def basket_ui() -> str:
    return ('<button class="basket-float" type="button" hidden>Корзина →</button>'
            '<dialog class="basket-dialog" aria-labelledby="basket-title"><div class="basket-head">'
            '<h2 id="basket-title">Корзина</h2><button class="basket-close" type="button" aria-label="Закрыть корзину">✕</button></div>'
            '<p class="basket-note">Корзина — это список на вашем устройстве. Она не отправляет заказ автоматически '
            'и ничего не оплачивает: позвоните и назовите позиции оператору.</p>'
            '<div class="basket-items" aria-live="polite"></div>'
            '<p class="basket-empty basket-status">Корзина пока пуста</p>'
            f'<a class="primary basket-checkout" href="{CFG.PHONE_HREF}" hidden>Оформить — позвонить ↗</a></dialog>')


def breadcrumbs(items) -> str:
    parts = []
    for name, path in items[:-1]:
        parts.append(f'<a href="{path}">{E(name)}</a><span> / </span>')
    parts.append(f"<span>{E(items[-1][0])}</span>")
    return f'<nav class="breadcrumbs" aria-label="Навигационная цепочка">{"".join(parts)}</nav>'


def intro(title: str, description: str) -> str:
    return (f'<div class="expanded-intro"><span class="eyebrow">{E(CFG.BRAND)} / МОСКВА</span>'
            f"<h1>{E(title)}</h1><p>{E(description)}</p></div>")


def product_card(item, index) -> str:
    category, name, volume, image = item
    label = CFG.CATEGORIES[category][0]
    href = product_path(item)
    terms = f"{name} {label} {volume}".lower()
    return (
        f'<article class="product expanded-product" data-search="{E(terms)}">'
        f'<div class="product-image"><a href="{href}">'
        f'<img src="{E(image)}" alt="{E(name)} — {E(label)}, {E(volume)}" loading="lazy" decoding="async"></a></div>'
        f'<div class="product-info"><span class="product-cat">{E(label)}</span>'
        f'<h3><a class="expanded-product-title" href="{href}">{E(name)}</a></h3>'
        f"<p>{E(volume)}</p><p>В наличии · цену уточняйте по телефону</p>"
        f'<button class="add-basket" data-product="{index}" type="button" aria-label="Добавить {E(name)} в корзину">В корзину</button>'
        f'<a href="{CFG.PHONE_HREF}" aria-label="Заказать {E(name)} по телефону">Заказать <span>↗</span></a></div></article>'
    )


def category_links(current: str | None = None) -> str:
    links = []
    for cat, (label, _) in CFG.CATEGORIES.items():
        active = ' aria-current="page"' if current == cat else ""
        links.append(f'<a class="category-link" href="catalog/{cat}/"{active}>{E(label)} <span>↗</span></a>')
    return '<div class="category-grid">' + "".join(links) + "</div>"


def district_links() -> str:
    links = []
    for d, (label, _, short) in CFG.DISTRICTS.items():
        links.append(f'<a class="category-link" href="delivery/{d}/">{E(short)} · {E(label)} <span>↗</span></a>')
    return '<div class="category-grid">' + "".join(links) + "</div>"


def search_box() -> str:
    return ('<label class="expanded-search"><span class="eyebrow">Поиск по каталогу</span>'
            '<input id="expanded-search" type="search" placeholder="Название или категория" aria-label="Поиск по каталогу"></label>'
            '<p class="search-empty basket-status" hidden>Ничего не найдено. Попробуйте другой запрос.</p>')


# --------------------------------------------------------------------------- page shell
def page(path: str, *, title: str, description: str, body: str, robots: str = "index,follow",
         schema=(), test: bool = False, og_type: str = "website", og_image: str | None = None,
         scripts=("expanded",), base_override: str | None = None) -> str:
    """Write one page. `path` is relative to the site root, e.g. '' or 'catalog/whisky/'."""
    depth = len([part for part in Path(path).parts if part])
    if test:
        out_dir = ROOT / "test" / path if path else ROOT / "test"
    else:
        out_dir = ROOT / path if path else ROOT
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = "../" * (depth + (1 if test else 0))
    if base_override is not None:
        prefix = base_override

    if test:
        robots = "noindex,nofollow"
        # The test bar carries already-prefixed links, so it is added after localize().
        bar = (f'<div class="test-bar">Тестовый просмотр · страницы закрыты от индексации · '
               f'<a href="{prefix}">рабочий сайт</a> · <a href="{prefix}test/">оглавление теста</a></div>')
    else:
        bar = ""

    body = bar + localize(body, prefix)

    canonical = "" if test else f'<link rel="canonical" href="{E(absolute(path))}">'
    og_image_url = og_image or absolute("assets/og/cover.png")
    json_ld = "".join(
        '<script type="application/ld+json">'
        + json.dumps(item, ensure_ascii=False).replace("<", "\\u003c")
        + "</script>"
        for item in schema
    )
    scripts_html = f'<script src="{prefix}assets/js/products.js" defer></script>'
    if "app" in scripts:
        scripts_html += f'<script src="{prefix}assets/js/app.js" defer></script>'
    if "expanded" in scripts:
        scripts_html += f'<script src="{prefix}assets/js/expanded.js" defer></script>'

    site_id = "alkonoch-test" if test else "alkonoch"
    document = f'''<!doctype html>
<html lang="ru" data-theme="1" data-site="{site_id}" data-image-base="{prefix}" data-base="{prefix}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><meta name="robots" content="{robots}"><title>{E(title)}</title><meta name="description" content="{E(description)}">{canonical}<meta name="theme-color" content="#151717"><meta property="og:type" content="{og_type}"><meta property="og:site_name" content="{E(CFG.BRAND)}"><meta property="og:locale" content="ru_RU"><meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(description)}"><meta property="og:url" content="{E(absolute(path))}"><meta property="og:image" content="{E(og_image_url)}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta name="twitter:card" content="summary_large_image"><link rel="icon" href="{prefix}favicon.ico" sizes="any"><link rel="icon" href="{prefix}logo.svg" type="image/svg+xml"><link rel="icon" type="image/png" sizes="192x192" href="{prefix}assets/icons/icon-192.png"><link rel="apple-touch-icon" sizes="180x180" href="{prefix}assets/icons/apple-touch-icon.png"><link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link rel="stylesheet" href="{prefix}assets/css/gate.css"><script src="{prefix}assets/js/gate.js"></script><link rel="stylesheet" href="{prefix}assets/css/styles.css"><link rel="stylesheet" href="{prefix}assets/css/expanded.css?v=4">{json_ld}{scripts_html}</head>
<body>{body}
</body></html>'''
    (out_dir / "index.html").write_text(document, encoding="utf-8")
    return path


# --------------------------------------------------------------------------- pages
def home_body() -> str:
    return HOME_TEMPLATE


def catalog_body(category: str | None) -> str:
    chunks = []
    if category is None:
        chunks.append(category_links() + search_box())
        for cat, (label, _) in CFG.CATEGORIES.items():
            cards = "".join(product_card(item, i) for i, item in enumerate(PRODUCTS) if item[0] == cat)
            chunks.append(f'<section class="catalog-section" id="{cat}"><h2>{E(label)}</h2><div class="products">{cards}</div></section>')
        chunks.append('<section class="expanded-copy"><h2>Перед звонком</h2><div>'
                      "<p>Можно выбрать несколько товаров и собрать список в корзине. При оформлении откроется звонок; "
                      "список остаётся на вашем устройстве и автоматически не передаётся.</p>"
                      "<p>Назовите оператору выбранные позиции и уточните стоимость и детали доставки.</p>"
                      "<p>Объёмы в карточках взяты из каталога и могут требовать уточнения: наличие, объём и цену подтвердит оператор.</p>"
                      "</div></section>")
    else:
        label, description = CFG.CATEGORIES[category]
        chunks.append(category_links(category) + search_box())
        cards = "".join(product_card(item, i) for i, item in enumerate(PRODUCTS) if item[0] == category)
        chunks.append(f'<section class="catalog-section" id="{category}"><h2>{E(label)}</h2><div class="products">{cards}</div></section>')
        chunks.append('<section class="expanded-copy"><h2>Как выбрать</h2><div>'
                      f"<p>{E(description)}</p>"
                      "<p>Добавьте интересующие напитки в корзину или позвоните сразу. Цены и условия доставки уточняются у оператора.</p>"
                      "</div></section>")
    return "".join(chunks)


def build_catalog(test: bool) -> None:
    # /catalog/
    title = "Каталог напитков — АЛКО НОЧЬ"
    description = ("30 позиций: виски, водка, джин, коньяк, ликёры, вермут, вино и пиво. "
                   "Фотографии и объёмы, поиск по названию. Наличие и цену уточняйте по телефону.")
    page("catalog/", title=title, description=description, test=test,
         schema=[ld_collection("Каталог напитков", description, "catalog/"),
                 ld_breadcrumbs([("Главная", "index.html"), ("Каталог", None)]),
                 ld_item_list("Каталог напитков", PRODUCTS)],
         body=header() + f'<main class="expanded-main">{breadcrumbs([("Главная", "index.html"), ("Каталог", None)])}'
                         + intro("Каталог напитков", description) + catalog_body(None) + "</main>" + footer() + basket_ui())

    for cat, (label, text) in CFG.CATEGORIES.items():
        items = [item for item in PRODUCTS if item[0] == cat]
        page(f"catalog/{cat}/", title=f"{label} — АЛКО НОЧЬ", description=text, test=test,
             schema=[ld_collection(label, text, f"catalog/{cat}/"),
                     ld_breadcrumbs([("Главная", "index.html"), ("Каталог", "catalog/"), (label, None)]),
                     ld_item_list(label, items)],
             body=header() + f'<main class="expanded-main">'
                             + breadcrumbs([("Главная", "index.html"), ("Каталог", "catalog/"), (label, None)])
                             + intro(label, text) + catalog_body(cat) + "</main>" + footer() + basket_ui())


def build_products(test: bool) -> None:
    for index, item in enumerate(PRODUCTS):
        category, name, volume, image = item
        label = CFG.CATEGORIES[category][0]
        description = f"{name}, {volume}: в наличии. Цену и условия доставки уточняйте по телефону."
        body = (
            header()
            + '<main class="expanded-main">'
            + breadcrumbs([("Главная", "index.html"), ("Каталог", "catalog/"), (label, f"catalog/{category}/"), (name, None)])
            + intro(name, description)
            + '<div class="preview-product-detail"><div class="preview-product-photo">'
            + f'<img src="{E(image)}" alt="{E(name)}, {E(volume)}" fetchpriority="high"></div><div>'
            + f'<p>Категория: <a href="catalog/{category}/">{E(label)}</a></p>'
            + f"<p>Объём: {E(volume)} <span class=\"basket-status\">(по данным каталога, уточните при заказе)</span></p>"
            + "<p>В наличии · цену уточняйте по телефону.</p>"
            + f'<button class="add-basket" data-product="{index}" type="button" aria-label="Добавить {E(name)} в корзину">В корзину</button>'
            + f'<p><a class="primary" href="{CFG.PHONE_HREF}">Заказать по телефону ↗</a></p>'
            + f'<p><a href="{CFG.TELEGRAM_URL}">Открыть Telegram-бот ↗</a></p>'
            + '<p class="basket-status">Корзина — список на вашем устройстве. Она не отправляет заказ автоматически.</p>'
            + "</div></div></main>"
            + footer() + basket_ui()
        )
        page(product_path(item), title=f"{name}, {volume} — АЛКО НОЧЬ", description=description,
             test=test, og_type="product", og_image=absolute(image),
             schema=[ld_product(item),
                     ld_breadcrumbs([("Главная", "index.html"), ("Каталог", "catalog/"),
                                     (label, f"catalog/{category}/"), (name, None)])],
             body=body)


def build_delivery(test: bool) -> None:
    description = ("Выберите напитки в каталоге и обсудите все детали заказа по телефону: наличие, объём, стоимость и условия доставки в вашем округе Москвы.")
    body = (
        header() + '<main class="expanded-main">'
        + breadcrumbs([("Главная", "index.html"), ("Доставка и заказ", None)])
        + intro("Доставка и заказ", description)
        + '<section class="expanded-copy"><h2>Три простых шага</h2><div><ol>'
          "<li>Выберите интересующие напитки в каталоге и при желании добавьте их в корзину.</li>"
          "<li>Позвоните нам и назовите выбранные позиции. Состав корзины не передаётся автоматически.</li>"
          "<li>Обсудите стоимость, адрес и удобные условия доставки с оператором.</li></ol>"
          "<p>Точные сроки и стоимость доставки зависят от деталей заказа. Уточните их до оформления по телефону.</p>"
          f'<a class="primary" href="{CFG.PHONE_HREF}">Позвонить нам ↗</a>'
          f'<p><a href="{CFG.TELEGRAM_URL}">Открыть Telegram-бот ↗</a></p></div></section>'
          '<section class="catalog-section"><h2>Округа Москвы</h2>'
          "<p>Выберите округ и уточните условия по вашему адресу.</p>" + district_links() + "</section></main>"
        + footer() + basket_ui()
    )
    page("delivery/", title="Доставка и заказ — АЛКО НОЧЬ", description=description, test=test,
         schema=[ld_breadcrumbs([("Главная", "index.html"), ("Доставка и заказ", None)])], body=body)

    for d, (label, where, short) in CFG.DISTRICTS.items():
        subtitle = (f"Доставка в {where} Москвы. Выберите напитки и уточните цену, сроки и стоимость доставки по телефону.")
        body = (
            header() + '<main class="expanded-main">'
            + breadcrumbs([("Главная", "index.html"), ("Доставка и заказ", "delivery/"),
                           (f"Доставка алкоголя: {label} Москвы", None)])
            + intro(f"Доставка алкоголя: {label} Москвы", subtitle)
            + f'<section class="expanded-copy"><h2>{E(short)} · {E(label)}</h2><div>'
              f"<p>Выберите напитки в каталоге и подготовьте список для заказа в {E(where)} Москвы. "
              "В карточках указаны названия, фотографии и объёмы.</p>"
              "<p>Назовите адрес оператору: цену напитков, стоимость и сроки доставки уточняйте по телефону.</p>"
              f'<p><a class="primary" href="catalog/">Открыть каталог ↗</a></p>'
              f'<p><a href="{CFG.TELEGRAM_URL}">Открыть Telegram-бот ↗</a></p></div></section>'
              '<section class="catalog-section"><h2>Другие округа</h2>' + district_links() + "</section></main>"
            + footer() + basket_ui()
        )
        page(f"delivery/{d}/", title=f"Доставка алкоголя: {label} Москвы — АЛКО НОЧЬ",
             description=subtitle, test=test,
             schema=[ld_breadcrumbs([("Главная", "index.html"), ("Доставка и заказ", "delivery/"),
                                     (f"Доставка алкоголя: {label} Москвы", None)])],
             body=body)


def build_faq(test: bool) -> None:
    description = "Собрали ответы о выборе напитков, корзине и оформлении заказа."
    details = "".join(f"<details><summary>{E(q)}</summary><p>{E(a)}</p></details>" for q, a in CFG.FAQ)
    body = (
        header() + '<main class="expanded-main">'
        + breadcrumbs([("Главная", "index.html"), ("Вопросы и ответы", None)])
        + intro("Вопросы и ответы", description)
        + f'<div class="faq-list">{details}</div>'
          '<div class="homepage-extra-nav">'
          '<a href="catalog/">Открыть каталог ↗</a>'
          f'<a href="{CFG.PHONE_HREF}">Позвонить нам ↗</a></div></main>'
        + footer() + basket_ui()
    )
    page("faq/", title="Вопросы и ответы — АЛКО НОЧЬ", description=description, test=test,
         schema=[ld_faq(), ld_breadcrumbs([("Главная", "index.html"), ("Вопросы и ответы", None)])],
         body=body)


def build_home(test: bool) -> None:
    description = ("Круглосуточная доставка алкоголя по Москве: 30 позиций — виски, водка, коньяк, ликёры, "
                   "вино и пиво. Наличие и цену уточняйте по телефону +7 (495) 095-95-99.")
    page("", title="Доставка алкоголя по Москве 24/7 — АЛКО НОЧЬ", description=description, test=test,
         scripts=("app",), schema=[ld_website(), ld_store()], body=home_body())


def write_products_js() -> None:
    payload = json.dumps(PRODUCTS, ensure_ascii=False, separators=(",", ":"))
    (ROOT / "assets" / "js" / "products.js").write_text(
        "/* Product data: [category, name, volume, image]. Volumes come from the source catalogue\n"
        "   and were not verified against the photos. Prices are intentionally absent. */\n"
        f"window.SITE_PRODUCTS = {payload};\n", encoding="utf-8")


def write_sitemap(paths) -> None:
    today = datetime.date.today().isoformat()
    urls = []
    for path in paths:
        loc = absolute(path)
        priority = "1.0" if path == "" else ("0.8" if path.count("/") <= 2 else "0.6")
        urls.append(f"  <url><loc>{E(loc)}</loc><lastmod>{today}</lastmod><priority>{priority}</priority></url>")
    content = ('<?xml version="1.0" encoding="UTF-8"?>\n'
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
               + "\n".join(urls) + "\n</urlset>\n")
    (ROOT / "sitemap.xml").write_text(content, encoding="utf-8")


def write_robots() -> None:
    content = ("User-agent: *\n"
               "Allow: /\n"
               "Disallow: /test/\n"
               "Disallow: /test.html\n"
               "\n"
               f"Sitemap: {absolute('sitemap.xml')}\n")
    (ROOT / "robots.txt").write_text(content, encoding="utf-8")


def write_cname() -> None:
    host = CFG.DOMAIN.split("://", 1)[-1].rstrip("/")
    (ROOT / "CNAME").write_text(host + "\n", encoding="utf-8")


def write_test_redirect() -> None:
    content = f'''<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Тестовый просмотр — {E(CFG.BRAND)}</title><meta http-equiv="refresh" content="0; url=./test/"><link rel="stylesheet" href="assets/css/gate.css"><script src="assets/js/gate.js"></script><link rel="stylesheet" href="assets/css/styles.css"></head>
<body><main class="expanded-main"><div class="expanded-intro"><span class="eyebrow">{E(CFG.BRAND)} / ТЕСТ</span><h1>Тестовый просмотр</h1><p><a class="primary" href="./test/">Открыть тестовый просмотр ↗</a></p><p class="basket-status">Страницы теста закрыты от индексации.</p></div></main></body></html>
'''
    (ROOT / "test.html").write_text(content, encoding="utf-8")


def write_404() -> None:
    content = f'''<!doctype html>
<html lang="ru" data-theme="1"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><meta name="robots" content="noindex,follow"><title>Страница не найдена — {E(CFG.BRAND)}</title><link rel="icon" href="favicon.ico" sizes="any"><link rel="stylesheet" href="assets/css/styles.css"><link rel="stylesheet" href="assets/css/expanded.css"></head>
<body><main class="expanded-main"><div class="expanded-intro"><span class="eyebrow">{E(CFG.BRAND)} / 404</span><h1>Страница не найдена</h1><p>Возможно, ссылка устарела. Откройте каталог или позвоните нам — подскажем по наличию и цене.</p><p><a class="primary" href="./">На главную ↗</a></p><p><a href="./catalog/">Каталог напитков ↗</a></p><p><a href="{CFG.PHONE_HREF}">{E(CFG.PHONE_HUMAN)}</a></p></div></main></body></html>
'''
    (ROOT / "404.html").write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Сборка сайта «АЛКО НОЧЬ»")
    parser.add_argument("--domain", help="домен, например https://example.ru (переопределяет site_config.py)")
    args = parser.parse_args()
    if args.domain:
        CFG.DOMAIN = args.domain.rstrip("/")
    if not CFG.DOMAIN.startswith("https://"):
        print("ВНИМАНИЕ: домен без https:// — canonical будет неполным", file=sys.stderr)

    for name in GENERATED:
        target = ROOT / name
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()

    write_products_js()

    index_paths = [""]
    build_home(False)
    build_catalog(False)
    build_products(False)
    build_delivery(False)
    build_faq(False)
    index_paths += ["catalog/"] + [f"catalog/{c}/" for c in CFG.CATEGORIES]
    index_paths += [product_path(p) for p in PRODUCTS]
    index_paths += ["delivery/"] + [f"delivery/{d}/" for d in CFG.DISTRICTS]
    index_paths += ["faq/"]

    build_home(True)
    build_catalog(True)
    build_products(True)
    build_delivery(True)
    build_faq(True)

    write_sitemap(index_paths)
    write_robots()
    write_cname()
    write_test_redirect()
    write_404()
    print(f"Готово: {len(index_paths)} рабочих страниц + столько же в /test/, домен {CFG.DOMAIN}")


if __name__ == "__main__":
    main()
