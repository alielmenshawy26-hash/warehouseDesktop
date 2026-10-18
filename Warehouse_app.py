# -*- coding: utf-8 -*-
"""
برنامج مخازن ومبيعات محلي لويندوز.
التخزين في SQLite داخل مجلد AppData؛ لا يحتاج إنترنت أو متصفح.

اتفاقية الرصيد: الرصيد الموجب = على العميل (مدين) ، السالب = للمورد (دائن)
  مدين: فواتير المبيعات + مرتجعات المشتريات + المبالغ المدفوعة (دفع)
  دائن: فواتير المشتريات + مرتجعات المبيعات + المبالغ المحصّلة (تحصيل)
"""
import os, sqlite3, webbrowser
from datetime import date, datetime, timedelta
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

APP_DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "WarehouseDesktop")
PRINT_DIR = os.path.join(APP_DATA_DIR, "printouts")
os.makedirs(PRINT_DIR, exist_ok=True)
DB_PATH = os.path.join(APP_DATA_DIR, "warehouse.db")

KINDS = ("مبيعات", "مشتريات", "مرتجع مبيعات", "مرتجع مشتريات")
SIGN = {"مشتريات": 1, "مرتجع مبيعات": 1, "مبيعات": -1, "مرتجع مشتريات": -1}      # أثر الفاتورة على المخزون
DEBIT_KINDS = ("مبيعات", "مرتجع مشتريات")                                          # فواتير تزيد الرصيد (مدين)
PAID_KIND = {"مبيعات": "تحصيل", "مشتريات": "دفع", "مرتجع مبيعات": "دفع", "مرتجع مشتريات": "تحصيل"}
PREFIX = {"مبيعات": "م", "مشتريات": "ش", "مرتجع مبيعات": "رم", "مرتجع مشتريات": "رش"}
PAID_LABEL = {"مبيعات": "المحصّل الآن من العميل", "مشتريات": "المدفوع الآن للمورد",
              "مرتجع مبيعات": "المدفوع الآن للعميل (رد نقدي)", "مرتجع مشتريات": "المحصّل الآن من المورد (رد نقدي)"}

# صافي الفاتورة = مجموع البنود - الخصم (يُستخدم مع الاسم المستعار i لجدول invoices)
NET_SQL = "(COALESCE((SELECT SUM(qty*price) FROM invoice_lines WHERE invoice_id=i.id),0)-COALESCE(i.discount,0))"
SIGNED_SALES_SQL = f"CASE i.kind WHEN 'مبيعات' THEN {NET_SQL} WHEN 'مرتجع مبيعات' THEN -{NET_SQL} ELSE 0 END"
STOCK_CASE = "CASE i.kind WHEN 'مشتريات' THEN l.qty WHEN 'مرتجع مبيعات' THEN l.qty WHEN 'مبيعات' THEN -l.qty WHEN 'مرتجع مشتريات' THEN -l.qty ELSE 0 END"

def raw_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con

class db:
    """اتصال بقاعدة البيانات: يحفظ عند النجاح، يتراجع عند الخطأ، ويقفل الاتصال دائمًا."""
    def __enter__(self):
        self.con = raw_db(); return self.con
    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None: self.con.commit()
            else: self.con.rollback()
        finally:
            self.con.close()
        return False

def now_ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def fmt_time(ts):
    """تحويل وقت مخزّن إلى نظام 12 ساعة (مثال: 02:35 م)."""
    if not ts: return ""
    try: t = datetime.strptime(str(ts)[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError: return ""
    return t.strftime("%I:%M ") + ("ص" if t.hour < 12 else "م")

EMP_KINDS = ("موظف", "عامل", "مندوب")
OFFICE = "مكتب"
DEFAULT_COMPANY = "شركة فرحات"
DEFAULT_TAGLINE = "للتوريدات العمومية"

def add_col(c, table, col, decl):
    cols = [r[1] for r in c.execute(f"PRAGMA table_info({table})")]
    if col not in cols:
        c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
        return True
    return False

def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), company TEXT DEFAULT '', english TEXT DEFAULT '', address TEXT DEFAULT '', phone TEXT DEFAULT '', taxno TEXT DEFAULT '');
        INSERT OR IGNORE INTO settings(id) VALUES(1);
        CREATE TABLE IF NOT EXISTS items(id INTEGER PRIMARY KEY, code TEXT UNIQUE, name TEXT NOT NULL, unit TEXT DEFAULT 'قطعة', sell_price REAL DEFAULT 0, buy_price REAL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS parties(id INTEGER PRIMARY KEY, name TEXT NOT NULL, kind TEXT DEFAULT 'عميل/مورد', phone TEXT DEFAULT '', address TEXT DEFAULT '', opening REAL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS invoices(id INTEGER PRIMARY KEY, number TEXT UNIQUE, kind TEXT NOT NULL, inv_date TEXT NOT NULL, party_id INTEGER, notes TEXT DEFAULT '', discount REAL DEFAULT 0, tax REAL DEFAULT 0, FOREIGN KEY(party_id) REFERENCES parties(id));
        CREATE TABLE IF NOT EXISTS invoice_lines(id INTEGER PRIMARY KEY, invoice_id INTEGER NOT NULL, item_id INTEGER, item_name TEXT NOT NULL, unit TEXT DEFAULT '', qty REAL NOT NULL, price REAL NOT NULL, FOREIGN KEY(invoice_id) REFERENCES invoices(id) ON DELETE CASCADE, FOREIGN KEY(item_id) REFERENCES items(id));
        CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY, party_id INTEGER NOT NULL, pay_date TEXT NOT NULL, kind TEXT NOT NULL, amount REAL NOT NULL, notes TEXT DEFAULT '', FOREIGN KEY(party_id) REFERENCES parties(id));
        CREATE TABLE IF NOT EXISTS employees(id INTEGER PRIMARY KEY, name TEXT NOT NULL, job TEXT DEFAULT '', phone TEXT DEFAULT '', salary REAL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS expense_cats(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
        CREATE TABLE IF NOT EXISTS expenses(id INTEGER PRIMARY KEY, exp_date TEXT NOT NULL, kind TEXT NOT NULL, category TEXT DEFAULT '', amount REAL NOT NULL, notes TEXT DEFAULT '', employee_id INTEGER, deducted REAL DEFAULT 0, FOREIGN KEY(employee_id) REFERENCES employees(id));
        CREATE TABLE IF NOT EXISTS cash_moves(id INTEGER PRIMARY KEY, move_date TEXT NOT NULL, kind TEXT NOT NULL, amount REAL NOT NULL, notes TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS audit_log(id INTEGER PRIMARY KEY, at TEXT NOT NULL, user TEXT DEFAULT '', action TEXT NOT NULL, details TEXT DEFAULT '');
        """)
        add_col(c, "settings", "operator", "TEXT DEFAULT ''")
        add_col(c, "settings", "backup_dir", "TEXT DEFAULT ''")
        add_col(c, "settings", "cash_opening", "REAL DEFAULT 0")
        add_col(c, "items", "min_stock", "REAL DEFAULT 0")
        add_col(c, "payments", "invoice_id", "INTEGER")
        # اسم الشركة في رأس البرنامج + السطر التاني تحته
        if add_col(c, "settings", "tagline", "TEXT DEFAULT ''"):
            c.execute("UPDATE settings SET tagline=? WHERE id=1", (DEFAULT_TAGLINE,))
            c.execute("UPDATE settings SET company=? WHERE id=1 AND TRIM(COALESCE(company,''))=''", (DEFAULT_COMPANY,))
        # نوع الموظف (موظف/عامل/مندوب)؛ خانة job القديمة أصبحت «الصفة»
        add_col(c, "employees", "kind", "TEXT DEFAULT 'موظف'")
        c.execute("UPDATE employees SET kind='موظف' WHERE kind IS NULL OR kind NOT IN ('موظف','عامل','مندوب')")
        # المندوب (NULL = مكتب) في فواتير المبيعات وسندات التحصيل
        add_col(c, "invoices", "rep_id", "INTEGER")
        add_col(c, "payments", "rep_id", "INTEGER")
        # وقت التسجيل
        for t in ("invoices", "payments", "expenses", "cash_moves"):
            add_col(c, t, "created_at", "TEXT")
        # عدّاد أرقام الفواتير (يمنع تكرار الرقم بعد حذف آخر فاتورة)
        c.execute("CREATE TABLE IF NOT EXISTS counters(kind TEXT PRIMARY KEY, last INTEGER NOT NULL DEFAULT 0)")
        # العينات: أصناف منفصلة تمامًا عن الأصناف العادية
        c.executescript("""
        CREATE TABLE IF NOT EXISTS sample_items(id INTEGER PRIMARY KEY, code TEXT UNIQUE, name TEXT NOT NULL, unit TEXT DEFAULT 'قطعة');
        CREATE TABLE IF NOT EXISTS samples(id INTEGER PRIMARY KEY, s_date TEXT NOT NULL, created_at TEXT, kind TEXT NOT NULL,
            sample_item_id INTEGER NOT NULL, qty REAL NOT NULL, cost REAL DEFAULT 0, party_id INTEGER, notes TEXT DEFAULT '',
            FOREIGN KEY(sample_item_id) REFERENCES sample_items(id), FOREIGN KEY(party_id) REFERENCES parties(id));
        """)
        if c.execute("SELECT COUNT(*) FROM expense_cats").fetchone()[0] == 0:
            for n in ("شيال", "أجور", "جاز", "إيجار عربية", "كهربا"):
                c.execute("INSERT OR IGNORE INTO expense_cats(name) VALUES(?)", (n,))

def fmt(n):
    return f"{float(n or 0):,.2f}"

def esc(s):
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def check_date(s):
    return date.fromisoformat(s.strip()).isoformat()

def open_file(path):
    try: os.startfile(path)
    except Exception: webbrowser.open("file:///" + path.replace("\\", "/"))

def party_label(p):
    """اسم العميل/المورد في القوائم: يضم الفرع/العنوان والهاتف عشان نفرّق بين الأسماء المتشابهة."""
    s = f'{p["id"]} - {p["name"]}'
    if p["address"]: s += f' — {p["address"]}'
    if p["phone"]: s += f' — {p["phone"]}'
    return s

def item_label(it):
    s = f'{it["id"]} - {it["name"]}'
    if it["code"]: s += f' [{it["code"]}]'
    return s

def log(c, action, details=""):
    """تسجيل عملية في سجل النشاط (داخل نفس المعاملة)."""
    try:
        u = c.execute("SELECT operator FROM settings WHERE id=1").fetchone()
        c.execute("INSERT INTO audit_log(at,user,action,details) VALUES(?,?,?,?)",
                  (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), (u["operator"] if u else "") or "", action, details))
    except Exception:
        pass

def num_of(number):
    try: return int(''.join(ch for ch in str(number or "") if ch.isdigit()))
    except ValueError: return 0

def next_no(kind):
    """الرقم التالي = أكبر رقم استُخدم لهذا النوع (حتى لو اتحذفت فاتورته) + 1."""
    with db() as c:
        used = [num_of(r[0]) for r in c.execute("SELECT number FROM invoices WHERE kind=?", (kind,))]
        cnt = c.execute("SELECT last FROM counters WHERE kind=?", (kind,)).fetchone()
    top = max(used + [cnt[0] if cnt else 0])
    if top: return f"{PREFIX[kind]}{top + 1}"
    return f"{PREFIX[kind]}{102820 if kind == 'مبيعات' else 1}"

def bump_counter(c, kind, number):
    n = num_of(number)
    if n: c.execute("INSERT INTO counters(kind,last) VALUES(?,?) ON CONFLICT(kind) DO UPDATE SET last=MAX(last,excluded.last)", (kind, n))

# ---------------- المناديب ----------------
def rep_label(r):
    return f'{r["id"]} - {r["name"]}'

def rep_lookup(c, include_id=None):
    """قائمة اختيار المندوب: «مكتب» + الموظفين من نوع مندوب (ومعهم المندوب الحالي للسجل لو اتغير نوعه)."""
    rows = c.execute("SELECT id,name FROM employees WHERE kind='مندوب' OR id=? ORDER BY name", (include_id or -1,)).fetchall()
    d = {OFFICE: None}
    for r in rows: d[rep_label(r)] = r["id"]
    return d

def rep_name_of(c, rep_id):
    if not rep_id: return OFFICE
    r = c.execute("SELECT name FROM employees WHERE id=?", (rep_id,)).fetchone()
    return r["name"] if r else OFFICE

def stock_of(c, item_id):
    return c.execute(f"SELECT COALESCE(SUM({STOCK_CASE}),0) FROM invoice_lines l JOIN invoices i ON i.id=l.invoice_id WHERE l.item_id=?", (item_id,)).fetchone()[0]

def check_stock(c, item_ids):
    """يرفع ValueError لو أي صنف سيصبح رصيده بالسالب (يُستدعى داخل المعاملة بعد التعديل)."""
    for iid in item_ids:
        if iid is None: continue
        if stock_of(c, iid) < -1e-9:
            r = c.execute("SELECT name FROM items WHERE id=?", (iid,)).fetchone()
            raise ValueError(f"الرصيد غير كافٍ للصنف «{r['name'] if r else iid}» (سيصبح بالسالب)")

# ---------------- حسابات العملاء والموردين ----------------
def party_moves(c, pid):
    """كل حركات الحساب (فواتير + سندات) مرتبة. كل حركة: (تاريخ, ترتيب, id, مرجع, بيان, مدين, دائن)"""
    moves = []
    for r in c.execute(f"SELECT i.id,i.number,i.kind,i.inv_date d,i.created_at,{NET_SQL} amt FROM invoices i WHERE i.party_id=?", (pid,)):
        amt = float(r["amt"]); deb = r["kind"] in DEBIT_KINDS
        moves.append((r["d"], 0, r["id"], r["number"], "فاتورة " + r["kind"], amt if deb else 0.0, 0.0 if deb else amt, (r["d"], 0, r["id"]), r["created_at"]))
    for r in c.execute("SELECT * FROM payments WHERE party_id=?", (pid,)):
        amt = float(r["amount"]); is_col = r["kind"] == "تحصيل"
        label = ("تحصيل" if is_col else "دفع") + (f" - {r['notes']}" if r["notes"] else "")
        # الدفعة المرتبطة بفاتورة تأتي مباشرة بعدها؛ السند المستقل بعد فواتير نفس اليوم
        key = (r["pay_date"], 0, r["invoice_id"] + 0.5) if r["invoice_id"] else (r["pay_date"], 1, r["id"])
        moves.append((r["pay_date"], 1, r["id"], f"سند {r['id']}", label, 0.0 if is_col else amt, amt if is_col else 0.0, key, r["created_at"]))
    moves.sort(key=lambda m: m[7])
    return moves

def party_balance(c, pid):
    p = c.execute("SELECT opening FROM parties WHERE id=?", (pid,)).fetchone()
    return float(p["opening"] or 0) + sum(m[5] - m[6] for m in party_moves(c, pid))

def build_statement(pid, start, end):
    with db() as c:
        party = c.execute("SELECT * FROM parties WHERE id=?", (pid,)).fetchone()
        moves = party_moves(c, pid)
    opening = float(party["opening"] or 0)
    for m in moves:
        if m[0] < start: opening += m[5] - m[6]
    rows, running = [], opening
    for m in moves:
        if start <= m[0] <= end:
            running += m[5] - m[6]
            rows.append((m[0], m[3], m[4], m[5], m[6], running, m[1], m[2], m[8]))
    return party, opening, rows, running

def party_last_text(c, pid):
    col = c.execute("SELECT pay_date,amount FROM payments WHERE party_id=? AND kind='تحصيل' ORDER BY pay_date DESC,id DESC LIMIT 1", (pid,)).fetchone()
    pay = c.execute("SELECT pay_date,amount FROM payments WHERE party_id=? AND kind='دفع' ORDER BY pay_date DESC,id DESC LIMIT 1", (pid,)).fetchone()
    inv = c.execute("SELECT inv_date,number,kind FROM invoices WHERE party_id=? ORDER BY inv_date DESC,id DESC LIMIT 1", (pid,)).fetchone()
    t1 = f"آخر تحصيل: {col['pay_date']} ({fmt(col['amount'])})" if col else "آخر تحصيل: —"
    t2 = f"آخر دفع: {pay['pay_date']} ({fmt(pay['amount'])})" if pay else "آخر دفع: —"
    t3 = f"آخر فاتورة: {inv['number']} ({inv['inv_date']})" if inv else "آخر فاتورة: —"
    return "   •   ".join([t1, t2, t3])

# ---------------- الخزنة ----------------
def treasury_moves(c):
    """حركات الخزنة: (تاريخ, ترتيب, id, مفتاح, بيان, وارد, صادر, وقت التسجيل)"""
    mv = []
    for r in c.execute("SELECT p.*,pt.name pname FROM payments p JOIN parties pt ON pt.id=p.party_id"):
        amt = float(r["amount"]); inn = r["kind"] == "تحصيل"
        label = ("تحصيل من " if inn else "دفع إلى ") + r["pname"] + (f" - {r['notes']}" if r["notes"] else "")
        mv.append((r["pay_date"], 0, r["id"], f"p-{r['id']}", label, amt if inn else 0.0, 0.0 if inn else amt, r["created_at"]))
    for r in c.execute("SELECT e.*,m.name ename FROM expenses e LEFT JOIN employees m ON m.id=e.employee_id"):
        amt = float(r["amount"])
        if r["kind"] == "مصروف": label = "مصروفات: " + (r["category"] or "")
        elif r["kind"] == "مرتب": label = "مرتب: " + (r["ename"] or "")
        else: label = "سلفة: " + (r["ename"] or "")
        if r["notes"]: label += f" - {r['notes']}"
        mv.append((r["exp_date"], 1, r["id"], f"e-{r['id']}", label, 0.0, amt, r["created_at"]))
    for r in c.execute("SELECT * FROM cash_moves"):
        amt = float(r["amount"]); inn = r["kind"] == "إيداع"
        label = r["kind"] + (f" - {r['notes']}" if r["notes"] else "")
        mv.append((r["move_date"], 2, r["id"], f"c-{r['id']}", label, amt if inn else 0.0, 0.0 if inn else amt, r["created_at"]))
    mv.sort(key=lambda m: (m[0], m[1], m[2]))
    return mv

def cash_opening(c):
    return float(c.execute("SELECT cash_opening FROM settings WHERE id=1").fetchone()[0] or 0)

def cash_balance(c):
    return cash_opening(c) + sum(m[5] - m[6] for m in treasury_moves(c))

# ---------------- الأرباح ----------------
def profit_summary(start, end):
    with db() as c:
        items = c.execute("SELECT id,name,buy_price FROM items").fetchall()
        sold = {(r["item_id"], r["kind"]): (r["q"], r["amt"]) for r in c.execute(
            "SELECT l.item_id,i.kind,SUM(l.qty) q,SUM(l.qty*l.price) amt FROM invoice_lines l JOIN invoices i ON i.id=l.invoice_id "
            "WHERE i.kind IN ('مبيعات','مرتجع مبيعات') AND i.inv_date BETWEEN ? AND ? GROUP BY l.item_id,i.kind", (start, end))}
        buy = {r["item_id"]: (r["q"], r["cost"]) for r in c.execute(
            "SELECT l.item_id,SUM(l.qty) q,SUM(l.qty*l.price) cost FROM invoice_lines l JOIN invoices i ON i.id=l.invoice_id "
            "WHERE i.kind='مشتريات' AND i.inv_date<=? GROUP BY l.item_id", (end,))}
        disc = {r["kind"]: float(r["d"]) for r in c.execute(
            "SELECT kind,COALESCE(SUM(discount),0) d FROM invoices WHERE kind IN ('مبيعات','مرتجع مبيعات') AND inv_date BETWEEN ? AND ? GROUP BY kind", (start, end))}
        ex = c.execute("SELECT kind,category,COALESCE(SUM(amount),0) a FROM expenses WHERE exp_date BETWEEN ? AND ? GROUP BY kind,category", (start, end)).fetchall()
    rows = []; rev = ret = cost = rcost = 0.0
    for it in items:
        sq, sa = sold.get((it["id"], "مبيعات"), (0, 0)); rq, ra = sold.get((it["id"], "مرتجع مبيعات"), (0, 0))
        if not sq and not rq: continue
        b = buy.get(it["id"])
        avg = (b[1] / b[0]) if b and b[0] else float(it["buy_price"] or 0)
        net_cost = (sq - rq) * avg
        rows.append((it["name"], sq - rq, sa - ra, avg, net_cost, sa - ra - net_cost))
        rev += sa; ret += ra; cost += sq * avg; rcost += rq * avg
    ds = disc.get("مبيعات", 0.0); dr = disc.get("مرتجع مبيعات", 0.0)
    gross = rev - ret - (cost - rcost) - (ds - dr)
    general = sum(float(r["a"]) for r in ex if r["kind"] == "مصروف")
    salary = sum(float(r["a"]) for r in ex if r["kind"] == "مرتب")
    adv = sum(float(r["a"]) for r in ex if r["kind"] == "سلفة")
    by_cat = sorted(((r["category"], float(r["a"])) for r in ex if r["kind"] == "مصروف"), key=lambda x: -x[1])
    exp_total = general + salary + adv
    return {"rows": rows, "rev": rev, "ret": ret, "cost": cost, "rcost": rcost, "ds": ds, "dr": dr, "gross": gross,
            "general": general, "salary": salary, "adv": adv, "by_cat": by_cat, "exp_total": exp_total, "actual": gross - exp_total}

def metric_rows(ps):
    return [("المبيعات", ps["rev"]), ("المرتجعات", ps["ret"]), ("صافي التكلفة", ps["cost"] - ps["rcost"]),
            ("الخصومات (صافي)", ps["ds"] - ps["dr"]), ("إجمالي الربح (Total)", ps["gross"]),
            ("المصروفات العامة", ps["general"]), ("المرتبات", ps["salary"]), ("السلف", ps["adv"]),
            ("إجمالي المصروفات", ps["exp_total"]), ("الربح الفعلي بعد المصروفات", ps["actual"])]

# ---------------- التقرير اليومي ----------------
def daily_rows(day):
    ps = profit_summary(day, day)
    with db() as c:
        def inv(kind):
            r = c.execute(f"SELECT COUNT(*) n,COALESCE(SUM({NET_SQL}),0) t FROM invoices i WHERE i.kind=? AND i.inv_date=?", (kind, day)).fetchone()
            return r["n"], float(r["t"])
        def pay(kind):
            r = c.execute("SELECT COUNT(*) n,COALESCE(SUM(amount),0) t FROM payments WHERE kind=? AND pay_date=?", (kind, day)).fetchone()
            return r["n"], float(r["t"])
        data = {k: inv(k) for k in KINDS}
        col = pay("تحصيل"); pa = pay("دفع")
        exp = c.execute("SELECT kind,category,COALESCE(SUM(amount),0) a FROM expenses WHERE exp_date=? GROUP BY kind,category", (day,)).fetchall()
        moves = treasury_moves(c); opening = cash_opening(c)
    ob = opening + sum(m[5] - m[6] for m in moves if m[0] < day)
    cin = sum(m[5] for m in moves if m[0] == day); cout = sum(m[6] for m in moves if m[0] == day)
    R = []
    R.append(("h", "الفواتير", ""))
    for k in KINDS:
        n, t = data[k]; R.append(("r", f"{k} ({n} فاتورة)", fmt(t)))
    R.append(("h", "السندات", ""))
    R.append(("r", f"تحصيلات (من العملاء / رد نقدي من الموردين) ({col[0]} سند)", fmt(col[1])))
    R.append(("r", f"مدفوعات (للموردين / رد نقدي للعملاء) ({pa[0]} سند)", fmt(pa[1])))
    R.append(("h", "المصروفات", ""))
    if not exp: R.append(("r", "لا توجد مصروفات", fmt(0)))
    for r in exp:
        lab = {"مصروف": "مصروفات: " + (r["category"] or ""), "مرتب": "مرتبات", "سلفة": "سلف"}[r["kind"]]
        R.append(("r", lab, fmt(r["a"])))
    R.append(("b", "إجمالي المصروفات", fmt(ps["exp_total"])))
    R.append(("h", "الخزنة", ""))
    R.append(("r", "رصيد أول اليوم", fmt(ob)))
    R.append(("r", "وارد اليوم", fmt(cin)))
    R.append(("r", "صادر اليوم", fmt(cout)))
    R.append(("b", "رصيد آخر اليوم", fmt(ob + cin - cout)))
    R.append(("h", "الأرباح", ""))
    R.append(("r", "صافي المبيعات (بعد المرتجعات)", fmt(ps["rev"] - ps["ret"])))
    R.append(("r", "صافي التكلفة", fmt(ps["cost"] - ps["rcost"])))
    R.append(("b", "إجمالي الربح", fmt(ps["gross"])))
    R.append(("b", "الربح الفعلي بعد المصروفات", fmt(ps["actual"])))
    return R

# ---------------- النسخ الاحتياطي التلقائي ----------------
LOCAL_BACKUP_DIR = os.path.join(APP_DATA_DIR, "backups")

def backup_dir():
    try:
        with db() as c: d = c.execute("SELECT backup_dir FROM settings WHERE id=1").fetchone()["backup_dir"]
    except Exception: d = ""
    return d or LOCAL_BACKUP_DIR

def auto_backup_path(d=None):
    return os.path.join(d or backup_dir(), f"warehouse_auto_{date.today().isoformat()}.db")

def _backup_to(d):
    os.makedirs(d, exist_ok=True)
    target = auto_backup_path(d)
    src = raw_db(); dest = sqlite3.connect(target)
    try: src.backup(dest)
    finally: dest.close(); src.close()
    files = sorted(f for f in os.listdir(d) if f.startswith("warehouse_auto_") and f.endswith(".db"))
    for f in files[:-30]:
        try: os.remove(os.path.join(d, f))
        except Exception: pass
    return target

def auto_backup():
    """نسخة واحدة لكل يوم (تُحدّث عند كل غلق)، ويُحتفظ بآخر 30 يومًا.
    لو المجلد المختار (فلاشة مثلًا) مش متاح، النسخة تتحفظ على الجهاز. ترجع (المسار, رسالة تحذير أو None)."""
    d = backup_dir()
    try:
        return _backup_to(d), None
    except Exception as e:
        warn = f"تعذّر حفظ النسخة الاحتياطية في:\n{d}\n({e})"
        if os.path.normcase(os.path.abspath(d)) != os.path.normcase(os.path.abspath(LOCAL_BACKUP_DIR)):
            try:
                t = _backup_to(LOCAL_BACKUP_DIR)
                return t, warn + f"\n\nتم حفظها بدلًا من ذلك على الجهاز في:\n{LOCAL_BACKUP_DIR}\nتأكد من تركيب الفلاشة."
            except Exception as e2:
                warn += f"\n\nوفشل الحفظ على الجهاز أيضًا: {e2}"
        return None, warn

BG = "#f2f7fc"; PANEL = "#fafcfe"; NAVY = "#123b67"; NAVBAR = "#e1edf8"; STRIPE = "#e4f2fb"; ACCENT = "#1f6fd1"

# كل شاشة تابعة لأي زرار في الشريط العلوي (عشان يتلوّن بالأزرق)
SECTION = {
    "show_home": "الرئيسية",
    "show_invoice": "الفواتير", "show_invoices": "الفواتير",
    "show_items": "الأصناف والمخزون", "show_stock": "الأصناف والمخزون",
    "show_sample_items": "الأصناف والمخزون", "show_samples": "الأصناف والمخزون",
    "show_parties": "العملاء والموظفون", "show_employees": "العملاء والموظفون",
    "show_account": "الحسابات", "show_balances": "الحسابات", "show_cash": "الحسابات",
    "show_payments": "التقارير والسندات", "show_profit": "التقارير والسندات", "show_reps": "التقارير والسندات",
    "show_daily": "التقارير والسندات", "show_log": "التقارير والسندات",
    "show_settings": "الإعدادات",
}

class StripedTree(ttk.Treeview):
    """جدول بصفوف ملونة بالتناوب (أبيض / أزرق فاتح)، والأعمدة معروضة من اليمين للشمال.
    الصف المحدد يفضل أزرق غامق: لون التناوب يتشال منه وقت التحديد ويرجع بعده."""
    STRIPES = ("even", "odd")

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._n = 0; self._sel = set()
        self.tag_configure("even", background="white")
        self.tag_configure("odd", background=STRIPE)
        self.bindtags(self.bindtags() + ("StripedTree",))

    def insert(self, parent, index, iid=None, **kw):
        if parent == "":
            tags = kw.get("tags", ())
            if isinstance(tags, str): tags = (tags,)
            kw["tags"] = (self.STRIPES[self._n % 2],) + tuple(t for t in tags if t not in self.STRIPES)
            self._n += 1
        return super().insert(parent, index, iid=iid, **kw)

    def delete(self, *items):
        super().delete(*items)
        if not self.get_children(""): self._n = 0; self._sel = set()

    def _restripe_selection(self):
        cur = set(self.selection())
        for iid in self._sel - cur:
            if self.exists(iid):
                tags = tuple(self.item(iid, "tags") or ())
                stripe = self.STRIPES[self.index(iid) % 2]
                if stripe not in tags: self.item(iid, tags=(stripe,) + tags)
        for iid in cur - self._sel:
            tags = tuple(t for t in (self.item(iid, "tags") or ()) if t not in self.STRIPES)
            self.item(iid, tags=tags)
        self._sel = cur

def _on_striped_select(e):
    try: e.widget._restripe_selection()
    except Exception: pass

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.geometry("1280x800")
        self.minsize(1100, 680)
        self.configure(bg=BG)
        self.style = ttk.Style(self)
        try: self.style.theme_use("clam")
        except Exception: pass
        st = self.style
        st.configure(".", font=("Tahoma", 10))
        st.configure("TButton", padding=6, font=("Tahoma", 10), background="#f7fafd", bordercolor="#c5d5e6", lightcolor="#ffffff", darkcolor="#dfe8f1")
        st.map("TButton", background=[("active", "#e3eefa")])
        st.configure("Nav.TButton", padding=(14, 7), font=("Tahoma", 11), foreground="#1d3d5f", background="#ffffff", bordercolor="#c5d5e6", lightcolor="#ffffff", darkcolor="#e6eef6")
        st.map("Nav.TButton", background=[("active", "#e3eefa")])
        st.configure("NavActive.TButton", padding=(14, 7), font=("Tahoma", 11, "bold"), foreground="white", background=ACCENT, bordercolor="#1a5fb4", lightcolor=ACCENT, darkcolor="#1a5fb4")
        st.map("NavActive.TButton", background=[("active", "#2a7be0")], foreground=[("active", "white")])
        st.configure("TLabel", font=("Tahoma", 10), background=BG)
        st.configure("Treeview", font=("Tahoma", 10), rowheight=27, background="white", fieldbackground="white", bordercolor="#c9d8e8")
        st.configure("Treeview.Heading", font=("Tahoma", 10), background="#d5e6f6", foreground="#173b60", bordercolor="#b9cde2", lightcolor="#e6f0fa", darkcolor="#b9cde2")
        st.map("Treeview.Heading", background=[("active", "#c6dcf2")])
        st.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", "white")])
        self.bind_class("StripedTree", "<<TreeviewSelect>>", _on_striped_select)
        # خلفيات فاتحة للنماذج بدل الرمادي الافتراضي
        for cls in ("Frame", "Labelframe", "Label"): self.option_add(f"*{cls}.background", PANEL)
        self.option_add("*Labelframe.foreground", NAVY)
        self.option_add("*Labelframe.font", ("Tahoma", 10, "bold"))
        self.option_add("*Labelframe.relief", "groove")
        st.configure("TCombobox", fieldbackground="white", background="#f7fafd", bordercolor="#c5d5e6", arrowcolor="#3b5f86")
        st.map("TCombobox", fieldbackground=[("readonly", "white"), ("disabled", "#eef2f6")], foreground=[("disabled", "#8a98a8")])
        st.configure("TEntry", fieldbackground="white", bordercolor="#c5d5e6")
        self.current_lines = []
        self.invoice_kind = "مبيعات"
        self.edit_id = None
        self.last_statement = None
        self.item_edit_id = None
        self.party_edit_id = None
        self.emp_edit_id = None
        self.pay_edit = None
        self.active_section = None
        # تلوين زرار القسم تلقائيًا مع فتح أي شاشة
        for name, sec in SECTION.items():
            orig = getattr(self, name)
            def wrapper(*a, _orig=orig, _sec=sec, **k):
                self.set_active(_sec); return _orig(*a, **k)
            setattr(self, name, wrapper)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.build_shell()
        self.refresh_header()
        self.show_home()

    def on_close(self):
        _, warn = auto_backup()
        if warn: messagebox.showwarning("النسخة الاحتياطية", warn)
        self.destroy()

    def report_callback_exception(self, exc, val, tb):
        import traceback
        txt = "".join(traceback.format_exception(exc, val, tb))
        try:
            with open(os.path.join(APP_DATA_DIR, "error_log.txt"), "a", encoding="utf-8") as f: f.write(now_ts() + "\n" + txt + "\n")
        except Exception: pass
        messagebox.showerror("خطأ غير متوقع", f"{val}\n\nتفاصيل الخطأ محفوظة في:\n{os.path.join(APP_DATA_DIR, 'error_log.txt')}")

    def build_shell(self):
        top = tk.Frame(self, bg=NAVY)
        top.pack(fill="x")
        brand = tk.Frame(top, bg=NAVY); brand.pack(side="right", padx=22, pady=(8, 8))
        self.hdr_company = tk.Label(brand, text="", font=("Tahoma", 19, "bold"), fg="white", bg=NAVY)
        self.hdr_company.pack(anchor="e")
        self.hdr_tagline = tk.Label(brand, text="", font=("Tahoma", 11), fg="#cfe2fa", bg=NAVY)
        self.hdr_tagline.pack(anchor="e")
        tk.Label(top, text="يعمل بدون إنترنت • حفظ محلي تلقائي", font=("Tahoma", 9), fg="#bcd5f2", bg=NAVY).pack(side="left", padx=22)
        groups = [
            ("الرئيسية", self.show_home, None),
            ("الفواتير", None, [("فاتورة مبيعات", lambda: self.show_invoice("مبيعات")), ("فاتورة مشتريات", lambda: self.show_invoice("مشتريات")),
                                 ("مرتجع مبيعات", lambda: self.show_invoice("مرتجع مبيعات")), ("مرتجع مشتريات", lambda: self.show_invoice("مرتجع مشتريات")),
                                 None, ("سجل الفواتير", self.show_invoices)]),
            ("الأصناف والمخزون", None, [("الأصناف", self.show_items), ("أرصدة الأصناف", self.show_stock), None,
                                         ("أصناف العينات", self.show_sample_items), ("عينات مبيعات", lambda: self.show_samples("عينات مبيعات")),
                                         ("عينات مشتريات", lambda: self.show_samples("عينات مشتريات"))]),
            ("العملاء والموظفون", None, [("العملاء والموردون", self.show_parties), ("الموظفون (مرتب وسلف)", self.show_employees)]),
            ("الحسابات", None, [("كشف الحساب", self.show_account), ("أرصدة الحسابات", self.show_balances), ("الخزنة", self.show_cash)]),
            ("التقارير والسندات", None, [("السندات (تحصيل / دفع / مصروفات)", self.show_payments), None, ("الأرباح", self.show_profit),
                                          ("تقرير المناديب", self.show_reps), ("تقرير يومي", self.show_daily), ("سجل النشاط", self.show_log)]),
            ("الإعدادات", None, [("الإعدادات", self.show_settings), ("نسخة احتياطية", self.backup)]),
        ]
        navbar = tk.Frame(self, bg=NAVBAR); navbar.pack(fill="x")
        self.nav_menus = []; self.nav_buttons = {}
        for label, fn, items in groups:
            if items is None:
                btn = ttk.Button(navbar, text=label, command=fn, style="Nav.TButton")
            else:
                menu = tk.Menu(self, tearoff=0, font=("Tahoma", 11), bg="white", activebackground=ACCENT, activeforeground="white")
                for it in items:
                    if it is None: menu.add_separator()
                    else: menu.add_command(label=it[0], command=it[1])
                self.nav_menus.append(menu)
                btn = ttk.Button(navbar, text=label + "  ▾", style="Nav.TButton")
                btn.configure(command=lambda b=btn, m=menu: self.open_menu(b, m))
            btn.pack(side="right", padx=3, pady=6)
            self.nav_buttons[label] = btn
        self.status = tk.Label(self, text="جاهز — البيانات محفوظة على هذا الكمبيوتر", anchor="e", bg=NAVBAR, fg="#173b60", font=("Tahoma", 9), padx=10, pady=6)
        self.status.pack(fill="x", side="bottom")
        self.body = tk.Frame(self, bg=BG)
        self.body.pack(fill="both", expand=True, padx=15, pady=12)

    def set_active(self, section):
        self.active_section = section
        for label, btn in getattr(self, "nav_buttons", {}).items():
            try: btn.configure(style="NavActive.TButton" if label == section else "Nav.TButton")
            except Exception: pass

    def refresh_header(self):
        with db() as c: s = c.execute("SELECT company,tagline FROM settings WHERE id=1").fetchone()
        company = (s["company"] or "").strip() or DEFAULT_COMPANY
        tagline = (s["tagline"] or "").strip()
        self.hdr_company.config(text=company)
        self.hdr_tagline.config(text=tagline)
        if tagline: self.hdr_tagline.pack(anchor="e")
        else: self.hdr_tagline.pack_forget()
        self.title(company)

    def open_menu(self, btn, menu):
        x = btn.winfo_rootx(); y = btn.winfo_rooty() + btn.winfo_height()
        try: menu.tk_popup(x, y)
        finally: menu.grab_release()

    def clear(self):
        for w in self.body.winfo_children(): w.destroy()

    def title_label(self, text):
        tk.Label(self.body, text=text, font=("Tahoma", 16, "bold"), bg=BG, fg=NAVY).pack(anchor="e", pady=(0, 8))

    def field(self, parent, label, var, values=None, side="right", search=False):
        bgc = parent.cget("bg")
        col = tk.Frame(parent, bg=bgc); col.pack(side=side, expand=True, fill="x", padx=5)
        tk.Label(col, text=label + (" (اكتب للبحث)" if search else ""), anchor="e", bg=bgc).pack(fill="x")
        if values is not None:
            w = ttk.Combobox(col, textvariable=var, values=values, state="normal" if search else "readonly", justify="right")
        else:
            w = ttk.Entry(col, textvariable=var, justify="right")
        w.pack(fill="x")
        if search and values is not None:
            allv = list(values)
            top = w.winfo_toplevel()
            lb = tk.Listbox(top, font=("Tahoma", 10), activestyle="none", exportselection=False, selectbackground="#1f6fd1",
                            selectforeground="white", highlightthickness=1, highlightbackground="#1f6fd1", justify="right")
            def matches():
                t = var.get().strip().lower()
                return [v for v in allv if t in v.lower()] if t else allv
            def hide(e=None):
                try: lb.place_forget()
                except Exception: pass
            def show():
                m = matches()
                if not m or (len(m) == 1 and m[0] == var.get()): return hide()
                lb.delete(0, "end")
                for v in m[:60]: lb.insert("end", v)
                lb.configure(height=min(len(m), 8))
                x = w.winfo_rootx() - top.winfo_rootx(); y = w.winfo_rooty() - top.winfo_rooty() + w.winfo_height()
                lb.place(x=x, y=y, width=max(w.winfo_width(), 300)); lb.lift()
                lb.selection_clear(0, "end"); lb.selection_set(0); lb.activate(0)
            def choose(idx=None):
                sel = lb.curselection() if idx is None else (idx,)
                if sel:
                    var.set(lb.get(sel[0])); hide(); w.icursor("end"); w.event_generate("<<ComboboxSelected>>")
            def move(d):
                if not lb.winfo_ismapped(): return show()
                cur = lb.curselection(); i = (cur[0] if cur else -1) + d
                i = max(0, min(lb.size() - 1, i))
                lb.selection_clear(0, "end"); lb.selection_set(i); lb.activate(i); lb.see(i)
            def on_return(e):
                if lb.winfo_ismapped(): choose()
                else:
                    m = matches()
                    if var.get() not in allv and m:
                        var.set(m[0]); w.event_generate("<<ComboboxSelected>>")
                return "break"
            def on_focus_out(e):
                def later():
                    m = matches()
                    if var.get() not in allv and len(m) == 1:
                        var.set(m[0]); w.event_generate("<<ComboboxSelected>>")
                    hide()
                w.after(180, later)
            w.bind("<KeyRelease>", lambda e: None if e.keysym in ("Up", "Down", "Return", "Escape", "Tab", "Left", "Right", "Shift_L", "Shift_R", "Control_L", "Control_R") else show())
            w.bind("<Down>", lambda e: (move(1), "break")[1])
            w.bind("<Up>", lambda e: (move(-1), "break")[1])
            w.bind("<Return>", on_return)
            w.bind("<Escape>", lambda e: hide())
            w.bind("<FocusOut>", on_focus_out)
            w.bind("<<ComboboxSelected>>", lambda e: hide(), add="+")
            lb.bind("<Button-1>", lambda e: (choose(lb.nearest(e.y)), "break")[1])
            w.bind("<Destroy>", lambda e: lb.destroy() if e.widget is w else None, add="+")
        return w

    def tree(self, parent, columns, headings, widths=None, height=None):
        box = tk.Frame(parent); box.pack(fill="both", expand=True)
        t = StripedTree(box, columns=columns, show="headings", height=height or 6)
        for i, col in enumerate(columns):
            t.heading(col, text=headings[i], anchor="e")
            t.column(col, width=(widths[i] if widths else 130), anchor="e")
        # أول عمود (الكود / الاسم) يظهر على اليمين، والأرقام على الشمال
        t["displaycolumns"] = tuple(reversed(columns))
        y = ttk.Scrollbar(box, orient="vertical", command=t.yview); t.configure(yscrollcommand=y.set)
        t.pack(side="right", fill="both", expand=True); y.pack(side="left", fill="y")
        return t

    def total_bar(self, parent, pairs, title="الإجمالي"):
        """شريط الإجمالي تحت الجدول. pairs = [(العنوان, القيمة), ...]"""
        bar = tk.Frame(parent, bg="#3f7cc0"); bar.pack(fill="x", pady=(2, 4))
        tk.Label(bar, text=title, bg="#3f7cc0", fg="white", font=("Tahoma", 12, "bold"), padx=14, pady=6).pack(side="right")
        for label, val in pairs:
            f = tk.Frame(bar, bg="#3f7cc0"); f.pack(side="right", padx=16)
            tk.Label(f, text=label + ":", bg="#3f7cc0", fg="#dcebfb", font=("Tahoma", 10)).pack(side="right")
            tk.Label(f, text=val, bg="#3f7cc0", fg="white", font=("Tahoma", 11, "bold")).pack(side="right", padx=4)
        return bar

    def search_bar(self, label, var):
        sb = tk.Frame(self.body, bg=BG); sb.pack(fill="x", pady=(0, 6))
        ttk.Entry(sb, textvariable=var, justify="right").pack(side="right", fill="x", expand=True)
        tk.Label(sb, text=label, bg=BG).pack(side="right", padx=6)

    # ================= الرئيسية (لوحة اليوم) =================
    def show_home(self):
        self.clear(); self.title_label("الرئيسية — لوحة اليوم")
        today = date.today().isoformat(); since = (date.today() - timedelta(days=29)).isoformat()
        with db() as c:
            sales_today = c.execute(f"SELECT COALESCE(SUM({SIGNED_SALES_SQL}),0) FROM invoices i WHERE i.inv_date=?", (today,)).fetchone()[0]
            col_today = c.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE kind='تحصيل' AND pay_date=?", (today,)).fetchone()[0]
            exp_today = c.execute("SELECT COALESCE(SUM(amount),0) FROM expenses WHERE exp_date=?", (today,)).fetchone()[0]
            cash = cash_balance(c)
            daily = {r["d"]: float(r["t"]) for r in c.execute(f"SELECT i.inv_date d,SUM({SIGNED_SALES_SQL}) t FROM invoices i WHERE i.inv_date>=? GROUP BY i.inv_date", (since,))}
            top_items = c.execute("SELECT l.item_name n,SUM(l.qty) q,SUM(l.qty*l.price) a FROM invoice_lines l JOIN invoices i ON i.id=l.invoice_id WHERE i.kind='مبيعات' AND i.inv_date>=? GROUP BY l.item_id ORDER BY a DESC LIMIT 5", (since,)).fetchall()
            top_cust = c.execute(f"SELECT p.name n,SUM({NET_SQL}) t FROM invoices i JOIN parties p ON p.id=i.party_id WHERE i.kind='مبيعات' AND i.inv_date>=? GROUP BY p.id ORDER BY t DESC LIMIT 5", (since,)).fetchall()
            debts = []
            for p in c.execute("SELECT id,name FROM parties").fetchall():
                b = party_balance(c, p["id"])
                if b > 0.005: debts.append((p["name"], b))
            debts.sort(key=lambda x: -x[1])
            low = []
            for it in c.execute("SELECT id,name,min_stock FROM items WHERE COALESCE(min_stock,0)>0").fetchall():
                st = stock_of(c, it["id"])
                if st <= it["min_stock"]: low.append((it["name"], st, it["min_stock"]))
            low.sort(key=lambda x: x[1])
        ps = profit_summary(today, today)
        cards = tk.Frame(self.body, bg=BG); cards.pack(fill="x")
        for title, val, color in [("مبيعات اليوم (صافي)", sales_today, "#1762a5"), ("المحصّل نقدًا اليوم", col_today, "#1c7c4d"),
                                  ("مصروفات اليوم", exp_today, "#b45309"), ("الربح الفعلي اليوم", ps["actual"], "#6d28d9"), ("رصيد الخزنة", cash, NAVY)]:
            card = tk.Frame(cards, bg="white", highlightbackground="#cbd8e7", highlightthickness=1, padx=14, pady=8)
            card.pack(side="right", expand=True, fill="x", padx=5)
            tk.Label(card, text=title, bg="white", fg="#50647b", font=("Tahoma", 10)).pack()
            tk.Label(card, text=fmt(val), bg="white", fg=color, font=("Tahoma", 17, "bold")).pack(pady=2)
        mid = tk.Frame(self.body, bg=BG); mid.pack(fill="both", expand=True, pady=(10, 4))
        left = tk.Frame(mid, bg=BG); left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        right = tk.Frame(mid, bg=BG); right.pack(side="right", fill="both", expand=True, padx=(6, 0))
        tk.Label(right, text="مبيعات آخر 30 يوم (الصافي)", bg=BG, fg=NAVY, font=("Tahoma", 11, "bold")).pack(anchor="e")
        cv = tk.Canvas(right, height=150, bg="white", highlightthickness=1, highlightbackground="#cbd8e7"); cv.pack(fill="both", expand=True)
        days = [(date.today() - timedelta(days=29 - i)).isoformat() for i in range(30)]
        vals = [daily.get(d, 0.0) for d in days]
        def draw(e=None):
            cv.delete("all"); w = cv.winfo_width(); h = cv.winfo_height()
            if w < 60 or h < 60: return
            mx = max(max(vals), 1.0); bw = (w - 50) / 30.0; base = h - 20
            for i, v in enumerate(vals):
                x0 = 40 + i * bw + 1; x1 = x0 + bw - 2; y0 = base - (max(v, 0) / mx) * (h - 45)
                cv.create_rectangle(x0, y0, x1, base, fill="#1762a5", outline="")
            cv.create_line(40, base, w - 5, base, fill="#999")
            cv.create_text(38, 8, text=fmt(mx), anchor="ne", font=("Tahoma", 8), fill="#555")
            cv.create_text(40, h - 8, text=days[0], anchor="w", font=("Tahoma", 8), fill="#555")
            cv.create_text(w - 5, h - 8, text=days[-1], anchor="e", font=("Tahoma", 8), fill="#555")
        cv.bind("<Configure>", draw)
        tk.Label(left, text="أكثر 5 أصناف مبيعًا (آخر 30 يوم)", bg=BG, fg=NAVY, font=("Tahoma", 11, "bold")).pack(anchor="e")
        t1 = self.tree(left, ("n", "q", "a"), ("الصنف", "الكمية", "المبيعات"), [220, 90, 120], height=5)
        for r in top_items: t1.insert("", "end", values=(r["n"], fmt(r["q"]), fmt(r["a"])))
        bot = tk.Frame(self.body, bg=BG); bot.pack(fill="both", expand=True, pady=(4, 0))
        for title, cols, heads, widths, rows in [
            ("أكثر 5 عملاء شراءً (آخر 30 يوم)", ("n", "t"), ("العميل", "المشتريات"), [200, 110], [(r["n"], fmt(r["t"])) for r in top_cust]),
            ("أكبر 5 ديون على العملاء", ("n", "t"), ("العميل", "المستحق"), [200, 110], [(n, fmt(b)) for n, b in debts[:5]]),
            ("أصناف قربت تخلص", ("n", "s", "m"), ("الصنف", "الرصيد", "الحد الأدنى"), [170, 80, 90], [(n, fmt(s), fmt(m)) for n, s, m in low[:8]])]:
            f = tk.Frame(bot, bg=BG); f.pack(side="right", fill="both", expand=True, padx=5)
            tk.Label(f, text=title, bg=BG, fg=NAVY, font=("Tahoma", 11, "bold")).pack(anchor="e")
            t = self.tree(f, cols, heads, widths, height=5)
            for row in rows: t.insert("", "end", values=row)
        tk.Label(self.body, text="مهم: النسخة الاحتياطية التلقائية تُحفظ يوميًا — ومع ذلك انسخ مجلد النسخ على فلاشة أو قرص آخر من وقت لآخر.", fg="#9b2c2c", bg=BG, font=("Tahoma", 10, "bold")).pack(anchor="e", pady=(4, 0))

    # ================= الأصناف =================
    def show_items(self):
        self.clear(); self.title_label("إدارة الأصناف"); self.item_edit_id = None
        form = tk.LabelFrame(self.body, text="بيانات الصنف", padx=10, pady=8); form.pack(fill="x", pady=(0, 8))
        self.item_fields = [("code", "كود الصنف"), ("name", "اسم الصنف"), ("unit", "الوحدة"), ("buy", "سعر الشراء"), ("sell", "سعر البيع"), ("min", "حد أدنى للتنبيه")]
        self.item_vars = {k: tk.StringVar() for k, _ in self.item_fields}
        self.reset_item_form()
        for k, label in self.item_fields: self.field(form, label, self.item_vars[k])
        actions = tk.Frame(form); actions.pack(fill="x", pady=6)
        ttk.Button(actions, text="حفظ الصنف", command=self.save_item).pack(side="right", padx=4)
        ttk.Button(actions, text="تفريغ الحقول", command=self.reset_item_form).pack(side="right", padx=4)
        tk.Label(actions, text="ضغطتين على صنف = كل فواتيره", fg="#50647b").pack(side="left")
        self.item_q = tk.StringVar()
        self.search_bar("بحث سريع (الكود أو الاسم):", self.item_q)
        self.item_q.trace_add("write", lambda *a: self.refresh_items())
        self.items_tree = self.tree(self.body, ("id", "code", "name", "unit", "buy", "sell", "min", "stock"), ("ID", "الكود", "اسم الصنف", "الوحدة", "سعر الشراء", "سعر البيع", "حد أدنى", "الرصيد"), [45, 100, 260, 80, 110, 110, 90, 100])
        self.items_tree.tag_configure("low", foreground="#b91c1c")
        self.items_tree.bind("<Double-1>", lambda e: self.item_invoices_selected(self.items_tree))
        bar = tk.Frame(self.body, bg=BG); bar.pack(fill="x", pady=6)
        ttk.Button(bar, text="فواتير الصنف المحدد", command=lambda: self.item_invoices_selected(self.items_tree)).pack(side="right", padx=4)
        ttk.Button(bar, text="تعديل المحدد", command=self.edit_selected_item).pack(side="right", padx=4)
        ttk.Button(bar, text="حذف المحدد", command=self.delete_selected_item).pack(side="right", padx=4)
        self.refresh_items()

    def reset_item_form(self):
        self.item_edit_id = None
        for k, v in self.item_vars.items(): v.set("قطعة" if k == "unit" else "0" if k in ("buy", "sell", "min") else "")

    def save_item(self):
        v = {k: x.get().strip() for k, x in self.item_vars.items()}
        if not v["name"]: return messagebox.showwarning("تنبيه", "اسم الصنف مطلوب")
        try: buy = float(v["buy"] or 0); sell = float(v["sell"] or 0); mn = float(v["min"] or 0)
        except ValueError: return messagebox.showerror("خطأ", "راجع الأسعار والحد الأدنى؛ يجب أن تكون أرقامًا")
        try:
            with db() as c:
                if self.item_edit_id:
                    old = c.execute("SELECT * FROM items WHERE id=?", (self.item_edit_id,)).fetchone()
                    c.execute("UPDATE items SET code=?,name=?,unit=?,buy_price=?,sell_price=?,min_stock=? WHERE id=?", (v["code"] or None, v["name"], v["unit"] or "قطعة", buy, sell, mn, self.item_edit_id))
                    ch = []
                    if abs(float(old["buy_price"] or 0) - buy) > 1e-9: ch.append(f"سعر الشراء {fmt(old['buy_price'])}←{fmt(buy)}")
                    if abs(float(old["sell_price"] or 0) - sell) > 1e-9: ch.append(f"سعر البيع {fmt(old['sell_price'])}←{fmt(sell)}")
                    if old["name"] != v["name"]: ch.append(f"الاسم {old['name']}←{v['name']}")
                    log(c, "تعديل صنف", f"{v['name']}: " + ("، ".join(ch) or "بدون تغيير في الأسعار"))
                else:
                    c.execute("INSERT INTO items(code,name,unit,buy_price,sell_price,min_stock) VALUES(?,?,?,?,?,?)", (v["code"] or None, v["name"], v["unit"] or "قطعة", buy, sell, mn))
                    log(c, "إضافة صنف", f"{v['name']} (شراء {fmt(buy)} / بيع {fmt(sell)})")
            self.status.config(text="تم حفظ الصنف")
            self.reset_item_form(); self.refresh_items()
        except sqlite3.IntegrityError: messagebox.showerror("خطأ", "كود الصنف مستخدم بالفعل")

    def refresh_items(self):
        if not hasattr(self, "items_tree") or not self.items_tree.winfo_exists(): return
        for x in self.items_tree.get_children(): self.items_tree.delete(x)
        q = self.item_q.get().strip().lower() if hasattr(self, "item_q") else ""
        with db() as c:
            rows = c.execute("SELECT * FROM items ORDER BY name").fetchall()
            for r in rows:
                if q and q not in (r["name"] or "").lower() and q not in (r["code"] or "").lower(): continue
                st = stock_of(c, r["id"]); mn = float(r["min_stock"] or 0)
                self.items_tree.insert("", "end", iid=str(r["id"]), values=(r["id"], r["code"] or "", r["name"], r["unit"], fmt(r["buy_price"]), fmt(r["sell_price"]), fmt(mn), fmt(st)),
                                       tags=("low",) if mn > 0 and st <= mn else ())

    def edit_selected_item(self):
        sel = self.items_tree.selection()
        if not sel: return messagebox.showwarning("تنبيه", "حدد صنفًا أولًا")
        with db() as c: r = c.execute("SELECT * FROM items WHERE id=?", (int(sel[0]),)).fetchone()
        self.item_edit_id = r["id"]
        for k, val in (("code", r["code"] or ""), ("name", r["name"]), ("unit", r["unit"]), ("buy", r["buy_price"]), ("sell", r["sell_price"]), ("min", r["min_stock"] or 0)):
            self.item_vars[k].set(str(val))
        self.status.config(text=f"جاري تعديل الصنف «{r['name']}» — عدّل الحقول واضغط «حفظ الصنف»")

    def delete_selected_item(self):
        sel = self.items_tree.selection()
        if not sel: return messagebox.showwarning("تنبيه", "حدد صنفًا أولًا")
        iid = int(sel[0])
        with db() as c:
            used = c.execute("SELECT COUNT(*) FROM invoice_lines WHERE item_id=?", (iid,)).fetchone()[0]
            name = c.execute("SELECT name FROM items WHERE id=?", (iid,)).fetchone()["name"]
        if used: return messagebox.showwarning("لا يمكن الحذف", "الصنف مستخدم في فواتير. يمكنك تعديله فقط.")
        if messagebox.askyesno("تأكيد", f"حذف الصنف «{name}»؟"):
            with db() as c:
                c.execute("DELETE FROM items WHERE id=?", (iid,)); log(c, "حذف صنف", name)
            self.refresh_items()

    def item_invoices_selected(self, tree):
        sel = tree.selection()
        if not sel: return messagebox.showwarning("تنبيه", "حدد صنفًا أولًا")
        self.show_item_invoices(int(sel[0]))

    def show_item_invoices(self, item_id):
        with db() as c:
            it = c.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
            rows = c.execute("SELECT i.id,i.inv_date,i.created_at,i.number,i.kind,p.name party,l.qty,l.price,l.qty*l.price amt FROM invoice_lines l JOIN invoices i ON i.id=l.invoice_id LEFT JOIN parties p ON p.id=i.party_id WHERE l.item_id=? ORDER BY i.inv_date DESC,i.id DESC", (item_id,)).fetchall()
            st = stock_of(c, item_id)
        win = tk.Toplevel(self); win.title(f"فواتير الصنف: {it['name']}"); win.geometry("920x560"); win.configure(bg=BG); win.transient(self)
        tk.Label(win, text=f"فواتير الصنف: {it['name']}", font=("Tahoma", 15, "bold"), bg=BG, fg=NAVY).pack(anchor="e", padx=15, pady=(12, 2))
        buy = sum(r["qty"] for r in rows if r["kind"] == "مشتريات"); sell = sum(r["qty"] for r in rows if r["kind"] == "مبيعات")
        rs = sum(r["qty"] for r in rows if r["kind"] == "مرتجع مبيعات"); rp = sum(r["qty"] for r in rows if r["kind"] == "مرتجع مشتريات")
        tk.Label(win, text=f"مشتريات: {fmt(buy)}   مبيعات: {fmt(sell)}   مرتجع مبيعات: {fmt(rs)}   مرتجع مشتريات: {fmt(rp)}   الرصيد الحالي: {fmt(st)}", bg=BG, font=("Tahoma", 10, "bold")).pack(anchor="e", padx=15)
        tk.Label(win, text="ضغطتين على أي فاتورة تفتح مكوناتها", bg=BG, fg="#50647b", font=("Tahoma", 9)).pack(anchor="e", padx=15)
        box = tk.Frame(win, bg=BG); box.pack(fill="both", expand=True, padx=15, pady=8)
        t = self.tree(box, ("date", "time", "number", "kind", "party", "qty", "price", "amt"), ("التاريخ", "الوقت", "رقم الفاتورة", "النوع", "العميل / المورد", "الكمية", "السعر", "الإجمالي"), [95, 75, 105, 115, 210, 85, 95, 105])
        for n, r in enumerate(rows): t.insert("", "end", iid=f"{r['id']}_{n}", values=(r["inv_date"], fmt_time(r["created_at"]), r["number"], r["kind"], r["party"] or "", fmt(r["qty"]), fmt(r["price"]), fmt(r["amt"])))
        t.bind("<Double-1>", lambda e: (t.selection() and self.view_invoice(int(t.selection()[0].split("_")[0]))))
        ttk.Button(win, text="إغلاق", command=win.destroy).pack(anchor="e", padx=15, pady=8)

    # ================= العملاء والموردون =================
    def show_parties(self):
        self.clear(); self.title_label("العملاء والموردون"); self.party_edit_id = None
        form = tk.LabelFrame(self.body, text="بيانات عميل / مورد", padx=10, pady=8); form.pack(fill="x", pady=(0, 8))
        self.party_vars = {k: tk.StringVar() for k in ("name", "kind", "phone", "address", "opening")}
        self.party_vars["kind"].set("عميل"); self.party_vars["opening"].set("0")
        for k, label in [("name", "الاسم"), ("kind", "النوع"), ("phone", "الهاتف"), ("address", "العنوان"), ("opening", "الرصيد الافتتاحي")]:
            self.field(form, label, self.party_vars[k], ["عميل", "مورد", "عميل/مورد"] if k == "kind" else None)
        tk.Label(form, text="الرصيد الافتتاحي: موجب = على العميل ، سالب = للمورد", fg="#50647b").pack(anchor="e")
        ttk.Button(form, text="حفظ الاسم", command=self.save_party).pack(anchor="e", pady=6)
        self.party_q = tk.StringVar()
        self.search_bar("بحث سريع (الاسم أو الهاتف):", self.party_q)
        self.party_q.trace_add("write", lambda *a: self.refresh_parties())
        self.parties_tree = self.tree(self.body, ("id", "name", "kind", "phone", "address", "opening", "balance", "last_col", "last_pay"),
                                      ("ID", "الاسم", "النوع", "الهاتف", "العنوان", "الرصيد الافتتاحي", "الرصيد الحالي", "آخر تحصيل", "آخر دفع"), [40, 200, 80, 110, 160, 110, 110, 100, 100])
        self.parties_tree.bind("<Double-1>", lambda e: self.party_statement())
        self.party_note = tk.Label(self.body, text="", bg=BG, fg="#6b7280", font=("Tahoma", 9), anchor="e"); self.party_note.pack(fill="x")
        self.parties_tree.bind("<<TreeviewSelect>>", self.party_selected)
        bar = tk.Frame(self.body, bg=BG); bar.pack(fill="x", pady=6)
        ttk.Button(bar, text="كشف حساب المحدد (فواتير + سندات)", command=self.party_statement).pack(side="right", padx=4)
        ttk.Button(bar, text="سند جديد للمحدد", command=self.party_voucher).pack(side="right", padx=4)
        ttk.Button(bar, text="تعديل المحدد", command=self.edit_selected_party).pack(side="right", padx=4)
        ttk.Button(bar, text="حذف المحدد", command=self.delete_selected_party).pack(side="right", padx=4)
        self.refresh_parties()

    def party_selected(self, e=None):
        sel = self.parties_tree.selection()
        if not sel: return
        with db() as c: self.party_note.config(text=party_last_text(c, int(sel[0])))

    def selected_party_id(self):
        sel = self.parties_tree.selection()
        if not sel:
            messagebox.showwarning("تنبيه", "حدد عميلًا أو موردًا من القائمة أولًا"); return None
        return int(sel[0])

    def party_statement(self):
        pid = self.selected_party_id()
        if pid: self.show_account(pid)

    def party_voucher(self):
        pid = self.selected_party_id()
        if pid: self.show_payments(pid)

    def save_party(self):
        v = {k: x.get().strip() for k, x in self.party_vars.items()}
        if not v["name"]: return messagebox.showwarning("تنبيه", "الاسم مطلوب")
        try: opening = float(v["opening"] or 0)
        except ValueError: return messagebox.showerror("خطأ", "الرصيد الافتتاحي يجب أن يكون رقمًا")
        with db() as c:
            if self.party_edit_id:
                old = c.execute("SELECT * FROM parties WHERE id=?", (self.party_edit_id,)).fetchone()
                c.execute("UPDATE parties SET name=?,kind=?,phone=?,address=?,opening=? WHERE id=?", (v["name"], v["kind"], v["phone"], v["address"], opening, self.party_edit_id))
                extra = f" (الرصيد الافتتاحي {fmt(old['opening'])}←{fmt(opening)})" if abs(float(old["opening"] or 0) - opening) > 1e-9 else ""
                log(c, "تعديل عميل/مورد", v["name"] + extra)
            else:
                c.execute("INSERT INTO parties(name,kind,phone,address,opening) VALUES(?,?,?,?,?)", (v["name"], v["kind"], v["phone"], v["address"], opening))
                log(c, "إضافة عميل/مورد", f"{v['name']} (رصيد افتتاحي {fmt(opening)})")
        self.party_edit_id = None
        for k in ("name", "phone", "address"): self.party_vars[k].set("")
        self.party_vars["opening"].set("0"); self.party_vars["kind"].set("عميل")
        self.refresh_parties(); self.status.config(text="تم حفظ العميل / المورد")

    def refresh_parties(self):
        if not hasattr(self, "parties_tree") or not self.parties_tree.winfo_exists(): return
        for x in self.parties_tree.get_children(): self.parties_tree.delete(x)
        q = self.party_q.get().strip().lower() if hasattr(self, "party_q") else ""
        with db() as c:
            for r in c.execute("SELECT * FROM parties ORDER BY name").fetchall():
                if q and q not in (r["name"] or "").lower() and q not in (r["phone"] or "").lower(): continue
                bal = party_balance(c, r["id"])
                lc = c.execute("SELECT MAX(pay_date) FROM payments WHERE party_id=? AND kind='تحصيل'", (r["id"],)).fetchone()[0] or ""
                lp = c.execute("SELECT MAX(pay_date) FROM payments WHERE party_id=? AND kind='دفع'", (r["id"],)).fetchone()[0] or ""
                self.parties_tree.insert("", "end", iid=str(r["id"]), values=(r["id"], r["name"], r["kind"], r["phone"], r["address"], fmt(r["opening"]), fmt(bal), lc, lp))

    def edit_selected_party(self):
        pid = self.selected_party_id()
        if not pid: return
        with db() as c: r = c.execute("SELECT * FROM parties WHERE id=?", (pid,)).fetchone()
        self.party_edit_id = pid
        for k, val in (("name", r["name"]), ("kind", r["kind"]), ("phone", r["phone"]), ("address", r["address"]), ("opening", r["opening"])): self.party_vars[k].set(str(val))
        self.status.config(text=f"جاري تعديل «{r['name']}» — عدّل الحقول واضغط «حفظ الاسم»")

    def delete_selected_party(self):
        pid = self.selected_party_id()
        if not pid: return
        with db() as c:
            used = c.execute("SELECT (SELECT COUNT(*) FROM invoices WHERE party_id=?)+(SELECT COUNT(*) FROM payments WHERE party_id=?)", (pid, pid)).fetchone()[0]
            name = c.execute("SELECT name FROM parties WHERE id=?", (pid,)).fetchone()["name"]
        if used: return messagebox.showwarning("لا يمكن الحذف", "له فواتير أو سندات. يمكنك تعديل بياناته فقط.")
        if messagebox.askyesno("تأكيد", f"حذف «{name}»؟"):
            with db() as c:
                c.execute("DELETE FROM parties WHERE id=?", (pid,)); log(c, "حذف عميل/مورد", name)
            self.refresh_parties()

    # ================= الفواتير =================
    def show_invoice(self, kind, edit_id=None):
        self.clear(); self.invoice_kind = kind; self.current_lines = []; self.edit_id = edit_id
        self.title_label(("تعديل " if edit_id else "") + "فاتورة " + kind)
        with db() as c:
            parties = c.execute("SELECT id,name,address,phone FROM parties ORDER BY name").fetchall()
            items = c.execute("SELECT id,code,name,unit,buy_price,sell_price FROM items ORDER BY name").fetchall()
            old = lines = None; paid_old = 0.0
            if edit_id:
                old = c.execute("SELECT * FROM invoices WHERE id=?", (edit_id,)).fetchone()
                lines = c.execute("SELECT * FROM invoice_lines WHERE invoice_id=?", (edit_id,)).fetchall()
                paid_old = float(c.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE invoice_id=?", (edit_id,)).fetchone()[0])
            self.inv_rep_lookup = rep_lookup(c, old["rep_id"] if old else None) if kind == "مبيعات" else {}
        form = tk.LabelFrame(self.body, text="بيانات الفاتورة", padx=10, pady=8); form.pack(fill="x")
        self.inv_no = tk.StringVar(value=old["number"] if old else next_no(kind))
        self.inv_date = tk.StringVar(value=old["inv_date"] if old else date.today().isoformat())
        self.inv_party = tk.StringVar(); self.inv_notes = tk.StringVar(value=old["notes"] if old else "")
        self.inv_discount = tk.StringVar(value=str(old["discount"] or 0) if old else "0")
        self.inv_paid = tk.StringVar(value=str(paid_old) if old else "0")
        self.party_lookup = {party_label(p): p["id"] for p in parties}
        self.item_lookup = {item_label(p): dict(p) for p in items}
        if old:
            for k, v in self.party_lookup.items():
                if v == old["party_id"]: self.inv_party.set(k)
            self.current_lines = [{"item_id": l["item_id"], "name": l["item_name"], "unit": l["unit"], "qty": l["qty"], "price": l["price"]} for l in lines]
        self.field(form, "رقم الفاتورة", self.inv_no)
        self.field(form, "التاريخ YYYY-MM-DD", self.inv_date)
        self.field(form, "العميل / المورد", self.inv_party, list(self.party_lookup), search=True)
        self.inv_rep = tk.StringVar(value=OFFICE)
        if kind == "مبيعات":
            if old and old["rep_id"]:
                for k, v in self.inv_rep_lookup.items():
                    if v == old["rep_id"]: self.inv_rep.set(k)
            self.field(form, "المندوب", self.inv_rep, list(self.inv_rep_lookup))
        self.field(form, "ملاحظات", self.inv_notes)
        add = tk.LabelFrame(self.body, text="إضافة صنف للفاتورة", padx=10, pady=8); add.pack(fill="x", pady=8)
        self.inv_item = tk.StringVar(); self.inv_qty = tk.StringVar(value="1"); self.inv_price = tk.StringVar(value="0")
        cb = self.field(add, "الصنف", self.inv_item, list(self.item_lookup), search=True)
        def price_changed(_=None):
            item = self.item_lookup.get(self.inv_item.get())
            if item: self.inv_price.set(str(item["sell_price"] if kind in ("مبيعات", "مرتجع مبيعات") else item["buy_price"]))
        cb.bind("<<ComboboxSelected>>", price_changed)
        self.field(add, "الكمية", self.inv_qty); self.field(add, "سعر الوحدة", self.inv_price)
        ttk.Button(add, text="إضافة الصنف", command=self.add_invoice_line).pack(side="right", padx=10, pady=15)
        self.inv_tree = self.tree(self.body, ("name", "qty", "unit", "price", "total"), ("الصنف", "الكمية", "الوحدة", "سعر الوحدة", "الإجمالي"), [380, 120, 100, 150, 160])
        bottom = tk.Frame(self.body, bg=BG); bottom.pack(fill="x", pady=8)
        self.inv_total_label = tk.Label(bottom, text="", font=("Tahoma", 13, "bold"), fg=NAVY, bg=BG); self.inv_total_label.pack(side="right")
        for label, var in (("الخصم", self.inv_discount), (PAID_LABEL[kind], self.inv_paid)):
            f = tk.Frame(bottom, bg=BG); f.pack(side="right", padx=14)
            tk.Label(f, text=label, bg=BG).pack(side="right", padx=4)
            ttk.Entry(f, textvariable=var, width=11, justify="right").pack(side="right")
        ttk.Button(bottom, text="حذف آخر صنف", command=self.remove_invoice_line).pack(side="left", padx=4)
        ttk.Button(bottom, text="حفظ التعديل" if edit_id else "حفظ الفاتورة وطباعتها", command=self.save_invoice).pack(side="left", padx=4)
        if edit_id: ttk.Button(bottom, text="إلغاء", command=self.show_invoices).pack(side="left", padx=4)
        self.inv_discount.trace_add("write", lambda *a: self.refresh_invoice_lines())
        self.refresh_invoice_lines()

    def add_invoice_line(self):
        item = self.item_lookup.get(self.inv_item.get())
        if not item: return messagebox.showwarning("تنبيه", "اختر الصنف")
        try: qty = float(self.inv_qty.get()); price = float(self.inv_price.get())
        except ValueError: return messagebox.showerror("خطأ", "الكمية والسعر يجب أن يكونا أرقامًا")
        if qty <= 0 or price < 0: return messagebox.showerror("خطأ", "الكمية يجب أن تكون أكبر من صفر والسعر غير سالب")
        if SIGN[self.invoice_kind] < 0 and not self.edit_id:
            with db() as c: st = stock_of(c, item["id"])
            st -= sum(l["qty"] for l in self.current_lines if l["item_id"] == item["id"])
            if qty > st: return messagebox.showwarning("رصيد غير كافٍ", f"الرصيد المتاح من {item['name']} هو {fmt(st)}")
        self.current_lines.append({"item_id": item["id"], "name": item["name"], "unit": item["unit"], "qty": qty, "price": price})
        self.refresh_invoice_lines()

    def remove_invoice_line(self):
        if self.current_lines: self.current_lines.pop(); self.refresh_invoice_lines()

    def get_discount(self):
        try: return float(self.inv_discount.get() or 0)
        except ValueError: return 0.0

    def refresh_invoice_lines(self):
        if not hasattr(self, "inv_tree") or not self.inv_tree.winfo_exists(): return
        for x in self.inv_tree.get_children(): self.inv_tree.delete(x)
        total = 0
        for l in self.current_lines:
            amount = l["qty"] * l["price"]; total += amount
            self.inv_tree.insert("", "end", values=(l["name"], fmt(l["qty"]), l["unit"], fmt(l["price"]), fmt(amount)))
        self.inv_total_label.config(text=f"الإجمالي: {fmt(total)}   الصافي: {fmt(total - self.get_discount())} ج.م")

    def save_invoice(self):
        if not self.current_lines: return messagebox.showwarning("تنبيه", "أضف صنفًا واحدًا على الأقل")
        party = self.party_lookup.get(self.inv_party.get())
        if not party: return messagebox.showwarning("تنبيه", "اختر العميل أو المورد")
        total = sum(l["qty"] * l["price"] for l in self.current_lines)
        try: discount = float(self.inv_discount.get() or 0); paid = float(self.inv_paid.get() or 0)
        except ValueError: return messagebox.showerror("خطأ", "الخصم والمدفوع يجب أن يكونا أرقامًا")
        if discount < 0 or discount > total: return messagebox.showerror("خطأ", "الخصم يجب أن يكون بين صفر وإجمالي الفاتورة")
        net = total - discount
        if paid < 0 or paid > net + 0.005: return messagebox.showerror("خطأ", "المبلغ المدفوع يجب أن يكون بين صفر وصافي الفاتورة")
        kind = self.invoice_kind; edit_id = self.edit_id; number = self.inv_no.get().strip() or next_no(kind)
        try: inv_date = check_date(self.inv_date.get())
        except ValueError: return messagebox.showerror("خطأ", "صيغة التاريخ غير صحيحة (YYYY-MM-DD)")
        rep_id = self.inv_rep_lookup.get(self.inv_rep.get()) if kind == "مبيعات" else None
        try:
            with db() as c:
                old_items = []
                if edit_id:
                    old_items = [r[0] for r in c.execute("SELECT DISTINCT item_id FROM invoice_lines WHERE invoice_id=?", (edit_id,))]
                    old_total = c.execute(f"SELECT {NET_SQL} FROM invoices i WHERE i.id=?", (edit_id,)).fetchone()[0]
                    created = c.execute("SELECT created_at FROM invoices WHERE id=?", (edit_id,)).fetchone()[0]
                    c.execute("UPDATE invoices SET number=?,inv_date=?,party_id=?,notes=?,discount=?,rep_id=? WHERE id=?", (number, inv_date, party, self.inv_notes.get().strip(), discount, rep_id, edit_id))
                    c.execute("DELETE FROM invoice_lines WHERE invoice_id=?", (edit_id,))
                    c.execute("DELETE FROM payments WHERE invoice_id=?", (edit_id,))
                    inv_id = edit_id
                else:
                    created = now_ts()
                    cur = c.execute("INSERT INTO invoices(number,kind,inv_date,party_id,notes,discount,rep_id,created_at) VALUES(?,?,?,?,?,?,?,?)", (number, kind, inv_date, party, self.inv_notes.get().strip(), discount, rep_id, created))
                    inv_id = cur.lastrowid
                bump_counter(c, kind, number)
                for l in self.current_lines:
                    c.execute("INSERT INTO invoice_lines(invoice_id,item_id,item_name,unit,qty,price) VALUES(?,?,?,?,?,?)", (inv_id, l["item_id"], l["name"], l["unit"], l["qty"], l["price"]))
                if paid > 0:
                    c.execute("INSERT INTO payments(party_id,pay_date,kind,amount,notes,invoice_id,rep_id,created_at) VALUES(?,?,?,?,?,?,?,?)", (party, inv_date, PAID_KIND[kind], paid, f"دفعة مع الفاتورة رقم {number}", inv_id, rep_id, created))
                check_stock(c, set(old_items) | {l["item_id"] for l in self.current_lines})
                rep_txt = f" — المندوب: {rep_name_of(c, rep_id)}" if kind == "مبيعات" else ""
                if edit_id: log(c, "تعديل فاتورة", f"{kind} رقم {number}: الصافي {fmt(old_total)}←{fmt(net)}" + rep_txt)
                else: log(c, "إضافة فاتورة", f"{kind} رقم {number} بصافي {fmt(net)}" + (f" ومدفوع {fmt(paid)}" if paid else "") + rep_txt)
        except sqlite3.IntegrityError: return messagebox.showerror("خطأ", "رقم الفاتورة موجود بالفعل؛ غيّر رقم الفاتورة")
        except ValueError as e: return messagebox.showerror("خطأ", str(e))
        self.status.config(text=f"تم حفظ فاتورة {kind} رقم {number} في قاعدة البيانات")
        if edit_id:
            if messagebox.askyesno("تم التعديل", "تم حفظ التعديل. هل تريد طباعة الفاتورة؟"): self.print_invoice(inv_id)
            self.show_invoices()
        else:
            self.print_invoice(inv_id); self.show_invoice(kind)

    def invoice_html(self, inv_id):
        with db() as c:
            inv = c.execute("SELECT i.*,p.name party_name,p.phone party_phone,p.address party_address,p.opening party_opening FROM invoices i LEFT JOIN parties p ON p.id=i.party_id WHERE i.id=?", (inv_id,)).fetchone()
            lines = c.execute("SELECT * FROM invoice_lines WHERE invoice_id=?", (inv_id,)).fetchall()
            settings = c.execute("SELECT * FROM settings WHERE id=1").fetchone()
            moves = party_moves(c, inv["party_id"]) if inv["party_id"] else []
            paid = float(c.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE invoice_id=?", (inv_id,)).fetchone()[0])
        total = sum(x["qty"] * x["price"] for x in lines)
        discount = float(inv["discount"] or 0); net = total - discount
        prior = float(inv["party_opening"] or 0)
        for m in moves:
            if m[7] < (inv["inv_date"], 0, inv_id): prior += m[5] - m[6]
        paid_effect = -paid if PAID_KIND[inv["kind"]] == "تحصيل" else paid
        current = prior + (net if inv["kind"] in DEBIT_KINDS else -net) + paid_effect
        rows = "".join(f"<tr><td>{n}</td><td>{esc(l['item_name'])}</td><td>{fmt(l['qty'])}</td><td>{esc(l['unit'])}</td><td>{fmt(l['price'])}</td><td>{fmt(l['qty']*l['price'])}</td></tr>" for n, l in enumerate(lines, 1))
        company = esc(settings["company"]) or "اسم الشركة"
        paid_div = f"<div>{esc(PAID_LABEL[inv['kind']])}: {fmt(paid)} ج.م</div>" if paid > 0 else ""
        copy = f"""<section class="copy">
          <div class="head"><div class="brand"><h1>{company}</h1><div>{esc(settings['english'])}</div><div>{esc(settings['address'])}　 {esc(settings['phone'])}</div></div>
          <h2>فاتورة {esc(inv['kind'])}　{esc(inv['number'])}</h2></div>
          <div class="meta"><div>التاريخ: <b>{esc(inv['inv_date'])}</b>　{esc(fmt_time(inv['created_at']))}</div><div>اسم الحساب: <b>{esc(inv['party_name'])}</b></div><div>الهاتف: {esc(inv['party_phone'])}</div></div>
          <table><thead><tr><th>م</th><th>اسم الصنف</th><th>الكمية</th><th>الوحدة</th><th>السعر</th><th>الإجمالي</th></tr></thead><tbody>{rows}</tbody></table>
          <div class="sum"><div>الإجمالي: {fmt(total)} ج.م</div><div>الخصم: {fmt(discount)} ج.م</div><div>الصافي: {fmt(net)} ج.م</div>{paid_div}</div>
          <div class="balance"><div>الرصيد السابق: {fmt(prior)} ج.م</div><div>الرصيد الحالي: {fmt(current)} ج.م</div></div>
          <div class="notes">ملاحظات: {esc(inv['notes'])}</div>
          <div class="sign"><span>توقيع المستلم</span><span>توقيع البائع</span></div>
        </section>"""
        return f"""<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8"><title>فاتورة {esc(inv['number'])}</title><style>
        @page{{size:A4 landscape;margin:7mm}}
        *{{box-sizing:border-box}}
        body{{font-family:Tahoma,Arial,sans-serif;color:#111;margin:0;font-size:9px}}
        .sheet{{display:grid;grid-template-columns:1fr 1fr;gap:5mm;width:100%}}
        .copy{{border:1px solid #555;border-radius:8px;padding:5mm;min-height:185mm;position:relative;break-inside:avoid}}
        .head{{text-align:center;border:1px solid #333;border-radius:8px;padding:5px 3px;margin-bottom:6px}}
        h1{{font-size:15px;margin:1px 0 3px}}h2{{font-size:13px;margin:6px 0 1px}}
        .brand{{line-height:1.55}}.meta{{border:1px solid #555;border-radius:6px;padding:5px;display:grid;grid-template-columns:1fr 1fr;gap:4px;margin-bottom:6px;font-size:9px}}
        table{{width:100%;border-collapse:collapse;font-size:8.5px}}
        th,td{{border:1px solid #555;padding:5px 3px;text-align:center;overflow-wrap:anywhere}}
        th{{background:#eee}}.sum{{display:flex;flex-wrap:wrap;justify-content:space-between;gap:4px;border:1px solid #555;padding:6px 4px;margin-top:6px;font-weight:bold;font-size:9px}}
        .balance{{display:flex;justify-content:space-between;gap:4px;border:1px solid #555;padding:6px 4px;margin-top:5px;font-weight:bold}}
        .notes{{margin-top:6px;min-height:12px}}.sign{{position:absolute;bottom:7mm;left:5mm;right:5mm;display:flex;justify-content:space-between;border-top:1px solid #bbb;padding-top:5px}}
        @media screen{{body{{background:#e9eef4;padding:12px}}.sheet{{max-width:1100px;margin:auto}}.copy{{background:white;min-height:650px;box-shadow:0 2px 9px #0002}}}}
        </style><div class="sheet">{copy}{copy}</div></html>"""

    def print_invoice(self, inv_id):
        path = os.path.join(PRINT_DIR, f"invoice_{inv_id}.html")
        with open(path, "w", encoding="utf-8") as f: f.write(self.invoice_html(inv_id))
        try: os.startfile(path)
        except Exception:
            try: webbrowser.open("file:///" + path.replace("\\", "/"))
            except Exception: pass
        messagebox.showinfo("تم", "تم حفظ الفاتورة وفتحها للطباعة (Ctrl+P).\nلو لم تفتح، افتح هذا الملف يدويًا:\n" + path)

    def view_invoice(self, inv_id):
        with db() as c:
            inv = c.execute("SELECT i.*,p.name pname,p.phone pphone FROM invoices i LEFT JOIN parties p ON p.id=i.party_id WHERE i.id=?", (inv_id,)).fetchone()
            lines = c.execute("SELECT * FROM invoice_lines WHERE invoice_id=?", (inv_id,)).fetchall()
            paid = float(c.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE invoice_id=?", (inv_id,)).fetchone()[0])
            rep = rep_name_of(c, inv["rep_id"]) if inv and inv["kind"] == "مبيعات" else ""
        if not inv: return
        win = tk.Toplevel(self); win.title(f"فاتورة {inv['kind']} {inv['number']}"); win.geometry("840x560"); win.configure(bg=BG); win.transient(self)
        total = sum(l["qty"] * l["price"] for l in lines); discount = float(inv["discount"] or 0)
        tk.Label(win, text=f"فاتورة {inv['kind']}  رقم {inv['number']}", font=("Tahoma", 15, "bold"), bg=BG, fg=NAVY).pack(anchor="e", padx=15, pady=(12, 2))
        tk.Label(win, text=f"التاريخ: {inv['inv_date']}  {fmt_time(inv['created_at'])}      الاسم: {inv['pname'] or ''}      الهاتف: {inv['pphone'] or ''}" + (f"      المندوب: {rep}" if rep else ""), bg=BG, font=("Tahoma", 10)).pack(anchor="e", padx=15)
        if inv["notes"]: tk.Label(win, text="ملاحظات: " + inv["notes"], bg=BG, font=("Tahoma", 10)).pack(anchor="e", padx=15)
        box = tk.Frame(win, bg=BG); box.pack(fill="both", expand=True, padx=15, pady=10)
        t = self.tree(box, ("n", "name", "qty", "unit", "price", "total"), ("م", "الصنف", "الكمية", "الوحدة", "السعر", "الإجمالي"), [40, 300, 100, 90, 120, 130])
        for n, l in enumerate(lines, 1): t.insert("", "end", values=(n, l["item_name"], fmt(l["qty"]), l["unit"], fmt(l["price"]), fmt(l["qty"] * l["price"])))
        tk.Label(win, text=f"الإجمالي: {fmt(total)}     الخصم: {fmt(discount)}     الصافي: {fmt(total - discount)} ج.م" + (f"     المدفوع: {fmt(paid)}" if paid else ""), font=("Tahoma", 13, "bold"), bg=BG, fg=NAVY).pack(anchor="e", padx=15)
        bar = tk.Frame(win, bg=BG); bar.pack(fill="x", padx=15, pady=10)
        ttk.Button(bar, text="طباعة", command=lambda: self.print_invoice(inv_id)).pack(side="right")
        ttk.Button(bar, text="تعديل الفاتورة", command=lambda: (win.destroy(), self.show_invoice(inv["kind"], inv_id))).pack(side="right", padx=6)
        ttk.Button(bar, text="إغلاق", command=win.destroy).pack(side="right", padx=6)

    # ---------------- سجل الفواتير ----------------
    def show_invoices(self):
        self.clear(); self.title_label("سجل الفواتير")
        with db() as c:
            all_rows = c.execute(f"SELECT i.id,i.number,i.kind,i.inv_date,i.created_at,i.rep_id,p.name party,r.name rep,{NET_SQL} total "
                                 "FROM invoices i LEFT JOIN parties p ON p.id=i.party_id LEFT JOIN employees r ON r.id=i.rep_id ORDER BY i.id DESC").fetchall()
            reps = rep_lookup(c)
        flt = tk.Frame(self.body, bg=BG); flt.pack(fill="x", pady=(0, 6))
        q_var = tk.StringVar(); rep_var = tk.StringVar(value="الكل")
        self.field(flt, "بحث سريع (رقم الفاتورة / الاسم / التاريخ / النوع)", q_var)
        rep_values = ["الكل"] + list(reps)
        self.field(flt, "المندوب (فواتير المبيعات)", rep_var, rep_values).configure(width=28)
        tree = self.tree(self.body, ("id", "kind", "number", "date", "time", "party", "rep", "total"),
                         ("ID", "النوع", "رقم الفاتورة", "التاريخ", "الوقت", "العميل / المورد", "المندوب", "الصافي"), [45, 110, 110, 100, 80, 270, 130, 130])
        totals = tk.Frame(self.body, bg=BG); totals.pack(fill="x")
        def fill(*a):
            for x in tree.get_children(): tree.delete(x)
            for w in totals.winfo_children(): w.destroy()
            q = q_var.get().strip().lower(); rv = rep_var.get()
            n = 0; tot = 0.0
            for r in all_rows:
                hay = " ".join(str(r[k] or "") for k in ("number", "kind", "inv_date", "party", "rep")).lower()
                if q and q not in hay: continue
                if rv != "الكل":
                    if r["kind"] != "مبيعات" or reps.get(rv) != r["rep_id"]: continue
                rep = (r["rep"] or OFFICE) if r["kind"] == "مبيعات" else ""
                tree.insert("", "end", values=(r["id"], r["kind"], r["number"], r["inv_date"], fmt_time(r["created_at"]), r["party"] or "", rep, fmt(r["total"])))
                n += 1; tot += float(r["total"] or 0)
            if rv != "الكل": self.total_bar(totals, [("عدد الفواتير", str(n)), ("إجمالي المبيعات", fmt(tot))])
        q_var.trace_add("write", fill); rep_var.trace_add("write", fill); fill()
        tree.bind("<Double-1>", lambda e: self.view_selected(tree))
        bar = tk.Frame(self.body, bg=BG); bar.pack(fill="x", pady=8)
        ttk.Button(bar, text="عرض مكونات الفاتورة", command=lambda: self.view_selected(tree)).pack(side="right", padx=4)
        ttk.Button(bar, text="تعديل", command=lambda: self.edit_selected_invoice(tree)).pack(side="right", padx=4)
        ttk.Button(bar, text="طباعة", command=lambda: self.print_selected(tree)).pack(side="right", padx=4)
        ttk.Button(bar, text="حذف", command=lambda: self.delete_invoice(tree)).pack(side="right", padx=4)

    def selected_invoice(self, tree):
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("تنبيه", "حدد فاتورة أولًا"); return None
        v = tree.item(sel[0], "values"); return int(v[0]), v[1]

    def view_selected(self, tree):
        s = self.selected_invoice(tree)
        if s: self.view_invoice(s[0])

    def print_selected(self, tree):
        s = self.selected_invoice(tree)
        if s: self.print_invoice(s[0])

    def edit_selected_invoice(self, tree):
        s = self.selected_invoice(tree)
        if s: self.show_invoice(s[1], s[0])

    def delete_invoice(self, tree):
        s = self.selected_invoice(tree)
        if not s: return
        inv_id = s[0]
        if not messagebox.askyesno("تأكيد", "حذف الفاتورة نهائيًا؟ سيتغير رصيد المخزون وحساب العميل/المورد، وسيُحذف أي مبلغ مدفوع مسجّل معها."): return
        try:
            with db() as c:
                inv = c.execute("SELECT * FROM invoices WHERE id=?", (inv_id,)).fetchone()
                item_ids = [r[0] for r in c.execute("SELECT DISTINCT item_id FROM invoice_lines WHERE invoice_id=?", (inv_id,))]
                total = c.execute(f"SELECT {NET_SQL} FROM invoices i WHERE i.id=?", (inv_id,)).fetchone()[0]
                c.execute("DELETE FROM payments WHERE invoice_id=?", (inv_id,))
                c.execute("DELETE FROM invoices WHERE id=?", (inv_id,))
                check_stock(c, item_ids)
                log(c, "حذف فاتورة", f"{inv['kind']} رقم {inv['number']} بتاريخ {inv['inv_date']} وصافي {fmt(total)}")
        except ValueError as e:
            return messagebox.showerror("لا يمكن الحذف", str(e))
        self.show_invoices()

    # ================= السندات (تحصيل / دفع / مصروفات) =================
    def show_payments(self, pid=None):
        self.clear(); self.title_label("السندات: تحصيل من عميل / دفع لمورد / مصروفات"); self.pay_edit = None
        with db() as c:
            parties = c.execute("SELECT id,name,address,phone FROM parties ORDER BY name").fetchall()
            cats = [r["name"] for r in c.execute("SELECT name FROM expense_cats ORDER BY name")]
            self.pay_rep_lookup = rep_lookup(c)
        self.pay_lookup = {party_label(p): p["id"] for p in parties}
        self.pay_kinds = {"تحصيل من عميل": "تحصيل", "دفع لمورد": "دفع", "مصروفات": "مصروف"}
        self.pay_form = form = tk.LabelFrame(self.body, text="سند جديد", padx=10, pady=6); form.pack(fill="x", pady=(0, 6))
        self.pay_party = tk.StringVar(); self.pay_kind = tk.StringVar(value="تحصيل من عميل"); self.pay_cat = tk.StringVar()
        self.pay_date = tk.StringVar(value=date.today().isoformat()); self.pay_amount = tk.StringVar(); self.pay_notes = tk.StringVar()
        self.pay_rep = tk.StringVar(value=OFFICE)
        for k, v in self.pay_lookup.items():
            if v == pid: self.pay_party.set(k)
        frow = tk.Frame(form); frow.pack(fill="x")
        brow = tk.Frame(form); brow.pack(fill="x", pady=(6, 0))
        self.pay_save_btn = ttk.Button(brow, text="حفظ السند", command=self.save_payment); self.pay_save_btn.pack(side="right", padx=4)
        ttk.Button(brow, text="+ بند جديد (للمصروفات)", command=self.add_category).pack(side="right", padx=4)
        self.pay_cancel_btn = ttk.Button(brow, text="إلغاء التعديل", command=self.cancel_payment_edit)
        self.pay_kind_w = self.field(frow, "نوع السند", self.pay_kind, list(self.pay_kinds))
        self.pay_party_w = self.field(frow, "العميل / المورد", self.pay_party, list(self.pay_lookup), search=True)
        self.pay_rep_w = self.field(frow, "المندوب (للتحصيل)", self.pay_rep, list(self.pay_rep_lookup))
        self.pay_cat_w = self.field(frow, "البند (للمصروفات)", self.pay_cat, cats)
        frow2 = tk.Frame(form); frow2.pack(fill="x", before=brow, pady=(4, 0))
        self.field(frow2, "التاريخ YYYY-MM-DD", self.pay_date)
        self.field(frow2, "المبلغ", self.pay_amount)
        self.field(frow2, "ملاحظات", self.pay_notes)
        def toggle(*a):
            k = self.pay_kinds[self.pay_kind.get()]
            self.pay_party_w.config(state="disabled" if k == "مصروف" else "normal")
            self.pay_cat_w.config(state="readonly" if k == "مصروف" else "disabled")
            self.pay_rep_w.config(state="readonly" if k == "تحصيل" else "disabled")
        self.pay_kind.trace_add("write", toggle); toggle()
        flt = tk.LabelFrame(self.body, text="قائمة السندات", padx=8, pady=4); flt.pack(fill="x", pady=(0, 4))
        self.vf_type = tk.StringVar(value="الكل"); self.vf_q = tk.StringVar(); self.vf_rep = tk.StringVar(value="الكل")
        self.vf_from = tk.StringVar(value=date.today().replace(day=1).isoformat()); self.vf_to = tk.StringVar(value=date.today().isoformat())
        self.field(flt, "النوع", self.vf_type, ["الكل", "تحصيل من عميل", "دفع لمورد", "مصروفات", "مرتبات", "سلف"])
        self.field(flt, "المندوب (التحصيل)", self.vf_rep, ["الكل"] + list(self.pay_rep_lookup))
        self.field(flt, "من", self.vf_from); self.field(flt, "إلى", self.vf_to); self.field(flt, "بحث (الاسم / البند / ملاحظات)", self.vf_q)
        ttk.Button(flt, text="عرض", command=self.refresh_payments).pack(side="right", padx=6, pady=8)
        self.pay_tree = self.tree(self.body, ("date", "time", "type", "name", "rep", "amount", "notes"),
                                  ("التاريخ", "الوقت", "النوع", "الاسم / البند", "المندوب", "المبلغ", "ملاحظات"), [100, 75, 120, 260, 120, 120, 330])
        self.pay_tree.bind("<Double-1>", lambda e: self.edit_payment())
        self.pay_totals = tk.Frame(self.body, bg=BG); self.pay_totals.pack(fill="x")
        bar = tk.Frame(self.body, bg=BG); bar.pack(fill="x", pady=4)
        ttk.Button(bar, text="تعديل السند المحدد", command=self.edit_payment).pack(side="right", padx=4)
        ttk.Button(bar, text="حذف السند المحدد", command=self.delete_payment).pack(side="right", padx=4)
        ttk.Button(bar, text="ملخص البنود للفترة", command=self.voucher_summary).pack(side="right", padx=4)
        tk.Label(bar, text="ضغطتين على سند = تعديله", bg=BG, fg="#50647b", font=("Tahoma", 9)).pack(side="left")
        self.refresh_payments()

    def add_category(self):
        name = simpledialog.askstring("بند جديد", "اسم البند (مثال: صيانة، كهربا، شيال):", parent=self)
        if not name or not name.strip(): return
        name = name.strip()
        with db() as c:
            c.execute("INSERT OR IGNORE INTO expense_cats(name) VALUES(?)", (name,)); log(c, "إضافة بند مصروفات", name)
            cats = [r["name"] for r in c.execute("SELECT name FROM expense_cats ORDER BY name")]
        self.pay_cat_w["values"] = cats; self.pay_cat.set(name)

    def reset_payment_form(self):
        self.pay_edit = None
        self.pay_form.config(text="سند جديد"); self.pay_save_btn.config(text="حفظ السند")
        self.pay_cancel_btn.pack_forget()
        self.pay_kind_w.config(state="readonly"); self.pay_kind.set(self.pay_kind.get())
        self.pay_amount.set(""); self.pay_notes.set(""); self.pay_date.set(date.today().isoformat())

    def cancel_payment_edit(self):
        self.reset_payment_form(); self.status.config(text="تم إلغاء التعديل")

    def edit_payment(self):
        sel = self.pay_tree.selection()
        if not sel: return messagebox.showwarning("تنبيه", "حدد سندًا أولًا")
        typ, rid = sel[0].split("-"); rid = int(rid)
        with db() as c:
            if typ == "p":
                r = c.execute("SELECT * FROM payments WHERE id=?", (rid,)).fetchone()
                if not r: return
                if r["invoice_id"]: return messagebox.showwarning("سند مرتبط بفاتورة", "هذا السند جزء من فاتورة. عدّل المبلغ المدفوع من تعديل الفاتورة.")
                kind_label = "تحصيل من عميل" if r["kind"] == "تحصيل" else "دفع لمورد"
                party = next((k for k, v in self.pay_lookup.items() if v == r["party_id"]), "")
                rep = OFFICE
                if r["rep_id"]:
                    if r["rep_id"] not in self.pay_rep_lookup.values():
                        self.pay_rep_lookup.update(rep_lookup(c, r["rep_id"])); self.pay_rep_w["values"] = list(self.pay_rep_lookup)
                    rep = next((k for k, v in self.pay_rep_lookup.items() if v == r["rep_id"]), OFFICE)
                vals = (r["pay_date"], r["amount"], r["notes"] or "")
            else:
                r = c.execute("SELECT * FROM expenses WHERE id=?", (rid,)).fetchone()
                if not r: return
                if r["kind"] != "مصروف": return messagebox.showwarning("تنبيه", "المرتبات والسلف لا تُعدّل من هنا. احذف السند وسجّله من جديد من شاشة الموظفين.")
                kind_label = "مصروفات"; party = ""; rep = OFFICE
                vals = (r["exp_date"], r["amount"], r["notes"] or "")
                self.pay_cat.set(r["category"] or "")
        self.pay_kind_w.config(state="readonly"); self.pay_kind.set(kind_label)
        self.pay_party.set(party); self.pay_rep.set(rep)
        self.pay_date.set(vals[0]); self.pay_amount.set(str(vals[1])); self.pay_notes.set(vals[2])
        self.pay_kind_w.config(state="disabled")
        self.pay_edit = (typ, rid)
        self.pay_form.config(text=f"تعديل سند رقم {rid}"); self.pay_save_btn.config(text="حفظ التعديل")
        self.pay_cancel_btn.pack(side="right", padx=4)
        self.status.config(text=f"جاري تعديل السند رقم {rid} — عدّل الحقول واضغط «حفظ التعديل»")

    def save_payment(self):
        kind = self.pay_kinds[self.pay_kind.get()]
        try: amount = float(self.pay_amount.get())
        except ValueError: return messagebox.showerror("خطأ", "المبلغ يجب أن يكون رقمًا")
        if amount <= 0: return messagebox.showerror("خطأ", "المبلغ يجب أن يكون أكبر من صفر")
        try: d = check_date(self.pay_date.get())
        except ValueError: return messagebox.showerror("خطأ", "صيغة التاريخ غير صحيحة (YYYY-MM-DD)")
        notes = self.pay_notes.get().strip(); edit = self.pay_edit
        if kind == "مصروف":
            cat = self.pay_cat.get().strip()
            if not cat: return messagebox.showwarning("تنبيه", "اختر البند (أو أضف بندًا جديدًا)")
            with db() as c:
                if edit:
                    old = c.execute("SELECT * FROM expenses WHERE id=?", (edit[1],)).fetchone()
                    c.execute("UPDATE expenses SET exp_date=?,category=?,amount=?,notes=? WHERE id=?", (d, cat, amount, notes, edit[1]))
                    log(c, "تعديل مصروف", f"رقم {edit[1]}: {old['category']} {fmt(old['amount'])} بتاريخ {old['exp_date']} ← {cat} {fmt(amount)} بتاريخ {d}")
                else:
                    c.execute("INSERT INTO expenses(exp_date,kind,category,amount,notes,created_at) VALUES(?,?,?,?,?,?)", (d, "مصروف", cat, amount, notes, now_ts()))
                    log(c, "مصروف", f"{cat}: {fmt(amount)} بتاريخ {d}")
        else:
            pid = self.pay_lookup.get(self.pay_party.get())
            if not pid: return messagebox.showwarning("تنبيه", "اختر الاسم")
            rep_id = self.pay_rep_lookup.get(self.pay_rep.get()) if kind == "تحصيل" else None
            with db() as c:
                rep_txt = f" — المندوب: {rep_name_of(c, rep_id)}" if kind == "تحصيل" else ""
                if edit:
                    old = c.execute("SELECT p.*,pt.name pname FROM payments p JOIN parties pt ON pt.id=p.party_id WHERE p.id=?", (edit[1],)).fetchone()
                    c.execute("UPDATE payments SET party_id=?,pay_date=?,amount=?,notes=?,rep_id=? WHERE id=?", (pid, d, amount, notes, rep_id, edit[1]))
                    log(c, "تعديل سند", f"سند رقم {edit[1]}: {old['pname']} {fmt(old['amount'])} بتاريخ {old['pay_date']} ← {self.pay_party.get()} {fmt(amount)} بتاريخ {d}" + rep_txt)
                else:
                    c.execute("INSERT INTO payments(party_id,pay_date,kind,amount,notes,rep_id,created_at) VALUES(?,?,?,?,?,?,?)", (pid, d, kind, amount, notes, rep_id, now_ts()))
                    log(c, "سند " + ("تحصيل" if kind == "تحصيل" else "دفع"), f"{self.pay_party.get()}: {fmt(amount)} بتاريخ {d}" + rep_txt)
        self.reset_payment_form()
        self.status.config(text="تم حفظ التعديل" if edit else "تم حفظ السند"); self.refresh_payments()

    def refresh_payments(self):
        for x in self.pay_tree.get_children(): self.pay_tree.delete(x)
        try: s = check_date(self.vf_from.get()); e = check_date(self.vf_to.get())
        except ValueError: return messagebox.showerror("خطأ", "صيغة التاريخ غير صحيحة (YYYY-MM-DD)")
        rows = []
        with db() as c:
            for r in c.execute("SELECT p.*,pt.name pname,m.name rname FROM payments p JOIN parties pt ON pt.id=p.party_id LEFT JOIN employees m ON m.id=p.rep_id WHERE p.pay_date BETWEEN ? AND ?", (s, e)):
                col = r["kind"] == "تحصيل"
                rows.append((r["pay_date"], f"p-{r['id']}", "تحصيل من عميل" if col else "دفع لمورد", r["pname"], float(r["amount"]), r["notes"] or "",
                             r["created_at"], (r["rname"] or OFFICE) if col else "", r["rep_id"]))
            for r in c.execute("SELECT e.*,m.name ename FROM expenses e LEFT JOIN employees m ON m.id=e.employee_id WHERE e.exp_date BETWEEN ? AND ?", (s, e)):
                typ = {"مصروف": "مصروفات", "مرتب": "مرتبات", "سلفة": "سلف"}[r["kind"]]
                name = r["category"] if r["kind"] == "مصروف" else (r["ename"] or "")
                rows.append((r["exp_date"], f"e-{r['id']}", typ, name, float(r["amount"]), r["notes"] or "", r["created_at"], "", None))
        t = self.vf_type.get(); q = self.vf_q.get().strip().lower(); rv = self.vf_rep.get()
        rows = [r for r in rows if (t == "الكل" or r[2] == t) and (not q or q in (r[3] + " " + r[5]).lower())]
        if rv != "الكل":
            rid = self.pay_rep_lookup.get(rv)
            rows = [r for r in rows if r[2] == "تحصيل من عميل" and r[8] == rid]
        rows.sort(key=lambda r: (r[0], r[6] or "", r[1]), reverse=True)
        self.vouchers_rows = rows
        for r in rows: self.pay_tree.insert("", "end", iid=r[1], values=(r[0], fmt_time(r[6]), r[2], r[3], r[7], fmt(r[4]), r[5]))
        for w in self.pay_totals.winfo_children(): w.destroy()
        inn = sum(r[4] for r in rows if r[2] == "تحصيل من عميل")
        out = sum(r[4] for r in rows if r[2] == "دفع لمورد")
        exp = sum(r[4] for r in rows if r[2] in ("مصروفات", "مرتبات", "سلف"))
        self.total_bar(self.pay_totals, [("عدد السندات", str(len(rows))), ("التحصيلات", fmt(inn)), ("المدفوعات", fmt(out)), ("المصروفات والمرتبات والسلف", fmt(exp))])

    def voucher_summary(self):
        rows = getattr(self, "vouchers_rows", [])
        agg = {}
        for r in rows: agg[(r[2], r[3])] = agg.get((r[2], r[3]), 0) + r[4]
        win = tk.Toplevel(self); win.title("ملخص البنود"); win.geometry("560x480"); win.configure(bg=BG); win.transient(self)
        tk.Label(win, text=f"ملخص السندات من {self.vf_from.get()} إلى {self.vf_to.get()}", font=("Tahoma", 13, "bold"), bg=BG, fg=NAVY).pack(anchor="e", padx=15, pady=10)
        box = tk.Frame(win, bg=BG); box.pack(fill="both", expand=True, padx=15)
        t = self.tree(box, ("type", "name", "total"), ("النوع", "الاسم / البند", "الإجمالي"), [140, 220, 140])
        for (typ, name), v in sorted(agg.items(), key=lambda x: (x[0][0], -x[1])): t.insert("", "end", values=(typ, name, fmt(v)))
        ttk.Button(win, text="إغلاق", command=win.destroy).pack(anchor="e", padx=15, pady=10)

    def delete_payment(self):
        sel = self.pay_tree.selection()
        if not sel: return messagebox.showwarning("تنبيه", "حدد سندًا أولًا")
        key = sel[0]; typ, rid = key.split("-"); rid = int(rid)
        with db() as c:
            if typ == "p":
                p = c.execute("SELECT * FROM payments WHERE id=?", (rid,)).fetchone()
                if p and p["invoice_id"]: return messagebox.showwarning("سند مرتبط بفاتورة", "هذا السند جزء من فاتورة. عدّل المبلغ المدفوع من تعديل الفاتورة.")
        if not messagebox.askyesno("تأكيد", "حذف السند المحدد نهائيًا؟"): return
        with db() as c:
            if typ == "p": c.execute("DELETE FROM payments WHERE id=?", (rid,)); log(c, "حذف سند", f"سند رقم {rid}")
            else: c.execute("DELETE FROM expenses WHERE id=?", (rid,)); log(c, "حذف مصروف/مرتب/سلفة", f"رقم {rid}")
        if self.pay_edit == (typ, rid): self.reset_payment_form()
        self.refresh_payments()

    # ================= الموظفون =================
    def show_employees(self):
        self.clear(); self.title_label("الموظفون (مرتب وسلف)"); self.emp_edit_id = None
        form = tk.LabelFrame(self.body, text="بيانات موظف", padx=10, pady=8); form.pack(fill="x", pady=(0, 8))
        self.emp_vars = {k: tk.StringVar() for k in ("name", "kind", "job", "phone", "salary")}
        self.emp_vars["salary"].set("0"); self.emp_vars["kind"].set("موظف")
        for k, label in [("name", "الاسم"), ("kind", "النوع"), ("job", "الصفة (سواق، محاسب، شيال...)"), ("phone", "الهاتف"), ("salary", "المرتب الشهري")]:
            self.field(form, label, self.emp_vars[k], list(EMP_KINDS) if k == "kind" else None)
        ttk.Button(form, text="حفظ", command=self.save_employee).pack(side="right", padx=8, pady=14)
        flt = tk.Frame(self.body, bg=BG); flt.pack(fill="x", pady=(0, 6))
        self.emp_filter = tk.StringVar(value="الكل")
        tk.Label(flt, text="عرض:", bg=BG).pack(side="right", padx=4)
        cb = ttk.Combobox(flt, textvariable=self.emp_filter, values=["الكل"] + list(EMP_KINDS), state="readonly", width=12, justify="right"); cb.pack(side="right")
        self.emp_filter.trace_add("write", lambda *a: self.refresh_employees())
        self.emp_tree = self.tree(self.body, ("id", "name", "kind", "job", "phone", "salary", "adv"), ("ID", "الاسم", "النوع", "الصفة", "الهاتف", "المرتب", "رصيد السلف"), [45, 230, 90, 150, 130, 120, 130])
        self.emp_tree.bind("<Double-1>", lambda e: self.employee_statement())
        self.emp_totals = tk.Frame(self.body, bg=BG); self.emp_totals.pack(fill="x")
        bar = tk.Frame(self.body, bg=BG); bar.pack(fill="x", pady=8)
        for text, fn in [("صرف مرتب", self.pay_salary), ("صرف سلفة", self.pay_advance), ("كشف الموظف", self.employee_statement), ("تعديل المحدد", self.edit_employee), ("حذف المحدد", self.delete_employee)]:
            ttk.Button(bar, text=text, command=fn).pack(side="right", padx=4)
        tk.Label(bar, text="ضغطتين على موظف = كشفه", bg=BG, fg="#50647b", font=("Tahoma", 9)).pack(side="left")
        self.refresh_employees()

    def emp_advance(self, c, eid):
        r = c.execute("SELECT COALESCE(SUM(CASE WHEN kind='سلفة' THEN amount ELSE 0 END),0)-COALESCE(SUM(CASE WHEN kind='مرتب' THEN deducted ELSE 0 END),0) FROM expenses WHERE employee_id=?", (eid,)).fetchone()
        return float(r[0])

    def refresh_employees(self):
        for x in self.emp_tree.get_children(): self.emp_tree.delete(x)
        f = self.emp_filter.get() if hasattr(self, "emp_filter") else "الكل"
        n = sal = adv = 0.0
        with db() as c:
            for r in c.execute("SELECT * FROM employees ORDER BY name").fetchall():
                if f != "الكل" and (r["kind"] or "موظف") != f: continue
                a = self.emp_advance(c, r["id"]); n += 1; sal += float(r["salary"] or 0); adv += a
                self.emp_tree.insert("", "end", iid=str(r["id"]), values=(r["id"], r["name"], r["kind"] or "موظف", r["job"] or "", r["phone"], fmt(r["salary"]), fmt(a)))
        for w in self.emp_totals.winfo_children(): w.destroy()
        self.total_bar(self.emp_totals, [("العدد", str(int(n))), ("إجمالي المرتبات الشهرية", fmt(sal)), ("إجمالي رصيد السلف", fmt(adv))])

    def save_employee(self):
        v = {k: x.get().strip() for k, x in self.emp_vars.items()}
        if not v["name"]: return messagebox.showwarning("تنبيه", "الاسم مطلوب")
        if v["kind"] not in EMP_KINDS: return messagebox.showwarning("تنبيه", "اختر النوع: موظف / عامل / مندوب")
        try: sal = float(v["salary"] or 0)
        except ValueError: return messagebox.showerror("خطأ", "المرتب يجب أن يكون رقمًا")
        with db() as c:
            if self.emp_edit_id:
                c.execute("UPDATE employees SET name=?,kind=?,job=?,phone=?,salary=? WHERE id=?", (v["name"], v["kind"], v["job"], v["phone"], sal, self.emp_edit_id))
                log(c, "تعديل موظف", f"{v['name']} ({v['kind']}{' - ' + v['job'] if v['job'] else ''}، مرتب {fmt(sal)})")
            else:
                c.execute("INSERT INTO employees(name,kind,job,phone,salary) VALUES(?,?,?,?,?)", (v["name"], v["kind"], v["job"], v["phone"], sal))
                log(c, "إضافة موظف", f"{v['name']} ({v['kind']}{' - ' + v['job'] if v['job'] else ''}، مرتب {fmt(sal)})")
        self.emp_edit_id = None
        for k in ("name", "job", "phone"): self.emp_vars[k].set("")
        self.emp_vars["salary"].set("0"); self.emp_vars["kind"].set("موظف"); self.refresh_employees()
        self.status.config(text="تم حفظ بيانات الموظف")

    def selected_emp(self):
        sel = self.emp_tree.selection()
        if not sel:
            messagebox.showwarning("تنبيه", "حدد موظفًا أولًا"); return None
        return int(sel[0])

    def edit_employee(self):
        eid = self.selected_emp()
        if not eid: return
        with db() as c: r = c.execute("SELECT * FROM employees WHERE id=?", (eid,)).fetchone()
        self.emp_edit_id = eid
        for k in ("name", "job", "phone", "salary"): self.emp_vars[k].set(str(r[k] or ("0" if k == "salary" else "")))
        self.emp_vars["kind"].set(r["kind"] if r["kind"] in EMP_KINDS else "موظف")
        self.status.config(text=f"جاري تعديل «{r['name']}» — عدّل الحقول واضغط «حفظ»")

    def delete_employee(self):
        eid = self.selected_emp()
        if not eid: return
        with db() as c:
            used = c.execute("SELECT (SELECT COUNT(*) FROM expenses WHERE employee_id=?)+(SELECT COUNT(*) FROM invoices WHERE rep_id=?)+(SELECT COUNT(*) FROM payments WHERE rep_id=?)", (eid, eid, eid)).fetchone()[0]
            name = c.execute("SELECT name FROM employees WHERE id=?", (eid,)).fetchone()["name"]
        if used: return messagebox.showwarning("لا يمكن الحذف", "له مرتبات أو سلف، أو مسجّل كمندوب على فواتير أو سندات. يمكنك تعديل بياناته فقط.")
        if messagebox.askyesno("تأكيد", f"حذف «{name}»؟"):
            with db() as c: c.execute("DELETE FROM employees WHERE id=?", (eid,)); log(c, "حذف موظف", name)
            self.refresh_employees()

    def small_form(self, title, fields, on_save, height=330):
        win = tk.Toplevel(self); win.title(title); win.geometry(f"430x{height}"); win.configure(bg=BG); win.transient(self); win.grab_set()
        tk.Label(win, text=title, font=("Tahoma", 14, "bold"), bg=BG, fg=NAVY).pack(anchor="e", padx=15, pady=10)
        vars_ = {}
        for key, label, default in fields:
            vars_[key] = tk.StringVar(value=default)
            tk.Label(win, text=label, bg=BG, anchor="e").pack(fill="x", padx=15)
            ttk.Entry(win, textvariable=vars_[key], justify="right").pack(fill="x", padx=15, pady=(0, 6))
        bar = tk.Frame(win, bg=BG); bar.pack(fill="x", padx=15, pady=8)
        ttk.Button(bar, text="حفظ", command=lambda: on_save(win, vars_)).pack(side="right")
        ttk.Button(bar, text="إلغاء", command=win.destroy).pack(side="right", padx=6)
        return win, vars_

    def pay_salary(self):
        eid = self.selected_emp()
        if not eid: return
        with db() as c: e = c.execute("SELECT * FROM employees WHERE id=?", (eid,)).fetchone(); adv = self.emp_advance(c, eid)
        sal = float(e["salary"] or 0)
        def save(win, v):
            try: s = float(v["sal"].get()); d = float(v["ded"].get() or 0); dt = check_date(v["date"].get())
            except ValueError: return messagebox.showerror("خطأ", "راجع التاريخ والأرقام", parent=win)
            if s <= 0 or d < 0 or d > s + 1e-9: return messagebox.showerror("خطأ", "الخصم من السلفة يجب أن يكون بين صفر والمرتب", parent=win)
            if d > adv + 1e-9: return messagebox.showerror("خطأ", f"رصيد السلفة الحالي {fmt(adv)} فقط", parent=win)
            with db() as c:
                c.execute("INSERT INTO expenses(exp_date,kind,category,amount,notes,employee_id,deducted,created_at) VALUES(?,?,?,?,?,?,?,?)", (dt, "مرتب", "مرتبات", s - d, f"مرتب شهر {v['month'].get()}", eid, d, now_ts()))
                log(c, "صرف مرتب", f"{e['name']}: المرتب {fmt(s)} - خصم سلفة {fmt(d)} = مدفوع {fmt(s - d)}")
            win.destroy(); self.refresh_employees(); self.status.config(text="تم صرف المرتب")
        win, v = self.small_form(f"صرف مرتب: {e['name']} (رصيد السلف {fmt(adv)})",
                                 [("date", "التاريخ", date.today().isoformat()), ("month", "عن شهر", date.today().strftime("%Y-%m")), ("sal", "المرتب", str(sal)), ("ded", "المخصوم من السلفة", str(min(adv, sal)))], save, 380)

    def pay_advance(self):
        eid = self.selected_emp()
        if not eid: return
        with db() as c: e = c.execute("SELECT * FROM employees WHERE id=?", (eid,)).fetchone()
        def save(win, v):
            try: a = float(v["amt"].get()); dt = check_date(v["date"].get())
            except ValueError: return messagebox.showerror("خطأ", "راجع التاريخ والمبلغ", parent=win)
            if a <= 0: return messagebox.showerror("خطأ", "المبلغ يجب أن يكون أكبر من صفر", parent=win)
            with db() as c:
                c.execute("INSERT INTO expenses(exp_date,kind,category,amount,notes,employee_id,created_at) VALUES(?,?,?,?,?,?,?)", (dt, "سلفة", "سلف", a, v["notes"].get().strip(), eid, now_ts()))
                log(c, "صرف سلفة", f"{e['name']}: {fmt(a)}")
            win.destroy(); self.refresh_employees(); self.status.config(text="تم صرف السلفة")
        self.small_form(f"صرف سلفة: {e['name']}", [("date", "التاريخ", date.today().isoformat()), ("amt", "المبلغ", ""), ("notes", "ملاحظات", "")], save, 330)

    def employee_statement(self):
        eid = self.selected_emp()
        if not eid: return
        with db() as c:
            e = c.execute("SELECT * FROM employees WHERE id=?", (eid,)).fetchone()
            rows = c.execute("SELECT * FROM expenses WHERE employee_id=? ORDER BY exp_date,id", (eid,)).fetchall()
            is_rep = e["kind"] == "مندوب"
            rep_rows = []
            has_rep_moves = c.execute("SELECT (SELECT COUNT(*) FROM invoices WHERE rep_id=?)+(SELECT COUNT(*) FROM payments WHERE rep_id=?)", (eid, eid)).fetchone()[0]
            if is_rep or has_rep_moves:
                for r in c.execute(f"SELECT i.id,i.inv_date d,i.created_at,i.number,p.name pname,{NET_SQL} amt FROM invoices i LEFT JOIN parties p ON p.id=i.party_id WHERE i.kind='مبيعات' AND i.rep_id=?", (eid,)):
                    rep_rows.append((r["d"], r["created_at"] or "", f"0-{r['id']}", "فاتورة مبيعات", r["number"], r["pname"] or "", float(r["amt"]), 0.0))
                for r in c.execute("SELECT p.id,p.pay_date d,p.created_at,p.amount,pt.name pname FROM payments p JOIN parties pt ON pt.id=p.party_id WHERE p.kind='تحصيل' AND p.rep_id=?", (eid,)):
                    rep_rows.append((r["d"], r["created_at"] or "", f"1-{r['id']}", "سند تحصيل", f"سند {r['id']}", r["pname"], 0.0, float(r["amount"])))
                rep_rows.sort(key=lambda x: (x[0], x[1], x[2]))
        win = tk.Toplevel(self); win.title(f"كشف الموظف: {e['name']}"); win.geometry("980x" + ("760" if rep_rows or is_rep else "540")); win.configure(bg=BG); win.transient(self)
        sub = (e["kind"] or "موظف") + (f" — {e['job']}" if e["job"] else "")
        tk.Label(win, text=f"كشف الموظف: {e['name']}  ({sub})  —  المرتب الشهري {fmt(e['salary'])}", font=("Tahoma", 14, "bold"), bg=BG, fg=NAVY).pack(anchor="e", padx=15, pady=10)
        tk.Label(win, text="المرتبات والسلف", font=("Tahoma", 11, "bold"), bg=BG, fg=NAVY).pack(anchor="e", padx=15)
        box = tk.Frame(win, bg=BG); box.pack(fill="both", expand=True, padx=15)
        t = self.tree(box, ("date", "time", "what", "gross", "ded", "cash", "bal", "notes"), ("التاريخ", "الوقت", "البيان", "المبلغ", "المخصوم من السلف", "المدفوع نقدًا", "رصيد السلف", "ملاحظات"), [95, 75, 70, 100, 130, 110, 110, 200], height=7)
        bal = 0.0
        for r in rows:
            amt = float(r["amount"]); ded = float(r["deducted"] or 0)
            if r["kind"] == "سلفة": bal += amt; t.insert("", "end", values=(r["exp_date"], fmt_time(r["created_at"]), "سلفة", fmt(amt), "", fmt(amt), fmt(bal), r["notes"]))
            else: bal -= ded; t.insert("", "end", values=(r["exp_date"], fmt_time(r["created_at"]), "مرتب", fmt(amt + ded), fmt(ded), fmt(amt), fmt(bal), r["notes"]))
        self.total_bar(win, [("رصيد السلف الحالي", fmt(bal) + " ج.م")], title="").pack_configure(padx=15)
        if rep_rows or is_rep:
            tk.Label(win, text="مبيعات وتحصيلات المندوب (ضغطتين على فاتورة = فتحها)", font=("Tahoma", 11, "bold"), bg=BG, fg=NAVY).pack(anchor="e", padx=15, pady=(8, 0))
            box2 = tk.Frame(win, bg=BG); box2.pack(fill="both", expand=True, padx=15)
            t2 = self.tree(box2, ("date", "time", "what", "ref", "party", "sales", "col"), ("التاريخ", "الوقت", "البيان", "المرجع", "العميل", "مبيعات", "تحصيل"), [95, 75, 110, 110, 260, 120, 120], height=7)
            for r in rep_rows:
                t2.insert("", "end", iid=r[2], values=(r[0], fmt_time(r[1]), r[3], r[4], r[5], fmt(r[6]) if r[6] else "", fmt(r[7]) if r[7] else ""))
            t2.bind("<Double-1>", lambda ev: t2.selection() and t2.selection()[0].startswith("0-") and self.view_invoice(int(t2.selection()[0][2:])))
            self.total_bar(win, [("إجمالي المبيعات", fmt(sum(r[6] for r in rep_rows))), ("إجمالي التحصيلات", fmt(sum(r[7] for r in rep_rows)))]).pack_configure(padx=15)
        ttk.Button(win, text="إغلاق", command=win.destroy).pack(anchor="e", padx=15, pady=6)

    # ================= الخزنة =================
    def show_cash(self):
        self.clear(); self.title_label("الخزنة / الصندوق")
        top = tk.Frame(self.body, bg=BG); top.pack(fill="x")
        self.cash_card = tk.Label(top, text="", font=("Tahoma", 22, "bold"), bg="white", fg=NAVY, padx=24, pady=10, highlightbackground="#cbd8e7", highlightthickness=1); self.cash_card.pack(side="right", padx=6)
        self.cash_sub = tk.Label(top, text="", bg=BG, fg="#50647b", font=("Tahoma", 10), justify="right"); self.cash_sub.pack(side="right", padx=10)
        ttk.Button(top, text="جرد الخزنة", command=self.cash_inventory).pack(side="left", padx=4)
        f1 = tk.LabelFrame(self.body, text="إيداع / سحب يدوي", padx=10, pady=6); f1.pack(fill="x", pady=(8, 4))
        self.cm_kind = tk.StringVar(value="إيداع"); self.cm_date = tk.StringVar(value=date.today().isoformat()); self.cm_amount = tk.StringVar(); self.cm_notes = tk.StringVar()
        self.field(f1, "النوع", self.cm_kind, ["إيداع", "سحب"]); self.field(f1, "التاريخ", self.cm_date); self.field(f1, "المبلغ", self.cm_amount); self.field(f1, "ملاحظات", self.cm_notes)
        ttk.Button(f1, text="حفظ", command=self.save_cash_move).pack(side="right", padx=8, pady=12)
        f2 = tk.Frame(self.body, bg=BG); f2.pack(fill="x", pady=4)
        with db() as c: op = cash_opening(c)
        self.cash_open_var = tk.StringVar(value=str(op))
        tk.Label(f2, text="رصيد أول المدة:", bg=BG).pack(side="right", padx=4)
        ttk.Entry(f2, textvariable=self.cash_open_var, width=14, justify="right").pack(side="right")
        ttk.Button(f2, text="حفظ رصيد أول المدة", command=self.save_cash_opening).pack(side="right", padx=6)
        self.cf_from = tk.StringVar(value=date.today().replace(day=1).isoformat()); self.cf_to = tk.StringVar(value=date.today().isoformat())
        ttk.Button(f2, text="عرض", command=self.refresh_cash).pack(side="left", padx=4)
        ttk.Entry(f2, textvariable=self.cf_to, width=12, justify="right").pack(side="left"); tk.Label(f2, text="إلى", bg=BG).pack(side="left", padx=4)
        ttk.Entry(f2, textvariable=self.cf_from, width=12, justify="right").pack(side="left"); tk.Label(f2, text="من", bg=BG).pack(side="left", padx=4)
        self.cash_tree = self.tree(self.body, ("date", "time", "what", "inn", "out", "bal"), ("التاريخ", "الوقت", "البيان", "وارد", "صادر", "الرصيد"), [105, 80, 420, 130, 130, 140])
        self.cash_totals = tk.Frame(self.body, bg=BG); self.cash_totals.pack(fill="x")
        self.refresh_cash()

    def refresh_cash(self):
        for x in self.cash_tree.get_children(): self.cash_tree.delete(x)
        try: s = check_date(self.cf_from.get()); e = check_date(self.cf_to.get())
        except ValueError: return messagebox.showerror("خطأ", "صيغة التاريخ غير صحيحة (YYYY-MM-DD)")
        with db() as c: op = cash_opening(c); mv = treasury_moves(c)
        bal = op + sum(m[5] - m[6] for m in mv if m[0] < s)
        self.cash_tree.insert("", "end", values=("", "", "رصيد سابق (مرحّل)", "", "", fmt(bal)))
        tin = tout = 0.0
        for m in mv:
            if s <= m[0] <= e:
                bal += m[5] - m[6]; tin += m[5]; tout += m[6]
                self.cash_tree.insert("", "end", values=(m[0], fmt_time(m[7]), m[4], fmt(m[5]) if m[5] else "", fmt(m[6]) if m[6] else "", fmt(bal)))
        total = op + sum(m[5] - m[6] for m in mv)
        self.cash_card.config(text=f"الرصيد الحالي: {fmt(total)} ج.م")
        self.cash_sub.config(text=f"خلال الفترة المعروضة:\nوارد {fmt(tin)}   صادر {fmt(tout)}")
        for w in self.cash_totals.winfo_children(): w.destroy()
        self.total_bar(self.cash_totals, [("وارد الفترة", fmt(tin)), ("صادر الفترة", fmt(tout)), ("الرصيد في آخر الفترة", fmt(bal))])

    def save_cash_move(self):
        try: a = float(self.cm_amount.get()); d = check_date(self.cm_date.get())
        except ValueError: return messagebox.showerror("خطأ", "راجع المبلغ والتاريخ")
        if a <= 0: return messagebox.showerror("خطأ", "المبلغ يجب أن يكون أكبر من صفر")
        with db() as c:
            c.execute("INSERT INTO cash_moves(move_date,kind,amount,notes,created_at) VALUES(?,?,?,?,?)", (d, self.cm_kind.get(), a, self.cm_notes.get().strip(), now_ts()))
            log(c, "حركة خزنة", f"{self.cm_kind.get()} {fmt(a)}")
        self.cm_amount.set(""); self.cm_notes.set(""); self.refresh_cash()

    def save_cash_opening(self):
        try: v = float(self.cash_open_var.get() or 0)
        except ValueError: return messagebox.showerror("خطأ", "الرقم غير صحيح")
        with db() as c:
            c.execute("UPDATE settings SET cash_opening=? WHERE id=1", (v,)); log(c, "رصيد أول مدة الخزنة", fmt(v))
        self.refresh_cash(); self.status.config(text="تم حفظ رصيد أول المدة")

    def cash_inventory(self):
        with db() as c: bal = cash_balance(c)
        counted = simpledialog.askfloat("جرد الخزنة", f"رصيد البرنامج الآن: {fmt(bal)}\nاكتب المبلغ الموجود فعليًا في الخزنة:", parent=self)
        if counted is None: return
        diff = counted - bal
        if abs(diff) < 0.005: return messagebox.showinfo("الجرد", "الخزنة مطابقة تمامًا ✔")
        msg = (f"زيادة في الخزنة بمقدار {fmt(diff)}" if diff > 0 else f"عجز في الخزنة بمقدار {fmt(-diff)}")
        if messagebox.askyesno("نتيجة الجرد", msg + "\n\nهل تسجّل تسوية لتطابق الرصيد؟"):
            with db() as c:
                c.execute("INSERT INTO cash_moves(move_date,kind,amount,notes,created_at) VALUES(?,?,?,?,?)", (date.today().isoformat(), "إيداع" if diff > 0 else "سحب", abs(diff), "تسوية جرد", now_ts()))
                log(c, "جرد خزنة", f"{msg} (رصيد البرنامج {fmt(bal)} / الفعلي {fmt(counted)})")
            self.refresh_cash()

    # ================= أرصدة الحسابات =================
    def show_balances(self):
        self.clear(); self.title_label("أرصدة الحسابات")
        with db() as c:
            data = []
            for p in c.execute("SELECT * FROM parties ORDER BY name").fetchall():
                b = party_balance(c, p["id"])
                lc = c.execute("SELECT MAX(pay_date) FROM payments WHERE party_id=? AND kind='تحصيل'", (p["id"],)).fetchone()[0] or ""
                lp = c.execute("SELECT MAX(pay_date) FROM payments WHERE party_id=? AND kind='دفع'", (p["id"],)).fetchone()[0] or ""
                li = c.execute("SELECT MAX(inv_date) FROM invoices WHERE party_id=?", (p["id"],)).fetchone()[0] or ""
                data.append((p["id"], p["name"], p["kind"], b, lc, lp, li))
            cash = cash_balance(c)
            inv_val = sum(max(stock_of(c, r["id"]), 0) * float(r["buy_price"] or 0) for r in c.execute("SELECT id,buy_price FROM items").fetchall())
        recv = sum(d[3] for d in data if d[3] > 0); pay = -sum(d[3] for d in data if d[3] < 0)
        cards = tk.Frame(self.body, bg=BG); cards.pack(fill="x", pady=(0, 8))
        for title, val, color in [("على العملاء (لنا)", recv, "#1c7c4d"), ("علينا للموردين", pay, "#b91c1c"), ("الخزنة", cash, NAVY),
                                  ("صافي المركز (خزنة + عملاء − موردين)", cash + recv - pay, "#6d28d9"), ("قيمة المخزون (بسعر الشراء)", inv_val, "#b45309")]:
            card = tk.Frame(cards, bg="white", highlightbackground="#cbd8e7", highlightthickness=1, padx=12, pady=8); card.pack(side="right", expand=True, fill="x", padx=4)
            tk.Label(card, text=title, bg="white", fg="#50647b", font=("Tahoma", 9)).pack()
            tk.Label(card, text=fmt(val), bg="white", fg=color, font=("Tahoma", 16, "bold")).pack()
        tk.Label(self.body, text="ضغطتين على الاسم تفتح كشف حسابه  (موجب = على العميل ، سالب = للمورد)", bg=BG, fg="#50647b", font=("Tahoma", 9)).pack(anchor="e")
        tree = self.tree(self.body, ("id", "name", "kind", "deb", "cred", "lc", "lp", "li"), ("ID", "الاسم", "النوع", "مدين (عليه)", "دائن (له)", "آخر تحصيل", "آخر دفع", "آخر فاتورة"), [45, 250, 90, 130, 130, 110, 110, 110])
        for d in sorted(data, key=lambda x: -abs(x[3])):
            tree.insert("", "end", iid=str(d[0]), values=(d[0], d[1], d[2], fmt(d[3]) if d[3] > 0.005 else fmt(0), fmt(-d[3]) if d[3] < -0.005 else fmt(0), d[4], d[5], d[6]))
        self.total_bar(self.body, [("إجمالي المدين", fmt(recv)), ("إجمالي الدائن", fmt(pay)), ("الصافي", fmt(recv - pay))])
        tree.bind("<Double-1>", lambda e: tree.selection() and self.show_account(int(tree.selection()[0])))

    # ================= أرصدة الأصناف =================
    def show_stock(self):
        self.clear(); self.title_label("أرصدة الأصناف")
        tk.Label(self.body, text="ضغطتين على صنف تفتح كل فواتيره  •  الأحمر = وصل للحد الأدنى", bg=BG, fg="#50647b", font=("Tahoma", 9)).pack(anchor="e")
        tree = self.tree(self.body, ("code", "name", "unit", "inn", "out", "stock"), ("الكود", "اسم الصنف", "الوحدة", "إجمالي الوارد", "إجمالي الصادر", "الرصيد الحالي"), [100, 300, 100, 160, 160, 150])
        tree.tag_configure("low", foreground="#b91c1c")
        with db() as c:
            for r in c.execute("SELECT it.*,COALESCE(SUM(CASE WHEN i.kind IN ('مشتريات','مرتجع مبيعات') THEN l.qty END),0) inn,COALESCE(SUM(CASE WHEN i.kind IN ('مبيعات','مرتجع مشتريات') THEN l.qty END),0) outq FROM items it LEFT JOIN invoice_lines l ON l.item_id=it.id LEFT JOIN invoices i ON i.id=l.invoice_id GROUP BY it.id ORDER BY it.name").fetchall():
                st = r["inn"] - r["outq"]; mn = float(r["min_stock"] or 0)
                tree.insert("", "end", iid=str(r["id"]), values=(r["code"] or "", r["name"], r["unit"], fmt(r["inn"]), fmt(r["outq"]), fmt(st)), tags=("low",) if mn > 0 and st <= mn else ())
        tree.bind("<Double-1>", lambda e: self.item_invoices_selected(tree))

    # ================= كشف الحساب =================
    def show_account(self, pid=None):
        self.clear(); self.title_label("كشف حساب عميل / مورد")
        with db() as c: parties = c.execute("SELECT * FROM parties ORDER BY name").fetchall()
        self.account_lookup = {party_label(p): p["id"] for p in parties}
        form = tk.Frame(self.body, bg=BG); form.pack(fill="x", pady=5)
        self.acc_party = tk.StringVar(); self.acc_from = tk.StringVar(value=date.today().replace(day=1).isoformat()); self.acc_to = tk.StringVar(value=date.today().isoformat())
        self.field(form, "الاسم", self.acc_party, list(self.account_lookup), search=True)
        self.field(form, "من تاريخ", self.acc_from); self.field(form, "إلى تاريخ", self.acc_to)
        ttk.Button(form, text="عرض الكشف", command=self.render_account).pack(side="right", padx=8, pady=20)
        ttk.Button(form, text="طباعة / PDF", command=self.print_statement).pack(side="right", padx=4, pady=20)
        self.acc_note = tk.Label(self.body, text="", bg=BG, fg="#6b7280", font=("Tahoma", 9), anchor="e"); self.acc_note.pack(fill="x")
        self.acc_result = tk.Frame(self.body, bg=BG); self.acc_result.pack(fill="both", expand=True)
        if pid:
            for k, v in self.account_lookup.items():
                if v == pid: self.acc_party.set(k)
            self.acc_from.set("2000-01-01")
            self.render_account()

    def render_account(self):
        for w in self.acc_result.winfo_children(): w.destroy()
        pid = self.account_lookup.get(self.acc_party.get())
        if not pid: return messagebox.showwarning("تنبيه", "اختر الاسم")
        try: start = check_date(self.acc_from.get()); end = check_date(self.acc_to.get())
        except ValueError: return messagebox.showerror("خطأ", "صيغة التاريخ غير صحيحة (YYYY-MM-DD)")
        if start > end: return messagebox.showerror("خطأ", "تاريخ البداية بعد تاريخ النهاية")
        party, opening, rows, closing = build_statement(pid, start, end)
        with db() as c: self.acc_note.config(text=party_last_text(c, pid))
        self.last_statement = (party, start, end, opening, rows, closing)
        tk.Label(self.acc_result, text="ضغطتين على فاتورة = فتحها  •  ضغطتين على سند = تفاصيله", bg=BG, fg="#50647b", font=("Tahoma", 9)).pack(anchor="e")
        tree = self.tree(self.acc_result, ("date", "time", "number", "kind", "debit", "credit", "balance"), ("التاريخ", "الوقت", "المرجع", "البيان", "مدين", "دائن", "الرصيد"), [110, 80, 130, 250, 130, 130, 140])
        tree.insert("", "end", iid="open", values=("", "", "", "رصيد سابق (مرحّل)", "", "", fmt(opening)))
        for r in rows: tree.insert("", "end", iid=f"{r[6]}-{r[7]}", values=(r[0], fmt_time(r[8]), r[1], r[2], fmt(r[3]), fmt(r[4]), fmt(r[5])))
        tree.bind("<Double-1>", lambda e: self.open_statement_row(tree))
        self.total_bar(self.acc_result, [("إجمالي المدين", fmt(sum(r[3] for r in rows))), ("إجمالي الدائن", fmt(sum(r[4] for r in rows))), ("الرصيد الختامي", fmt(closing) + " ج.م")])
        tk.Label(self.acc_result, text="الرصيد: موجب = على العميل ، سالب = للمورد", bg=BG, fg="#50647b", font=("Tahoma", 9)).pack(anchor="e")

    def open_statement_row(self, tree):
        sel = tree.selection()
        if not sel or "-" not in sel[0]: return
        typ, rid = sel[0].split("-"); rid = int(rid)
        if typ == "0": return self.view_invoice(rid)
        with db() as c:
            p = c.execute("SELECT * FROM payments WHERE id=?", (rid,)).fetchone()
            rep =rep_name_of(c, p["rep_id"]) if p and p["kind"] == "تحصيل" else ""
        if p: messagebox.showinfo(f"سند رقم {rid}", f"التاريخ: {p['pay_date']}  {fmt_time(p['created_at'])}\nالنوع: {'تحصيل' if p['kind'] == 'تحصيل' else 'دفع'}\nالمبلغ: {fmt(p['amount'])} ج.م" + (f"\nالمندوب: {rep}" if rep else "") + f"\nملاحظات: {p['notes'] or '-'}")

    def print_statement(self):
        if not self.last_statement: return messagebox.showwarning("تنبيه", "اعرض الكشف أولًا ثم اطبعه")
        party, start, end, opening, rows, closing = self.last_statement
        with db() as c: s = c.execute("SELECT * FROM settings WHERE id=1").fetchone()
        body = f"<tr><td></td><td></td><td></td><td>رصيد سابق (مرحّل)</td><td></td><td></td><td>{fmt(opening)}</td></tr>"
        body += "".join(f"<tr><td>{esc(r[0])}</td><td>{esc(fmt_time(r[8]))}</td><td>{esc(r[1])}</td><td>{esc(r[2])}</td><td>{fmt(r[3])}</td><td>{fmt(r[4])}</td><td>{fmt(r[5])}</td></tr>" for r in rows)
        body += f"<tr class='t'><td colspan='4'>الإجمالي</td><td>{fmt(sum(r[3] for r in rows))}</td><td>{fmt(sum(r[4] for r in rows))}</td><td>{fmt(closing)}</td></tr>"
        html = f"""<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8"><title>كشف حساب</title><style>
        @page{{size:A4;margin:12mm}}body{{font-family:Tahoma,Arial,sans-serif;font-size:12px;color:#111}}
        h1,h2,h3{{text-align:center;margin:4px}}table{{width:100%;border-collapse:collapse;margin-top:10px}}
        th,td{{border:1px solid #555;padding:5px;text-align:center}}th{{background:#eee}}
        tr:nth-child(even) td{{background:#f6fafd}}tr.t td{{font-weight:bold;background:#e3eef9}}
        .tot{{margin-top:10px;font-weight:bold;font-size:14px}}</style>
        <h1>{esc(s['company']) or 'اسم الشركة'}</h1><h2>كشف حساب: {esc(party['name'])}</h2>
        <h3>من {esc(start)} إلى {esc(end)}</h3>
        <table><thead><tr><th>التاريخ</th><th>الوقت</th><th>المرجع</th><th>البيان</th><th>مدين</th><th>دائن</th><th>الرصيد</th></tr></thead><tbody>{body}</tbody></table>
        <div class="tot">الرصيد الختامي: {fmt(closing)} ج.م</div>
        <div>موجب = على العميل ، سالب = للمورد</div></html>"""
        path = os.path.join(PRINT_DIR, f"statement_{party['id']}.html")
        with open(path, "w", encoding="utf-8") as f: f.write(html)
        open_file(path)

    # ================= الأرباح =================
    def show_profit(self):
        self.clear(); self.title_label("تقرير الأرباح")
        bar = tk.Frame(self.body, bg=BG); bar.pack(fill="x", pady=2)
        self.pf_from = tk.StringVar(value=date.today().replace(day=1).isoformat()); self.pf_to = tk.StringVar(value=date.today().isoformat())
        self.field(bar, "من تاريخ", self.pf_from); self.field(bar, "إلى تاريخ", self.pf_to)
        ttk.Button(bar, text="عرض التقرير", command=self.render_profit).pack(side="right", padx=6, pady=18)
        ttk.Button(bar, text="مقارنة", command=self.compare_dialog).pack(side="right", padx=4, pady=18)
        self.pf_result = tk.Frame(self.body, bg=BG); self.pf_result.pack(fill="both", expand=True)
        self.render_profit()

    def render_profit(self):
        for w in self.pf_result.winfo_children(): w.destroy()
        try: start = check_date(self.pf_from.get()); end = check_date(self.pf_to.get())
        except ValueError: return messagebox.showerror("خطأ", "صيغة التاريخ غير صحيحة (YYYY-MM-DD)")
        if start > end: return messagebox.showerror("خطأ", "تاريخ البداية بعد تاريخ النهاية")
        ps = profit_summary(start, end)
        wrap = tk.Frame(self.pf_result, bg=BG); wrap.pack(fill="both", expand=True, pady=(4, 0))
        sumf = tk.Frame(wrap, bg=BG); sumf.pack(side="right", fill="y", padx=(8, 0))
        tk.Label(sumf, text="ملخص الفترة", bg=BG, fg=NAVY, font=("Tahoma", 11, "bold")).pack(anchor="e")
        st = self.tree(sumf, ("l", "v"), ("البند", "القيمة (ج.م)"), [300, 120], height=11)
        st.tag_configure("key", font=("Tahoma", 11, "bold"), foreground="#123b67")
        for label, v in metric_rows(ps): st.insert("", "end", values=(label, fmt(v)), tags=("key",) if ("Total" in label or "الفعلي" in label) else ())
        itf = tk.Frame(wrap, bg=BG); itf.pack(side="left", fill="both", expand=True)
        tk.Label(itf, text="تفصيل الأصناف", bg=BG, fg=NAVY, font=("Tahoma", 11, "bold")).pack(anchor="e")
        tree = self.tree(itf, ("name", "qty", "rev", "avg", "cost", "profit"), ("الصنف", "الكمية الصافية", "المبيعات الصافية", "متوسط التكلفة", "إجمالي التكلفة", "الربح"), [150, 105, 125, 110, 120, 90])
        for r in ps["rows"]: tree.insert("", "end", values=(r[0], fmt(r[1]), fmt(r[2]), fmt(r[3]), fmt(r[4]), fmt(r[5])))
        if ps["by_cat"]:
            tk.Label(self.pf_result, text="المصروفات العامة: " + " • ".join(f"{n}: {fmt(a)}" for n, a in ps["by_cat"]), bg=BG, fg="#50647b", font=("Tahoma", 9), wraplength=1200, justify="right").pack(anchor="e")
        tk.Label(self.pf_result, text="التكلفة = متوسط سعر الشراء المرجّح للصنف حتى تاريخ النهاية (بدون خصومات المشتريات). إجمالي الربح = المبيعات − المرتجعات − التكلفة − الخصومات. الربح الفعلي = إجمالي الربح − المصروفات − المرتبات − السلف.", bg=BG, fg="#50647b", font=("Tahoma", 9), wraplength=1200, justify="right").pack(anchor="e")

    def compare_dialog(self):
        try: start = check_date(self.pf_from.get()); end = check_date(self.pf_to.get())
        except ValueError: return messagebox.showerror("خطأ", "صيغة التاريخ غير صحيحة (YYYY-MM-DD)")
        win = tk.Toplevel(self); win.title("مقارنة الأرباح"); win.geometry("860x560"); win.configure(bg=BG); win.transient(self)
        mode = tk.StringVar(value="الشهر السابق"); cf = tk.StringVar(); ct = tk.StringVar()
        top = tk.Frame(win, bg=BG); top.pack(fill="x", padx=15, pady=10)
        self.field(top, "طريقة المقارنة", mode, ["الفترة السابقة بنفس الطول", "الشهر السابق", "فترة أخرى"])
        self.field(top, "من تاريخ (فترة أخرى)", cf); self.field(top, "إلى تاريخ (فترة أخرى)", ct)
        info = tk.Label(win, text="", bg=BG, fg=NAVY, font=("Tahoma", 10, "bold")); info.pack(anchor="e", padx=15)
        box = tk.Frame(win, bg=BG); box.pack(fill="both", expand=True, padx=15, pady=8)
        def run():
            for w in box.winfo_children(): w.destroy()
            s = date.fromisoformat(start); e = date.fromisoformat(end); m = mode.get()
            if m == "الفترة السابقة بنفس الطول":
                n = (e - s).days + 1; pe = s - timedelta(days=1); pb = pe - timedelta(days=n - 1)
            elif m == "الشهر السابق":
                pe = s.replace(day=1) - timedelta(days=1); pb = pe.replace(day=1)
            else:
                try: pb = date.fromisoformat(check_date(cf.get())); pe = date.fromisoformat(check_date(ct.get()))
                except ValueError: return messagebox.showerror("خطأ", "اكتب تواريخ فترة المقارنة بصيغة YYYY-MM-DD", parent=win)
            if pb > pe: return messagebox.showerror("خطأ", "تاريخ بداية المقارنة بعد نهايتها", parent=win)
            a = profit_summary(start, end); b = profit_summary(pb.isoformat(), pe.isoformat())
            info.config(text=f"الحالية: {start} ← {end}        المقارنة: {pb} ← {pe}")
            t = self.tree(box, ("m", "cur", "prev", "diff", "pct"), ("البند", "الفترة الحالية", "فترة المقارنة", "الفرق", "النسبة %"), [250, 130, 130, 130, 100])
            t.tag_configure("key", font=("Tahoma", 10, "bold"), foreground="#123b67")
            for (label, x), (_, y) in zip(metric_rows(a), metric_rows(b)):
                d = x - y; pct = f"{(d / abs(y) * 100):+.1f}%" if abs(y) > 1e-9 else "—"
                t.insert("", "end", values=(label, fmt(x), fmt(y), f"{d:+,.2f}", pct), tags=("key",) if ("Total" in label or "الفعلي" in label) else ())
        ttk.Button(top, text="قارن", command=run).pack(side="right", padx=8, pady=14)
        run()

    # ================= التقرير اليومي =================
    def show_daily(self):
        self.clear(); self.title_label("التقرير اليومي")
        bar = tk.Frame(self.body, bg=BG); bar.pack(fill="x", pady=2)
        self.dr_date = tk.StringVar(value=date.today().isoformat())
        self.field(bar, "التاريخ YYYY-MM-DD", self.dr_date)
        ttk.Button(bar, text="عرض", command=self.render_daily).pack(side="right", padx=6, pady=18)
        ttk.Button(bar, text="طباعة", command=self.print_daily).pack(side="right", padx=4, pady=18)
        self.dr_box = tk.Frame(self.body, bg=BG); self.dr_box.pack(fill="both", expand=True)
        self.render_daily()

    def render_daily(self):
        for w in self.dr_box.winfo_children(): w.destroy()
        try: day = check_date(self.dr_date.get())
        except ValueError: return messagebox.showerror("خطأ", "صيغة التاريخ غير صحيحة (YYYY-MM-DD)")
        self.dr_rows = daily_rows(day); self.dr_day = day
        t = self.tree(self.dr_box, ("l", "v"), ("البند", "القيمة"), [520, 200])
        t.tag_configure("h", background="#dbe7f4", font=("Tahoma", 10, "bold")); t.tag_configure("b", font=("Tahoma", 10, "bold"), foreground="#123b67")
        for kind, label, val in self.dr_rows: t.insert("", "end", values=(label, val), tags=(kind,) if kind in ("h", "b") else ())

    def print_daily(self):
        if not hasattr(self, "dr_rows"): return
        with db() as c: s = c.execute("SELECT * FROM settings WHERE id=1").fetchone()
        body = ""
        for kind, label, val in self.dr_rows:
            if kind == "h": body += f"<tr><th colspan='2'>{esc(label)}</th></tr>"
            else: body += f"<tr{' class=b' if kind == 'b' else ''}><td>{esc(label)}</td><td>{esc(val)}</td></tr>"
        html = f"""<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8"><title>تقرير يومي</title><style>
        @page{{size:A4;margin:12mm}}body{{font-family:Tahoma,Arial,sans-serif;font-size:12px;color:#111}}
        h1,h2{{text-align:center;margin:4px}}table{{width:100%;border-collapse:collapse;margin-top:10px}}
        th,td{{border:1px solid #555;padding:5px 8px;text-align:right}}th{{background:#ddd}}tr.b td{{font-weight:bold;background:#f3f3f3}}</style>
        <h1>{esc(s['company']) or 'اسم الشركة'}</h1><h2>التقرير اليومي — {esc(self.dr_day)}</h2><table>{body}</table></html>"""
        path = os.path.join(PRINT_DIR, f"daily_{self.dr_day}.html")
        with open(path, "w", encoding="utf-8") as f: f.write(html)
        open_file(path)

    # ================= سجل النشاط =================
    def show_log(self):
        self.clear(); self.title_label("سجل النشاط (للقراءة فقط)")
        with db() as c: acts = ["الكل"] + [r[0] for r in c.execute("SELECT DISTINCT action FROM audit_log ORDER BY action")]
        bar = tk.Frame(self.body, bg=BG); bar.pack(fill="x")
        self.lg_from = tk.StringVar(value=(date.today() - timedelta(days=7)).isoformat()); self.lg_to = tk.StringVar(value=date.today().isoformat())
        self.lg_act = tk.StringVar(value="الكل"); self.lg_q = tk.StringVar()
        self.field(bar, "من", self.lg_from); self.field(bar, "إلى", self.lg_to); self.field(bar, "العملية", self.lg_act, acts); self.field(bar, "بحث في التفاصيل", self.lg_q)
        ttk.Button(bar, text="عرض", command=self.refresh_log).pack(side="right", padx=6, pady=18)
        self.lg_tree = self.tree(self.body, ("at", "user", "act", "det"), ("الوقت", "المستخدم", "العملية", "التفاصيل"), [150, 110, 160, 650])
        self.lg_tree.bind("<Double-1>", lambda e: self.lg_tree.selection() and messagebox.showinfo("تفاصيل العملية", "\n".join(str(x) for x in self.lg_tree.item(self.lg_tree.selection()[0], "values"))))
        self.refresh_log()

    def refresh_log(self):
        for x in self.lg_tree.get_children(): self.lg_tree.delete(x)
        try: s = check_date(self.lg_from.get()); e = check_date(self.lg_to.get())
        except ValueError: return messagebox.showerror("خطأ", "صيغة التاريخ غير صحيحة (YYYY-MM-DD)")
        q = self.lg_q.get().strip().lower(); act = self.lg_act.get()
        with db() as c: rows = c.execute("SELECT * FROM audit_log WHERE substr(at,1,10) BETWEEN ? AND ? ORDER BY id DESC", (s, e)).fetchall()
        for r in rows:
            if act != "الكل" and r["action"] != act: continue
            if q and q not in (r["details"] or "").lower(): continue
            self.lg_tree.insert("", "end", values=(r["at"], r["user"], r["action"], r["details"]))

    # ================= تقرير المناديب =================
    def rep_moves(self, c, rep_key, s, e):
        """حركات مندوب في فترة: فواتير مبيعات + سندات تحصيل. rep_key = 0 للمكتب."""
        rows = []
        for r in c.execute(f"SELECT i.id,i.inv_date d,i.created_at,i.number,p.name pname,{NET_SQL} amt FROM invoices i LEFT JOIN parties p ON p.id=i.party_id "
                           "WHERE i.kind='مبيعات' AND COALESCE(i.rep_id,0)=? AND i.inv_date BETWEEN ? AND ?", (rep_key, s, e)):
            rows.append((r["d"], r["created_at"] or "", f"0-{r['id']}", "فاتورة مبيعات", r["number"], r["pname"] or "", float(r["amt"]), 0.0))
        for r in c.execute("SELECT p.id,p.pay_date d,p.created_at,p.amount,pt.name pname FROM payments p JOIN parties pt ON pt.id=p.party_id "
                           "WHERE p.kind='تحصيل' AND COALESCE(p.rep_id,0)=? AND p.pay_date BETWEEN ? AND ?", (rep_key, s, e)):
            rows.append((r["d"], r["created_at"] or "", f"1-{r['id']}", "سند تحصيل", f"سند {r['id']}", r["pname"], 0.0, float(r["amount"])))
        rows.sort(key=lambda x: (x[0], x[1], x[2]))
        return rows

    def show_reps(self):
        self.clear(); self.title_label("تقرير المناديب")
        bar = tk.Frame(self.body, bg=BG); bar.pack(fill="x", pady=2)
        self.rp_from = tk.StringVar(value=date.today().replace(day=1).isoformat()); self.rp_to = tk.StringVar(value=date.today().isoformat())
        self.field(bar, "من تاريخ", self.rp_from); self.field(bar, "إلى تاريخ", self.rp_to)
        ttk.Button(bar, text="عرض التقرير", command=self.render_reps).pack(side="right", padx=6, pady=18)
        tk.Label(self.body, text="المبيعات = صافي فواتير المبيعات المسجّلة باسم المندوب (المرتجعات لا تُخصم)  •  التحصيلات = سندات التحصيل باسمه  •  ضغطتين على مندوب = تفاصيله",
                 bg=BG, fg="#50647b", font=("Tahoma", 9)).pack(anchor="e")
        self.rp_box = tk.Frame(self.body, bg=BG); self.rp_box.pack(fill="both", expand=True)
        self.render_reps()

    def render_reps(self):
        for w in self.rp_box.winfo_children(): w.destroy()
        try: s = check_date(self.rp_from.get()); e = check_date(self.rp_to.get())
        except ValueError: return messagebox.showerror("خطأ", "صيغة التاريخ غير صحيحة (YYYY-MM-DD)")
        if s > e: return messagebox.showerror("خطأ", "تاريخ البداية بعد تاريخ النهاية")
        with db() as c:
            reps = c.execute("SELECT id,name,phone FROM employees WHERE kind='مندوب' OR id IN (SELECT rep_id FROM invoices WHERE rep_id IS NOT NULL) "
                             "OR id IN (SELECT rep_id FROM payments WHERE rep_id IS NOT NULL) ORDER BY name").fetchall()
            data = []
            for key, name in [(r["id"], r["name"]) for r in reps] + [(0, OFFICE)]:
                mv = self.rep_moves(c, key, s, e)
                n = sum(1 for m in mv if m[2].startswith("0-"))
                ncol = sum(1 for m in mv if m[2].startswith("1-"))
                data.append((key, name, n, sum(m[6] for m in mv), ncol, sum(m[7] for m in mv)))
        tree = self.tree(self.rp_box, ("id", "name", "n", "sales", "ncol", "col", "diff"),
                         ("ID", "المندوب", "عدد الفواتير", "المبيعات", "عدد سندات التحصيل", "التحصيلات", "الفرق (مبيعات − تحصيلات)"), [45, 220, 100, 140, 140, 140, 190])
        for d in data:
            tree.insert("", "end", iid=str(d[0]), values=(d[0] or "", d[1], d[2], fmt(d[3]), d[4], fmt(d[5]), fmt(d[3] - d[5])))
        tree.bind("<Double-1>", lambda ev: tree.selection() and self.rep_detail(int(tree.selection()[0]), s, e))
        ts = sum(d[3] for d in data); tc = sum(d[5] for d in data)
        self.total_bar(self.rp_box, [("عدد الفواتير", str(sum(d[2] for d in data))), ("إجمالي المبيعات", fmt(ts)), ("إجمالي التحصيلات", fmt(tc)), ("الفرق", fmt(ts - tc))])

    def rep_detail(self, rep_key, s, e):
        with db() as c:
            name = OFFICE if not rep_key else rep_name_of(c, rep_key)
            rows = self.rep_moves(c, rep_key, s, e)
        win = tk.Toplevel(self); win.title(f"المندوب: {name}"); win.geometry("940x560"); win.configure(bg=BG); win.transient(self)
        tk.Label(win, text=f"المندوب: {name}   —   من {s} إلى {e}", font=("Tahoma", 14, "bold"), bg=BG, fg=NAVY).pack(anchor="e", padx=15, pady=(12, 2))
        tk.Label(win, text="ضغطتين على فاتورة = فتحها", bg=BG, fg="#50647b", font=("Tahoma", 9)).pack(anchor="e", padx=15)
        box = tk.Frame(win, bg=BG); box.pack(fill="both", expand=True, padx=15, pady=6)
        t = self.tree(box, ("date", "time", "what", "ref", "party", "sales", "col"), ("التاريخ", "الوقت", "البيان", "المرجع", "العميل", "مبيعات", "تحصيل"), [95, 75, 110, 110, 260, 120, 120])
        for r in rows: t.insert("", "end", iid=r[2], values=(r[0], fmt_time(r[1]), r[3], r[4], r[5], fmt(r[6]) if r[6] else "", fmt(r[7]) if r[7] else ""))
        t.bind("<Double-1>", lambda ev: t.selection() and t.selection()[0].startswith("0-") and self.view_invoice(int(t.selection()[0][2:])))
        self.total_bar(win, [("إجمالي المبيعات", fmt(sum(r[6] for r in rows))), ("إجمالي التحصيلات", fmt(sum(r[7] for r in rows)))]).pack_configure(padx=15)
        ttk.Button(win, text="إغلاق", command=win.destroy).pack(anchor="e", padx=15, pady=8)

    # ================= العينات (منفصلة تمامًا عن الأصناف والحسابات) =================
    SAMPLE_IN = "عينات مشتريات"; SAMPLE_OUT = "عينات مبيعات"

    def sample_balance(self, c, sid):
        r = c.execute("SELECT COALESCE(SUM(CASE WHEN kind=? THEN qty ELSE 0 END),0) inn, COALESCE(SUM(CASE WHEN kind=? THEN qty ELSE 0 END),0) outq FROM samples WHERE sample_item_id=?",
                      (self.SAMPLE_IN, self.SAMPLE_OUT, sid)).fetchone()
        return float(r["inn"]), float(r["outq"])

    def show_sample_items(self):
        self.clear(); self.title_label("أصناف العينات")
        tk.Label(self.body, text="أصناف العينات منفصلة تمامًا عن الأصناف العادية: لا تؤثر على المخزون ولا الأرباح ولا الخزنة ولا أرصدة العملاء.", bg=BG, fg="#50647b", font=("Tahoma", 9)).pack(anchor="e")
        self.si_edit_id = None
        form = tk.LabelFrame(self.body, text="بيانات صنف عينة", padx=10, pady=8); form.pack(fill="x", pady=(4, 8))
        self.si_vars = {k: tk.StringVar() for k in ("code", "name", "unit")}; self.si_vars["unit"].set("قطعة")
        for k, label in [("code", "كود العينة"), ("name", "اسم العينة"), ("unit", "الوحدة")]: self.field(form, label, self.si_vars[k])
        ttk.Button(form, text="حفظ", command=self.save_sample_item).pack(side="right", padx=8, pady=14)
        ttk.Button(form, text="تفريغ", command=self.reset_sample_item).pack(side="right", padx=4, pady=14)
        self.si_q = tk.StringVar(); self.search_bar("بحث سريع (الكود أو الاسم):", self.si_q)
        self.si_q.trace_add("write", lambda *a: self.refresh_sample_items())
        self.si_tree = self.tree(self.body, ("id", "code", "name", "unit", "inn", "out", "bal"), ("ID", "الكود", "اسم العينة", "الوحدة", "الوارد", "المنصرف", "الرصيد"), [45, 100, 280, 90, 120, 120, 120])
        self.si_tree.bind("<Double-1>", lambda e: self.sample_item_moves())
        bar = tk.Frame(self.body, bg=BG); bar.pack(fill="x", pady=6)
        ttk.Button(bar, text="حركات العينة المحددة", command=self.sample_item_moves).pack(side="right", padx=4)
        ttk.Button(bar, text="تعديل المحدد", command=self.edit_sample_item).pack(side="right", padx=4)
        ttk.Button(bar, text="حذف المحدد", command=self.delete_sample_item).pack(side="right", padx=4)
        tk.Label(bar, text="ضغطتين على عينة = حركاتها", bg=BG, fg="#50647b", font=("Tahoma", 9)).pack(side="left")
        self.refresh_sample_items()

    def reset_sample_item(self):
        self.si_edit_id = None; self.si_vars["code"].set(""); self.si_vars["name"].set(""); self.si_vars["unit"].set("قطعة")

    def save_sample_item(self):
        v = {k: x.get().strip() for k, x in self.si_vars.items()}
        if not v["name"]: return messagebox.showwarning("تنبيه", "اسم العينة مطلوب")
        try:
            with db() as c:
                if self.si_edit_id:
                    c.execute("UPDATE sample_items SET code=?,name=?,unit=? WHERE id=?", (v["code"] or None, v["name"], v["unit"] or "قطعة", self.si_edit_id)); log(c, "تعديل صنف عينة", v["name"])
                else:
                    c.execute("INSERT INTO sample_items(code,name,unit) VALUES(?,?,?)", (v["code"] or None, v["name"], v["unit"] or "قطعة")); log(c, "إضافة صنف عينة", v["name"])
        except sqlite3.IntegrityError: return messagebox.showerror("خطأ", "كود العينة مستخدم بالفعل")
        self.reset_sample_item(); self.refresh_sample_items(); self.status.config(text="تم حفظ صنف العينة")

    def refresh_sample_items(self):
        if not hasattr(self, "si_tree") or not self.si_tree.winfo_exists(): return
        for x in self.si_tree.get_children(): self.si_tree.delete(x)
        q = self.si_q.get().strip().lower()
        with db() as c:
            for r in c.execute("SELECT * FROM sample_items ORDER BY name").fetchall():
                if q and q not in (r["name"] or "").lower() and q not in (r["code"] or "").lower(): continue
                inn, out = self.sample_balance(c, r["id"])
                self.si_tree.insert("", "end", iid=str(r["id"]), values=(r["id"], r["code"] or "", r["name"], r["unit"], fmt(inn), fmt(out), fmt(inn - out)))

    def selected_sample_item(self):
        sel = self.si_tree.selection()
        if not sel: messagebox.showwarning("تنبيه", "حدد عينة أولًا"); return None
        return int(sel[0])

    def edit_sample_item(self):
        sid = self.selected_sample_item()
        if not sid: return
        with db() as c: r = c.execute("SELECT * FROM sample_items WHERE id=?", (sid,)).fetchone()
        self.si_edit_id = sid
        self.si_vars["code"].set(r["code"] or ""); self.si_vars["name"].set(r["name"]); self.si_vars["unit"].set(r["unit"] or "قطعة")
        self.status.config(text=f"جاري تعديل العينة «{r['name']}» — عدّل الحقول واضغط «حفظ»")

    def delete_sample_item(self):
        sid = self.selected_sample_item()
        if not sid: return
        with db() as c:
            used = c.execute("SELECT COUNT(*) FROM samples WHERE sample_item_id=?", (sid,)).fetchone()[0]
            name = c.execute("SELECT name FROM sample_items WHERE id=?", (sid,)).fetchone()["name"]
        if used: return messagebox.showwarning("لا يمكن الحذف", "العينة لها حركات مسجّلة. يمكنك تعديلها فقط.")
        if messagebox.askyesno("تأكيد", f"حذف العينة «{name}»؟"):
            with db() as c: c.execute("DELETE FROM sample_items WHERE id=?", (sid,)); log(c, "حذف صنف عينة", name)
            self.refresh_sample_items()

    def sample_item_moves(self):
        sid = self.selected_sample_item()
        if not sid: return
        with db() as c:
            it = c.execute("SELECT * FROM sample_items WHERE id=?", (sid,)).fetchone()
            rows = c.execute("SELECT s.*,p.name pname FROM samples s LEFT JOIN parties p ON p.id=s.party_id WHERE s.sample_item_id=? ORDER BY s.s_date,s.id", (sid,)).fetchall()
        win = tk.Toplevel(self); win.title(f"حركات العينة: {it['name']}"); win.geometry("900x520"); win.configure(bg=BG); win.transient(self)
        tk.Label(win, text=f"حركات العينة: {it['name']}", font=("Tahoma", 14, "bold"), bg=BG, fg=NAVY).pack(anchor="e", padx=15, pady=10)
        box = tk.Frame(win, bg=BG); box.pack(fill="both", expand=True, padx=15)
        t = self.tree(box, ("date", "time", "kind", "party", "inn", "out", "bal", "cost", "notes"), ("التاريخ", "الوقت", "النوع", "العميل / المورد", "وارد", "منصرف", "الرصيد", "التكلفة (للعلم)", "ملاحظات"), [95, 75, 115, 190, 80, 80, 80, 110, 160])
        bal = 0.0
        for r in rows:
            inn = r["kind"] == self.SAMPLE_IN; q = float(r["qty"]); bal += q if inn else -q
            t.insert("", "end", values=(r["s_date"], fmt_time(r["created_at"]), r["kind"], r["pname"] or "", fmt(q) if inn else "", "" if inn else fmt(q), fmt(bal), fmt(r["cost"]), r["notes"] or ""))
        self.total_bar(win, [("الرصيد الحالي", fmt(bal) + " " + (it["unit"] or ""))]).pack_configure(padx=15)
        ttk.Button(win, text="إغلاق", command=win.destroy).pack(anchor="e", padx=15, pady=6)

    def show_samples(self, kind):
        self.clear(); self.title_label(kind)
        inn = kind == self.SAMPLE_IN
        tk.Label(self.body, text=("عينات واردة لنا (تزيد رصيد العينات)" if inn else "عينات خارجة منا (تقلل رصيد العينات)") +
                 " — التكلفة للعلم فقط، ولا يوجد أي أثر على المخزون أو الأرباح أو الخزنة أو رصيد العميل/المورد.", bg=BG, fg="#50647b", font=("Tahoma", 9)).pack(anchor="e")
        with db() as c:
            sitems = c.execute("SELECT * FROM sample_items ORDER BY name").fetchall()
            parties = c.execute("SELECT id,name,address,phone FROM parties ORDER BY name").fetchall()
        self.smp_kind = kind
        self.smp_item_lookup = {item_label(r): r["id"] for r in sitems}
        self.smp_party_lookup = {party_label(p): p["id"] for p in parties}
        form = tk.LabelFrame(self.body, text="حركة عينة جديدة", padx=10, pady=6); form.pack(fill="x", pady=(4, 6))
        self.smp_date = tk.StringVar(value=date.today().isoformat()); self.smp_item = tk.StringVar(); self.smp_qty = tk.StringVar(value="1")
        self.smp_cost = tk.StringVar(value="0"); self.smp_party = tk.StringVar(); self.smp_notes = tk.StringVar()
        row = tk.Frame(form); row.pack(fill="x")
        self.field(row, "التاريخ YYYY-MM-DD", self.smp_date)
        self.field(row, "العينة", self.smp_item, list(self.smp_item_lookup), search=True)
        self.field(row, "الكمية", self.smp_qty)
        self.field(row, "التكلفة (للعلم فقط)", self.smp_cost)
        self.field(row, ("المورد" if inn else "العميل") + " (اختياري)", self.smp_party, list(self.smp_party_lookup), search=True)
        self.field(row, "ملاحظات", self.smp_notes)
        b = tk.Frame(form); b.pack(fill="x", pady=(6, 0))
        ttk.Button(b, text="حفظ", command=self.save_sample).pack(side="right", padx=4)
        ttk.Button(b, text="+ صنف عينة جديد", command=self.show_sample_items).pack(side="right", padx=4)
        if not sitems: tk.Label(b, text="لا توجد أصناف عينات بعد — أضفها من «أصناف العينات» أولًا", fg="#b45309").pack(side="left")
        flt = tk.LabelFrame(self.body, text="السجل", padx=8, pady=4); flt.pack(fill="x", pady=(0, 4))
        self.smp_from = tk.StringVar(value=date.today().replace(day=1).isoformat()); self.smp_to = tk.StringVar(value=date.today().isoformat()); self.smp_q = tk.StringVar()
        self.field(flt, "من", self.smp_from); self.field(flt, "إلى", self.smp_to); self.field(flt, "بحث (العينة / الاسم / ملاحظات)", self.smp_q)
        ttk.Button(flt, text="عرض", command=self.refresh_samples).pack(side="right", padx=6, pady=8)
        self.smp_tree = self.tree(self.body, ("date", "time", "item", "qty", "cost", "party", "notes"),
                                  ("التاريخ", "الوقت", "العينة", "الكمية", "التكلفة (للعلم)", "المورد" if inn else "العميل", "ملاحظات"), [100, 75, 240, 90, 120, 220, 260])
        self.smp_totals = tk.Frame(self.body, bg=BG); self.smp_totals.pack(fill="x")
        bar = tk.Frame(self.body, bg=BG); bar.pack(fill="x", pady=4)
        ttk.Button(bar, text="حذف الحركة المحددة", command=self.delete_sample).pack(side="right", padx=4)
        self.refresh_samples()

    def save_sample(self):
        sid = self.smp_item_lookup.get(self.smp_item.get())
        if not sid: return messagebox.showwarning("تنبيه", "اختر العينة")
        try: qty = float(self.smp_qty.get()); cost = float(self.smp_cost.get() or 0); d = check_date(self.smp_date.get())
        except ValueError: return messagebox.showerror("خطأ", "راجع التاريخ والكمية والتكلفة")
        if qty <= 0 or cost < 0: return messagebox.showerror("خطأ", "الكمية يجب أن تكون أكبر من صفر والتكلفة غير سالبة")
        party_txt = self.smp_party.get().strip()
        pid = self.smp_party_lookup.get(party_txt) if party_txt else None
        if party_txt and not pid: return messagebox.showwarning("تنبيه", "اختر الاسم من القائمة أو اترك الخانة فاضية")
        with db() as c:
            if self.smp_kind == self.SAMPLE_OUT:
                inn, out = self.sample_balance(c, sid)
                if qty > inn - out + 1e-9 and not messagebox.askyesno("رصيد العينات", f"رصيد العينة المسجّل {fmt(inn - out)} فقط.\nتكمل التسجيل؟"): return
            c.execute("INSERT INTO samples(s_date,created_at,kind,sample_item_id,qty,cost,party_id,notes) VALUES(?,?,?,?,?,?,?,?)",
                      (d, now_ts(), self.smp_kind, sid, qty, cost, pid, self.smp_notes.get().strip()))
            log(c, self.smp_kind, f"{self.smp_item.get()}: كمية {fmt(qty)}، تكلفة {fmt(cost)}" + (f" — {party_txt}" if party_txt else ""))
        self.smp_qty.set("1"); self.smp_cost.set("0"); self.smp_notes.set("")
        self.status.config(text="تم حفظ حركة العينة"); self.refresh_samples()

    def refresh_samples(self):
        for x in self.smp_tree.get_children(): self.smp_tree.delete(x)
        try: s = check_date(self.smp_from.get()); e = check_date(self.smp_to.get())
        except ValueError: return messagebox.showerror("خطأ", "صيغة التاريخ غير صحيحة (YYYY-MM-DD)")
        q = self.smp_q.get().strip().lower()
        with db() as c:
            rows = c.execute("SELECT s.*,si.name iname,si.unit,p.name pname FROM samples s JOIN sample_items si ON si.id=s.sample_item_id LEFT JOIN parties p ON p.id=s.party_id "
                             "WHERE s.kind=? AND s.s_date BETWEEN ? AND ? ORDER BY s.s_date DESC,s.id DESC", (self.smp_kind, s, e)).fetchall()
        tq = tc = 0.0; n = 0
        for r in rows:
            if q and q not in " ".join([r["iname"] or "", r["pname"] or "", r["notes"] or ""]).lower(): continue
            self.smp_tree.insert("", "end", iid=str(r["id"]), values=(r["s_date"], fmt_time(r["created_at"]), r["iname"], fmt(r["qty"]) + " " + (r["unit"] or ""), fmt(r["cost"]), r["pname"] or "", r["notes"] or ""))
            tq += float(r["qty"]); tc += float(r["cost"] or 0); n += 1
        for w in self.smp_totals.winfo_children(): w.destroy()
        self.total_bar(self.smp_totals, [("عدد الحركات", str(n)), ("إجمالي الكمية", fmt(tq)), ("إجمالي التكلفة (للعلم)", fmt(tc))])

    def delete_sample(self):
        sel = self.smp_tree.selection()
        if not sel: return messagebox.showwarning("تنبيه", "حدد حركة أولًا")
        if not messagebox.askyesno("تأكيد", "حذف حركة العينة المحددة نهائيًا؟"): return
        rid = int(sel[0])
        with db() as c:
            r = c.execute("SELECT s.*,si.name iname FROM samples s JOIN sample_items si ON si.id=s.sample_item_id WHERE s.id=?", (rid,)).fetchone()
            c.execute("DELETE FROM samples WHERE id=?", (rid,))
            if r: log(c, "حذف حركة عينة", f"{r['kind']}: {r['iname']} كمية {fmt(r['qty'])} بتاريخ {r['s_date']}")
        self.refresh_samples()

    # ================= الإعدادات والنسخ الاحتياطي =================
    def show_settings(self):
        self.clear(); self.title_label("الإعدادات")
        with db() as c: s = c.execute("SELECT * FROM settings WHERE id=1").fetchone()
        form = tk.LabelFrame(self.body, text="بيانات الشركة (تظهر في رأس البرنامج والفواتير)", padx=12, pady=10); form.pack(fill="x")
        self.settings_vars = {}
        for k, label in [("company", "اسم الشركة بالعربي (العنوان الكبير فوق)"), ("tagline", "السطر التاني تحت اسم الشركة (مثال: للتوريدات العمومية)"),
                         ("english", "اسم الشركة بالإنجليزية"), ("address", "العنوان / الفرع"), ("phone", "رقم الهاتف"),
                         ("taxno", "الرقم الضريبي (اختياري)"), ("operator", "اسم المستخدم (يظهر في سجل النشاط)")]:
            var = tk.StringVar(value=s[k] or ""); self.settings_vars[k] = var
            col = tk.Frame(form); col.pack(fill="x", pady=3); tk.Label(col, text=label, anchor="e").pack(fill="x"); ttk.Entry(col, textvariable=var, justify="right").pack(fill="x")
        ttk.Button(form, text="حفظ الإعدادات", command=self.save_settings).pack(anchor="e", pady=8)
        bf = tk.LabelFrame(self.body, text="النسخ الاحتياطي التلقائي (نسخة يوميًا عند فتح البرنامج وعند إغلاقه، ويُحتفظ بآخر 30 يومًا)", padx=12, pady=10); bf.pack(fill="x", pady=10)
        self.bk_label = tk.Label(bf, text="المجلد الحالي: " + backup_dir(), anchor="e"); self.bk_label.pack(fill="x")
        tk.Label(bf, text="لو المجلد المختار (فلاشة مثلًا) مش متاح وقت النسخ، النسخة بتتحفظ على الجهاز وبيظهر تنبيه.", anchor="e", fg="#50647b", font=("Tahoma", 9)).pack(fill="x")
        b = tk.Frame(bf); b.pack(fill="x", pady=6)
        ttk.Button(b, text="اختيار مجلد آخر للنسخ التلقائية (مثلًا فلاشة)", command=self.choose_backup_dir).pack(side="right")
        ttk.Button(b, text="الرجوع لمجلد الجهاز الافتراضي", command=self.reset_backup_dir).pack(side="right", padx=6)

    def save_settings(self):
        v = {k: x.get().strip() for k, x in self.settings_vars.items()}
        with db() as c:
            c.execute("UPDATE settings SET company=?,tagline=?,english=?,address=?,phone=?,taxno=?,operator=? WHERE id=1",
                      (v["company"], v["tagline"], v["english"], v["address"], v["phone"], v["taxno"], v["operator"]))
            log(c, "تعديل الإعدادات", "بيانات الشركة")
        self.refresh_header()
        messagebox.showinfo("تم", "تم حفظ الإعدادات")

    def choose_backup_dir(self):
        d = filedialog.askdirectory(title="اختر مجلد النسخ الاحتياطي التلقائي")
        if not d: return
        with db() as c:
            c.execute("UPDATE settings SET backup_dir=? WHERE id=1", (d,)); log(c, "تغيير مجلد النسخ التلقائي", d)
        self.bk_label.config(text="المجلد الحالي: " + d)

    def reset_backup_dir(self):
        with db() as c:
            c.execute("UPDATE settings SET backup_dir='' WHERE id=1"); log(c, "تغيير مجلد النسخ التلقائي", LOCAL_BACKUP_DIR)
        self.bk_label.config(text="المجلد الحالي: " + LOCAL_BACKUP_DIR)

    def backup(self):
        target = filedialog.asksaveasfilename(title="حفظ نسخة احتياطية", defaultextension=".db", filetypes=[("قاعدة بيانات SQLite", "*.db")], initialfile=f"warehouse_backup_{date.today().isoformat()}.db")
        if target:
            try:
                with db() as c:
                    dest = sqlite3.connect(target)
                    try: c.backup(dest)
                    finally: dest.close()
                    log(c, "نسخة احتياطية يدوية", target)
            except Exception as e:
                return messagebox.showerror("نسخة احتياطية", f"تعذّر حفظ النسخة:\n{e}")
            messagebox.showinfo("نسخة احتياطية", "تم حفظ النسخة الاحتياطية بنجاح")

def write_error_log(txt):
    try:
        os.makedirs(APP_DATA_DIR, exist_ok=True)
        with open(os.path.join(APP_DATA_DIR, "error_log.txt"), "a", encoding="utf-8") as f: f.write(now_ts() + "\n" + txt + "\n")
    except Exception: pass

def main():
    try:
        init_db()
        warn = None
        if not os.path.exists(auto_backup_path()): _, warn = auto_backup()
        app = App()
        if warn: app.after(600, lambda: messagebox.showwarning("النسخة الاحتياطية", warn, parent=app))
        app.mainloop()
    except Exception as e:
        # أي خطأ وقت فتح البرنامج يتسجل ويظهر في رسالة (البرنامج بيشتغل من غير نافذة أوامر)
        import traceback
        write_error_log(traceback.format_exc())
        try:
            r = tk.Tk(); r.withdraw()
            messagebox.showerror("تعذّر تشغيل البرنامج", f"{e}\n\nتفاصيل الخطأ محفوظة في:\n{os.path.join(APP_DATA_DIR, 'error_log.txt')}", parent=r)
            r.destroy()
        except Exception: pass

if __name__ == "__main__":
    main()
