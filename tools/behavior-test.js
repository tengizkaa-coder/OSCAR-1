/* Поведенческие тесты собранного сайта: доступ, каталог, переходы внутри /test/, корзина.
 *
 * Запуск (jsdom ставится отдельно, в репозиторий не попадает):
 *   python3 -m http.server 8000 --bind 127.0.0.1   # в корне репозитория
 *   ВАЖНО: не tools/preview-server.py — он перенаправляет «/» на «/test/», и тесты главной упадут.
 *   mkdir -p /tmp/sitetest && cd /tmp/sitetest && npm init -y && npm i jsdom@24
 *   cp <repo>/tools/behavior-test.js . && BASE=http://127.0.0.1:8000 node behavior-test.js
 */
const { JSDOM, ResourceLoader, VirtualConsole } = require('jsdom');

const BASE = process.env.BASE || 'http://127.0.0.1:8000';
const MOBILE = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1';
const DESKTOP = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36';
const GOOGLEBOT = 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)';
const YANDEXBOT = 'Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)';

class LocalOnly extends ResourceLoader {
  fetch(url, options) {
    if (url.startsWith(BASE)) return super.fetch(url, options);
    return null; // пропускаем Google Fonts и прочие внешние хосты
  }
}

const results = [];
function check(name, condition, extra = '') {
  results.push({ name, ok: !!condition });
  console.log(`${condition ? 'PASS' : 'FAIL'}  ${name}${extra ? '  — ' + extra : ''}`);
}

async function load(path, { ua = DESKTOP, referrer = '', session = null, local = null } = {}) {
  const dom = await JSDOM.fromURL(BASE + path, {
    referrer: referrer || undefined,
    runScripts: 'dangerously',
    resources: new LocalOnly(),
    pretendToBeVisual: true,
    virtualConsole: new VirtualConsole(),
    beforeParse(window) {
      // jsdom 24 игнорирует опцию userAgent, поэтому UA ставим до запуска скриптов страницы.
      Object.defineProperty(window.navigator, 'userAgent', { value: ua, configurable: true });
      if (session) Object.entries(session).forEach(([key, value]) => window.sessionStorage.setItem(key, String(value)));
      if (local) Object.entries(local).forEach(([key, value]) => window.localStorage.setItem(key, String(value)));
    },
  });
  await new Promise((resolve) => dom.window.addEventListener('load', resolve));
  await new Promise((resolve) => setTimeout(resolve, 120));
  return dom;
}

const blocked = (dom) => dom.window.document.documentElement.getAttribute('data-blocked') === '1';
const blockedBox = (dom) => dom.window.document.getElementById('blocked');
const visibleCards = (dom) => [...dom.window.document.querySelectorAll('#products article.product')].filter((card) => !card.hidden);
const urlOf = (dom, href) => new URL(href, dom.window.location.href).pathname;

(async () => {
  // ------------------------------------------------------------ правила доступа
  let dom = await load('/', { ua: DESKTOP });
  check('десктоп: прямой вход → белый экран', blocked(dom));
  check('десктоп: белый экран без текста', blockedBox(dom) !== null && blockedBox(dom).textContent.trim() === '');
  dom.window.close();

  dom = await load('/', { ua: MOBILE });
  check('телефон: прямой вход закрыт', blocked(dom));
  check('телефон: «Ошибка загрузки страницы.»', (blockedBox(dom)?.textContent || '').includes('Ошибка загрузки'));
  dom.window.close();

  dom = await load('/', { ua: MOBILE, referrer: 'https://www.google.com/' });
  check('телефон из Google: доступ открыт', !blocked(dom));
  check('телефон из Google: вход запомнен', dom.window.sessionStorage.getItem('alkonoch-search-entry') === '1');
  dom.window.close();

  dom = await load('/', { ua: MOBILE, referrer: 'https://yandex.ru/search/?text=alko' });
  check('телефон из Яндекса: доступ открыт', !blocked(dom));
  dom.window.close();

  dom = await load('/catalog/', { ua: MOBILE, referrer: BASE + '/' });
  check('телефон: внутренний переход без поискового входа закрыт', blocked(dom));
  dom.window.close();

  dom = await load('/catalog/', { ua: MOBILE, referrer: BASE + '/', session: { 'alkonoch-search-entry': '1' } });
  check('телефон: внутренний переход после входа открыт', !blocked(dom));
  dom.window.close();

  dom = await load('/catalog/product/jameson/', { ua: MOBILE, referrer: BASE + '/catalog/whisky/', session: { 'alkonoch-search-entry': '1' } });
  check('телефон: страница товара открыта', !blocked(dom));
  dom.window.close();

  for (const [ua, name] of [[GOOGLEBOT, 'Googlebot'], [YANDEXBOT, 'YandexBot']]) {
    dom = await load('/', { ua });
    check(`${name}: доступ открыт`, !blocked(dom));
    dom.window.close();
  }

  // ------------------------------------------------------------ каталог в статическом HTML
  const rawHome = await (await fetch(BASE + '/')).text();
  check('главная: 30 карточек в HTML без JavaScript', (rawHome.match(/article class="product"/g) || []).length === 30);
  check('главная: 11 фильтров в HTML', (rawHome.match(/<button type="button" data-category=/g) || []).length === 11);
  check('главная: названия категорий есть в HTML', rawHome.includes('>Виски<') && rawHome.includes('>Пиво<'));
  check('главная: герой — 3 статичные бутылки', (rawHome.match(/class="hero-bottle/g) || []).length === 3);

  dom = await load('/', { ua: GOOGLEBOT });
  let doc = dom.window.document;
  check('главная: 30 карточек отрисовано', doc.querySelectorAll('#products article.product').length === 30);
  const firstHref = urlOf(dom, doc.querySelector('#products a.expanded-product-title').getAttribute('href'));
  check('главная: карточка ведёт на страницу товара', /^\/catalog\/product\/[a-z0-9-]+\/$/.test(firstHref), firstHref);
  const cardText = doc.querySelector('#products .product-info').textContent;
  check('главная: «В наличии» и цена по телефону', cardText.includes('В наличии') && cardText.includes('цену уточняйте по телефону'));
  check('главная: у карточки есть ссылка на звонок', !!doc.querySelector('#products .product-info a[href^="tel:"]'));

  const searchInput = doc.getElementById('search');
  searchInput.value = 'jameson';
  searchInput.dispatchEvent(new dom.window.Event('input'));
  check('главная: поиск «jameson» → 1 позиция', visibleCards(dom).length === 1, String(visibleCards(dom).length));
  searchInput.value = 'нет такого напитка';
  searchInput.dispatchEvent(new dom.window.Event('input'));
  check('главная: пустой результат показывает подсказку', !doc.getElementById('empty').hidden);
  searchInput.value = '';
  searchInput.dispatchEvent(new dom.window.Event('input'));
  doc.querySelector('#filters button[data-category="vodka"]').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }));
  check('главная: фильтр «Водка» → 4 позиции', visibleCards(dom).length === 4, String(visibleCards(dom).length));
  check('главная: перенумерация видимых карточек', visibleCards(dom)[0].querySelector('.product-number').textContent === '01');
  doc.querySelector('#filters button[data-category="all"]').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }));
  check('главная: «Все напитки» → снова 30', visibleCards(dom).length === 30);
  dom.window.close();

  // ------------------------------------------------------------ поиск на страницах каталога
  dom = await load('/catalog/', { ua: GOOGLEBOT });
  doc = dom.window.document;
  const catalogSearch = doc.getElementById('expanded-search');
  catalogSearch.value = 'виски';
  catalogSearch.dispatchEvent(new dom.window.Event('input'));
  const visibleSections = [...doc.querySelectorAll('.catalog-section')].filter((section) => !section.hidden && section.querySelector('.expanded-product'));
  check('каталог: поиск «виски» оставляет один раздел', visibleSections.length === 1, String(visibleSections.length));
  catalogSearch.value = 'нет такого';
  catalogSearch.dispatchEvent(new dom.window.Event('input'));
  check('каталог: пустой результат показывает подсказку', !doc.querySelector('.search-empty').hidden);
  dom.window.close();

  dom = await load('/catalog/whisky/', { ua: GOOGLEBOT });
  doc = dom.window.document;
  const categorySearch = doc.getElementById('expanded-search');
  categorySearch.value = 'jack';
  categorySearch.dispatchEvent(new dom.window.Event('input'));
  const leftCards = [...doc.querySelectorAll('.expanded-product')].filter((card) => !card.hidden);
  const otherSections = [...doc.querySelectorAll('.catalog-section')].filter((section) => !section.querySelector('.expanded-product'));
  check('раздел: поиск «jack» → 1 позиция', leftCards.length === 1, String(leftCards.length));
  check('раздел: блок «Другие разделы» не скрывается поиском', otherSections.length > 0 && otherSections.every((section) => !section.hidden));
  dom.window.close();

  // ------------------------------------------------------------ переходы внутри /test/
  dom = await load('/test/', { ua: DESKTOP });
  doc = dom.window.document;
  check('/test/ открыт с десктопа', !blocked(dom));
  check('/test/ помечен как тестовый просмотр', !!doc.querySelector('.test-bar'));
  check('/test/ закрыт от индексации', doc.querySelector('meta[name=robots]').content.includes('noindex'));
  check('/test/: 30 карточек в HTML', doc.querySelectorAll('#products article.product').length === 30);
  const navCatalog = doc.querySelector('.navigation a[href$="catalog/"]');
  check('/test/: ссылка «Каталог» ведёт внутрь /test/', urlOf(dom, navCatalog.getAttribute('href')).startsWith('/test/catalog/'), urlOf(dom, navCatalog.getAttribute('href')));
  dom.window.close();

  dom = await load('/test/catalog/', { ua: DESKTOP });
  check('/test/catalog/ открыт', !blocked(dom) && dom.window.document.querySelector('h1').textContent.includes('Каталог'));
  check('/test/catalog/: 30 карточек', dom.window.document.querySelectorAll('article.expanded-product').length === 30);
  const catLink = dom.window.document.querySelector('.category-grid a.category-link[href*="whisky"]');
  const catUrl = urlOf(dom, catLink.getAttribute('href'));
  check('/test/catalog/: ссылка на раздел ведёт внутрь /test/', catUrl === '/test/catalog/whisky/', catUrl);
  dom.window.close();

  dom = await load('/test/catalog/whisky/', { ua: DESKTOP });
  doc = dom.window.document;
  check('/test/catalog/whisky/ открыт', !blocked(dom) && doc.querySelector('h1').textContent.trim() === 'Виски');
  check('/test/catalog/whisky/: 5 позиций', doc.querySelectorAll('article.expanded-product').length === 5);
  const productHref = urlOf(dom, doc.querySelector('a.expanded-product-title').getAttribute('href'));
  check('/test/catalog/whisky/: ссылка на товар внутри /test/', productHref.startsWith('/test/catalog/product/'), productHref);
  dom.window.close();

  dom = await load('/test/catalog/product/jameson/', { ua: DESKTOP });
  doc = dom.window.document;
  check('/test/catalog/product/jameson/ открыт', !blocked(dom) && doc.querySelector('h1').textContent.includes('Jameson'));
  check('товар в /test/: кнопка звонка', !!doc.querySelector('a[href="tel:+74950959599"]'));
  check('товар в /test/: ссылка на Telegram', !!doc.querySelector('a[href="https://t.me/alkomsk_shop_bot"]'));
  const crumbs = [...doc.querySelectorAll('.breadcrumbs a')].map((a) => urlOf(dom, a.getAttribute('href')));
  check('товар в /test/: хлебные крошки внутри /test/', crumbs.every((url) => url.startsWith('/test/')), crumbs.join(' '));
  const others = [...doc.querySelectorAll('.homepage-extra-nav a[href*="catalog/product"]')].map((a) => urlOf(dom, a.getAttribute('href')));
  check('товар в /test/: «Ещё в разделе» внутри /test/', others.length > 0 && others.every((url) => url.startsWith('/test/')), String(others.length));
  dom.window.close();

  for (const [path, heading] of [['/test/delivery/', 'Доставка'], ['/test/delivery/cao/', 'Центральный округ'], ['/test/faq/', 'Вопросы']]) {
    const page = await load(path, { ua: DESKTOP });
    const pageDoc = page.window.document;
    const escapes = [...pageDoc.querySelectorAll('a[href]')]
      .map((a) => a.getAttribute('href'))
      .filter((href) => href && !/^(https?:|tel:|mailto:|#)/.test(href) && !href.startsWith('../'))
      .map((href) => urlOf(page, href))
      .filter((url) => !url.startsWith('/test/'));
    check(`${path} открыт и не уводит из /test/`, !blocked(page) && pageDoc.querySelector('h1').textContent.includes(heading) && escapes.length === 0, escapes.slice(0, 3).join(' '));
    page.window.close();
  }

  const rawTestCatalog = await (await fetch(BASE + '/test/catalog/')).text();
  const pageLinks = [...rawTestCatalog.matchAll(/<a[^>]+href="([^"]+)"[^>]*>/g)]
    .filter(([tag]) => !tag.includes('data-tree="production"'))
    .map(([, href]) => href)
    .filter((href) => href.endsWith('/') && !/^(https?:|tel:)/.test(href));
  const resolved = pageLinks.map((href) => new URL(href, BASE + '/test/catalog/').pathname);
  check('/test/catalog/: все ссылки на разделы внутри /test/', resolved.every((url) => url.startsWith('/test/')), resolved.filter((url) => !url.startsWith('/test/')).slice(0, 3).join(' '));

  // ------------------------------------------------------------ корзина
  dom = await load('/catalog/', { ua: MOBILE, referrer: 'https://www.google.com/' });
  doc = dom.window.document;
  doc.querySelector('.add-basket[data-product="0"]').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }));
  const stored = JSON.parse(dom.window.localStorage.getItem('selection-alkonoch-v1') || '{}');
  check('корзина: позиция записана в localStorage', stored['0'] === 1, JSON.stringify(stored));
  check('корзина: счётчик в шапке', doc.querySelector('.basket-count').textContent === '1');
  doc.querySelector('.basket-open').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }));
  check('корзина: диалог открывается', doc.querySelector('.basket-dialog').hasAttribute('open') || doc.querySelector('.basket-dialog').open === true);
  check('корзина: оформление — ссылка на звонок', doc.querySelector('.basket-checkout').getAttribute('href') === 'tel:+74950959599');
  check('корзина: нет формы отправки заказа', doc.querySelectorAll('.basket-dialog form').length === 0);
  const savedBasket = dom.window.localStorage.getItem('selection-alkonoch-v1');
  dom.window.close();

  dom = await load('/catalog/product/jameson/', {
    ua: MOBILE, referrer: BASE + '/catalog/', session: { 'alkonoch-search-entry': '1' },
    local: { 'selection-alkonoch-v1': savedBasket },
  });
  check('корзина: сохраняется между страницами', dom.window.document.querySelector('.basket-count').textContent === '1');
  const productLd = [...dom.window.document.querySelectorAll('script[type="application/ld+json"]')]
    .map((node) => JSON.parse(node.textContent)).find((data) => data['@type'] === 'Product');
  check('товар: JSON-LD без цены', productLd && !JSON.stringify(productLd.offers).includes('price'));
  check('товар: абсолютная картинка в JSON-LD', productLd.image[0].startsWith('https://24alkomoscow.site/img/'));
  dom.window.close();

  dom = await load('/test/catalog/', { ua: DESKTOP, local: { 'selection-alkonoch-v1': savedBasket } });
  check('корзина теста отдельная от рабочей', dom.window.document.querySelector('.basket-count').textContent === '0');
  dom.window.close();

  const failed = results.filter((result) => !result.ok);
  console.log(`\nВсего проверок: ${results.length}, провалено: ${failed.length}`);
  process.exit(failed.length ? 1 : 0);
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
