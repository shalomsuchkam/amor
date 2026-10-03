#!/usr/bin/env python3
"""SEO-аудит собранного сайта. Запуск: python3 tools/audit.py  (после tools/build.py)"""
import re, json, sys, pathlib
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = "https://sharkong.kz"
PAGES = {"ru": ("index.html", "/"), "kk": ("kk/index.html", "/kk/"), "en": ("en/index.html", "/en/")}
issues, notes = [], []
def bad(level, page, msg): issues.append((level, page, msg))

class P(HTMLParser):
    def __init__(self):
        super().__init__(); self.tags=[]; self.stack=[]; self.text=[]; self.ids=[]; self.imgs=[]; self.links=[]; self.metas=[]; self.link_tags=[]; self.scripts=[]; self.headings=[]; self.title=None; self._t=None; self._h=None; self.jsonld=[]; self._j=False; self.lang=None; self.in_script=False
    def handle_starttag(self, tag, attrs):
        a=dict(attrs); self.tags.append(tag)
        if tag=="html": self.lang=a.get("lang")
        if "id" in a: self.ids.append(a["id"])
        if tag=="meta": self.metas.append(a)
        if tag=="link": self.link_tags.append(a)
        if tag=="img": self.imgs.append(a)
        if tag=="a" and "href" in a: self.links.append(a)
        if tag=="script":
            self.in_script=True
            if a.get("type")=="application/ld+json": self._j=True; self.jsonld.append("")
            else: self.scripts.append(a)
        if tag=="title": self._t=""
        if re.fullmatch(r"h[1-6]",tag): self._h=[int(tag[1]),""]
    def handle_endtag(self, tag):
        if tag=="title": self.title=self._t; self._t=None
        if tag=="script": self.in_script=False; self._j=False
        if self._h and tag==f"h{self._h[0]}": self.headings.append((self._h[0],self._h[1].strip())); self._h=None
    def handle_data(self, d):
        if self._t is not None: self._t+=d
        if self._j: self.jsonld[-1]+=d
        elif not self.in_script:
            self.text.append(d)
            if self._h: self._h[1]+=d

def parse(path):
    p=P(); p.feed((ROOT/path).read_text(encoding="utf-8")); return p

def meta(p, key, attr="name"):
    for m in p.metas:
        if m.get(attr)==key: return m.get("content")

stats={}
for lang,(f,url) in PAGES.items():
    raw=(ROOT/f).read_text(encoding="utf-8"); p=parse(f); pg=lang
    full=SITE+url
    # head
    if p.lang!=lang: bad("ERR",pg,f"html lang={p.lang}")
    t=p.title or ""
    if not 25<=len(t)<=70: bad("WARN",pg,f"title length {len(t)}: {t}")
    d=meta(p,"description") or ""
    if not 70<=len(d)<=165: bad("WARN",pg,f"description length {len(d)}")
    canon=[l["href"] for l in p.link_tags if l.get("rel")=="canonical"]
    if canon!=[full]: bad("ERR",pg,f"canonical {canon} != {full}")
    hl={l["hreflang"]:l["href"] for l in p.link_tags if l.get("rel")=="alternate" and "hreflang" in l}
    exp={"ru":SITE+"/","kk":SITE+"/kk/","en":SITE+"/en/","x-default":SITE+"/"}
    if hl!=exp: bad("ERR",pg,f"hreflang {hl}")
    for k in ("og:title","og:description","og:image","og:url","og:type","og:locale"):
        if not meta(p,k,"property"): bad("ERR",pg,f"missing {k}")
    if meta(p,"og:url","property")!=full: bad("ERR",pg,"og:url != canonical")
    if not meta(p,"viewport"): bad("ERR",pg,"no viewport")
    rb=meta(p,"robots") or ""
    if "noindex" in rb: bad("ERR",pg,"noindex on a public page")
    # headings
    h1=[h for h in p.headings if h[0]==1]
    if len(h1)!=1: bad("ERR",pg,f"{len(h1)} h1")
    last=0
    for lv,tx in p.headings:
        if last and lv>last+1: bad("WARN",pg,f"heading jump h{last}->h{lv}: {tx[:40]}")
        if not tx: bad("ERR",pg,f"empty h{lv}")
        last=lv
    # ids, links
    dup={i for i in p.ids if p.ids.count(i)>1}
    if dup: bad("ERR",pg,f"duplicate ids {dup}")
    for a in p.links:
        h=a["href"]
        if h.startswith("#") and len(h)>1 and h[1:] not in p.ids: bad("ERR",pg,f"broken anchor {h}")
        elif h.startswith("/") and not h.startswith("//"):
            path=h.split("#")[0].split("?")[0]
            fp=ROOT/path.lstrip("/")
            if not (fp.is_file() or (fp/"index.html").is_file() or path=="/"): bad("ERR",pg,f"broken internal link {h}")
        elif h.startswith("http") and a.get("target")=="_blank" and "noopener" not in a.get("rel",""): bad("WARN",pg,f"_blank without noopener {h}")
    # images
    for im in p.imgs:
        s=im.get("src","")
        if "alt" not in im: bad("ERR",pg,f"img without alt {s}")
        elif im["alt"]=="" and "/assets/d-" in s: bad("WARN",pg,f"empty alt on content img {s}")
        if s.startswith("/") and not (ROOT/s.lstrip("/")).is_file(): bad("ERR",pg,f"missing image file {s}")
        if not (im.get("width") and im.get("height")): bad("WARN",pg,f"img without width/height {s}")
    first=[im for im in p.imgs][:3]
    for im in p.imgs:
        if "/assets/" in im.get("src","") and im.get("loading") not in ("lazy","eager") and im.get("fetchpriority")!="high" and "logo-mark" not in im["src"]: bad("WARN",pg,f"non-lazy image {im['src']}")
    # json-ld
    types=[]
    for blob in p.jsonld:
        try:
            j=json.loads(blob); g=j.get("@graph",[j]); types+= [x.get("@type") for x in g]
            faq=[x for x in g if x.get("@type")=="FAQPage"]
            if faq:
                n=len(faq[0]["mainEntity"]); dom=raw.count('class="qa rv"')
                if n!=dom: bad("ERR",pg,f"FAQ schema {n} != DOM {dom}")
            if any("review" in json.dumps(x).lower() or "aggregateRating" in json.dumps(x) for x in g): bad("ERR",pg,"review/rating markup present")
        except Exception as e: bad("ERR",pg,f"bad JSON-LD {e}")
    for need in ("HomeAndConstructionBusiness","WebSite","WebPage","FAQPage"):
        if need not in types: bad("ERR",pg,f"JSON-LD lacks {need}")
    # leftovers
    if "{{" in raw: bad("ERR",pg,"template placeholder left")
    if "data-i18n" in raw: bad("WARN",pg,"data-i18n leftovers")
    if "—" in raw or "–" in raw: bad("WARN",pg,"dash characters on page")
    body=" ".join(p.text); body=re.sub(r"\s+"," ",body)
    if lang=="en" and re.search(r"[А-Яа-яЁё]", body): bad("ERR",pg,"Cyrillic on EN page: "+re.search(r".{20}[А-Яа-яЁё]+.{10}",body).group(0))
    if lang=="ru" and re.search(r"\b(Request a quote|Estimate cost)\b", body): bad("ERR",pg,"English CTA on RU page")
    kz_cyr=re.search(r"\b(Оставить заявку|Рассчитать смету)\b", body)
    if lang=="kk" and kz_cyr: bad("ERR",pg,"Russian CTA on KZ page")
    # render blocking
    blocking=[l["href"] for l in p.link_tags if l.get("rel")=="stylesheet" and l.get("media")!="print"]
    blocking=[b for b in blocking if "sharkong" in b or b.startswith("/")]
    if len(blocking)>1: bad("WARN",pg,f"{len(blocking)} render-blocking stylesheets")
    for s in p.scripts:
        if s.get("src") and not ("defer" in s or "async" in s): bad("WARN",pg,f"blocking script {s['src']}")
    words=len(body.split())
    kw = "алматы" if lang!="en" else "almaty"
    for label,val in (("title",t),("description",d),("h1"," ".join(h[1] for h in h1))):
        if kw not in val.lower() and not (lang=="kk" and "алматы" in val.lower()): bad("WARN",pg,f"keyword '{kw}' missing in {label}")
    stats[lang]=dict(html_kb=round(len(raw)/1024,1),words=words,h2=len([h for h in p.headings if h[0]==2]),imgs=len(p.imgs),jsonld=types)

# sitemap / robots / misc
sm=(ROOT/"sitemap.xml").read_text()
for l,(f,u) in PAGES.items():
    if f"<loc>{SITE}{u}</loc>" not in sm: bad("ERR","sitemap",f"missing {u}")
rb=(ROOT/"robots.txt").read_text()
if "Sitemap: https://sharkong.kz/sitemap.xml" not in rb: bad("ERR","robots","no sitemap line")
if "Disallow: /\n" in rb: bad("ERR","robots","site disallowed")
nf=(ROOT/"404.html").read_text()
if "noindex" not in nf: bad("ERR","404","no noindex")
try: json.loads((ROOT/"manifest.webmanifest").read_text())
except Exception as e: bad("ERR","manifest",str(e))
for f in ("llms.txt",".htaccess","assets/og.jpg","assets/icon.png"):
    if not (ROOT/f).exists(): bad("ERR","files",f"missing {f}")
size=sum(f.stat().st_size for f in (ROOT/"assets").glob("*"))
notes.append(f"assets total {round(size/1024)} KB")
big=[f.name for f in (ROOT/"assets").glob("*") if f.stat().st_size>250*1024]
if big: bad("WARN","assets",f"heavy files {big}")

errs=[i for i in issues if i[0]=="ERR"]; warns=[i for i in issues if i[0]=="WARN"]
print(json.dumps(stats,ensure_ascii=False)); print(notes)
for lv,pg,m in issues: print(f"{lv:4} [{pg}] {m}")
print(f"\n{len(errs)} errors, {len(warns)} warnings")
sys.exit(1 if errs else 0)
