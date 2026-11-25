/* Поведенческие тесты собранного сайта: правила доступа, каталог, поиск, корзина.
 *
 * Запуск (jsdom ставится отдельно, в репозиторий не попадает):
 *   python3 -m http.server 8000 --bind 127.0.0.1   # в корне репозитория
 *   mkdir -p /tmp/sitetest && cd /tmp/sitetest && npm init -y && npm i jsdom@24
 *   cp <repo>/tools/behavior-test.js . && node behavior-test.js
 *
 * Переменная BASE меняет адрес сервера: BASE=http://127.0.0.1:8000 node behavior-test.js
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
    return null; // skip Google Fonts and other external hosts
  }
}

const results = [];
function check(name, condition, extra = '') {
  results.push({ name, ok: !!condition, extra });
  console.log(`${condition ? 'PASS' : 'FAIL'}  ${name}${extra ? '  — ' + extra : ''}`);
}

async function load(path, { ua = DESKTOP, referrer = '', session = null, local = null } = {}) {
  const dom = await JSDOM.fromURL(BASE + path, {
    userAgent: ua,
    referrer: referrer || undefined,
    runScripts: 'dangerously',
    resources: new LocalOnly(),
    pretendToBeVisual: true,
    virtualConsole: new VirtualConsole(),
    beforeParse(window) {
      // jsdom 24 ignores the userAgent option, so the UA is installed before the page scripts run.
      Object.defineProperty(window.navigator, 'userAgent', { value: ua, configurable: true });
      if (session) Object.entries(session).forEach(([k, v]) => window.sessionStorage.setItem(k, v));
      if (local) Object.entries(local).forEach(([k, v]) => window.localStorage.setItem(k, v));
    },
  });
  await new Promise((resolve) => dom.window.addEventListener('load', resolve));
  await new Promise((resolve) => setTimeout(resolve, 120));
  return dom;
}

const blocked = (dom) => dom.window.document.documentElement.getAttribute('data-blocked') === '1';
const blockedBox = (dom) => dom.window.document.getElementById('blocked');
const session = (dom, key) => dom.window.sessionStorage.getItem(key);

(async () => {
  // ---------------------------------------------------------------- access rules
  let dom = await load('/', { ua: DESKTOP });
  check('десктоп: прямой вход → белый экран', blocked(dom));
  check('десктоп: белый экран без текста', blockedBox(dom) !== null && blockedBox(dom).textContent.trim() === '');
  dom.window.close();

  dom = await load('/', { ua: MOBILE });
  check('телефон: прямой вход закрыт', blocked(dom));
  check('телефон: показывает «Ошибка загрузки страницы.»', (blockedBox(dom)?.textContent || '').includes('Ошибка загрузки'));
  dom.window.close();

  dom = await load('/', { ua: MOBILE, referrer: 'https://www.google.com/' });
  check('телефон из Google: доступ открыт', !blocked(dom));
  check('телефон из Google: записан признак входа', session(dom, 'alkonoch-search-entry') === '1');
  dom.window.close();

  dom = await load('/', { ua: MOBILE, referrer: 'https://yandex.ru/search/?text=delivery' });
  check('телефон из Яндекса: доступ открыт', !blocked(dom));
  dom.window.close();

  dom = await load('/catalog/', { ua: MOBILE, referrer: BASE + '/' });
  check('телефон: внутренний переход без поискового входа закрыт', blocked(dom));
  dom.window.close();

  dom = await load('/catalog/', { ua: MOBILE, referrer: BASE + '/', session: { 'alkonoch-search-entry': '1' } });
  check('телефон: внутренний переход после входа из поиска открыт', !blocked(dom));
  dom.window.close();

  dom = await load('/catalog/product/jameson/', { ua: MOBILE, referrer: BASE + '/catalog/', session: { 'alkonoch-search-entry': '1' } });
  check('телефон: переход на страницу товара открыт', !blocked(dom));
  dom.window.close();

  dom = await load('/', { ua: GOOGLEBOT });
  check('Googlebot: доступ открыт', !blocked(dom));
  dom.window.close();

  dom = await load('/', { ua: YANDEXBOT });
  check('YandexBot: доступ открыт', !blocked(dom));
  dom.window.close();

  dom = await load('/test/', { ua: DESKTOP });
  check('/test/ с десктопа доступен', !blocked(dom));
  check('/test/ помечен как тестовый просмотр', !!dom.window.document.querySelector('.test-bar'));
  check('/test/ закрыт от индексации', dom.window.document.querySelector('meta[name=robots]').content.includes('noindex'));
  dom.window.close();

  for (const path of ['/test/catalog/', '/test/catalog/whisky/', '/test/catalog/product/jameson/', '/test/delivery/cao/', '/test/faq/']) {
    const page = await load(path, { ua: DESKTOP });
    check(`${path} с десктопа доступен и открыт`, !blocked(page) && page.window.document.querySelector('h1') !== null);
    page.window.close();
  }

  // ---------------------------------------------------------------- home catalogue
  dom = await load('/', { ua: GOOGLEBOT });
  let doc = dom.window.document;
  check('главная: 30 карточек товаров', doc.querySelectorAll('#products article.product').length === 30, String(doc.querySelectorAll('#products article.product').length));
  check('главная: 11 фильтров категорий', doc.querySelectorAll('#filters button').length === 11, String(doc.querySelectorAll('#filters button').length));
  check('главная: в герое 3 бутылки', doc.querySelectorAll('#hero-bottles img').length === 3);
  check('главная: картинки героя грузятся из img/', [...doc.querySelectorAll('#hero-bottles img')].every((img) => img.getAttribute('src').startsWith('img/')));
  check('главная: заголовок h1 содержит «Доставка алкоголя»', doc.querySelector('h1').textContent.includes('Доставка алкоголя'));
  const search = doc.getElementById('search');
  search.value = 'jameson';
  search.dispatchEvent(new dom.window.Event('input'));
  check('главная: поиск «jameson» → 1 карточка', doc.querySelectorAll('#products article.product').length === 1);
  search.value = '';
  search.dispatchEvent(new dom.window.Event('input'));
  doc.querySelector('#filters button[data-category="vodka"]').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }));
  check('главная: фильтр «Водка» → 4 карточки', doc.querySelectorAll('#products article.product').length === 4, String(doc.querySelectorAll('#products article.product').length));
  const homeLink = doc.querySelector('#products a.expanded-product-title');
  check('главная: карточка ведёт на страницу товара', /^catalog\/product\/[a-z0-9-]+\/$/.test(homeLink.getAttribute('href')), homeLink.getAttribute('href'));
  check('главная: в карточке «В наличии» и цена по телефону', doc.querySelector('#products .product-info').textContent.includes('В наличии') && doc.querySelector('#products .product-info').textContent.includes('цену уточняйте по телефону'));
  dom.window.close();

  // ---------------------------------------------------------------- catalogue page
  dom = await load('/catalog/', { ua: MOBILE, referrer: 'https://www.google.com/' });
  doc = dom.window.document;
  check('каталог: 30 карточек', doc.querySelectorAll('article.expanded-product').length === 30);
  check('каталог: 10 ссылок категорий', doc.querySelectorAll('.category-grid a.category-link').length === 10);
  const csearch = doc.getElementById('expanded-search');
  csearch.value = 'виски';
  csearch.dispatchEvent(new dom.window.Event('input'));
  const visibleSections = [...doc.querySelectorAll('.catalog-section')].filter((s) => !s.hidden).length;
  check('каталог: поиск оставляет только разделы с совпадениями', visibleSections === 1, String(visibleSections));
  csearch.value = 'неттакого';
  csearch.dispatchEvent(new dom.window.Event('input'));
  check('каталог: пустой результат показывает подсказку', !doc.querySelector('.search-empty').hidden);
  csearch.value = '';
  csearch.dispatchEvent(new dom.window.Event('input'));

  const addButton = doc.querySelector('.add-basket[data-product="0"]');
  addButton.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }));
  const stored = JSON.parse(dom.window.localStorage.getItem('selection-alkonoch-v1') || '{}');
  check('корзина: товар записан в localStorage', stored['0'] === 1, JSON.stringify(stored));
  check('корзина: счётчик в шапке обновился', doc.querySelector('.basket-count').textContent === '1');
  check('корзина: плавающая кнопка появилась', doc.querySelector('.basket-float').hidden === false);
  doc.querySelector('.basket-open').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }));
  check('корзина: диалог открывается', doc.querySelector('.basket-dialog').hasAttribute('open') || doc.querySelector('.basket-dialog').open === true);
  const checkout = doc.querySelector('.basket-checkout');
  check('корзина: оформление — ссылка на звонок', checkout.getAttribute('href') === 'tel:+74950959599');
  check('корзина: нет формы отправки заказа', doc.querySelectorAll('.basket-dialog form').length === 0);
  check('корзина: текст объясняет, что заказ не отправляется', doc.querySelector('.basket-note').textContent.includes('не отправляет заказ автоматически'));
  const savedBasket = dom.window.localStorage.getItem('selection-alkonoch-v1');
  dom.window.close();

  // ---------------------------------------------------------------- persistence
  dom = await load('/catalog/product/jameson/', {
    ua: MOBILE,
    referrer: BASE + '/catalog/',
    session: { 'alkonoch-search-entry': '1' },
    local: { 'selection-alkonoch-v1': savedBasket },
  });
  doc = dom.window.document;
  check('корзина сохраняется между страницами', doc.querySelector('.basket-count').textContent === '1');
  check('страница товара: объём и наличие', doc.body.textContent.includes('0,7 л') && doc.body.textContent.includes('В наличии'));
  check('страница товара: кнопка звонка', !!doc.querySelector('a[href="tel:+74950959599"]'));
  check('страница товара: ссылка на Telegram-бота', !!doc.querySelector('a[href="https://t.me/alkomsk_shop_bot"]'));
  const productLd = [...doc.querySelectorAll('script[type="application/ld+json"]')].map((s) => JSON.parse(s.textContent)).find((d) => d['@type'] === 'Product');
  check('страница товара: Product JSON-LD без цены', productLd && !JSON.stringify(productLd.offers).includes('price'), JSON.stringify(productLd?.offers));
  check('страница товара: абсолютная картинка в JSON-LD', productLd.image[0].startsWith('https://24alkomoscow.site/img/'));
  dom.window.close();

  // ---------------------------------------------------------------- test tree keeps its own basket
  dom = await load('/test/catalog/', { ua: DESKTOP, local: { 'selection-alkonoch-v1': savedBasket } });
  doc = dom.window.document;
  check('тестовый каталог: своя корзина, не смешивается с рабочей', doc.querySelector('.basket-count').textContent === '0');
  dom.window.close();

  const failed = results.filter((r) => !r.ok);
  console.log(`\nВсего проверок: ${results.length}, провалено: ${failed.length}`);
  process.exit(failed.length ? 1 : 0);
})().catch((error) => { console.error(error); process.exit(1); });
