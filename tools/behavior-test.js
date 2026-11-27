/* Поведенческие тесты собранного сайта: витрина, корзина, поиск, /test/.
 *
 * Запуск (jsdom ставится отдельно, в репозиторий не попадает):
 *   python3 -m http.server 8000 --bind 127.0.0.1   # в корне репозитория
 *   ВАЖНО: не tools/preview-server.py — он перенаправляет «/» на «/test/», и тесты главной упадут.
 *   mkdir -p /tmp/sitetest && cd /tmp/sitetest && npm init -y && npm i jsdom@24
 *   cp <repo>/tools/behavior-test.js . && BASE=http://127.0.0.1:8000 node behavior-test.js
 *
 * Проверяется то, что видит посетитель: страницы открываются, каталог на месте,
 * корзина считает и запоминает позиции, но никуда их не отправляет, а тестовое
 * дерево остаётся закрытым от индексации и не уводит в рабочий сайт.
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

async function load(path, { ua = DESKTOP, local = null } = {}) {
  const dom = await JSDOM.fromURL(BASE + path, {
    runScripts: 'dangerously',
    resources: new LocalOnly(),
    pretendToBeVisual: true,
    virtualConsole: new VirtualConsole(),
    beforeParse(window) {
      // jsdom 24 игнорирует опцию userAgent, поэтому UA ставим до запуска скриптов страницы.
      Object.defineProperty(window.navigator, 'userAgent', { value: ua, configurable: true });
      if (local) Object.entries(local).forEach(([key, value]) => window.localStorage.setItem(key, String(value)));
    },
  });
  await new Promise((resolve) => dom.window.addEventListener('load', resolve));
  await new Promise((resolve) => setTimeout(resolve, 120));
  return dom;
}

const doc = (dom) => dom.window.document;
const cards = (dom, scope = 'article.product') => [...doc(dom).querySelectorAll(scope)];
const counter = (dom) => doc(dom).querySelector('.site-header .basket-count');
const store = (dom, key = 'selection-alkonoch-v1') => {
  try { return JSON.parse(dom.window.localStorage.getItem(key) || '{}'); } catch { return {}; }
};
const click = (node) => node.dispatchEvent(new node.ownerDocument.defaultView.MouseEvent('click', { bubbles: true, cancelable: true }));

(async () => {
  // ------------------------------------------------ главная открыта всем
  let dom = await load('/', { ua: DESKTOP });
  check('десктоп: главная открыта, без заглушки', !doc(dom).documentElement.hasAttribute('data-blocked'));
  check('десктоп: есть заголовок H1', doc(dom).querySelectorAll('h1').length === 1);
  check('главная: полка категорий из 10 разделов', doc(dom).querySelectorAll('.category-link').length === 10);
  check('главная: две полки с товарами', doc(dom).querySelectorAll('[data-shelf]').length === 2);
  check('главная: карточек товаров не меньше 20', cards(dom).length >= 20, `найдено ${cards(dom).length}`);
  check('главная: три преимущества', doc(dom).querySelectorAll('.feature').length === 3);
  check('главная: в герое три бутылки', doc(dom).querySelectorAll('.hero-bottle').length === 3);
  check('на странице нет цены в рублях', !doc(dom).body.textContent.includes('₽'));
  check('у карточек есть «Цену уточняйте»', doc(dom).body.textContent.includes('Цену уточняйте'));
  dom.window.close();

  dom = await load('/', { ua: MOBILE });
  check('телефон: главная открыта', !doc(dom).documentElement.hasAttribute('data-blocked') && doc(dom).querySelectorAll('.product').length >= 20);
  check('телефон: есть нижняя панель со звонком', !!doc(dom).querySelector('.mobile-bar a[href^="tel:"]'));
  dom.window.close();

  dom = await load('/', { ua: GOOGLEBOT });
  check('Googlebot: страница отдаётся полностью', doc(dom).querySelectorAll('.product').length >= 20);
  dom.window.close();

  dom = await load('/', { ua: YANDEXBOT });
  check('YandexBot: страница отдаётся полностью', doc(dom).querySelectorAll('.product').length >= 20);
  dom.window.close();

  // ------------------------------------------------ корзина
  dom = await load('/');
  check('корзина: счётчик начинается с нуля', counter(dom).textContent.trim() === '0');
  const addButton = doc(dom).querySelector('.shelf-track .add-basket');
  const productName = addButton.dataset.label.replace(' — в корзине', '');
  click(addButton);
  check('корзина: после нажатия счётчик равен 1', counter(dom).textContent.trim() === '1');
  check('корзина: позиция записана в localStorage', Object.values(store(dom)).reduce((a, b) => a + b, 0) === 1);
  check('корзина: кнопка подтвердила добавление', addButton.textContent.includes('Добавлено'));

  const opener = doc(dom).querySelector('.site-header .basket-open');
  click(opener);
  check('корзина: панель открывается', doc(dom).querySelector('.cart-drawer').hasAttribute('open'));
  check('корзина: в списке есть добавленный товар', (doc(dom).querySelector('.basket-row .basket-name') || {}).textContent === productName);
  check('корзина: в строке виден объём', Boolean(doc(dom).querySelector('.basket-row .basket-sub')));

  click(doc(dom).querySelector('.basket-row .quantity button:last-child'));
  check('корзина: «+» увеличивает количество', counter(dom).textContent.trim() === '2');
  click(doc(dom).querySelector('.basket-row .quantity button'));
  check('корзина: «−» уменьшает количество', counter(dom).textContent.trim() === '1');

  const checkout = doc(dom).querySelector('.basket-checkout');
  check('корзина: оформление ведёт на звонок', (checkout.getAttribute('href') || '').startsWith('tel:'));
  check('корзина: на странице нет формы заказа', doc(dom).querySelectorAll('form').length === 0);
  check('корзина: подписано, что заказ не отправляется', doc(dom).querySelector('.basket-note').textContent.includes('не отправляется'));
  dom.window.close();

  dom = await load('/', { local: { 'selection-alkonoch-v1': '{"0":3}' } });
  check('корзина: сохраняется между загрузками', counter(dom).textContent.trim() === '3');
  dom.window.close();

  // ------------------------------------------------ страница товара
  dom = await load('/catalog/product/jameson/');
  check('товар: H1 с названием', (doc(dom).querySelector('h1') || {}).textContent === 'Jameson');
  check('товар: цена заменена на уточнение', doc(dom).querySelector('.detail-price .price-value').textContent === 'Цену уточняйте');
  check('товар: кнопка «В корзину» на месте', !!doc(dom).querySelector('.add-basket'));
  check('товар: блок «С этим товаром также покупают»',
    (doc(dom).querySelector('#also-title') || {}).textContent === 'С этим товаром также покупают');
  check('товар: в блоке пять карточек', doc(dom).querySelectorAll('#also article.product').length === 5);
  check('товар: есть ссылка на звонок', !!doc(dom).querySelector('a[href^="tel:"]'));
  click(doc(dom).querySelector('.add-basket'));
  check('товар: добавление в корзину работает', counter(dom).textContent.trim() === '1');
  dom.window.close();

  // ------------------------------------------------ категория
  dom = await load('/catalog/whisky/');
  const chips = doc(dom).querySelector('.page-meta .chip strong');
  check('категория: H1 — название раздела', (doc(dom).querySelector('h1') || {}).textContent === 'Виски');
  check('категория: счётчик совпадает с числом карточек', Number(chips.textContent) === cards(dom).length);
  check('категория: есть ссылки на другие разделы', doc(dom).querySelectorAll('.seo-links a').length === 9);
  check('категория: нет дублирующего заголовка раздела в полке', doc(dom).querySelectorAll('.category-link').length === 0);
  dom.window.close();

  // ------------------------------------------------ поиск
  dom = await load('/catalog/');
  const search = doc(dom).querySelector('#catalog-search');
  search.value = 'jack';
  search.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
  await new Promise((resolve) => setTimeout(resolve, 60));
  const visible = [...doc(dom).querySelectorAll('#products article.product')].filter((card) => !card.hidden);
  check('поиск: «jack» оставляет одну карточку', visible.length === 1, `видно ${visible.length}`);
  check('поиск: скрытые разделы убраны', [...doc(dom).querySelectorAll('.catalog-section')].every((section) => !section.hidden || section.querySelector('article.product')));

  search.value = 'нет-такого-напитка';
  search.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
  await new Promise((resolve) => setTimeout(resolve, 60));
  check('поиск: пустой результат показывает подсказку', !doc(dom).querySelector('.search-empty').hidden);

  search.value = '';
  search.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
  await new Promise((resolve) => setTimeout(resolve, 60));
  check('поиск: сброс возвращает весь каталог', [...doc(dom).querySelectorAll('#products article.product')].every((card) => !card.hidden));

  const chip = doc(dom).querySelector('#category-chips button[data-category="gin"]');
  click(chip);
  await new Promise((resolve) => setTimeout(resolve, 60));
  const ginVisible = [...doc(dom).querySelectorAll('#products article.product')].filter((card) => !card.hidden);
  check('фильтр: «Джин» оставляет товары только этого раздела', ginVisible.length === 2 && ginVisible.every((card) => card.dataset.category === 'gin'));
  dom.window.close();

  // ------------------------------------------------ мобильное меню
  dom = await load('/', { ua: MOBILE });
  click(doc(dom).querySelector('.burger'));
  check('меню: бургер раскрывает навигацию', doc(dom).querySelector('.mobile-nav').classList.contains('open'));
  dom.window.close();

  // ------------------------------------------------ тестовое дерево
  dom = await load('/test/');
  check('/test/: страница открыта', doc(dom).querySelectorAll('.product').length >= 20);
  check('/test/: noindex', (doc(dom).querySelector('meta[name="robots"]').getAttribute('content') || '').includes('noindex'));
  check('/test/: нет canonical', !doc(dom).querySelector('link[rel="canonical"]'));
  const testLinks = [...doc(dom).querySelectorAll('a[href]')]
    .map((a) => a.getAttribute('href'))
    .filter((href) => /^\.\.\//.test(href) === false && !/^(https?:|tel:|mailto:|#)/.test(href));
  const outside = [...doc(dom).querySelectorAll('a[href]')].filter((a) => {
    const href = a.getAttribute('href');
    if (/^(https?:|tel:|mailto:|#)/.test(href)) return false;
    if (href.startsWith('../../')) return false; // общие файлы: assets/, img/, logo.svg
    return !href.startsWith('.') && !href.startsWith('catalog') && !href.startsWith('delivery') && !href.startsWith('faq');
  });
  check('/test/: ссылки не уводят из теста', outside.length === 0, `подозрительных ${outside.length}`);
  check('/test/: есть предупреждающая полоса', !!doc(dom).querySelector('.test-bar'));
  const testAdd = doc(dom).querySelector('.add-basket');
  click(testAdd);
  check('/test/: отдельная корзина', store(dom, 'selection-alkonoch-test-v1')[testAdd.dataset.product] === 1);
  dom.window.close();

  dom = await load('/test/catalog/whisky/');
  check('/test/: страница категории открыта', cards(dom).length === 5);
  check('/test/: категория noindex', (doc(dom).querySelector('meta[name="robots"]').getAttribute('content') || '').includes('noindex'));
  dom.window.close();

  // ------------------------------------------------ итог
  const failed = results.filter((item) => !item.ok);
  console.log(`\nИтого: ${results.length} проверок, ${failed.length} провалов`);
  if (failed.length) {
    for (const item of failed) console.log('  FAIL:', item.name);
    process.exit(1);
  }
})().catch((error) => {
  console.error('Тест упал:', error);
  process.exit(1);
});
