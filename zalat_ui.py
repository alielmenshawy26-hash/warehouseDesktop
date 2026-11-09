# -*- coding: utf-8 -*-
"""
سيستم المخازن والمبيعات — النسخة الأوفلاين (نفس كود زلط).
نفس قاعدة البيانات ونفس الحسابات بتاعة Warehouse_app.py — الشكل بس اللي جديد (HTML/CSS/JS جوه نافذة WebView2).
التشغيل:  python zalat_ui.py            → نافذة البرنامج
          python zalat_ui.py --serve 8765 → للتجربة من المتصفح (http://127.0.0.1:8765)
"""
import os, sys, json, threading, traceback, subprocess, time
from datetime import date, timedelta

import Warehouse_app as W

UI_VERSION = "تجريبي"


def _base_dir():
    if getattr(sys, "frozen", False): return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


UI_DIR = os.path.join(_base_dir(), "ui")


DAYLOCK = "__DAYLOCK__"     # الواجهة بتطلب باسوورد المحاسب/المالك وتعيد المحاولة

# ---------- الصلاحيات: كل يوزر ليه الشاشات المسموحله بيها ----------
ALL_SCREENS = ["home", "inv:مبيعات", "inv:مشتريات", "inv:مرتجع مبيعات", "inv:مرتجع مشتريات", "log", "vch:new", "vch:log",
               "acc:statement", "acc:balances", "acc:cash", "acc:subcash", "par:list", "itm:list", "itm:stock", "itm:sales", "itm:buys", "itm:damaged",
               "smp:items", "smp:out", "smp:in", "emp:list", "emp:att", "emp:attlog", "emp:attreq", "emp:repreq", "emp:veh",
               "rep:daily", "rep:monthly", "rep:profit", "rep:reps", "rep:targets", "rep:log", "req", "set:main", "acc:assets", "prd:new", "prd:log", "prd:sell"]
OWNER_ONLY_SCREENS = {"rep:profit", "set:users", "acc:assets", "rep:monthly"}
DEFAULT_SCREENS = {
    W.ROLE_ACC: [k for k in ALL_SCREENS if k not in OWNER_ONLY_SCREENS],
    W.ROLE_REP: ["home", "inv:مبيعات", "log", "vch:new", "vch:log", "acc:statement", "acc:balances", "req"],
}
_INV = ["inv:مبيعات", "inv:مشتريات", "inv:مرتجع مبيعات", "inv:مرتجع مشتريات"]
# كل أمر بيتسمح لو اليوزر عنده شاشة من الشاشات دي (الأوامر اللي مش هنا مسموحة لأي حد داخل)
METHOD_SCREENS = {}
for _keys, _methods in [
    (["home"], "dashboard expected mark_called unmark_called hide_expected unhide_expected"),
    (_INV + ["log", "home"], "invoice_setup save_invoice invoice print_invoice invoice_for_edit delete_invoice"),
    (["log", "home"], "invoices"),
    (["vch:new", "vch:log"], "voucher_setup save_voucher voucher_preview add_expense_cat delete_expense_cat rename_expense_cat vouchers voucher delete_voucher print_receipt"),
    (["acc:statement", "acc:balances"], "parties_list statement print_statement payment_detail"),
    (["acc:balances"], "balances delete_parties print_balances"),
    (["acc:cash"], "cash add_cash_move delete_cash_move cash_count cash_count_setup cash_count_save cash_count_print cash_count_pdf cash_transfer_add cash_transfer_delete"),
    (["acc:subcash"], "subcash save_subcash delete_subcash"),
    (["par:list"], "parties_full party_get save_party"),
    (["itm:list", "itm:stock", "itm:sales", "itm:buys"], "item_invoices"),
    (["itm:list"], "items_full save_item delete_item"),
    (["itm:stock"], "stock save_price print_stock_count"),
    (["itm:sales", "itm:buys"], "items_flow"),
    (["itm:damaged"], "damaged save_damaged delete_damaged"),
    (["prd:new", "prd:log"], "production_setup save_production production_list delete_production print_production"),
    (["prd:sell"], "sell_setup quick_sale"),
    (["smp:items", "smp:out", "smp:in"], "sample_items save_sample_item delete_sample_item sample_moves samples save_sample delete_sample"),
    (["rep:profit"], "profit profit_compare"),
    (["rep:reps"], "reps_report rep_detail"),
    (["rep:targets"], "targets set_target clear_target target_items set_target_items"),
    (["rep:log"], "activity_log"),
    (["rep:daily", "home"], "daily_report print_daily"),
    (["rep:daily"], "daily_trend"),
    (["emp:list"], "employees save_employee toggle_employee delete_employee salary_suggest pay_salary pay_advance pay_commission workers pay_workers add_loading loading_logs delete_loading update_loading employee_statement"),
    (["emp:att"], "attendance_day save_attendance"),
    (["emp:attlog"], "attendance_log delete_attendance"),
    (["emp:attreq", "emp:repreq"], "requests decide_request"),
    (["emp:veh"], "vehicles save_vehicle save_vehicle_log delete_vehicle_log delete_vehicle"),
    (["set:main"], "settings_get settings_save set_logo trust_save print_trust_form"),
    (["req"], "req_list req_decide inv_request_get req_counts"),
    (["acc:assets"], "assets_report save_asset assets_adopt"),
    (["rep:monthly"], "monthly_report monthly_print"),
]:
    for _m in _methods.split(): METHOD_SCREENS[_m] = set(_keys)
NO_REP = {"close_day", "day_unlock", "req_decide", "inv_request_get"}       # المندوب مايقفلش اليوم ومايفتحش أيام مقفولة


def user_screens(r):
    """الشاشات المسموحة ليوزر (من صف جدول users)."""
    if r["role"] == W.ROLE_OWNER: return ALL_SCREENS + ["set:users"]
    raw = (r["screens"] if "screens" in r.keys() else "") or ""
    try: lst = json.loads(raw) if raw else None
    except ValueError: lst = None
    base = DEFAULT_SCREENS.get(r["role"], DEFAULT_SCREENS[W.ROLE_ACC]) if lst is None else lst
    if r["role"] == W.ROLE_ACC: base = list(base) + ["req"]       # المحاسب دايمًا بيوافق على طلبات المناديب (فواتير وسندات وحضور)
    return [k for k in ALL_SCREENS if k in base and k not in OWNER_ONLY_SCREENS]


PAY_PERIODS = ["يومي", "أسبوعي", "كل أسبوعين", "شهري"]
PAY_METHODS = ["كاش", "انستاباي", "فودافون كاش", "تحويل بنكي"]
ASSET = "أصول"      # حسابات أصول: أرباح الملاك المسحوبة، تريسكل، كمبيوتر ... (مش عملاء)
DRAWER = "درج"


def owners_list(c):
    r = c.execute("SELECT COALESCE(owners_list,'') FROM settings WHERE id=1").fetchone()
    raw = (r[0] if r else "") or ""
    return [x.strip() for x in raw.replace(",", "،").split("،") if x.strip()]


def holders_setup(c):
    """اللي ممكن الفلوس تبقى معاهم: الملاك + المحاسبين + الدرج (والمندوب بيتحدد من خانة المندوب)."""
    accs = [r[0] for r in c.execute("SELECT username FROM users WHERE role=? AND active=1 ORDER BY username", (W.ROLE_ACC,)).fetchall()]
    return {"owners": owners_list(c), "accountants": accs, "drawer": DRAWER}
PERIOD_DAYS = {"أسبوعي": 7, "كل أسبوعين": 14}

def pay_period_of(r):
    """طريقة القبض: لو مش متحددة = يومي للعامل وشهري لغيره."""
    p = (r["pay_period"] if "pay_period" in r.keys() else "") or ""
    return p if p in PAY_PERIODS else ("يومي" if (r["kind"] or "") == "عامل" else "شهري")

class _Quiet:
    """بديل لشاشة السيستم القديم: أي self.status.config(...) وغيرها بتتجاهل بهدوء."""
    def __init__(self, **kw): self.__dict__.update(kw)
    def __getattr__(self, name): return _Quiet()
    def __call__(self, *a, **k): return None


class UIError(Exception):
    pass


def _today(): return date.today().isoformat()


def _r2(x): return round(float(x or 0), 2)


class Api:
    """كل دالة هنا بتتنادي من الواجهة (JavaScript) وبترجع JSON."""

    # ---------- التشغيل والدخول ----------
    def boot(self):
        try:
            with W.db() as c: c.execute("SELECT 1").fetchone()
        except Exception as e:
            return {"db_error": (str(e) if isinstance(e, W.DBUnavailable) else W.pg_error_text(e)) + f"\n({W.server_label()})"}
        W.init_db()
        try:
            if not os.path.exists(W.auto_backup_path()): W.auto_backup()      # نسخة احتياطية يومية (زي السيستم القديم)
        except Exception: W.write_error_log("new-ui backup: " + traceback.format_exc())
        with W.db() as c:
            n = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            st = c.execute("SELECT * FROM settings WHERE id=1").fetchone()
        return {"has_users": n > 0, "company": ((st["company"] or "").strip() if st else "") or W.DEFAULT_COMPANY, "tagline": ((st["tagline"] or "").strip() if st else ""),
                "english": (st["english"] if st else "") or "", "logo": W.logo_data_uri(), "version": W.version_text(), "build": W.APP_BUILD,
                "theme": W.BRAND_THEME, "features": W.BRAND_FEATURES,
                "server": W.server_label(), "today": _today()}

    def login(self, username, password):
        with W.db() as c:
            r = c.execute("SELECT * FROM users WHERE username=? AND active=1", ((username or "").strip(),)).fetchone()
        if not r or not W.check_pw(password or "", r["pw_hash"], r["salt"]):
            raise UIError("اسم المستخدم أو كلمة السر غير صحيحة")
        if r["role"] == W.ROLE_REP and not (r["emp_id"] if "emp_id" in r.keys() else None):
            raise UIError("اليوزر ده «مندوب» ولسه مش مربوط بمندوب من الموظفين — المالك يربطه من شاشة المستخدمين")
        W.CURRENT_USER.clear()
        W.CURRENT_USER.update(id=r["id"], username=r["username"], role=r["role"], screens=user_screens(r), emp_id=(r["emp_id"] if "emp_id" in r.keys() else None))
        with W.db() as c: W.log(c, "تسجيل دخول", f"{r['username']} ({r['role']}) — الواجهة الجديدة")
        return self.me()

    def me(self):
        return {"id": W.CURRENT_USER.get("id"), "username": W.CURRENT_USER.get("username"), "role": W.CURRENT_USER.get("role"), "owner": W.is_owner(),
                "screens": W.CURRENT_USER.get("screens") or [], "rep": W.CURRENT_USER.get("role") == W.ROLE_REP}

    def logout(self):
        W.CURRENT_USER.clear(); W.CURRENT_USER.update(id=None, username="", role=""); W.DAY_OK["until"] = 0.0
        return True

    def _need_login(self):
        if not W.CURRENT_USER.get("id"): raise UIError("لازم تسجّل دخول الأول")

    # ---------- تقفيل اليوم ----------
    def _day(self, *dates):
        msg = W.check_day(*dates)
        if msg: raise UIError(DAYLOCK + msg)

    def day_unlock(self, pw):
        self._need_login()
        who = W.verify_day_password(pw)
        if not who: raise UIError("كلمة السر غلط — لازم باسوورد المحاسب أو المالك")
        W.DAY_OK["until"] = time.time() + 600
        with W.db() as c: W.log(c, "فتح يوم مقفول", f"تعديل في يوم {W.day_closed(c)} أو قبله — بباسوورد {who}")
        return True

    def close_day(self):
        """زرار «تقفيل اليوم»: جرد الخزنة PDF + نسخة احتياطية + قفل التعديل على اليوم."""
        self._need_login()
        day = _today(); steps = []
        # 1) جرد الخزنة: آخر جرد النهارده يتحفظ PDF مع النسخ
        r_cnt, _st = self._count_row(day=day)
        if r_cnt:
            try: pdf = self.cash_count_pdf(r_cnt["id"], to_desktop=False)
            except Exception: pdf = ""
            steps.append({"ok": bool(pdf), "t": ("جرد الخزنة اتحفظ PDF: " + pdf) if pdf else "جرد الخزنة: الـ PDF ماتعملش"})
        else: steps.append({"ok": False, "t": "مفيش جرد خزنة النهارده — اعمله من «الخزنة ← جرد الخزنة» وبعدين اقفل اليوم تاني لو عايزه يتحفظ"})
        # 3) نسخة احتياطية في المجلد المختار
        path, warn = W.backup_copy("close")
        if path and not warn: steps.append({"ok": True, "t": "نسخة احتياطية جديدة اتعملت (النسخ القديمة زي ما هي): " + path})
        elif path: steps.append({"ok": False, "t": warn})
        else: steps.append({"ok": False, "t": warn or "النسخة الاحتياطية فشلت"})
        # 4) قفل التعديل
        with W.db() as c:
            c.execute("UPDATE settings SET day_closed=? WHERE id=1", (day,))
            W.log(c, "تقفيل اليوم", f"يوم {day} — " + " • ".join(("✔ " if s["ok"] else "✖ " if s["ok"] is False else "— ") + s["t"] for s in steps))
        W.DAY_OK["until"] = 0.0
        steps.append({"ok": True, "t": f"يوم {day} اتقفل — أي تعديل في فواتيره أو سنداته محتاج باسوورد المحاسب أو المالك"})
        return {"day": day, "steps": steps}

    # ---------- الرئيسية ----------
    def dashboard(self, day=None):
        self._need_login()
        day = W.check_date(day or _today())
        with W.db() as c:
            inv = {}
            for k in W.KINDS:
                r = c.execute(f"SELECT COUNT(*) n, COALESCE(SUM({W.NET_SQL}),0) t, COALESCE(SUM({W.INV_TONS_SQL}),0) tons, COALESCE(SUM({W.INV_BAGS_SQL}),0) bags "
                              "FROM invoices i WHERE i.kind=? AND i.inv_date=?", (k, day)).fetchone()
                inv[k] = {"n": r["n"], "total": _r2(r["t"]), "tons": _r2(r["tons"]), "bags": _r2(r["bags"])}
            rows = c.execute(f"SELECT i.id,i.number,i.kind,i.created_at,i.pay_type,p.name party,e.name rep,{W.NET_SQL} net, i.printed_at "
                             "FROM invoices i LEFT JOIN parties p ON p.id=i.party_id LEFT JOIN employees e ON e.id=i.rep_id "
                             "WHERE i.inv_date=? ORDER BY i.created_at DESC, i.id DESC", (day,)).fetchall()
            top = c.execute("SELECT MIN(l.item_name) name, MIN(COALESCE(l.unit,'')) unit, "
                            "SUM(CASE i.kind WHEN 'مبيعات' THEN l.qty ELSE -l.qty END) q, SUM(CASE i.kind WHEN 'مبيعات' THEN l.qty*l.price ELSE -l.qty*l.price END) a "
                            "FROM invoice_lines l JOIN invoices i ON i.id=l.invoice_id WHERE i.kind IN ('مبيعات','مرتجع مبيعات') AND i.inv_date=? "
                            "GROUP BY l.item_id ORDER BY a DESC", (day,)).fetchall()
            col = c.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE kind='تحصيل' AND pay_date=?", (day,)).fetchone()[0]
            exp = c.execute("SELECT COALESCE(SUM(amount),0) FROM expenses WHERE exp_date=?", (day,)).fetchone()[0]
            cash = W.cash_balance(c)
        out = {
            "day": day, "closed": W.day_closed(), "inv": inv, "collections": _r2(col), "expenses": _r2(exp), "cash": _r2(cash),
            "count": sum(v["n"] for v in inv.values()),
            "rows": [{"id": r["id"], "number": r["number"], "kind": r["kind"], "time": W.fmt_time(r["created_at"]), "pay": r["pay_type"] or "",
                      "party": r["party"] or "", "rep": r["rep"] or "", "net": _r2(r["net"]), "printed": bool(r["printed_at"])} for r in rows],
            "top": [{"name": r["name"], "unit": r["unit"], "qty": _r2(r["q"]), "amount": _r2(r["a"])} for r in top if (r["a"] or 0) > 0][:6],
        }
        if W.is_owner():
            ps = W.profit_summary(day, day)
            out["profit"] = {"gross": _r2(ps["gross"]), "net": _r2(ps["actual"])}
        return out

    def today_bar(self):
        """الشريط اللي تحت في كل الشاشات: ملخص النهارده."""
        self._need_login()
        day = _today()
        with W.db() as c:
            r = {k: c.execute(f"SELECT COUNT(*), COALESCE(SUM({W.NET_SQL}),0) FROM invoices i WHERE i.kind=? AND i.inv_date=?", (k, day)).fetchone() for k in W.KINDS}
            col = c.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE kind='تحصيل' AND pay_date=?", (day,)).fetchone()[0]
            exp = c.execute("SELECT COALESCE(SUM(amount),0) FROM expenses WHERE exp_date=?", (day,)).fetchone()[0]
        return {"count": sum(v[0] for v in r.values()), "sales": _r2(r["مبيعات"][1]), "buys": _r2(r["مشتريات"][1]), "n_buys": r["مشتريات"][0],
                "ret": _r2(r["مرتجع مبيعات"][1]), "collections": _r2(col), "expenses": _r2(exp), "closed": W.day_closed() == day}

    def daily_report(self, day=None):
        self._need_login()
        day = W.check_date(day or _today())
        return {"day": day, "rows": [list(r) for r in W.daily_rows(day)]}

    def daily_trend(self, d_from=None, d_to=None):
        """للعرض بس جنب التقرير اليومي: كل يوم في الفترة — فواتير ومبيعات وتحصيلات (والربح للمالك بس)."""
        self._need_login()
        from datetime import date as _d, timedelta as _td
        end = _d.fromisoformat(W.check_date(d_to or _today()))
        start = _d.fromisoformat(W.check_date(d_from)) if d_from else end - _td(days=13)
        if start > end: start, end = end, start
        if (end - start).days > 92: start = end - _td(days=92)             # أقصى 3 شهور
        E = W.EFFECTIVE_DATE_SQL; a, b = start.isoformat(), end.isoformat()
        with W.db() as c:
            inv = {}
            for d, kind, cnt, t in c.execute(f"SELECT {E} d, i.kind, COUNT(*), COALESCE(SUM({W.NET_SQL}),0) FROM invoices i WHERE i.kind IN ('مبيعات','مرتجع مبيعات') AND {E} BETWEEN ? AND ? GROUP BY d, i.kind", (a, b)).fetchall():
                x = inv.setdefault(d, [0, 0.0]); x[0] += cnt if kind == "مبيعات" else 0; x[1] += float(t) if kind == "مبيعات" else -float(t)
            col = {r[0]: float(r[1]) for r in c.execute("SELECT pay_date, COALESCE(SUM(amount),0) FROM payments WHERE kind='تحصيل' AND pay_date BETWEEN ? AND ? GROUP BY pay_date", (a, b)).fetchall()}
            own = W.CURRENT_USER.get("role") == W.ROLE_OWNER
            prof = {}
            if own:                       # إجمالي الربح لكل يوم في لفة واحدة (نفس حساب تقرير الأرباح: بيع − تكلفة FIFO − خصومات)
                f = W.fifo_engine(c)
                for d, kind, lid, q, pr in c.execute(f"SELECT {E} d, i.kind, l.id, l.qty, l.price FROM invoice_lines l JOIN invoices i ON i.id=l.invoice_id "
                                                     f"WHERE i.kind IN ('مبيعات','مرتجع مبيعات') AND {E} BETWEEN ? AND ?", (a, b)).fetchall():
                    v = float(q or 0) * (float(pr or 0) - (f["line"].get(lid, 0.0) if lid else 0.0))
                    prof[d] = prof.get(d, 0.0) + (v if kind == "مبيعات" else -v)
                for d, kind, ds in c.execute(f"SELECT {E} d, i.kind, COALESCE(SUM(i.discount),0) FROM invoices i WHERE i.kind IN ('مبيعات','مرتجع مبيعات') AND {E} BETWEEN ? AND ? GROUP BY d, i.kind", (a, b)).fetchall():
                    prof[d] = prof.get(d, 0.0) - (float(ds) if kind == "مبيعات" else -float(ds))
                for d, dv in c.execute("SELECT pay_date, COALESCE(SUM(amount),0) FROM payments WHERE kind=? AND pay_date BETWEEN ? AND ? GROUP BY pay_date", (W.DISC_KIND, a, b)).fetchall():
                    prof[d] = prof.get(d, 0.0) - float(dv)
        out = []
        names = ["الاتنين", "التلات", "الأربع", "الخميس", "الجمعة", "السبت", "الحد"]
        d = end
        while d >= start:
            ds = d.isoformat()
            r = {"date": ds, "day": names[d.weekday()], "n": inv.get(ds, [0, 0])[0], "sales": _r2(inv.get(ds, [0, 0.0])[1]), "collect": _r2(col.get(ds, 0.0))}
            if own: r["profit"] = _r2(prof.get(ds, 0.0))
            out.append(r); d -= _td(days=1)
        return {"rows": out, "profit": own, "from": a, "to": b}

    # ---------- العملاء المتوقعين (الجرس) ----------
    def expected(self):
        self._need_login()
        with W.db() as c: rows = W.expected_customers(c)
        return [{"id": r["id"], "name": r["name"], "phone": r["phone"], "rep": r["rep"], "every": _r2(r["every"]), "last": r["last"],
                 "late": r["late"], "tons": _r2(r["tons"]), "amount": _r2(r["amount"]), "called": r["called"], "note": r["note"]} for r in rows]

    def mark_called(self, pid, note=""):
        self._need_login()
        with W.db() as c:
            name = c.execute("SELECT name FROM parties WHERE id=?", (pid,)).fetchone()[0]
            c.execute("INSERT INTO followups(party_id,f_date,note,by_user,created_at) VALUES(?,?,?,?,?)", (pid, _today(), (note or "").strip(), W.CURRENT_USER.get("username", ""), W.now_ts()))
            W.log(c, "متابعة عميل", f"{name}: اتكلم معاه" + (f" — {note.strip()}" if (note or "").strip() else ""))
        return self.expected()

    def unmark_called(self, pid):
        self._need_login()
        with W.db() as c: c.execute("DELETE FROM followups WHERE party_id=? AND f_date=?", (pid, _today()))
        return self.expected()

    def hide_expected(self, pid):
        self._need_login()
        with W.db() as c:
            name = c.execute("SELECT name FROM parties WHERE id=?", (pid,)).fetchone()[0]
            c.execute("UPDATE parties SET exp_hidden=? WHERE id=?", (_today(), pid))
            W.log(c, "متابعة عميل", f"{name}: اتشال من قايمة المتوقعين")
        return self.expected()

    def unhide_expected(self, pid):
        self._need_login()
        with W.db() as c: c.execute("UPDATE parties SET exp_hidden=NULL WHERE id=?", (pid,))
        return self.expected()

    # ---------- الفاتورة ----------
    def invoice_setup(self, kind, day=None):
        """كل اللي شاشة الفاتورة محتاجاه: العملاء، الأصناف (بالسعر المناسب)، المناديب، الرقم الجاي."""
        self._need_login()
        if kind not in W.KINDS: raise UIError("نوع فاتورة غلط")
        day = W.check_date(day or _today())
        sale_side = kind in ("مبيعات", "مرتجع مبيعات")
        with W.db() as c:
            parties = c.execute("SELECT id,name,address,phone,rep_id,kind FROM parties ORDER BY name").fetchall()
            items = c.execute("SELECT id,code,name,unit,buy_price,sell_price FROM items ORDER BY name").fetchall()
            stock = W.stock_map(c)
            reps = W.rep_lookup(c) if kind == "مبيعات" else {}
            vehicles = [{"id": v[0], "label": v[1] + (f" — {v[2]}" if v[2] else "")} for v in c.execute("SELECT id,name,COALESCE(driver,'') FROM vehicles WHERE COALESCE(active,1)=1 ORDER BY name").fetchall()] if kind == "مبيعات" else []
        return {"vehicles": vehicles, "delivery": kind == "مبيعات",
            "kind": kind, "number": W.next_no(kind, day), "date": day, "paytypes": kind in W.PAYTYPE_KINDS, "paid_label": W.PAID_LABEL[kind],
            "parties": [{"id": p["id"], "label": W.party_label(p), "rep_id": p["rep_id"], "kind": p["kind"] or ""} for p in parties],
            "items": [{"id": it["id"], "label": W.item_label(it), "name": it["name"], "unit": it["unit"] or "", "code": it["code"] or "",
                       "price": _r2(it["sell_price"] if sale_side else it["buy_price"]), "stock": _r2(stock.get(it["id"], 0))} for it in items],
            "reps": [{"id": v, "label": k} for k, v in reps.items()],
            "out_side": W.SIGN[kind] < 0, "returns_damaged": kind == "مرتجع مبيعات", "show_profit": kind == "مبيعات" and W.is_owner(),
        }

    def next_number(self, kind, day):
        self._need_login()
        return W.next_no(kind, W.check_date(day))

    def item_info(self, kind, item_id, party_id=None):
        """رصيد الصنف، المحجوز، وآخر سعر للعميل/المورد ده."""
        self._need_login()
        sale_side = kind in ("مبيعات", "مرتجع مبيعات")
        out = {}
        with W.db() as c:
            if item_id:
                out["stock"] = _r2(W.stock_of(c, item_id)); out["available"] = _r2(min(W.stock_of(c, item_id), W.stock_of(c, item_id, None)))
                out["reserved"] = _r2(W.reserved_of(c, item_id))
            if party_id: out["balance"] = _r2(W.party_balance(c, party_id))
            if item_id and party_id:
                r = c.execute("SELECT l.price,i.inv_date,i.number FROM invoice_lines l JOIN invoices i ON i.id=l.invoice_id "
                              "WHERE i.kind=? AND i.party_id=? AND l.item_id=? ORDER BY i.inv_date DESC,i.id DESC LIMIT 1",
                              ("مبيعات" if sale_side else "مشتريات", party_id, item_id)).fetchone()
                out["last"] = {"price": _r2(r["price"]), "date": r["inv_date"], "number": r["number"]} if r else None
        return out

    def party_info(self, party_id):
        self._need_login()
        with W.db() as c: return {"balance": _r2(W.party_balance(c, party_id))}

    def lines_profit(self, lines, edit_id=None):
        """ربح الفاتورة (للمالك بس، مش بيتطبع)."""
        self._need_login()
        if not W.is_owner(): return None
        with W.db() as c: pre = W.fifo_preview(c, [(l["item_id"], float(l["qty"])) for l in lines], skip_invoice=edit_id)
        out = []
        for i, l in enumerate(lines):
            cost = pre[i] if l.get("item_id") else 0.0
            out.append({"cost": _r2(cost), "profit": _r2(float(l["qty"]) * (float(l["price"]) - cost))})
        return out

    def verify_owner(self, password):
        who = W.verify_owner_password(password)
        if not who: raise UIError("كلمة سر المالك غير صحيحة")
        return who

    def save_invoice(self, p, credit_pw=None, neg_pw=None, do_print=False):
        """p = {kind, party_id, number, date, due, discount, paid, pay_type, notes, rep_id, lines:[{item_id,name,unit,qty,price,damaged}]}"""
        self._need_login()
        lines = [{"item_id": int(l["item_id"]), "name": l["name"], "unit": l.get("unit") or "", "qty": float(l["qty"]), "price": float(l["price"]),
                  "damaged": 1 if l.get("damaged") else 0} for l in (p.get("lines") or [])]
        od = None
        if p.get("edit_id"):
            with W.db() as c:
                o = c.execute("SELECT inv_date FROM invoices WHERE id=?", (p["edit_id"],)).fetchone(); od = o[0] if o else None
        is_rep = W.CURRENT_USER.get("role") == W.ROLE_REP
        if not is_rep: self._day(p.get("date") or _today(), od)
        try:
            d = W.prepare_invoice(p["kind"], lines, p.get("party_id"), p.get("number") or "", p.get("date") or "", p.get("due") or "",
                                  p.get("discount") or 0, p.get("paid") or 0, p.get("pay_type"), p.get("notes") or "", p.get("rep_id"), p.get("edit_id"))
        except W.InvoiceInputError as e:
            return {"ok": False, "error": str(e), "title": e.title}
        if is_rep:                                   # المندوب: الفاتورة بتتبعت طلب للمحاسب يوافق عليها
            pl = {k: p.get(k) for k in ("kind", "party_id", "date", "due", "discount", "paid", "pay_type", "notes", "rep_id", "vehicle_id")}; pl["lines"] = lines
            with W.db() as c:
                rid = c.execute("INSERT INTO inv_requests(created_at,rep_id,by_user,party_id,kind,net,payload) VALUES(?,?,?,?,?,?,?)",
                                (W.now_ts(), W.CURRENT_USER.get("emp_id"), W.CURRENT_USER.get("username", ""), p.get("party_id"), p["kind"], d["net"], json.dumps(pl, ensure_ascii=False))).lastrowid
                pn = (c.execute("SELECT name FROM parties WHERE id=?", (p.get("party_id"),)).fetchone() or [""])[0]
                W.log(c, "طلب فاتورة من مندوب", f"طلب رقم {rid}: {p['kind']} — {pn} — {W.fmt(d['net'])} (مستني موافقة)")
            return {"ok": True, "request_id": rid, "net": _r2(d["net"])}
        override = False
        if credit_pw:
            override = W.verify_owner_password(credit_pw)
            if not override: return {"ok": False, "error": "كلمة سر المالك غير صحيحة", "need": "credit"}
        neg_who = None
        if neg_pw:
            neg_who = W.verify_owner_password(neg_pw)
            if not neg_who: return {"ok": False, "error": "كلمة سر المالك غير صحيحة", "need": "neg"}
        try:
            W._TLS.allow_neg = neg_who
            inv_id, number = W.persist_invoice(d, override=override, auto_no=(not p.get("edit_id")) and p.get("auto_no", True))
        except W.CreditLimitExceeded as e:
            return {"ok": False, "need": "credit", "error": f"العميل «{e.name}» هيعدّي الحد الائتماني.\nالحد: {W.fmt(e.limit)} — الرصيد بعد الفاتورة: {W.fmt(e.after)}\n"
                                                            f"الزيادة عن الحد: {W.fmt(e.after - e.limit)}"}
        except W.NegativeStock as e:
            return {"ok": False, "need": "neg", "error": str(e) + "\nالرصيد هيبقى بالسالب — مسموح بس بكلمة سر المالك."}
        except W.DBIntegrityError:
            return {"ok": False, "error": "رقم الفاتورة ده موجود بالفعل في نفس اليوم؛ غيّر الرقم"}
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        finally:
            W._TLS.allow_neg = None
        if p["kind"] == "مبيعات":                    # التوصيل: العربية أو استلام مكتب
            try: vid = int(p.get("vehicle_id") or 0) or None
            except (TypeError, ValueError): vid = None
            with W.db() as c: c.execute("UPDATE invoices SET vehicle_id=? WHERE id=?", (vid, inv_id))
        if p.get("request_id"):                      # موافقة على طلب مندوب: الطلب بيتقفل ومربوط بالفاتورة
            with W.db() as c:
                c.execute("UPDATE inv_requests SET status='approved', decided_at=?, decided_by=?, invoice_id=? WHERE id=? AND status='pending'",
                          (W.now_ts(), W.CURRENT_USER.get("username", ""), inv_id, int(p["request_id"])))
                W.log(c, "موافقة على طلب فاتورة", f"طلب رقم {p['request_id']} ← فاتورة {d['kind']} رقم {number}")
        if do_print: self.print_invoice(inv_id)
        return {"ok": True, "id": inv_id, "number": number, "net": _r2(d["net"])}

    # ---------- سجل الفواتير ----------
    def invoices(self, d_from=None, d_to=None, kind="", q=""):
        self._need_login()
        a = W.check_date(d_from or _today()); b = W.check_date(d_to or a)
        sql = (f"SELECT i.id,i.number,i.kind,i.inv_date,i.due_date,i.created_at,i.pay_type,i.printed_at,p.name party,e.name rep,v.name vname,{W.NET_SQL} net, "
               "COALESCE((SELECT SUM(amount) FROM payments WHERE invoice_id=i.id),0) paid "
               "FROM invoices i LEFT JOIN parties p ON p.id=i.party_id LEFT JOIN employees e ON e.id=i.rep_id LEFT JOIN vehicles v ON v.id=i.vehicle_id WHERE i.inv_date BETWEEN ? AND ?")
        args = [a, b]
        if kind in W.KINDS: sql += " AND i.kind=?"; args.append(kind)
        sql += " ORDER BY i.inv_date DESC, i.created_at DESC, i.id DESC"
        with W.db() as c: rows = c.execute(sql, args).fetchall()
        qn = W._norm((q or "").strip())
        out = []
        for r in rows:
            if qn and qn not in W._norm(f"{r['party'] or ''} {r['number']} {r['rep'] or ''}"): continue
            out.append({"id": r["id"], "number": r["number"], "kind": r["kind"], "date": r["inv_date"], "due": r["due_date"] or "", "time": W.fmt_time(r["created_at"]), "created_at": r["created_at"] or "",
                        "pay": r["pay_type"] or "", "party": r["party"] or "", "rep": r["rep"] or "", "net": _r2(r["net"]), "paid": _r2(r["paid"]), "printed": bool(r["printed_at"]),
                        "delivery": (r["vname"] or "استلام مكتب") if r["kind"] == "مبيعات" else ""})
        return out

    def invoice(self, inv_id):
        self._need_login()
        with W.db() as c:
            i = c.execute("SELECT i.*, p.name party, p.phone phone, e.name rep, v.name vname FROM invoices i LEFT JOIN parties p ON p.id=i.party_id LEFT JOIN vehicles v ON v.id=i.vehicle_id "
                          "LEFT JOIN employees e ON e.id=i.rep_id WHERE i.id=?", (inv_id,)).fetchone()
            if not i: raise UIError("الفاتورة مش موجودة")
            lines = c.execute("SELECT * FROM invoice_lines WHERE invoice_id=? ORDER BY id", (inv_id,)).fetchall()
            paid = c.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE invoice_id=?", (inv_id,)).fetchone()[0]
            costs = W.fifo_engine(c)["line"] if (i["kind"] == "مبيعات" and W.is_owner()) else None
        total = sum(float(l["qty"]) * float(l["price"]) for l in lines)
        out = {"id": i["id"], "number": i["number"], "kind": i["kind"], "date": i["inv_date"], "due": i["due_date"] or "", "time": W.fmt_time(i["created_at"]),
               "party": i["party"] or "", "party_id": i["party_id"], "phone": i["phone"] or "", "delivery": (i["vname"] or "استلام مكتب") if i["kind"] == "مبيعات" else "", "rep": i["rep"] or "", "pay": i["pay_type"] or "", "notes": i["notes"] or "",
               "total": _r2(total), "discount": _r2(i["discount"]), "net": _r2(total - float(i["discount"] or 0)), "paid": _r2(paid),
               "printed": i["printed_at"] or "", "print_count": i["print_count"] or 0,
               "lines": [{"name": l["item_name"], "unit": l["unit"] or "", "qty": _r2(l["qty"]), "price": _r2(l["price"]), "total": _r2(float(l["qty"]) * float(l["price"])),
                          "damaged": bool(l["damaged"])} for l in lines]}
        if costs is not None:
            prof = sum(float(l["qty"]) * (float(l["price"]) - costs.get(l["id"], 0.0)) for l in lines) - float(i["discount"] or 0)
            out["profit"] = _r2(prof)
        return out

    def print_invoice(self, inv_id):
        self._need_login()
        os.makedirs(W.PRINT_DIR, exist_ok=True)
        path = os.path.join(W.PRINT_DIR, f"invoice_{inv_id}.html")
        with open(path, "w", encoding="utf-8") as f: f.write(W.App.invoice_html(None, inv_id))
        W.print_page(path)
        try:
            with W.db() as c: c.execute("UPDATE invoices SET printed_at=?, print_count=COALESCE(print_count,0)+1 WHERE id=?", (W.now_ts(), inv_id))
        except Exception: pass
        return True

    # ---------- تعديل وحذف الفواتير ----------
    def invoice_for_edit(self, inv_id):
        self._need_login()
        with W.db() as c:
            i = c.execute("SELECT * FROM invoices WHERE id=?", (inv_id,)).fetchone()
            if not i: raise UIError("الفاتورة مش موجودة")
            lines = c.execute("SELECT * FROM invoice_lines WHERE invoice_id=? ORDER BY id", (inv_id,)).fetchall()
            paid = c.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE invoice_id=?", (inv_id,)).fetchone()[0]
        msg = W.check_locked(i["inv_date"])
        if msg: raise UIError(msg)
        self._day(i["inv_date"])
        return {"id": i["id"], "kind": i["kind"], "number": i["number"], "date": i["inv_date"], "due": i["due_date"] or "", "party_id": i["party_id"],
                "rep_id": i["rep_id"], "vehicle_id": i["vehicle_id"], "notes": i["notes"] or "", "discount": _r2(i["discount"]), "paid": _r2(paid), "pay_type": i["pay_type"] or "آجل",
                "lines": [{"item_id": l["item_id"], "name": l["item_name"], "unit": l["unit"] or "", "qty": float(l["qty"]), "price": float(l["price"]),
                           "damaged": int(l["damaged"] or 0)} for l in lines]}

    def delete_invoice(self, inv_id, neg_pw=None):
        self._need_login()
        with W.db() as c: o = c.execute("SELECT inv_date FROM invoices WHERE id=?", (inv_id,)).fetchone()
        if not o: raise UIError("الفاتورة مش موجودة")
        msg = W.check_locked(o[0])
        if msg: raise UIError(msg)
        self._day(o[0])
        who = None
        if neg_pw:
            who = W.verify_owner_password(neg_pw)
            if not who: return {"ok": False, "need": "neg", "error": "كلمة سر المالك غير صحيحة"}
        try:
            W._TLS.allow_neg = who
            W.App._delete_invoice_id(None, inv_id)
        except W.NegativeStock as e:
            return {"ok": False, "need": "neg", "error": str(e) + "\nالرصيد هيبقى بالسالب — مسموح بس بكلمة سر المالك."}
        finally:
            W._TLS.allow_neg = None
        return {"ok": True}

    # ---------- السندات ----------
    def voucher_setup(self):
        self._need_login()
        with W.db() as c:
            parties = c.execute("SELECT id,name,address,phone,rep_id,kind FROM parties ORDER BY name").fetchall()
            cats = [r["name"] for r in c.execute("SELECT name FROM expense_cats ORDER BY name")]
            reps = W.rep_lookup(c)
        with W.db() as c: hs = holders_setup(c)
        return {"today": _today(), "cats": cats, "methods": PAY_METHODS, "holders": hs, "reps": [{"id": v, "label": k} for k, v in reps.items()],
                "parties": [{"id": p["id"], "label": W.party_label(p), "rep_id": p["rep_id"], "kind": p["kind"] or ""} for p in parties]}

    def add_expense_cat(self, name):
        self._need_login()
        name = (name or "").strip()
        if not name: raise UIError("اكتب اسم البند")
        with W.db() as c:
            c.execute("INSERT OR IGNORE INTO expense_cats(name) VALUES(?)", (name,)); W.log(c, "إضافة بند مصروفات", name)
        return name

    def delete_expense_cat(self, name, pw):
        """حذف بند مصروفات من القايمة — بكلمة سر اليوزر الداخل. المصروفات القديمة بتفضل باسم البند زي ما هي."""
        self._need_login()
        name = (name or "").strip()
        if not name: raise UIError("اختار البند الأول")
        if name == "مصروفات أخرى": raise UIError("«مصروفات أخرى» بند أساسي ومينفعش يتمسح")
        with W.db() as c:
            u = c.execute("SELECT * FROM users WHERE id=?", (W.CURRENT_USER.get("id"),)).fetchone()
            if not u or not W.check_pw(pw or "", u["pw_hash"], u["salt"]): raise UIError("كلمة السر غلط")
            if not c.execute("SELECT 1 FROM expense_cats WHERE name=?", (name,)).fetchone(): raise UIError("البند ده مش موجود في القايمة")
            used = c.execute("SELECT COUNT(*) FROM expenses WHERE category=?", (name,)).fetchone()[0]
            c.execute("DELETE FROM expense_cats WHERE name=?", (name,))
            W.log(c, "حذف بند مصروفات", name + (f" — عليه {used} مصروف قديم فضل زي ما هو" if used else ""))
        return {"used": used}

    def rename_expense_cat(self, old, new, pw):
        """تعديل اسم بند — بكلمة سر اليوزر. المصروفات القديمة بتتنقل للاسم الجديد."""
        self._need_login()
        old = (old or "").strip(); new = (new or "").strip()
        if not old or not new: raise UIError("اكتب الاسم الجديد")
        if old == "مصروفات أخرى": raise UIError("«مصروفات أخرى» بند أساسي ومينفعش يتغير اسمه")
        with W.db() as c:
            u = c.execute("SELECT * FROM users WHERE id=?", (W.CURRENT_USER.get("id"),)).fetchone()
            if not u or not W.check_pw(pw or "", u["pw_hash"], u["salt"]): raise UIError("كلمة السر غلط")
            if c.execute("SELECT 1 FROM expense_cats WHERE name=?", (new,)).fetchone(): raise UIError(f"فيه بند اسمه «{new}» بالفعل")
            c.execute("UPDATE expense_cats SET name=? WHERE name=?", (new, old))
            used = c.execute("SELECT COUNT(*) FROM expenses WHERE category=?", (old,)).fetchone()[0]
            c.execute("UPDATE expenses SET category=? WHERE category=?", (new, old))
            W.log(c, "تعديل بند مصروفات", f"{old} ← {new}" + (f" — واتعدّل في {used} مصروف" if used else ""))
        return {"name": new, "used": used}

    def voucher_preview(self, kind, party_id, amount, edit_id=None):
        """رصيد الحساب قبل وبعد السند."""
        self._need_login()
        if kind == "مصروف" or not party_id: return None
        amt = W._f(amount)
        with W.db() as c:
            bal = W.party_balance(c, party_id)
            if edit_id:
                old = c.execute("SELECT kind,amount,party_id FROM payments WHERE id=?", (edit_id,)).fetchone()
                if old and old["party_id"] == party_id: bal += float(old["amount"]) if old["kind"] in ("تحصيل", W.DISC_KIND) else -float(old["amount"])
        after = bal - amt if kind in ("تحصيل", W.DISC_KIND) else bal + amt
        return {"before": _r2(bal), "after": _r2(after)}

    def save_voucher(self, p, do_print=False):
        """p = {kind: تحصيل|دفع|مصروف|خصم مسموح به, party_id, rep_id, cat, date, amount, notes, edit_id} — نفس قواعد السيستم القديم."""
        self._need_login()
        kind = p.get("kind")
        if kind not in ("تحصيل", "دفع", "مصروف", W.DISC_KIND): raise UIError("نوع السند غلط")
        try: amount = W._f(p.get("amount"), None)
        except ValueError: raise UIError("المبلغ يجب أن يكون رقمًا")
        if amount is None: raise UIError("المبلغ يجب أن يكون رقمًا")
        if amount <= 0: raise UIError("المبلغ يجب أن يكون أكبر من صفر")
        try: d = W.check_date(p.get("date") or "")
        except ValueError: raise UIError("صيغة التاريخ غير صحيحة")
        notes = (p.get("notes") or "").strip(); edit = p.get("edit_id")
        if W.CURRENT_USER.get("role") == W.ROLE_REP:   # المندوب: سند التحصيل بيتبعت طلب للمحاسب يوافق عليه
            with W.db() as c:
                meth = p.get("method") if p.get("method") in PAY_METHODS else "كاش"
                rid = c.execute("INSERT INTO rep_requests(created_at,rep_id,party_id,amount,notes,status,chat_id,method) VALUES(?,?,?,?,?,'pending','',?)",
                                (W.now_ts(), W.CURRENT_USER.get("emp_id"), int(p.get("party_id")), amount, notes, meth)).lastrowid
                pn = (c.execute("SELECT name FROM parties WHERE id=?", (p.get("party_id"),)).fetchone() or [""])[0]
                W.log(c, "طلب تحصيل من مندوب", f"طلب رقم {rid}: {pn} — {W.fmt(amount)} (من الموقع، مستني موافقة)")
            return {"request_id": rid}
        old_date = None
        if edit:
            with W.db() as c:
                o = c.execute("SELECT exp_date FROM expenses WHERE id=?" if kind == "مصروف" else "SELECT pay_date FROM payments WHERE id=?", (edit,)).fetchone()
                old_date = o[0] if o else None
        msg = W.check_locked(d, old_date)
        if msg: raise UIError(msg)
        self._day(d, old_date)
        saved = None
        if kind == "مصروف":
            cat = (p.get("cat") or "").strip()
            if not cat: raise UIError("اختر البند (أو أضف بندًا جديدًا)")
            with W.db() as c:
                if edit:
                    old = c.execute("SELECT * FROM expenses WHERE id=?", (edit,)).fetchone()
                    c.execute("UPDATE expenses SET exp_date=?,category=?,amount=?,notes=? WHERE id=?", (d, cat, amount, notes, edit))
                    W.log(c, "تعديل مصروف", f"رقم {edit}: {old['category']} {W.fmt(old['amount'])} بتاريخ {old['exp_date']} ← {cat} {W.fmt(amount)} بتاريخ {d}")
                else:
                    c.execute("INSERT INTO expenses(exp_date,kind,category,amount,notes,created_at) VALUES(?,?,?,?,?,?)", (d, "مصروف", cat, amount, notes, W.now_ts()))
                    W.log(c, "مصروف", f"{cat}: {W.fmt(amount)} بتاريخ {d}")
        else:
            pid = p.get("party_id")
            if not pid: raise UIError("اختر الاسم")
            rep_id = p.get("rep_id") if kind == "تحصيل" else None
            with W.db() as c:
                pname = c.execute("SELECT name FROM parties WHERE id=?", (pid,)).fetchone()[0]
                rep_txt = f" — المندوب: {W.rep_name_of(c, rep_id)}" if kind == "تحصيل" else ""
                if edit:
                    old = c.execute("SELECT p.*,pt.name pname FROM payments p JOIN parties pt ON pt.id=p.party_id WHERE p.id=?", (edit,)).fetchone()
                    if old["invoice_id"]: raise UIError("هذا السند جزء من فاتورة. عدّل المبلغ المدفوع من تعديل الفاتورة.")
                    c.execute("UPDATE payments SET party_id=?,pay_date=?,amount=?,notes=?,rep_id=? WHERE id=?", (pid, d, amount, notes, rep_id, edit))
                    saved = edit
                    self._holder(c, saved, kind, rep_id, p)
                    W.log(c, "تعديل سند", f"سند رقم {edit}: {old['pname']} {W.fmt(old['amount'])} بتاريخ {old['pay_date']} ← {pname} {W.fmt(amount)} بتاريخ {d}" + rep_txt)
                else:
                    saved = c.execute("INSERT INTO payments(party_id,pay_date,kind,amount,notes,rep_id,created_at) VALUES(?,?,?,?,?,?,?)", (pid, d, kind, amount, notes, rep_id, W.now_ts())).lastrowid
                    self._holder(c, saved, kind, rep_id, p)
                    W.log(c, W.DISC_KIND if kind == W.DISC_KIND else "سند " + ("تحصيل" if kind == "تحصيل" else "دفع"), f"{pname}: {W.fmt(amount)} بتاريخ {d}" + rep_txt)
        if do_print and saved: self.print_receipt(saved)
        return {"ok": True, "id": saved}

    def vouchers(self, d_from=None, d_to=None, typ="الكل", rep_id=None, q=""):
        self._need_login()
        s_ = W.check_date(d_from or _today()); e_ = W.check_date(d_to or s_)
        rows = []
        with W.db() as c:
            for r in c.execute("SELECT p.*,pt.name pname,m.name rname,i.number inv_no,i.kind inv_kind FROM payments p JOIN parties pt ON pt.id=p.party_id "
                               "LEFT JOIN employees m ON m.id=p.rep_id LEFT JOIN invoices i ON i.id=p.invoice_id WHERE p.pay_date BETWEEN ? AND ?", (s_, e_)):
                col = r["kind"] == "تحصيل"
                rows.append({"key": f"p-{r['id']}", "id": r["id"], "date": r["pay_date"], "created": r["created_at"] or "", "time": W.fmt_time(r["created_at"]),
                             "type": W.DISC_KIND if r["kind"] == W.DISC_KIND else "تحصيل من عميل" if col else "دفع لمورد", "name": r["pname"], "party_id": r["party_id"],
                             "rep": (r["rname"] or W.OFFICE) if col else "", "rep_id": r["rep_id"], "amount": _r2(r["amount"]), "notes": r["notes"] or "",
                             "invoice_id": r["invoice_id"], "invoice": (f"{r['inv_kind']} {r['inv_no']}" if r["invoice_id"] else "")})
            for r in c.execute("SELECT e.*,m.name ename FROM expenses e LEFT JOIN employees m ON m.id=e.employee_id WHERE e.exp_date BETWEEN ? AND ?", (s_, e_)):
                t = {"مصروف": "مصروفات", "مرتب": "مرتبات", "سلفة": "سلف", "عمولة": "عمولات"}.get(r["kind"], r["kind"])
                if r["kind"] == "مرتب" and r["category"] in W.WAGE_CATS: t += f" ({r['category']})"
                rows.append({"key": f"e-{r['id']}", "id": r["id"], "date": r["exp_date"], "created": r["created_at"] or "", "time": W.fmt_time(r["created_at"]),
                             "type": t, "name": r["category"] if r["kind"] == "مصروف" else (r["ename"] or ""), "rep": "", "rep_id": None,
                             "amount": _r2(r["amount"]), "notes": r["notes"] or "", "invoice_id": None, "invoice": "", "expense_kind": r["kind"]})
        qn = W._norm((q or "").strip())
        rows = [r for r in rows if (typ in ("", "الكل", None) or r["type"].split(" (")[0] == typ) and (not qn or qn in W._norm(r["name"] + " " + r["notes"]))]
        if rep_id not in (None, "", "الكل"):
            rows = [r for r in rows if r["type"] == "تحصيل من عميل" and (r["rep_id"] or None) == (int(rep_id) if rep_id != "office" else None)]
        rows.sort(key=lambda r: (r["date"], r["created"], r["key"]), reverse=True)
        return rows

    def voucher(self, key):
        """بيانات سند للتعديل (أو الفاتورة اللي هو جزء منها)."""
        self._need_login()
        typ, rid = key.split("-"); rid = int(rid)
        with W.db() as c:
            if typ == "p":
                r = c.execute("SELECT p.*, i.kind inv_kind FROM payments p LEFT JOIN invoices i ON i.id=p.invoice_id WHERE p.id=?", (rid,)).fetchone()
                if not r: raise UIError("السند مش موجود")
                if r["invoice_id"]: return {"invoice_id": r["invoice_id"], "invoice_kind": r["inv_kind"]}
                return {"edit_id": rid, "kind": r["kind"], "party_id": r["party_id"], "rep_id": r["rep_id"], "date": r["pay_date"], "amount": _r2(r["amount"]), "notes": r["notes"] or "",
                        "method": (r["method"] if "method" in r.keys() else "") or "كاش", "holder": (r["holder"] if "holder" in r.keys() else "") or ""}
            r = c.execute("SELECT * FROM expenses WHERE id=?", (rid,)).fetchone()
            if not r: raise UIError("السند مش موجود")
            if r["kind"] != "مصروف": raise UIError("المرتبات والسلف والعمولات لا تُعدّل من هنا. احذف السند وسجّله من جديد من شاشة الموظفين.")
            return {"edit_id": rid, "kind": "مصروف", "cat": r["category"] or "", "date": r["exp_date"], "amount": _r2(r["amount"]), "notes": r["notes"] or ""}

    def delete_voucher(self, key):
        self._need_login()
        typ, rid = key.split("-"); rid = int(rid)
        with W.db() as c:
            if typ == "p":
                p = c.execute("SELECT * FROM payments WHERE id=?", (rid,)).fetchone()
                if p and p["invoice_id"]: raise UIError("هذا السند جزء من فاتورة. عدّل المبلغ المدفوع من تعديل الفاتورة.")
                dd = p["pay_date"] if p else None
            else:
                x = c.execute("SELECT exp_date FROM expenses WHERE id=?", (rid,)).fetchone(); dd = x[0] if x else None
        msg = W.check_locked(dd)
        if msg: raise UIError(msg)
        self._day(dd)
        with W.db() as c:
            if typ == "p": c.execute("DELETE FROM payments WHERE id=?", (rid,)); W.log(c, "حذف سند", f"سند رقم {rid}")
            else:
                c.execute("UPDATE loading_logs SET expense_id=NULL WHERE expense_id=?", (rid,))
                c.execute("DELETE FROM expenses WHERE id=?", (rid,)); W.log(c, "حذف مصروف/مرتب/سلفة", f"رقم {rid}")
        return True

    def print_receipt(self, pay_id):
        self._need_login()
        path = os.path.join(W.PRINT_DIR, f"receipt_{pay_id}.html")
        with open(path, "w", encoding="utf-8") as f: f.write(W.App.receipt_html(None, pay_id))
        W.print_page(path)
        return True

    # ---------- كشف الحساب والأرصدة ----------
    def parties_list(self):
        self._need_login()
        with W.db() as c: parties = c.execute("SELECT id,name,address,phone,rep_id,kind FROM parties ORDER BY name").fetchall()
        return [{"id": p["id"], "label": W.party_label(p), "kind": p["kind"] or ""} for p in parties]

    def statement(self, pid, d_from, d_to):
        self._need_login()
        a = W.check_date(d_from); b = W.check_date(d_to)
        if a > b: raise UIError("تاريخ البداية بعد تاريخ النهاية")
        party, opening, rows, closing = W.build_statement(pid, a, b)
        with W.db() as c: note = W.party_last_text(c, pid)
        return {"party": party["name"], "phone": party["phone"] or "", "opening": _r2(opening), "closing": _r2(closing), "note": note,
                "rows": [{"date": r[0], "ref": r[1], "what": r[2], "debit": _r2(r[3]), "credit": _r2(r[4]), "balance": _r2(r[5]),
                          "type": r[6], "rid": r[7], "time": W.fmt_time(r[8])} for r in rows]}

    def print_statement(self, pid, d_from, d_to):
        self._need_login()
        a = W.check_date(d_from); b = W.check_date(d_to)
        party, opening, rows, closing = W.build_statement(pid, a, b)
        from types import SimpleNamespace
        W.App.print_statement(SimpleNamespace(last_statement=(party, a, b, opening, rows, closing)))
        return True

    def payment_detail(self, pay_id):
        self._need_login()
        with W.db() as c:
            p = c.execute("SELECT p.*, pt.name pname FROM payments p JOIN parties pt ON pt.id=p.party_id WHERE p.id=?", (pay_id,)).fetchone()
            if not p: raise UIError("السند مش موجود")
            rep = W.rep_name_of(c, p["rep_id"]) if p["kind"] == "تحصيل" else ""
        return {"id": pay_id, "date": p["pay_date"], "time": W.fmt_time(p["created_at"]), "name": p["pname"],
                "kind": p["kind"] if p["kind"] == W.DISC_KIND else "تحصيل" if p["kind"] == "تحصيل" else "دفع",
                "amount": _r2(p["amount"]), "rep": rep, "notes": p["notes"] or "", "invoice_id": p["invoice_id"]}

    def balances(self):
        self._need_login()
        with W.db() as c:
            ld = W.last_dates(c); data = []
            bal = W._balance_bulk(c, _today())                      # كل الأرصدة في استعلامين (أسرع بكتير من رصيد لكل حساب)
            for p in c.execute("SELECT * FROM parties ORDER BY name").fetchall():
                b = bal.get(p["id"], 0.0)
                data.append({"id": p["id"], "name": p["name"], "kind": p["kind"] or "", "phone": p["phone"] or "", "balance": _r2(b),
                             "lc": ld[0].get(p["id"]) or "", "lp": ld[1].get(p["id"]) or "", "li": ld[2].get(p["id"]) or ""})
            cash = W.cash_balance(c)
            stm = W.stock_map(c)
            sale_val = sum(max(stm.get(r["id"], 0.0), 0) * float(r["sell_price"] or 0) for r in c.execute("SELECT id,sell_price FROM items").fetchall())
            inv_val = W.fifo_stock_value(c)
        pr = [d for d in data if d["kind"] != ASSET]
        recv = sum(d["balance"] for d in pr if d["balance"] > 0); pay = -sum(d["balance"] for d in pr if d["balance"] < 0)
        assets = sum(d["balance"] for d in data if d["kind"] == ASSET)
        return {"rows": data, "cards": {"recv": _r2(recv), "pay": _r2(pay), "cash": _r2(cash), "inv": _r2(inv_val), "sale": _r2(sale_val), "assets": _r2(assets),
                                        "net": _r2(cash + inv_val + recv - pay)}}

    @staticmethod
    def _del_pw(pw):
        """الحذف في العملاء/الموظفين/الأصناف/الحسابات محتاج باسوورد محاسب أو المالك."""
        who = W.verify_day_password(pw)
        if not who: raise UIError("باسوورد المحاسب أو المالك غلط — مااتحذفش حاجة" if pw else "الحذف محتاج باسوورد المحاسب أو المالك")
        return who

    def delete_parties(self, ids, pw=None):
        self._need_login()
        who = self._del_pw(pw)
        with W.db() as c:
            info = [(i, c.execute("SELECT name FROM parties WHERE id=?", (i,)).fetchone()[0],
                     c.execute("SELECT (SELECT COUNT(*) FROM invoices WHERE party_id=?)+(SELECT COUNT(*) FROM payments WHERE party_id=?)+(SELECT COUNT(*) FROM samples WHERE party_id=?)", (i, i, i)).fetchone()[0]) for i in ids]
        used = [n for _, n, u in info if u]; free = [(i, n) for i, n, u in info if not u]
        with W.db() as c:
            for i, n in free:
                c.execute("DELETE FROM parties WHERE id=?", (i,)); W.log(c, "حذف عميل/مورد", f"{n} (بباسوورد {who})")
        return {"deleted": [n for _, n in free], "kept": used}

    def print_balances(self, ids=None, q=""):
        """أرصدة الحسابات (اللي ظاهرة أو المحددة) → صفحة طباعة (ومنها PDF)."""
        self._need_login()
        b = self.balances(); rows = b["rows"]
        if ids: keep = set(ids); rows = [d for d in rows if d["id"] in keep]
        elif q:
            qn = W._norm(q); rows = [d for d in rows if qn in W._norm(d["name"] + " " + d["kind"])]
        rows.sort(key=lambda d: -abs(d["balance"]))
        if not rows: raise UIError("مفيش حسابات")
        with W.db() as c: st = c.execute("SELECT * FROM settings WHERE id=1").fetchone()
        esc, fmt = W.esc, W.fmt
        r_ = sum(d["balance"] for d in rows if d["balance"] > 0); p_ = -sum(d["balance"] for d in rows if d["balance"] < 0)
        body = "".join(f"<tr><td>{n}</td><td class='nm'>{esc(d['name'])}</td><td>{esc(d['kind'])}</td><td>{fmt(d['balance']) if d['balance'] > 0.005 else ''}</td>"
                       f"<td>{fmt(-d['balance']) if d['balance'] < -0.005 else ''}</td><td>{d['lc']}</td><td>{d['lp']}</td><td>{d['li']}</td></tr>" for n, d in enumerate(rows, 1))
        t = b["cards"]
        cards = "" if (q or ids) else ("<div class='cards'>" + "".join(f"<div><b>{k}</b><span>{fmt(v)}</span></div>" for k, v in (
            ("على العملاء (لنا)", t["recv"]), ("علينا للموردين", t["pay"]), ("الخزنة", t["cash"]), ("الأصول", t.get("assets", 0)), ("قيمة المخزون (بسعر الشراء)", t["inv"]), ("صافي الأملاك", t["net"]))) + "</div>")
        sub = f"بتاريخ {_today()}" + (f"  •  بحث: {esc(q)}" if q else "") + ("  •  الحسابات المحددة بس" if ids else "")
        html = f"""<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8"><title>أرصدة الحسابات</title><style>
        @page{{size:A4;margin:10mm}}*{{box-sizing:border-box}}body{{font-family:Tahoma,Arial,sans-serif;font-size:12.5px;color:#111;margin:0}}
        .hd{{display:flex;align-items:center;justify-content:space-between;border-bottom:2px solid #123b67;padding-bottom:6px}}.hd img{{height:58px}}
        h1{{margin:0;font-size:21px;color:#123b67}}h2{{text-align:center;margin:10px 0 2px}}.sub{{text-align:center;color:#444;margin-bottom:8px}}
        .cards{{display:flex;gap:6px;margin:6px 0 10px}}.cards div{{flex:1;border:1px solid #9fb4cc;border-radius:6px;padding:5px;text-align:center}}
        .cards b{{display:block;font-size:11px;color:#123b67}}.cards span{{font-size:15px;font-weight:bold}}
        table{{width:100%;border-collapse:collapse;table-layout:fixed}}th,td{{border:1px solid #666;padding:4px 3px;text-align:center;white-space:nowrap;overflow:hidden}}td.nm{{text-align:right;white-space:normal}}
        th{{background:#e8eef5;font-size:11.5px}}tr:nth-child(even) td{{background:#f6fafd}}tfoot td{{font-weight:bold;background:#e8eef5}}thead{{display:table-header-group}}tr{{break-inside:avoid}}
        .ft{{margin-top:8px;color:#555;font-size:11px}}</style>
        <div class="hd"><div><h1>{esc(st['company']) or W.DEFAULT_COMPANY}</h1><div>{esc(st['tagline'] or W.DEFAULT_TAGLINE)}</div></div><img src="{W.logo_data_uri()}"></div>
        <h2>أرصدة الحسابات</h2><div class="sub">{sub}</div>{cards}
        <table><colgroup><col style="width:4%"><col style="width:32%"><col style="width:6%"><col style="width:12.6%"><col style="width:12.6%"><col style="width:10.9%"><col style="width:10.9%"><col style="width:11%"></colgroup>
        <thead><tr><th>م</th><th>الاسم</th><th>النوع</th><th>مدين (عليه)</th><th>دائن (له)</th><th>آخر تحصيل</th><th>آخر دفع</th><th>آخر فاتورة</th></tr></thead>
        <tbody>{body}</tbody><tfoot><tr><td colspan="3">الإجمالي ({len(rows)} حساب)</td><td>{fmt(r_)}</td><td>{fmt(p_)}</td><td colspan="3">الصافي: {fmt(r_ - p_)}</td></tr></tfoot></table>
        <div class="ft">طُبع في {_today()} — {W.fmt_time(W.now_ts())}</div></html>"""
        hp = os.path.join(W.PRINT_DIR, "balances.html")
        with open(hp, "w", encoding="utf-8") as f: f.write(html)
        W.print_page(hp)
        return True

    # ---------- الخزنة ----------
    def cash(self, d_from=None, d_to=None):
        self._need_login()
        a = W.check_date(d_from or _today()); b = W.check_date(d_to or a)
        with W.db() as c: op = W.cash_opening(c); mv = W.treasury_moves(c)
        bal = op + sum(m[5] - m[6] for m in mv if m[0] < a)
        start = bal; rows = []; tin = tout = 0.0
        for m in mv:
            if a <= m[0] <= b:
                bal += m[5] - m[6]; tin += m[5]; tout += m[6]
                rows.append({"key": m[3], "date": m[0], "time": W.fmt_time(m[7]), "what": m[4], "in": _r2(m[5]), "out": _r2(m[6]), "balance": _r2(bal)})
        return {"opening_setting": _r2(op), "start": _r2(start), "rows": rows, "in": _r2(tin), "out": _r2(tout), "end": _r2(bal),
                "current": _r2(op + sum(m[5] - m[6] for m in mv))}

    def add_cash_move(self, kind, d, amount, notes=""):
        self._need_login()
        if kind not in ("إيداع", "سحب"): raise UIError("النوع غلط")
        try: a = W._f(amount, None); d = W.check_date(d)
        except ValueError: raise UIError("راجع المبلغ والتاريخ")
        if not a or a <= 0: raise UIError("المبلغ يجب أن يكون أكبر من صفر")
        msg = W.check_locked(d)
        if msg: raise UIError(msg)
        with W.db() as c:
            c.execute("INSERT INTO cash_moves(move_date,kind,amount,notes,created_at) VALUES(?,?,?,?,?)", (d, kind, a, (notes or "").strip(), W.now_ts()))
            W.log(c, "حركة خزنة", f"{kind} {W.fmt(a)}")
        return True

    def delete_cash_move(self, key):
        self._need_login()
        if not str(key).startswith("c-"): raise UIError("الفواتير والسندات والمصروفات بتتحذف من شاشاتها. هنا بتحذف الإيداع والسحب اليدوي بس.")
        mid = int(key[2:])
        with W.db() as c: m = c.execute("SELECT * FROM cash_moves WHERE id=?", (mid,)).fetchone()
        if not m: raise UIError("الحركة مش موجودة")
        msg = W.check_locked(m["move_date"])
        if msg: raise UIError(msg)
        with W.db() as c:
            c.execute("DELETE FROM cash_moves WHERE id=?", (mid,))
            W.log(c, "حذف حركة خزنة", f"{m['kind']} {W.fmt(m['amount'])} — {m['move_date']}" + (f" — {m['notes']}" if m["notes"] else ""))
        return True

    def set_cash_opening(self, v, owner_pw=None):
        """رصيد أول مدة الخزنة — من الإعدادات وبكلمة سر المالك بس."""
        self._need_login()
        try: v = W._f(v)
        except ValueError: raise UIError("الرقم غير صحيح")
        who = W.verify_owner_password(owner_pw or "")
        if not who: raise UIError("كلمة سر المالك غير صحيحة")
        with W.db() as c:
            old = c.execute("SELECT COALESCE(cash_opening,0) FROM settings WHERE id=1").fetchone()[0]
            c.execute("UPDATE settings SET cash_opening=? WHERE id=1", (v,)); W.log(c, "رصيد أول مدة الخزنة", f"{W.fmt(old)} ← {W.fmt(v)} — بكلمة سر {who}")
        return True

    def _holder(self, c, pay_id, kind, rep_id, p):
        """مع مين فلوس السند وطريقة الدفع: لو فيه مندوب = معاه (أو اللي سلّمها له)، لو مكتب = اللي اتختار (مالك / محاسب / درج)."""
        if kind != "تحصيل": return
        meth = p.get("method") if p.get("method") in PAY_METHODS else "كاش"
        hs = holders_setup(c); allowed = hs["owners"] + hs["accountants"] + [DRAWER]
        if rep_id:                                   # مع المندوب، إلا لو اتختار إنه سلّمها (للدرج / مالك / محاسب)
            holder = p.get("holder") if p.get("holder") in allowed else (c.execute("SELECT name FROM employees WHERE id=?", (rep_id,)).fetchone() or [""])[0]
        else:
            holder = p.get("holder") if p.get("holder") in allowed else DRAWER
        c.execute("UPDATE payments SET holder=?, method=? WHERE id=?", (holder, meth, pay_id))

    def cash_count_setup(self):
        """الجرد المفصّل: رصيد السيستم + اللي مع المناديب والملاك من السندات من آخر جرد، والباقي في الدرج."""
        self._need_login()
        with W.db() as c:
            bal = W.cash_balance(c); hs = holders_setup(c)
            reps = [r[0] for r in c.execute("SELECT name FROM employees WHERE kind='مندوب' AND COALESCE(active,1)=1 ORDER BY name").fetchall()]
            last = c.execute("SELECT * FROM cash_counts ORDER BY id DESC LIMIT 1").fetchone()
            since = last["created_at"] if last else "0000"
            rows = c.execute("SELECT COALESCE(holder,''), COALESCE(method,''), SUM(amount) FROM payments WHERE kind='تحصيل' AND COALESCE(created_at,'')>? AND COALESCE(holder,'')<>'' "
                             "GROUP BY holder, method", (since,)).fetchall()
        rep_set, own_set = set(reps), set(hs["owners"] + hs["accountants"])
        lines = []
        prev = json.loads(last["data"] or "{}").get("lines", []) if last else []
        for l in prev:                                           # اللي كان مع حد في آخر جرد بيفضل معاه (لحد ما يتعدّل)
            if l.get("group") in ("rep", "owner") and float(l.get("amount") or 0): lines.append({"group": l["group"], "who": l["who"], "method": l["method"], "amount": _r2(l["amount"]), "src": "من آخر جرد"})
        for who, meth, amt in rows:
            if who == DRAWER: continue
            g = "rep" if who in rep_set else "owner" if who in own_set else "owner"
            hit = next((x for x in lines if x["group"] == g and x["who"] == who and x["method"] == (meth or "كاش")), None)
            if hit: hit["amount"] = _r2(hit["amount"] + float(amt or 0)); hit["src"] = "آخر جرد + سندات"
            else: lines.append({"group": g, "who": who, "method": meth or "كاش", "amount": _r2(amt), "src": "سندات من آخر جرد"})
        # التحويلات من آخر جرد (من حد لحد / من طريقة لطريقة) — الدرج بيتحسب لوحده
        with W.db() as c2:
            trs = [dict(r) for r in c2.execute("SELECT * FROM cash_transfers WHERE COALESCE(created_at,'')>? ORDER BY id", (since,)).fetchall()]
        def bump(who, meth, amt, src):
            if who == DRAWER: return
            g = "rep" if who in rep_set else "owner"
            hit = next((x for x in lines if x["group"] == g and x["who"] == who and x["method"] == meth), None)
            if hit: hit["amount"] = _r2(hit["amount"] + amt); hit["src"] = (hit.get("src") or "") + (" + تحويل" if "تحويل" not in (hit.get("src") or "") else "")
            else: lines.append({"group": g, "who": who, "method": meth, "amount": _r2(amt), "src": src})
        for t in trs:
            bump(t["from_who"], t["from_method"] or "كاش", -float(t["amount"]), "تحويل")
            bump(t["to_who"], t["to_method"] or "كاش", float(t["amount"]), "تحويل")
        lines = [l for l in lines if abs(l["amount"]) >= 0.005]
        return {"system": _r2(bal), "reps": reps, "owners": hs["owners"] + hs["accountants"], "methods": PAY_METHODS, "lines": lines, "transfers": trs, "drawer": DRAWER,
                "last": {"date": last["c_date"], "at": last["created_at"], "diff": _r2(last["diff"])} if last else None, "today": _today()}

    def assets_report(self, d_from=None, d_to=None):
        """شاشة «الأصول وأرباح الملاك» (للملاك بس): صرف أرباح كل مالك زي المرتبات + الأصول (تريسكل، كمبيوتر ...)."""
        self._need_login()
        if not W.is_owner(): raise UIError("الشاشة دي للملاك بس")
        d_from = d_from or "0000-00-00"; d_to = d_to or "9999-99-99"
        rows = []
        with W.db() as c:
            bal = W._balance_bulk(c, _today())
            for p in c.execute("SELECT id,name,COALESCE(opening,0) AS opening,COALESCE(asset_type,'') AS atype FROM parties WHERE kind=? ORDER BY name", (ASSET,)).fetchall():
                q = lambda sql, *a: c.execute(sql, (p["id"],) + a).fetchone()
                took = q("SELECT COALESCE(SUM(amount),0), COUNT(*), MIN(pay_date) FROM payments WHERE party_id=? AND kind='دفع'")
                per = q("SELECT COALESCE(SUM(CASE WHEN kind='دفع' THEN amount ELSE -amount END),0) FROM payments WHERE party_id=? AND kind IN ('دفع','تحصيل') AND pay_date BETWEEN ? AND ?", d_from, d_to)
                last = q("SELECT pay_date, amount FROM payments WHERE party_id=? AND kind='دفع' ORDER BY pay_date DESC, id DESC LIMIT 1")
                rows.append({"id": p["id"], "name": p["name"], "opening": _r2(p["opening"]), "took": _r2(took[0]), "times": took[1], "first_date": took[2] or "",
                             "p_took": _r2(per[0]), "balance": _r2(bal.get(p["id"], p["opening"])), "last_date": last[0] if last else "", "last_amount": _r2(last[1]) if last else 0,
                             "atype": "أصل" if p["atype"] == "أصل" else "مالك"})
            sug = [{"id": r[0], "name": r[1]} for r in c.execute("SELECT id,name FROM parties WHERE kind<>? AND (name LIKE ? OR name LIKE ?) ORDER BY name", (ASSET, "%ارباح%", "%أرباح%")).fetchall()]
        tot = lambda k, t: _r2(sum(r[k] for r in rows if r["atype"] == t))
        return {"rows": rows, "suggest": sug, "cards": {"owners": tot("balance", "مالك"), "p_took": tot("p_took", "مالك"), "assets": tot("balance", "أصل")}}

    def save_asset(self, a):
        """مالك جديد (حساب أرباحه) أو أصل جديد (تريسكل، كمبيوتر ...) / تعديل."""
        self._need_login()
        if not W.is_owner(): raise UIError("للملاك بس")
        name = (a.get("name") or "").strip()
        if not name: raise UIError("الاسم مطلوب")
        try: opening = W._f(a.get("opening"))
        except ValueError: raise UIError("الرقم مش مظبوط")
        atype = "أصل" if a.get("atype") == "أصل" else "مسحوبات مالك"
        with W.db() as c:
            if c.execute("SELECT 1 FROM parties WHERE name=? AND id<>?", (name, a.get("id") or 0)).fetchone(): raise UIError("الاسم ده موجود قبل كده")
            if a.get("id"):
                c.execute("UPDATE parties SET name=?,opening=?,kind=?,asset_type=? WHERE id=?", (name, opening, ASSET, atype, a["id"])); pid = a["id"]
                W.log(c, "تعديل في الأصول وأرباح الملاك", f"{name} ({atype}) — افتتاحي {W.fmt(opening)}")
            else:
                pid = c.execute("INSERT INTO parties(name,kind,opening,asset_type) VALUES(?,?,?,?)", (name, ASSET, opening, atype)).lastrowid
                W.log(c, "إضافة في الأصول وأرباح الملاك", f"{name} ({atype}) — افتتاحي {W.fmt(opening)}")
        return pid

    def assets_adopt(self, ids):
        """نقل حسابات «ارباح ...» القديمة (كانت متسجلة عملاء) لأرباح الملاك."""
        self._need_login()
        if not W.is_owner(): raise UIError("للملاك بس")
        with W.db() as c:
            for i in ids or []:
                r = c.execute("SELECT name FROM parties WHERE id=?", (i,)).fetchone()
                if not r: continue
                c.execute("UPDATE parties SET kind=?,asset_type='مسحوبات مالك',rep_id=NULL WHERE id=?", (ASSET, i))
                W.log(c, "نقل حساب لأرباح الملاك", r[0])
        return True

    def cash_transfer_add(self, t):
        """تحويل فلوس بين اللي معاهم الفلوس: مندوب / مالك / محاسب / الدرج، ومن طريقة لطريقة (فودافون كاش ← كاش مثلًا)."""
        self._need_login()
        try: amt = _r2(W._f(t.get("amount")))
        except ValueError: raise UIError("المبلغ مش مظبوط")
        if amt <= 0: raise UIError("المبلغ لازم يكون أكبر من صفر")
        with W.db() as c:
            hs = holders_setup(c)
            reps = [r[0] for r in c.execute("SELECT name FROM employees WHERE kind='مندوب'").fetchall()]
            ok = set(reps + hs["owners"] + hs["accountants"] + [DRAWER])
            fw, tw = (t.get("from_who") or "").strip(), (t.get("to_who") or "").strip()
            if fw not in ok or tw not in ok: raise UIError("اختار من مين ولمين")
            fm = t.get("from_method") if t.get("from_method") in PAY_METHODS else "كاش"
            tm = t.get("to_method") if t.get("to_method") in PAY_METHODS else "كاش"
            if fw == DRAWER: fm = "كاش"
            if tw == DRAWER: tm = "كاش"
            if fw == tw and fm == tm: raise UIError("من ولـ نفس الحاجة")
            tid = c.execute("INSERT INTO cash_transfers(t_date,created_at,by_user,from_who,from_method,to_who,to_method,amount,notes) VALUES(?,?,?,?,?,?,?,?,?)",
                            (_today(), W.now_ts(), W.CURRENT_USER.get("username", ""), fw, fm, tw, tm, amt, (t.get("notes") or "").strip())).lastrowid
            W.log(c, "تحويل في الخزنة", f"{W.fmt(amt)}: {fw} ({fm}) ← {tw} ({tm})" + (f" — {t.get('notes')}" if t.get("notes") else ""))
        return tid

    def cash_transfer_delete(self, tid):
        self._need_login()
        with W.db() as c:
            r = c.execute("SELECT * FROM cash_transfers WHERE id=?", (tid,)).fetchone()
            if not r: raise UIError("التحويل مش موجود")
            c.execute("DELETE FROM cash_transfers WHERE id=?", (tid,))
            W.log(c, "حذف تحويل في الخزنة", f"{W.fmt(r['amount'])}: {r['from_who']} ← {r['to_who']}")
        return True

    def cash_count_save(self, data):
        self._need_login()
        lines = []
        for l in data.get("lines") or []:
            try: amt = W._f(l.get("amount"))
            except ValueError: raise UIError("راجع المبالغ في الجرد")
            if abs(amt) < 0.005: continue
            lines.append({"group": l.get("group") if l.get("group") in ("rep", "owner", "drawer") else "drawer", "who": (l.get("who") or "").strip() or DRAWER,
                          "method": l.get("method") if l.get("method") in PAY_METHODS else "كاش", "amount": _r2(amt)})
        counted = _r2(sum(l["amount"] for l in lines))
        with W.db() as c:
            bal = _r2(W.cash_balance(c)); diff = _r2(counted - bal)
            last = c.execute("SELECT created_at FROM cash_counts ORDER BY id DESC LIMIT 1").fetchone()
            trs = [{k: t[k] for k in ("from_who", "from_method", "to_who", "to_method", "amount", "notes", "created_at")}
                   for t in c.execute("SELECT * FROM cash_transfers WHERE COALESCE(created_at,'')>? ORDER BY id", ((last[0] if last else None) or "0000",)).fetchall()]
            cid = c.execute("INSERT INTO cash_counts(c_date,created_at,by_user,system,counted,diff,data) VALUES(?,?,?,?,?,?,?)",
                            (_today(), W.now_ts(), W.CURRENT_USER.get("username", ""), bal, counted, diff, json.dumps({"lines": lines, "notes": (data.get("notes") or "").strip(), "transfers": trs}, ensure_ascii=False))).lastrowid
            W.log(c, "جرد خزنة مفصّل", f"السيستم {W.fmt(bal)} — المعدود {W.fmt(counted)} — " + ("مطابق" if abs(diff) < 0.005 else (f"زيادة {W.fmt(diff)}" if diff > 0 else f"عجز {W.fmt(-diff)}")))
        return {"id": cid, "system": bal, "counted": counted, "diff": diff}

    def _count_row(self, cid=None, day=None):
        with W.db() as c:
            r = c.execute("SELECT * FROM cash_counts WHERE id=?", (cid,)).fetchone() if cid else c.execute("SELECT * FROM cash_counts WHERE c_date=? ORDER BY id DESC LIMIT 1", (day or _today(),)).fetchone()
            st = c.execute("SELECT * FROM settings WHERE id=1").fetchone()
        return r, st

    def _count_html(self, r, st):
        esc = W.esc if hasattr(W, "esc") else (lambda x: str(x))
        d = json.loads(r["data"] or "{}"); lines = d.get("lines", [])
        sec = lambda g, title: ("" if not [l for l in lines if l["group"] == g] else
            f"<h3>{title}</h3><table><tr><th>الاسم</th><th>طريقة الدفع</th><th>المبلغ</th></tr>" + "".join(f"<tr><td>{esc(l['who'])}</td><td>{esc(l['method'])}</td><td class='n'>{W.fmt(l['amount'])}</td></tr>" for l in lines if l["group"] == g)
            + f"<tr class='t'><td colspan='2'>الإجمالي</td><td class='n'>{W.fmt(sum(l['amount'] for l in lines if l['group'] == g))}</td></tr></table>")
        trs = d.get("transfers") or []
        trs_html = "" if not trs else ("<h3>التحويلات</h3><table><tr><th>من</th><th>إلى</th><th>المبلغ</th><th>ملاحظات</th></tr>" + "".join(
            f"<tr><td>{esc(t['from_who'])}{'' if t['from_who'] == DRAWER else ' (' + esc(t['from_method']) + ')'}</td><td>{esc(t['to_who'])}{'' if t['to_who'] == DRAWER else ' (' + esc(t['to_method']) + ')'}</td>"
            f"<td class='n'>{W.fmt(t['amount'])}</td><td>{esc(t.get('notes') or '')}</td></tr>" for t in trs) + "</table>")
        diff = float(r["diff"] or 0)
        res = "مطابق ✔" if abs(diff) < 0.005 else (f"زيادة {W.fmt(diff)}" if diff > 0 else f"عجز {W.fmt(-diff)}")
        return f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><title>جرد الخزنة {r['c_date']}</title><style>
          @page{{size:A4;margin:12mm}} body{{font-family:Tahoma,Arial,sans-serif;font-size:15px;font-weight:bold;color:#000}}
          .hd{{display:flex;justify-content:space-between;align-items:center;border-bottom:2px solid #000;padding-bottom:6px}} .hd img{{height:20mm}}
          h1{{font-size:24px;margin:0}} h2{{font-size:20px;margin:10px 0}} h3{{font-size:18px;margin:14px 0 6px}}
          table{{width:100%;border-collapse:collapse}} td,th{{border:1.5px solid #000;padding:6px 8px;text-align:right}} th{{background:#e8eef7}}
          .n{{text-align:left;direction:ltr}} .t td{{background:#f3f3f3}} .sum td{{font-size:17px}}</style></head><body>
          <div class="hd"><div><h1>{esc((st['company'] if st else '') or W.DEFAULT_COMPANY)}</h1><div>جرد الخزنة — {r['c_date']} ({esc(W.fmt_time(r['created_at']))}) — {esc(r['by_user'] or '')}</div></div><img src="{W.logo_data_uri()}"></div>
          {sec('rep', '١. مع المناديب')}{sec('owner', '٢. مع الملاك')}{sec('drawer', '٣. الدرج (خزنة المخزن)')}{trs_html}
          <h3>الخلاصة</h3><table class="sum"><tr><td>المعدود</td><td class="n">{W.fmt(r['counted'])}</td></tr><tr><td>رصيد الخزنة في السيستم</td><td class="n">{W.fmt(r['system'])}</td></tr>
          <tr><td>النتيجة</td><td class="n">{res}</td></tr></table>{('<p>ملاحظات: ' + esc(d.get('notes')) + '</p>') if d.get('notes') else ''}</body></html>"""

    def cash_count_print(self, cid):
        self._need_login()
        r, st = self._count_row(cid)
        if not r: raise UIError("الجرد مش موجود")
        path = os.path.join(W.PRINT_DIR if hasattr(W, "PRINT_DIR") else W.APP_DATA_DIR, f"cash_count_{r['id']}.html")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f: f.write(self._count_html(r, st))
        W.print_page(path)
        return True

    def cash_count_pdf(self, cid, to_desktop=True):
        """PDF للجرد: على سطح المكتب (أو مجلد النسخ) — بيرجع المسار."""
        self._need_login()
        r, st = self._count_row(cid)
        if not r: raise UIError("الجرد مش موجود")
        html = os.path.join(W.APP_DATA_DIR, "pdfwork", f"cash_count_{r['id']}.html"); os.makedirs(os.path.dirname(html), exist_ok=True)
        with open(html, "w", encoding="utf-8") as f: f.write(self._count_html(r, st))
        folder = os.path.join(os.path.expanduser("~"), "Desktop") if to_desktop else W.backup_dir()
        if not os.path.isdir(folder): folder = os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop") if os.path.isdir(os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop")) else W.backup_dir()
        os.makedirs(folder, exist_ok=True)
        out = os.path.join(folder, f"جرد الخزنة {r['c_date']} ({r['id']}).pdf")
        if not W.html_to_pdf(html, out): raise UIError("مش قادر يعمل PDF (محتاج Edge أو Chrome على الجهاز)")
        return out

    def count_text(self, r):
        d = json.loads(r["data"] or "{}"); lines = d.get("lines", [])
        e = W._e if hasattr(W, "_e") else str
        out = [f"🧮 <b>جرد الخزنة {e(r['c_date'])}</b>"]
        for g, t in (("rep", "مع المناديب"), ("owner", "مع الملاك"), ("drawer", "الدرج")):
            ls = [l for l in lines if l["group"] == g]
            if ls: out.append(f"\n<b>— {t} —</b>"); out += [f"• {e(l['who'])} ({e(l['method'])}): {W.fmt(l['amount'])}" for l in ls]
        diff = float(r["diff"] or 0)
        out.append(f"\n<b>المعدود: {W.fmt(r['counted'])} — السيستم: {W.fmt(r['system'])}</b>")
        out.append("✔ مطابق" if abs(diff) < 0.005 else (f"⬆ زيادة {W.fmt(diff)}" if diff > 0 else f"⬇ عجز {W.fmt(-diff)}"))
        return "\n".join(out)

    def cash_count(self, counted, settle=False):
        """جرد الخزنة: الفرق بين الموجود فعلًا ورصيد البرنامج، ولو settle نسجّل تسوية."""
        self._need_login()
        counted = W._f(counted)
        with W.db() as c: bal = W.cash_balance(c)
        diff = counted - bal
        if settle and abs(diff) >= 0.005:
            msg = (f"زيادة في الخزنة بمقدار {W.fmt(diff)}" if diff > 0 else f"عجز في الخزنة بمقدار {W.fmt(-diff)}")
            with W.db() as c:
                c.execute("INSERT INTO cash_moves(move_date,kind,amount,notes,created_at) VALUES(?,?,?,?,?)", (_today(), "إيداع" if diff > 0 else "سحب", abs(diff), "تسوية جرد", W.now_ts()))
                W.log(c, "جرد خزنة", f"{msg} (رصيد البرنامج {W.fmt(bal)} / الفعلي {W.fmt(counted)})")
        return {"balance": _r2(bal), "diff": _r2(diff)}

    # ---------- العملاء والموردون ----------
    def parties_full(self, kf="الكل", q=""):
        self._need_login()
        out = []; qn = W._norm((q or "").strip())
        with W.db() as c:
            ld = W.last_dates(c)
            for r in c.execute("SELECT p.*,m.name rname FROM parties p LEFT JOIN employees m ON m.id=p.rep_id ORDER BY p.name").fetchall():
                if qn and qn not in W._norm(f"{r['name'] or ''} {r['phone'] or ''} {r['rname'] or ''} {r['address'] or ''}"): continue
                if kf == "عملاء" and r["kind"] in ("مورد", ASSET): continue
                if kf == "موردين" and r["kind"] in ("عميل", ASSET): continue
                if kf == ASSET and r["kind"] != ASSET: continue
                bal = W.party_balance(c, r["id"]); lim = float(r["credit_limit"] or 0)
                if kf == "عليهم فلوس" and bal <= 0.005: continue
                if kf == "ليهم فلوس" and bal >= -0.005: continue
                if kf == "عدّوا الحد الائتماني" and not (lim and bal > lim + 0.005): continue
                out.append({"id": r["id"], "name": r["name"], "kind": r["kind"] or "", "rep": (r["rname"] or W.OFFICE) if r["kind"] not in ("مورد", ASSET) else "",
                            "phone": r["phone"] or "", "address": r["address"] or "", "opening": _r2(r["opening"]), "balance": _r2(bal), "limit": _r2(lim),
                            "over": bool(lim and bal > lim + 0.005), "lc": ld[0].get(r["id"]) or "", "lp": ld[1].get(r["id"]) or ""})
        return out

    def party_get(self, pid):
        self._need_login()
        with W.db() as c:
            r = c.execute("SELECT * FROM parties WHERE id=?", (pid,)).fetchone()
            reps = W.rep_lookup(c, r["rep_id"] if r else None)
        if not r: raise UIError("الحساب مش موجود")
        return {"id": r["id"], "name": r["name"], "kind": r["kind"] or "عميل", "phone": r["phone"] or "", "address": r["address"] or "", "opening": _r2(r["opening"]),
                "rep_id": r["rep_id"], "limit": _r2(r["credit_limit"]), "reps": [{"id": v, "label": k} for k, v in reps.items()]}

    def party_reps(self):
        self._need_login()
        with W.db() as c: reps = W.rep_lookup(c)
        return [{"id": v, "label": k} for k, v in reps.items()]

    def save_party(self, p, owner_pw=None):
        self._need_login()
        name = (p.get("name") or "").strip()
        if not name: raise UIError("الاسم مطلوب")
        try: opening = W._f(p.get("opening"))
        except ValueError: raise UIError("الرصيد الافتتاحي يجب أن يكون رقمًا")
        try: limit = W._f(p.get("limit"))
        except ValueError: raise UIError("الحد الائتماني يجب أن يكون رقمًا")
        if limit < 0: raise UIError("الحد الائتماني لا يكون بالسالب")
        kind = p.get("kind") if p.get("kind") in ("عميل", "مورد", "عميل/مورد", ASSET) else "عميل"
        rep_id = p.get("rep_id"); edit = p.get("id")
        old_limit = 0.0
        if edit:
            with W.db() as c: old_limit = float(c.execute("SELECT COALESCE(credit_limit,0) FROM parties WHERE id=?", (edit,)).fetchone()[0])
        limit_who = None
        if abs(limit - old_limit) > 1e-9:
            limit_who = W.verify_owner_password(owner_pw) if owner_pw else None
            if not limit_who:
                return {"ok": False, "need": "owner", "error": f"تغيير الحد الائتماني لـ«{name}» من {W.fmt(old_limit)} إلى {W.fmt(limit)} محتاج كلمة سر المالك." + ("\nكلمة السر غلط." if owner_pw else "")}
        with W.db() as c:
            rep_txt = f" — المندوب: {W.rep_name_of(c, rep_id)}"
            if limit_who: rep_txt += f" — الحد الائتماني {W.fmt(old_limit)}←{W.fmt(limit)} (بموافقة {limit_who})"
            if edit:
                old = c.execute("SELECT * FROM parties WHERE id=?", (edit,)).fetchone()
                c.execute("UPDATE parties SET name=?,kind=?,phone=?,address=?,opening=?,rep_id=?,credit_limit=? WHERE id=?",
                          (name, kind, (p.get("phone") or "").strip(), (p.get("address") or "").strip(), opening, rep_id, limit, edit))
                extra = f" (الرصيد الافتتاحي {W.fmt(old['opening'])}←{W.fmt(opening)})" if abs(float(old["opening"] or 0) - opening) > 1e-9 else ""
                W.log(c, "تعديل عميل/مورد", name + extra + rep_txt); pid = edit
            else:
                pid = c.execute("INSERT INTO parties(name,kind,phone,address,opening,rep_id,credit_limit) VALUES(?,?,?,?,?,?,?)",
                                (name, kind, (p.get("phone") or "").strip(), (p.get("address") or "").strip(), opening, rep_id, limit)).lastrowid
                W.log(c, "إضافة عميل/مورد", f"{name} (رصيد افتتاحي {W.fmt(opening)})" + rep_txt)
        return {"ok": True, "id": pid}

    # ---------- الأصناف ----------
    def items_full(self, q=""):
        self._need_login()
        qn = W._norm((q or "").strip())
        with W.db() as c:
            stock = W.stock_map(c)
            rows = c.execute("SELECT * FROM items ORDER BY name").fetchall()
        out = []
        for r in rows:
            if qn and qn not in W._norm(f"{r['name'] or ''} {r['code'] or ''}"): continue
            st = stock.get(r["id"], 0.0); mn = float(r["min_stock"] or 0)
            out.append({"id": r["id"], "code": r["code"] or "", "name": r["name"], "unit": r["unit"] or "", "buy": _r2(r["buy_price"]), "sell": _r2(r["sell_price"]),
                        "min": _r2(mn), "opening": _r2(r["opening_qty"]), "stock": _r2(st), "low": bool(mn > 0 and st <= mn)})
        return out

    def save_item(self, p, neg_pw=None):
        self._need_login()
        name = (p.get("name") or "").strip()
        if not name: raise UIError("اسم الصنف مطلوب")
        try: buy = W._f(p.get("buy")); sell = W._f(p.get("sell")); mn = W._f(p.get("min")); oq = W._f(p.get("opening"))
        except ValueError: raise UIError("راجع الأسعار والحد الأدنى ورصيد أول المدة؛ يجب أن تكون أرقامًا")
        code = (p.get("code") or "").strip() or None; unit = (p.get("unit") or "").strip() or "قطعة"; edit = p.get("id")
        who = None
        if neg_pw:
            who = W.verify_owner_password(neg_pw)
            if not who: return {"ok": False, "need": "neg", "error": "كلمة سر المالك غير صحيحة"}
        if oq < 0 and not who: return {"ok": False, "need": "neg", "error": f"رصيد أول المدة لـ«{name}» = {W.fmt(oq)}.\nالرصيد بالسالب محتاج كلمة سر المالك."}
        try:
            W._TLS.allow_neg = who
            with W.db() as c:
                if edit:
                    old = c.execute("SELECT * FROM items WHERE id=?", (edit,)).fetchone()
                    c.execute("UPDATE items SET code=?,name=?,unit=?,buy_price=?,sell_price=?,min_stock=?,opening_qty=? WHERE id=?", (code, name, unit, buy, sell, mn, oq, edit))
                    W.check_stock(c, [edit])
                    ch = []
                    if abs(float(old["opening_qty"] or 0) - oq) > 1e-9: ch.append(f"رصيد أول المدة {W.fmt(old['opening_qty'] or 0)}←{W.fmt(oq)}")
                    if abs(float(old["buy_price"] or 0) - buy) > 1e-9: ch.append(f"سعر الشراء {W.fmt(old['buy_price'])}←{W.fmt(buy)}")
                    if abs(float(old["sell_price"] or 0) - sell) > 1e-9: ch.append(f"سعر البيع {W.fmt(old['sell_price'])}←{W.fmt(sell)}")
                    if old["name"] != name: ch.append(f"الاسم {old['name']}←{name}")
                    W.log(c, "تعديل صنف", f"{name}: " + ("، ".join(ch) or "بدون تغيير في الأسعار"))
                else:
                    c.execute("INSERT INTO items(code,name,unit,buy_price,sell_price,min_stock,opening_qty) VALUES(?,?,?,?,?,?,?)", (code, name, unit, buy, sell, mn, oq))
                    W.log(c, "إضافة صنف", f"{name} (شراء {W.fmt(buy)} / بيع {W.fmt(sell)}" + (f" / رصيد أول المدة {W.fmt(oq)}" if oq else "") + ")")
        except W.DBIntegrityError: raise UIError("كود الصنف مستخدم بالفعل")
        except W.NegativeStock as e: return {"ok": False, "need": "neg", "error": f"{e}\nرصيد أول المدة الجديد أقل من اللي اتباع فعلًا."}
        finally: W._TLS.allow_neg = None
        return {"ok": True}

    def delete_item(self, iid, pw=None):
        self._need_login()
        who = self._del_pw(pw)
        with W.db() as c:
            used = c.execute("SELECT (SELECT COUNT(*) FROM invoice_lines WHERE item_id=?)+(SELECT COUNT(*) FROM damaged WHERE item_id=?)", (iid, iid)).fetchone()[0]
            name = c.execute("SELECT name FROM items WHERE id=?", (iid,)).fetchone()["name"]
        if used: raise UIError("الصنف مستخدم في فواتير أو هالك. تقدر تعدّله بس.")
        with W.db() as c: c.execute("DELETE FROM items WHERE id=?", (iid,)); W.log(c, "حذف صنف", f"{name} (بباسوورد {who})")
        return True

    def item_invoices(self, item_id, d_from=None, d_to=None, kinds=None):
        self._need_login()
        cond, args = "", [item_id]
        if d_from and d_to: cond += f" AND {W.EFFECTIVE_DATE_SQL} BETWEEN ? AND ?"; args += [d_from, d_to]
        if kinds: cond += " AND i.kind IN (" + ",".join("?" * len(kinds)) + ")"; args += list(kinds)
        with W.db() as c:
            it = c.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
            rows = c.execute("SELECT i.id,i.inv_date,i.created_at,i.number,i.kind,p.name party,l.qty,l.price,l.qty*l.price amt FROM invoice_lines l JOIN invoices i ON i.id=l.invoice_id "
                             "LEFT JOIN parties p ON p.id=i.party_id WHERE l.item_id=?" + cond + " ORDER BY i.inv_date DESC,i.id DESC", args).fetchall()
            st = W.stock_of(c, item_id)
        return {"name": it["name"], "unit": it["unit"] or "", "opening": _r2(it["opening_qty"]), "stock": _r2(st),
                "rows": [{"id": r["id"], "date": r["inv_date"], "time": W.fmt_time(r["created_at"]), "number": r["number"], "kind": r["kind"], "party": r["party"] or "",
                          "qty": _r2(r["qty"]), "price": _r2(r["price"]), "amount": _r2(r["amt"])} for r in rows]}

    def stock(self):
        """أرصدة الأصناف: أول المدة، الوارد، الصادر، الهالك، الرصيد، المحجوز."""
        self._need_login()
        today = _today(); out = []
        with W.db() as c:
            direct = {r[0]: float(r[1]) for r in c.execute("SELECT item_id,SUM(qty) FROM damaged WHERE d_date<=? AND production_id IS NULL GROUP BY item_id", (today,))}
            pin, pout = {}, {}                       # الإنتاج: العيش وارد والدقيق صادر (مش هالك)
            for r in c.execute("SELECT item_id, SUM(CASE WHEN qty<0 THEN -qty ELSE 0 END), SUM(CASE WHEN qty>0 THEN qty ELSE 0 END) FROM damaged WHERE d_date<=? AND production_id IS NOT NULL GROUP BY item_id", (today,)):
                pin[r[0]] = float(r[1] or 0); pout[r[0]] = float(r[2] or 0)
            after_map = W.stock_map(c, "9999-12-31")
            for r in c.execute("SELECT it.*,"
                               "COALESCE(SUM(CASE WHEN i.kind='مشتريات' OR (i.kind='مرتجع مبيعات' AND COALESCE(l.damaged,0)=0) THEN l.qty END),0) inn,"
                               "COALESCE(SUM(CASE WHEN i.kind IN ('مبيعات','مرتجع مشتريات') THEN l.qty END),0) outq,"
                               "COALESCE(SUM(CASE WHEN i.kind='مرتجع مبيعات' AND COALESCE(l.damaged,0)=1 THEN l.qty END),0) dret "
                               f"FROM items it LEFT JOIN (invoice_lines l JOIN invoices i ON i.id=l.invoice_id AND {W.EFFECTIVE_DATE_SQL}<=?) ON l.item_id=it.id "
                               "GROUP BY it.id ORDER BY it.name", (today,)).fetchall():
                d = direct.get(r["id"], 0.0); op = float(r["opening_qty"] or 0)
                inn = float(r["inn"]) + pin.get(r["id"], 0.0); outq = float(r["outq"]) + pout.get(r["id"], 0.0)
                st = op + inn - outq - d; mn = float(r["min_stock"] or 0)
                after = after_map.get(r["id"], 0.0); res = st - after
                out.append({"id": r["id"], "code": r["code"] or "", "name": r["name"], "unit": r["unit"] or "", "buy": _r2(r["buy_price"]), "sell": _r2(r["sell_price"]),
                            "opening": _r2(op), "in": _r2(inn), "out": _r2(outq), "dmg": _r2(d + float(r["dret"])), "stock": _r2(st),
                            "reserved": _r2(res) if abs(res) > 1e-9 else 0, "after": _r2(after), "low": bool(mn > 0 and st <= mn)})
        return out

    def save_price(self, iid, buy, sell):
        self._need_login()
        try: buy = W._f(buy); sell = W._f(sell)
        except ValueError: raise UIError("السعر لازم يكون رقم")
        if buy < 0 or sell < 0: raise UIError("السعر مينفعش يكون بالسالب")
        with W.db() as c:
            old = c.execute("SELECT name,buy_price,sell_price FROM items WHERE id=?", (iid,)).fetchone()
            if abs(float(old["buy_price"] or 0) - buy) < 1e-9 and abs(float(old["sell_price"] or 0) - sell) < 1e-9: return {"changed": False}
            c.execute("UPDATE items SET buy_price=?, sell_price=? WHERE id=?", (buy, sell, iid))
            W.log(c, "تعديل سعر صنف", f"{old['name']}: شراء {W.fmt(old['buy_price'] or 0)}←{W.fmt(buy)} / بيع {W.fmt(old['sell_price'] or 0)}←{W.fmt(sell)}")
        return {"changed": True, "warn": bool(sell and buy and sell < buy)}

    def print_stock_count(self):
        self._need_login()
        W.App.print_stock_count(_Quiet())
        return True

    def items_flow(self, kind, d_from, d_to):
        """المبيعات أو المشتريات لكل صنف في الفترة (بعد خصم المرتجع)."""
        self._need_login()
        sale = kind == "مبيعات"; ret = "مرتجع مبيعات" if sale else "مرتجع مشتريات"; kind = "مبيعات" if sale else "مشتريات"
        a = W.check_date(d_from); b = W.check_date(d_to)
        with W.db() as c:
            rows = c.execute(f"""SELECT l.item_id, MIN(l.item_name) nm, MIN(COALESCE(l.unit,'')) un,
                    SUM(CASE i.kind WHEN ? THEN l.qty WHEN ? THEN -l.qty ELSE 0 END) q,
                    SUM(CASE i.kind WHEN ? THEN l.qty*l.price WHEN ? THEN -l.qty*l.price ELSE 0 END) a
                    FROM invoice_lines l JOIN invoices i ON i.id=l.invoice_id
                    WHERE i.kind IN (?,?) AND {W.EFFECTIVE_DATE_SQL} BETWEEN ? AND ? GROUP BY l.item_id""", (kind, ret, kind, ret, kind, ret, a, b)).fetchall()
            codes = {r[0]: r[1] or "" for r in c.execute("SELECT id, code FROM items").fetchall()}
        out = [{"id": r[0], "code": codes.get(r[0], ""), "name": r[1], "unit": r[2], "qty": _r2(r[3]), "amount": _r2(r[4])} for r in rows
               if r[0] is not None and (abs(float(r[3] or 0)) > 1e-9 or abs(float(r[4] or 0)) > 1e-9)]
        out.sort(key=lambda x: -x["amount"])
        return {"kinds": [kind, ret], "rows": out}

    # ---------- الهالك ----------
    def damaged(self, d_from, d_to, src="الكل", q=""):
        self._need_login()
        a = W.check_date(d_from); b = W.check_date(d_to); rows = []
        with W.db() as c:
            eng = W.fifo_engine(c)
            for r in c.execute("SELECT d.*,it.name iname,it.unit FROM damaged d JOIN items it ON it.id=d.item_id WHERE d.d_date BETWEEN ? AND ? AND d.production_id IS NULL", (a, b)):
                cost = eng["dmg"].get(r["id"], float(r["unit_cost"] or 0))
                rows.append({"key": f"d-{r['id']}", "date": r["d_date"], "created": r["created_at"] or "", "time": W.fmt_time(r["created_at"]), "item": r["iname"],
                             "qty": _r2(r["qty"]), "cost": _r2(cost), "value": _r2(float(r["qty"]) * cost), "src": "هالك من المخزن", "notes": r["notes"] or "", "invoice_id": None})
            for r in c.execute("SELECT l.id lid,l.item_id,l.item_name,l.qty,i.id,i.number,i.inv_date,i.created_at,i.notes,p.name pname FROM invoice_lines l JOIN invoices i ON i.id=l.invoice_id "
                               "LEFT JOIN parties p ON p.id=i.party_id WHERE i.kind='مرتجع مبيعات' AND COALESCE(l.damaged,0)=1 AND COALESCE(NULLIF(i.due_date,''), i.inv_date) BETWEEN ? AND ?", (a, b)).fetchall():
                cost = eng["line"].get(r["lid"], 0.0) if r["item_id"] else 0.0
                rows.append({"key": f"r-{r['id']}-{r['lid']}", "date": r["inv_date"], "created": r["created_at"] or "", "time": W.fmt_time(r["created_at"]), "item": r["item_name"],
                             "qty": _r2(r["qty"]), "cost": _r2(cost), "value": _r2(float(r["qty"]) * cost), "src": f"مرتجع هالك — {r['pname'] or ''} (فاتورة {r['number']})",
                             "notes": r["notes"] or "", "invoice_id": r["id"]})
        if src == "مرتجع هالك": rows = [r for r in rows if r["key"].startswith("r-")]
        elif src == "هالك من المخزن": rows = [r for r in rows if r["key"].startswith("d-")]
        qn = W._norm((q or "").strip())
        if qn: rows = [r for r in rows if qn in W._norm(r["item"] + " " + r["src"] + " " + r["notes"])]
        rows.sort(key=lambda r: (r["date"], r["created"]), reverse=True)
        return rows

    def save_damaged(self, item_id, d, qty, notes="", neg_pw=None):
        self._need_login()
        try: qty = W._f(qty); d = W.check_date(d)
        except ValueError: raise UIError("راجع التاريخ والكمية")
        if qty <= 0: raise UIError("الكمية يجب أن تكون أكبر من صفر")
        who = W.verify_owner_password(neg_pw) if neg_pw else None
        if neg_pw and not who: return {"ok": False, "need": "neg", "error": "كلمة سر المالك غير صحيحة"}
        try:
            W._TLS.allow_neg = who
            with W.db() as c:
                name = c.execute("SELECT name FROM items WHERE id=?", (item_id,)).fetchone()[0]
                cost = W.fifo_preview(c, [(item_id, qty)])[0]
                c.execute("INSERT INTO damaged(d_date,created_at,item_id,qty,unit_cost,notes) VALUES(?,?,?,?,?,?)", (d, W.now_ts(), item_id, qty, cost, (notes or "").strip()))
                W.check_stock(c, [item_id])
                W.log(c, "تسجيل هالك", f"{name}: كمية {W.fmt(qty)} بتكلفة {W.fmt(cost)}/وحدة = {W.fmt(qty * cost)}")
        except W.NegativeStock as e: return {"ok": False, "need": "neg", "error": str(e) + "\nالرصيد هيبقى بالسالب — مسموح بس بكلمة سر المالك."}
        finally: W._TLS.allow_neg = None
        return {"ok": True}

    def delete_damaged(self, key):
        self._need_login()
        if not str(key).startswith("d-"): raise UIError("ده مرتجع هالك — عدّله أو احذفه من فاتورة المرتجع نفسها.")
        rid = int(key[2:])
        with W.db() as c:
            r = c.execute("SELECT d.*,it.name iname FROM damaged d JOIN items it ON it.id=d.item_id WHERE d.id=?", (rid,)).fetchone()
            if r and r["production_id"]: raise UIError("ده دقيق اتصرف في الإنتاج — احذفه من سجل الإنتاج.")
            c.execute("DELETE FROM damaged WHERE id=?", (rid,))
            if r: W.log(c, "حذف هالك", f"{r['iname']}: كمية {W.fmt(r['qty'])} بتاريخ {r['d_date']}")
        return True

    # ---------- الإنتاج (للأفران) ----------
    BREADS = ("سياحي",)                 # الفرن بيعمل نوع واحد (البلدي هو السياحي)
    SHBAK = "زبون الشباك"
    TRAY_SIZES = (21, 24, 25)

    @staticmethod
    def _bread_item(c, bread="سياحي"):
        """صنف العيش في المخزن (بيتعمل لوحده أول مرة): الإنتاج بيدخّله والبيع بيطلّعه."""
        name = f"عيش {bread}"
        r = c.execute("SELECT id FROM items WHERE name=?", (name,)).fetchone()
        if r: return r[0]
        return c.execute("INSERT INTO items(code,name,unit,sell_price,buy_price) VALUES(?,?,?,?,?)", (None, name, "رغيف", 0, 0)).lastrowid

    def _shbak(self, c):
        r = c.execute("SELECT id FROM parties WHERE name=?", (self.SHBAK,)).fetchone()
        if r: return r[0]
        return c.execute("INSERT INTO parties(name,kind) VALUES(?,?)", (self.SHBAK, "عميل")).lastrowid

    def _need_prod(self):
        self._need_login()
        if not W.has_feature("production"): raise UIError("شاشة الإنتاج مش متفعّلة في النسخة دي")

    @staticmethod
    def _flour_qty(unit, bags, bag_kg):
        """الدقيق بيتخصم من المخزن بوحدة الصنف: شيكارة = عدد الشكاير، كيلو = الشكاير × وزن الشيكارة، طن = بالطن."""
        u = W._norm(unit or "")
        if "كيلو" in u or "كجم" in u or u in ("كج", "kg"): return bags * bag_kg
        if "طن" in u: return bags * bag_kg / 1000.0
        return bags

    @staticmethod
    def _prod_calc(r):
        bags, bag_kg = float(r["bags"] or 0), float(r["bag_kg"] or 0) or 50.0
        trays, per = float(r["trays"] or 0), float(r["per_tray"] or 0)
        loaves = trays * per; flour_kg = bags * bag_kg
        loaf_g = (flour_kg * 1000.0 / loaves) if loaves else 0.0          # وزن الرغيف = وزن الدقيق ÷ عدد الأرغفة
        return {"loaves": loaves, "flour_kg": flour_kg, "bread_kg": flour_kg, "loaf_g": loaf_g,
                "flour_per_loaf": (flour_kg * 1000.0 / loaves) if loaves else 0.0,     # جرام دقيق في الرغيف
                "loaves_per_bag": (loaves / bags) if bags else 0.0, "trays_per_bag": (trays / bags) if bags else 0.0}

    def production_setup(self):
        self._need_prod()
        with W.db() as c:
            items = []
            for r in c.execute("SELECT id,code,name,unit FROM items ORDER BY name").fetchall():
                items.append({"id": r["id"], "code": r["code"] or "", "name": r["name"], "unit": r["unit"] or "", "stock": _r2(W.stock_of(c, r["id"]))})
            last = {}
            for b in self.BREADS:          # آخر إنتاج لكل نوع = القيم الافتراضية (الطاولة فيها كام رغيف، وزن الرغيف، صنف الدقيق)
                r = c.execute("SELECT * FROM production WHERE bread=? ORDER BY p_date DESC, id DESC LIMIT 1", (b,)).fetchone()
                last[b] = {"per_tray": _r2(r["per_tray"]), "bag_kg": _r2(r["bag_kg"] or 50), "flour_item_id": r["flour_item_id"]} if r else \
                          {"per_tray": 0, "bag_kg": 50, "flour_item_id": None}
        guess = next((i["id"] for i in items if "دقيق" in W._norm(i["name"])), None)
        return {"breads": list(self.BREADS), "items": items, "last": last, "flour_guess": guess, "today": _today(), "tray_sizes": list(self.TRAY_SIZES)}

    def save_production(self, v, neg_pw=None):
        self._need_prod()
        try:
            d = W.check_date(v.get("date") or _today())
            bags = W._f(v.get("bags") or 0); bag_kg = W._f(v.get("bag_kg") or 50); trays = W._f(v.get("trays") or 0)
            per = W._f(v.get("per_tray") or 0)
        except ValueError: raise UIError("راجع الأرقام والتاريخ")
        bread = (v.get("bread") or self.BREADS[0]).strip()
        if bread not in self.BREADS: bread = self.BREADS[0]
        if bags <= 0: raise UIError("عدد شكاير الدقيق لازم يكون أكبر من صفر")
        if bag_kg <= 0: raise UIError("وزن الشيكارة لازم يكون أكبر من صفر")
        if trays <= 0 or per <= 0: raise UIError("اكتب عدد الطاولات وعدد الأرغفة في الطاولة")
        loaf_g = bags * bag_kg * 1000.0 / (trays * per)
        pid = int(v["id"]) if v.get("id") else None
        fid = int(v["flour_item_id"]) if v.get("flour_item_id") else None
        deduct = bool(v.get("deduct", True)) and fid is not None
        with W.db() as c: old = c.execute("SELECT * FROM production WHERE id=?", (pid,)).fetchone() if pid else None
        if pid and not old: raise UIError("الإنتاج ده مش موجود")
        self._day(d, *( [old["p_date"]] if old else []))
        who = W.verify_owner_password(neg_pw) if neg_pw else None
        if neg_pw and not who: return {"ok": False, "need": "neg", "error": "كلمة سر المالك غير صحيحة"}
        try:
            W._TLS.allow_neg = who
            with W.db() as c:
                user = W.CURRENT_USER.get("username") or ""
                if pid:
                    c.execute("UPDATE production SET p_date=?,bread=?,flour_item_id=?,bags=?,bag_kg=?,trays=?,per_tray=?,loaf_g=?,notes=? WHERE id=?",
                              (d, bread, fid, bags, bag_kg, trays, per, loaf_g, (v.get("notes") or "").strip(), pid))
                    old_items = [r[0] for r in c.execute("SELECT item_id FROM damaged WHERE production_id=?", (pid,))]
                    c.execute("DELETE FROM damaged WHERE production_id=?", (pid,))
                else:
                    pid = c.execute("INSERT INTO production(p_date,created_at,bread,flour_item_id,bags,bag_kg,trays,per_tray,loaf_g,notes,by_user) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                                    (d, W.now_ts(), bread, fid, bags, bag_kg, trays, per, loaf_g, (v.get("notes") or "").strip(), user)).lastrowid
                    old_items = []
                fname = ""; ts = W.now_ts(); fcost = 0.0
                if deduct:
                    it = c.execute("SELECT name,unit FROM items WHERE id=?", (fid,)).fetchone()
                    if not it: raise UIError("صنف الدقيق مش موجود")
                    fname = it["name"]; q = self._flour_qty(it["unit"], bags, bag_kg)
                    cost = W.fifo_preview(c, [(fid, q)])[0]; fcost = cost * q
                    c.execute("INSERT INTO damaged(d_date,created_at,item_id,qty,unit_cost,notes,production_id) VALUES(?,?,?,?,?,?,?)",
                              (d, ts, fid, q, cost, f"إنتاج عيش {bread}", pid))
                bid = self._bread_item(c, bread); loaves = trays * per          # العيش اللي اتعمل بيدخل المخزن (سالب في جدول الصرف = وارد)
                c.execute("INSERT INTO damaged(d_date,created_at,item_id,qty,unit_cost,notes,production_id) VALUES(?,?,?,?,?,?,?)",
                          (d, ts, bid, -loaves, fcost / loaves, f"إنتاج عيش {bread}", pid))
                W.check_stock(c, list({*old_items, bid, *([fid] if deduct else [])}))
                k = self._prod_calc({"bags": bags, "bag_kg": bag_kg, "trays": trays, "per_tray": per, "loaf_g": loaf_g})
                W.log(c, "تعديل إنتاج" if old else "تسجيل إنتاج",
                      f"عيش {bread} {d}: {W.fmt(bags)} شيكارة{(' ' + fname) if fname else ''} ← {W.fmt(trays)} طاولة × {W.fmt(per)} = {W.fmt(k['loaves'])} رغيف")
        except W.NegativeStock as e: return {"ok": False, "need": "neg", "error": str(e) + "\nالرصيد هيبقى بالسالب — مسموح بس بكلمة سر المالك."}
        finally: W._TLS.allow_neg = None
        return {"ok": True, "id": pid}

    def production_list(self, d_from, d_to, bread="الكل"):
        self._need_prod()
        a = W.check_date(d_from); b = W.check_date(d_to)
        if a > b: raise UIError("تاريخ البداية بعد تاريخ النهاية")
        rows = []
        with W.db() as c:
            eng = None
            cost_of = {}
            dm = c.execute("SELECT id, production_id, qty, unit_cost FROM damaged WHERE production_id IS NOT NULL AND qty>0 AND d_date BETWEEN ? AND ?", (a, b)).fetchall()
            if dm:
                eng = W.fifo_engine(c)
                for r in dm: cost_of[r["production_id"]] = cost_of.get(r["production_id"], 0.0) + float(r["qty"] or 0) * eng["dmg"].get(r["id"], float(r["unit_cost"] or 0))
            for r in c.execute("SELECT p.*, it.name fname FROM production p LEFT JOIN items it ON it.id=p.flour_item_id WHERE p.p_date BETWEEN ? AND ? ORDER BY p.p_date DESC, p.id DESC", (a, b)).fetchall():
                if bread not in ("الكل", "", None) and r["bread"] != bread: continue
                k = self._prod_calc(r); cost = cost_of.get(r["id"], 0.0)
                rows.append({"id": r["id"], "date": r["p_date"], "time": W.fmt_time(r["created_at"]), "bread": r["bread"], "flour": r["fname"] or "", "flour_item_id": r["flour_item_id"],
                             "deducted": r["id"] in cost_of, "bags": _r2(r["bags"]), "bag_kg": _r2(r["bag_kg"]), "trays": _r2(r["trays"]), "per_tray": _r2(r["per_tray"]),
                             "loaf_g": _r2(k["loaf_g"]), "loaves": _r2(k["loaves"]), "flour_kg": _r2(k["flour_kg"]), "bread_kg": _r2(k["bread_kg"]),
                             "flour_per_loaf": _r2(k["flour_per_loaf"]), "loaves_per_bag": _r2(k["loaves_per_bag"]), "cost": _r2(cost),
                             "loaf_cost": round(cost / k["loaves"], 4) if k["loaves"] else 0, "notes": r["notes"] or "", "user": r["by_user"] or ""})
        # ملخص لكل يوم ولكل نوع
        days = {}
        for r in rows:
            dd = days.setdefault((r["date"], r["bread"]), {"date": r["date"], "bread": r["bread"], "bags": 0.0, "trays": 0.0, "loaves": 0.0, "flour_kg": 0.0, "bread_kg": 0.0, "cost": 0.0})
            for f in ("bags", "trays", "loaves", "flour_kg", "bread_kg", "cost"): dd[f] += r[f]
        summary = sorted(days.values(), key=lambda x: (x["date"], x["bread"]), reverse=True)
        for x in summary:
            x["loaves_per_bag"] = _r2(x["loaves"] / x["bags"]) if x["bags"] else 0
            for f in ("bags", "trays", "loaves", "flour_kg", "bread_kg", "cost"): x[f] = _r2(x[f])
        tot = {}
        for b_ in self.BREADS:
            rs = [r for r in rows if r["bread"] == b_]
            if rs:
                bags = sum(r["bags"] for r in rs); loaves = sum(r["loaves"] for r in rs)
                tot[b_] = {"bags": _r2(bags), "loaves": _r2(loaves), "trays": _r2(sum(r["trays"] for r in rs)), "bread_kg": _r2(sum(r["bread_kg"] for r in rs)),
                           "cost": _r2(sum(r["cost"] for r in rs)), "loaves_per_bag": _r2(loaves / bags) if bags else 0}
        return {"rows": rows, "summary": summary, "totals": tot}

    def delete_production(self, pid, neg_pw=None):
        self._need_prod()
        with W.db() as c:
            r = c.execute("SELECT * FROM production WHERE id=?", (pid,)).fetchone()
        if not r: raise UIError("الإنتاج ده مش موجود")
        self._day(r["p_date"])
        who = W.verify_owner_password(neg_pw) if neg_pw else None
        if neg_pw and not who: return {"ok": False, "need": "neg", "error": "كلمة سر المالك غير صحيحة"}
        try:
            W._TLS.allow_neg = who
            with W.db() as c:
                its = [x[0] for x in c.execute("SELECT item_id FROM damaged WHERE production_id=?", (pid,))]
                c.execute("DELETE FROM damaged WHERE production_id=?", (pid,))
                c.execute("DELETE FROM production WHERE id=?", (pid,))
                W.check_stock(c, its)
                W.log(c, "حذف إنتاج", f"عيش {r['bread']} {r['p_date']}: {W.fmt(r['bags'])} شيكارة ← {W.fmt(float(r['trays'] or 0) * float(r['per_tray'] or 0))} رغيف")
        except W.NegativeStock as e: return {"ok": False, "need": "neg", "error": str(e) + "\nالعيش ده اتباع — لو اتحذف الرصيد هيبقى بالسالب (مسموح بس بكلمة سر المالك)."}
        finally: W._TLS.allow_neg = None
        return {"ok": True}

    # ---------- بيع الشباك (كام رغيف + بكام = فاتورة نقدي على طول) ----------
    def sell_setup(self):
        self._need_prod()
        today = _today()
        with W.db() as c:
            bid = self._bread_item(c); shb = self._shbak(c)
            it = c.execute("SELECT name,unit,sell_price FROM items WHERE id=?", (bid,)).fetchone()
            prod = -float(c.execute("SELECT COALESCE(SUM(qty),0) FROM damaged WHERE item_id=? AND production_id IS NOT NULL AND qty<0 AND d_date=?", (bid, today)).fetchone()[0])
            sold = c.execute("SELECT COALESCE(SUM(CASE WHEN i.kind='مبيعات' THEN l.qty ELSE -l.qty END),0), "
                             "COALESCE(SUM(CASE WHEN i.kind='مبيعات' THEN l.qty*l.price ELSE -l.qty*l.price END),0) "
                             "FROM invoice_lines l JOIN invoices i ON i.id=l.invoice_id WHERE l.item_id=? AND i.kind IN ('مبيعات','مرتجع مبيعات') AND i.inv_date=?", (bid, today)).fetchone()
            cash = float(c.execute("SELECT COALESCE(SUM(p.amount),0) FROM payments p JOIN invoices i ON i.id=p.invoice_id JOIN invoice_lines l ON l.invoice_id=i.id "
                                   "WHERE l.item_id=? AND i.kind='مبيعات' AND i.inv_date=?", (bid, today)).fetchone()[0])
            stock = W.stock_of(c, bid)
            custs = [{"id": r["id"], "name": r["name"]} for r in c.execute("SELECT id,name FROM parties WHERE kind LIKE '%عميل%' AND id<>? ORDER BY name", (shb,)).fetchall()]
            recent = []
            for r in c.execute(f"SELECT i.id,i.number,i.created_at,p.name party,l.qty,l.price,{W.NET_SQL} net, COALESCE((SELECT SUM(amount) FROM payments WHERE invoice_id=i.id),0) paid, "
                               "COALESCE(i.by_user,'') by_user FROM invoices i JOIN invoice_lines l ON l.invoice_id=i.id LEFT JOIN parties p ON p.id=i.party_id "
                               "WHERE l.item_id=? AND i.kind='مبيعات' AND i.inv_date=? ORDER BY i.created_at DESC, i.id DESC LIMIT 30", (bid, today)).fetchall():
                recent.append({"id": r["id"], "number": r["number"], "time": W.fmt_time(r["created_at"]), "party": r["party"] or "", "qty": _r2(r["qty"]),
                               "net": _r2(r["net"]), "paid": _r2(r["paid"]), "user": r["by_user"]})
        return {"item_id": bid, "item": it["name"], "unit": it["unit"] or "رغيف", "price": _r2(it["sell_price"]), "shbak_id": shb, "customers": custs,
                "today": {"produced": _r2(prod), "sold": _r2(sold[0]), "amount": _r2(sold[1]), "cash": _r2(cash), "stock": _r2(stock)}, "recent": recent, "date": today}

    def quick_sale(self, qty, amount, party_id=None, cash=True):
        """البياع بيكتب كام رغيف وبكام → فاتورة مبيعات بتتسجل على طول (الشباك = نقدي)."""
        self._need_prod()
        try: qty = W._f(qty); amount = W._f(amount)
        except ValueError: raise UIError("اكتب عدد الأرغفة والمبلغ بالأرقام")
        if qty <= 0: raise UIError("اكتب كام رغيف")
        if amount < 0: raise UIError("المبلغ مش بالسالب")
        d = _today(); self._day(d)
        with W.db() as c:
            bid = self._bread_item(c); shb = self._shbak(c)
            it = c.execute("SELECT name,unit FROM items WHERE id=?", (bid,)).fetchone()
            pid = int(party_id) if party_id else shb
            if not c.execute("SELECT 1 FROM parties WHERE id=?", (pid,)).fetchone(): raise UIError("العميل مش موجود")
        is_shb = pid == shb
        if is_shb: cash = True
        lines = [{"item_id": bid, "name": it["name"], "unit": it["unit"] or "رغيف", "qty": qty, "price": amount / qty, "damaged": 0}]
        try:
            dd = W.prepare_invoice("مبيعات", lines, pid, "", d, "", 0, amount if cash else 0, "نقدي" if cash else "آجل", "بيع سريع" + (" — الشباك" if is_shb else ""), None, None)
        except W.InvoiceInputError as e: raise UIError(str(e))
        try:
            W._TLS.allow_neg = "بيع الشباك"                  # البيع ميقفش — لو الرصيد سالب بيبان في لوحة النهارده
            inv_id, number = W.persist_invoice(dd, override=False, auto_no=True)
        except W.CreditLimitExceeded as e:
            raise UIError(f"العميل «{e.name}» هيعدّي الحد الائتماني ({W.fmt(e.limit)}) — سجّلها من فاتورة المبيعات بكلمة سر المالك")
        finally: W._TLS.allow_neg = None
        with W.db() as c:
            c.execute("UPDATE invoices SET by_user=? WHERE id=?", (W.CURRENT_USER.get("username") or "", inv_id))
            W.log(c, "بيع سريع", f"{W.fmt(qty)} رغيف بـ {W.fmt(amount)} — {'الشباك' if is_shb else 'عميل'} (فاتورة {number})")
        return {"ok": True, "id": inv_id, "number": number}

    def print_production(self, d_from, d_to, bread="الكل"):
        self._need_prod()
        d = self.production_list(d_from, d_to, bread)
        if not d["rows"]: raise UIError("مفيش إنتاج في الفترة دي")
        with W.db() as c: st = c.execute("SELECT * FROM settings WHERE id=1").fetchone()
        esc = W.esc; f = W.fmt
        tot_rows = "".join(f"<tr><td>{f(t['bags'])}</td><td>{f(t['trays'])}</td><td><b>{f(t['loaves'])}</b></td><td>{f(t['loaves_per_bag'])}</td><td>{f(t['bread_kg'])}</td></tr>"
                           for b, t in d["totals"].items())
        sum_rows = "".join(f"<tr><td>{x['date']}</td><td>{f(x['bags'])}</td><td>{f(x['trays'])}</td><td><b>{f(x['loaves'])}</b></td><td>{f(x['loaves_per_bag'])}</td><td>{f(x['bread_kg'])}</td></tr>"
                           for x in d["summary"])
        det = "".join(f"<tr><td>{r['date']}</td><td>{r['time']}</td><td>{f(r['bags'])}</td><td>{f(r['trays'])}</td><td>{f(r['per_tray'])}</td><td><b>{f(r['loaves'])}</b></td>"
                      f"<td>{f(r['loaf_g'])}</td><td>{f(r['bread_kg'])}</td><td class='nm'>{esc(r['notes'])}</td></tr>" for r in d["rows"])
        title = "تقرير الإنتاج"
        html = f"""<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8"><title>{title}</title><style>
        @page{{size:A4;margin:10mm}}body{{font-family:Tahoma,Arial,sans-serif;font-size:12.5px;color:#111;margin:0}}
        .hd{{display:flex;align-items:center;justify-content:space-between;border-bottom:2px solid #333;padding-bottom:6px}}.hd img{{height:58px}}
        h1{{margin:0;font-size:21px}}h2{{text-align:center;margin:10px 0 2px}}.sub{{text-align:center;color:#444;margin-bottom:6px}}h3{{margin:12px 0 4px}}
        table{{width:100%;border-collapse:collapse}}th,td{{border:1px solid #666;padding:4px 5px;text-align:center}}th{{background:#efe7da}}td.nm{{text-align:right}}
        thead{{display:table-header-group}}tr{{break-inside:avoid}}</style>
        <div class="hd"><div><h1>{esc(st['company'] or W.DEFAULT_COMPANY)}</h1><div>{esc(st['tagline'] or '')}</div></div><img src="{W.logo_data_uri()}"></div>
        <h2>{title}</h2><div class="sub">من {d_from} إلى {d_to}</div>
        <h3>الإجمالي</h3><table><thead><tr><th>شكاير الدقيق</th><th>الطاولات</th><th>الأرغفة</th><th>رغيف/شيكارة</th><th>الدقيق (كجم)</th></tr></thead><tbody>{tot_rows}</tbody></table>
        <h3>كل يوم</h3><table><thead><tr><th>التاريخ</th><th>شكاير</th><th>طاولات</th><th>أرغفة</th><th>رغيف/شيكارة</th><th>الدقيق (كجم)</th></tr></thead><tbody>{sum_rows}</tbody></table>
        <h3>التفاصيل</h3><table><thead><tr><th>التاريخ</th><th>الوقت</th><th>شكاير</th><th>طاولات</th><th>رغيف/طاولة</th><th>الأرغفة</th><th>وزن الرغيف (جم)</th><th>الدقيق (كجم)</th><th>ملاحظات</th></tr></thead>
        <tbody>{det}</tbody></table></html>"""
        path = os.path.join(W.PRINT_DIR, "production.html"); os.makedirs(W.PRINT_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh: fh.write(html)
        W.print_page(path)
        return True

    # ---------- العينات ----------
    SAMPLE_IN = "عينات مشتريات"; SAMPLE_OUT = "عينات مبيعات"

    def _sample_bal(self, c, sid):
        r = c.execute("SELECT COALESCE(SUM(CASE WHEN kind=? THEN qty ELSE 0 END),0) inn, COALESCE(SUM(CASE WHEN kind=? THEN qty ELSE 0 END),0) outq FROM samples WHERE sample_item_id=?",
                      (self.SAMPLE_IN, self.SAMPLE_OUT, sid)).fetchone()
        return float(r["inn"]), float(r["outq"])

    def sample_items(self):
        self._need_login(); out = []
        with W.db() as c:
            for r in c.execute("SELECT * FROM sample_items ORDER BY name").fetchall():
                inn, o = self._sample_bal(c, r["id"])
                out.append({"id": r["id"], "code": r["code"] or "", "name": r["name"], "unit": r["unit"] or "", "label": W.item_label(r), "in": _r2(inn), "out": _r2(o), "balance": _r2(inn - o)})
        return out

    def save_sample_item(self, p):
        self._need_login()
        name = (p.get("name") or "").strip()
        if not name: raise UIError("اسم العينة مطلوب")
        code = (p.get("code") or "").strip() or None; unit = (p.get("unit") or "").strip() or "قطعة"
        try:
            with W.db() as c:
                if p.get("id"): c.execute("UPDATE sample_items SET code=?,name=?,unit=? WHERE id=?", (code, name, unit, p["id"])); W.log(c, "تعديل صنف عينة", name)
                else: c.execute("INSERT INTO sample_items(code,name,unit) VALUES(?,?,?)", (code, name, unit)); W.log(c, "إضافة صنف عينة", name)
        except W.DBIntegrityError: raise UIError("كود العينة مستخدم بالفعل")
        return True

    def delete_sample_item(self, sid):
        self._need_login()
        with W.db() as c:
            used = c.execute("SELECT COUNT(*) FROM samples WHERE sample_item_id=?", (sid,)).fetchone()[0]
            name = c.execute("SELECT name FROM sample_items WHERE id=?", (sid,)).fetchone()["name"]
        if used: raise UIError("العينة ليها حركات مسجّلة. تقدر تعدّلها بس.")
        with W.db() as c: c.execute("DELETE FROM sample_items WHERE id=?", (sid,)); W.log(c, "حذف صنف عينة", name)
        return True

    def sample_moves(self, sid):
        self._need_login()
        with W.db() as c:
            it = c.execute("SELECT * FROM sample_items WHERE id=?", (sid,)).fetchone()
            rows = c.execute("SELECT s.*,p.name pname FROM samples s LEFT JOIN parties p ON p.id=s.party_id WHERE s.sample_item_id=? ORDER BY s.s_date,s.id", (sid,)).fetchall()
        bal = 0.0; out = []
        for r in rows:
            inn = r["kind"] == self.SAMPLE_IN; q = float(r["qty"]); bal += q if inn else -q
            out.append({"date": r["s_date"], "time": W.fmt_time(r["created_at"]), "kind": r["kind"], "party": r["pname"] or "", "in": _r2(q) if inn else 0, "out": 0 if inn else _r2(q),
                        "balance": _r2(bal), "cost": _r2(r["cost"]), "notes": r["notes"] or ""})
        return {"name": it["name"], "unit": it["unit"] or "", "rows": out, "balance": _r2(bal)}

    def samples(self, kind, d_from, d_to, q=""):
        self._need_login()
        a = W.check_date(d_from); b = W.check_date(d_to); qn = W._norm((q or "").strip())
        with W.db() as c:
            rows = c.execute("SELECT s.*,si.name iname,si.unit,p.name pname FROM samples s JOIN sample_items si ON si.id=s.sample_item_id LEFT JOIN parties p ON p.id=s.party_id "
                             "WHERE s.kind=? AND s.s_date BETWEEN ? AND ? ORDER BY s.s_date DESC,s.id DESC", (kind, a, b)).fetchall()
        return [{"id": r["id"], "date": r["s_date"], "time": W.fmt_time(r["created_at"]), "item": r["iname"], "unit": r["unit"] or "", "qty": _r2(r["qty"]), "cost": _r2(r["cost"]),
                 "party": r["pname"] or "", "notes": r["notes"] or ""} for r in rows
                if not qn or qn in W._norm(" ".join([r["iname"] or "", r["pname"] or "", r["notes"] or ""]))]

    def save_sample(self, kind, p, force=False):
        self._need_login()
        if kind not in (self.SAMPLE_IN, self.SAMPLE_OUT): raise UIError("نوع غلط")
        sid = p.get("item_id")
        if not sid: raise UIError("اختر العينة")
        try: qty = W._f(p.get("qty")); cost = W._f(p.get("cost")); d = W.check_date(p.get("date") or "")
        except ValueError: raise UIError("راجع التاريخ والكمية والتكلفة")
        if qty <= 0 or cost < 0: raise UIError("الكمية يجب أن تكون أكبر من صفر والتكلفة غير سالبة")
        pid = p.get("party_id")
        with W.db() as c:
            if kind == self.SAMPLE_OUT and not force:
                inn, o = self._sample_bal(c, sid)
                if qty > inn - o + 1e-9: return {"ok": False, "confirm": f"رصيد العينة المسجّل {W.fmt(inn - o)} بس.\nتكمل التسجيل؟"}
            iname = c.execute("SELECT name FROM sample_items WHERE id=?", (sid,)).fetchone()[0]
            pname = c.execute("SELECT name FROM parties WHERE id=?", (pid,)).fetchone()[0] if pid else ""
            c.execute("INSERT INTO samples(s_date,created_at,kind,sample_item_id,qty,cost,party_id,notes) VALUES(?,?,?,?,?,?,?,?)",
                      (d, W.now_ts(), kind, sid, qty, cost, pid, (p.get("notes") or "").strip()))
            W.log(c, kind, f"{iname}: كمية {W.fmt(qty)}، تكلفة {W.fmt(cost)}" + (f" — {pname}" if pname else ""))
        return {"ok": True}

    def delete_sample(self, rid):
        self._need_login()
        with W.db() as c:
            r = c.execute("SELECT s.*,si.name iname FROM samples s JOIN sample_items si ON si.id=s.sample_item_id WHERE s.id=?", (rid,)).fetchone()
            c.execute("DELETE FROM samples WHERE id=?", (rid,))
            if r: W.log(c, "حذف حركة عينة", f"{r['kind']}: {r['iname']} كمية {W.fmt(r['qty'])} بتاريخ {r['s_date']}")
        return True

    # ---------- التقارير ----------
    def _owner(self):
        self._need_login()
        if not W.is_owner(): raise UIError("الشاشة دي للمالك بس")

    def profit(self, d_from, d_to):
        self._owner()
        a = W.check_date(d_from); b = W.check_date(d_to)
        if a > b: raise UIError("تاريخ البداية بعد تاريخ النهاية")
        ps = W.profit_summary(a, b)
        with W.db() as c: ids = {r[1]: r[0] for r in c.execute("SELECT id,name FROM items").fetchall()}
        return {"metrics": [[l, _r2(v)] for l, v in W.metric_rows(ps)], "net": _r2(ps["actual"]), "gross": _r2(ps["gross"]),
                "rows": [{"id": ids.get(r[0]), "name": r[0], "qty": _r2(r[1]), "rev": _r2(r[2]), "avg": _r2(r[3]), "cost": _r2(r[4]), "profit": _r2(r[5])} for r in ps["rows"]],
                "by_cat": [[n, _r2(v)] for n, v in ps["by_cat"]]}

    # ---------- التقرير الشهري (للملاك) ----------
    @staticmethod
    def _month_range(month):
        import calendar
        try: y, m = int(month[:4]), int(month[5:7]); assert 1 <= m <= 12
        except Exception: raise UIError("الشهر مش مظبوط")
        return f"{y:04d}-{m:02d}-01", f"{y:04d}-{m:02d}-{calendar.monthrange(y, m)[1]:02d}", (f"{y - 1:04d}-12" if m == 1 else f"{y:04d}-{m - 1:02d}")

    def _month_core(self, a, b):
        ps = W.profit_summary(a, b); E = W.EFFECTIVE_DATE_SQL
        with W.db() as c:
            inv = {r[0]: (r[1], _r2(r[2])) for r in c.execute(f"SELECT i.kind, COUNT(*), COALESCE(SUM({W.NET_SQL}),0) FROM invoices i WHERE {E} BETWEEN ? AND ? GROUP BY i.kind", (a, b)).fetchall()}
            pay = {r[0]: _r2(r[1]) for r in c.execute("SELECT kind, COALESCE(SUM(amount),0) FROM payments WHERE pay_date BETWEEN ? AND ? GROUP BY kind", (a, b)).fetchall()}
        g = lambda k: inv.get(k, (0, 0.0))
        return ps, {"sales": g("مبيعات")[1], "n_sales": g("مبيعات")[0], "ret": g("مرتجع مبيعات")[1], "buys": g("مشتريات")[1], "n_buys": g("مشتريات")[0],
                    "buy_ret": g("مرتجع مشتريات")[1], "collect": pay.get("تحصيل", 0.0), "paid": pay.get("دفع", 0.0), "disc": pay.get(W.DISC_KIND, 0.0),
                    "gross": _r2(ps["gross"]), "exp": _r2(ps["exp_total"]), "net": _r2(ps["actual"]), "general": _r2(ps["general"]), "salary": _r2(ps["salary"]),
                    "adv": _r2(ps["adv"]), "damaged": _r2(ps["damaged"]), "commission": _r2(ps["commission"])}

    def monthly_report(self, month=None):
        """تقرير شهري لكل الشركة: الأرقام الأساسية + مقارنة بالشهر اللي قبله + جداول (أيام، عملاء، أصناف، مناديب، مصروفات، خزنة)."""
        self._owner()
        month = (month or _today()[:7])[:7]
        a, b, prev = self._month_range(month)
        pa, pb, _ = self._month_range(prev)
        ps, k = self._month_core(a, b)
        _, pk = self._month_core(pa, pb)
        E = W.EFFECTIVE_DATE_SQL
        with W.db() as c:
            days = {}
            for d, kind, n, t in c.execute(f"SELECT {E} d, i.kind, COUNT(*), COALESCE(SUM({W.NET_SQL}),0) FROM invoices i WHERE {E} BETWEEN ? AND ? GROUP BY d, i.kind", (a, b)).fetchall():
                x = days.setdefault(d, {"date": d, "sales": 0.0, "ret": 0.0, "buys": 0.0, "n": 0, "collect": 0.0, "exp": 0.0})
                if kind == "مبيعات": x["sales"] += float(t); x["n"] += n
                elif kind == "مرتجع مبيعات": x["ret"] += float(t)
                elif kind == "مشتريات": x["buys"] += float(t)
            for d, t in c.execute("SELECT pay_date, COALESCE(SUM(amount),0) FROM payments WHERE kind='تحصيل' AND pay_date BETWEEN ? AND ? GROUP BY pay_date", (a, b)).fetchall():
                days.setdefault(d, {"date": d, "sales": 0.0, "ret": 0.0, "buys": 0.0, "n": 0, "collect": 0.0, "exp": 0.0})["collect"] += float(t)
            for d, t in c.execute("SELECT exp_date, COALESCE(SUM(amount),0) FROM expenses WHERE exp_date BETWEEN ? AND ? GROUP BY exp_date", (a, b)).fetchall():
                days.setdefault(d, {"date": d, "sales": 0.0, "ret": 0.0, "buys": 0.0, "n": 0, "collect": 0.0, "exp": 0.0})["exp"] += float(t)
            days = [{kk: (_r2(v) if isinstance(v, float) else v) for kk, v in x.items()} for _, x in sorted(days.items())]
            cust = c.execute(f"SELECT p.id, p.name, SUM(CASE WHEN i.kind='مبيعات' THEN {W.NET_SQL} ELSE -{W.NET_SQL} END) net, SUM(CASE WHEN i.kind='مبيعات' THEN 1 ELSE 0 END) n "
                             f"FROM invoices i JOIN parties p ON p.id=i.party_id WHERE i.kind IN ('مبيعات','مرتجع مبيعات') AND {E} BETWEEN ? AND ? GROUP BY p.id, p.name ORDER BY net DESC LIMIT 15", (a, b)).fetchall()
            col = {r[0]: float(r[1]) for r in c.execute("SELECT party_id, SUM(amount) FROM payments WHERE kind='تحصيل' AND pay_date BETWEEN ? AND ? GROUP BY party_id", (a, b)).fetchall()}
            customers = [{"id": r[0], "name": r[1], "net": _r2(r[2]), "n": r[3], "collect": _r2(col.get(r[0], 0))} for r in cust]
            reps = []
            for rid, name in [(r[0], r[1]) for r in c.execute("SELECT id,name FROM employees WHERE kind='مندوب' OR id IN (SELECT rep_id FROM invoices WHERE rep_id IS NOT NULL) ORDER BY name").fetchall()] + [(None, W.OFFICE)]:
                cond = "i.rep_id=?" if rid else "i.rep_id IS NULL"; arg = (rid,) if rid else ()
                s = c.execute(f"SELECT COUNT(*), COALESCE(SUM({W.NET_SQL}),0) FROM invoices i WHERE i.kind='مبيعات' AND {cond} AND {E} BETWEEN ? AND ?", arg + (a, b)).fetchone()
                cl = c.execute(f"SELECT COALESCE(SUM(amount),0) FROM payments WHERE kind='تحصيل' AND {'rep_id=?' if rid else 'rep_id IS NULL'} AND pay_date BETWEEN ? AND ?", arg + (a, b)).fetchone()[0]
                if s[0] or cl: reps.append({"name": name, "n": s[0], "sales": _r2(s[1]), "collect": _r2(cl)})
            moves = W.treasury_moves(c); opening = W.cash_opening(c)
            ob = opening + sum(m[5] - m[6] for m in moves if m[0] < a)
            cin = sum(m[5] for m in moves if a <= m[0] <= b); cout = sum(m[6] for m in moves if a <= m[0] <= b)
            bal = W._balance_bulk(c, b)
            kinds = {r[0]: r[1] for r in c.execute("SELECT id,kind FROM parties").fetchall()}
            recv = sum(v for pid, v in bal.items() if v > 0 and kinds.get(pid) not in ("مورد", ASSET))
            payb = -sum(v for pid, v in bal.items() if v < 0 and kinds.get(pid) != ASSET)
            owners = _r2(c.execute("SELECT COALESCE(SUM(p.amount),0) FROM payments p JOIN parties t ON t.id=p.party_id WHERE t.kind=? AND COALESCE(t.asset_type,'')<>'أصل' AND p.kind='دفع' AND p.pay_date BETWEEN ? AND ?", (ASSET, a, b)).fetchone()[0])
        items = sorted(ps["rows"], key=lambda r: -r[5])
        return {"month": month, "from": a, "to": b, "prev": prev, "k": k, "pk": pk, "days": days, "customers": customers, "reps": reps,
                "items": [{"name": r[0], "qty": _r2(r[1]), "rev": _r2(r[2]), "cost": _r2(r[4]), "profit": _r2(r[5])} for r in items[:15]],
                "items_low": [{"name": r[0], "qty": _r2(r[1]), "rev": _r2(r[2]), "profit": _r2(r[5])} for r in items[-5:] if r[5] < 0],
                "exp_cats": [[n, _r2(v)] for n, v in ps["by_cat"]], "metrics": [[l, _r2(v)] for l, v in W.metric_rows(ps)],
                "cash": {"open": _r2(ob), "in": _r2(cin), "out": _r2(cout), "close": _r2(ob + cin - cout)},
                "end": {"recv": _r2(recv), "pay": _r2(payb), "owners": owners}}

    def monthly_print(self, month=None):
        d = self.monthly_report(month)
        esc = W.esc; f = W.fmt; k = d["k"]; pk = d["pk"]
        with W.db() as c: st = c.execute("SELECT * FROM settings WHERE id=1").fetchone()
        def chg(a, b): return "—" if not b else f"{(a - b) / abs(b) * 100:+.0f}%"
        tbl = lambda head, rows: "<table><tr>" + "".join(f"<th>{h}</th>" for h in head) + "</tr>" + "".join("<tr>" + "".join(f"<td{' class=n' if isinstance(v, (int, float)) else ''}>{f(v) if isinstance(v, float) else esc(str(v))}</td>" for v in r) + "</tr>" for r in rows) + "</table>"
        key = [("المبيعات", k["sales"], pk["sales"]), ("المرتجعات", k["ret"], pk["ret"]), ("المشتريات", k["buys"], pk["buys"]), ("التحصيلات", k["collect"], pk["collect"]),
               ("المدفوع للموردين", k["paid"], pk["paid"]), ("إجمالي الربح", k["gross"], pk["gross"]), ("المصروفات", k["exp"], pk["exp"]), ("صافي الربح", k["net"], pk["net"])]
        html = f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><title>التقرير الشهري {d['month']}</title><style>
          @page{{size:A4;margin:10mm}} body{{font-family:Tahoma,Arial,sans-serif;font-size:13px;font-weight:bold;color:#000}}
          .hd{{display:flex;justify-content:space-between;align-items:center;border-bottom:2px solid #000;padding-bottom:6px}} .hd img{{height:18mm}}
          h1{{font-size:22px;margin:0}} h3{{font-size:16px;margin:14px 0 6px}} table{{width:100%;border-collapse:collapse;page-break-inside:auto}} tr{{page-break-inside:avoid}}
          td,th{{border:1.2px solid #000;padding:4px 6px;text-align:right}} th{{background:#e8eef7}} .n{{text-align:left;direction:ltr}}
          .two{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}</style></head><body>
          <div class="hd"><div><h1>{esc((st['company'] if st else '') or W.DEFAULT_COMPANY)}</h1><div>التقرير الشهري — {d['month']} ({d['from']} ← {d['to']})</div></div><img src="{W.logo_data_uri()}"></div>
          <h3>الأرقام الأساسية (مقارنة بشهر {d['prev']})</h3>{tbl(["البند", "الشهر ده", "الشهر اللي قبله", "التغيير"], [(n, float(a), float(b), chg(a, b)) for n, a, b in key])}
          <div class="two"><div><h3>الأرباح بالتفصيل</h3>{tbl(["البند", "المبلغ"], [(n, float(v)) for n, v in d['metrics']])}</div>
          <div><h3>الخزنة</h3>{tbl(["البند", "المبلغ"], [("أول الشهر", float(d['cash']['open'])), ("دخل", float(d['cash']['in'])), ("خرج", float(d['cash']['out'])), ("آخر الشهر", float(d['cash']['close']))])}
          <h3>آخر الشهر</h3>{tbl(["البند", "المبلغ"], [("على العملاء (لنا)", float(d['end']['recv'])), ("علينا للموردين", float(d['end']['pay'])), ("أرباح اتصرفت للملاك", float(d['end']['owners']))])}</div></div>
          <h3>أكبر العملاء</h3>{tbl(["العميل", "عدد الفواتير", "صافي المبيعات", "اتحصّل منه"], [(r['name'], r['n'], float(r['net']), float(r['collect'])) for r in d['customers']])}
          <h3>أكتر الأصناف ربح</h3>{tbl(["الصنف", "الكمية", "المبيعات", "التكلفة", "الربح"], [(r['name'], float(r['qty']), float(r['rev']), float(r['cost']), float(r['profit'])) for r in d['items']])}
          <div class="two"><div><h3>المناديب</h3>{tbl(["المندوب", "فواتير", "مبيعات", "تحصيل"], [(r['name'], r['n'], float(r['sales']), float(r['collect'])) for r in d['reps']])}</div>
          <div><h3>المصروفات</h3>{tbl(["البند", "المبلغ"], [(n, float(v)) for n, v in d['exp_cats']] or [("مفيش", 0.0)])}</div></div>
          <h3>الأيام</h3>{tbl(["اليوم", "فواتير", "مبيعات", "مرتجع", "مشتريات", "تحصيل", "مصروفات"], [(x['date'], x['n'], float(x['sales']), float(x['ret']), float(x['buys']), float(x['collect']), float(x['exp'])) for x in d['days']])}
          </body></html>"""
        path = os.path.join(W.PRINT_DIR, f"monthly_{d['month']}.html"); os.makedirs(W.PRINT_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh: fh.write(html)
        W.print_page(path)
        return True

    def profit_compare(self, d_from, d_to, mode, cf=None, ct=None):
        self._owner()
        from datetime import date as _d, timedelta as _td
        a = W.check_date(d_from); b = W.check_date(d_to); s_ = _d.fromisoformat(a); e_ = _d.fromisoformat(b)
        if mode == "الفترة السابقة بنفس الطول":
            n = (e_ - s_).days + 1; pe = s_ - _td(days=1); pb = pe - _td(days=n - 1)
        elif mode == "الشهر السابق":
            pe = s_.replace(day=1) - _td(days=1); pb = pe.replace(day=1)
        else:
            try: pb = _d.fromisoformat(W.check_date(cf)); pe = _d.fromisoformat(W.check_date(ct))
            except (ValueError, TypeError): raise UIError("اكتب تواريخ فترة المقارنة")
        if pb > pe: raise UIError("تاريخ بداية المقارنة بعد نهايتها")
        x = W.profit_summary(a, b); y = W.profit_summary(pb.isoformat(), pe.isoformat())
        return {"cur": [a, b], "prev": [pb.isoformat(), pe.isoformat()],
                "rows": [[l, _r2(u), _r2(v)] for (l, u), (_, v) in zip(W.metric_rows(x), W.metric_rows(y))]}

    def reps_report(self, d_from, d_to):
        self._need_login()
        a = W.check_date(d_from); b = W.check_date(d_to)
        if a > b: raise UIError("تاريخ البداية بعد تاريخ النهاية")
        out = []
        with W.db() as c:
            reps = c.execute("SELECT id,name,phone,COALESCE(active,1) active FROM employees WHERE kind='مندوب' OR id IN (SELECT rep_id FROM invoices WHERE rep_id IS NOT NULL) "
                             "OR id IN (SELECT rep_id FROM payments WHERE rep_id IS NOT NULL) ORDER BY name").fetchall()
            for key, name, active in [(r["id"], r["name"], r["active"]) for r in reps] + [(0, W.OFFICE, 1)]:
                mv = W.App.rep_moves(None, c, key, a, b)
                due_all = (lambda ep: ep[0] - ep[1])(W.rep_commission(c, key)) if key else 0.0
                cust_due, _ = W.rep_customers_due(c, key)
                if not active and not mv and abs(due_all) < 0.005 and abs(cust_due) < 0.005: continue   # ساب الشغل ومالوش حركة ولا فلوس: مايظهرش
                out.append({"key": key, "name": name, "n": sum(1 for m in mv if m[2].startswith("0-")), "qty": _r2(sum(m[8] for m in mv)), "tons": _r2(sum(m[10] for m in mv)),
                            "sales": _r2(sum(m[6] for m in mv)), "col": _r2(sum(m[7] for m in mv)), "cust": _r2(cust_due), "comm": _r2(sum(m[9] for m in mv)), "due": _r2(due_all)})
        return out

    def rep_detail(self, key, d_from, d_to):
        self._need_login()
        a = W.check_date(d_from); b = W.check_date(d_to)
        with W.db() as c:
            mv = W.App.rep_moves(None, c, key, a, b)
            custs = []
            for p in c.execute("SELECT id,name,phone FROM parties WHERE COALESCE(rep_id,0)=? AND kind<>'مورد' AND kind<>'أصول' ORDER BY name", (key,)).fetchall():
                bal = W.party_balance(c, p["id"])
                if abs(bal) > 0.005: custs.append({"id": p["id"], "name": p["name"], "phone": p["phone"] or "", "balance": _r2(bal)})
        custs.sort(key=lambda x: -x["balance"])
        return {"rows": [{"date": m[0], "time": W.fmt_time(m[1]), "key": m[2], "what": m[3], "ref": m[4], "party": m[5], "sales": _r2(m[6]), "col": _r2(m[7]),
                          "qty": _r2(m[8]), "comm": _r2(m[9]), "tons": _r2(m[10])} for m in mv], "customers": custs}

    def targets(self, month):
        self._need_login()
        with W.db() as c: rows = W.target_rows(c, month)
        return [{"id": r[0], "name": r[1], "target": _r2(r[2]), "unit": r[3], "done": _r2(r[4]), "bags": _r2(r[5]), "tons": _r2(r[6]),
                 "pct": round(r[4] / r[2] * 100) if r[2] else None} for r in rows]

    def target_items(self):
        """الأصناف وهل بتتحسب في التارجت (الافتراضي: الدقيق)."""
        self._need_login()
        with W.db() as c:
            rows = c.execute("SELECT id,name,unit,in_target FROM items ORDER BY name").fetchall()
        dflt = lambda n: ("دقيق" in (n or "")) or ("خباز" in (n or ""))
        return [{"id": r["id"], "name": r["name"], "unit": r["unit"] or "", "on": bool(r["in_target"]) if r["in_target"] is not None else dflt(r["name"]), "auto": r["in_target"] is None} for r in rows]

    def set_target_items(self, on_ids):
        self._need_login()
        on = {int(i) for i in on_ids or []}
        with W.db() as c:
            for (iid,) in c.execute("SELECT id FROM items").fetchall(): c.execute("UPDATE items SET in_target=? WHERE id=?", (1 if iid in on else 0, iid))
            W.log(c, "أصناف التارجت", f"{len(on)} صنف بيتحسب في تارجت المناديب")
        return True

    def set_target(self, rep_id, month, qty, unit):
        self._need_login()
        try: q = W._f(qty)
        except ValueError: raise UIError("اكتب رقم")
        if q < 0: raise UIError("التارجت مينفعش يكون بالسالب")
        unit = unit if unit in W.COMM_UNITS else "طن"
        with W.db() as c:
            name = c.execute("SELECT name FROM employees WHERE id=?", (rep_id,)).fetchone()[0]
            c.execute("DELETE FROM rep_targets WHERE rep_id=? AND month=?", (rep_id, month))
            c.execute("INSERT INTO rep_targets(rep_id,month,qty,unit) VALUES(?,?,?,?)", (rep_id, month, q, unit))
            W.log(c, "تحديد تارجت مندوب", f"{name}: {W.fmt(q)} {unit} من شهر {month}")
        return True

    def clear_target(self, rep_id, month):
        self._need_login()
        with W.db() as c:
            name = c.execute("SELECT name FROM employees WHERE id=?", (rep_id,)).fetchone()[0]
            c.execute("DELETE FROM rep_targets WHERE rep_id=? AND month>=?", (rep_id, month))
            c.execute("INSERT INTO rep_targets(rep_id,month,qty,unit) VALUES(?,?,?,?)", (rep_id, month, 0, "شيكارة"))
            W.log(c, "إلغاء تارجت", f"{name} من {month}")
        return True

    def activity_log(self, d_from, d_to, act="الكل", q=""):
        self._need_login()
        a = W.check_date(d_from); b = W.check_date(d_to); qn = (q or "").strip().lower()
        with W.db() as c:
            acts = [r[0] for r in c.execute("SELECT DISTINCT action FROM audit_log ORDER BY action")]
            rows = c.execute("SELECT * FROM audit_log WHERE substr(at,1,10) BETWEEN ? AND ? ORDER BY id DESC LIMIT 5000", (a, b)).fetchall()
        return {"actions": acts, "rows": [{"at": r["at"], "user": r["user"], "action": r["action"], "details": r["details"] or ""} for r in rows
                                          if (act in ("الكل", "", None) or r["action"] == act) and (not qn or qn in (r["details"] or "").lower())]}

    def print_daily(self, day):
        self._need_login()
        from types import SimpleNamespace
        day = W.check_date(day)
        W.App.print_daily(_Quiet(dr_rows=W.daily_rows(day), dr_day=day))
        return True

    def print_trust_form(self):
        self._need_login()
        W.App.print_trust_form(_Quiet())
        return True

    # ---------- الصندوق الفرعي ----------
    def subcash(self, d_from, d_to):
        self._need_login()
        a = W.check_date(d_from); b = W.check_date(d_to)
        with W.db() as c: rows = c.execute("SELECT * FROM sub_cash ORDER BY m_date, id").fetchall()
        sg = lambda r: float(r["amount"]) * (1 if r["kind"] == "إيداع" else -1)
        bal = sum(sg(r) for r in rows if r["m_date"] < a); start = bal; out = []; tin = tout = 0.0
        for r in rows:
            if not (a <= r["m_date"] <= b): continue
            amt = float(r["amount"]); inn = r["kind"] == "إيداع"; bal += sg(r); tin += amt if inn else 0; tout += 0 if inn else amt
            out.append({"id": r["id"], "date": r["m_date"], "time": W.fmt_time(r["created_at"]), "what": r["kind"] + (f" — {r['notes']}" if r["notes"] else ""),
                        "in": _r2(amt) if inn else 0, "out": 0 if inn else _r2(amt), "balance": _r2(bal)})
        return {"start": _r2(start), "rows": out, "in": _r2(tin), "out": _r2(tout), "total": _r2(sum(sg(r) for r in rows))}

    def save_subcash(self, kind, d, amount, notes="", force=False):
        self._need_login()
        if kind not in ("إيداع", "سحب"): raise UIError("النوع غلط")
        try: amt = W._f(amount, None); d = W.check_date(d)
        except ValueError: raise UIError("راجع المبلغ والتاريخ")
        if not amt or amt <= 0: raise UIError("المبلغ لازم يكون أكبر من صفر")
        with W.db() as c:
            bal = float(c.execute("SELECT COALESCE(SUM(CASE WHEN kind='إيداع' THEN amount ELSE -amount END),0) FROM sub_cash").fetchone()[0])
            if kind == "سحب" and amt > bal + 0.005 and not force: return {"ok": False, "confirm": f"رصيد الصندوق الفرعي {W.fmt(bal)} بس.\nتكمّل السحب ويبقى الرصيد بالسالب؟"}
            c.execute("INSERT INTO sub_cash(m_date,created_at,kind,amount,notes) VALUES(?,?,?,?,?)", (d, W.now_ts(), kind, amt, (notes or "").strip()))
            W.log(c, "الصندوق الفرعي", f"{kind} {W.fmt(amt)} بتاريخ {d}" + (f" — {notes.strip()}" if (notes or "").strip() else ""))
        return {"ok": True}

    def delete_subcash(self, rid):
        self._need_login()
        with W.db() as c:
            r = c.execute("SELECT * FROM sub_cash WHERE id=?", (rid,)).fetchone()
            c.execute("DELETE FROM sub_cash WHERE id=?", (rid,))
            if r: W.log(c, "حذف حركة صندوق فرعي", f"{r['kind']} {W.fmt(r['amount'])} بتاريخ {r['m_date']}")
        return True

    # ---------- الموظفون ----------
    def _adv(self, c, eid):
        r = c.execute("SELECT COALESCE(SUM(CASE WHEN kind='سلفة' THEN amount ELSE 0 END),0)-COALESCE(SUM(CASE WHEN kind='مرتب' THEN deducted ELSE 0 END),0) FROM expenses WHERE employee_id=?", (eid,)).fetchone()
        return float(r[0])

    def _att_times(self, c):
        r = c.execute("SELECT att_start, att_grace FROM settings WHERE id=1").fetchone()
        return (r["att_start"] or "09:00", r["att_grace"] or "09:30")

    def employees(self, f="الكل"):
        self._need_login(); out = []
        with W.db() as c:
            ds, dg = self._att_times(c)
            for r in c.execute("SELECT * FROM employees ORDER BY name").fetchall():
                left = not (r["active"] if r["active"] is not None else 1)
                if f == W.EMP_LEFT:
                    if not left: continue
                elif left or (f not in ("الكل", "", None) and (r["kind"] or "موظف") != f): continue
                earned, paid = W.rep_commission(c, r["id"])
                out.append({"id": r["id"], "name": r["name"], "kind": r["kind"] or "موظف", "job": r["job"] or "", "phone": r["phone"] or "", "salary": _r2(r["salary"]), "pay_period": pay_period_of(r),
                            "adv": _r2(self._adv(c, r["id"])), "commission": _r2(r["commission"]), "comm_unit": r["comm_unit"] or "شيكارة",
                            "is_rep": bool(r["kind"] == "مندوب" or earned or paid), "due": _r2(earned - paid), "left": left, "left_date": r["left_date"] or "",
                            "loader": W.is_loader(r["kind"], r["job"]), "att_start": W.time12(r["att_start"]) if r["att_start"] else "",
                            "att_grace": W.time12(r["att_grace"]) if r["att_grace"] else "", "t_start": r["att_start"] or ds, "t_grace": r["att_grace"] or dg})
        return {"rows": out, "kinds": list(W.EMP_KINDS), "left_label": W.EMP_LEFT, "default_start": ds, "default_grace": dg}

    def save_employee(self, p):
        self._need_login()
        name = (p.get("name") or "").strip()
        if not name: raise UIError("الاسم مطلوب")
        kind = p.get("kind")
        if kind not in W.EMP_KINDS: raise UIError("اختر النوع: " + " / ".join(W.EMP_KINDS))
        try: sal = W._f(p.get("salary")); comm = W._f(p.get("commission"))
        except ValueError: raise UIError("المرتب والعمولة يجب أن يكونا أرقامًا")
        if comm < 0: raise UIError("العمولة لا تكون بالسالب")
        cunit = p.get("comm_unit") if p.get("comm_unit") in W.COMM_UNITS else "شيكارة"
        t_start, t_grace = W.parse_time(p.get("t_start") or ""), W.parse_time(p.get("t_grace") or "")
        if not t_start or not t_grace: raise UIError("اختار ميعاد الحضور وآخر ميعاد من غير تأخير")
        if W.minutes_of(t_grace) < W.minutes_of(t_start): raise UIError("«آخر ميعاد من غير تأخير» لازم يكون بعد ميعاد الحضور أو زيه")
        job = (p.get("job") or "").strip(); phone = (p.get("phone") or "").strip(); edit = p.get("id")
        period = p.get("pay_period") if p.get("pay_period") in PAY_PERIODS else ("يومي" if kind == "عامل" else "شهري")
        ctxt = f"، عمولة {W.fmt(comm)}/{cunit}" if kind == "مندوب" else ""
        with W.db() as c:
            if edit:
                old = c.execute("SELECT commission, comm_unit FROM employees WHERE id=?", (edit,)).fetchone()
                if abs(float(old["commission"] or 0) - comm) > 1e-9 or (old["comm_unit"] or "شيكارة") != cunit:
                    ctxt += f" (العمولة {W.fmt(old['commission'] or 0)}/{old['comm_unit'] or 'شيكارة'}←{W.fmt(comm)}/{cunit} — على الفواتير الجديدة فقط)"
                c.execute("UPDATE employees SET name=?,kind=?,job=?,phone=?,salary=?,commission=?,comm_unit=?,att_start=?,att_grace=?,pay_period=? WHERE id=?", (name, kind, job, phone, sal, comm, cunit, t_start, t_grace, period, edit))
                W.log(c, "تعديل موظف", f"{name} ({kind}{' - ' + job if job else ''}، مرتب {W.fmt(sal)} — قبض {period}{ctxt})")
            else:
                c.execute("INSERT INTO employees(name,kind,job,phone,salary,commission,comm_unit,att_start,att_grace,pay_period) VALUES(?,?,?,?,?,?,?,?,?,?)", (name, kind, job, phone, sal, comm, cunit, t_start, t_grace, period))
                W.log(c, "إضافة موظف", f"{name} ({kind}{' - ' + job if job else ''}، مرتب {W.fmt(sal)} — قبض {period}{ctxt})")
        return True

    def toggle_employee(self, eid):
        self._need_login()
        with W.db() as c:
            e = c.execute("SELECT * FROM employees WHERE id=?", (eid,)).fetchone()
            active = e["active"] if e["active"] is not None else 1
            if active: c.execute("UPDATE employees SET active=0, left_date=? WHERE id=?", (_today(), eid)); W.log(c, "موظف ساب الشغل", e["name"])
            else: c.execute("UPDATE employees SET active=1, left_date='' WHERE id=?", (eid,)); W.log(c, "موظف رجع الشغل", e["name"])
        return not active

    def delete_employee(self, eid, pw=None):
        self._need_login()
        who = self._del_pw(pw)
        with W.db() as c:
            used = c.execute("SELECT (SELECT COUNT(*) FROM expenses WHERE employee_id=?)+(SELECT COUNT(*) FROM invoices WHERE rep_id=?)+(SELECT COUNT(*) FROM payments WHERE rep_id=?)+(SELECT COUNT(*) FROM attendance WHERE employee_id=?)", (eid, eid, eid, eid)).fetchone()[0]
            name = c.execute("SELECT name FROM employees WHERE id=?", (eid,)).fetchone()["name"]
        if used: raise UIError(f"«{name}» ليه مرتبات أو سلف أو حضور أو فواتير، فلو اتمسح الحسابات القديمة هتبوظ.\nاستخدم «ساب الشغل» بدل الحذف.")
        with W.db() as c: c.execute("DELETE FROM employees WHERE id=?", (eid,)); W.log(c, "حذف موظف", f"{name} (بباسوورد {who})")
        return True

    def salary_suggest(self, eid, d=None):
        """المبلغ المقترح للصرف حسب طريقة القبض: العامل الأسبوعي = اليومية × أيام حضوره في الأسبوع."""
        self._need_login(); d = W.check_date(d or _today())
        from datetime import date as _d, timedelta as _td
        with W.db() as c:
            e = c.execute("SELECT * FROM employees WHERE id=?", (eid,)).fetchone()
            per = pay_period_of(e); sal = float(e["salary"] or 0)
            if per in PERIOD_DAYS:
                start = (_d.fromisoformat(d) - _td(days=PERIOD_DAYS[per] - 1)).isoformat()
                label = f"{per} من {start} إلى {d}"
                if (e["kind"] or "") == "عامل":
                    days = c.execute("SELECT COUNT(*) FROM attendance WHERE employee_id=? AND present=1 AND a_date BETWEEN ? AND ?", (eid, start, d)).fetchone()[0]
                    dtxt = "يوم واحد" if days == 1 else "يومين" if days == 2 else f"{days} أيام" if 3 <= days <= 10 else f"{days} يوم"
                    return {"period": per, "label": label + f" ({dtxt} حضور × {W.fmt(sal)})", "amount": _r2(sal * days), "days": days}
                return {"period": per, "label": label, "amount": _r2(sal)}
            if per == "يومي": return {"period": per, "label": f"يومية {d}", "amount": _r2(sal)}
            return {"period": per, "label": f"شهر {d[:7]}", "amount": _r2(sal)}

    def pay_salary(self, eid, amount, deduct, d, month, label=None):
        self._need_login()
        try: s_ = W._f(amount); dd = W._f(deduct); d = W.check_date(d)
        except ValueError: raise UIError("راجع التاريخ والأرقام")
        if s_ <= 0 or dd < 0 or dd > s_ + 1e-9: raise UIError("الخصم من السلفة يجب أن يكون بين صفر والمرتب")
        msg = W.check_locked(d)
        if msg: raise UIError(msg)
        with W.db() as c:
            e = c.execute("SELECT * FROM employees WHERE id=?", (eid,)).fetchone(); adv = self._adv(c, eid)
            if dd > adv + 1e-9: raise UIError(f"رصيد السلفة الحالي {W.fmt(adv)} بس")
            note = f"مرتب {label}" if label else f"مرتب شهر {month}"
            cat = "يوميات" if (e["kind"] or "") == "عامل" else "مرتبات"
            c.execute("INSERT INTO expenses(exp_date,kind,category,amount,notes,employee_id,deducted,created_at) VALUES(?,?,?,?,?,?,?,?)", (d, "مرتب", cat, s_ - dd, note, eid, dd, W.now_ts()))
            W.log(c, "صرف مرتب", f"{e['name']}: المرتب {W.fmt(s_)} - خصم سلفة {W.fmt(dd)} = مدفوع {W.fmt(s_ - dd)}")
        return True

    def pay_advance(self, eid, amount, d, notes=""):
        self._need_login()
        try: a = W._f(amount); d = W.check_date(d)
        except ValueError: raise UIError("راجع التاريخ والمبلغ")
        if a <= 0: raise UIError("المبلغ يجب أن يكون أكبر من صفر")
        msg = W.check_locked(d)
        if msg: raise UIError(msg)
        with W.db() as c:
            e = c.execute("SELECT name FROM employees WHERE id=?", (eid,)).fetchone()
            c.execute("INSERT INTO expenses(exp_date,kind,category,amount,notes,employee_id,created_at) VALUES(?,?,?,?,?,?,?)", (d, "سلفة", "سلف", a, (notes or "").strip(), eid, W.now_ts()))
            W.log(c, "صرف سلفة", f"{e['name']}: {W.fmt(a)}")
        return True

    def pay_commission(self, eid, amount, d, notes=""):
        self._need_login()
        try: a = W._f(amount); d = W.check_date(d)
        except ValueError: raise UIError("راجع التاريخ والمبلغ")
        if a <= 0: raise UIError("المبلغ يجب أن يكون أكبر من صفر")
        msg = W.check_locked(d)
        if msg: raise UIError(msg)
        with W.db() as c:
            e = c.execute("SELECT name FROM employees WHERE id=?", (eid,)).fetchone(); earned, paid = W.rep_commission(c, eid); due = earned - paid
            if a > due + 0.005: raise UIError(f"الباقي له من العمولة {W.fmt(due)} بس")
            c.execute("INSERT INTO expenses(exp_date,kind,category,amount,notes,employee_id,created_at) VALUES(?,?,?,?,?,?,?)", (d, "عمولة", "عمولات", a, (notes or "").strip(), eid, W.now_ts()))
            W.log(c, "صرف عمولة", f"{e['name']}: {W.fmt(a)} (الباقي بعدها {W.fmt(due - a)})")
        return True

    def workers(self, mode, d):
        """العمال الشغالين لصرف اليوميات (mode=daily) أو الشيالين لصرف/إضافة التشوين (mode=load_pay / load_add)."""
        self._need_login(); d = W.check_date(d)
        with W.db() as c:
            ws = c.execute("SELECT id,name,salary,job,kind,pay_period FROM employees WHERE kind='عامل' AND COALESCE(active,1)=1 ORDER BY name").fetchall()
            if mode == "daily": ws = [r for r in ws if pay_period_of(r) == "يومي"]      # اللي بيقبض أسبوعي/كل أسبوعين بيتصرفله من «صرف مرتب»
            if mode != "daily": ws = [r for r in ws if W.is_loader(r["kind"], r["job"])]
            out = []
            if mode == "daily":
                att = {r[0]: r[1] for r in c.execute("SELECT employee_id, present FROM attendance WHERE a_date=?", (d,)).fetchall()}
                paid = {r[0] for r in c.execute("SELECT employee_id FROM expenses WHERE kind='مرتب' AND category='يوميات' AND exp_date=?", (d,)).fetchall()}
                for r in ws:
                    notes = (["✔ اتصرفله يومية اليوم ده"] if r["id"] in paid else []) + (["غايب"] if att and not att.get(r["id"]) else [])
                    out.append({"id": r["id"], "name": r["name"], "amount": _r2(r["salary"]), "checked": not (r["id"] in paid or (att and not att.get(r["id"]))), "info": " • ".join(notes)})
            elif mode == "load_pay":
                acc = {r[0]: (r[1], float(r[2]), float(r[3])) for r in c.execute("SELECT employee_id, COUNT(*), COALESCE(SUM(amount),0), COALESCE(SUM(tons*1.0/crew),0) FROM loading_logs WHERE l_date=? AND expense_id IS NULL GROUP BY employee_id", (d,)).fetchall()}
                paid = {r[0] for r in c.execute("SELECT DISTINCT employee_id FROM loading_logs WHERE l_date=? AND expense_id IS NOT NULL", (d,)).fetchall()}
                for r in ws:
                    n, a, t = acc.get(r["id"], (0, 0.0, 0.0))
                    out.append({"id": r["id"], "name": r["name"], "amount": _r2(a), "checked": bool(a), "info": f"{n} نقلة — نصيبه {W.fmt(t)} طن" if n else ("✔ اتصرفله" if r["id"] in paid else "مفيش تشوين")})
            else:
                acc = {r[0]: (r[1], r[2]) for r in c.execute("SELECT employee_id, COUNT(*), COALESCE(SUM(amount),0) FROM loading_logs WHERE l_date=? AND expense_id IS NULL GROUP BY employee_id", (d,)).fetchall()}
                for r in ws:
                    n, a = acc.get(r["id"], (0, 0))
                    out.append({"id": r["id"], "name": r["name"], "amount": 0, "checked": True, "info": f"متسجل النهارده: {n} نقلة = {W.fmt(a)}" if n else ""})
        return out

    def pay_workers(self, mode, d, picked):
        """picked = [[id, amount], ...] — صرف يوميات أو صرف تشوين اليوم."""
        self._need_login(); d = W.check_date(d)
        msg = W.check_locked(d)
        if msg: raise UIError(msg)
        picked = [(int(i), W._f(a)) for i, a in picked if W._f(a) > 0]
        if any(a < 0 for _, a in picked): raise UIError("مفيش مبالغ بالسالب")
        if not picked: raise UIError("مفيش حد متعلّم بمبلغ")
        with W.db() as c:
            for eid, a in picked:
                if mode == "daily":
                    c.execute("INSERT INTO expenses(exp_date,kind,category,amount,notes,employee_id,deducted,created_at) VALUES(?,?,?,?,?,?,0,?)", (d, "مرتب", "يوميات", a, f"يومية يوم {d}", eid, W.now_ts()))
                else:
                    logs = c.execute("SELECT id, tons, crew FROM loading_logs WHERE l_date=? AND employee_id=? AND expense_id IS NULL", (d, eid)).fetchall()
                    t = sum(float(x["tons"]) / max(int(x["crew"] or 1), 1) for x in logs)
                    xid = c.execute("INSERT INTO expenses(exp_date,kind,category,amount,notes,employee_id,deducted,created_at) VALUES(?,?,?,?,?,?,0,?)",
                                    (d, "مرتب", "تشوين", a, f"تشوين يوم {d}: {len(logs)} نقلة — نصيبه {W.fmt(t)} طن", eid, W.now_ts())).lastrowid
                    if logs: c.execute(f"UPDATE loading_logs SET expense_id=? WHERE id IN ({','.join('?' * len(logs))})", (xid, *[x["id"] for x in logs]))
            if mode == "daily": W.log(c, "صرف يوميات", f"{d}: {len(picked)} عامل بإجمالي {W.fmt(sum(a for _, a in picked))}")
            else: W.log(c, "صرف تشوين", f"{d}: {len(picked)} شيال بإجمالي {W.fmt(sum(a for _, a in picked))}")
        return len(picked)

    def add_loading(self, d, tons, price, ids, notes=""):
        self._need_login(); d = W.check_date(d)
        msg = W.check_locked(d)
        if msg: raise UIError(msg)
        tons = W._f(tons); price = W._f(price); ids = [int(i) for i in ids]
        if tons <= 0 or price <= 0: raise UIError("اكتب عدد الأطنان (أو الشكاير) وسعر الطن")
        if not ids: raise UIError("علّم الشيالين")
        each = tons * price / len(ids)
        with W.db() as c:
            for eid in ids:
                c.execute("INSERT INTO loading_logs(l_date,employee_id,tons,price,amount,crew,notes,created_at) VALUES(?,?,?,?,?,?,?,?)", (d, eid, tons, price, each, len(ids), (notes or "").strip(), W.now_ts()))
            W.log(c, "إضافة تشوين", f"{d}: {W.fmt(tons)} طن × {W.fmt(price)} = {W.fmt(tons * price)} على {len(ids)} عامل" + (f" — {notes.strip()}" if (notes or "").strip() else ""))
        return True

    def loading_logs(self, d_from, d_to):
        self._need_login(); a = W.check_date(d_from); b = W.check_date(d_to)
        with W.db() as c:
            rows = c.execute("SELECT l.*, e.name FROM loading_logs l JOIN employees e ON e.id=l.employee_id WHERE l.l_date BETWEEN ? AND ? ORDER BY l.l_date DESC, l.id DESC", (a, b)).fetchall()
        return [{"id": r["id"], "date": r["l_date"], "name": r["name"], "tons": _r2(r["tons"]), "price": _r2(r["price"]), "amount": _r2(r["amount"]), "crew": r["crew"],
                 "notes": r["notes"] or "", "paid": bool(r["expense_id"])} for r in rows]

    def update_loading(self, lid, tons, price, amount=None, notes=None):
        """تعديل نقلة تشوين (لسه ماتصرفتش): الأطنان وسعر الطن ونصيب الشيال."""
        self._need_login()
        with W.db() as c: r = c.execute("SELECT * FROM loading_logs WHERE id=?", (lid,)).fetchone()
        if not r: raise UIError("السطر مش موجود")
        if r["expense_id"]: raise UIError("السطر ده اتصرف خلاص. لو عايز تعدّله امسح صرفه من سجل السندات الأول.")
        msg = W.check_locked(r["l_date"])
        if msg: raise UIError(msg)
        try: tons = W._f(tons); price = W._f(price); amt = W._f(amount) if amount not in (None, "") else tons * price / max(1, int(r["crew"] or 1))
        except ValueError: raise UIError("الأرقام مش مظبوطة")
        if tons <= 0 or price <= 0 or amt < 0: raise UIError("اكتب الأطنان وسعر الطن")
        with W.db() as c:
            c.execute("UPDATE loading_logs SET tons=?,price=?,amount=?,notes=? WHERE id=?", (tons, price, amt, (notes if notes is not None else r["notes"]) or "", lid))
            name = (c.execute("SELECT name FROM employees WHERE id=?", (r["employee_id"],)).fetchone() or [""])[0]
            W.log(c, "تعديل تشوين", f"{r['l_date']} — {name}: {W.fmt(r['tons'])} طن × {W.fmt(r['price'])} = {W.fmt(r['amount'])} ← {W.fmt(tons)} طن × {W.fmt(price)} = {W.fmt(amt)}")
        return True

    def delete_loading(self, lid):
        self._need_login()
        with W.db() as c: r = c.execute("SELECT * FROM loading_logs WHERE id=?", (lid,)).fetchone()
        if r["expense_id"]: raise UIError("السطر ده اتصرف خلاص. لو عايز تلغيه امسح صرفه من سجل السندات الأول.")
        with W.db() as c: c.execute("DELETE FROM loading_logs WHERE id=?", (lid,)); W.log(c, "حذف تشوين", f"{r['l_date']}: {W.fmt(r['tons'])} طن — {W.fmt(r['amount'])}")
        return True

    def employee_statement(self, eid):
        self._need_login()
        with W.db() as c:
            e = c.execute("SELECT * FROM employees WHERE id=?", (eid,)).fetchone()
            rows = c.execute("SELECT * FROM expenses WHERE employee_id=? ORDER BY exp_date,id", (eid,)).fetchall()
            earned, cpaid = W.rep_commission(c, eid)
        bal = 0.0; out = []
        for r in rows:
            amt = float(r["amount"]); ded = float(r["deducted"] or 0)
            if r["kind"] == "عمولة": out.append({"date": r["exp_date"], "time": W.fmt_time(r["created_at"]), "what": "صرف عمولة", "gross": _r2(amt), "ded": 0, "paid": _r2(amt), "adv": _r2(bal), "notes": r["notes"] or ""})
            elif r["kind"] == "سلفة": bal += amt; out.append({"date": r["exp_date"], "time": W.fmt_time(r["created_at"]), "what": "سلفة", "gross": _r2(amt), "ded": 0, "paid": _r2(amt), "adv": _r2(bal), "notes": r["notes"] or ""})
            else:
                bal -= ded
                out.append({"date": r["exp_date"], "time": W.fmt_time(r["created_at"]), "what": ("مرتب أسبوعين" if "كل أسبوعين" in (r["notes"] or "") else "أسبوعية" if "أسبوعي" in (r["notes"] or "") else {"يوميات": "يومية", "تشوين": "تشوين"}.get(r["category"], "مرتب")), "gross": _r2(amt + ded), "ded": _r2(ded), "paid": _r2(amt), "adv": _r2(bal), "notes": r["notes"] or ""})
        for o, r in zip(out, rows): o["key"] = f"e-{r['id']}"
        return {"name": e["name"], "kind": e["kind"] or "موظف", "salary": _r2(e["salary"]), "rows": out, "adv": _r2(bal), "earned": _r2(earned), "cpaid": _r2(cpaid)}

    # ---------- الحضور ----------
    def attendance_day(self, d):
        self._need_login(); d = W.check_date(d)
        with W.db() as c:
            ds, dg = self._att_times(c)
            emps = c.execute("SELECT id,name,kind,job,att_start,att_grace FROM employees WHERE COALESCE(active,1)=1 OR id IN (SELECT employee_id FROM attendance WHERE a_date=?) ORDER BY name", (d,)).fetchall()
            recs = {r["employee_id"]: r for r in c.execute("SELECT * FROM attendance WHERE a_date=?", (d,))}
        return {"saved": bool(recs), "rows": [{"id": e["id"], "name": e["name"], "kind": e["kind"] or "", "job": e["job"] or "", "start": e["att_start"] or ds, "grace": e["att_grace"] or dg,
                                               "present": bool(recs[e["id"]]["present"]) if e["id"] in recs else False,
                                               "check_in": (recs[e["id"]]["check_in"] or "") if e["id"] in recs else "", "notes": (recs[e["id"]]["notes"] or "") if e["id"] in recs else ""} for e in emps]}

    def save_attendance(self, d, rows):
        self._need_login()
        try: dd = W.check_date(d)
        except ValueError: raise UIError("التاريخ غير صحيح")
        if dd > _today(): raise UIError("مينفعش تسجّل حضور ليوم لسه مجاش")
        data = []
        with W.db() as c:
            ds, dg = self._att_times(c)
            graces = {r["id"]: r["att_grace"] or dg for r in c.execute("SELECT id, att_grace FROM employees").fetchall()}
        for r in rows:
            t = (W.parse_time(r.get("check_in") or "") if r.get("present") else "") or ""
            if r.get("present") and r.get("check_in") and not t: raise UIError(f"ساعة وصول «{r.get('name')}» مش مظبوطة")
            late = max(0, W.minutes_of(t) - W.minutes_of(graces.get(int(r["id"]), dg))) if t else 0
            data.append((int(r["id"]), dd, 1 if r.get("present") else 0, t, late, (r.get("notes") or "").strip(), W.now_ts()))
        with W.db() as c:
            c.execute("DELETE FROM attendance WHERE a_date=?", (dd,))
            for x in data: c.execute("INSERT INTO attendance(employee_id,a_date,present,check_in,late_min,notes,created_at) VALUES(?,?,?,?,?,?,?)", x)
            pres = sum(x[2] for x in data); late = sum(1 for x in data if x[4])
            W.log(c, "تسجيل حضور", f"{dd}: حاضر {pres} / غياب {len(data) - pres} / متأخر {late}")
        return {"present": pres, "absent": len(data) - pres, "late": late}

    def attendance_log(self, d_from, d_to, eid=None):
        self._need_login()
        cond, args = "a.a_date BETWEEN ? AND ?", [W.check_date(d_from), W.check_date(d_to)]
        if eid: cond += " AND a.employee_id=?"; args.append(int(eid))
        with W.db() as c:
            rows = c.execute(f"SELECT a.*, m.name FROM attendance a JOIN employees m ON m.id=a.employee_id WHERE {cond} ORDER BY a.a_date DESC, m.name", args).fetchall()
            summ = c.execute(f"""SELECT m.id, m.name, SUM(a.present) pres, SUM(1-a.present) abs, SUM(CASE WHEN a.present=1 AND a.late_min>0 THEN 1 ELSE 0 END) late_n,
                                 SUM(CASE WHEN a.present=1 THEN a.late_min ELSE 0 END) late_t FROM attendance a JOIN employees m ON m.id=a.employee_id
                                 WHERE {cond} GROUP BY m.id ORDER BY m.name""", args).fetchall()
            emps = [{"id": r["id"], "name": r["name"]} for r in c.execute("SELECT id,name FROM employees ORDER BY name").fetchall()]
        from datetime import datetime as _dt
        det = []
        for r in rows:
            dd = _dt.strptime(r["a_date"], "%Y-%m-%d").date()
            state = "غياب" if not r["present"] else ("متأخر" if r["late_min"] else "حاضر")
            det.append({"id": r["id"], "date": r["a_date"], "day": "ال" + W.AR_DAYS[(dd.weekday() - 5) % 7], "name": r["name"], "state": state,
                        "in": W.time12(r["check_in"]) if r["check_in"] else "—", "late": W.fmt_minutes(r["late_min"]) if r["present"] and r["late_min"] else "—", "notes": r["notes"] or ""})
        return {"emps": emps, "summary": [{"id": r["id"], "name": r["name"], "pres": r["pres"] or 0, "abs": r["abs"] or 0, "late_n": r["late_n"] or 0,
                                           "late_t": W.fmt_minutes(r["late_t"]) if r["late_t"] else "—", "late_min": r["late_t"] or 0} for r in summ], "rows": det}

    def delete_attendance(self, rid):
        self._need_login()
        with W.db() as c:
            r = c.execute("SELECT a.*, m.name FROM attendance a JOIN employees m ON m.id=a.employee_id WHERE a.id=?", (rid,)).fetchone()
            c.execute("DELETE FROM attendance WHERE id=?", (rid,)); W.log(c, "حذف حضور", f"{r['a_date']}: {r['name']}")
        return True

    # ---------- طلبات تليجرام ----------
    # ---------- طلبات المناديب من الموقع (فواتير / تحصيل / حضور) ----------
    def req_list(self, which, status="pending"):
        """which = inv | pay | att. المندوب بيشوف طلباته بس."""
        self._need_login()
        mine = W.CURRENT_USER.get("emp_id") if W.CURRENT_USER.get("role") == W.ROLE_REP else None
        st = "" if status in ("all", "", None) else status
        if which in ("pay", "att"):
            rows = self.requests("att" if which == "att" else "rep", st or "all")
            return [r for r in rows if mine is None or r.get("rep_id") == mine]
        cond, args = [], []
        if st: cond.append("r.status=?"); args.append(st)
        if mine is not None: cond.append("r.rep_id=?"); args.append(mine)
        with W.db() as c:
            rows = c.execute("SELECT r.*, p.name pname, e.name rname FROM inv_requests r LEFT JOIN parties p ON p.id=r.party_id LEFT JOIN employees e ON e.id=r.rep_id"
                             + (" WHERE " + " AND ".join(cond) if cond else "") + " ORDER BY r.id DESC LIMIT 500", args).fetchall()
        out = []
        for r in rows:
            pl = json.loads(r["payload"] or "{}")
            out.append({"id": r["id"], "created_at": r["created_at"], "rname": r["rname"] or "", "pname": r["pname"] or "", "kind": r["kind"], "net": _r2(r["net"]),
                        "lines": len(pl.get("lines") or []), "status": r["status"], "status_text": W.REQ_STATUS.get(r["status"], r["status"]) + (f" — {r['decided_by']}" if r["status"] != "pending" and r["decided_by"] else ""),
                        "invoice_id": r["invoice_id"], "reason": r["reason"] or "", "by_user": r["by_user"] or ""})
        return out

    def inv_request_get(self, rid):
        """بيانات طلب فاتورة عشان المحاسب يراجعها في شاشة الفاتورة ويحفظها."""
        self._need_login()
        with W.db() as c: r = c.execute("SELECT * FROM inv_requests WHERE id=?", (rid,)).fetchone()
        if not r: raise UIError("الطلب مش موجود")
        if r["status"] != "pending": raise UIError(f"الطلب ده {W.REQ_STATUS.get(r['status'], r['status'])} بالفعل")
        pl = json.loads(r["payload"]); pl["request_id"] = r["id"]
        return pl

    def req_decide(self, which, rid, ok, reason=""):
        self._need_login()
        if which == "inv":
            if ok: raise UIError("الموافقة على الفاتورة بتتعمل من «مراجعة وحفظ»")
            with W.db() as c:
                r = c.execute("SELECT status FROM inv_requests WHERE id=?", (rid,)).fetchone()
                if not r or r[0] != "pending": raise UIError("الطلب ده مش مستني موافقة")
                c.execute("UPDATE inv_requests SET status='rejected', decided_at=?, decided_by=?, reason=? WHERE id=?", (W.now_ts(), W.CURRENT_USER.get("username", ""), (reason or "").strip(), rid))
                W.log(c, "رفض طلب فاتورة", f"طلب رقم {rid}" + (f" — {reason.strip()}" if (reason or "").strip() else ""))
            return {"done": True, "text": "❌ اترفض"}
        res = self.decide_request("att" if which == "att" else "rep", rid, ok)
        if which == "pay" and ok and res.get("done"):
            with W.db() as c:
                r = c.execute("SELECT r.payment_id, COALESCE(r.method,'') m, e.name FROM rep_requests r LEFT JOIN employees e ON e.id=r.rep_id WHERE r.id=?", (rid,)).fetchone()
                if r and r[0]: c.execute("UPDATE payments SET holder=?, method=? WHERE id=?", (r[2] or "", r[1] or "كاش", r[0]))
        return res

    def req_counts(self):
        """عدد طلبات المناديب المستنية (للزرار اللي فوق عند المحاسب والمالك)."""
        self._need_login()
        if W.CURRENT_USER.get("role") == W.ROLE_REP: return {"inv": 0, "pay": 0, "att": 0, "total": 0}
        with W.db() as c:
            n = {k: c.execute(f"SELECT COUNT(*) FROM {t} WHERE status='pending'").fetchone()[0] for k, t in (("inv", "inv_requests"), ("pay", "rep_requests"), ("att", "att_requests"))}
        n["total"] = sum(n.values()); return n

    def rep_checkin(self, lat=None, lon=None, acc=None):
        """زرار المندوب: تسجيل حضور بموقعه. جوه المخزن (والتسجيل التلقائي شغال) ← يتسجل على طول، غير كده ← طلب للمحاسب."""
        self._need_login()
        if W.CURRENT_USER.get("role") != W.ROLE_REP: raise UIError("الزرار ده للمناديب بس")
        emp = W.CURRENT_USER.get("emp_id"); d = _today()
        from datetime import datetime as _dt
        t = _dt.now().strftime("%H:%M")
        try: lat, lon = (float(lat), float(lon)) if lat is not None and lon is not None else (None, None)
        except Exception: lat = lon = None
        try: acc = float(acc) if acc is not None else None
        except Exception: acc = None
        with W.db() as c:
            if c.execute("SELECT 1 FROM attendance WHERE employee_id=? AND a_date=? AND present=1", (emp, d)).fetchone(): raise UIError("حضورك النهارده متسجل بالفعل ✔")
            if c.execute("SELECT 1 FROM att_requests WHERE rep_id=? AND a_date=? AND status='pending'", (emp, d)).fetchone(): raise UIError("طلب حضورك النهارده مبعوت بالفعل ومستني موافقة")
            pl = W.att_place(c)
            dist = W.geo_dist(lat, lon, pl["lat"], pl["lon"]) if lat is not None and pl.get("lat") is not None else None
            inside = dist is not None and dist <= pl["radius"]
            dtxt = "" if dist is None else (f"{dist / 1000:.1f} كم" if dist >= 1000 else f"{dist:.0f} متر")
            if inside and pl["auto"]:
                late = W.record_attendance(c, emp, d, t, f"📍 من الموقع (جوه المخزن — {dtxt})")
                W.log(c, "حضور مندوب بالموقع", f"{d} الساعة {W.time12(t)} — جوه المخزن ({dtxt})" + (f" متأخر {late} د" if late else ""))
                return {"time": W.time12(t), "done": True, "late": late, "dist": dtxt}
            reason = ("جوه المخزن" if inside else f"بره المخزن ({dtxt})") if dist is not None else ("من غير موقع" if lat is None else "مكان المخزن مش متحدد")
            if acc and dist is not None and not inside: reason += f" — دقة الموقع ±{acc:.0f} م"
            c.execute("INSERT INTO att_requests(created_at,rep_id,a_date,check_in,lat,lon,dist,live,reason,status,chat_id) VALUES(?,?,?,?,?,?,?,0,?,'pending','')",
                      (W.now_ts(), emp, d, t, lat, lon, dist, reason))
            W.log(c, "طلب حضور من مندوب", f"{d} الساعة {W.time12(t)} — {reason} (مستني موافقة)")
        return {"time": W.time12(t), "done": False, "reason": reason, "dist": dtxt}

    def requests(self, which, status="pending"):
        self._need_login()
        cond = "WHERE r.status=?" if status not in ("all", "", None) else ""; args = (status,) if cond else ()
        with W.db() as c:
            if which == "att":
                rows = c.execute(f"SELECT r.*, e.name rname FROM att_requests r LEFT JOIN employees e ON e.id=r.rep_id {cond} ORDER BY r.id DESC LIMIT 500", args).fetchall()
            else:
                rows = c.execute(f"SELECT r.*, p.name pname, e.name rname FROM rep_requests r LEFT JOIN parties p ON p.id=r.party_id LEFT JOIN employees e ON e.id=r.rep_id {cond} ORDER BY r.id DESC LIMIT 500", args).fetchall()
        out = []
        for r in rows:
            d = {k: r[k] for k in r.keys()}
            d["status_text"] = W.REQ_STATUS.get(r["status"], r["status"]) + (f" — {r['decided_by']}" if r["status"] != "pending" and r["decided_by"] else "")
            out.append({k: (v if isinstance(v, (int, float, str, type(None))) else str(v)) for k, v in d.items()})
        return out

    def decide_request(self, which, rid, ok):
        self._need_login()
        fn = W.decide_att_request if which == "att" else W.decide_rep_request
        done, text = fn(int(rid), bool(ok), W.CURRENT_USER.get("username", ""))
        return {"done": done, "text": text}

    # ---------- العربيات ----------
    def vehicles(self, d_from, d_to):
        self._need_login(); a = W.check_date(d_from); b = W.check_date(d_to); out = []
        with W.db() as c:
            for v in c.execute("SELECT * FROM vehicles ORDER BY COALESCE(active,1) DESC, name").fetchall():
                sm = W.vehicle_summary(c, v["id"], a, b)
                out.append({"id": v["id"], "name": v["name"], "plate": v["plate"] or "", "driver": v["driver"] or "", "notes": v["notes"] or "", "active": bool(v["active"] if v["active"] is not None else 1),
                            "km": _r2(sm["km"]), "liters": _r2(sm["liters"]), "fuel": _r2(sm["fuel"]), "total": _r2(sm["total"]), "km_per_l": _r2(sm["km_per_l"]) if sm["km_per_l"] else None,
                            "cost_km": _r2(sm["cost_km"]) if sm["cost_km"] else None, "last_odo": _r2(sm["last_odo"]) if sm["last_odo"] is not None else None,
                            "logs": [{"id": l["id"], "date": l["v_date"], "kind": l["kind"], "odo": _r2(l["odometer"]) if l["odometer"] is not None else None, "liters": _r2(l["liters"]),
                                      "amount": _r2(l["amount"]), "notes": l["notes"] or ""} for l in reversed(sm["logs"])]})
        return {"kinds": list(W.VEHICLE_KINDS), "rows": out}

    def save_vehicle(self, p):
        self._need_login()
        name = (p.get("name") or "").strip()
        if not name: raise UIError("اكتب اسم العربية")
        vals = (name, (p.get("plate") or "").strip(), (p.get("driver") or "").strip(), (p.get("notes") or "").strip(), 1 if p.get("active", True) else 0)
        with W.db() as c:
            if p.get("id"): c.execute("UPDATE vehicles SET name=?,plate=?,driver=?,notes=?,active=? WHERE id=?", vals + (p["id"],)); W.log(c, "تعديل عربية", name)
            else: c.execute("INSERT INTO vehicles(name,plate,driver,notes,active,created_at) VALUES(?,?,?,?,?,?)", vals + (W.now_ts(),)); W.log(c, "إضافة عربية", name)
        return True

    def save_vehicle_log(self, p, force=False):
        self._need_login()
        vid = p.get("vehicle_id")
        if not vid: raise UIError("اختار العربية")
        try: d = W.check_date(p.get("date") or "")
        except ValueError: raise UIError("صيغة التاريخ غلط")
        if d > _today(): raise UIError("مينفعش تسجّل ليوم لسه مجاش")
        kind = p.get("kind")
        if kind not in W.VEHICLE_KINDS: raise UIError("اختار النوع")
        try:
            odo = W._f(p.get("odo"), None); liters = W._f(p.get("liters")); amount = W._f(p.get("amount"))
        except ValueError: raise UIError("العداد واللترات والمبلغ لازم يكونوا أرقام")
        if kind == "قراءة عداد" and odo is None: raise UIError("اكتب قراءة العداد")
        if kind != "قراءة عداد" and amount <= 0: raise UIError("اكتب المبلغ")
        if (odo is not None and odo < 0) or liters < 0 or amount < 0: raise UIError("مفيش أرقام بالسالب")
        if amount > 0:
            msg = W.check_locked(d)
            if msg: raise UIError(msg)
        notes = (p.get("notes") or "").strip()
        with W.db() as c:
            if odo is not None and not force:
                before = c.execute("SELECT MAX(odometer) FROM vehicle_logs WHERE vehicle_id=? AND v_date<=? AND odometer IS NOT NULL", (vid, d)).fetchone()[0]
                after = c.execute("SELECT MIN(odometer) FROM vehicle_logs WHERE vehicle_id=? AND v_date>? AND odometer IS NOT NULL", (vid, d)).fetchone()[0]
                if (before is not None and odo < float(before)) or (after is not None and odo > float(after)):
                    return {"ok": False, "confirm": f"القراءة دي ({W.fmt(odo)}) مش ماشية مع القراءات التانية" + (f" (أعلى قراءة لحد اليوم ده: {W.fmt(before)})" if before is not None else "")
                            + (f" (أقل قراءة بعده: {W.fmt(after)})" if after is not None else "") + ".\nتسجلها برضه؟"}
            vname = c.execute("SELECT name FROM vehicles WHERE id=?", (vid,)).fetchone()[0]
            exp_id = None
            if amount > 0:
                exp_id = c.execute("INSERT INTO expenses(exp_date,kind,category,amount,notes,created_at) VALUES(?,?,?,?,?,?)",
                                   (d, "مصروف", f"عربيات — {kind}", amount, f"{vname}" + (f" — عداد {W.fmt(odo)}" if odo is not None else "") + (f" — {W.fmt(liters)} لتر" if liters else "") + (f" — {notes}" if notes else ""), W.now_ts())).lastrowid
                c.execute("INSERT OR IGNORE INTO expense_cats(name) VALUES(?)", (f"عربيات — {kind}",))
            c.execute("INSERT INTO vehicle_logs(vehicle_id,v_date,kind,odometer,liters,amount,notes,expense_id,created_at) VALUES(?,?,?,?,?,?,?,?,?)", (vid, d, kind, odo, liters, amount, notes, exp_id, W.now_ts()))
            W.log(c, "العربيات", f"{vname}: {kind}" + (f" — عداد {W.fmt(odo)}" if odo is not None else "") + (f" — {W.fmt(amount)}" if amount else "") + f" ({d})")
        return {"ok": True}

    def delete_vehicle_log(self, lid):
        self._need_login()
        with W.db() as c: l = c.execute("SELECT * FROM vehicle_logs WHERE id=?", (lid,)).fetchone()
        if l["expense_id"]:
            msg = W.check_locked(l["v_date"])
            if msg: raise UIError(msg)
        with W.db() as c:
            if l["expense_id"]: c.execute("DELETE FROM expenses WHERE id=?", (l["expense_id"],))
            c.execute("DELETE FROM vehicle_logs WHERE id=?", (lid,))
            W.log(c, "حذف حركة عربية", f"{l['kind']} — {l['v_date']}" + (f" — {W.fmt(l['amount'])}" if l["amount"] else ""))
        return True

    def delete_vehicle(self, vid):
        self._need_login()
        with W.db() as c:
            v = c.execute("SELECT * FROM vehicles WHERE id=?", (vid,)).fetchone()
            logs = c.execute("SELECT v_date, amount, expense_id FROM vehicle_logs WHERE vehicle_id=?", (vid,)).fetchall()
        exps = [l for l in logs if l["expense_id"]]
        if exps:
            msg = W.check_locked(*[l["v_date"] for l in exps])
            if msg: raise UIError(msg)
        tot = sum(float(l["amount"] or 0) for l in exps)
        with W.db() as c:
            for l in exps: c.execute("DELETE FROM expenses WHERE id=?", (l["expense_id"],))
            c.execute("DELETE FROM vehicle_logs WHERE vehicle_id=?", (vid,)); c.execute("DELETE FROM vehicles WHERE id=?", (vid,))
            W.log(c, "حذف عربية", f"{v['name']}" + (f" ({v['plate']})" if v["plate"] else "") + f" — {len(logs)} سطر" + (f" ومصروفات {W.fmt(tot)}" if exps else ""))
        return True

    # ---------- الإعدادات ----------
    def settings_get(self):
        self._need_login()
        with W.db() as c:
            st = c.execute("SELECT * FROM settings WHERE id=1").fetchone()
            g = lambda k: (st[k] if k in st.keys() else "") or ""
            return {"company": g("company") or W.DEFAULT_COMPANY, "tagline": g("tagline"), "english": g("english"), "address": g("address"), "phone": g("phone"), "taxno": g("taxno"), "owners_list": g("owners_list"),
                    "trust_from": g("trust_from"), "trust_to": g("trust_to"), "trust_to_addr": g("trust_to_addr"),
                    "lock_until": g("lock_until"), "lock_auto": bool(st["lock_auto"]) if "lock_auto" in st.keys() else False, "lock_now": W.lock_date(c),
                    "backup_dir": W.backup_dir(), "server": W.server_label(), "version": W.version_text(), "owner": W.is_owner(), "brand_locked": W.BRAND_LOCKED,
                    "cash_opening": _r2(float((st["cash_opening"] if "cash_opening" in st.keys() else 0) or 0))}

    def settings_save(self, v):
        self._need_login()
        with W.db() as c:
            c.execute("UPDATE settings SET english=?,address=?,phone=?,taxno=? WHERE id=1",
                      ((v.get("english") or "").strip(), (v.get("address") or "").strip(), (v.get("phone") or "").strip(), (v.get("taxno") or "").strip()))
            # اسم الشركة وتحت الاسم مقفولين جوه النسخة (W.BRAND_*) — مش بيتغيروا من هنا
            if W.is_owner() and v.get("owners_list") is not None:
                c.execute("UPDATE settings SET owners_list=? WHERE id=1", ("،".join(x.strip() for x in str(v["owners_list"]).replace(",", "،").split("،") if x.strip()),))
            W.log(c, "تعديل الإعدادات", "بيانات الشركة")
        return True

    def set_logo(self, data_url=None):
        """الشعار مقفول جوه النسخة — بيتغيّر بنسخة جديدة من المطور بس."""
        self._need_login()
        if W.BRAND_LOCKED: raise UIError("اسم الشركة والشعار مقفولين في النسخة دي — بيتغيروا بنسخة جديدة من المطور")
        if not W.is_owner(): raise UIError("الشعار بيتغيّر من المالك بس")
        b64 = ""
        if data_url:
            import base64 as _b
            try: head, b64 = data_url.split(",", 1); raw = _b.b64decode(b64)
            except Exception: raise UIError("الصورة مش مظبوطة")
            if not (raw[:8] == b"\x89PNG\r\n\x1a\n" or raw[:3] == b"\xff\xd8\xff"): raise UIError("الشعار لازم يكون صورة PNG أو JPG")
            if len(raw) > 1_500_000: raise UIError("الصورة كبيرة — صغّرها لأقل من 1.5 ميجا")
        with W.db() as c:
            c.execute("UPDATE settings SET logo_b64=? WHERE id=1", (b64,)); W.log(c, "تغيير الشعار", "شعار جديد" if b64 else "رجوع للشعار العام")
        return W.logo_data_uri()

    def trust_save(self, v):
        self._need_login()
        v = {k: (v.get(k) or "").strip() for k in ("trust_from", "trust_to", "trust_to_addr")}
        with W.db() as c:
            c.execute("UPDATE settings SET trust_from=?,trust_to=?,trust_to_addr=? WHERE id=1", (v["trust_from"], v["trust_to"], v["trust_to_addr"]))
            W.log(c, "تعديل بيانات إيصال الأمانة", f"من: {v['trust_from']} — إلى: {v['trust_to']} — {v['trust_to_addr']}")
        return True

    def lock_save(self, until, auto):
        self._owner()
        d = W.check_date(until) if until else ""
        with W.db() as c:
            c.execute("UPDATE settings SET lock_until=? WHERE id=1", (d,)); W.log(c, "إقفال الشهور", ("مقفول لحد " + d) if d else "اتفتح الإقفال اليدوي")
            c.execute("UPDATE settings SET lock_auto=? WHERE id=1", (1 if auto else 0,)); W.log(c, "إقفال الشهور", "أوتوماتيك أول كل شهر: " + ("شغال" if auto else "مقفول"))
        return W.lock_date()

    def backup_now(self):
        self._need_login()
        path, warn = W.backup_copy("manual")
        if not path: raise UIError(warn or "النسخة الاحتياطية فشلت")
        with W.db() as c: W.log(c, "نسخة احتياطية يدوية", path + (f" — {warn}" if warn else ""))
        return {"path": path, "warn": warn or ""}

    def open_backup_folder(self):
        self._need_login()
        d = W.backup_dir(); os.makedirs(d, exist_ok=True); W.open_file(d)
        return True

    # ---------- المستخدمين ----------
    def users(self):
        self._owner()
        with W.db() as c:
            emps = {r[0]: r[1] for r in c.execute("SELECT id,name FROM employees").fetchall()}
            return [{"id": r["id"], "username": r["username"], "role": r["role"], "active": bool(r["active"]), "created": r["created_at"] or "",
                     "screens": user_screens(r), "emp_id": r["emp_id"], "emp": emps.get(r["emp_id"], "")}
                    for r in c.execute("SELECT * FROM users ORDER BY role DESC,username").fetchall()]

    def access_setup(self):
        """للشاشة بتاعة الصلاحيات: كل الشاشات والمناديب."""
        self._owner()
        with W.db() as c: reps = [{"id": r[0], "name": r[1]} for r in c.execute("SELECT id,name FROM employees WHERE kind='مندوب' AND COALESCE(active,1)=1 ORDER BY name").fetchall()]
        return {"screens": ALL_SCREENS, "owner_only": sorted(OWNER_ONLY_SCREENS), "defaults": DEFAULT_SCREENS, "reps": reps, "roles": [W.ROLE_OWNER, W.ROLE_ACC, W.ROLE_REP]}

    def set_user_access(self, uid, role, screens, emp_id=None):
        self._owner()
        if role not in (W.ROLE_OWNER, W.ROLE_ACC, W.ROLE_REP): raise UIError("اختر الصلاحية")
        screens = [k for k in (screens or []) if k in ALL_SCREENS and k not in OWNER_ONLY_SCREENS]
        if role == W.ROLE_REP and not emp_id: raise UIError("اختار المندوب اللي اليوزر ده بتاعه")
        with W.db() as c:
            u = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
            if not u: raise UIError("اليوزر مش موجود")
            if u["role"] == W.ROLE_OWNER and role != W.ROLE_OWNER and not self._active_owners(c, u["id"]): raise UIError("لازم يفضل مالك واحد شغال على الأقل")
            c.execute("UPDATE users SET role=?, screens=?, emp_id=? WHERE id=?", (role, json.dumps(screens, ensure_ascii=False), int(emp_id) if role == W.ROLE_REP else None, uid))
            W.log(c, "صلاحيات مستخدم", f"{u['username']}: {role} — {len(screens)} شاشة")
        return True

    def _active_owners(self, c, exclude=None):
        return c.execute("SELECT COUNT(*) FROM users WHERE role=? AND active=1 AND id<>?", (W.ROLE_OWNER, exclude or -1)).fetchone()[0]

    def add_user(self, name, p1, p2, role, emp_id=None):
        self._owner()
        name = (name or "").strip()
        if not name: raise UIError("اكتب اسم المستخدم")
        if len(p1 or "") < 4: raise UIError("كلمة السر لازم تكون 4 حروف/أرقام على الأقل")
        if p1 != p2: raise UIError("كلمتين السر مش متطابقتين")
        if role not in (W.ROLE_OWNER, W.ROLE_ACC, W.ROLE_REP): raise UIError("اختر الصلاحية")
        if role == W.ROLE_REP and not emp_id: raise UIError("اختار المندوب اللي اليوزر ده بتاعه")
        h_, salt = W.hash_pw(p1)
        try:
            with W.db() as c:
                c.execute("INSERT INTO users(username,pw_hash,salt,role,active,created_at,emp_id) VALUES(?,?,?,?,1,?,?)", (name, h_, salt, role, W.now_ts(), int(emp_id) if role == W.ROLE_REP else None))
                W.log(c, "إضافة مستخدم", f"{name} ({role})")
        except W.DBIntegrityError: raise UIError("اسم المستخدم موجود بالفعل")
        return True

    def change_password(self, uid, p1, p2):
        self._need_login()
        if not W.is_owner() and int(uid) != W.CURRENT_USER.get("id"): raise UIError("تقدر تغيّر كلمة السر بتاعتك بس")
        if len(p1 or "") < 4: raise UIError("كلمة السر لازم تكون 4 حروف/أرقام على الأقل")
        if p1 != p2: raise UIError("كلمتين السر مش متطابقتين")
        h_, salt = W.hash_pw(p1)
        with W.db() as c:
            u = c.execute("SELECT username FROM users WHERE id=?", (uid,)).fetchone()
            c.execute("UPDATE users SET pw_hash=?,salt=? WHERE id=?", (h_, salt, uid)); W.log(c, "تغيير كلمة سر", u["username"])
        return True

    def toggle_user(self, uid):
        self._owner()
        with W.db() as c:
            u = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
            if u["active"] and u["role"] == W.ROLE_OWNER and not self._active_owners(c, u["id"]): raise UIError("لازم يفضل مالك واحد شغال على الأقل")
            if u["id"] == W.CURRENT_USER.get("id") and u["active"]: raise UIError("مينفعش توقف حسابك وانت داخل بيه")
            c.execute("UPDATE users SET active=? WHERE id=?", (0 if u["active"] else 1, u["id"]))
            W.log(c, "إيقاف مستخدم" if u["active"] else "تفعيل مستخدم", u["username"])
        return True

    def delete_user(self, uid):
        self._owner()
        with W.db() as c:
            u = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
            if u["role"] == W.ROLE_OWNER and not self._active_owners(c, u["id"]): raise UIError("لازم يفضل مالك واحد شغال على الأقل")
            if u["id"] == W.CURRENT_USER.get("id"): raise UIError("مينفعش تحذف حسابك وانت داخل بيه")
            c.execute("DELETE FROM users WHERE id=?", (u["id"],)); W.log(c, "حذف مستخدم", u["username"])
        return True

    # ---------- اختيار ملف / فولدر (نافذة ويندوز) ----------
    def pick_file(self, kind):
        """kind = excel | json | folder. بيرجع المسار أو None."""
        self._need_login()
        try:
            import webview
            win = webview.windows[0]
        except Exception:
            raise UIError("اختيار الملفات شغال من نافذة البرنامج بس")
        if kind == "folder":
            r = win.create_file_dialog(webview.FOLDER_DIALOG)
        else:
            types = ("Excel (*.xlsx)", "All files (*.*)") if kind == "excel" else ("JSON (*.json)", "All files (*.*)")
            r = win.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False, file_types=types)
        if not r: return None
        return r[0] if isinstance(r, (list, tuple)) else r

    # ---------- الاستيراد من Excel ----------
    def import_start(self, what, path):
        self._owner()
        if what not in ("items", "parties"): raise UIError("نوع غلط")
        try: _, hr, _, found = W.import_found_date(path, what)
        except W.ImportProblem as e: raise UIError(str(e))
        return {"found": found or ""}

    def import_preview(self, what, path, asof):
        self._owner()
        asof = (asof or "").strip()
        if asof:
            try: asof = W.check_date(asof.replace("/", "-"))
            except ValueError: raise UIError("التاريخ مش مظبوط — اكتبه كده: 2026-10-31")
        try: ctx = W.import_plan(what, path, asof)
        except W.ImportProblem as e: raise UIError(str(e))
        self._import_ctx = ctx
        return {"msg": ctx["msg"]}

    def import_run(self, replace, force_no_backup=False):
        self._owner()
        ctx = getattr(self, "_import_ctx", None)
        if not ctx: raise UIError("اعرض ملخص الاستيراد الأول")
        try: done = W.import_apply(ctx, bool(replace), force_no_backup=bool(force_no_backup))
        except W.ImportNeedsConfirm as e: return {"ok": False, "confirm": str(e)}
        except W.ImportProblem as e: raise UIError(str(e))
        self._import_ctx = None
        return {"ok": True, "done": done}

    # ---------- مكان المخزن (حضور المناديب) ----------
    def place_get(self):
        self._need_login()
        with W.db() as c: pl = W.att_place(c)
        return {"pos": f"{pl['lat']}, {pl['lon']}" if pl.get("lat") is not None else "", "radius": pl["radius"], "auto": bool(pl["auto"]), "live": bool(pl["live"])}

    def place_save(self, pos, radius, auto, live):
        self._owner()
        txt = (pos or "").strip().translate(W._AR_DIGITS).replace("،", ",")
        lat = lon = None
        if txt:
            try:
                lat, lon = [float(x) for x in txt.replace(" ", "").split(",")[:2]]
                assert -90 <= lat <= 90 and -180 <= lon <= 180
            except Exception: raise UIError("الإحداثيات مش مظبوطة — لازم تبقى زي: 30.123456, 31.234567")
        try:
            rad = int(float(radius)); assert 20 <= rad <= 5000
        except Exception: raise UIError("المسافة لازم تبقى رقم من 20 لـ 5000 متر")
        with W.db() as c:
            c.execute("UPDATE settings SET wh_lat=?, wh_lon=?, wh_radius=?, att_auto=?, att_live=? WHERE id=1", (lat, lon, rad, 1 if auto else 0, 1 if live else 0))
            W.log(c, "إعدادات حضور المناديب", f"{txt or 'مفيش موقع'} — {rad} م — تلقائي: {'أيوه' if auto else 'لأ'} — مباشر: {'أيوه' if live else 'لأ'}")
        return True

    # ---------- مجلد النسخ الاحتياطي ----------
    def backup_dir_set(self, d):
        self._owner()
        d = d or ""
        if W.DB_CFG.get("mode") == "postgres":
            cfg = dict(W.DB_CFG); cfg["backup_dir"] = d; W.save_db_config(cfg)
            with W.db() as c: W.log(c, "تغيير مجلد النسخ التلقائي (الجهاز ده)", d or W.LOCAL_BACKUP_DIR)
        else:
            with W.db() as c: c.execute("UPDATE settings SET backup_dir=? WHERE id=1", (d,)); W.log(c, "تغيير مجلد النسخ التلقائي", d or W.LOCAL_BACKUP_DIR)
        return W.backup_dir()

    # ---------- تليجرام وجوجل شيت ----------
    ONLINE_BOOLS = ("enabled", "show_profit", "tg_daily", "tg_commands", "al_low", "al_returns", "al_sensitive", "al_credit", "al_attendance", "al_expected", "gs_enabled")

    def online_get(self):
        self._owner()
        cfg = W.load_online_config()
        out = {k: bool(cfg.get(k)) for k in self.ONLINE_BOOLS}
        out.update({"tg_token": cfg.get("tg_token") or "", "tg_time": cfg.get("tg_time") or "21:00", "al_big": cfg.get("al_big") or 0, "gs_sheet": cfg.get("gs_sheet") or "",
                    "gs_every": cfg.get("gs_every") or 10, "gs_key": cfg.get("gs_key") or "", "gs_email": W.gs_key_email(cfg.get("gs_key")) if cfg.get("gs_key") else "",
                    "status_tg": cfg.get("status_tg") or "", "status_gs": cfg.get("status_gs") or "", "users": self._tg_users(cfg)})
        return out

    def _tg_users(self, cfg):
        u = [{"cid": cid, "name": n, "role": "مدير", "emp": ""} for cid, n in (cfg.get("tg_chats") or {}).items()]
        u += [{"cid": cid, "name": r.get("tg", ""), "role": "محاسب" if W.is_acct(r) else "مندوب", "emp": r.get("name", "")} for cid, r in (cfg.get("tg_reps") or {}).items()]
        u += [{"cid": cid, "name": n, "role": "⏳ مستني ربط", "emp": ""} for cid, n in (cfg.get("tg_pending") or {}).items()]
        return u

    def online_save(self, v):
        self._owner()
        import re
        c = dict(W.ONLINE_CFG or W.load_online_config())
        for k in self.ONLINE_BOOLS: c[k] = bool(v.get(k))
        c["tg_token"] = (v.get("tg_token") or "").strip(); c["gs_sheet"] = (v.get("gs_sheet") or "").strip(); c["gs_key"] = v.get("gs_key") or c.get("gs_key") or ""
        t = (v.get("tg_time") or "").strip() or "21:00"
        if not re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", t): raise UIError("ساعة التقرير لازم تبقى زي 21:00")
        c["tg_time"] = t
        try: c["al_big"] = float(str(v.get("al_big") or 0).strip() or 0); c["gs_every"] = max(int(float(str(v.get("gs_every") or 10).strip() or 10)), 2)
        except ValueError: raise UIError("مبلغ الفاتورة الكبيرة ودقايق التحديث لازم يبقوا أرقام")
        if c["gs_enabled"] and (not c["gs_key"] or not W.gs_sheet_id(c["gs_sheet"])): raise UIError("عشان تشغّل الشيت: اختار ملف المفتاح وحط لينك الشيت")
        old = W.load_online_config()
        if c["tg_token"] != old.get("tg_token"): c["tg_offset"] = 0
        if c["enabled"] and not old.get("enabled"): c["last_audit_id"] = None; c["last_invoice_id"] = None
        W.save_online_config(**c)
        with W.db() as cc: W.log(cc, "إعدادات المتابعة من الموبايل", ("شغالة" if c["enabled"] else "مقفولة") + f" — Telegram: {len(c.get('tg_chats') or {})} موبايل — Sheets: {'شغال' if c['gs_enabled'] else 'مقفول'}")
        try: W.start_online_service().nudge()
        except Exception: pass
        return True

    def gs_set_key(self, path):
        self._owner()
        if not path or not W.gs_key_email(path): raise UIError("الملف ده مش ملف مفتاح Service Account")
        import shutil
        dest = os.path.join(W.APP_DATA_DIR, "google_key.json"); shutil.copyfile(path, dest); W._GS_CREDS.pop(dest, None)
        W.save_online_config(gs_key=dest)
        return {"gs_key": dest, "gs_email": W.gs_key_email(dest)}

    def gs_sync_now(self):
        self._owner()
        from datetime import datetime as _dt
        c = W.load_online_config()
        if not c.get("gs_key") or not W.gs_sheet_id(c.get("gs_sheet") or ""): raise UIError("احفظ ملف المفتاح ولينك الشيت الأول")
        old = getattr(W._TLS, "as_owner", False); W._TLS.as_owner = bool(c.get("show_profit"))
        try:
            n = W.sheets_sync(c)
            W.save_online_config(status_gs=f"{_dt.now().strftime('%H:%M')} — ✔ الشيت اتحدث ({n} صف)")
            return f"✔ الشيت اتحدث ({n} صف)"
        except Exception as e: raise UIError("✖ " + str(e))
        finally: W._TLS.as_owner = old

    def tg_find(self, token):
        """بيدوّر على رسايل جديدة للبوت (/start) وبيرجع اللي مستنيين ربط."""
        self._owner()
        tok = (token or "").strip()
        if not tok: raise UIError("اكتب توكن البوت الأول")
        cfg = W.load_online_config()
        if tok != cfg.get("tg_token"): W.save_online_config(tg_token=tok, tg_offset=0)
        try:
            me = W.tg_call(tok, "getMe")
            found = dict(W.ONLINE_CFG.get("tg_pending") or {})
            try:
                ups = W.tg_call(tok, "getUpdates", {"offset": int(W.ONLINE_CFG.get("tg_offset") or 0), "timeout": 0}, timeout=15)
                off = int(W.ONLINE_CFG.get("tg_offset") or 0)
                for u in ups or []:
                    off = max(off, u["update_id"] + 1); m = u.get("message") or {}; ch = m.get("chat") or {}
                    if ch.get("id") and str(ch.get("id")) not in (W.ONLINE_CFG.get("tg_chats") or {}) and str(ch.get("id")) not in (W.ONLINE_CFG.get("tg_reps") or {}):
                        found[str(ch["id"])] = " ".join(x for x in (ch.get("first_name"), ch.get("last_name")) if x) or ch.get("title") or ch.get("username") or str(ch["id"])
                W.save_online_config(tg_offset=off, tg_pending=found)
            except W.TelegramError as e:
                if "Conflict" not in str(e): raise
                W.save_online_config(tg_pending=found)
        except W.TelegramError as e: raise UIError("✖ " + str(e))
        with W.db() as c:
            reps = [{"id": r["id"], "name": r["name"]} for r in c.execute("SELECT id,name FROM employees WHERE kind='مندوب' AND COALESCE(active,1)=1 ORDER BY name").fetchall()]
            emps = [{"id": r["id"], "name": r["name"]} for r in c.execute("SELECT id,name FROM employees WHERE COALESCE(active,1)=1 ORDER BY name").fetchall()]
        return {"bot": me.get("username", ""), "pending": [{"cid": k, "name": v} for k, v in found.items()], "reps": reps, "emps": emps}

    def tg_assign(self, cid, role, emp_id=None):
        """role = manager | acct | rep | remove — ربط (أو تغيير صفة أو إلغاء ربط) موبايل."""
        self._owner()
        cid = str(cid); cfg = W.load_online_config(); tok = cfg.get("tg_token") or ""
        chats = dict(cfg.get("tg_chats") or {}); reps = dict(cfg.get("tg_reps") or {}); pend = dict(cfg.get("tg_pending") or {})
        name = chats.get(cid) or (reps.get(cid) or {}).get("tg") or pend.get(cid) or cid
        chats.pop(cid, None); reps.pop(cid, None); pend.pop(cid, None)
        note = None
        if role == "manager":
            chats[cid] = name; note = f"✅ اتربطت بنجاح بـ {W._e(W.LICENSED_COMPANY)}\n\n" + W.tg_help_text()
        elif role in ("acct", "rep"):
            with W.db() as c: e = c.execute("SELECT id,name FROM employees WHERE id=?", (emp_id,)).fetchone()
            if not e: raise UIError("اختار الموظف")
            if role == "acct": reps[cid] = {"emp_id": e["id"], "name": e["name"], "tg": name, "role": "acct"}; note = f"✅ اتربطت كمحاسب: {W._e(e['name'])}\n\n" + W.acct_help_text()
            else: reps[cid] = {"emp_id": e["id"], "name": e["name"], "tg": name}; note = f"✅ اتربطت كمندوب: {W._e(e['name'])}\n\n" + W.rep_help_text()
        elif role != "remove": raise UIError("اختار الصفة")
        W.save_online_config(tg_chats=chats, tg_reps=reps, tg_pending=pend)
        if note and tok:
            try: W.tg_send_text(tok, cid, note)
            except Exception: pass
        return self._tg_users(W.load_online_config())

    def tg_test(self):
        self._owner()
        cfg = W.load_online_config(); tok = cfg.get("tg_token"); ch = cfg.get("tg_chats") or {}
        if not tok or not ch: raise UIError("اربط موبايل مدير الأول")
        try:
            for cid in ch: W.tg_send_text(tok, cid, "👋 رسالة تجربة من برنامج المخازن\n\n" + W.cash_text())
        except Exception as e: raise UIError("✖ " + str(e))
        return True

    def tg_unlink_all(self):
        self._owner()
        W.save_online_config(tg_chats={}, tg_reps={}, tg_pending={})
        return True

    # ---------- السيرفر (قاعدة البيانات) ----------
    def server_get(self):
        self._owner()
        c = dict(W.DB_CFG)
        return {"mode": c.get("mode") or "sqlite", "host": c.get("host") or "", "port": c.get("port") or 5432, "dbname": c.get("dbname") or "warehouse",
                "user": c.get("user") or "postgres", "password": c.get("password") or "", "label": W.server_label()}

    def _read_cfg(self, v):
        c = dict(W.DB_CFG); c["mode"] = "postgres" if v.get("mode") == "postgres" else "sqlite"
        for k in ("host", "dbname", "user", "password"): c[k] = (v.get(k) or "").strip()
        try: c["port"] = int(v.get("port") or 5432)
        except ValueError: raise UIError("المنفذ لازم يكون رقم (عادةً 5432)")
        if c["mode"] == "postgres" and not c["host"]: raise UIError("اكتب عنوان الجهاز الأساسي")
        return c

    def server_test(self, v):
        self._owner()
        c = self._read_cfg(v)
        if c["mode"] != "postgres": return "الوضع ده مش محتاج اختبار."
        try:
            W._pg_connect(c).close(); return "✔ الاتصال تمام"
        except Exception as e:
            if "does not exist" in str(e):
                try: W._pg_connect(c, dbname="postgres").close(); return "✔ الاتصال بالسيرفر تمام.\nقاعدة البيانات لسه مش موجودة، وهتتعمل لوحدها لما تدوس حفظ."
                except Exception as e2: e = e2
            raise UIError("✖ " + W.pg_error_text(e))

    def server_save(self, v, migrate=None):
        """بيحفظ إعدادات الاتصال. لو السيرفر فاضي وفيه داتا على الجهاز: بيسأل (migrate) قبل ما ينقلها."""
        self._owner()
        c = self._read_cfg(v); old = dict(W.DB_CFG)
        if c["mode"] == "sqlite":
            W.save_db_config(c); W.DB_CFG.clear(); W.DB_CFG.update(c); W.pg_reset_connection(); W.init_db()
            return {"ok": True, "restart": True}
        try:
            W.DB_CFG.clear(); W.DB_CFG.update(c); W.pg_reset_connection()
            W.pg_ensure_database(c); W.init_db(); empty = W.pg_is_empty()
        except Exception as e:
            W.DB_CFG.clear(); W.DB_CFG.update(old); W.pg_reset_connection()
            raise UIError("✖ " + (str(e) if isinstance(e, W.DBUnavailable) else W.pg_error_text(e)))
        src, local = W.DB_PATH, None
        for p in (W.DB_PATH, W.OFFLINE_DB_PATH):
            cnt = W._local_data_counts(p)
            if cnt and (cnt["invoices"] or cnt["items"] or cnt["parties"]): src, local = p, cnt; break
        if empty and local and migrate is None:
            W.DB_CFG.clear(); W.DB_CFG.update(old); W.pg_reset_connection()
            return {"ok": False, "ask_migrate": f"السيرفر فاضي. تنقل الداتا اللي على الجهاز ده للسيرفر؟\n\nفواتير: {local['invoices']} • أصناف: {local['items']} • عملاء وموردين: {local['parties']} • مستخدمين: {local['users']}\n\n⚠️ اعمل الخطوة دي من جهاز واحد بس (الجهاز اللي عليه الداتا الحقيقية)."}
        if empty and local and migrate:
            try: W.import_sqlite_to_pg(src)
            except Exception as e:
                W.DB_CFG.clear(); W.DB_CFG.update(old); W.pg_reset_connection()
                raise UIError("✖ النقل فشل: " + str(e))
        W.save_db_config(c)
        return {"ok": True, "restart": True}

    # ---------- أول مرة (مفيش مستخدمين) ----------
    # ---------- الموقع ----------
    def web_get(self):
        self._owner()
        import socket
        ips = []
        try: cand = socket.gethostbyname_ex(socket.gethostname())[2]
        except Exception: cand = []
        try: cand += [i[4][0] for i in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)]
        except Exception: pass
        for ip in cand:
            if not ip.startswith("127.") and ip not in ips: ips.append(ip)
        port = int(W.DB_CFG.get("web_port") or 8780)
        is_ts = lambda ip: ip.startswith("100.") and 64 <= int(ip.split(".")[1]) <= 127      # عناوين Tailscale
        ts = [ip for ip in ips if is_ts(ip)]
        host = socket.gethostname().lower()
        return {"enabled": bool(W.DB_CFG.get("web_enabled")), "port": port, "running": _WEB["port"], "sessions": len(SESSIONS),
                "links": [f"http://{ip}:{port}" for ip in ips if not is_ts(ip)],
                "ts_links": ([f"http://{host}:{port}"] if ts else []) + [f"http://{ip}:{port}" for ip in ts]}

    def web_save(self, enabled, port):
        self._owner()
        try: port = int(port)
        except (TypeError, ValueError): raise UIError("رقم البورت لازم يبقى رقم")
        if not (1024 <= port <= 65535): raise UIError("البورت لازم يكون بين 1024 و 65535")
        cfg = dict(W.DB_CFG); cfg["web_enabled"] = bool(enabled); cfg["web_port"] = port; W.save_db_config(cfg); W.DB_CFG.update(cfg)
        stop_web()
        if enabled:
            try: start_web(port)
            except OSError as e: raise UIError(f"مش قادر يشغّل الموقع على البورت {port} — غالبًا مستخدم في برنامج تاني ({e})")
        with W.db() as c: W.log(c, "الموقع", ("شغال على البورت " + str(port)) if enabled else "اتقفل")
        return self.web_get()

    def first_owner(self, name, p1, p2):
        with W.db() as c: n = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if n: raise UIError("فيه مستخدمين بالفعل")
        name = (name or "").strip()
        if not name: raise UIError("اكتب اسم المستخدم")
        if len(p1 or "") < 4: raise UIError("كلمة السر لازم تكون 4 حروف/أرقام على الأقل")
        if p1 != p2: raise UIError("كلمتين السر مش متطابقتين")
        h_, salt = W.hash_pw(p1)
        with W.db() as c:
            uid = c.execute("INSERT INTO users(username,pw_hash,salt,role,active,created_at) VALUES(?,?,?,?,1,?)", (name, h_, salt, W.ROLE_OWNER, W.now_ts())).lastrowid
        W.CURRENT_USER.update(id=uid, username=name, role=W.ROLE_OWNER, screens=ALL_SCREENS + ["set:users"], emp_id=None)
        with W.db() as c: W.log(c, "إنشاء حساب المالك", name)
        return self.me()

    def server_settings_boot(self):
        """لما السيرفر مش متاح وقت الفتح: إعدادات الاتصال من غير تسجيل دخول."""
        c = dict(W.DB_CFG)
        return {"mode": c.get("mode") or "sqlite", "host": c.get("host") or "", "port": c.get("port") or 5432, "dbname": c.get("dbname") or "warehouse", "user": c.get("user") or "postgres", "password": c.get("password") or ""}

    def server_save_boot(self, v):
        """حفظ إعدادات الاتصال من شاشة «السيرفر مش متاح» (من غير نقل داتا)."""
        c = self._read_cfg(v); W.save_db_config(c); W.DB_CFG.clear(); W.DB_CFG.update(c); W.pg_reset_connection()
        return True


# ---------- الربط مع الواجهة ----------
from concurrent.futures import ThreadPoolExecutor
_WORKER = ThreadPoolExecutor(max_workers=1, thread_name_prefix="zalat-api")   # thread واحد = اتصال واحد بالسيرفر بيتعاد استخدامه


class Ctx:
    """جلسة واحدة: البرنامج على الجهاز ليه جلسة، وكل حد داخل من الموقع ليه جلسة لوحده."""
    def __init__(self, web=False):
        self.api = Api(); self.user = {"id": None, "username": "", "role": ""}; self.day_ok = 0.0; self.web = web; self.seen = time.time()


# أوامر مينفعش تتعمل من الموقع (بتفتح أو بتختار حاجات على جهاز المخزن نفسه)
WEB_BLOCKED = {"pick_file", "open_backup_folder", "import_start", "import_preview", "import_run", "backup_dir_set", "gs_set_key",
               "server_get", "server_test", "server_save", "server_settings_boot", "server_save_boot", "open_old_app", "web_get", "web_save", "cash_count_pdf"}


def call_api(api, name, args, ctx=None):
    return _WORKER.submit(_call_api, api, name, args, ctx).result()


def _call_api(api, name, args, ctx=None):
    if name.startswith("_") or not hasattr(api, name): return {"__error": "unknown"}
    if ctx is not None and ctx.web and name in WEB_BLOCKED: return {"__error": "الأمر ده بيتعمل من البرنامج على جهاز المخزن بس، مش من الموقع"}
    if ctx is not None:                       # كل أمر بيتنفذ باسم صاحب الجلسة (الـ worker واحد، فمفيش تداخل)
        W.CURRENT_USER.clear(); W.CURRENT_USER.update(ctx.user); W.DAY_OK["until"] = ctx.day_ok
        W._TLS.capture_print = [] if ctx.web else None
    try:
        _guard(name, args or [])
        res = {"result": _scope(name, getattr(api, name)(*(args or [])))}
        cap = getattr(W._TLS, "capture_print", None)
        if cap:
            try:
                with open(cap[-1], encoding="utf-8") as f: res["print_html"] = f.read()
            except Exception: pass
        return res
    except (UIError, W.InvoiceInputError, ValueError) as e:
        return {"__error": str(e)}
    except Exception as e:
        W.write_error_log("new-ui " + name + ": " + traceback.format_exc())
        msg = str(e) if isinstance(e, W.DBUnavailable) else (W.pg_error_text(e) if W.using_pg() else repr(e))
        return {"__error": "حصل خطأ: " + msg}
    finally:
        if ctx is not None:
            ctx.user = dict(W.CURRENT_USER); ctx.day_ok = W.DAY_OK["until"]; ctx.seen = time.time()
            W._TLS.capture_print = None


def _rep_parties(c, emp):
    """العملاء اللي المندوب يقدر يشتغل عليهم: كل العملاء (مش الموردين)."""
    return {r[0] for r in c.execute("SELECT id FROM parties WHERE COALESCE(kind,'') NOT IN ('مورد','أصول')").fetchall()}


def _guard(name, args):
    """الحماية في السيرفر نفسه: اليوزر مايقدرش ينفذ أمر شاشة مش مسموحله بيها (حتى لو عدّى الواجهة)."""
    u = W.CURRENT_USER
    if not u.get("id"): return
    if name not in ("logout", "boot"):                    # الصلاحيات بتتقري من الداتا كل مرة (لو المالك غيّرها أو وقف اليوزر بتسري على طول)
        with W.db() as c: r = c.execute("SELECT * FROM users WHERE id=?", (u["id"],)).fetchone()
        if not r or not r["active"]:
            u.clear(); u.update(id=None, username="", role=""); raise UIError("__LOGIN__")
        u.update(role=r["role"], screens=user_screens(r), emp_id=(r["emp_id"] if "emp_id" in r.keys() else None))
    if u.get("role") == W.ROLE_OWNER: return
    if name in ("statement", "print_statement", "save_voucher", "save_party", "delete_parties", "party_get") and args:
        a0 = args[0]; pids = a0 if isinstance(a0, list) else [a0.get("party_id") or a0.get("id")] if isinstance(a0, dict) else [a0]
        ids = _asset_ids()
        if any(str(x) in {str(i) for i in ids} for x in pids if x is not None): raise UIError("حسابات الأصول للملاك بس")
        if name == "save_party" and isinstance(a0, dict) and a0.get("kind") == ASSET: raise UIError("حسابات الأصول للملاك بس")
    need = METHOD_SCREENS.get(name)
    if need and not (need & set(u.get("screens") or [])): raise UIError("مش مسموحلك بالشاشة دي — اطلب من المالك يفتحهالك")
    if u.get("role") != W.ROLE_REP: return
    if name in NO_REP: raise UIError("الأمر ده للمحاسب أو المالك بس")
    emp = u.get("emp_id")
    with W.db() as c:
        mine = _rep_parties(c, emp)
        if name == "save_invoice":
            p = args[0]
            if p.get("kind") not in ("مبيعات", "مرتجع مبيعات"): raise UIError("المندوب بيعمل فواتير مبيعات ومرتجع مبيعات بس")
            if int(p.get("party_id") or 0) not in mine: raise UIError("ده مش عميل")
            p["rep_id"] = emp
            if p.get("edit_id"):
                o = c.execute("SELECT rep_id FROM invoices WHERE id=?", (p["edit_id"],)).fetchone()
                if not o or o[0] != emp: raise UIError("الفاتورة دي مش بتاعتك")
        elif name in ("invoice", "print_invoice", "invoice_for_edit", "delete_invoice"):
            o = c.execute("SELECT rep_id FROM invoices WHERE id=?", (args[0],)).fetchone()
            if not o or o[0] != emp: raise UIError("الفاتورة دي مش بتاعتك")
        elif name == "save_voucher":
            p = args[0]
            if p.get("kind") != "تحصيل": raise UIError("المندوب بيعمل سندات تحصيل بس")
            if int(p.get("party_id") or 0) not in mine: raise UIError("ده مش عميل")
            p["rep_id"] = emp
            if p.get("edit_id"):
                o = c.execute("SELECT rep_id FROM payments WHERE id=?", (p["edit_id"],)).fetchone()
                if not o or o[0] != emp: raise UIError("السند ده مش بتاعك")
        elif name in ("voucher", "delete_voucher", "print_receipt"):
            key = str(args[0]); typ, rid = (key.split("-") + ["0"])[:2] if "-" in key else ("p", key)
            if typ != "p": raise UIError("المندوب بيشوف سندات التحصيل بس")
            o = c.execute("SELECT rep_id FROM payments WHERE id=?", (int(rid),)).fetchone()
            if not o or o[0] != emp: raise UIError("السند ده مش بتاعك")
        elif name in ("statement", "print_statement", "voucher_preview"):
            pid = args[1] if name == "voucher_preview" else args[0]
            if pid and int(pid) not in mine: raise UIError("المندوب بيشوف حسابات العملاء بس")
        elif name in ("delete_parties", "print_balances"):
            raise UIError("الأمر ده للمحاسب أو المالك بس")


def _asset_ids():
    with W.db() as c: return {r[0] for r in c.execute("SELECT id FROM parties WHERE kind=?", (ASSET,)).fetchall()}


def _hide_assets(name, res):
    """حسابات «الأصول» (أرباح الملاك ...) بتبان للملاك بس."""
    if name not in ("invoice_setup", "voucher_setup", "parties_list", "parties_full", "balances"): return res
    ids = _asset_ids()
    if not ids: return res
    if name in ("invoice_setup", "voucher_setup") and isinstance(res, dict): res["parties"] = [p for p in res.get("parties") or [] if p.get("id") not in ids]
    elif name in ("parties_list", "parties_full") and isinstance(res, list): res = [p for p in res if p.get("id") not in ids]
    elif name == "balances" and isinstance(res, dict):
        res["rows"] = [r for r in res.get("rows") or [] if r.get("id") not in ids]
        cd = res.get("cards") or {}
        if "assets" in cd: cd["assets"] = 0; cd["hide_assets"] = True
    return res


def _scope(name, res):
    """المندوب بيشوف عملاءه وفواتيره وسنداته بس، وحسابات الأصول للملاك بس."""
    u = W.CURRENT_USER
    if u.get("id") and u.get("role") == W.ROLE_ACC: return _hide_assets(name, res)
    if u.get("role") != W.ROLE_REP or not u.get("id"): return res
    emp = u.get("emp_id")
    with W.db() as c:
        mine = _rep_parties(c, emp)
        rname = (c.execute("SELECT name FROM employees WHERE id=?", (emp,)).fetchone() or [""])[0]
    if name in ("invoice_setup", "voucher_setup") and isinstance(res, dict):
        res["parties"] = [p for p in res.get("parties") or [] if p.get("id") in mine]
        if "reps" in res: res["reps"] = [r for r in res["reps"] if r.get("id") == emp] or res["reps"][:0]
    elif name == "parties_list": res = [p for p in res if p.get("id") in mine]
    elif name == "balances" and isinstance(res, dict):
        res["rows"] = [r for r in res.get("rows") or [] if r.get("id") in mine]
        res["cards"] = {"recv": _r2(sum(max(r.get("balance", 0), 0) for r in res["rows"])), "pay": 0, "cash": 0, "inv": 0, "sale": 0, "net": 0, "rep": True}
    elif name == "invoices": res = [r for r in res if r.get("rep") == rname]
    elif name == "vouchers": res = [r for r in res if r.get("rep") == rname and str(r.get("key", "")).startswith("p-")]
    elif name == "dashboard" and isinstance(res, dict):
        res["rows"] = [r for r in res.get("rows") or [] if r.get("rep") == rname]
    elif name == "expected" and isinstance(res, list): res = [r for r in res if r.get("rep") == rname]
    elif name == "today_bar" and isinstance(res, dict):
        with W.db() as c:
            r = {k: c.execute(f"SELECT COUNT(*), COALESCE(SUM({W.NET_SQL}),0) FROM invoices i WHERE i.kind=? AND i.inv_date=? AND i.rep_id=?", (k, _today(), emp)).fetchone() for k in ("مبيعات", "مرتجع مبيعات")}
            col = c.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE kind='تحصيل' AND pay_date=? AND rep_id=?", (_today(), emp)).fetchone()[0]
        res = {"count": r["مبيعات"][0] + r["مرتجع مبيعات"][0], "sales": _r2(r["مبيعات"][1]), "buys": 0, "n_buys": 0, "ret": _r2(r["مرتجع مبيعات"][1]),
               "collections": _r2(col), "expenses": 0, "closed": res.get("closed")}
    return res


class Bridge:
    """اللي الـ JavaScript بيشوفه جوه نافذة البرنامج: window.pywebview.api.call(name, args)."""
    def __init__(self): self._ctx = Ctx(web=False); self._api = self._ctx.api
    def call(self, name, args=None): return call_api(self._api, name, args, self._ctx)


# ---------- الموقع (أكتر من حد في نفس الوقت، كل واحد بجلسته) ----------
SESSIONS = {}                    # token -> Ctx
_FAILS = {}                      # ip -> [عدد المحاولات الغلط, آخر وقت]
SESSION_IDLE = 12 * 3600
_WEB = {"srv": None, "port": None}


def _session(token):
    now = time.time()
    for t in [t for t, c in SESSIONS.items() if now - c.seen > SESSION_IDLE]: SESSIONS.pop(t, None)
    return SESSIONS.get(token or "")


def make_handler(dev=False):
    from http.server import SimpleHTTPRequestHandler
    import secrets as _secrets
    from http.cookies import SimpleCookie

    class H(SimpleHTTPRequestHandler):
        extensions_map = {**SimpleHTTPRequestHandler.extensions_map, ".webmanifest": "application/manifest+json", ".js": "text/javascript", ".css": "text/css", ".png": "image/png"}
        def __init__(self, *a, **k): super().__init__(*a, directory=UI_DIR, **k)
        def log_message(self, *a): pass

        def end_headers(self):
            self.send_header("X-Content-Type-Options", "nosniff"); self.send_header("Referrer-Policy", "same-origin")
            if self.path.endswith((".js", ".css", ".html", "/", ".webmanifest")): self.send_header("Cache-Control", "no-cache")
            if self.path.endswith("sw.js"): self.send_header("Service-Worker-Allowed", "/")
            super().end_headers()

        def _ip(self):
            return (self.headers.get("CF-Connecting-IP") or self.headers.get("X-Forwarded-For") or self.client_address[0]).split(",")[0].strip()

        def _token(self):
            c = SimpleCookie(self.headers.get("Cookie") or "")
            return c["zs"].value if "zs" in c else ""

        def _send(self, obj, cookie=None):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(200); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(body)))
            if cookie is not None:
                secure = "; Secure" if (self.headers.get("X-Forwarded-Proto") == "https" or self.headers.get("CF-Visitor", "").find("https") >= 0) else ""
                self.send_header("Set-Cookie", f"zs={cookie}; Path=/; HttpOnly; SameSite=Lax; Max-Age={SESSION_IDLE if cookie else 0}{secure}")
            self.end_headers(); self.wfile.write(body)

        def do_GET(self):
            if self.path.split("?")[0] == "/web.js":          # علامة إن ده الموقع (مش البرنامج على الجهاز)
                b = b"window.ZALAT_WEB=1;"
                self.send_response(200); self.send_header("Content-Type", "application/javascript"); self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b); return
            if self.path.split("?")[0] in ("/", ""): self.path = "/index.html"
            return super().do_GET()

        def do_POST(self):
            if not self.path.startswith("/api/"): self.send_error(404); return
            name = self.path.rsplit("/", 1)[-1]
            n = int(self.headers.get("Content-Length") or 0)
            if n > 5_000_000: self.send_error(413); return
            try: args = json.loads(self.rfile.read(n) or b"[]")
            except ValueError: return self._send({"__error": "طلب غلط"})
            ip = self._ip(); tok = self._token(); ctx = _session(tok)
            if name == "login":
                f = _FAILS.get(ip)
                if f and f[0] >= 5 and time.time() - f[1] < 300:
                    return self._send({"__error": "محاولات دخول غلط كتير — استنى 5 دقايق وجرب تاني"})
                ctx = Ctx(web=not dev)
                res = call_api(ctx.api, "login", args, ctx)
                if "__error" in res:
                    f = _FAILS.setdefault(ip, [0, 0]); f[0] += 1; f[1] = time.time()
                    return self._send(res)
                _FAILS.pop(ip, None)
                tok = _secrets.token_urlsafe(32); SESSIONS[tok] = ctx
                return self._send(res, cookie=tok)
            if name == "logout":
                if ctx: call_api(ctx.api, "logout", [], ctx); SESSIONS.pop(tok, None)
                return self._send({"result": True}, cookie="")
            if ctx is None:
                if name == "boot":                     # قبل الدخول: بيانات الشركة والشعار بس
                    tmp = Ctx(web=not dev); r = call_api(tmp.api, "boot", [], tmp)
                    if "result" in r: r["result"]["web"] = True
                    return self._send(r)
                if name == "first_owner":
                    tmp = Ctx(web=not dev); r = call_api(tmp.api, name, args, tmp)
                    if "__error" in r: return self._send(r)
                    tok = _secrets.token_urlsafe(32); SESSIONS[tok] = tmp
                    return self._send(r, cookie=tok)
                return self._send({"__error": "__LOGIN__"})
            r = call_api(ctx.api, name, args, ctx)
            if name == "boot" and "result" in r: r["result"]["web"] = True
            return self._send(r)
    return H


def serve(port=8765, host="127.0.0.1", dev=True):
    """الموقع: الواجهة على http://host:port والـ API على POST /api/<name> (بجلسات لكل مستخدم)."""
    from http.server import ThreadingHTTPServer
    srv = ThreadingHTTPServer((host, port), make_handler(dev))
    print(f"http://{host}:{port}", flush=True)
    srv.serve_forever()


def start_web(port):
    """تشغيل الموقع في الخلفية من جوه البرنامج على جهاز المخزن."""
    from http.server import ThreadingHTTPServer
    if _WEB["srv"]: return _WEB["port"]
    srv = ThreadingHTTPServer(("0.0.0.0", int(port)), make_handler(False))
    threading.Thread(target=srv.serve_forever, daemon=True, name="zalat-web").start()
    _WEB.update(srv=srv, port=int(port))
    return int(port)


def stop_web():
    if _WEB["srv"]:
        try: _WEB["srv"].shutdown(); _WEB["srv"].server_close()
        except Exception: pass
    _WEB.update(srv=None, port=None); SESSIONS.clear()


def main():
    if "--serve" in sys.argv:
        i = sys.argv.index("--serve")
        return serve(int(sys.argv[i + 1]) if len(sys.argv) > i + 1 else 8765)
    if "--web" in sys.argv:                   # الموقع لوحده من غير شاشة البرنامج (لجهاز سيرفر)
        i = sys.argv.index("--web")
        return serve(int(sys.argv[i + 1]) if len(sys.argv) > i + 1 and sys.argv[i + 1].isdigit() else 8780, "0.0.0.0", dev=False)
    try:
        if W.DB_CFG.get("web_enabled"): start_web(W.DB_CFG.get("web_port") or 8780)
    except Exception: W.write_error_log("web: " + traceback.format_exc())
    try:
        import webview
        win = webview.create_window("سيستم المخازن والمبيعات", os.path.join(UI_DIR, "index.html"), js_api=Bridge(), width=1366, height=840,
                                    min_size=(1000, 640), background_color="#eef2f7", text_select=True)
        webview.start(lambda: win.maximize(), gui="edgechromium" if os.name == "nt" else None, private_mode=False,
                      storage_path=os.path.join(W.APP_DATA_DIR, "webview"))
    except Exception as e:
        W.write_error_log("new-ui start: " + traceback.format_exc())
        try:
            import tkinter as tk
            from tkinter import messagebox
            r = tk.Tk(); r.withdraw()
            messagebox.showerror("الواجهة الجديدة", f"الواجهة الجديدة مش راضية تفتح:\n{e}\n\nلو الجهاز مفيهوش «Microsoft Edge WebView2 Runtime» نزّله من موقع مايكروسوفت.\nاستخدم السيستم القديم لحد ما نصلحها.\n"
                                                    f"تفاصيل الخطأ في:\n{os.path.join(W.APP_DATA_DIR, 'error_log.txt')}", parent=r)
            r.destroy()
        except Exception: pass


if __name__ == "__main__":
    main()
