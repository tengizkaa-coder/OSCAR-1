#!/usr/bin/env python3
"""Сборка сайта «АЛКО НОЧЬ».

Из одного описания собираются два дерева страниц:

  • рабочее  — /            (index,follow, canonical на домен, открыто всем)
  • тестовое — /test/       (noindex,nofollow, полностью самодостаточно)

Все внутренние ссылки строятся через Ctx, а не переписываются регулярками:

  Ctx.page('catalog/whisky/')  → ссылка на страницу того же дерева
  Ctx.asset('img/jameson.png') → ссылка на общий файл (img/, assets/, logo.svg)

Поэтому страницы рабочего дерева никогда не ведут в /test/, а тестовые страницы не
выходят за пределы /test/ (кроме общих картинок и стилей).

Каталог, полки, карточки и страницы товаров отрисованы статически в HTML:
JavaScript отвечает только за корзину-список, прокрутку полок и поиск по готовым
карточкам. Цены на сайте не публикуются — их называет оператор по телефону.

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
# Три бутылки в герое главной: те же, что на обложке для соцсетей.
HERO_SLUGS = ["jameson", "chianti", "asti"]
# Полки главной: крепкое и лёгкое — весь каталог без повторов.
STRONG = ["whisky", "vodka", "gin", "cognac", "liqueur", "vermouth"]
SHELF_LIGHT = ["white-wine", "red-wine", "sparkling", "beer"]
PRICE_TEXT = "Цену уточняйте"
PRICE_NOTE = f"по телефону {CFG.PHONE_HUMAN}"


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


def interleave(categories: list[str], limit: int) -> list[list[str]]:
    """Берёт товары по кругу из категорий: полка получается разнообразной."""
    pools = [items_of(category)[:] for category in categories]
    result: list[list[str]] = []
    while len(result) < limit and any(pools):
        for pool in pools:
            if pool and len(result) < limit:
                result.append(pool.pop(0))
    return result


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


# --------------------------------------------------------------------------- иконки
ICON_PHONE = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
              'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 '
              '19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 '
              '1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 '
              '2.8.7a2 2 0 0 1 1.7 2z"/></svg>')
ICON_CART = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
             'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="width:18px;height:18px">'
             '<circle cx="9" cy="20" r="1.4"/><circle cx="18" cy="20" r="1.4"/>'
             '<path d="M2 3h2.2l2.4 11.2a2 2 0 0 0 2 1.6h8.6a2 2 0 0 0 2-1.5L21 7H6"/></svg>')
ICON_SEARCH = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
               'stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>')
ICON_TRUCK = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
              'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M1 3h13v12H1z"/>'
              '<path d="M14 8h4l3 3.2V15h-7z"/><circle cx="5.5" cy="18.5" r="2.2"/><circle cx="17.5" cy="18.5" r="2.2"/></svg>')
ICON_LIST = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
             'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 6h13M8 12h13M8 18h13"/>'
             '<circle cx="3.5" cy="6" r="1.2"/><circle cx="3.5" cy="12" r="1.2"/><circle cx="3.5" cy="18" r="1.2"/></svg>')
ICON_LOGO = ('<svg viewBox="0 0 48 48" aria-hidden="true"><circle cx="24" cy="24" r="22" fill="none" '
             'stroke="currentColor" stroke-width="1"/><path d="M12 9v30M9 18h6M9 22h6M6 31h18M18 8v28" '
             'fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>')


# --------------------------------------------------------------------------- schema.org
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
def topbar(ctx: Ctx) -> str:
    return (
        '<div class="topbar"><div class="wrap">'
        '<div class="topbar-left">'
        f'<span class="topbar-note"><span class="dot"></span>Москва · доставка 24/7</span>'
        f'<a href="{ctx.page("delivery/")}">Доставка и оплата</a>'
        '</div>'
        '<div class="topbar-right">'
        f'<a href="{CFG.TELEGRAM_URL}">Telegram-бот</a>'
        f'<a href="{CFG.PHONE_HREF}">{E(CFG.PHONE_HUMAN)}</a>'
        f'<span class="topbar-age">{E(CFG.AGE)}</span>'
        '</div></div></div>'
    )


def header(ctx: Ctx, current: str = "") -> str:
    def item(label: str, path: str) -> str:
        active = ' aria-current="page"' if current == path else ""
        return f'<a href="{ctx.page(path)}"{active}>{label}</a>'

    nav = "".join([item("Главная", ""), item("Каталог", "catalog/"), item("Доставка", "delivery/"),
                   item("Вопросы", "faq/")])
    mobile_nav = "".join([item("Главная", ""), item("Каталог напитков", "catalog/"),
                          item("Доставка и оплата", "delivery/"), item("Вопросы и ответы", "faq/"),
                          f'<a href="{CFG.TELEGRAM_URL}">Telegram-бот</a>'])
    return (
        f'<header class="site-header"><div class="wrap">'
        f'<a class="brand" href="{ctx.page("")}">'
        f'<img src="{ctx.asset("logo.svg")}" alt="{E(CFG.BRAND)}" width="38" height="38">'
        f'<span class="brand-text"><span class="brand-name">{E(CFG.BRAND)}</span>'
        f'<span class="brand-tag">{E(CFG.TAGLINE)}</span></span></a>'
        f'<nav class="main-nav" aria-label="Основная навигация">{nav}</nav>'
        f'<div class="header-actions">'
        f'<a class="header-phone" href="{CFG.PHONE_HREF}"><span>Заказ по телефону</span>'
        f'<strong>{E(CFG.PHONE_HUMAN)}</strong></a>'
        f'<button class="cart-button basket-open" type="button" aria-haspopup="dialog" '
        f'aria-label="Корзина, позиций: 0">{ICON_CART}<span>Корзина</span>'
        f'<span class="basket-count">0</span></button>'
        f'<button class="burger" type="button" aria-label="Открыть меню" aria-expanded="false" '
        f'aria-controls="mobile-nav"><span></span></button>'
        '</div></div>'
        f'<nav class="mobile-nav" id="mobile-nav" aria-label="Мобильная навигация"><div class="wrap">'
        f'{mobile_nav}</div></nav></header>'
    )


def footer(ctx: Ctx) -> str:
    catalog_links = "".join(
        f'<li><a href="{ctx.page(f"catalog/{cat}/")}">{E(label)}</a></li>' for cat, label in LABELS.items())
    districts = list(CFG.DISTRICTS.items())[:4]
    info = (f'<li><a href="{ctx.page("catalog/")}">Каталог напитков</a></li>'
            f'<li><a href="{ctx.page("delivery/")}">Доставка и оплата</a></li>'
            f'<li><a href="{ctx.page("faq/")}">Вопросы и ответы</a></li>'
            + "".join(f'<li><a href="{ctx.page(f"delivery/{key}/")}">{E(short)}</a></li>'
                      for key, (_, _, short) in districts))
    return (
        '<footer class="site-footer"><div class="wrap">'
        '<div class="footer-top">'
        '<div class="footer-brand">'
        f'<span class="brand-text"><span class="brand-name">{E(CFG.BRAND)}</span>'
        f'<span class="brand-tag">{E(CFG.TAGLINE)}</span></span>'
        f'<p>{E(CFG.DISCLAIMER)}.</p>'
        f'<p class="age">{E(CFG.AGE)}</p></div>'
        f'<div class="footer-col"><h2>Каталог</h2><ul>{catalog_links}</ul></div>'
        f'<div class="footer-col"><h2>Покупателям</h2><ul>{info}</ul></div>'
        f'<div class="footer-col"><h2>Контакты</h2><ul>'
        f'<li><a class="footer-phone" href="{CFG.PHONE_HREF}">{E(CFG.PHONE_HUMAN)}</a></li>'
        f'<li><a href="{CFG.TELEGRAM_URL}">Telegram-бот {E(CFG.TELEGRAM_HANDLE)}</a></li>'
        '<li>Заказ и консультация — по телефону и в Telegram</li></ul></div>'
        '</div>'
        '<div class="footer-bottom">'
        f'<span>{E(CFG.DISCLAIMER)}</span>'
        f'<span class="age">{E(CFG.AGE)} · {E(CFG.BRAND)}</span>'
        '</div></div></footer>'
    )


def mobile_bar(ctx: Ctx) -> str:
    return (
        '<div class="mobile-bar">'
        f'<a class="btn btn-primary" href="{CFG.PHONE_HREF}">Позвонить</a>'
        f'<button class="cart-button basket-open" type="button" aria-haspopup="dialog" '
        f'aria-label="Корзина, позиций: 0">{ICON_CART}<span class="basket-count">0</span></button>'
        '</div>'
    )


def cart_drawer() -> str:
    return (
        '<dialog class="cart-drawer" aria-labelledby="cart-title">'
        '<div class="cart-head"><h2 id="cart-title">Корзина</h2>'
        '<button class="cart-close basket-close" type="button" aria-label="Закрыть корзину">✕</button></div>'
        '<div class="cart-body"><div class="basket-items"></div>'
        '<p class="basket-empty">Корзина пуста. Добавьте напитки из каталога.</p></div>'
        '<div class="cart-foot">'
        '<p class="basket-note">Корзина — это список на вашем устройстве. Заказ не отправляется '
        'автоматически и ничего не оплачивается: позвоните и назовите позиции оператору.</p>'
        f'<a class="btn btn-primary btn-block basket-checkout" href="{CFG.PHONE_HREF}" hidden>'
        f'Оформить — позвонить</a>'
        f'<a class="basket-tg" href="{CFG.TELEGRAM_URL}">Отправить список в Telegram-бот</a>'
        '</div></dialog>'
    )


def breadcrumbs(ctx: Ctx, items) -> str:
    parts = []
    for name, path in items[:-1]:
        parts.append(f'<a href="{ctx.page(path)}">{E(name)}</a><span> / </span>')
    parts.append(f"<span>{E(items[-1][0])}</span>")
    return f'<nav class="breadcrumbs" aria-label="Навигационная цепочка">{"".join(parts)}</nav>'


def page_head(ctx: Ctx, title: str, lead: str, items=None, meta: str = "") -> str:
    crumbs = breadcrumbs(ctx, items) if items else ""
    return (f'<div class="page-head">{crumbs}<h1>{E(title)}</h1>'
            f'<p class="page-lead">{E(lead)}</p>{meta}</div>')


# --------------------------------------------------------------------------- карточки
def product_card(ctx: Ctx, item, *, heading: int = 3) -> str:
    category, name, volume, image = item
    label = LABELS[category]
    href = ctx.page(product_path(item))
    terms = E(f"{name} {label} {volume}".lower())
    h = f"h{heading}"
    return (
        f'<article class="product" data-category="{E(category)}" data-search="{terms}">'
        '<div class="product-media"><span class="badge-instock">В наличии</span>'
        f'<a href="{href}" tabindex="-1"><img src="{ctx.asset(image)}" '
        f'alt="{E(name)} — {E(label)}, {E(volume)}" loading="lazy" decoding="async"></a></div>'
        '<div class="product-body">'
        f'<span class="product-cat">{E(label)}</span>'
        f'<{h} class="product-title"><a href="{href}">{E(name)}</a></{h}>'
        f'<p class="product-volume">{E(volume)}</p>'
        f'<div class="product-price"><span class="price-value">{PRICE_TEXT}</span>'
        f'<span class="price-note">{E(PRICE_NOTE)}</span></div>'
        '<div class="product-actions">'
        f'<button class="add-basket" type="button" data-product="{index_of(item)}" '
        f'data-label="{E(name)} — в корзине">В корзину</button>'
        f'<a class="product-call" href="{CFG.PHONE_HREF}" '
        f'aria-label="Позвонить и заказать: {E(name)}">{ICON_PHONE}</a>'
        '</div></div></article>'
    )


def product_cards(ctx: Ctx, items) -> str:
    return "".join(product_card(ctx, item) for item in items)


def shelf(ctx: Ctx, anchor: str, title: str, subtitle: str, items, link: str | None = "catalog/",
          link_label: str = "Весь каталог") -> str:
    cards = product_cards(ctx, items)
    controls = ('<div class="shelf-controls">'
                f'<button class="shelf-nav" type="button" data-shelf-prev aria-label="Прокрутить «{E(title)}» назад">←</button>'
                f'<button class="shelf-nav" type="button" data-shelf-next aria-label="Прокрутить «{E(title)}» вперёд">→</button>'
                '</div>')
    link_html = f'<a class="section-link" href="{ctx.page(link)}">{E(link_label)} →</a>' if link else ""
    return (
        f'<section class="shelf" id="{E(anchor)}" data-shelf aria-labelledby="{E(anchor)}-title">'
        '<div class="shelf-head"><div>'
        f'<h2 id="{E(anchor)}-title">{E(title)}</h2><p>{E(subtitle)}</p></div>'
        f'<div class="shelf-tools">{link_html}{controls}</div></div>'
        f'<div class="shelf-track">{cards}</div></section>'
    )


def category_rail(ctx: Ctx, current: str = "", *, counts: bool = False) -> str:
    links = []
    for cat, label in LABELS.items():
        active = ' aria-current="page"' if current == cat else ""
        first = items_of(cat)[0]
        count = f'<small>{len(items_of(cat))} поз.</small>' if counts else ""
        links.append(
            f'<a class="category-link" href="{ctx.page(f"catalog/{cat}/")}"{active}>'
            f'<img src="{ctx.asset(first[3])}" alt="" loading="lazy" decoding="async">'
            f'<span>{E(label)}</span>{count}</a>')
    return f'<div class="cat-track">{"".join(links)}</div>'


def district_tiles(ctx: Ctx, current: str = "") -> str:
    tiles = []
    for key, (label, _, short) in CFG.DISTRICTS.items():
        active = ' aria-current="page"' if current == key else ""
        tiles.append(f'<a class="tile" href="{ctx.page(f"delivery/{key}/")}"{active}>'
                     f'<strong>{E(short)}</strong><span>{E(label)}</span></a>')
    return f'<div class="tile-grid">{"".join(tiles)}</div>'


def features_block() -> str:
    items = [
        (ICON_TRUCK, "Доставка по Москве",
         f"{len(CFG.DISTRICTS)} округов — от Центрального до Зеленоградского. "
         "Условия по вашему адресу назовёт оператор."),
        (ICON_PHONE, "Заказ звонком или в Telegram",
         "Позвоните или напишите боту: подтвердим наличие, объём и стоимость."),
        (ICON_LIST, "Корзина-список",
         "Соберите позиции на сайте. Список хранится на вашем устройстве и никуда не уходит."),
    ]
    cards = "".join(f'<div class="feature"><span class="feature-icon">{icon}</span>'
                    f'<div><h3>{E(title)}</h3><p>{E(text)}</p></div></div>'
                    for icon, title, text in items)
    return f'<section class="section" aria-label="Как мы работаем"><div class="features">{cards}</div></section>'


def cta_band(ctx: Ctx) -> str:
    return (
        '<section class="section"><div class="cta-band">'
        '<div><h2>Не нашли нужный напиток?</h2>'
        '<p>Позвоните — подскажем, что есть в наличии, и назовём стоимость.</p></div>'
        '<div class="cta-band-actions">'
        f'<a class="btn btn-light" href="{CFG.PHONE_HREF}">Позвонить {E(CFG.PHONE_HUMAN)}</a>'
        f'<a class="btn btn-outline" href="{CFG.TELEGRAM_URL}">Написать в Telegram</a>'
        '</div></div></section>'
    )


# --------------------------------------------------------------------------- шапка документа
def analytics() -> str:
    """Счётчики Метрики/GA4: только рабочие страницы и только при заданных ID."""
    blocks = []
    if CFG.YANDEX_METRIKA_ID:
        counter = str(CFG.YANDEX_METRIKA_ID).strip()
        blocks.append(
            "<script>(function(){(function(m,e,t,r,i,k,a){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};"
            "m[i].l=1*new Date();k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,"
            "a.parentNode.insertBefore(k,a)})(window,document,'script','https://mc.yandex.ru/metrika/tag.js','ym');"
            f"ym({E(counter)},'init',{{clickmap:true,trackLinks:true,accurateTrackBounce:true}});}})();</script>"
            f'<noscript><div><img src="https://mc.yandex.ru/watch/{E(counter)}" '
            'style="position:absolute;left:-9999px" alt=""></div></noscript>')
    if CFG.GA4_ID:
        gid = E(str(CFG.GA4_ID).strip())
        blocks.append(
            "<script>(function(){var s=document.createElement('script');s.async=true;"
            f"s.src='https://www.googletagmanager.com/gtag/js?id={gid}';document.head.appendChild(s);"
            "window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)}window.gtag=gtag;"
            f"gtag('js',new Date());gtag('config','{gid}');}})();</script>")
    return "".join(blocks)


def render(ctx: Ctx, *, title: str, description: str, body: str, robots: str = "index,follow",
           schema=(), og_type: str = "website", og_image: str | None = None,
           test_bar: bool = True) -> Path:
    prefix_depth = ctx.depth + (1 if ctx.tree else 0)
    asset_prefix = "../" * prefix_depth
    page_prefix = ctx.page("")
    canonical = "" if ctx.is_test else f'<link rel="canonical" href="{E(absolute(ctx.path))}">'
    og_url = "" if ctx.is_test else f'<meta property="og:url" content="{E(absolute(ctx.path))}">'
    json_ld = "".join(
        '<script type="application/ld+json">'
        + json.dumps(block, ensure_ascii=False).replace("<", "\\u003c")
        + "</script>" for block in schema)
    scripts_html = (f'<script src="{asset_prefix}assets/js/products.js" defer></script>'
                    f'<script src="{asset_prefix}assets/js/site.js" defer></script>')
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
<html lang="ru" data-site="{site_id}" data-image-base="{asset_prefix}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><meta name="robots" content="{robots if not ctx.is_test else "noindex,nofollow"}"><title>{E(title)}</title><meta name="description" content="{E(description)}">{canonical}<meta name="theme-color" content="#0c1a12"><meta property="og:type" content="{og_type}"><meta property="og:site_name" content="{E(CFG.BRAND)}"><meta property="og:locale" content="ru_RU"><meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(description)}">{og_url}<meta property="og:image" content="{E(og_image or absolute("assets/og/cover.png"))}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta name="twitter:card" content="summary_large_image"><link rel="icon" href="{asset_prefix}favicon.ico" sizes="any"><link rel="icon" href="{asset_prefix}logo.svg" type="image/svg+xml"><link rel="icon" type="image/png" sizes="192x192" href="{asset_prefix}assets/icons/icon-192.png"><link rel="apple-touch-icon" sizes="180x180" href="{asset_prefix}assets/icons/apple-touch-icon.png"><link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Unbounded:wght@600;700&display=swap"><link rel="stylesheet" href="{asset_prefix}assets/css/site.css?v=1">{json_ld}{analytics_html}{scripts_html}</head>
<body>{body}
</body></html>'''
    target = ctx.out_dir()
    target.mkdir(parents=True, exist_ok=True)
    file = target / "index.html"
    file.write_text(document, encoding="utf-8")
    return file


def page(ctx: Ctx, *, title: str, description: str, content: str, **kwargs) -> Path:
    body = topbar(ctx) + header(ctx, kwargs.pop("current", "")) + content + footer(ctx) + mobile_bar(ctx) + cart_drawer()
    return render(ctx, title=title, description=description, body=body, **kwargs)


# --------------------------------------------------------------------------- главная
def home_body(ctx: Ctx) -> str:
    by_slug = {slug(item): item for item in PRODUCTS}
    hero_items = [by_slug[name] for name in HERO_SLUGS if name in by_slug]
    hero_parts = []
    for position, item in enumerate(hero_items):
        extra = ' fetchpriority="high"' if position == 1 else ' loading="lazy"'
        hero_parts.append(
            f'<img class="hero-bottle bottle-{position}" src="{ctx.asset(item[3])}" '
            f'alt="{E(item[1])}"{extra} decoding="async">')
    hero = (
        '<section class="hero"><div class="wrap">'
        '<div class="hero-copy">'
        '<span class="hero-eyebrow"><span class="dot"></span>Москва · круглосуточно</span>'
        '<h1>Доставка алкоголя <em>по Москве</em></h1>'
        f'<p class="hero-lead">Виски, водка, коньяк, вино, игристое и пиво — {len(PRODUCTS)} позиций '
        'с фотографиями. Соберите список в корзине и оформите заказ звонком или в Telegram.</p>'
        '<div class="hero-cta">'
        f'<a class="btn btn-light" href="{ctx.page("catalog/")}">Открыть каталог</a>'
        f'<a class="btn btn-outline" href="{CFG.PHONE_HREF}">{ICON_PHONE}Позвонить</a>'
        '</div>'
        f'<p class="hero-note">Цены не публикуем: стоимость и условия доставки подтверждает оператор '
        f'<strong>{E(CFG.PHONE_HUMAN)}</strong>.</p>'
        '</div>'
        f'<div class="hero-visual"><span class="hero-glow"></span>{"".join(hero_parts)}'
        f'<div class="hero-badges"><span class="hero-badge">В наличии · {len(PRODUCTS)} позиций</span>'
        '<span class="hero-badge">Заказ по звонку и в Telegram</span></div></div>'
        '</div></section>'
    )
    categories = (
        '<section class="cat-rail" aria-labelledby="cats-title"><div class="wrap">'
        '<h2 class="sr-only" id="cats-title">Категории напитков</h2>'
        + category_rail(ctx) + '</div></section>'
    )
    note = ('<p class="page-lead" style="margin:4px 0 0">Наличие, объём и стоимость подтверждает оператор: '
            'цены на сайте не публикуются.</p>')
    shelves = (
        '<div class="wrap">'
        + shelf(ctx, "strong", "Крепкий алкоголь",
                "Виски, водка, джин, коньяк, ликёры и вермут · наличие и цену уточняйте по телефону",
                [item for category in STRONG for item in items_of(category)])
        + shelf(ctx, "wine-beer", "Вино, игристое и пиво",
                "Белое и красное вино, игристое, пильзнер и лагер",
                [item for category in SHELF_LIGHT for item in items_of(category)],
                link="catalog/", link_label="Все напитки")
        + note + '</div>'
    )
    seo = (
        '<section class="seo-block"><div class="wrap"><div class="seo-inner">'
        '<div><h2>Доставка алкоголя по Москве</h2>'
        f'<p>В каталоге {len(PRODUCTS)} позиций в {len(CAT_SLUGS)} разделах: виски, водка, джин, коньяк, '
        'ликёры, вермут, вино, игристое и пиво. У каждой позиции есть фотография и объём из каталога — '
        'сравните их и соберите список перед звонком.</p>'
        '<h3>Как сделать заказ</h3>'
        '<ol><li>Выберите напитки в каталоге и добавьте нужные позиции в корзину.</li>'
        f'<li>Позвоните по номеру {E(CFG.PHONE_HUMAN)} или напишите в Telegram-бот.</li>'
        '<li>Оператор подтвердит наличие и стоимость, уточнит адрес и условия доставки.</li></ol>'
        '<h3>Что уточнить при звонке</h3>'
        '<ul><li>наличие и объём конкретной позиции;</li>'
        '<li>стоимость выбранных напитков;</li>'
        '<li>стоимость и условия доставки по вашему адресу.</li></ul>'
        '</div>'
        '<div><h2>Округа Москвы</h2>'
        f'<p>Доставка по Москве: {len(CFG.DISTRICTS)} округов, от Центрального до Зеленоградского. '
        'Выберите округ, чтобы посмотреть условия по вашему адресу.</p>'
        + '<div class="seo-links">'
        + "".join(f'<a href="{ctx.page(f"delivery/{key}/")}">{E(short)}</a>'
                  for key, (_, _, short) in CFG.DISTRICTS.items())
        + '</div>'
        '<h3>Частые вопросы</h3>'
        '<p>Как работает корзина, что уточняет оператор и как оформить заказ — собрали в разделе '
        f'<a href="{ctx.page("faq/")}">«Вопросы и ответы»</a>.</p>'
        f'<p>{E(CFG.DISCLAIMER)}. Продажа лицам младше 18 лет не осуществляется.</p>'
        '</div></div></div></section>'
    )
    return hero + categories + shelves + features_block() + cta_band(ctx) + seo


def build_home(ctx: Ctx) -> None:
    description = (f"Доставка алкоголя по Москве: {len(PRODUCTS)} позиций — виски, водка, коньяк, вино, "
                   f"игристое и пиво. Наличие и цену уточняйте по телефону {CFG.PHONE_HUMAN}.")
    page(ctx, title="Доставка алкоголя по Москве — АЛКО НОЧЬ", description=description,
         content=home_body(ctx), schema=[ld_website(), ld_store()])


# --------------------------------------------------------------------------- каталог
def catalog_sections(ctx: Ctx) -> str:
    sections = []
    for cat, label in LABELS.items():
        items = items_of(cat)
        sections.append(
            f'<section class="catalog-section" id="{cat}" data-section>'
            f'<h2>{E(label)}<span>{len(items)} поз. · '
            f'<a href="{ctx.page(f"catalog/{cat}/")}">открыть раздел</a></span></h2>'
            f'<div class="products-grid">{product_cards(ctx, items)}</div></section>')
    return "".join(sections)


def search_toolbar(ctx: Ctx, *, chips: bool) -> str:
    chips_html = ""
    if chips:
        buttons = '<button type="button" data-category="all" aria-pressed="true">Все напитки</button>'
        buttons += "".join(
            f'<button type="button" data-category="{cat}" aria-pressed="false">{E(label)}</button>'
            for cat, label in LABELS.items())
        chips_html = f'<div class="chips" id="category-chips" role="group" aria-label="Категории">{buttons}</div>'
    return (
        '<div class="toolbar">'
        '<label class="search-field">' + ICON_SEARCH +
        '<input id="catalog-search" type="search" placeholder="Найти напиток: Jameson, вино, джин…" '
        'aria-label="Поиск по каталогу"></label></div>' + chips_html
    )


def build_catalog(ctx: Ctx) -> None:
    description = (f"{len(PRODUCTS)} позиций в {len(CAT_SLUGS)} разделах: виски, водка, джин, коньяк, ликёры, "
                   "вермут, вино, игристое и пиво. Фотографии и объёмы, поиск по названию. "
                   "Цену уточняйте по телефону.")
    lead = ("Выберите напитки по фотографиям и объёмам, добавьте нужные позиции в корзину и назовите "
            "список оператору — он подтвердит наличие и стоимость.")
    meta = (f'<div class="page-meta"><span class="chip"><strong>{len(PRODUCTS)}</strong> позиций</span>'
            f'<span class="chip"><strong>{len(CAT_SLUGS)}</strong> разделов</span>'
            f'<span class="chip">{PRICE_TEXT} по телефону</span></div>')
    content = ('<main class="wrap">'
               + page_head(ctx, "Каталог напитков", lead,
                           [("Главная", ""), ("Каталог", None)], meta)
               + '<section class="section" style="padding-top:6px">'
               + category_rail(ctx, counts=True) + '</section>'
               + search_toolbar(ctx, chips=True)
               + '<div id="products">' + catalog_sections(ctx) + '</div>'
               + '<div class="empty-hint search-empty" hidden>Ничего не найдено. Попробуйте другое '
                 'название или позвоните — подскажем по наличию.'
               f' <a class="btn btn-primary" href="{CFG.PHONE_HREF}">Позвонить</a></div>'
               + '<section class="section"><div class="prose"><h2>Перед заказом</h2>'
                 '<p>Корзина — это список на вашем устройстве. Она не отправляет заказ автоматически '
                 'и ничего не оплачивает: при оформлении откроется звонок, и вы назовёте позиции '
                 'оператору.</p>'
                 '<p>Объёмы в карточках взяты из каталога и по фотографиям не проверялись: наличие, '
                 'объём и цену подтвердит оператор.</p></div></section>'
               '</main>')
    page(ctx, title="Каталог напитков — АЛКО НОЧЬ", description=description, content=content,
         current="catalog/",
         schema=[ld_collection("Каталог напитков", description, "catalog/"),
                 ld_breadcrumbs([("Главная", ""), ("Каталог", None)]),
                 ld_item_list("Каталог напитков", PRODUCTS)])


def build_category(ctx: Ctx, cat: str) -> None:
    label, text = CFG.CATEGORIES[cat]
    items = items_of(cat)
    siblings = [(LABELS[other], f"catalog/{other}/") for other in CAT_SLUGS if other != cat]
    meta = (f'<div class="page-meta"><span class="chip"><strong>{len(items)}</strong> позиций</span>'
            f'<span class="chip">В наличии</span>'
            f'<span class="chip">{PRICE_TEXT} по телефону</span></div>')
    content = ('<main class="wrap">'
               + page_head(ctx, label, text,
                           [("Главная", ""), ("Каталог", "catalog/"), (label, None)], meta)
               + '<div style="padding-top:10px">' + search_toolbar(ctx, chips=False) + '</div>'
               + f'<div id="products"><section class="catalog-section" id="{cat}" data-section>'
               + f'<div class="products-grid">{product_cards(ctx, items)}</div></section></div>'
               + '<div class="empty-hint search-empty" hidden>В этом разделе ничего не найдено. '
                 'Сбросьте поиск или позвоните — подскажем по наличию.</div>'
               + '<section class="section"><div class="prose"><h2>Как выбрать</h2>'
                 '<p>Добавьте интересующие напитки в корзину или позвоните сразу: цену, наличие и условия '
                 'доставки подтверждает оператор. Объёмы в карточках взяты из каталога и по фотографиям '
                 'не проверялись.</p>'
               + f'<p><a class="btn btn-primary" href="{CFG.PHONE_HREF}">Позвонить {E(CFG.PHONE_HUMAN)}</a> '
               + f'<a href="{ctx.page("catalog/")}">Весь каталог</a></p></div></section>'
               + '<section class="section"><h2 style="font-size:22px;font-weight:800;margin-bottom:14px">'
                 'Другие разделы</h2>'
               + '<div class="seo-links">'
               + "".join(f'<a href="{ctx.page(path)}">{E(name)}</a>' for name, path in siblings)
               + '</div></section>'
               + '</main>')
    page(ctx, title=f"{label} — купить с доставкой по Москве | АЛКО НОЧЬ", description=text,
         content=content, current="catalog/",
         schema=[ld_collection(label, text, f"catalog/{cat}/"),
                 ld_breadcrumbs([("Главная", ""), ("Каталог", "catalog/"), (label, None)]),
                 ld_item_list(label, items)])


# --------------------------------------------------------------------------- товар
def build_product(ctx: Ctx, item) -> None:
    category, name, volume, image = item
    label = LABELS[category]
    index = index_of(item)
    description = f"{name}, {volume}: в наличии. Цену и условия доставки уточняйте по телефону."
    same = [other for other in items_of(category) if other is not item]
    if len(same) < 5:
        extra = [other for other in interleave(CAT_SLUGS, 12) if other is not item and other not in same]
        same = (same + extra)[:5]
    else:
        same = same[:5]
    detail = (
        '<div class="product-detail">'
        f'<div class="detail-media"><img src="{ctx.asset(image)}" alt="{E(name)}, {E(volume)}" '
        'fetchpriority="high" decoding="async"></div>'
        '<div class="detail-info">'
        f'<div class="detail-meta"><span class="chip"><a href="{ctx.page(f"catalog/{category}/")}">'
        f'{E(label)}</a></span><span class="chip">{E(volume)}</span>'
        '<span class="chip"><span class="badge-instock" style="position:static">В наличии</span></span></div>'
        f'<h1>{E(name)}</h1>'
        '<div class="detail-price">'
        f'<span class="price-value">{PRICE_TEXT}</span>'
        f'<span class="price-note">Стоимость и условия доставки подтвердит оператор по телефону '
        f'{E(CFG.PHONE_HUMAN)}.</span></div>'
        '<div class="detail-actions">'
        '<div class="qty"><button type="button" data-qty-step="-1" aria-label="Уменьшить количество">−</button>'
        '<output id="detail-qty">1</output>'
        '<button type="button" data-qty-step="1" aria-label="Увеличить количество">+</button></div>'
        f'<button class="btn btn-primary add-basket" type="button" data-product="{index}" data-qty="1" '
        f'data-label="{E(name)} — в корзине">В корзину</button>'
        f'<a class="btn btn-ghost" href="{CFG.PHONE_HREF}">{ICON_PHONE}Позвонить</a>'
        '</div>'
        '<div class="detail-links">'
        f'<a href="{CFG.TELEGRAM_URL}">Написать в Telegram-бот</a>'
        f'<a href="{ctx.page(f"catalog/{category}/")}">Ещё в разделе «{E(label)}»</a>'
        f'<a href="{ctx.page("delivery/")}">Доставка и оплата</a></div>'
        '<p class="detail-note">Объём указан по данным каталога и по фотографии не проверялся. '
        'Цены на сайте не публикуются: наличие и стоимость подтверждает оператор. Корзина — список '
        'на вашем устройстве, заказ она не отправляет.</p>'
        '</div></div>'
    )
    content = ('<main class="wrap">'
               + '<div class="page-head">'
               + breadcrumbs(ctx, [("Главная", ""), ("Каталог", "catalog/"),
                                   (label, f"catalog/{category}/"), (name, None)])
               + '</div>'
               + detail
               + shelf(ctx, "also", "С этим товаром также покупают",
                       f"Другие позиции раздела «{label}» и каталога", same, link=None)
               + f'<p class="breadcrumbs"><a href="{ctx.page("catalog/")}">← Весь каталог</a> · '
               f'<a href="{ctx.page("delivery/")}">Доставка и округа</a> · '
               f'<a href="{ctx.page("faq/")}">Вопросы</a></p>'
               + '</main>')
    page(ctx, title=f"{name}, {volume} — АЛКО НОЧЬ", description=description, content=content,
         current="catalog/", og_type="product", og_image=absolute(image),
         schema=[ld_product(item),
                 ld_breadcrumbs([("Главная", ""), ("Каталог", "catalog/"),
                                 (label, f"catalog/{category}/"), (name, None)])])


# --------------------------------------------------------------------------- доставка
def build_delivery(ctx: Ctx) -> None:
    description = ("Как оформить заказ: выберите напитки, позвоните оператору или напишите в Telegram. "
                   "Наличие, стоимость и условия доставки по вашему адресу подтверждает оператор.")
    steps = (
        '<h2>Как оформить заказ</h2><ol>'
        '<li>Выберите напитки в каталоге и при желании добавьте их в корзину.</li>'
        f'<li>Позвоните по номеру {E(CFG.PHONE_HUMAN)} или напишите в Telegram-бот и назовите список.</li>'
        '<li>Оператор подтвердит наличие и стоимость, уточнит адрес и условия доставки.</li></ol>'
        '<h2>Что уточняет оператор</h2><ul>'
        '<li>наличие и объём выбранной позиции;</li>'
        '<li>цену напитков;</li>'
        '<li>стоимость и условия доставки по вашему адресу;</li>'
        '<li>удобное время получения.</li></ul>'
        '<h2>Оплата</h2>'
        '<p>Способ оплаты согласуется при заказе: его подтвердит оператор вместе со стоимостью. '
        'На сайте оплата не проводится — корзина только собирает список позиций.</p>'
        '<p>Цены на сайте не публикуются намеренно: ассортимент и стоимость меняются, поэтому '
        'актуальные данные называет оператор.</p>'
    )
    content = ('<main class="wrap">'
               + page_head(ctx, "Доставка и оплата", description,
                           [("Главная", ""), ("Доставка и оплата", None)],
                           f'<div class="page-meta"><span class="chip">Москва</span>'
                           f'<span class="chip"><strong>{len(CFG.DISTRICTS)}</strong> округов</span>'
                           f'<span class="chip">Заказ по телефону и в Telegram</span></div>')
               + f'<section class="section" style="padding-top:10px"><div class="prose">{steps}'
               + f'<p><a class="btn btn-primary" href="{CFG.PHONE_HREF}">Позвонить {E(CFG.PHONE_HUMAN)}</a> '
               + f'<a class="btn btn-ghost" href="{CFG.TELEGRAM_URL}">Telegram-бот</a></p></div></section>'
               + '<section class="section"><h2 style="font-size:24px;font-weight:800;margin-bottom:12px">'
                 'Округа Москвы</h2><p style="color:#6b7a72;margin-bottom:16px">Выберите округ, чтобы '
                 'посмотреть условия по вашему адресу.</p>'
               + district_tiles(ctx)
               + '</section>'
               + cta_band(ctx)
               + '</main>')
    page(ctx, title="Доставка и оплата — АЛКО НОЧЬ", description=description, content=content,
         current="delivery/",
         schema=[ld_breadcrumbs([("Главная", ""), ("Доставка и оплата", None)])])


def build_district(ctx: Ctx, district: str) -> None:
    label, where, short = CFG.DISTRICTS[district]
    title = f"Доставка алкоголя: {label} Москвы"
    description = (f"Доставка в {where} Москвы: выберите напитки в каталоге и уточните наличие, цену и "
                   "условия доставки по телефону или в Telegram.")
    text = (
        f'<h2>{E(short)} · {E(label)}</h2>'
        f'<p>Выберите напитки в каталоге и подготовьте список для заказа в {E(where)} Москвы: '
        'в карточках указаны названия, фотографии и объёмы.</p>'
        f'<p>Позвоните по номеру {E(CFG.PHONE_HUMAN)} или напишите в Telegram-бот и назовите адрес. '
        'Оператор подтвердит наличие и стоимость, а также условия доставки именно по вашему адресу — '
        'на сайте эти условия не публикуются.</p>'
        '<ul><li>наличие и объём выбранной позиции;</li><li>цена напитков;</li>'
        '<li>стоимость и условия доставки в ваш округ;</li><li>удобное время получения.</li></ul>'
    )
    content = ('<main class="wrap">'
               + page_head(ctx, title, description,
                           [("Главная", ""), ("Доставка и оплата", "delivery/"), (short, None)],
                           f'<div class="page-meta"><span class="chip">Москва · {E(short)}</span>'
                           f'<span class="chip">{PRICE_TEXT} по телефону</span></div>')
               + f'<section class="section" style="padding-top:10px"><div class="prose">{text}'
               + f'<p><a class="btn btn-primary" href="{CFG.PHONE_HREF}">Позвонить</a> '
               + f'<a class="btn btn-ghost" href="{ctx.page("catalog/")}">Открыть каталог</a></p></div>'
               + '</section>'
               + '<section class="section"><h2 style="font-size:22px;font-weight:800;margin-bottom:14px">'
                 'Другие округа</h2>' + district_tiles(ctx, district)
               + f'<p class="breadcrumbs" style="margin-top:16px">'
                 f'<a href="{ctx.page("delivery/")}">Доставка и оплата</a> · '
                 f'<a href="{ctx.page("catalog/")}">Каталог напитков</a></p></section>'
               + '</main>')
    page(ctx, title=f"{title} — АЛКО НОЧЬ", description=description, content=content,
         current="delivery/",
         schema=[ld_breadcrumbs([("Главная", ""), ("Доставка и оплата", "delivery/"), (short, None)])])


# --------------------------------------------------------------------------- вопросы
def build_faq(ctx: Ctx) -> None:
    description = "Ответы на частые вопросы: как работает корзина, как оформить заказ, что уточняет оператор."
    details = "".join(f"<details><summary>{E(question)}</summary><p>{E(answer)}</p></details>"
                      for question, answer in CFG.FAQ)
    content = ('<main class="wrap">'
               + page_head(ctx, "Вопросы и ответы", description,
                           [("Главная", ""), ("Вопросы и ответы", None)])
               + f'<section class="section" style="padding-top:10px"><div class="faq-list">{details}</div>'
               + f'<p class="breadcrumbs" style="margin-top:20px"><a href="{ctx.page("catalog/")}">Каталог</a> · '
                 f'<a href="{ctx.page("delivery/")}">Доставка и оплата</a> · '
                 f'<a href="{CFG.PHONE_HREF}">{E(CFG.PHONE_HUMAN)}</a></p></section>'
               + cta_band(ctx)
               + '</main>')
    page(ctx, title="Вопросы и ответы — АЛКО НОЧЬ", description=description, content=content,
         current="faq/",
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
        "   Цен нет намеренно: стоимость называет оператор по телефону. */\n"
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
<html lang="ru" data-site="alkonoch-test"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Тестовый просмотр — {E(CFG.BRAND)}</title><meta http-equiv="refresh" content="0; url=./test/"><link rel="icon" href="favicon.ico" sizes="any"><link rel="stylesheet" href="assets/css/site.css?v=1"></head>
<body><div class="test-bar">Тестовый просмотр · страницы закрыты от индексации</div><main class="wrap"><div class="page-head"><h1>Тестовый просмотр</h1><p class="page-lead">Открывается тестовое дерево страниц: те же разделы, каталог и товары.</p><div class="page-meta"><a class="btn btn-primary" href="./test/">Открыть тестовый просмотр</a><a class="btn btn-ghost" href="./">Рабочий сайт</a></div></div></main></body></html>
''', encoding="utf-8")


def write_404() -> None:
    (ROOT / "404.html").write_text(f'''<!doctype html>
<html lang="ru" data-site="alkonoch"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><meta name="robots" content="noindex,follow"><title>Страница не найдена — {E(CFG.BRAND)}</title><link rel="icon" href="favicon.ico" sizes="any"><link rel="stylesheet" href="assets/css/site.css?v=1"></head>
<body><main class="wrap"><div class="page-head"><nav class="breadcrumbs" aria-label="Навигационная цепочка"><a href="./">Главная</a><span> / </span><span>Страница не найдена</span></nav><h1>Страница не найдена</h1><p class="page-lead">Возможно, ссылка устарела. Откройте каталог или позвоните — подскажем по наличию и цене.</p><div class="page-meta"><a class="btn btn-primary" href="./catalog/">Каталог напитков</a><a class="btn btn-ghost" href="{CFG.PHONE_HREF}">{E(CFG.PHONE_HUMAN)}</a><a class="btn btn-ghost" href="{CFG.TELEGRAM_URL}">Telegram-бот</a></div></div></main></body></html>
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
