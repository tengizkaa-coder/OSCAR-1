/* Catalogue pages, category pages and product pages:
   client-side search filter + basket list kept in localStorage on this device.
   The basket never sends an order anywhere; checkout is a tel: link. */
(() => {
  const root = document.documentElement;
  const site = root.dataset.site;
  const imageBase = root.dataset.imageBase || '';
  const products = window.SITE_PRODUCTS;
  if (!site || !Array.isArray(products)) return;
  const key = `selection-${site}-v1`;
  let basket = {};
  try {
    const saved = JSON.parse(localStorage.getItem(key) || '{}');
    for (const [id, count] of Object.entries(saved)) {
      if (/^\d+$/.test(id) && products[Number(id)] && Number.isInteger(count) && count > 0 && count <= 99) basket[id] = count;
    }
  } catch { /* In-memory fallback if storage is unavailable. */ }

  const countEl = document.querySelector('.basket-count');
  const float = document.querySelector('.basket-float');
  const dialog = document.querySelector('.basket-dialog');
  const rows = document.querySelector('.basket-items');
  const empty = document.querySelector('.basket-empty');
  const checkout = document.querySelector('.basket-checkout');

  if (countEl && float && dialog && rows && empty && checkout) {
    const render = () => {
      const entries = Object.entries(basket);
      const count = entries.reduce((sum, [, qty]) => sum + qty, 0);
      countEl.textContent = String(count);
      float.hidden = count === 0;
      float.textContent = `Корзина · ${count} →`;
      empty.hidden = count > 0;
      checkout.hidden = count === 0;
      rows.replaceChildren();
      for (const [id, qty] of entries) {
        const item = products[Number(id)];
        const row = document.createElement('div'); row.className = 'basket-row';
        const image = document.createElement('img'); image.src = imageBase + item[3]; image.alt = '';
        const name = document.createElement('span'); name.className = 'basket-name'; name.textContent = `${item[1]} · ${item[2]}`;
        const controls = document.createElement('div'); controls.className = 'quantity';
        const minus = document.createElement('button'); minus.type = 'button'; minus.textContent = '−'; minus.setAttribute('aria-label', `Уменьшить количество: ${item[1]}`); minus.addEventListener('click', () => change(id, -1));
        const number = document.createElement('span'); number.textContent = String(qty);
        const plus = document.createElement('button'); plus.type = 'button'; plus.textContent = '+'; plus.disabled = qty >= 99; plus.setAttribute('aria-label', `Увеличить количество: ${item[1]}`); plus.addEventListener('click', () => change(id, 1));
        controls.append(minus, number, plus); row.append(image, name, controls); rows.append(row);
      }
    };
    const change = (id, delta) => {
      if (!products[Number(id)]) return;
      const count = Math.max(0, Math.min(99, (basket[id] || 0) + delta));
      if (count) basket[id] = count; else delete basket[id];
      try { localStorage.setItem(key, JSON.stringify(basket)); } catch { /* In-memory fallback. */ }
      render();
    };
    document.querySelectorAll('.add-basket').forEach(button => button.addEventListener('click', () => {
      change(button.dataset.product, 1);
      button.textContent = 'Добавлено ✓';
      clearTimeout(button.resetTimer);
      button.resetTimer = setTimeout(() => { button.textContent = 'В корзину'; }, 1200);
    }));
    const open = () => { if (!dialog.open) typeof dialog.showModal === 'function' ? dialog.showModal() : dialog.setAttribute('open', ''); };
    const close = () => { typeof dialog.close === 'function' ? dialog.close() : dialog.removeAttribute('open'); };
    const openBtn = document.querySelector('.basket-open');
    if (openBtn) openBtn.addEventListener('click', open);
    float.addEventListener('click', open);
    const closeBtn = document.querySelector('.basket-close');
    if (closeBtn) closeBtn.addEventListener('click', close);
    render();
    if (location.hash === '#basket') open();
  }

  const search = document.querySelector('#expanded-search');
  if (search) search.addEventListener('input', () => {
    const term = search.value.trim().toLocaleLowerCase('ru');
    let count = 0;
    document.querySelectorAll('.expanded-product').forEach(card => {
      card.hidden = !card.dataset.search.includes(term);
      if (!card.hidden) count++;
    });
    document.querySelectorAll('.catalog-section').forEach(section => { section.hidden = !section.querySelector('.expanded-product:not([hidden])'); });
    const emptyMsg = document.querySelector('.search-empty');
    if (emptyMsg) emptyMsg.hidden = count > 0;
  });
})();
