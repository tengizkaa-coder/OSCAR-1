#!/usr/bin/env python3
"""Сборка сайта «АЛКО НОЧЬ» с нуля.

Из одного описания собираются два дерева страниц:

  • рабочее  — /            (index,follow, ограничения доступа, canonical на домен)
  • тестовое — /test/       (noindex,nofollow, открыто всем, полностью самодостаточно)

Все внутренние ссылки строятся через Ctx, а не переписываются регулярками:

  Ctx.page('catalog/whisky/')  → ссылка на страницу того же дерева
  Ctx.asset('img/jameson.png') → ссылка на общий файл (img/, assets/, logo.svg)

Поэтому страницы рабочего дерева никогда не ведут в /test/, а тестовые страницы не
выходят за пределы /test/ (кроме общих картинок и стилей).

Каталог, фильтры, карточки товаров и подборки рендерятся статически в HTML —
JavaScript только фильтрует уже готовую разметку.

Запуск:
  python3 tools/build.py
  python3 tools/build.py --domain https://new-domain.ru
"""
from __future__ import annotations

import argparse
import datetime
import html
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import site_config as CFG  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PRODUCTS: list[list[str]] = json.loads((ROOT / "tools" / "data" / "products.json").read_text(encoding="utf-8"))
GENERATED = ["index.html", "test.html", "404.html", "sitemap.xml", "robots.txt", "CNAME",
             "catalog", "delivery", "faq", "test"]
CAT_SLUGS = list(CFG.CATEGORIES)
LABELS = {slug: label for slug, (label, _) in CFG.CATEGORIES.items()}
# Порядок карточек на главной: те же три бутылки, что на обложке для соцсетей.
HERO_SLUGS = ["jameson", "chianti", "asti"]


# --------------------------------------------------------------------------- helpers
def E(value) -> str:
    return html.escape(str(value), quote=True)


def slug(item) -> str:
    return Path(item[3]).stem


def product_path(item) -> str:
    return f"catalog/product/{slug(item)}/"


def absolute(path: str) -> str:
    return f"{CFG.DOMAIN}/{path}"


def items_of(category: str) -> list[list[str]]:
    return [item for item in PRODUCTS if item[0] == category]


def index_of(item) -> int:
    return PRODUCTS.index(item)


class Ctx:
    """Контекст страницы: путь внутри своего дерева и само дерево."""

    def __init__(self, path: str = "", tree: str = ""):
        self.path = path            # '' для главной, 'catalog/whisky/' и т. п.
        self.tree = tree            # '' — рабочее дерево, 'test/' — тестовое
        self.depth = len([part for part in path.split("/") if part])

    @property
    def is_test(self) -> bool:
        return bool(self.tree)

    def page(self, target: str = "") -> str:
        """Ссылка на страницу того же дерева (target — путь от корня дерева)."""
        if not target:
            return "./" if self.depth == 0 else "../" * self.depth
        return "../" * self.depth + target

    def asset(self, target: str) -> str:
        """Ссылка на общий файл в корне сайта (assets/, img/, logo.svg, favicon.ico)."""
        return "../" * (self.depth + (1 if self.tree else 0)) + target

    def out_dir(self) -> Path:
        base = ROOT / self.tree if self.tree else ROOT
        return base / self.path if self.path else base


# --------------------------------------------------------------------------- schema
def ld_website() -> dict:
    return {"@context": "https://schema.org", "@type": "WebSite", "@id": absolute("#website"),
            "name": CFG.BRAND, "url": absolute(""), "inLanguage": "ru-RU",
            "publisher": {"@id": absolute("#store")}}


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
                {"@type": "OfferCatalog", "name": label,
                 "url": absolute(f"catalog/{cat}/"),
                 "numberOfItems": len(items_of(cat))}
                for cat, label in LABELS.items()
            ],
        },
    }
    if CFG.STORE_ADDRESS:
        data["address"] = {"@type": "PostalAddress", **CFG.STORE_ADDRESS}
    return data


def ld_breadcrumbs(items) -> dict:
    """items: [(название, путь в дереве или None для текущей страницы)]"""
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": position, "name": name,
             **({"item": absolute(path)} if path else {})}
            for position, (name, path) in enumerate(items, start=1)
        ],
    }


def ld_item_list(name: str, items) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": name,
        "numberOfItems": len(items),
        "itemListElement": [
            {"@type": "ListItem", "position": position, "name": item[1],
             "url": absolute(product_path(item))}
            for position, item in enumerate(items, start=1)
        ],
    }


def ld_product(item) -> dict:
    category, name, volume, image = item
    return {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": name,
        "url": absolute(product_path(item)),
        "image": [absolute(image)],
        "description": f"{name}, {volume}: в наличии. Цену и условия доставки уточняйте по телефону.",
        "category": LABELS[category],
        "additionalProperty": [{"@type": "PropertyValue", "name": "Объём", "value": volume}],
        "offers": {
            "@type": "Offer",
            "url": absolute(product_path(item)),
            "availability": "https://schema.org/InStock",
            "seller": {"@id": absolute("#store")},
        },
    }


def ld_faq() -> dict:
    return {"@context": "https://schema.org", "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": question,
                            "acceptedAnswer": {"@type": "Answer", "text": answer}}
                           for question, answer in CFG.FAQ]}


def ld_collection(name: str, description: str, path: str) -> dict:
    return {"@context": "https://schema.org", "@type": "CollectionPage", "name": name,
            "description": description, "url": absolute(path),
            "isPartOf": {"@id": absolute("#website")}, "inLanguage": "ru-RU"}


# --------------------------------------------------------------------------- общие блоки
def header(ctx: Ctx, current: str = "") -> str:
    def item(label: str, path: str) -> str:
        active = ' aria-current="page"' if current == path else ""
        return f'<a href="{ctx.page(path)}"{active}>{label}</a>'

    nav = "".join([item("Главная", ""), item("Каталог", "catalog/"), item("Доставка", "delivery/"),
                   item("Вопросы", "faq/"), f'<a href="{CFG.TELEGRAM_URL}">Telegram-бот</a>'])
    return (f'<header class="header expanded-header">'
            f'<a class="brand" href="{ctx.page("")}"><img src="{ctx.asset("logo.svg")}" alt="">'
            f'<span>{E(CFG.BRAND)}<small>{E(CFG.TAGLINE)}</small></span></a>'
            f'<nav class="navigation" aria-label="Навигация">{nav}</nav>'
            f'<a class="header-phone" href="{CFG.PHONE_HREF}">{E(CFG.PHONE_HUMAN)} <span>↗</span></a>'
            '<button class="basket-open" type="button" aria-haspopup="dialog">Корзина '
            '<span class="basket-count">0</span></button></header>')


def footer(ctx: Ctx) -> str:
    return (f'<footer class="expanded-footer"><div><strong>{E(CFG.BRAND)}</strong>'
            f'<p>{E(CFG.TAGLINE)}</p><p><a href="{ctx.page("catalog/")}">Каталог напитков ↗</a> · '
            f'<a href="{ctx.page("delivery/")}">Доставка и округа ↗</a></p></div>'
            f'<div><a href="{CFG.PHONE_HREF}">{E(CFG.PHONE_HUMAN)}</a>'
            f'<p><a href="{CFG.TELEGRAM_URL}">Telegram-бот</a></p>'
            f'<p>{E(CFG.DISCLAIMER)} · {E(CFG.AGE)}</p></div></footer>')


def basket_ui() -> str:
    return ('<button class="basket-float" type="button" hidden>Корзина →</button>'
            '<dialog class="basket-dialog" aria-labelledby="basket-title"><div class="basket-head">'
            '<h2 id="basket-title">Корзина</h2>'
            '<button class="basket-close" type="button" aria-label="Закрыть корзину">✕</button></div>'
            '<p class="basket-note">Корзина — это список на вашем устройстве. Она не отправляет заказ '
            'автоматически и ничего не оплачивает: позвоните и назовите позиции оператору.</p>'
            '<div class="basket-items" aria-live="polite"></div>'
            '<p class="basket-empty basket-status">Корзина пока пуста</p>'
            f'<a class="primary basket-checkout" href="{CFG.PHONE_HREF}" hidden>Оформить — позвонить ↗</a>'
            '</dialog>')


def breadcrumbs(ctx: Ctx, items) -> str:
    parts = []
    for name, path in items[:-1]:
        parts.append(f'<a href="{ctx.page(path)}">{E(name)}</a><span> / </span>')
    parts.append(f"<span>{E(items[-1][0])}</span>")
    return f'<nav class="breadcrumbs" aria-label="Навигационная цепочка">{"".join(parts)}</nav>'


def intro(title: str, description: str) -> str:
    return (f'<div class="expanded-intro"><span class="eyebrow">{E(CFG.BRAND)} / МОСКВА</span>'
            f"<h1>{E(title)}</h1><p>{E(description)}</p></div>")


def search_box() -> str:
    return ('<label class="expanded-search"><span class="eyebrow">Поиск по каталогу</span>'
            '<input id="expanded-search" type="search" placeholder="Название или категория" '
            'aria-label="Поиск по каталогу"></label>'
            '<p class="search-empty basket-status" hidden>Ничего не найдено. Попробуйте другой запрос.</p>')


def category_grid(ctx: Ctx, current: str = "", *, counts: bool = False) -> str:
    links = []
    for cat, label in LABELS.items():
        active = ' aria-current="page"' if current == cat else ""
        suffix = f" · {len(items_of(cat))}" if counts else ""
        links.append(f'<a class="category-link" href="{ctx.page(f"catalog/{cat}/")}"{active}>'
                     f'{E(label)}{suffix} <span>↗</span></a>')
    return '<div class="category-grid">' + "".join(links) + "</div>"


def district_grid(ctx: Ctx, current: str = "") -> str:
    links = []
    for district, (label, _, short) in CFG.DISTRICTS.items():
        active = ' aria-current="page"' if current == district else ""
        links.append(f'<a class="category-link" href="{ctx.page(f"delivery/{district}/")}"{active}>'
                     f'{E(short)} · {E(label)} <span>↗</span></a>')
    return '<div class="category-grid">' + "".join(links) + "</div>"


def product_card(ctx: Ctx, item, position: int, *, with_cart: bool = True, numbered: bool = True) -> str:
    category, name, volume, image = item
    label = LABELS[category]
    href = ctx.page(product_path(item))
    terms = E(f"{name} {label} {volume}".lower())
    number = f'<span class="product-number">{position:02d}</span>' if numbered else ""
    cart = (f'<button class="add-basket" data-product="{index_of(item)}" type="button" '
            f'aria-label="Добавить {E(name)} в корзину">В корзину</button>') if with_cart else ""
    return (
        f'<article class="product{" expanded-product" if with_cart else ""}" '
        f'data-category="{E(category)}" data-search="{terms}">'
        f'<div class="product-image">{number}<a href="{href}">'
        f'<img src="{ctx.asset(image)}" alt="{E(name)} — {E(label)}, {E(volume)}" '
        f'loading="lazy" decoding="async"></a></div>'
        f'<div class="product-info"><span class="product-cat">{E(label)}</span>'
        f'<h3><a class="expanded-product-title" href="{href}">{E(name)}</a></h3>'
        f"<p>{E(volume)}</p><p>В наличии · цену уточняйте по телефону</p>{cart}"
        f'<a href="{CFG.PHONE_HREF}" aria-label="Заказать {E(name)} по телефону">Заказать <span>↗</span></a>'
        "</div></article>"
    )


def product_cards(ctx: Ctx, items, *, with_cart: bool = True, numbered: bool = True) -> str:
    return "".join(product_card(ctx, item, position, with_cart=with_cart, numbered=numbered)
                   for position, item in enumerate(items, start=1))


# --------------------------------------------------------------------------- шапка документа
def analytics() -> str:
    """Счётчики Метрики/GA4: только рабочие страницы и только разрешённые посетители."""
    blocks = []
    if CFG.YANDEX_METRIKA_ID:
        counter = str(CFG.YANDEX_METRIKA_ID).strip()
        blocks.append(
            "<script>(function(){if(document.documentElement.hasAttribute('data-blocked'))return;"
            "(function(m,e,t,r,i,k,a){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};"
            "m[i].l=1*new Date();k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,"
            "a.parentNode.insertBefore(k,a)})(window,document,'script','https://mc.yandex.ru/metrika/tag.js','ym');"
            f"ym({E(counter)},'init',{{clickmap:true,trackLinks:true,accurateTrackBounce:true}});}})();</script>"
            f'<noscript><div><img src="https://mc.yandex.ru/watch/{E(counter)}" '
            'style="position:absolute;left:-9999px" alt=""></div></noscript>')
    if CFG.GA4_ID:
        gid = E(str(CFG.GA4_ID).strip())
        blocks.append(
            "<script>(function(){if(document.documentElement.hasAttribute('data-blocked'))return;"
            "var s=document.createElement('script');s.async=true;"
            f"s.src='https://www.googletagmanager.com/gtag/js?id={gid}';document.head.appendChild(s);"
            "window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)}window.gtag=gtag;"
            f"gtag('js',new Date());gtag('config','{gid}');}})();</script>")
    return "".join(blocks)


def render(ctx: Ctx, *, title: str, description: str, body: str, robots: str = "index,follow",
           schema=(), og_type: str = "website", og_image: str | None = None,
           scripts=("expanded",), test_bar: bool = True) -> Path:
    prefix_depth = ctx.depth + (1 if ctx.tree else 0)
    asset_prefix = "../" * prefix_depth
    page_prefix = ctx.page("")
    canonical = "" if ctx.is_test else f'<link rel="canonical" href="{E(absolute(ctx.path))}">'
    og_url = "" if ctx.is_test else f'<meta property="og:url" content="{E(absolute(ctx.path))}">'
    json_ld = "".join(
        '<script type="application/ld+json">'
        + json.dumps(block, ensure_ascii=False).replace("<", "\\u003c")
        + "</script>" for block in schema)
    scripts_html = f'<script src="{asset_prefix}assets/js/products.js" defer></script>'
    if "app" in scripts:
        scripts_html += f'<script src="{asset_prefix}assets/js/app.js" defer></script>'
    if "expanded" in scripts:
        scripts_html += f'<script src="{asset_prefix}assets/js/expanded.js" defer></script>'
    analytics_html = "" if ctx.is_test else analytics()

    if ctx.is_test and test_bar:
        # data-tree="production" помечает осознанные ссылки из теста в рабочий сайт:
        # проверка tools/check.py пропускает их и не считает выходом за пределы дерева.
        body = (f'<div class="test-bar">Тестовый просмотр · страницы закрыты от индексации · '
                f'<a href="{asset_prefix}" data-tree="production">рабочий сайт</a> · '
                f'<a href="{ctx.page("")}">главная теста</a> · '
                f'<a href="{ctx.page("catalog/")}">каталог теста</a></div>' + body)

    site_id = "alkonoch-test" if ctx.is_test else "alkonoch"
    document = f'''<!doctype html>
<html lang="ru" data-theme="1" data-site="{site_id}" data-image-base="{asset_prefix}" data-page-base="{page_prefix}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><meta name="robots" content="{robots if not ctx.is_test else "noindex,nofollow"}"><title>{E(title)}</title><meta name="description" content="{E(description)}">{canonical}<meta name="theme-color" content="#151717"><meta property="og:type" content="{og_type}"><meta property="og:site_name" content="{E(CFG.BRAND)}"><meta property="og:locale" content="ru_RU"><meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(description)}">{og_url}<meta property="og:image" content="{E(og_image or absolute("assets/og/cover.png"))}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta name="twitter:card" content="summary_large_image"><link rel="icon" href="{asset_prefix}favicon.ico" sizes="any"><link rel="icon" href="{asset_prefix}logo.svg" type="image/svg+xml"><link rel="icon" type="image/png" sizes="192x192" href="{asset_prefix}assets/icons/icon-192.png"><link rel="apple-touch-icon" sizes="180x180" href="{asset_prefix}assets/icons/apple-touch-icon.png"><link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link rel="stylesheet" href="{asset_prefix}assets/css/gate.css"><script src="{asset_prefix}assets/js/gate.js"></script><link rel="stylesheet" href="{asset_prefix}assets/css/styles.css"><link rel="stylesheet" href="{asset_prefix}assets/css/expanded.css?v=5">{json_ld}{analytics_html}{scripts_html}</head>
<body>{body}
</body></html>'''
    target = ctx.out_dir()
    target.mkdir(parents=True, exist_ok=True)
    file = target / "index.html"
    file.write_text(document, encoding="utf-8")
    return file


# --------------------------------------------------------------------------- главная
LOGO_SVG = ('<svg viewBox="0 0 48 48" aria-hidden="true"><circle cx="24" cy="24" r="22" fill="none" '
            'stroke="currentColor" stroke-width="1"/><path d="M12 9v30M9 18h6M9 22h6M6 31h18M18 8v28" '
            'fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" '
            'stroke-linejoin="round"/></svg>')


def home_body(ctx: Ctx) -> str:
    by_slug = {slug(item): item for item in PRODUCTS}
    hero_items = [by_slug[name] for name in HERO_SLUGS if name in by_slug]
    hero_parts = []
    for position, item in enumerate(hero_items):
        extra = ' fetchpriority="high"' if position == 1 else ' loading="lazy"'
        hero_parts.append(
            f'<img class="hero-bottle bottle-{position}" src="{ctx.asset(item[3])}" '
            f'alt="{E(item[1])}"{extra}>')
    hero = "".join(hero_parts)
    filters = ('<button type="button" data-category="all" aria-pressed="true">Все напитки</button>'
               + "".join(f'<button type="button" data-category="{cat}" aria-pressed="false">'
                         f'{E(label)}</button>' for cat, label in LABELS.items()))
    ordered = [item for cat in CAT_SLUGS for item in items_of(cat)]
    cards = product_cards(ctx, ordered, with_cart=False)
    return f'''<header class="header"><a href="#top" class="brand" aria-label="{E(CFG.BRAND)} — в начало">{LOGO_SVG}<span>{E(CFG.BRAND)}<small>{E(CFG.TAGLINE)}</small></span></a><nav class="navigation" aria-label="Навигация"><a href="{ctx.page("catalog/")}">Каталог</a><a href="{ctx.page("delivery/")}">Доставка</a><a href="{ctx.page("faq/")}">Вопросы</a></nav><a class="header-phone" href="{CFG.PHONE_HREF}">{E(CFG.PHONE_HUMAN)} <span>↗</span></a></header>
<main id="top"><section class="hero"><div class="hero-copy"><div class="eyebrow"><span class="live-dot"></span>01 / МОСКВА</div><h1>Доставка алкоголя<br>для вашего вечера</h1><p>Выберите любимые напитки — оформим заказ по телефону.</p><div class="hero-actions"><a class="primary" href="{CFG.PHONE_HREF}">Заказать по телефону <span>↗</span></a><a class="secondary" href="#catalog">Смотреть каталог <span>↓</span></a></div><div class="hero-note"><span>●</span> Круглосуточно <i></i> Москва</div></div><div class="hero-visual"><div class="visual-ring"></div><span class="visual-label">{E(CFG.BRAND)} / 24</span><div class="bottle-stage" id="hero-bottles">{hero}</div><div class="visual-stamp">ВЫБИРАЙТЕ<br>С НАСТРОЕНИЕМ <span>✳</span></div></div><div class="hero-bottom"><span>НАПИТКИ ДЛЯ ВАШЕГО ВЕЧЕРА</span><span>ЛИСТАЙТЕ ВНИЗ ↓</span></div></section>
<section class="catalog section" id="catalog"><div class="section-heading"><div><span class="eyebrow">АССОРТИМЕНТ / {len(PRODUCTS)} ПОЗИЦИЙ</span><h2>Найдите <em>своё</em></h2></div><p>От проверенной классики до любимых вкусов. Наличие и цены уточняйте по телефону.</p></div><div class="catalog-tools"><div class="filters" id="filters" role="group" aria-label="Категории товаров">{filters}</div><label class="search"><span aria-hidden="true">⌕</span><input id="search" type="search" placeholder="Поиск напитка" aria-label="Поиск напитка"></label></div><div class="products" id="products" aria-live="polite">{cards}</div><p id="empty" hidden>Ничего не найдено. Попробуйте другой запрос.</p><p class="basket-status">{len(PRODUCTS)} позиций. В карточках есть ссылки на раздел, страницу товара и звонок.</p></section>
<section class="how section" id="how"><div><span class="eyebrow">ПРОСТО И ПОНЯТНО</span><h2>Как сделать <em>заказ</em></h2><a class="primary" href="{CFG.PHONE_HREF}">Позвонить нам <span>↗</span></a></div><ol class="steps"><li><span>01</span><div><h3>Выберите</h3><p>Найдите напитки в каталоге.</p></div></li><li><span>02</span><div><h3>Позвоните</h3><p>Уточните цену и условия доставки, оформите заказ.</p></div></li><li><span>03</span><div><h3>Ожидайте</h3><p>Детали доставки согласуем по телефону.</p></div></li></ol></section>
<section class="section homepage-more"><div class="section-heading"><div><span class="eyebrow">РАЗДЕЛЫ / КАТАЛОГ</span><h2>Выбирайте <em>по категориям</em></h2></div><p>Выберите напитки для своего вечера: сравните позиции по категориям и уточните детали звонком.</p></div>{category_grid(ctx, counts=True)}<div class="homepage-extra-nav"><a href="{ctx.page("catalog/")}">Весь каталог и корзина ↗</a><a href="{ctx.page("delivery/")}">Доставка и заказ ↗</a><a href="{ctx.page("faq/")}">Вопросы и ответы ↗</a><a href="{CFG.TELEGRAM_URL}">Telegram-бот ↗</a></div></section></main>
<footer class="footer"><div class="footer-top"><div class="footer-brand">{LOGO_SVG}<strong>{E(CFG.BRAND)}</strong></div><div><span>НА СВЯЗИ 24/7</span><a href="{CFG.PHONE_HREF}">{E(CFG.PHONE_HUMAN)}</a></div></div><div class="footer-bottom"><p>{E(CFG.DISCLAIMER)}</p><span>{E(CFG.AGE)} · {E(CFG.BRAND)}</span></div></footer><a class="mobile-call" href="{CFG.PHONE_HREF}">Заказать по телефону ↗</a>'''


def build_home(ctx: Ctx) -> None:
    description = ("Круглосуточная доставка алкоголя по Москве: 30 позиций — виски, водка, коньяк, ликёры, "
                   "вино и пиво. Наличие и цену уточняйте по телефону +7 (495) 095-95-99.")
    render(ctx, title="Доставка алкоголя по Москве 24/7 — АЛКО НОЧЬ", description=description,
           body=home_body(ctx), scripts=("app",), schema=[ld_website(), ld_store()])


# --------------------------------------------------------------------------- каталог
def catalog_body(ctx: Ctx) -> str:
    sections = []
    for cat, label in LABELS.items():
        items = items_of(cat)
        sections.append(
            f'<section class="catalog-section" id="{cat}"><h2>{E(label)}'
            f'<span class="basket-status"> · {len(items)} поз. · <a href="{ctx.page(f"catalog/{cat}/")}">'
            f'открыть раздел</a></span></h2><div class="products">{product_cards(ctx, items)}</div></section>')
    extra = ('<section class="expanded-copy"><h2>Перед звонком</h2><div>'
             "<p>Можно выбрать несколько товаров и собрать список в корзине. При оформлении откроется "
             "звонок; список остаётся на вашем устройстве и автоматически не передаётся.</p>"
             "<p>Назовите оператору выбранные позиции и уточните стоимость и детали доставки.</p>"
             "<p>Объёмы в карточках взяты из каталога и могут требовать уточнения: наличие, объём и цену "
             "подтвердит оператор.</p></div></section>")
    return category_grid(ctx, counts=True) + search_box() + "".join(sections) + extra


def build_catalog(ctx: Ctx) -> None:
    title = "Каталог напитков — АЛКО НОЧЬ"
    description = ("30 позиций: виски, водка, джин, коньяк, ликёры, вермут, вино и пиво. Фотографии и объёмы, "
                   "поиск по названию, 10 разделов. Наличие и цену уточняйте по телефону.")
    body = (header(ctx, "catalog/")
            + '<main class="expanded-main">'
            + breadcrumbs(ctx, [("Главная", ""), ("Каталог", None)])
            + intro("Каталог напитков", description)
            + catalog_body(ctx) + "</main>" + footer(ctx) + basket_ui())
    render(ctx, title=title, description=description, body=body,
           schema=[ld_collection("Каталог напитков", description, "catalog/"),
                   ld_breadcrumbs([("Главная", ""), ("Каталог", None)]),
                   ld_item_list("Каталог напитков", PRODUCTS)])


def build_category(ctx: Ctx, cat: str) -> None:
    label, text = CFG.CATEGORIES[cat]
    items = items_of(cat)
    siblings = [(LABELS[other], f"catalog/{other}/") for other in CAT_SLUGS if other != cat]
    body = (header(ctx, "catalog/")
            + '<main class="expanded-main">'
            + breadcrumbs(ctx, [("Главная", ""), ("Каталог", "catalog/"), (label, None)])
            + intro(label, text)
            + category_grid(ctx, cat, counts=True) + search_box()
            + f'<section class="catalog-section" id="{cat}"><h2>{E(label)}'
              f'<span class="basket-status"> · {len(items)} поз.</span></h2>'
              f'<div class="products">{product_cards(ctx, items)}</div></section>'
            + '<section class="expanded-copy"><h2>Как выбрать</h2><div>'
            + f"<p>{E(text)}</p>"
              "<p>Добавьте интересующие напитки в корзину или позвоните сразу. Цены и условия доставки "
              "уточняются у оператора.</p>"
              f'<p><a class="primary" href="{ctx.page("catalog/")}">Весь каталог ↗</a></p></div></section>'
            + '<section class="catalog-section"><h2>Другие разделы</h2>'
              '<div class="homepage-extra-nav">'
            + "".join(f'<a href="{ctx.page(path)}">{E(name)} ↗</a>' for name, path in siblings)
            + '</div></section></main>' + footer(ctx) + basket_ui())
    render(ctx, title=f"{label} — АЛКО НОЧЬ", description=text, body=body,
           schema=[ld_collection(label, text, f"catalog/{cat}/"),
                   ld_breadcrumbs([("Главная", ""), ("Каталог", "catalog/"), (label, None)]),
                   ld_item_list(label, items)])


# --------------------------------------------------------------------------- товар
def build_product(ctx: Ctx, item) -> None:
    category, name, volume, image = item
    label = LABELS[category]
    index = index_of(item)
    others = [other for other in items_of(category) if other is not item]
    description = f"{name}, {volume}: в наличии. Цену и условия доставки уточняйте по телефону."
    others_html = ""
    if others:
        links = "".join(
            f'<a href="{ctx.page(product_path(other))}">{E(other[1])} · {E(other[2])} <span>↗</span></a>'
            for other in others)
        others_html = (f'<section class="catalog-section"><h2>Ещё в разделе «{E(label)}»</h2>'
                       f'<div class="homepage-extra-nav">{links}</div></section>')
    body = (header(ctx, "catalog/")
            + '<main class="expanded-main">'
            + breadcrumbs(ctx, [("Главная", ""), ("Каталог", "catalog/"), (label, f"catalog/{category}/"), (name, None)])
            + intro(name, description)
            + '<div class="preview-product-detail"><div class="preview-product-photo">'
            + f'<img src="{ctx.asset(image)}" alt="{E(name)}, {E(volume)}" fetchpriority="high"></div><div>'
            + f'<p>Раздел: <a href="{ctx.page(f"catalog/{category}/")}">{E(label)}</a></p>'
            + f'<p>Объём: {E(volume)} <span class="basket-status">(по данным каталога, уточните при заказе)</span></p>'
            + "<p>В наличии · цену уточняйте по телефону.</p>"
            + f'<button class="add-basket" data-product="{index}" type="button" '
              f'aria-label="Добавить {E(name)} в корзину">В корзину</button>'
            + f'<p><a class="primary" href="{CFG.PHONE_HREF}">Заказать по телефону ↗</a></p>'
            + f'<p><a href="{CFG.TELEGRAM_URL}">Открыть Telegram-бот ↗</a></p>'
            + '<p class="basket-status">Корзина — список на вашем устройстве. Она не отправляет заказ '
              'автоматически.</p></div></div>'
            + others_html
            + f'<p class="basket-status"><a href="{ctx.page("catalog/")}">← Весь каталог</a> · '
              f'<a href="{ctx.page("delivery/")}">Доставка и округа</a> · '
              f'<a href="{ctx.page("faq/")}">Вопросы</a></p>'
            + "</main>" + footer(ctx) + basket_ui())
    render(ctx, title=f"{name}, {volume} — АЛКО НОЧЬ", description=description, body=body,
           og_type="product", og_image=absolute(image),
           schema=[ld_product(item),
                   ld_breadcrumbs([("Главная", ""), ("Каталог", "catalog/"),
                                   (label, f"catalog/{category}/"), (name, None)])])


# --------------------------------------------------------------------------- доставка
def build_delivery(ctx: Ctx) -> None:
    description = ("Выберите напитки в каталоге и обсудите все детали заказа по телефону: наличие, объём, "
                   "стоимость и условия доставки в вашем округе Москвы.")
    body = (header(ctx, "delivery/")
            + '<main class="expanded-main">'
            + breadcrumbs(ctx, [("Главная", ""), ("Доставка и заказ", None)])
            + intro("Доставка и заказ", description)
            + '<section class="expanded-copy"><h2>Три простых шага</h2><div><ol>'
              "<li>Выберите интересующие напитки в каталоге и при желании добавьте их в корзину.</li>"
              "<li>Позвоните нам и назовите выбранные позиции. Состав корзины не передаётся автоматически.</li>"
              "<li>Обсудите стоимость, адрес и удобные условия доставки с оператором.</li></ol>"
              "<p>Точные сроки и стоимость доставки зависят от деталей заказа. Уточните их до оформления "
              "по телефону.</p>"
              f'<p><a class="primary" href="{CFG.PHONE_HREF}">Позвонить нам ↗</a></p>'
              f'<p><a href="{CFG.TELEGRAM_URL}">Открыть Telegram-бот ↗</a></p></div></section>'
              '<section class="catalog-section"><h2>Округа Москвы</h2>'
              "<p>Выберите округ и уточните условия по вашему адресу.</p>" + district_grid(ctx)
            + '<div class="homepage-extra-nav">'
            + f'<a href="{ctx.page("catalog/")}">Открыть каталог ↗</a>'
            + f'<a href="{ctx.page("faq/")}">Вопросы и ответы ↗</a></div></section></main>'
            + footer(ctx) + basket_ui())
    render(ctx, title="Доставка и заказ — АЛКО НОЧЬ", description=description, body=body,
           schema=[ld_breadcrumbs([("Главная", ""), ("Доставка и заказ", None)])])


def build_district(ctx: Ctx, district: str) -> None:
    label, where, short = CFG.DISTRICTS[district]
    title = f"Доставка алкоголя: {label} Москвы"
    description = (f"Доставка в {where} Москвы. Выберите напитки и уточните цену, сроки и стоимость "
                   "доставки по телефону.")
    body = (header(ctx, "delivery/")
            + '<main class="expanded-main">'
            + breadcrumbs(ctx, [("Главная", ""), ("Доставка и заказ", "delivery/"), (title, None)])
            + intro(title, description)
            + f'<section class="expanded-copy"><h2>{E(short)} · {E(label)}</h2><div>'
            + f"<p>Выберите напитки в каталоге и подготовьте список для заказа в {E(where)} Москвы. "
              "В карточках указаны названия, фотографии и объёмы.</p>"
              "<p>Назовите адрес оператору: цену напитков, стоимость и сроки доставки уточняйте по телефону.</p>"
            + f'<p><a class="primary" href="{ctx.page("catalog/")}">Открыть каталог ↗</a></p>'
            + f'<p><a href="{CFG.PHONE_HREF}">Позвонить: {E(CFG.PHONE_HUMAN)}</a> · '
              f'<a href="{CFG.TELEGRAM_URL}">Telegram-бот ↗</a></p></div></section>'
              '<section class="catalog-section"><h2>Другие округа</h2>'
            + district_grid(ctx, district)
            + f'<div class="homepage-extra-nav"><a href="{ctx.page("delivery/")}">Доставка и заказ ↗</a>'
              f'<a href="{ctx.page("catalog/")}">Каталог напитков ↗</a></div></section></main>'
            + footer(ctx) + basket_ui())
    render(ctx, title=f"{title} — АЛКО НОЧЬ", description=description, body=body,
           schema=[ld_breadcrumbs([("Главная", ""), ("Доставка и заказ", "delivery/"), (title, None)])])


# --------------------------------------------------------------------------- вопросы
def build_faq(ctx: Ctx) -> None:
    description = "Собрали ответы о выборе напитков, корзине и оформлении заказа."
    details = "".join(f"<details><summary>{E(question)}</summary><p>{E(answer)}</p></details>"
                      for question, answer in CFG.FAQ)
    body = (header(ctx, "faq/")
            + '<main class="expanded-main">'
            + breadcrumbs(ctx, [("Главная", ""), ("Вопросы и ответы", None)])
            + intro("Вопросы и ответы", description)
            + f'<div class="faq-list">{details}</div>'
              '<div class="homepage-extra-nav">'
            + f'<a href="{ctx.page("catalog/")}">Открыть каталог ↗</a>'
            + f'<a href="{ctx.page("delivery/")}">Доставка и округа ↗</a>'
            + f'<a href="{CFG.PHONE_HREF}">Позвонить нам ↗</a>'
            + f'<a href="{CFG.TELEGRAM_URL}">Telegram-бот ↗</a></div></main>'
            + footer(ctx) + basket_ui())
    render(ctx, title="Вопросы и ответы — АЛКО НОЧЬ", description=description, body=body,
           schema=[ld_faq(), ld_breadcrumbs([("Главная", ""), ("Вопросы и ответы", None)])])


# --------------------------------------------------------------------------- служебные файлы
def build_tree(tree: str) -> list[str]:
    paths = [""]
    build_home(Ctx("", tree))
    build_catalog(Ctx("catalog/", tree))
    for cat in CAT_SLUGS:
        build_category(Ctx(f"catalog/{cat}/", tree), cat)
        paths.append(f"catalog/{cat}/")
    for item in PRODUCTS:
        build_product(Ctx(product_path(item), tree), item)
        paths.append(product_path(item))
    build_delivery(Ctx("delivery/", tree))
    paths.append("delivery/")
    for district in CFG.DISTRICTS:
        build_district(Ctx(f"delivery/{district}/", tree), district)
        paths.append(f"delivery/{district}/")
    build_faq(Ctx("faq/", tree))
    paths.append("faq/")
    paths.insert(1, "catalog/")
    return paths


def write_products_js() -> None:
    payload = json.dumps(PRODUCTS, ensure_ascii=False, separators=(",", ":"))
    (ROOT / "assets" / "js" / "products.js").write_text(
        "/* Данные каталога: [категория, название, объём, фото].\n"
        "   Объёмы взяты из исходного каталога и по фотографиям не проверялись.\n"
        "   Цен нет намеренно. */\n"
        f"window.SITE_PRODUCTS = {payload};\n", encoding="utf-8")


def write_sitemap(paths: list[str]) -> None:
    today = datetime.date.today().isoformat()
    rows = []
    for path in paths:
        priority = "1.0" if path == "" else ("0.8" if path.count("/") <= 2 else "0.6")
        rows.append(f"  <url><loc>{E(absolute(path))}</loc><lastmod>{today}</lastmod>"
                    f"<priority>{priority}</priority></url>")
    (ROOT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(rows) + "\n</urlset>\n", encoding="utf-8")


def write_robots() -> None:
    (ROOT / "robots.txt").write_text(
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /test/\n"
        "Disallow: /test.html\n"
        "\n"
        f"Sitemap: {absolute('sitemap.xml')}\n", encoding="utf-8")


def write_cname() -> None:
    (ROOT / "CNAME").write_text(CFG.DOMAIN.split("://", 1)[-1].rstrip("/") + "\n", encoding="utf-8")


def write_test_redirect() -> None:
    (ROOT / "test.html").write_text(f'''<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Тестовый просмотр — {E(CFG.BRAND)}</title><meta http-equiv="refresh" content="0; url=./test/"><link rel="stylesheet" href="assets/css/gate.css"><script src="assets/js/gate.js"></script><link rel="stylesheet" href="assets/css/styles.css"><link rel="stylesheet" href="assets/css/expanded.css"></head>
<body><div class="test-bar">Тестовый просмотр · страницы закрыты от индексации</div><main class="expanded-main"><div class="expanded-intro"><span class="eyebrow">{E(CFG.BRAND)} / ТЕСТ</span><h1>Тестовый просмотр</h1><p><a class="primary" href="./test/">Открыть тестовый просмотр ↗</a></p><p><a href="./test/catalog/">Каталог теста ↗</a> · <a href="./">Рабочий сайт ↗</a></p><p class="basket-status">Страницы теста закрыты от индексации.</p></div></main></body></html>
''', encoding="utf-8")


def write_404() -> None:
    (ROOT / "404.html").write_text(f'''<!doctype html>
<html lang="ru" data-theme="1"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><meta name="robots" content="noindex,follow"><title>Страница не найдена — {E(CFG.BRAND)}</title><link rel="icon" href="favicon.ico" sizes="any"><link rel="stylesheet" href="assets/css/styles.css"><link rel="stylesheet" href="assets/css/expanded.css"></head>
<body><main class="expanded-main"><nav class="breadcrumbs" aria-label="Навигационная цепочка"><a href="./">Главная</a><span> / </span><span>Страница не найдена</span></nav><div class="expanded-intro"><span class="eyebrow">{E(CFG.BRAND)} / 404</span><h1>Страница не найдена</h1><p>Возможно, ссылка устарела. Откройте каталог или позвоните — подскажем по наличию и цене.</p></div><div class="homepage-extra-nav"><a href="./catalog/">Каталог напитков ↗</a><a href="./delivery/">Доставка ↗</a><a href="./faq/">Вопросы ↗</a><a href="{CFG.PHONE_HREF}">{E(CFG.PHONE_HUMAN)}</a><a href="{CFG.TELEGRAM_URL}">Telegram-бот ↗</a></div></main></body></html>
''', encoding="utf-8")


# --------------------------------------------------------------------------- main
def main() -> None:
    parser = argparse.ArgumentParser(description="Сборка сайта «АЛКО НОЧЬ»")
    parser.add_argument("--domain", help="домен, например https://example.ru")
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
    production_paths = build_tree("")
    build_tree("test/")
    write_sitemap(production_paths)
    write_robots()
    write_cname()
    write_test_redirect()
    write_404()
    print(f"Готово: {len(production_paths)} рабочих страниц + столько же в /test/, домен {CFG.DOMAIN}")


if __name__ == "__main__":
    main()
