/* Поведение витрины: корзина-список в localStorage, полки с прокруткой,
   мобильное меню и поиск по уже отрисованным карточкам.

   Корзина ничего никуда не отправляет и не оплачивает: это список на устройстве,
   оформление заказа — звонок оператору. Без JavaScript каталог, карточки и
   страницы товаров остаются полностью работоспособными. */
(() => {
  const root = document.documentElement;
  const site = root.dataset.site || 'alkonoch';
  const imageBase = root.dataset.imageBase || '';
  const products = Array.isArray(window.SITE_PRODUCTS) ? window.SITE_PRODUCTS : [];
  const key = `selection-${site}-v1`;

  /* ---------------------------------------------------------------- корзина */
  const baskets = [...document.querySelectorAll('.basket-count')];
  const drawer = document.querySelector('.cart-drawer');
  const rows = drawer && drawer.querySelector('.basket-items');
  const empty = drawer && drawer.querySelector('.basket-empty');
  const checkout = drawer && drawer.querySelector('.basket-checkout');
  const openers = [...document.querySelectorAll('.basket-open')];
  let basket = {};

  try {
    const saved = JSON.parse(localStorage.getItem(key) || '{}');
    for (const [id, count] of Object.entries(saved)) {
      const product = products[Number(id)];
      if (product && /^\d+$/.test(id) && Number.isInteger(count) && count > 0 && count <= 99) {
        basket[id] = count;
      }
    }
  } catch { /* без localStorage работаем из памяти */ }

  const persist = () => {
    try { localStorage.setItem(key, JSON.stringify(basket)); } catch { /* память */ }
  };

  const total = () => Object.values(basket).reduce((sum, count) => sum + count, 0);

  const renderCounters = () => {
    const count = total();
    for (const node of baskets) {
      node.textContent = String(count);
      const holder = node.closest('.cart-button');
      if (holder) holder.setAttribute('aria-label', `Корзина, позиций: ${count}`);
    }
  };

  const change = (id, delta) => {
    if (!products[Number(id)]) return;
    const next = Math.max(0, Math.min(99, (basket[id] || 0) + delta));
    if (next) basket[id] = next; else delete basket[id];
    persist();
    renderBasket();
  };

  function renderBasket() {
    renderCounters();
    if (!drawer) return;
    const entries = Object.entries(basket);
    const count = total();
    if (empty) empty.hidden = count > 0;
    if (checkout) checkout.hidden = count === 0;
    if (!rows) return;
    rows.replaceChildren();
    for (const [id, qty] of entries) {
      const item = products[Number(id)];
      if (!item) continue;
      const row = document.createElement('div');
      row.className = 'basket-row';

      const image = document.createElement('img');
      image.src = imageBase + item[3];
      image.alt = '';
      image.loading = 'lazy';

      const text = document.createElement('div');
      const name = document.createElement('span');
      name.className = 'basket-name';
      name.textContent = item[1];
      const sub = document.createElement('span');
      sub.className = 'basket-sub';
      sub.textContent = [item[2], 'цену уточним по телефону'].join(' · ');
      text.append(name, sub);

      const controls = document.createElement('div');
      controls.className = 'quantity';
      const minus = document.createElement('button');
      minus.type = 'button';
      minus.textContent = '−';
      minus.setAttribute('aria-label', `Убрать одну позицию: ${item[1]}`);
      minus.addEventListener('click', () => change(id, -1));
      const value = document.createElement('span');
      value.textContent = String(qty);
      const plus = document.createElement('button');
      plus.type = 'button';
      plus.textContent = '+';
      plus.disabled = qty >= 99;
      plus.setAttribute('aria-label', `Добавить ещё: ${item[1]}`);
      plus.addEventListener('click', () => change(id, 1));
      controls.append(minus, value, plus);

      row.append(image, text, controls);
      rows.append(row);
    }
  }

  let toastTimer;
  const toast = message => {
    let node = document.querySelector('.toast');
    if (!node) {
      node = document.createElement('div');
      node.className = 'toast';
      node.setAttribute('role', 'status');
      document.body.append(node);
    }
    node.textContent = message;
    node.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => node.classList.remove('show'), 1800);
  };

  const openDrawer = () => {
    if (!drawer) return;
    try {
      if (typeof drawer.showModal === 'function' && !drawer.open) drawer.showModal();
      else drawer.setAttribute('open', '');
    } catch (error) {
      drawer.setAttribute('open', '');
    }
  };
  const closeDrawer = () => {
    if (!drawer) return;
    try {
      if (typeof drawer.close === 'function') drawer.close();
    } catch (error) { /* ниже снимем атрибут */ }
    if (drawer.hasAttribute('open')) drawer.removeAttribute('open');
  };

  if (drawer) {
    for (const button of openers) button.addEventListener('click', openDrawer);
    const closeButton = drawer.querySelector('.basket-close');
    if (closeButton) closeButton.addEventListener('click', closeDrawer);
    drawer.addEventListener('click', event => { if (event.target === drawer) closeDrawer(); });
    renderBasket();
    if (location.hash === '#basket') openDrawer();
  }

  document.addEventListener('click', event => {
    const button = event.target.closest('.add-basket');
    if (!button) return;
    const amount = Number(button.dataset.qty || 1) || 1;
    const id = button.dataset.product;
    for (let step = 0; step < amount; step += 1) change(id, 1);
    const label = button.dataset.label || 'Добавлено в корзину';
    button.classList.add('added');
    const initial = button.textContent;
    button.textContent = 'Добавлено ✓';
    clearTimeout(button.resetTimer);
    button.resetTimer = setTimeout(() => {
      button.classList.remove('added');
      button.textContent = initial;
    }, 1400);
    toast(label);
  });

  /* ---------------------------------------------------------------- счётчик на странице товара */
  const qtyOutput = document.querySelector('#detail-qty');
  if (qtyOutput) {
    const set = delta => {
      const next = Math.max(1, Math.min(99, Number(qtyOutput.textContent || 1) + delta));
      qtyOutput.textContent = String(next);
      document.querySelectorAll('.add-basket[data-qty]').forEach(button => {
        button.dataset.qty = String(next);
        button.dataset.label = `Добавлено: ${next} шт.`;
      });
    };
    document.querySelectorAll('[data-qty-step]').forEach(button => {
      button.addEventListener('click', () => set(Number(button.dataset.qtyStep)));
    });
  }

  /* ---------------------------------------------------------------- полки с прокруткой */
  for (const shelf of document.querySelectorAll('[data-shelf]')) {
    const track = shelf.querySelector('.shelf-track');
    if (!track) continue;
    const prev = shelf.querySelector('[data-shelf-prev]');
    const next = shelf.querySelector('[data-shelf-next]');
    const step = () => Math.max(180, track.clientWidth * 0.8);
    const sync = () => {
      const max = track.scrollWidth - track.clientWidth - 2;
      if (prev) prev.disabled = track.scrollLeft <= 2;
      if (next) next.disabled = track.scrollLeft >= max;
    };
    if (prev) prev.addEventListener('click', () => track.scrollBy({ left: -step(), behavior: 'smooth' }));
    if (next) next.addEventListener('click', () => track.scrollBy({ left: step(), behavior: 'smooth' }));
    track.addEventListener('scroll', sync, { passive: true });
    window.addEventListener('resize', sync);
    sync();
  }

  /* ---------------------------------------------------------------- мобильное меню */
  const burger = document.querySelector('.burger');
  const mobileNav = document.querySelector('.mobile-nav');
  if (burger && mobileNav) {
    burger.addEventListener('click', () => {
      const open = mobileNav.classList.toggle('open');
      burger.setAttribute('aria-expanded', String(open));
    });
  }

  /* ---------------------------------------------------------------- поиск по каталогу */
  const search = document.querySelector('#catalog-search');
  const chips = document.querySelector('#category-chips');
  const grid = document.querySelector('#products');
  if (search && grid) {
    const cards = [...grid.querySelectorAll('article.product')];
    const sections = [...document.querySelectorAll('.catalog-section[data-section]')];
    const emptyHint = document.querySelector('.search-empty');
    let active = 'all';

    const apply = () => {
      const term = search.value.trim().toLocaleLowerCase('ru');
      let shown = 0;
      for (const card of cards) {
        const byCategory = active === 'all' || card.dataset.category === active;
        const byTerm = !term || (card.dataset.search || '').includes(term);
        const visible = byCategory && byTerm;
        card.hidden = !visible;
        if (visible) shown += 1;
      }
      for (const section of sections) {
        const inside = [...section.querySelectorAll('article.product')];
        if (inside.length) section.hidden = !inside.some(card => !card.hidden);
      }
      if (emptyHint) emptyHint.hidden = shown > 0;
    };

    search.addEventListener('input', apply);

    if (chips) {
      chips.addEventListener('click', event => {
        const button = event.target.closest('button[data-category]');
        if (!button) return;
        active = button.dataset.category;
        chips.querySelectorAll('button').forEach(item => {
          item.setAttribute('aria-pressed', String(item === button));
        });
        apply();
      });
    }

    const fromUrl = new URLSearchParams(location.search).get('q');
    if (fromUrl) { search.value = fromUrl; }
    apply();
  }
})();
