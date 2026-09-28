/* Amor Flowers — клиентская логика корзины (localStorage), допродажа,
   плавное появление блоков при скролле. Никакого фреймворка — чистый JS,
   чтобы прототип открывался без сборки. */

(function () {
  "use strict";

  const STORAGE_KEY = "amor_cart_v1";
  const S = window.AMOR.strings;

  const MAX_QTY = 50;   // тот же потолок, что и на сервере

  /*
   * Читает корзину из localStorage и приводит её к пригодному виду.
   *
   * Раньше здесь стоял голый JSON.parse: он ловил только синтаксическую
   * ошибку. Если в хранилище оказывался валидный JSON, но не массив
   * (например `{"a":1}` — после смены формата, из-за расширения браузера
   * или недописанной записи), дальше падало `get(...).reduce is not a
   * function`. Корзина ломалась насмерть: кнопка «В корзину» молча
   * переставала работать, само оно не чинилось, и покупатель не мог
   * оформить заказ, пока вручную не очистит данные сайта. Он просто уходил.
   *
   * Теперь всё, что не проходит проверку, отбрасывается, а хранилище
   * переписывается очищенным значением — корзина чинит себя сама.
   */
  function get() {
    let raw;
    try {
      raw = localStorage.getItem(STORAGE_KEY);
    } catch (e) {
      return [];               // приватный режим Safari запрещает доступ
    }
    if (!raw) return [];

    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch (e) {
      parsed = null;
    }

    if (!Array.isArray(parsed)) {
      try { localStorage.removeItem(STORAGE_KEY); } catch (e) {}
      return [];
    }

    const clean = [];
    for (const item of parsed) {
      if (!item || typeof item !== "object") continue;
      if (item.id === undefined || item.id === null || item.id === "") continue;

      const price = Number(item.price);
      const qty = Math.floor(Number(item.qty));
      // Цена и количество должны быть конечными числами в разумных границах.
      // Сервер всё равно пересчитает цену сам, но показывать покупателю
      // отрицательный или NaN-итог нельзя.
      if (!Number.isFinite(price) || price < 0) continue;
      if (!Number.isFinite(qty) || qty < 1) continue;

      clean.push({
        id: item.id,
        name: String(item.name || ""),
        price: price,
        qty: Math.min(qty, MAX_QTY)
      });
    }

    // Если что-то отбросили или поправили — сразу перезаписываем,
    // чтобы мусор не копился и не всплыл в следующей сессии.
    // Сверяем содержимое, а не длину: обрезка количества длину не меняет.
    const serialized = JSON.stringify(clean);
    if (serialized !== raw) {
      try { localStorage.setItem(STORAGE_KEY, serialized); } catch (e) {}
    }
    return clean;
  }

  function save(items) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    } catch (e) {
      // Переполнение квоты или приватный режим — корзина останется
      // в памяти на время сессии, но заказ оформить всё равно можно.
    }
    updateCount();
  }

  function add(product, qty) {
    qty = Math.floor(Number(qty)) || 1;
    if (qty < 1) qty = 1;
    const items = get();
    const existing = items.find((i) => String(i.id) === String(product.id));
    if (existing) {
      existing.qty = Math.min(existing.qty + qty, MAX_QTY);
    } else {
      items.push({
        id: product.id,
        name: String(product.name || ""),
        price: Number(product.price) || 0,
        qty: Math.min(qty, MAX_QTY)
      });
    }
    save(items);
  }

  function remove(id) {
    save(get().filter((i) => String(i.id) !== String(id)));
  }

  function setQty(id, qty) {
    const items = get();
    const item = items.find((i) => String(i.id) === String(id));
    if (item) {
      const n = Math.floor(Number(qty));
      item.qty = Math.min(Math.max(1, Number.isFinite(n) ? n : 1), MAX_QTY);
      save(items);
    }
  }

  function clear() {
    save([]);
  }

  function total() {
    return get().reduce((sum, i) => sum + i.price * i.qty, 0);
  }

  function count() {
    return get().reduce((sum, i) => sum + i.qty, 0);
  }

  function fmt(n) {
    return n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  }

  function updateCount() {
    const el = document.getElementById("cart-count");
    if (!el) return;
    const c = count();
    el.textContent = c;
    el.hidden = c === 0;
  }

  // ---------------------------------------------------------- cart page

  function renderCartPage() {
    const items = get();
    const emptyEl = document.getElementById("cart-empty");
    const loadedEl = document.getElementById("cart-loaded");
    if (!emptyEl || !loadedEl) return;

    if (!items.length) {
      emptyEl.hidden = false;
      loadedEl.hidden = true;
      return;
    }
    emptyEl.hidden = true;
    loadedEl.hidden = false;

    const rowsEl = document.getElementById("cart-rows");
    rowsEl.innerHTML = items
      .map(
        (i) => `
      <div class="cart-row" data-id="${i.id}">
        <div class="thumb-mini" style="background:linear-gradient(155deg,#f1dedf,#e3b9bd);"></div>
        <div>
          <div class="cart-name">${escapeHtml(i.name)}</div>
          <button class="cart-remove js-remove" data-id="${i.id}">${S.remove}</button>
        </div>
        <div class="qty-stepper">
          <button type="button" class="js-qty-minus" data-id="${i.id}">−</button>
          <span>${i.qty}</span>
          <button type="button" class="js-qty-plus" data-id="${i.id}">+</button>
        </div>
        <div style="font-weight:600;">${fmt(i.price * i.qty)} ${S.currency}</div>
      </div>`
      )
      .join("");

    document.getElementById("summary-count").textContent = count();
    document.getElementById("summary-total").textContent = fmt(total()) + " " + S.currency;

    rowsEl.querySelectorAll(".js-remove").forEach((btn) =>
      btn.addEventListener("click", () => {
        remove(btn.dataset.id);
        renderCartPage();
      })
    );
    rowsEl.querySelectorAll(".js-qty-plus").forEach((btn) =>
      btn.addEventListener("click", () => {
        const item = get().find((i) => String(i.id) === String(btn.dataset.id));
        setQty(btn.dataset.id, item.qty + 1);
        renderCartPage();
      })
    );
    rowsEl.querySelectorAll(".js-qty-minus").forEach((btn) =>
      btn.addEventListener("click", () => {
        const item = get().find((i) => String(i.id) === String(btn.dataset.id));
        setQty(btn.dataset.id, item.qty - 1);
        renderCartPage();
      })
    );
  }

  // ------------------------------------------------------- checkout page

  function renderCheckoutSummary() {
    const items = get();
    const emptyEl = document.getElementById("checkout-empty");
    const layoutEl = document.getElementById("checkout-layout");
    if (!emptyEl || !layoutEl) return;

    if (!items.length) {
      emptyEl.hidden = false;
      layoutEl.hidden = true;
      return;
    }
    emptyEl.hidden = true;
    layoutEl.hidden = false;

    document.getElementById("checkout-summary-rows").innerHTML = items
      .map(
        (i) => `<div class="summary-row"><span>${escapeHtml(i.name)} × ${i.qty}</span><span>${fmt(i.price * i.qty)} ${S.currency}</span></div>`
      )
      .join("");
    document.getElementById("checkout-summary-total").textContent = fmt(total()) + " " + S.currency;
  }

  // ------------------------------------------------------------- addons

  const ADDON_SUGGESTIONS = [
    { id: "addon-card", name: "Открытка ручной работы", price: 1500 },
    { id: "addon-balloon", name: "Шар с гелием и конфетти", price: 4500 },
    { id: "addon-bear", name: "Плюшевый мишка, 40 см", price: 9000 },
  ];

  function showAddonModal() {
    const modal = document.getElementById("addon-modal");
    const list = document.getElementById("addon-list");
    if (!modal || !list) return;
    list.innerHTML = ADDON_SUGGESTIONS.map(
      (a) => `
      <div class="addon-item" data-id="${a.id}">
        <div class="thumb-mini" style="background:linear-gradient(155deg,#f2e3df,#e7cfc7);"></div>
        <div class="addon-name">${a.name}</div>
        <div class="addon-price">${fmt(a.price)} ${S.currency}</div>
        <button class="btn btn-ghost btn-sm js-addon-add" data-id="${a.id}">${S.addToCart}</button>
      </div>`
    ).join("");

    list.querySelectorAll(".js-addon-add").forEach((btn) =>
      btn.addEventListener("click", () => {
        const addon = ADDON_SUGGESTIONS.find((a) => a.id === btn.dataset.id);
        add(addon, 1);
        btn.textContent = "✓";
        btn.disabled = true;
      })
    );
    modal.hidden = false;
  }

  function hideAddonModal() {
    document.getElementById("addon-modal").hidden = true;
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  window.AmorCart = {
    get, add, remove, setQty, clear, total, count,
    renderCartPage, renderCheckoutSummary, showAddonModal, hideAddonModal,
  };

  document.addEventListener("DOMContentLoaded", () => {
    updateCount();

    document.querySelectorAll(".js-add-to-cart").forEach((btn) => {
      if (btn.id === "product-add-btn") return; // handled on product page with qty stepper
      btn.addEventListener("click", () => {
        add({ id: btn.dataset.id, name: btn.dataset.name, price: parseInt(btn.dataset.price, 10) }, 1);
        const original = btn.textContent;
        btn.textContent = "✓";
        setTimeout(() => (btn.textContent = original), 900);
      });
    });

    const addonSkip = document.getElementById("addon-skip");
    if (addonSkip) addonSkip.addEventListener("click", hideAddonModal);
    const addonModal = document.getElementById("addon-modal");
    if (addonModal) {
      addonModal.addEventListener("click", (e) => {
        if (e.target === addonModal) hideAddonModal();
      });
    }

    // ---------------------------------------------------- luxe filter selects
    document.querySelectorAll("[data-luxe-select]").forEach((wrap) => {
      const trigger = wrap.querySelector("[data-luxe-trigger]");
      if (!trigger) return;
      trigger.addEventListener("click", (e) => {
        e.stopPropagation();
        const wasOpen = wrap.classList.contains("is-open");
        document.querySelectorAll("[data-luxe-select].is-open").forEach((el) => el.classList.remove("is-open"));
        if (!wasOpen) wrap.classList.add("is-open");
      });
      const resetBtn = wrap.querySelector("[data-luxe-reset]");
      if (resetBtn) {
        resetBtn.addEventListener("click", () => {
          wrap.querySelectorAll('input[type="checkbox"]').forEach((cb) => (cb.checked = false));
        });
      }
      wrap.querySelector(".luxe-select-panel").addEventListener("click", (e) => e.stopPropagation());
    });
    document.addEventListener("click", () => {
      document.querySelectorAll("[data-luxe-select].is-open").forEach((el) => el.classList.remove("is-open"));
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        document.querySelectorAll("[data-luxe-select].is-open").forEach((el) => el.classList.remove("is-open"));
      }
    });

    // ------------------------------------------------------------ site search
    const searchWidget = document.getElementById("site-search");
    if (searchWidget) {
      const toggleBtn = document.getElementById("search-toggle");
      const input = document.getElementById("search-input");
      const resultsEl = document.getElementById("search-results");
      let debounceTimer = null;

      toggleBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        searchWidget.classList.toggle("is-open");
        if (searchWidget.classList.contains("is-open")) {
          setTimeout(() => input.focus(), 50);
          if (!input.value) resultsEl.innerHTML = `<p class="search-hint">${S.searchHint}</p>`;
        }
      });
      searchWidget.querySelector(".search-flyout").addEventListener("click", (e) => e.stopPropagation());
      document.addEventListener("click", () => searchWidget.classList.remove("is-open"));
      document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") searchWidget.classList.remove("is-open");
      });

      function renderResults(data) {
        if (!data.results.length) {
          resultsEl.innerHTML = `<p class="search-empty">${S.searchNoResults}</p>`;
          return;
        }
        const rows = data.results
          .map(
            (r) => `
          <a class="search-result-row" href="${r.url}">
            <span class="search-result-thumb" style="background:linear-gradient(155deg,#f1dedf,#e3b9bd);"></span>
            <span>
              <span class="search-result-name">${escapeHtml(r.name)}</span><br>
              <span class="search-result-price">${fmt(r.price)} ${S.currency}${r.is_test_price ? " · тест" : ""}</span>
            </span>
          </a>`
          )
          .join("");
        resultsEl.innerHTML = rows + `<a class="search-show-all" href="${data.show_all_url}">${S.searchShowAll}</a>`;
      }

      input.addEventListener("input", () => {
        const q = input.value.trim();
        clearTimeout(debounceTimer);
        if (q.length < 2) {
          resultsEl.innerHTML = `<p class="search-hint">${S.searchHint}</p>`;
          return;
        }
        debounceTimer = setTimeout(() => {
          fetch(`${window.AMOR.searchUrl}?q=${encodeURIComponent(q)}`)
            .then((r) => r.json())
            .then(renderResults)
            .catch(() => {});
        }, 250);
      });
    }

    // reveal-on-scroll
    if ("IntersectionObserver" in window) {
      const io = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              entry.target.classList.add("is-visible");
              io.unobserve(entry.target);
            }
          });
        },
        { threshold: 0.12 }
      );
      document.querySelectorAll(".reveal").forEach((el) => io.observe(el));
    } else {
      document.querySelectorAll(".reveal").forEach((el) => el.classList.add("is-visible"));
    }
  });
})();

/* --------------------------------------------------------------------------
   Телефонные поля: всегда начинаются с +7 и не дают его стереть.
   Раньше человек вводил номер как угодно (8707…, 707…), сервер это чинил,
   но пользователь не понимал, какой формат от него ждут.
   -------------------------------------------------------------------------- */
(function () {
  var fields = document.querySelectorAll('.js-phone');
  if (!fields.length) return;

  function format(digits) {
    // digits — только цифры без ведущей 7
    var out = '+7';
    if (digits.length) out += ' ' + digits.slice(0, 3);
    if (digits.length > 3) out += ' ' + digits.slice(3, 6);
    if (digits.length > 6) out += ' ' + digits.slice(6, 8);
    if (digits.length > 8) out += ' ' + digits.slice(8, 10);
    return out;
  }

  function normalize(raw) {
    var d = (raw || '').replace(/\D/g, '');
    if (d.charAt(0) === '8') d = '7' + d.slice(1);   // 8707… -> 7707…
    if (d.charAt(0) === '7') d = d.slice(1);          // убираем код страны
    return d.slice(0, 10);
  }

  fields.forEach(function (el) {
    if (!el.value || el.value.replace(/\D/g, '') === '') el.value = '+7 ';

    el.addEventListener('focus', function () {
      if (!el.value.trim() || el.value.trim() === '+7') el.value = '+7 ';
      // курсор всегда после кода страны
      requestAnimationFrame(function () {
        var end = el.value.length;
        try { el.setSelectionRange(end, end); } catch (e) {}
      });
    });

    el.addEventListener('input', function () {
      el.value = format(normalize(el.value));
    });

    // Backspace не должен съедать «+7»
    el.addEventListener('keydown', function (e) {
      if (e.key === 'Backspace' && el.value.replace(/\D/g, '').length <= 1) {
        e.preventDefault();
        el.value = '+7 ';
      }
    });
  });
})();

/* --------------------------------------------------------------------------
   Нижняя навигация: светящийся маячок едет к активной вкладке.
   Ширину не подгоняем под вкладку — маячок фиксированный и центрируется
   по иконке, так он читается как источник света, а не как подложка.
   -------------------------------------------------------------------------- */
(function () {
  var bar = document.getElementById('tabbar');
  var pill = document.getElementById('tab-pill');
  if (!bar || !pill) return;

  var row = bar.querySelector('.tabbar-row');

  function place(el, animate) {
    if (!el || !row) return;
    var r = el.getBoundingClientRect();
    var rowRect = row.getBoundingClientRect();
    if (!r.width) return;
    if (!animate) pill.style.transition = 'none';
    pill.style.width = r.width + 'px';
    pill.style.transform = 'translateX(' + (r.left - rowRect.left) + 'px)';
    if (!animate) { void pill.offsetWidth; pill.style.transition = ''; }
    pill.classList.add('ready');
  }

  function current() {
    return bar.querySelector('.tab.active') || bar.querySelector('.tab');
  }

  place(current(), false);
  window.addEventListener('resize', function () { place(current(), false); });
  window.addEventListener('orientationchange', function () {
    setTimeout(function () { place(current(), false); }, 250);
  });

  bar.querySelectorAll('.tab').forEach(function (tab) {
    tab.addEventListener('pointerdown', function () { place(tab, true); });
  });
})();



/* --------------------------------------------------------------------------
   Одноразовый код: запрос и проверка. Работает и на регистрации,
   и на восстановлении пароля — различаются только идентификаторы полей.
   -------------------------------------------------------------------------- */
(function () {
  function csrf(form) {
    var el = form && form.querySelector('input[name="_csrf"]');
    return el ? el.value : '';
  }

  function contactFields(form, extra) {
    // Канал выбирает сервер; шлём то поле, которое есть в форме.
    var email = form.querySelector('input[name="email"]');
    var phone = form.querySelector('input[name="phone"]');
    if (email && email.value) extra.email = email.value;
    if (phone && phone.value) extra.phone = phone.value;
    return extra;
  }

  function post(url, data) {
    return fetch(url, {
      method: 'POST',
      headers: {'Content-Type': 'application/x-www-form-urlencoded'},
      body: new URLSearchParams(data)
    }).then(function (r) { return r.json(); });
  }

  // --- регистрация ---
  var box = document.getElementById('otp-box');
  if (box) {
    var form = box.closest('form');
    var phone = form.querySelector('.js-phone');
    var hint = document.getElementById('otp-hint');
    var codeBox = document.getElementById('otp-code-box');
    var codeInput = document.getElementById('otp-code');
    var sendBtn = document.getElementById('otp-send');
    var checkBtn = document.getElementById('otp-check');

    post('/account/verify/send', {_csrf: csrf(form), phone: '+7 700 000 00 00', email: 'probe@example.com', probe: 1})
      .then(function (d) { if (d && d.enabled) box.hidden = false; })
      .catch(function () {});

    sendBtn.addEventListener('click', function () {
      hint.textContent = 'Отправляем код…';
      post('/account/verify/send', contactFields(form, {_csrf: csrf(form), purpose: 'register'}))
        .then(function (d) {
          if (d.error) { hint.textContent = d.error; return; }
          hint.textContent = 'Код отправлен в ' + (d.channel || 'сообщение') + '. Введите его ниже.';
          codeBox.hidden = false;
          codeInput.focus();
        });
    });

    checkBtn.addEventListener('click', function () {
      hint.textContent = 'Проверяем…';
      post('/account/verify/check', contactFields(form, {_csrf: csrf(form),
                                     code: codeInput.value, purpose: 'register'}))
        .then(function (d) {
          if (d.verified) {
            hint.textContent = 'Номер подтверждён ✓';
            sendBtn.disabled = true; checkBtn.disabled = true; codeInput.disabled = true;
          } else {
            hint.textContent = d.error || 'Неверный код.';
          }
        });
    });
  }

  // --- восстановление пароля ---
  var fSend = document.getElementById('forgot-send');
  if (fSend) {
    var fForm = fSend.closest('form');
    var fPhone = document.getElementById('forgot-phone');
    var fHint = document.getElementById('forgot-hint');
    fSend.addEventListener('click', function () {
      fHint.textContent = 'Отправляем код…';
      post('/account/verify/send', contactFields(fForm, {_csrf: csrf(fForm), purpose: 'reset'}))
        .then(function (d) {
          fHint.textContent = d.error ? d.error
            : 'Если номер зарегистрирован, код придёт в ' + (d.channel || 'сообщение') + '.';
        });
    });
  }
})();

/* --------------------------------------------------------------------------
   Уведомление о cookie. Показывается один раз — согласие запоминаем
   в localStorage, чтобы не мозолить глаза постоянным посетителям.
   -------------------------------------------------------------------------- */
(function () {
  var note = document.getElementById('cookie-note');
  if (!note) return;
  var KEY = 'af_cookie_ok';
  try { if (localStorage.getItem(KEY)) return; } catch (e) {}

  setTimeout(function () { note.hidden = false; }, 1200);

  var btn = document.getElementById('cookie-ok');
  if (btn) btn.addEventListener('click', function () {
    note.hidden = true;
    try { localStorage.setItem(KEY, '1'); } catch (e) {}
  });
})();
