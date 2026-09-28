/* =========================================================================
   Amor Flowers — ads.js
   Слой измерения для Google Ads + GA4.

   Что делает:
     1. Consent Mode v2 — согласие ДО загрузки gtag (иначе Ads режет данные
        по ЕЭЗ, а с 2024 без этого часть конверсий вообще не учитывается).
     2. Захват gclid / gbraid / wbraid из URL в cookie на 90 дней —
        без этого офлайн-конверсии из CRM невозможно привязать к клику.
     3. Товарные события GA4: view_item, add_to_cart, begin_checkout,
        purchase, generate_lead.
     4. Enhanced conversions — телефон/почта в SHA-256, не в открытом виде.
     5. Дублирование ключевых событий на сервер (/api/track), чтобы
        блокировщики и iOS ITP не съедали конверсии целиком.

   Конфиг приходит из base.html в window.AMOR_ADS.
   Пока ID не заданы — модуль работает вхолостую и ничего не грузит.
   ========================================================================= */
(function () {
  "use strict";

  var CFG = window.AMOR_ADS || {};
  var HAS_ADS = !!CFG.awId;      // AW-XXXXXXXXX
  var HAS_GA4 = !!CFG.ga4Id;     // G-XXXXXXXXXX

  /* ------------------------------------------------------------------
     1. Consent Mode v2 — ставится ПЕРВЫМ, до любого хита
     ------------------------------------------------------------------ */
  window.dataLayer = window.dataLayer || [];
  function gtag() { window.dataLayer.push(arguments); }
  window.gtag = window.gtag || gtag;

  var CONSENT_KEY = "amor_consent_v1";

  function storedConsent() {
    try { return JSON.parse(localStorage.getItem(CONSENT_KEY)); }
    catch (e) { return null; }
  }

  var saved = storedConsent();

  gtag("consent", "default", {
    ad_storage: "denied",
    ad_user_data: "denied",
    ad_personalization: "denied",
    analytics_storage: "denied",
    functionality_storage: "granted",
    security_storage: "granted",
    wait_for_update: 500
  });

  if (saved && saved.granted) {
    gtag("consent", "update", {
      ad_storage: "granted",
      ad_user_data: "granted",
      ad_personalization: "granted",
      analytics_storage: "granted"
    });
  }

  window.amorGrantConsent = function () {
    try { localStorage.setItem(CONSENT_KEY, JSON.stringify({ granted: true, at: Date.now() })); } catch (e) {}
    gtag("consent", "update", {
      ad_storage: "granted",
      ad_user_data: "granted",
      ad_personalization: "granted",
      analytics_storage: "granted"
    });
  };

  /* ------------------------------------------------------------------
     2. Захват идентификаторов клика.
        gclid  — обычные клики
        gbraid — iOS, web-to-app
        wbraid — iOS, app-to-web
        Живут 90 дней: окно атрибуции Google Ads по умолчанию.
     ------------------------------------------------------------------ */
  var CLICK_KEYS = ["gclid", "gbraid", "wbraid"];

  function setCookie(name, value, days) {
    var d = new Date();
    d.setTime(d.getTime() + days * 864e5);
    document.cookie = name + "=" + encodeURIComponent(value) +
      ";expires=" + d.toUTCString() + ";path=/;SameSite=Lax";
  }

  function getCookie(name) {
    var m = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return m ? decodeURIComponent(m.pop()) : "";
  }

  function captureClickIds() {
    var params = new URLSearchParams(window.location.search);
    CLICK_KEYS.forEach(function (k) {
      var v = params.get(k);
      if (v) {
        setCookie("amor_" + k, v, 90);
        setCookie("amor_click_at", String(Date.now()), 90);
      }
    });
    // utm-метки тоже сохраняем — по ним видно кампанию в CRM
    ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"].forEach(function (k) {
      var v = params.get(k);
      if (v) setCookie("amor_" + k, v, 90);
    });
  }

  function clickContext() {
    var ctx = {};
    CLICK_KEYS.concat(["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"])
      .forEach(function (k) {
        var v = getCookie("amor_" + k);
        if (v) ctx[k] = v;
      });
    return ctx;
  }

  /* ------------------------------------------------------------------
     3. Загрузка gtag.js
     ------------------------------------------------------------------ */
  function loadGtag() {
    if (!HAS_ADS && !HAS_GA4) return;
    var id = CFG.ga4Id || CFG.awId;
    var s = document.createElement("script");
    s.async = true;
    s.src = "https://www.googletagmanager.com/gtag/js?id=" + encodeURIComponent(id);
    document.head.appendChild(s);

    gtag("js", new Date());
    if (HAS_GA4) gtag("config", CFG.ga4Id, { currency: "KZT", send_page_view: true });
    if (HAS_ADS) {
      gtag("config", CFG.awId, {
        allow_enhanced_conversions: true,
        // Отсчёт окна атрибуции ведём от клика, а не от сессии
        conversion_linker: true
      });
    }
  }

  /* ------------------------------------------------------------------
     4. Enhanced conversions — хэшируем на клиенте, сырое не отправляем
     ------------------------------------------------------------------ */
  function normalizePhone(raw) {
    var d = String(raw || "").replace(/\D/g, "");
    if (!d) return "";
    if (d.length === 10) d = "7" + d;                 // 7071234567
    if (d.length === 11 && d[0] === "8") d = "7" + d.slice(1);
    return "+" + d;                                    // E.164
  }

  function sha256(text) {
    if (!window.crypto || !window.crypto.subtle) return Promise.resolve("");
    var buf = new TextEncoder().encode(String(text).trim().toLowerCase());
    return window.crypto.subtle.digest("SHA-256", buf).then(function (h) {
      return Array.prototype.map.call(new Uint8Array(h), function (b) {
        return b.toString(16).padStart(2, "0");
      }).join("");
    });
  }

  function setUserData(user) {
    if (!HAS_ADS || !user) return Promise.resolve();
    var jobs = [];
    var out = {};
    if (user.email) jobs.push(sha256(user.email).then(function (h) { if (h) out.sha256_email_address = h; }));
    if (user.phone) jobs.push(sha256(normalizePhone(user.phone)).then(function (h) { if (h) out.sha256_phone_number = h; }));
    return Promise.all(jobs).then(function () {
      if (Object.keys(out).length) gtag("set", "user_data", out);
    });
  }

  /* ------------------------------------------------------------------
     5. Серверное дублирование — блокировщики режут клиентские хиты
     ------------------------------------------------------------------ */
  function serverTrack(name, payload) {
    if (!CFG.trackUrl) return;
    var body = JSON.stringify({
      event: name,
      payload: payload || {},
      click: clickContext(),
      page: location.pathname,
      ts: Date.now()
    });
    try {
      if (navigator.sendBeacon) {
        navigator.sendBeacon(CFG.trackUrl, new Blob([body], { type: "application/json" }));
      } else {
        fetch(CFG.trackUrl, { method: "POST", headers: { "Content-Type": "application/json" }, body: body, keepalive: true });
      }
    } catch (e) {}
  }

  /* ------------------------------------------------------------------
     6. Публичное API событий
     ------------------------------------------------------------------ */
  var Ads = {
    viewItem: function (item) {
      gtag("event", "view_item", {
        currency: "KZT",
        value: item.price,
        items: [{ item_id: item.id, item_name: item.name, price: item.price, quantity: 1 }]
      });
    },

    addToCart: function (item, qty) {
      var payload = {
        currency: "KZT",
        value: item.price * (qty || 1),
        items: [{ item_id: item.id, item_name: item.name, price: item.price, quantity: qty || 1 }]
      };
      gtag("event", "add_to_cart", payload);
      serverTrack("add_to_cart", payload);
    },

    beginCheckout: function (items, total) {
      var payload = { currency: "KZT", value: total, items: items };
      gtag("event", "begin_checkout", payload);
      serverTrack("begin_checkout", payload);
    },

    /* Главная конверсия. Оплата подтверждается на сервере — здесь
       только клиентский дубль для быстрой атрибуции. */
    purchase: function (order) {
      var run = function () {
        var payload = {
          transaction_id: order.id,
          currency: "KZT",
          value: order.total,
          items: order.items || []
        };
        gtag("event", "purchase", payload);
        if (HAS_ADS && CFG.labelPurchase) {
          gtag("event", "conversion", {
            send_to: CFG.awId + "/" + CFG.labelPurchase,
            transaction_id: order.id,
            value: order.total,
            currency: "KZT"
          });
        }
        serverTrack("purchase", payload);
      };
      setUserData(order.user).then(run, run);
    },

    /* Клик в WhatsApp = лид. Для круглосуточной доставки это часто
       главное действие: заказ уходит в мессенджер, а не через корзину. */
    lead: function (source) {
      gtag("event", "generate_lead", { method: source || "whatsapp", currency: "KZT" });
      if (HAS_ADS && CFG.labelLead) {
        gtag("event", "conversion", { send_to: CFG.awId + "/" + CFG.labelLead });
      }
      serverTrack("generate_lead", { method: source || "whatsapp" });
    },

    clickContext: clickContext,
    normalizePhone: normalizePhone
  };

  /* Автоподхват кликов, размеченных в шаблонах через data-ads-lead */
  document.addEventListener("click", function (e) {
    var el = e.target.closest("[data-ads-lead]");
    if (el) Ads.lead(el.getAttribute("data-ads-lead"));
  }, { passive: true });

  captureClickIds();
  loadGtag();
  window.AmorAds = Ads;
})();
