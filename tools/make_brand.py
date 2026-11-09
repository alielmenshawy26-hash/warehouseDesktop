"""بيجهّز ملف client_brand.py لعميل معيّن قبل الـ build (الاسم والشعار بيتقفلوا جوه البرنامج).

الاستخدام:  python tools/make_brand.py farahat
كل عميل ليه فولدر في clients/<slug>/ فيه:
  client.json  →  {"company": "اسم الشركة", "tagline": "تحت الاسم",
                   "features": ["production"],            ← اختياري: شاشات زيادة للعميل ده (production = الإنتاج للأفران)
                   "theme": {"--navy": "#3b2414", ...}}    ← اختياري: ألوان البرنامج للعميل ده (متغيرات app.css)
  logo.png     →  الشعار (PNG أو JPG) — اختياري، من غيره بياخد الشعار العام
"""
import base64, json, os, sys
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

def main(slug):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    d = os.path.join(root, "clients", slug)
    if not os.path.isdir(d): raise SystemExit(f"مفيش عميل اسمه {slug} في clients/")
    cfg = json.load(open(os.path.join(d, "client.json"), encoding="utf-8"))
    if not (cfg.get("company") or "").strip(): raise SystemExit("client.json لازم يكون فيه company")
    logo = ""
    for name in ("logo.png", "logo.jpg", "logo.jpeg"):
        p = os.path.join(d, name)
        if os.path.exists(p):
            raw = open(p, "rb").read()
            if not (raw[:8] == b"\x89PNG\r\n\x1a\n" or raw[:3] == b"\xff\xd8\xff"): raise SystemExit(f"{name} مش صورة PNG/JPG")
            logo = base64.b64encode(raw).decode(); break
    out = os.path.join(root, "client_brand.py")
    with open(out, "w", encoding="utf-8") as f:
        f.write("# ملف بيتعمل لوحده وقت الـ build (tools/make_brand.py) — متعدّلوش بإيدك\n")
        f.write(f"BRAND_SLUG = {slug!r}\nBRAND_COMPANY = {cfg['company'].strip()!r}\nBRAND_TAGLINE = {(cfg.get('tagline') or '').strip()!r}\nBRAND_LOGO_B64 = {logo!r}\n")
        theme = {k: str(v) for k, v in (cfg.get("theme") or {}).items() if str(k).startswith("--")}
        f.write(f"BRAND_THEME = {theme!r}\nBRAND_FEATURES = {list(cfg.get('features') or [])!r}\n")
    print(f"✔ client_brand.py جاهز: {cfg['company']} ({slug})" + (" + شعار" if logo else " (الشعار العام)"))

if __name__ == "__main__":
    if len(sys.argv) != 2: raise SystemExit(__doc__)
    main(sys.argv[1])
