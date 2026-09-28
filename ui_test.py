from playwright.sync_api import sync_playwright
res=[]
def check(n, ok, d=""):
    res.append((n,bool(ok),d)); print(f"  [{'OK  ' if ok else 'FAIL'}] {n}" + (f" — {d}" if d else ""))

with sync_playwright() as p:
    b=p.chromium.launch()

    print("\n10. ДЕСКТОП: ИНТЕРФЕЙС")
    pg=b.new_page(viewport={"width":1440,"height":900})
    errs=[]; pg.on("console", lambda m: errs.append(m.text) if m.type=="error" else None)
    pg.on("pageerror", lambda e: errs.append("JS: "+str(e)))
    pg.goto("http://localhost:5050/", wait_until="networkidle"); pg.wait_for_timeout(900)
    check("нет ошибок JS на главной", len([e for e in errs if e.startswith('JS')])==0, str(errs[:2]))
    pg.evaluate("""async()=>{const h=document.body.scrollHeight;for(let y=0;y<h;y+=400){window.scrollTo(0,y);await new Promise(r=>setTimeout(r,45));}}""")
    pg.wait_for_timeout(600)
    vis=pg.evaluate("document.querySelectorAll('.reveal.is-visible').length")
    tot=pg.evaluate("document.querySelectorAll('.reveal').length")
    check("все секции проявились", vis==tot, f"{vis}/{tot}")
    check("стекло в шапке", "blur" in pg.eval_on_selector(".site-header","e=>getComputedStyle(e).backdropFilter"))
    pg.evaluate("window.scrollTo(0,400)"); pg.wait_for_timeout(500)
    check("шапка уплотняется при скролле", pg.eval_on_selector(".site-header","e=>e.dataset.scrolled")=="1")
    check("таб-бар скрыт на десктопе", pg.eval_on_selector(".tabbar","e=>getComputedStyle(e).display")=="none")
    check("палитра не изменилась",
          pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--rose-deep').trim()")=="#a9636f")

    print("\n11. КОРЗИНА (реальный клик)")
    pg.goto("http://localhost:5050/catalog", wait_until="networkidle"); pg.wait_for_timeout(700)
    pg.evaluate("document.querySelectorAll('.reveal').forEach(e=>e.classList.add('is-visible'))")
    pg.locator("button:has-text('В корзину')").first.click(); pg.wait_for_timeout(900)
    cnt=pg.evaluate("JSON.parse(localStorage.getItem('amor_cart_v1')||'[]').length")
    check("товар кладётся в корзину", cnt==1, f"{cnt} позиций")
    badge=pg.eval_on_selector("#cart-count","e=>e.textContent")
    check("счётчик в шапке обновился", badge.strip()=="1", badge)
    pg.goto("http://localhost:5050/cart", wait_until="networkidle"); pg.wait_for_timeout(700)
    check("корзина отрисовалась", pg.locator(".cart-row, #cart-rows tr").count()>0)
    pg.goto("http://localhost:5050/checkout", wait_until="networkidle"); pg.wait_for_timeout(600)
    check("checkout видит товар", pg.eval_on_selector_all("#checkout-layout, .checkout-summary","e=>e.length")>0)

    print("\n12. МОБИЛЬНАЯ ВЕРСИЯ (390px)")
    m=b.new_page(viewport={"width":390,"height":844}, is_mobile=True, has_touch=True,
      user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148")
    merrs=[]; m.on("pageerror", lambda e: merrs.append(str(e)))
    m.goto("http://localhost:5050/", wait_until="networkidle"); m.wait_for_timeout(1000)
    vp=m.evaluate("({doc:document.documentElement.scrollWidth,win:window.innerWidth})")
    check("нет горизонтального переполнения", vp["doc"]<=vp["win"]+1, str(vp))
    check("таб-бар виден", m.eval_on_selector(".tabbar","e=>getComputedStyle(e).display")=="block")
    check("4 вкладки + отдельная кнопка WhatsApp",
          m.eval_on_selector_all(".tab","e=>e.length")==4 and m.eval_on_selector_all(".tab-wa","e=>e.length")==1)
    check("подпись только у активной вкладки",
          m.eval_on_selector(".tab.active .tab-label","e=>getComputedStyle(e).opacity")=="1" and
          m.eval_on_selector(".tab:not(.active) .tab-label","e=>getComputedStyle(e).opacity")=="0")
    m.evaluate("window.scrollTo(0,1500)"); m.wait_for_timeout(800)
    hid=m.eval_on_selector("#tabbar","e=>e.dataset.hidden")
    m.evaluate("window.scrollTo(0,1250)"); m.wait_for_timeout(800)
    shown=m.eval_on_selector("#tabbar","e=>e.dataset.hidden")
    check("панель прячется вниз и возвращается вверх", hid=="1" and shown=="0", f"вниз={hid} вверх={shown}")
    m.evaluate("window.scrollTo(0,480)"); m.wait_for_timeout(600)
    q=m.evaluate("""()=>{const w=document.querySelector('.quicknav');
      const it=[...document.querySelectorAll('.quicknav-item')];
      return {rows:[...new Set(it.map(e=>Math.round(e.getBoundingClientRect().top)))].length,
              scrollable:w.scrollWidth>w.clientWidth,
              heights:[...new Set(it.map(e=>Math.round(e.getBoundingClientRect().height)))].length,
              clipped:[...document.querySelectorAll('.quicknav-item>span:not(.quicknav-circle)')].filter(e=>e.scrollHeight>e.clientHeight+1).length};}""")
    check("кружки в один ряд", q["rows"]==1, f"рядов {q['rows']}")
    check("кружки одинаковой высоты", q["heights"]==1)
    check("лента листается", q["scrollable"])
    check("подписи не обрезаны", q["clipped"]==0, f"обрезано {q['clipped']}")
    small=m.evaluate("""()=>{const b=[];document.querySelectorAll('.tab,.icon-btn,.btn').forEach(e=>{const r=e.getBoundingClientRect();if(r.width>0&&(r.height<44||r.width<44))b.push(Math.round(r.width)+'x'+Math.round(r.height));});return b;}""")
    check("все кнопки не меньше 44px", len(small)==0, str(small[:4]))
    m.locator("[data-sheet-open]").click(force=True); m.wait_for_timeout(1000)
    ty=m.eval_on_selector("#nav-sheet","e=>getComputedStyle(e).transform")
    check("лист меню открывается", "matrix" in ty and "100" not in ty.split(",")[-1], ty[-24:])
    check("лист содержит навигацию", m.eval_on_selector_all(".sheet-link","e=>e.length")>=4)
    check("открытый лист доступен с клавиатуры",
          m.evaluate("""()=>{const l=document.querySelector('#nav-sheet .sheet-link');l.focus();return document.activeElement===l;}"""))
    m.keyboard.press("Escape"); m.wait_for_timeout(700)
    check("закрытый лист не ловит фокус",
          not m.evaluate("""()=>{const l=document.querySelector('#nav-sheet .sheet-link');l.focus();return document.activeElement===l;}"""))
    check("нет ошибок JS на мобильном", len(merrs)==0, str(merrs[:2]))
    m.goto("http://localhost:5050/catalog", wait_until="networkidle"); m.wait_for_timeout(800)
    vp2=m.evaluate("({doc:document.documentElement.scrollWidth,win:window.innerWidth})")
    check("каталог без переполнения", vp2["doc"]<=vp2["win"]+1, str(vp2))

    print("\n13. ДОСТУПНОСТЬ И РЕЖИМЫ")
    r=b.new_page(viewport={"width":1440,"height":900})
    r.emulate_media(reduced_motion="reduce")
    r.goto("http://localhost:5050/", wait_until="networkidle"); r.wait_for_timeout(900)
    rv=r.evaluate("document.querySelectorAll('.reveal.is-visible').length+'/'+document.querySelectorAll('.reveal').length")
    a,t2=rv.split("/")
    check("при reduced-motion контент виден сразу", a==t2, rv)

    nojs=b.new_context(java_script_enabled=False).new_page()
    nojs.goto("http://localhost:5050/", wait_until="domcontentloaded"); nojs.wait_for_timeout(500)
    op=nojs.eval_on_selector(".reveal","e=>getComputedStyle(e).opacity")
    check("без JS контент не пропадает", float(op)==1.0, f"opacity {op}")

    b.close()

print("\n"+"="*62)
ok=sum(1 for _,o,_ in res if o)
print(f"ИНТЕРФЕЙС: {ok} из {len(res)} ({round(ok/len(res)*100)}%)")
for n,o,d in res:
    if not o: print(f"  · {n} — {d}")
