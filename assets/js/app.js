/* Главная: фильтры по категориям и поиск по уже отрисованным карточкам.
   Карточки, номера и подписи приходят из HTML, поэтому каталог виден и без JavaScript:
   скрипт только скрывает лишнее и перенумеровывает видимые позиции. */
(() => {
  const grid = document.getElementById('products');
  const filters = document.getElementById('filters');
  const search = document.getElementById('search');
  const empty = document.getElementById('empty');
  if (!grid || !filters || !search || !empty) return;

  const cards = [...grid.querySelectorAll('article.product')].map(element => ({
    element,
    category: element.dataset.category || '',
    terms: (element.dataset.search || '').toLocaleLowerCase('ru'),
    number: element.querySelector('.product-number'),
  }));
  let active = 'all';

  const apply = () => {
    const query = search.value.trim().toLocaleLowerCase('ru');
    let shown = 0;
    for (const card of cards) {
      const matchesCategory = active === 'all' || card.category === active;
      const matchesQuery = !query || card.terms.includes(query);
      const visible = matchesCategory && matchesQuery;
      card.element.hidden = !visible;
      if (visible) {
        shown += 1;
        if (card.number) card.number.textContent = String(shown).padStart(2, '0');
      }
    }
    empty.hidden = shown !== 0;
    grid.setAttribute('data-visible', String(shown));
  };

  filters.addEventListener('click', event => {
    const button = event.target.closest('button[data-category]');
    if (!button) return;
    active = button.dataset.category;
    filters.querySelectorAll('button').forEach(item => {
      item.setAttribute('aria-pressed', String(item === button));
    });
    apply();
  });

  search.addEventListener('input', apply);
  apply();
})();
