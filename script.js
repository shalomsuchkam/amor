(() => {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* ignore */ } }
  };

  /* ---------- Язык ---------- */
  const ru = {};
  $$('[data-i18n]').forEach(el => { ru[el.dataset.i18n] = el.textContent; });
  $$('[data-i18n-html]').forEach(el => { ru[el.dataset.i18nHtml] = el.innerHTML; });
  ru.title = document.title;
  ru.desc = $('meta[name="description"]').content;
  let lang = 'ru';

  const setLang = (l, persist = true) => {
    if (!['ru', 'kk', 'en'].includes(l)) l = 'ru';
    lang = l;
    const dict = l === 'ru' ? ru : window.I18N[l];
    $$('[data-i18n]').forEach(el => { const v = dict[el.dataset.i18n]; if (v != null) el.textContent = v; });
    $$('[data-i18n-html]').forEach(el => { const v = dict[el.dataset.i18nHtml]; if (v != null) el.innerHTML = v; });
    document.documentElement.lang = l === 'kk' ? 'kk' : l;
    document.title = dict.title;
    $('meta[name="description"]').content = dict.desc;
    $$('[data-set-lang]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.setLang === l)));
    if (persist) store.set('sk-lang', l);
    updateCalc(false);
    splitStatement();
  };
  $$('[data-set-lang]').forEach(b => b.addEventListener('click', () => setLang(b.dataset.setLang)));

  /* ---------- Навигация и меню ---------- */
  const nav = $('.nav');
  const burger = $('.burger');
  const menu = $('#menu');
  const toggleMenu = (open) => {
    const o = open ?? !menu.classList.contains('open');
    menu.classList.toggle('open', o);
    menu.setAttribute('aria-hidden', String(!o));
    burger.setAttribute('aria-expanded', String(o));
    document.body.classList.toggle('lock', o);
  };
  burger.addEventListener('click', () => toggleMenu());
  $$('a', menu).forEach(a => a.addEventListener('click', () => toggleMenu(false)));
  addEventListener('keydown', e => { if (e.key === 'Escape') toggleMenu(false); });

  // прячем капсулу при прокрутке вниз, возвращаем при прокрутке вверх
  let lastY = 0, ticking = false;
  addEventListener('scroll', () => {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(() => {
      const y = scrollY;
      nav.classList.toggle('hide', y > lastY && y > 400 && !menu.classList.contains('open'));
      lastY = y; ticking = false;
    });
  }, { passive: true });

  // подсветка активного раздела
  const links = $$('.nav-links a');
  const spy = new IntersectionObserver(es => {
    es.forEach(e => {
      if (e.isIntersecting) links.forEach(a => a.classList.toggle('on', a.getAttribute('href') === '#' + e.target.id));
    });
  }, { rootMargin: '-45% 0px -50% 0px' });
  links.forEach(a => { const t = $(a.getAttribute('href')); if (t) spy.observe(t); });

  /* ---------- Появление при прокрутке ---------- */
  const io = new IntersectionObserver(es => {
    es.forEach(e => { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } });
  }, { threshold: .12, rootMargin: '0px 0px -6% 0px' });
  $$('.rv:not(.hero-sub):not(.hero-cta)').forEach(el => io.observe(el));

  /* ---------- Манифест: слова проявляются по очереди ---------- */
  const statement = $('#statement');
  function splitStatement() {
    const text = statement.textContent.trim();
    statement.setAttribute('aria-label', text);
    statement.innerHTML = text.split(/\s+/).map((w, i) => `<span class="w" aria-hidden="true" style="--i:${i}">${w}</span>`).join(' ');
    if (statement.classList.contains('in') || reduce) statement.classList.add('in');
  }
  splitStatement();
  new IntersectionObserver((es, o) => es.forEach(e => { if (e.isIntersecting) { statement.classList.add('in'); o.disconnect(); } }), { threshold: .35 }).observe(statement);

  /* ---------- Счётчики ---------- */
  $$('[data-count]').forEach(n => {
    const to = +n.dataset.count;
    if (!reduce) n.textContent = '0';
    new IntersectionObserver((es, o) => es.forEach(e => {
      if (!e.isIntersecting) return;
      o.disconnect();
      if (reduce) return;
      const t0 = performance.now();
      const step = t => {
        const p = Math.min((t - t0) / 1600, 1);
        n.textContent = Math.round(to * (1 - Math.pow(1 - p, 4)));
        if (p < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    }), { threshold: .6 }).observe(n);
  });

  /* ---------- GSAP: параллакс героя и стопка этапов ---------- */
  const initGsap = () => {
    if (reduce || !window.gsap || !window.ScrollTrigger) return;
    gsap.registerPlugin(ScrollTrigger);
    gsap.to('#heroImg', { yPercent: -12, ease: 'none', scrollTrigger: { trigger: '.hero', start: 'top top', end: 'bottom top', scrub: true } });

    const mm = gsap.matchMedia();
    mm.add('(min-width: 901px)', () => {
      const steps = gsap.utils.toArray('.step');
      steps.forEach((s, i) => {
        if (i === steps.length - 1) return;
        gsap.to(s, {
          scale: .93, opacity: .45, ease: 'none',
          scrollTrigger: { trigger: steps[i + 1], start: 'top 85%', end: 'top 15%', scrub: true }
        });
      });
    });
  };
  addEventListener('load', initGsap);

  /* ---------- До / после ---------- */
  const baBox = $('#baBox'), baHandle = $('#baHandle');
  let pos = 50, dragging = false;
  const setPos = p => {
    pos = Math.max(0, Math.min(100, p));
    baBox.style.setProperty('--pos', pos + '%');
    baHandle.setAttribute('aria-valuenow', Math.round(pos));
  };
  const fromEvent = e => { const r = baBox.getBoundingClientRect(); setPos((e.clientX - r.left) / r.width * 100); };
  baBox.addEventListener('pointerdown', e => { dragging = true; baBox.classList.add('drag'); baBox.setPointerCapture(e.pointerId); fromEvent(e); });
  baBox.addEventListener('pointermove', e => { if (dragging) fromEvent(e); });
  const endDrag = () => { dragging = false; baBox.classList.remove('drag'); };
  baBox.addEventListener('pointerup', endDrag);
  baBox.addEventListener('pointercancel', endDrag);
  baHandle.addEventListener('keydown', e => {
    if (e.key === 'ArrowLeft') { setPos(pos - 5); e.preventDefault(); }
    if (e.key === 'ArrowRight') { setPos(pos + 5); e.preventDefault(); }
  });
  // единожды показываем, что ползунок двигается
  new IntersectionObserver((es, o) => es.forEach(e => {
    if (!e.isIntersecting) return;
    o.disconnect();
    if (reduce) return;
    const t0 = performance.now();
    const step = t => {
      if (dragging) return;
      const p = Math.min((t - t0) / 1800, 1);
      setPos(50 + Math.sin(p * Math.PI * 2) * 22 * (1 - p));
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }), { threshold: .6 }).observe(baBox);

  /* ---------- Галерея ---------- */
  const strips = $$('.strip');
  const openStrip = s => { strips.forEach(x => x.classList.toggle('is-open', x === s)); };
  strips.forEach(s => {
    s.addEventListener('mouseenter', () => { if (matchMedia('(min-width: 901px)').matches) openStrip(s); });
    s.addEventListener('focus', () => openStrip(s));
    s.addEventListener('click', () => openStrip(s));
  });

  /* ---------- Калькулятор ---------- */
  const BASE = 80000, DESIGN = 15000;
  const area = $('#area'), design = $('#design'), packs = $$('.pack');
  const fmt = n => Math.round(n).toLocaleString('ru-RU').replace(/ | /g, ' ');
  let shown = 0, calcState = null, raf = 0;

  function updateCalc(animate = true) {
    const a = +area.value;
    const pi = packs.findIndex(p => p.classList.contains('is-on'));
    const k = +packs[pi].dataset.k;
    const withDesign = design.checked;
    const perSqm = BASE * k + (withDesign ? DESIGN : 0);
    const total = a * perSqm;
    const d = window.I18N.dyn[lang];
    $('#areaOut').textContent = a;
    area.style.setProperty('--fill', ((a - area.min) / (area.max - area.min) * 100) + '%');
    $('#perSqm').textContent = fmt(perSqm) + ' ₸';
    $('#term').textContent = d.term[pi];
    calcState = { a, pi, withDesign, total, perSqm };
    cancelAnimationFrame(raf);
    if (!animate || reduce) { shown = total; $('#total').textContent = fmt(total); return; }
    const from = shown, t0 = performance.now();
    const step = t => {
      const p = Math.min((t - t0) / 700, 1);
      shown = from + (total - from) * (1 - Math.pow(1 - p, 3));
      $('#total').textContent = fmt(shown);
      if (p < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
  }
  packs.forEach(p => p.addEventListener('click', () => {
    packs.forEach(x => { x.classList.toggle('is-on', x === p); x.setAttribute('aria-checked', String(x === p)); });
    updateCalc();
  }));
  area.addEventListener('input', () => updateCalc());
  design.addEventListener('change', () => updateCalc());

  const summary = () => {
    const d = window.I18N.dyn[lang], c = calcState;
    return `${d.calc}: ${d.name[c.pi]}, ${c.a} ${d.m2}, ${c.withDesign ? d.withD : d.noD}. ${d.total} ${fmt(c.total)} ₸`;
  };
  let withCalc = false;
  $('#calcCta').addEventListener('click', () => {
    withCalc = true;
    const s = $('#formSum');
    s.textContent = summary(); s.hidden = false;
  });

  /* ---------- FAQ ---------- */
  $$('.q').forEach(q => q.addEventListener('click', () => {
    const qa = q.parentElement, o = !qa.classList.contains('open');
    qa.classList.toggle('open', o);
    q.setAttribute('aria-expanded', String(o));
  }));

  /* ---------- Форма: уходит в WhatsApp ---------- */
  const form = $('#form'), fName = $('#fName'), fPhone = $('#fPhone'), fMsg = $('#fMsg');
  fPhone.addEventListener('input', () => {
    let d = fPhone.value.replace(/\D/g, '');
    if (d.startsWith('8')) d = '7' + d.slice(1);
    if (!d.startsWith('7')) d = '7' + d;
    d = d.slice(0, 11);
    const p = [d.slice(0, 1), d.slice(1, 4), d.slice(4, 7), d.slice(7, 9), d.slice(9, 11)];
    fPhone.value = '+' + p[0] + (p[1] ? ' ' + p[1] : '') + (p[2] ? ' ' + p[2] : '') + (p[3] ? ' ' + p[3] : '') + (p[4] ? ' ' + p[4] : '');
  });
  fPhone.addEventListener('focus', () => { if (!fPhone.value) fPhone.value = '+7 '; });
  form.addEventListener('submit', e => {
    e.preventDefault();
    const okName = fName.value.trim().length >= 2;
    const okPhone = fPhone.value.replace(/\D/g, '').length === 11;
    fName.parentElement.classList.toggle('bad', !okName);
    fPhone.parentElement.classList.toggle('bad', !okPhone);
    if (!okName || !okPhone) { (okName ? fPhone : fName).focus(); return; }
    const d = window.I18N.dyn[lang];
    const lines = [d.greet, `${d.fName}: ${fName.value.trim()}`, `${d.fPhone}: ${fPhone.value}`];
    if (fMsg.value.trim()) lines.push(fMsg.value.trim());
    if (withCalc) lines.push(summary());
    window.open('https://wa.me/77775948384?text=' + encodeURIComponent(lines.join('\n')), '_blank', 'noopener');
  });

  // кнопка WhatsApp не нужна рядом с формой
  const fab = $('.fab');
  new IntersectionObserver(es => es.forEach(e => {
    fab.style.opacity = e.isIntersecting ? '0' : '1';
    fab.style.pointerEvents = e.isIntersecting ? 'none' : 'auto';
  })).observe($('#contact'));

  /* ---------- Старт ---------- */
  const saved = store.get('sk-lang');
  const nl = (navigator.language || '').slice(0, 2);
  setLang(saved || (nl === 'kk' ? 'kk' : 'ru'), false);
  updateCalc(false);
})();
