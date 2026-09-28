/* =========================================================================
   Amor Flowers — fluid.js
   Движение по модели Apple «Designing Fluid Interfaces»:
   пружины вместо фиксированных длительностей, передача скорости пальца
   в анимацию, проекция инерции, прерываемость в любой момент,
   резиновые границы. Без зависимостей — только rAF и Pointer Events.
   ========================================================================= */
(function () {
  "use strict";

  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------------------------------------------------------------------
     1. Пружина. Два параметра, как у Apple: damping (перелёт) и response
        (скорость достижения цели в секундах). Не «длительность» —
        время затухания вытекает из физики.
        Ключевое: анимация всегда стартует от ТЕКУЩЕГО экранного значения
        и несёт текущую скорость, поэтому её можно перехватить на лету.
     --------------------------------------------------------------------- */
  function Spring(opts) {
    opts = opts || {};
    this.damping = opts.damping == null ? 1.0 : opts.damping;
    this.response = opts.response == null ? 0.4 : opts.response;
    this.value = opts.from || 0;
    this.target = opts.from || 0;
    this.velocity = 0;
    this.onUpdate = opts.onUpdate || function () {};
    this.onRest = opts.onRest || function () {};
    this._raf = null;
    this._last = 0;
  }

  Spring.prototype.setTarget = function (target, velocity) {
    this.target = target;
    // Перенацеливание НЕ обнуляет скорость — иначе на развороте жеста
    // возникает разрыв скорости, «кирпичная стена» (§3).
    if (velocity != null) this.velocity = velocity;
    this._start();
  };

  Spring.prototype.set = function (value) {
    this.stop();
    this.value = this.target = value;
    this.velocity = 0;
    this.onUpdate(value);
  };

  Spring.prototype.stop = function () {
    if (this._raf) cancelAnimationFrame(this._raf);
    this._raf = null;
  };

  Spring.prototype._start = function () {
    if (this._raf) return;
    this._last = performance.now();
    var self = this;
    var tick = function (now) {
      var dt = Math.min((now - self._last) / 1000, 1 / 30); // клип на лаг вкладки
      self._last = now;

      var omega = (2 * Math.PI) / self.response;   // собственная частота
      var zeta = self.damping;
      var x = self.value - self.target;
      // Полуявный Эйлер: устойчив и дёшев, точности для UI достаточно
      var accel = -omega * omega * x - 2 * zeta * omega * self.velocity;
      self.velocity += accel * dt;
      self.value += self.velocity * dt;

      self.onUpdate(self.value);

      if (Math.abs(self.value - self.target) < 0.05 && Math.abs(self.velocity) < 0.05) {
        self.value = self.target;
        self.velocity = 0;
        self.onUpdate(self.value);
        self._raf = null;
        self.onRest();
        return;
      }
      self._raf = requestAnimationFrame(tick);
    };
    this._raf = requestAnimationFrame(tick);
  };

  /* ---------------------------------------------------------------------
     2. Проекция инерции — точная функция Apple из сэмпла Fluid Interfaces.
        Не v²/2a из учебника: там экспоненциальное затухание.
     --------------------------------------------------------------------- */
  function project(velocity, decelerationRate) {
    var d = decelerationRate == null ? 0.998 : decelerationRate;
    return (velocity / 1000) * d / (1 - d);
  }

  /* ---------------------------------------------------------------------
     3. Резиновая граница — сопротивление растёт с выходом за край (§9)
     --------------------------------------------------------------------- */
  function rubberband(overshoot, dimension, constant) {
    var c = constant == null ? 0.55 : constant;
    return (overshoot * dimension * c) / (dimension + c * Math.abs(overshoot));
  }

  /* ---------------------------------------------------------------------
     4. Трекер скорости: история последних точек, а не одна дельта.
        Скорость по одному кадру шумит и врёт на паузе перед отпусканием.
     --------------------------------------------------------------------- */
  function Tracker() {
    this.points = [];
  }
  Tracker.prototype.add = function (pos) {
    var now = performance.now();
    this.points.push({ pos: pos, t: now });
    while (this.points.length > 6) this.points.shift();
  };
  Tracker.prototype.velocity = function () {
    var pts = this.points;
    if (pts.length < 2) return 0;
    var last = pts[pts.length - 1];
    var first = pts[0];
    // Точки старше 100 мс игнорируем: палец мог замереть перед отпусканием
    for (var i = pts.length - 1; i >= 0; i--) {
      if (last.t - pts[i].t <= 100) first = pts[i];
    }
    var dt = (last.t - first.t) / 1000;
    if (dt <= 0) return 0;
    return (last.pos - first.pos) / dt;   // px/s
  };
  Tracker.prototype.reset = function () { this.points = []; };

  /* =====================================================================
     Отклик на нажатие: подсветка на pointer-DOWN, не на click (§1).
     Отменяется, если палец ушёл с элемента — и возвращается, если вернулся.
     ===================================================================== */
  function pressFeedback() {
    var SEL = ".btn, .tab, .icon-btn, .product-card, .category-tile, .sheet-link, .filter-chip, .quicknav-item";
    document.querySelectorAll(SEL).forEach(function (el) {
      el.setAttribute("data-press", "");
    });

    document.addEventListener("pointerdown", function (e) {
      var el = e.target.closest("[data-press]");
      if (el) el.setAttribute("data-pressed", "1");
    }, { passive: true });

    ["pointerup", "pointercancel", "pointerleave"].forEach(function (evt) {
      document.addEventListener(evt, function () {
        document.querySelectorAll('[data-pressed="1"]').forEach(function (el) {
          el.removeAttribute("data-pressed");
        });
      }, { passive: true });
    });

    document.addEventListener("pointermove", function (e) {
      var pressed = document.querySelector('[data-pressed="1"]');
      if (!pressed) return;
      var under = document.elementFromPoint(e.clientX, e.clientY);
      if (!under || !pressed.contains(under)) pressed.removeAttribute("data-pressed");
    }, { passive: true });
  }

  /* =====================================================================
     Хедер: уплотняется, когда под него заезжает контент (scroll edge effect)
     ===================================================================== */
  function headerMaterial() {
    var header = document.querySelector(".site-header");
    if (!header) return;
    var ticking = false;
    function update() {
      header.setAttribute("data-scrolled", window.scrollY > 8 ? "1" : "0");
      ticking = false;
    }
    update();
    window.addEventListener("scroll", function () {
      if (!ticking) { ticking = true; requestAnimationFrame(update); }
    }, { passive: true });
  }

  /* =====================================================================
     Reveal-on-scroll со страховкой.
     Раньше .reveal { opacity: 0 } жил в CSS: если наблюдатель не срабатывал,
     посетитель видел пустую страницу. Теперь скрытие включает сам JS,
     и есть таймер, который принудительно всё показывает.
     ===================================================================== */
  function reveal() {
    var nodes = document.querySelectorAll(".reveal");
    if (!nodes.length) return;

    function showAll() {
      document.querySelectorAll(".reveal").forEach(function (el) {
        el.classList.add("is-visible");
      });
    }

    if (reduced || !("IntersectionObserver" in window)) { showAll(); return; }

    document.documentElement.classList.add("js-fluid");

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        var el = entry.target;
        // Каскад внутри одной группы: соседи проявляются со сдвигом,
        // но сдвиг маленький — это подсказка порядка, а не шоу.
        var sibs = Array.prototype.slice.call(el.parentNode.children).indexOf(el);
        el.style.transitionDelay = Math.min(sibs, 5) * 45 + "ms";
        el.classList.add("is-visible");
        io.unobserve(el);
      });
    }, { threshold: 0.08, rootMargin: "0px 0px -6% 0px" });

    nodes.forEach(function (el) { io.observe(el); });

    // Страховка: что бы ни случилось с наблюдателем — контент виден
    setTimeout(showAll, 2500);
    window.addEventListener("load", function () { setTimeout(showAll, 800); });
  }

  /* =====================================================================
     Инерционная лента (Instagram/Telegram-подобное перелистывание).
     Тянется 1:1 за пальцем, на отпускании проецирует инерцию и
     доводит пружиной до ближайшей карточки. Прерывается в любой момент.
     ===================================================================== */
  function railify(rail) {
    var tracker = new Tracker();
    var dragging = false;
    var startX = 0;
    var startScroll = 0;
    var moved = 0;
    var pointerId = null;

    var spring = new Spring({
      damping: 0.86,          // лёгкий перелёт — жест нёс инерцию (§4)
      response: 0.42,
      onUpdate: function (v) { rail.scrollLeft = v; }
    });

    function maxScroll() { return rail.scrollWidth - rail.clientWidth; }

    function snapPoints() {
      var pts = [];
      Array.prototype.forEach.call(rail.children, function (child) {
        pts.push(child.offsetLeft - rail.offsetLeft);
      });
      return pts;
    }

    function nearest(value) {
      var pts = snapPoints();
      var best = pts[0] || 0;
      var bestD = Infinity;
      pts.forEach(function (p) {
        var d = Math.abs(p - value);
        if (d < bestD) { bestD = d; best = p; }
      });
      return Math.max(0, Math.min(best, maxScroll()));
    }

    rail.addEventListener("pointerdown", function (e) {
      if (e.pointerType === "touch") return;  // тач отдаём нативному скроллу iOS
      spring.stop();                          // перехват на лету, без прыжка
      dragging = true;
      moved = 0;
      pointerId = e.pointerId;
      startX = e.clientX;
      startScroll = rail.scrollLeft;
      tracker.reset();
      tracker.add(e.clientX);
      rail.setPointerCapture(e.pointerId);
      rail.setAttribute("data-dragging", "1");
    });

    rail.addEventListener("pointermove", function (e) {
      if (!dragging || e.pointerId !== pointerId) return;
      var dx = e.clientX - startX;
      moved = Math.abs(dx);
      tracker.add(e.clientX);

      var next = startScroll - dx;
      var max = maxScroll();
      // Резиновые края вместо жёсткого стопа
      if (next < 0) next = -rubberband(-next, rail.clientWidth);
      else if (next > max) next = max + rubberband(next - max, rail.clientWidth);
      rail.scrollLeft = next;
    });

    function release(e) {
      if (!dragging || (e && e.pointerId !== pointerId)) return;
      dragging = false;
      rail.removeAttribute("data-dragging");

      var v = -tracker.velocity();                       // px/s по оси скролла
      var projected = rail.scrollLeft + project(v);      // куда жест «летит»
      var target = nearest(projected);                   // снап к ближайшей карточке

      spring.value = rail.scrollLeft;
      spring.setTarget(target, v);                       // передача скорости (§5)
    }

    rail.addEventListener("pointerup", release);
    rail.addEventListener("pointercancel", release);

    // Клик после протаскивания не должен открывать карточку
    rail.addEventListener("click", function (e) {
      if (moved > 8) { e.preventDefault(); e.stopPropagation(); }
      moved = 0;
    }, true);
  }

  function rails() {
    document.querySelectorAll(".rail").forEach(railify);
  }

  /* =====================================================================
     Нижний лист: тянется за пальцем, закрывается по скорости, а не по
     позиции — короткий быстрый флик закрывает, медленное долгое тянет назад.
     ===================================================================== */
  function bottomSheet() {
    var sheet = document.getElementById("nav-sheet");
    var scrim = document.getElementById("nav-scrim");
    var openers = document.querySelectorAll("[data-sheet-open]");
    if (!sheet || !scrim) return;

    var height = 0;
    var open = false;
    var tracker = new Tracker();
    var dragging = false;
    var startY = 0;
    var startVal = 0;

    var spring = new Spring({
      damping: 0.86,
      response: 0.34,
      from: 1,
      onUpdate: function (v) {
        sheet.style.transform = "translate3d(0," + v * 100 + "%,0)";
        scrim.style.opacity = String(Math.max(0, 1 - v));
      },
      onRest: function () {
        if (spring.target === 1) {
          scrim.setAttribute("data-open", "0");
          sheet.setAttribute("aria-hidden", "true");
        }
      }
    });

    function show() {
      open = true;
      height = sheet.offsetHeight || 1;
      scrim.setAttribute("data-open", "1");
      sheet.setAttribute("aria-hidden", "false");
      sheet.removeAttribute("inert");
      spring.setTarget(0);
    }
    function hide() {
      open = false;
      spring.setTarget(1);
      // aria-hidden прячет лист от скринридера, но не от клавиатуры:
      // ссылки внутри по-прежнему получали фокус, и он уходил в пустоту.
      // inert убирает элемент и из порядка обхода, и из дерева доступности.
      sheet.setAttribute("inert", "");
    }

    openers.forEach(function (btn) {
      btn.addEventListener("click", function (e) { e.preventDefault(); open ? hide() : show(); });
    });
    scrim.addEventListener("click", hide);
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && open) hide(); });

    sheet.addEventListener("pointerdown", function (e) {
      if (e.target.closest("a")) return;    // ссылка — это тап, не перетаскивание
      spring.stop();
      dragging = true;
      height = sheet.offsetHeight || 1;
      startY = e.clientY;
      startVal = spring.value;
      tracker.reset();
      tracker.add(e.clientY);
      sheet.setPointerCapture(e.pointerId);
    });

    sheet.addEventListener("pointermove", function (e) {
      if (!dragging) return;
      tracker.add(e.clientY);
      var dy = (e.clientY - startY) / height;
      var v = startVal + dy;
      if (v < 0) v = -rubberband(-v * height, height) / height;  // вверх — резина
      spring.value = v;
      sheet.style.transform = "translate3d(0," + v * 100 + "%,0)";
      scrim.style.opacity = String(Math.max(0, 1 - v));
    });

    function done() {
      if (!dragging) return;
      dragging = false;
      var vy = tracker.velocity();                 // px/s
      var normalized = vy / height;                // доли высоты в секунду
      var projected = spring.value + project(normalized);
      // Решение по ЗНАКУ скорости, а не по позиции (§10)
      var target = projected > 0.5 ? 1 : 0;
      open = target === 0;
      spring.setTarget(target, normalized);
    }
    sheet.addEventListener("pointerup", done);
    sheet.addEventListener("pointercancel", done);

    spring.set(1);
    sheet.setAttribute("inert", "");   // стартовое состояние — закрыт
  }

  /* =====================================================================
     Таб-бар прячется, когда пользователь читает, и возвращается, когда
     тянет вверх. Поведение из Safari и Instagram: панель не должна
     занимать место, пока ею не пользуются.

     Два порога вместо одного: скрываем только после заметного движения
     вниз, показываем почти сразу. Асимметрия намеренная — вернуть
     навигацию должно быть легче, чем случайно её потерять.
     ===================================================================== */
  function tabbarAutoHide() {
    var bar = document.getElementById("tabbar");
    if (!bar) return;

    var lastY = window.scrollY;
    var accumulated = 0;
    var hidden = false;
    var ticking = false;

    var HIDE_AFTER = 64;   // px вниз подряд, прежде чем спрятать
    var SHOW_AFTER = 24;   // px вверх, чтобы вернуть
    var TOP_ZONE = 120;    // у самого верха панель всегда видна

    function setHidden(next) {
      if (next === hidden) return;
      hidden = next;
      bar.setAttribute("data-hidden", next ? "1" : "0");
    }

    function update() {
      ticking = false;
      var y = window.scrollY;
      var delta = y - lastY;
      lastY = y;

      // Резиновый отскок в iOS даёт отрицательный scrollY — игнорируем
      if (y < TOP_ZONE) { accumulated = 0; setHidden(false); return; }

      // Копим движение в одну сторону, разворот обнуляет счётчик
      if ((delta > 0) !== (accumulated > 0)) accumulated = 0;
      accumulated += delta;

      if (accumulated > HIDE_AFTER) { setHidden(true); accumulated = 0; }
      else if (accumulated < -SHOW_AFTER) { setHidden(false); accumulated = 0; }
    }

    window.addEventListener("scroll", function () {
      if (!ticking) { ticking = true; requestAnimationFrame(update); }
    }, { passive: true });

    // Открытый лист меню — панель не должна выезжать поверх него
    var sheetOpener = document.querySelector("[data-sheet-open]");
    if (sheetOpener) {
      sheetOpener.addEventListener("click", function () { setHidden(false); });
    }
  }

  /* =====================================================================
     Счётчик корзины в таб-баре — синхронизируем с существующей логикой
     ===================================================================== */
  function cartBadge() {
    var badge = document.getElementById("tab-cart-count");
    var source = document.getElementById("cart-count");
    if (!badge || !source) return;
    function sync() {
      var v = source.textContent.trim();
      if (source.hasAttribute("hidden") || !v || v === "0") badge.hidden = true;
      else { badge.hidden = false; badge.textContent = v; }
    }
    sync();
    new MutationObserver(sync).observe(source, {
      childList: true, characterData: true, subtree: true, attributes: true
    });
  }

  /* ------------------------------------------------------------------- */
  document.addEventListener("DOMContentLoaded", function () {
    headerMaterial();
    reveal();
    pressFeedback();
    rails();
    bottomSheet();
    tabbarAutoHide();
    cartBadge();
  });

  window.AmorFluid = { Spring: Spring, project: project, rubberband: rubberband, Tracker: Tracker };
})();
