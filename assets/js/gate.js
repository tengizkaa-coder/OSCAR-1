/* Client-side access rules copied from the main site (АЛКО МСК) and adapted for АЛКО НОЧЬ.
   This is NOT security: user-agent and referrer can be forged, and a real visitor
   without a referrer can be blocked. It only reduces casual direct/desktop visits.
   Rules:
   - /test/ (the whole test tree) is always open.
   - Search engine robots are allowed, otherwise the site can never be indexed.
   - Mobile visitors are allowed after a click from Google/Yandex/Bing, and then
     may navigate inside the site in the same tab (sessionStorage flag).
   - Everything else gets a white screen; on mobile only a short error text is shown. */
(function () {
  var root = document.documentElement;
  var ua = navigator.userAgent || '';
  var bot = /Googlebot|Googlebot-Image|Google-InspectionTool|GoogleOther|AdsBot-Google|Mediapartners-Google|Storebot-Google|YandexBot|YandexMobileBot|YandexAccessibilityBot|YandexMetrika|YandexWebmaster|YandexImages|YandexVideo|Bingbot|DuckDuckBot|Applebot|Slurp|Mail\.RU_Bot/i.test(ua);
  var phone = /Android.+Mobile|iPhone|iPod|Windows Phone|Mobile Safari|Mobile/i.test(ua) && !/iPad|Tablet/i.test(ua);
  var preview = /(^|\/)test(\/|$)/i.test(location.pathname) || /\/test\.html$/i.test(location.pathname);
  var search = false;
  var sameSite = false;
  var authorized = false;
  try {
    var ref = new URL(document.referrer);
    var host = ref.hostname.toLowerCase();
    search = /(^|\.)(google\.[a-z.]+|yandex\.[a-z.]+|ya\.ru|bing\.com|duckduckgo\.com|mail\.ru|go\.mail\.ru)$/.test(host) ||
      /^(www\.)?(maps\.google|yandex|m\.yandex)\./.test(host);
    sameSite = ref.origin === location.origin;
  } catch (e) { /* no usable referrer */ }
  try { authorized = sessionStorage.getItem('alkonoch-search-entry') === '1'; } catch (e) {}
  if (phone && search) {
    try { sessionStorage.setItem('alkonoch-search-entry', '1'); } catch (e) {}
  }
  if (preview || bot || (phone && (search || (sameSite && authorized)))) {
    root.setAttribute('data-access', 'allowed');
    return;
  }
  root.setAttribute('data-blocked', '1');
  document.addEventListener('DOMContentLoaded', function () {
    var box = document.createElement('div');
    box.id = 'blocked';
    if (phone) box.textContent = 'Ошибка загрузки страницы.';
    document.body.appendChild(box);
  });
})();
