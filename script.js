(() => {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const canHover = matchMedia('(hover: hover) and (pointer: fine)').matches;
  // язык задаёт сама страница (/, /kk/, /en/): тексты уже переведены при сборке
  const lang = ['kk', 'en'].includes(document.documentElement.lang) ? document.documentElement.lang : 'ru';
  let lenis = null;

  /* ---------- Меню ---------- */
  const nav = $('.nav'), burger = $('.burger'), menu = $('#menu');
  const toggleMenu = (open) => {
    const o = open ?? !menu.classList.contains('open');
    menu.classList.toggle('open', o);
    menu.setAttribute('aria-hidden', String(!o));
    burger.setAttribute('aria-expanded', String(o));
    document.body.classList.toggle('lock', o);
    if (lenis) (o ? lenis.stop() : lenis.start());
  };
  burger.addEventListener('click', () => toggleMenu());
  $$('a', menu).forEach(a => a.addEventListener('click', () => toggleMenu(false)));
  addEventListener('keydown', e => { if (e.key === 'Escape') toggleMenu(false); });

  // капсула уходит вверх при прокрутке вниз и возвращается при прокрутке вверх
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

  const links = $$('.nav-links a');
  const spy = new IntersectionObserver(es => es.forEach(e => {
    if (e.isIntersecting) links.forEach(a => a.classList.toggle('on', a.getAttribute('href') === '#' + e.target.id));
  }), { rootMargin: '-45% 0px -50% 0px' });
  links.forEach(a => { const t = $(a.getAttribute('href')); if (t) spy.observe(t); });

  /* ---------- Появление при прокрутке ---------- */
  const io = new IntersectionObserver(es => es.forEach(e => {
    if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
  }), { threshold: .12, rootMargin: '0px 0px -6% 0px' });
  $$('.rv, .reveal-img').forEach(el => io.observe(el));

  /* ---------- Манифест: слова загораются по мере прокрутки ---------- */
  const statement = $('#statement');
  const text = statement.textContent.trim();
  statement.setAttribute('aria-label', text);
  statement.innerHTML = text.split(/\s+/).map((w, i) => `<span class="w" aria-hidden="true" style="--i:${i}">${w}</span>`).join(' ');
  const statementFallback = () => new IntersectionObserver((es, o) => es.forEach(e => {
    if (e.isIntersecting) { statement.classList.add('in'); o.disconnect(); }
  }), { threshold: .35 }).observe(statement);

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

  /* ---------- Подсветка карточек под курсором и магнитные кнопки ---------- */
  if (canHover && !reduce) {
    $$('.cell').forEach(c => {
      c.addEventListener('pointermove', e => {
        const r = c.getBoundingClientRect();
        c.style.setProperty('--mx', (e.clientX - r.left) + 'px');
        c.style.setProperty('--my', (e.clientY - r.top) + 'px');
      }, { passive: true });
    });
    $$('.magnetic').forEach(b => {
      b.addEventListener('pointermove', e => {
        const r = b.getBoundingClientRect();
        b.style.setProperty('--tx', ((e.clientX - r.left - r.width / 2) * .16) + 'px');
        b.style.setProperty('--ty', ((e.clientY - r.top - r.height / 2) * .28) + 'px');
      }, { passive: true });
      b.addEventListener('pointerleave', () => { b.style.setProperty('--tx', '0px'); b.style.setProperty('--ty', '0px'); });
    });
  }

  /* ---------- Плавная прокрутка и GSAP ---------- */
  const initMotion = () => {
    const g = window.gsap, ST = window.ScrollTrigger;
    if (!g || !ST) { statementFallback(); return; }
    g.registerPlugin(ST);

    if (window.Lenis && !reduce) {
      lenis = new window.Lenis({ lerp: .09, smoothWheel: true });
      lenis.on('scroll', ST.update);
      g.ticker.add(t => lenis.raf(t * 1000));
      g.ticker.lagSmoothing(0);
      $$('a[href^="#"]').forEach(a => a.addEventListener('click', e => {
        const id = a.getAttribute('href');
        if (id.length < 2) return;
        const target = $(id);
        if (!target) return;
        e.preventDefault();
        lenis.scrollTo(target, { offset: id === '#top' ? 0 : -70, duration: 1.4 });
      }));
    }

    if (reduce) { statement.classList.add('in'); return; }

    // манифест
    statement.classList.add('gs');
    g.fromTo($$('.w', statement), { opacity: .16 }, {
      opacity: 1, ease: 'none', stagger: .12,
      scrollTrigger: { trigger: statement, start: 'top 82%', end: 'bottom 48%', scrub: true }
    });

    // параллакс героя
    g.to('#heroImg', { yPercent: -10, ease: 'none', scrollTrigger: { trigger: '.hero', start: 'top top', end: 'bottom top', scrub: true } });

    const mm = g.matchMedia();
    // стопка этапов
    mm.add('(min-width: 901px)', () => {
      const steps = g.utils.toArray('.step');
      steps.forEach((s, i) => {
        if (i === steps.length - 1) return;
        g.to(s, { scale: .94, opacity: .5, ease: 'none',
          scrollTrigger: { trigger: steps[i + 1], start: 'top 85%', end: 'top 15%', scrub: true } });
      });
    });
    // горизонтальная панорама галереи
    mm.add('(min-width: 901px)', () => {
      const hp = $('#hpan'), track = $('#htrack'), prog = $('#hprog');
      if (!hp || !track) return;
      hp.classList.add('is-pinned');
      const dist = () => Math.max(0, track.scrollWidth - hp.clientWidth);
      const tween = g.to(track, {
        x: () => -dist(), ease: 'none',
        scrollTrigger: {
          trigger: hp, start: 'top top', end: () => '+=' + dist(), pin: true, scrub: .6, invalidateOnRefresh: true,
          onUpdate: s => { prog.style.transform = `scaleX(${s.progress})`; }
        }
      });
      $$('.hslide img', track).forEach(img => {
        g.fromTo(img, { xPercent: 4 }, { xPercent: -4, ease: 'none',
          scrollTrigger: { trigger: img.parentElement, containerAnimation: tween, start: 'left right', end: 'right left', scrub: true } });
      });
      return () => hp.classList.remove('is-pinned');
    });

    addEventListener('load', () => ST.refresh());
  };
  if (document.readyState === 'complete') initMotion(); else addEventListener('load', initMotion);
  // страховка: если библиотеки не загрузились, слова манифеста всё равно появятся
  setTimeout(() => { if (!statement.classList.contains('gs')) statementFallback(); }, 4000);

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

  /* ---------- Калькулятор ---------- */
  const BASE = 80000, DESIGN = 15000;
  const area = $('#area'), design = $('#design'), packs = $$('.pack');
  const fmt = n => Math.round(n).toLocaleString('ru-RU').replace(/ | /g, ' ');
  let shown = 0, calcState = null, raf = 0;
  const setTotal = n => { const t = fmt(n); $('#total').textContent = t; $('#barTotal').textContent = t; };

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
    if (!animate || reduce) { shown = total; setTotal(total); return; }
    const from = shown, t0 = performance.now();
    const step = t => {
      const p = Math.min((t - t0) / 700, 1);
      shown = from + (total - from) * (1 - Math.pow(1 - p, 3));
      setTotal(shown);
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

  let quizNote = '', withCalc = false;
  const summary = () => {
    const d = window.I18N.dyn[lang], c = calcState;
    return `${d.calc}: ${d.name[c.pi]}, ${c.a} ${d.m2}, ${c.withDesign ? d.withD : d.noD}. ${d.total} ${fmt(c.total)} ₸` + (quizNote ? ` (${quizNote})` : '');
  };
  $$('.calc-go, .calc-go-quiz').forEach(a => a.addEventListener('click', () => {
    withCalc = true;
    const s = $('#formSum');
    s.textContent = summary(); s.hidden = false;
  }));

  // на телефоне итог остаётся виден, пока листаете калькулятор
  const bar = $('#calcBar');
  const vis = { pr: false, ct: false };
  const syncBar = () => {
    const on = vis.pr && !vis.ct;
    bar.classList.toggle('on', on);
    bar.setAttribute('aria-hidden', String(!on));
    document.body.classList.toggle('has-bar', on);
  };
  new IntersectionObserver(es => es.forEach(e => { vis.pr = e.isIntersecting; syncBar(); }), { rootMargin: '-30% 0px -10% 0px' }).observe($('#pricing .calc'));
  new IntersectionObserver(es => es.forEach(e => { vis.ct = e.isIntersecting; syncBar(); })).observe($('#contact'));

  /* ---------- FAQ ---------- */
  $$('.q').forEach(q => q.addEventListener('click', () => {
    const qa = q.parentElement, o = !qa.classList.contains('open');
    qa.classList.toggle('open', o);
    q.setAttribute('aria-expanded', String(o));
    if (window.ScrollTrigger) setTimeout(() => window.ScrollTrigger.refresh(), 750);
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

  /* ---------- Отзывы из reviews.json (только настоящие) ---------- */
  fetch('/reviews.json').then(r => r.ok ? r.json() : []).then(list => {
    if (!Array.isArray(list) || !list.length) return;
    const box = $('#revList');
    list.slice(0, 6).forEach(r => {
      const f = document.createElement('figure');
      f.className = 'rev rv';
      const q = document.createElement('blockquote'); q.textContent = '“' + r.text + '”';
      const c = document.createElement('cite'); const b = document.createElement('b'); b.textContent = r.name;
      c.append(b, r.detail || ''); f.append(q, c); box.append(f); io.observe(f);
    });
    $('#reviews').hidden = false;
  }).catch(() => {});

  // кнопка WhatsApp не нужна рядом с формой
  const fab = $('.fab');
  new IntersectionObserver(es => es.forEach(e => fab.classList.toggle('gone', e.isIntersecting))).observe($('#contact'));

  /* ---------- Видео: iframe грузится только по клику ---------- */
  const yt = $('#yt');
  if (yt) {
    $('.yt-play', yt).addEventListener('click', () => {
      const f = document.createElement('iframe');
      f.src = `https://www.youtube-nocookie.com/embed/${yt.dataset.id}?autoplay=1&rel=0&playsinline=1&modestbranding=1`;
      f.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
      f.allowFullscreen = true; f.title = 'Sharkong';
      yt.replaceChildren(f);
    });
  }

  /* ---------- Квиз: подбор пакета ---------- */
  const quiz = $('#quizBox');
  if (quiz) {
    const panels = $$('.qpanel', quiz), ans = [], labels = [];
    let step = 0;
    const show = n => {
      step = n;
      panels.forEach((p, i) => p.classList.toggle('is-on', i === n));
      $('#qStep').textContent = `${Math.min(n + 1, 4)} / 4`;
      $('#qBar').style.transform = `scaleX(${Math.min(n + 1, 4) / 4})`;
      $('#qBack').hidden = n === 0 || n === 4;
      $('#qRestart').hidden = n !== 4;
    };
    const finish = () => {
      const pi = +ans[2];
      packs.forEach((x, i) => { x.classList.toggle('is-on', i === pi); x.setAttribute('aria-checked', String(i === pi)); });
      area.value = ans[1]; design.checked = true;
      updateCalc(false);
      const d = window.I18N.dyn[lang];
      $('#qPack').textContent = d.name[pi];
      $('#qPrice').textContent = fmt(calcState.total) + ' ₸';
      $('#qTerm').textContent = d.term[pi];
      quizNote = `${labels[0]}, ${labels[3]}`;
      show(4);
    };
    $$('.opt', quiz).forEach(b => b.addEventListener('click', () => {
      const q = +b.closest('.qpanel').dataset.q;
      ans[q] = b.dataset.v; labels[q] = b.textContent.trim();
      $$('.opt', b.parentElement).forEach(o => o.classList.toggle('is-on', o === b));
      setTimeout(() => (q < 3 ? show(q + 1) : finish()), reduce ? 0 : 220);
    }));
    $('#qBack').addEventListener('click', () => show(Math.max(0, step - 1)));
    $('#qRestart').addEventListener('click', () => { $$('.opt', quiz).forEach(o => o.classList.remove('is-on')); show(0); });
    show(0);
  }

  updateCalc(false);
})();
