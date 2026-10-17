# -*- coding: utf-8 -*-
"""
برنامج مخازن ومبيعات محلي لويندوز.
التخزين في SQLite داخل مجلد AppData؛ لا يحتاج إنترنت أو متصفح.

اتفاقية الرصيد: الرصيد الموجب = على العميل (مدين) ، السالب = للمورد (دائن)
  مدين: فواتير المبيعات + المبالغ المدفوعة للمورد
  دائن: فواتير المشتريات + المبالغ المحصّلة من العميل
"""
import os, sqlite3, webbrowser
from datetime import date
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

APP_DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "WarehouseDesktop")
PRINT_DIR = os.path.join(APP_DATA_DIR, "printouts")
os.makedirs(PRINT_DIR, exist_ok=True)
DB_PATH = os.path.join(APP_DATA_DIR, "warehouse.db")

# صافي الفاتورة = مجموع البنود - الخصم (يُستخدم مع الاسم المستعار i لجدول invoices)
NET_SQL = "(COALESCE((SELECT SUM(qty*price) FROM invoice_lines WHERE invoice_id=i.id),0)-COALESCE(i.discount,0))"

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con

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
        """)

def fmt(n):
    return f"{float(n or 0):,.2f}"

def esc(s):
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def check_date(s):
    return date.fromisoformat(s.strip()).isoformat()

def open_file(path):
    try: os.startfile(path)
    except Exception: webbrowser.open("file:///" + path.replace("\\", "/"))

def next_no(kind):
    prefix = "م" if kind == "مبيعات" else "ش"
    with db() as c:
        row = c.execute("SELECT number FROM invoices WHERE kind=? ORDER BY id DESC LIMIT 1", (kind,)).fetchone()
    if row:
        try: n = int(''.join(ch for ch in row['number'] if ch.isdigit())) + 1
        except Exception: n = 1
    else:
        n = 102820 if kind == "مبيعات" else 1
    return f"{prefix}{n}"

def party_moves(c, pid):
    """كل حركات الحساب (فواتير + سندات) مرتبة. كل حركة: (تاريخ, ترتيب, id, مرجع, بيان, مدين, دائن)"""
    moves = []
    for r in c.execute(f"SELECT i.id,i.number,i.kind,i.inv_date d,{NET_SQL} amt FROM invoices i WHERE i.party_id=?", (pid,)):
        amt = float(r["amt"])
        moves.append((r["d"], 0, r["id"], r["number"], "فاتورة " + r["kind"],
                      amt if r["kind"] == "مبيعات" else 0.0, amt if r["kind"] == "مشتريات" else 0.0))
    for r in c.execute("SELECT * FROM payments WHERE party_id=?", (pid,)):
        amt = float(r["amount"])
        is_col = r["kind"] == "تحصيل"
        label = ("تحصيل من العميل" if is_col else "دفع للمورد") + (f" - {r['notes']}" if r["notes"] else "")
        moves.append((r["pay_date"], 1, r["id"], f"سند {r['id']}", label,
                      0.0 if is_col else amt, amt if is_col else 0.0))
    moves.sort(key=lambda m: (m[0], m[1], m[2]))
    return moves

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
            rows.append((m[0], m[3], m[4], m[5], m[6], running))
    return party, opening, rows, running

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("سيستم المخازن والمبيعات")
        self.geometry("1180x760")
        self.minsize(980, 650)
        self.configure(bg="#eef3f8")
        self.style = ttk.Style(self)
        try: self.style.theme_use("clam")
        except Exception: pass
        self.style.configure("TButton", padding=7, font=("Tahoma", 10))
        self.style.configure("TLabel", font=("Tahoma", 10), background="#eef3f8")
        self.style.configure("Treeview", font=("Tahoma", 10), rowheight=27)
        self.style.configure("Treeview.Heading", font=("Tahoma", 10, "bold"))
        self.current_lines = []
        self.invoice_kind = "مبيعات"
        self.last_statement = None
        self.build_shell()
        self.show_home()

    def report_callback_exception(self, exc, val, tb):
        import traceback
        txt = "".join(traceback.format_exception(exc, val, tb))
        try:
            with open(os.path.join(APP_DATA_DIR, "error_log.txt"), "a", encoding="utf-8") as f: f.write(txt + "\n")
        except Exception: pass
        messagebox.showerror("خطأ غير متوقع", f"{val}\n\nتفاصيل الخطأ محفوظة في:\n{os.path.join(APP_DATA_DIR, 'error_log.txt')}")

    def build_shell(self):
        top = tk.Frame(self, bg="#123b67", height=78)
        top.pack(fill="x")
        tk.Label(top, text="سيستم المخازن والمبيعات", font=("Tahoma", 21, "bold"), fg="white", bg="#123b67").pack(side="right", padx=22, pady=18)
        tk.Label(top, text="يعمل بدون إنترنت • حفظ محلي تلقائي بقاعدة بيانات", font=("Tahoma", 10), fg="#d9eaff", bg="#123b67").pack(side="left", padx=22)
        nav = tk.Frame(self, bg="#dbe7f4")
        nav.pack(fill="x")
        for label, fn in [("الرئيسية", self.show_home), ("الأصناف", self.show_items), ("العملاء والموردون", self.show_parties),
                          ("فاتورة مبيعات", lambda: self.show_invoice("مبيعات")), ("فاتورة مشتريات", lambda: self.show_invoice("مشتريات")),
                          ("السندات (تحصيل / دفع)", self.show_payments), ("أرصدة الأصناف", self.show_stock),
                          ("كشف الحساب", self.show_account), ("الفواتير", self.show_invoices),
                          ("الإعدادات", self.show_settings), ("نسخة احتياطية", self.backup)]:
            ttk.Button(nav, text=label, command=fn).pack(side="right", padx=3, pady=7)
        self.body = tk.Frame(self, bg="#eef3f8")
        self.body.pack(fill="both", expand=True, padx=15, pady=14)
        self.status = tk.Label(self, text="جاهز — البيانات محفوظة على هذا الكمبيوتر", anchor="e", bg="#dbe7f4", fg="#173b60", font=("Tahoma", 9), padx=10, pady=6)
        self.status.pack(fill="x", side="bottom")

    def clear(self):
        for w in self.body.winfo_children(): w.destroy()

    def title_label(self, text):
        tk.Label(self.body, text=text, font=("Tahoma", 17, "bold"), bg="#eef3f8", fg="#123b67").pack(anchor="e", pady=(0, 12))

    def field(self, parent, label, var, values=None, side="right"):
        col = tk.Frame(parent); col.pack(side=side, expand=True, fill="x", padx=5)
        tk.Label(col, text=label, anchor="e").pack(fill="x")
        if values is not None:
            w = ttk.Combobox(col, textvariable=var, values=values, state="readonly", justify="right")
        else:
            w = ttk.Entry(col, textvariable=var, justify="right")
        w.pack(fill="x")
        return w

    def tree(self, parent, columns, headings, widths=None):
        box = tk.Frame(parent); box.pack(fill="both", expand=True)
        t = ttk.Treeview(box, columns=columns, show="headings")
        for i, col in enumerate(columns):
            t.heading(col, text=headings[i], anchor="e")
            t.column(col, width=(widths[i] if widths else 130), anchor="e")
        y = ttk.Scrollbar(box, orient="vertical", command=t.yview); t.configure(yscrollcommand=y.set)
        t.pack(side="right", fill="both", expand=True); y.pack(side="left", fill="y")
        return t

    # ---------------- الرئيسية ----------------
    def show_home(self):
        self.clear(); self.title_label("الرئيسية")
        with db() as c:
            items = c.execute("SELECT COUNT(*) FROM items").fetchone()[0]
            sales = c.execute("SELECT COUNT(*) FROM invoices WHERE kind='مبيعات'").fetchone()[0]
            buys = c.execute("SELECT COUNT(*) FROM invoices WHERE kind='مشتريات'").fetchone()[0]
        row = tk.Frame(self.body, bg="#eef3f8"); row.pack(fill="x")
        for title, val in [("عدد الأصناف", items), ("فواتير المبيعات", sales), ("فواتير المشتريات", buys)]:
            card = tk.Frame(row, bg="white", highlightbackground="#cbd8e7", highlightthickness=1, padx=28, pady=22)
            card.pack(side="right", expand=True, fill="x", padx=7)
            tk.Label(card, text=title, bg="white", fg="#50647b", font=("Tahoma", 11)).pack()
            tk.Label(card, text=str(val), bg="white", fg="#1762a5", font=("Tahoma", 24, "bold")).pack(pady=8)
        tk.Label(self.body, text="طريقة الاستخدام: أضف الأصناف والعملاء/الموردين، ثم أنشئ فواتير المشتريات والمبيعات، وسجّل التحصيلات والمدفوعات من شاشتها. كل عملية حفظ تُسجّل مباشرة في قاعدة البيانات.", wraplength=950, justify="right", bg="#eef3f8", font=("Tahoma", 12)).pack(anchor="e", pady=30)
        tk.Label(self.body, text="مهم: استخدم زر «نسخة احتياطية» بانتظام واحفظ النسخة على فلاشة أو قرص آخر.", fg="#9b2c2c", bg="#eef3f8", font=("Tahoma", 11, "bold")).pack(anchor="e")

    # ---------------- الأصناف ----------------
    def show_items(self):
        self.clear(); self.title_label("إدارة الأصناف")
        form = tk.LabelFrame(self.body, text="بيانات الصنف", padx=10, pady=10); form.pack(fill="x", pady=(0, 12))
        fields = [("code", "كود الصنف"), ("name", "اسم الصنف"), ("unit", "الوحدة"), ("buy", "سعر الشراء"), ("sell", "سعر البيع")]
        self.item_vars = {k: tk.StringVar(value="قطعة" if k == "unit" else "0" if k in ("buy", "sell") else "") for k, _ in fields}
        for k, label in fields: self.field(form, label, self.item_vars[k])
        actions = tk.Frame(form); actions.pack(fill="x", pady=8)
        ttk.Button(actions, text="حفظ الصنف", command=self.save_item).pack(side="right", padx=4)
        ttk.Button(actions, text="تفريغ الحقول", command=lambda: [v.set("قطعة" if k == "unit" else "0" if k in ("buy", "sell") else "") for k, v in self.item_vars.items()]).pack(side="right", padx=4)
        self.items_tree = self.tree(self.body, ("id", "code", "name", "unit", "buy", "sell", "stock"), ("ID", "الكود", "اسم الصنف", "الوحدة", "سعر الشراء", "سعر البيع", "الرصيد"), [45, 100, 280, 90, 120, 120, 100])
        self.refresh_items()

    def stock_qty(self, item_id):
        with db() as c:
            r = c.execute("""SELECT COALESCE(SUM(CASE WHEN i.kind='مشتريات' THEN l.qty ELSE -l.qty END),0)
            FROM invoice_lines l JOIN invoices i ON i.id=l.invoice_id WHERE l.item_id=?""", (item_id,)).fetchone()
        return r[0]

    def save_item(self):
        v = {k: x.get().strip() for k, x in self.item_vars.items()}
        if not v["name"]: return messagebox.showwarning("تنبيه", "اسم الصنف مطلوب")
        try:
            with db() as c:
                c.execute("INSERT INTO items(code,name,unit,buy_price,sell_price) VALUES(?,?,?,?,?)",
                          (v["code"] or None, v["name"], v["unit"] or "قطعة", float(v["buy"] or 0), float(v["sell"] or 0)))
            self.status.config(text="تم حفظ الصنف")
            self.refresh_items()
        except sqlite3.IntegrityError: messagebox.showerror("خطأ", "كود الصنف مستخدم بالفعل")
        except ValueError: messagebox.showerror("خطأ", "راجع الأسعار؛ يجب أن تكون أرقامًا")

    def refresh_items(self):
        if not hasattr(self, "items_tree") or not self.items_tree.winfo_exists(): return
        for x in self.items_tree.get_children(): self.items_tree.delete(x)
        with db() as c: rows = c.execute("SELECT * FROM items ORDER BY name").fetchall()
        for r in rows:
            self.items_tree.insert("", "end", values=(r["id"], r["code"] or "", r["name"], r["unit"], fmt(r["buy_price"]), fmt(r["sell_price"]), fmt(self.stock_qty(r["id"]))))

    # ---------------- العملاء والموردون ----------------
    def show_parties(self):
        self.clear(); self.title_label("العملاء والموردون")
        form = tk.LabelFrame(self.body, text="بيانات عميل / مورد", padx=10, pady=10); form.pack(fill="x", pady=(0, 12))
        self.party_vars = {k: tk.StringVar() for k in ("name", "kind", "phone", "address", "opening")}
        self.party_vars["kind"].set("عميل")
        for k, label in [("name", "الاسم"), ("kind", "النوع"), ("phone", "الهاتف"), ("address", "العنوان"), ("opening", "الرصيد الافتتاحي")]:
            self.field(form, label, self.party_vars[k], ["عميل", "مورد", "عميل/مورد"] if k == "kind" else None)
        tk.Label(form, text="الرصيد الافتتاحي: موجب = على العميل ، سالب = للمورد", fg="#50647b").pack(anchor="e")
        ttk.Button(form, text="حفظ الاسم", command=self.save_party).pack(anchor="e", pady=8)
        self.parties_tree = self.tree(self.body, ("id", "name", "kind", "phone", "address", "opening"), ("ID", "الاسم", "النوع", "الهاتف", "العنوان", "الرصيد الافتتاحي"), [50, 260, 120, 150, 300, 140])
        self.parties_tree.bind("<Double-1>", lambda e: self.party_statement())
        bar = tk.Frame(self.body, bg="#eef3f8"); bar.pack(fill="x", pady=8)
        ttk.Button(bar, text="كشف حساب المحدد (فواتير + سندات)", command=self.party_statement).pack(side="right", padx=4)
        ttk.Button(bar, text="سند جديد للمحدد", command=self.party_voucher).pack(side="right", padx=4)
        self.refresh_parties()

    def selected_party_id(self):
        sel = self.parties_tree.selection()
        if not sel:
            messagebox.showwarning("تنبيه", "حدد عميلًا أو موردًا من القائمة أولًا")
            return None
        return int(self.parties_tree.item(sel[0], "values")[0])

    def party_statement(self):
        pid = self.selected_party_id()
        if pid: self.show_account(pid)

    def party_voucher(self):
        pid = self.selected_party_id()
        if pid: self.show_payments(pid)

    def save_party(self):
        v = {k: x.get().strip() for k, x in self.party_vars.items()}
        if not v["name"]: return messagebox.showwarning("تنبيه", "الاسم مطلوب")
        try:
            with db() as c: c.execute("INSERT INTO parties(name,kind,phone,address,opening) VALUES(?,?,?,?,?)", (v["name"], v["kind"], v["phone"], v["address"], float(v["opening"] or 0)))
            self.refresh_parties(); self.status.config(text="تم حفظ العميل / المورد")
        except ValueError: messagebox.showerror("خطأ", "الرصيد الافتتاحي يجب أن يكون رقمًا")

    def refresh_parties(self):
        if not hasattr(self, "parties_tree") or not self.parties_tree.winfo_exists(): return
        for x in self.parties_tree.get_children(): self.parties_tree.delete(x)
        with db() as c: rows = c.execute("SELECT * FROM parties ORDER BY name").fetchall()
        for r in rows: self.parties_tree.insert("", "end", values=(r["id"], r["name"], r["kind"], r["phone"], r["address"], fmt(r["opening"])))

    # ---------------- الفواتير ----------------
    def show_invoice(self, kind):
        self.clear(); self.invoice_kind = kind; self.current_lines = []
        self.title_label("فاتورة " + kind)
        with db() as c:
            parties = c.execute("SELECT id,name FROM parties ORDER BY name").fetchall()
            items = c.execute("SELECT id,code,name,unit,buy_price,sell_price FROM items ORDER BY name").fetchall()
        form = tk.LabelFrame(self.body, text="بيانات الفاتورة", padx=10, pady=8); form.pack(fill="x")
        self.inv_no = tk.StringVar(value=next_no(kind)); self.inv_date = tk.StringVar(value=date.today().isoformat())
        self.inv_party = tk.StringVar(); self.inv_notes = tk.StringVar(); self.inv_discount = tk.StringVar(value="0")
        self.party_lookup = {f'{p["id"]} - {p["name"]}': p["id"] for p in parties}
        self.item_lookup = {f'{p["id"]} - {p["name"]}': dict(p) for p in items}
        self.field(form, "رقم الفاتورة", self.inv_no)
        self.field(form, "التاريخ YYYY-MM-DD", self.inv_date)
        self.field(form, "العميل / المورد", self.inv_party, list(self.party_lookup))
        self.field(form, "ملاحظات", self.inv_notes)
        add = tk.LabelFrame(self.body, text="إضافة صنف للفاتورة", padx=10, pady=8); add.pack(fill="x", pady=8)
        self.inv_item = tk.StringVar(); self.inv_qty = tk.StringVar(value="1"); self.inv_price = tk.StringVar(value="0")
        cb = self.field(add, "الصنف", self.inv_item, list(self.item_lookup))
        def price_changed(_=None):
            item = self.item_lookup.get(self.inv_item.get())
            if item: self.inv_price.set(str(item["sell_price"] if kind == "مبيعات" else item["buy_price"]))
        cb.bind("<<ComboboxSelected>>", price_changed)
        self.field(add, "الكمية", self.inv_qty); self.field(add, "سعر الوحدة", self.inv_price)
        ttk.Button(add, text="إضافة الصنف", command=self.add_invoice_line).pack(side="right", padx=10, pady=15)
        self.inv_tree = self.tree(self.body, ("name", "qty", "unit", "price", "total"), ("الصنف", "الكمية", "الوحدة", "سعر الوحدة", "الإجمالي"), [380, 120, 100, 150, 160])
        bottom = tk.Frame(self.body, bg="#eef3f8"); bottom.pack(fill="x", pady=8)
        self.inv_total_label = tk.Label(bottom, text="", font=("Tahoma", 14, "bold"), fg="#123b67", bg="#eef3f8"); self.inv_total_label.pack(side="right")
        dis = tk.Frame(bottom, bg="#eef3f8"); dis.pack(side="right", padx=20)
        tk.Label(dis, text="الخصم", bg="#eef3f8").pack(side="right", padx=4)
        ttk.Entry(dis, textvariable=self.inv_discount, width=10, justify="right").pack(side="right")
        ttk.Button(bottom, text="حذف آخر صنف", command=self.remove_invoice_line).pack(side="left", padx=4)
        ttk.Button(bottom, text="حفظ الفاتورة وطباعتها", command=self.save_invoice).pack(side="left", padx=4)
        self.inv_discount.trace_add("write", lambda *a: self.refresh_invoice_lines())
        self.refresh_invoice_lines()

    def add_invoice_line(self):
        item = self.item_lookup.get(self.inv_item.get())
        if not item: return messagebox.showwarning("تنبيه", "اختر الصنف")
        try: qty = float(self.inv_qty.get()); price = float(self.inv_price.get())
        except ValueError: return messagebox.showerror("خطأ", "الكمية والسعر يجب أن يكونا أرقامًا")
        if qty <= 0 or price < 0: return messagebox.showerror("خطأ", "الكمية يجب أن تكون أكبر من صفر والسعر غير سالب")
        if self.invoice_kind == "مبيعات":
            stock = self.stock_qty(item["id"]) - sum(l["qty"] for l in self.current_lines if l["item_id"] == item["id"])
            if qty > stock: return messagebox.showwarning("رصيد غير كافٍ", f"الرصيد المتاح من {item['name']} هو {fmt(stock)}")
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
        try: discount = float(self.inv_discount.get() or 0)
        except ValueError: return messagebox.showerror("خطأ", "الخصم يجب أن يكون رقمًا")
        if discount < 0 or discount > total: return messagebox.showerror("خطأ", "الخصم يجب أن يكون بين صفر وإجمالي الفاتورة")
        kind = self.invoice_kind; number = self.inv_no.get().strip() or next_no(kind)
        try:
            inv_date = check_date(self.inv_date.get())
        except ValueError:
            return messagebox.showerror("خطأ", "صيغة التاريخ غير صحيحة (YYYY-MM-DD)")
        try:
            with db() as c:
                cur = c.execute("INSERT INTO invoices(number,kind,inv_date,party_id,notes,discount) VALUES(?,?,?,?,?,?)", (number, kind, inv_date, party, self.inv_notes.get().strip(), discount))
                inv_id = cur.lastrowid
                for l in self.current_lines:
                    if kind == "مبيعات":
                        stock = c.execute("""SELECT COALESCE(SUM(CASE WHEN i.kind='مشتريات' THEN x.qty ELSE -x.qty END),0) FROM invoice_lines x JOIN invoices i ON i.id=x.invoice_id WHERE x.item_id=?""", (l["item_id"],)).fetchone()[0]
                        if l["qty"] > stock: raise ValueError("الرصيد أصبح غير كافٍ للصنف " + l["name"])
                    c.execute("INSERT INTO invoice_lines(invoice_id,item_id,item_name,unit,qty,price) VALUES(?,?,?,?,?,?)", (inv_id, l["item_id"], l["name"], l["unit"], l["qty"], l["price"]))
            self.status.config(text=f"تم حفظ فاتورة {kind} رقم {number} في قاعدة البيانات")
            self.print_invoice(inv_id)
            self.show_invoice(kind)
        except sqlite3.IntegrityError: messagebox.showerror("خطأ", "رقم الفاتورة موجود بالفعل؛ غيّر رقم الفاتورة")
        except ValueError as e: messagebox.showerror("خطأ", str(e))

    def invoice_html(self, inv_id):
        with db() as c:
            inv = c.execute("SELECT i.*,p.name party_name,p.phone party_phone,p.address party_address,p.opening party_opening FROM invoices i LEFT JOIN parties p ON p.id=i.party_id WHERE i.id=?", (inv_id,)).fetchone()
            lines = c.execute("SELECT * FROM invoice_lines WHERE invoice_id=?", (inv_id,)).fetchall()
            settings = c.execute("SELECT * FROM settings WHERE id=1").fetchone()
            moves = party_moves(c, inv["party_id"]) if inv["party_id"] else []
        total = sum(x["qty"] * x["price"] for x in lines)
        discount = float(inv["discount"] or 0)
        net = total - discount
        prior = float(inv["party_opening"] or 0)
        for m in moves:
            before = (m[1] == 0 and (m[0] < inv["inv_date"] or (m[0] == inv["inv_date"] and m[2] < inv_id))) or (m[1] == 1 and m[0] < inv["inv_date"])
            if before: prior += m[5] - m[6]
        current = prior + (net if inv["kind"] == "مبيعات" else -net)
        rows = "".join(f"<tr><td>{n}</td><td>{esc(l['item_name'])}</td><td>{fmt(l['qty'])}</td><td>{esc(l['unit'])}</td><td>{fmt(l['price'])}</td><td>{fmt(l['qty']*l['price'])}</td></tr>" for n, l in enumerate(lines, 1))
        company = esc(settings["company"]) or "اسم الشركة"
        copy = f"""<section class="copy">
          <div class="head"><div class="brand"><h1>{company}</h1><div>{esc(settings['english'])}</div><div>{esc(settings['address'])}　 {esc(settings['phone'])}</div></div>
          <h2>فاتورة {esc(inv['kind'])}　{esc(inv['number'])}</h2></div>
          <div class="meta"><div>التاريخ: <b>{esc(inv['inv_date'])}</b></div><div>اسم الحساب: <b>{esc(inv['party_name'])}</b></div><div>الهاتف: {esc(inv['party_phone'])}</div></div>
          <table><thead><tr><th>م</th><th>اسم الصنف</th><th>الكمية</th><th>الوحدة</th><th>السعر</th><th>الإجمالي</th></tr></thead><tbody>{rows}</tbody></table>
          <div class="sum"><div>الإجمالي: {fmt(total)} ج.م</div><div>الخصم: {fmt(discount)} ج.م</div><div>الصافي: {fmt(net)} ج.م</div></div>
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
        th{{background:#eee}}.sum{{display:flex;justify-content:space-between;gap:4px;border:1px solid #555;padding:6px 4px;margin-top:6px;font-weight:bold;font-size:9px}}
        .balance{{display:flex;justify-content:space-between;gap:4px;border:1px solid #555;padding:6px 4px;margin-top:5px;font-weight:bold}}
        .notes{{margin-top:6px;min-height:12px}}.sign{{position:absolute;bottom:7mm;left:5mm;right:5mm;display:flex;justify-content:space-between;border-top:1px solid #bbb;padding-top:5px}}
        @media screen{{body{{background:#e9eef4;padding:12px}}.sheet{{max-width:1100px;margin:auto}}.copy{{background:white;min-height:650px;box-shadow:0 2px 9px #0002}}}}
        </style><div class="sheet">{copy}{copy}</div></html>"""

    def print_invoice(self, inv_id):
        path = os.path.join(PRINT_DIR, f"invoice_{inv_id}.html")
        with open(path, "w", encoding="utf-8") as f: f.write(self.invoice_html(inv_id))
        try:
            os.startfile(path)
        except Exception:
            try: webbrowser.open("file:///" + path.replace("\\", "/"))
            except Exception: pass
        messagebox.showinfo("تم", "تم حفظ الفاتورة وفتحها للطباعة (Ctrl+P).\nلو لم تفتح، افتح هذا الملف يدويًا:\n" + path)

    # ---------------- التحصيلات والمدفوعات ----------------
    def show_payments(self, pid=None):
        self.clear(); self.title_label("السندات: تحصيل من عميل / دفع لمورد")
        with db() as c: parties = c.execute("SELECT id,name FROM parties ORDER BY name").fetchall()
        self.pay_lookup = {f'{p["id"]} - {p["name"]}': p["id"] for p in parties}
        self.pay_kinds = {"تحصيل من عميل": "تحصيل", "دفع لمورد": "دفع"}
        form = tk.LabelFrame(self.body, text="سند جديد", padx=10, pady=8); form.pack(fill="x", pady=(0, 10))
        self.pay_party = tk.StringVar(); self.pay_kind = tk.StringVar(value="تحصيل من عميل")
        self.pay_date = tk.StringVar(value=date.today().isoformat()); self.pay_amount = tk.StringVar(); self.pay_notes = tk.StringVar()
        for k, v in self.pay_lookup.items():
            if v == pid: self.pay_party.set(k)
        self.field(form, "الاسم", self.pay_party, list(self.pay_lookup))
        self.field(form, "نوع السند", self.pay_kind, list(self.pay_kinds))
        self.field(form, "التاريخ YYYY-MM-DD", self.pay_date)
        self.field(form, "المبلغ", self.pay_amount)
        self.field(form, "ملاحظات", self.pay_notes)
        ttk.Button(form, text="حفظ السند", command=self.save_payment).pack(side="right", padx=10, pady=12)
        self.pay_tree = self.tree(self.body, ("id", "date", "party", "kind", "amount", "notes"), ("رقم السند", "التاريخ", "الاسم", "النوع", "المبلغ", "ملاحظات"), [80, 120, 280, 150, 140, 300])
        ttk.Button(self.body, text="حذف السند المحدد", command=self.delete_payment).pack(anchor="e", pady=8)
        self.refresh_payments()

    def save_payment(self):
        pid = self.pay_lookup.get(self.pay_party.get())
        if not pid: return messagebox.showwarning("تنبيه", "اختر الاسم")
        try: amount = float(self.pay_amount.get())
        except ValueError: return messagebox.showerror("خطأ", "المبلغ يجب أن يكون رقمًا")
        if amount <= 0: return messagebox.showerror("خطأ", "المبلغ يجب أن يكون أكبر من صفر")
        try: d = check_date(self.pay_date.get())
        except ValueError: return messagebox.showerror("خطأ", "صيغة التاريخ غير صحيحة (YYYY-MM-DD)")
        with db() as c:
            c.execute("INSERT INTO payments(party_id,pay_date,kind,amount,notes) VALUES(?,?,?,?,?)", (pid, d, self.pay_kinds[self.pay_kind.get()], amount, self.pay_notes.get().strip()))
        self.pay_amount.set(""); self.pay_notes.set("")
        self.status.config(text="تم حفظ السند"); self.refresh_payments()

    def refresh_payments(self):
        for x in self.pay_tree.get_children(): self.pay_tree.delete(x)
        with db() as c:
            rows = c.execute("SELECT p.*,pt.name pname FROM payments p JOIN parties pt ON pt.id=p.party_id ORDER BY p.pay_date DESC,p.id DESC").fetchall()
        for r in rows:
            self.pay_tree.insert("", "end", values=(r["id"], r["pay_date"], r["pname"], "تحصيل من عميل" if r["kind"] == "تحصيل" else "دفع لمورد", fmt(r["amount"]), r["notes"]))

    def delete_payment(self):
        sel = self.pay_tree.selection()
        if not sel: return messagebox.showwarning("تنبيه", "حدد سندًا أولًا")
        pid = self.pay_tree.item(sel[0], "values")[0]
        if messagebox.askyesno("تأكيد", "حذف السند المحدد نهائيًا؟"):
            with db() as c: c.execute("DELETE FROM payments WHERE id=?", (pid,))
            self.refresh_payments()

    # ---------------- أرصدة الأصناف ----------------
    def show_stock(self):
        self.clear(); self.title_label("أرصدة الأصناف")
        tree = self.tree(self.body, ("code", "name", "unit", "buy", "sell", "stock"), ("الكود", "اسم الصنف", "الوحدة", "إجمالي المشتريات", "إجمالي المبيعات", "الرصيد الحالي"), [100, 300, 100, 170, 170, 150])
        with db() as c:
            for i in c.execute("SELECT * FROM items ORDER BY name").fetchall():
                r = c.execute("""SELECT COALESCE(SUM(CASE WHEN inv.kind='مشتريات' THEN l.qty ELSE 0 END),0) p,COALESCE(SUM(CASE WHEN inv.kind='مبيعات' THEN l.qty ELSE 0 END),0) s FROM invoice_lines l JOIN invoices inv ON inv.id=l.invoice_id WHERE l.item_id=?""", (i["id"],)).fetchone()
                tree.insert("", "end", values=(i["code"] or "", i["name"], i["unit"], fmt(r["p"]), fmt(r["s"]), fmt(r["p"] - r["s"])))

    # ---------------- كشف الحساب ----------------
    def show_account(self, pid=None):
        self.clear(); self.title_label("كشف حساب عميل / مورد")
        with db() as c: parties = c.execute("SELECT * FROM parties ORDER BY name").fetchall()
        self.account_lookup = {f'{p["id"]} - {p["name"]}': p["id"] for p in parties}
        form = tk.Frame(self.body, bg="#eef3f8"); form.pack(fill="x", pady=5)
        self.acc_party = tk.StringVar(); self.acc_from = tk.StringVar(value=date.today().replace(day=1).isoformat()); self.acc_to = tk.StringVar(value=date.today().isoformat())
        self.field(form, "الاسم", self.acc_party, list(self.account_lookup))
        self.field(form, "من تاريخ", self.acc_from); self.field(form, "إلى تاريخ", self.acc_to)
        ttk.Button(form, text="عرض الكشف", command=self.render_account).pack(side="right", padx=8, pady=20)
        ttk.Button(form, text="طباعة / PDF", command=self.print_statement).pack(side="right", padx=4, pady=20)
        self.acc_result = tk.Frame(self.body, bg="#eef3f8"); self.acc_result.pack(fill="both", expand=True)
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
        self.last_statement = (party, start, end, opening, rows, closing)
        tree = self.tree(self.acc_result, ("date", "number", "kind", "debit", "credit", "balance"), ("التاريخ", "المرجع", "البيان", "مدين", "دائن", "الرصيد"), [120, 140, 240, 130, 130, 140])
        tree.insert("", "end", values=("", "", "رصيد سابق (مرحّل)", "", "", fmt(opening)))
        for r in rows: tree.insert("", "end", values=(r[0], r[1], r[2], fmt(r[3]), fmt(r[4]), fmt(r[5])))
        tk.Label(self.acc_result, text=f"الرصيد الختامي: {fmt(closing)} ج.م  (موجب = على العميل ، سالب = للمورد)", font=("Tahoma", 14, "bold"), bg="#eef3f8", fg="#123b67").pack(anchor="e", pady=8)

    def print_statement(self):
        if not self.last_statement: return messagebox.showwarning("تنبيه", "اعرض الكشف أولًا ثم اطبعه")
        party, start, end, opening, rows, closing = self.last_statement
        with db() as c: s = c.execute("SELECT * FROM settings WHERE id=1").fetchone()
        body = f"<tr><td></td><td></td><td>رصيد سابق (مرحّل)</td><td></td><td></td><td>{fmt(opening)}</td></tr>"
        body += "".join(f"<tr><td>{esc(r[0])}</td><td>{esc(r[1])}</td><td>{esc(r[2])}</td><td>{fmt(r[3])}</td><td>{fmt(r[4])}</td><td>{fmt(r[5])}</td></tr>" for r in rows)
        html = f"""<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8"><title>كشف حساب</title><style>
        @page{{size:A4;margin:12mm}}body{{font-family:Tahoma,Arial,sans-serif;font-size:12px;color:#111}}
        h1,h2,h3{{text-align:center;margin:4px}}table{{width:100%;border-collapse:collapse;margin-top:10px}}
        th,td{{border:1px solid #555;padding:5px;text-align:center}}th{{background:#eee}}
        .tot{{margin-top:10px;font-weight:bold;font-size:14px}}</style>
        <h1>{esc(s['company']) or 'اسم الشركة'}</h1><h2>كشف حساب: {esc(party['name'])}</h2>
        <h3>من {esc(start)} إلى {esc(end)}</h3>
        <table><thead><tr><th>التاريخ</th><th>المرجع</th><th>البيان</th><th>مدين</th><th>دائن</th><th>الرصيد</th></tr></thead><tbody>{body}</tbody></table>
        <div class="tot">الرصيد الختامي: {fmt(closing)} ج.م</div>
        <div>موجب = على العميل ، سالب = للمورد</div></html>"""
        path = os.path.join(PRINT_DIR, f"statement_{party['id']}.html")
        with open(path, "w", encoding="utf-8") as f: f.write(html)
        open_file(path)

    # ---------------- سجل الفواتير ----------------
    def show_invoices(self):
        self.clear(); self.title_label("سجل الفواتير")
        with db() as c:
            rows = c.execute(f"SELECT i.id,i.number,i.kind,i.inv_date,p.name party,{NET_SQL} total FROM invoices i LEFT JOIN parties p ON p.id=i.party_id ORDER BY i.id DESC").fetchall()
        tree = self.tree(self.body, ("id", "kind", "number", "date", "party", "total"), ("ID", "النوع", "رقم الفاتورة", "التاريخ", "العميل / المورد", "الصافي"), [45, 100, 130, 130, 300, 150])
        for r in rows: tree.insert("", "end", values=(r["id"], r["kind"], r["number"], r["inv_date"], r["party"] or "", fmt(r["total"])))
        tree.bind("<Double-1>", lambda e: self.print_selected(tree))
        bar = tk.Frame(self.body, bg="#eef3f8"); bar.pack(fill="x", pady=8)
        ttk.Button(bar, text="طباعة الفاتورة المحددة", command=lambda: self.print_selected(tree)).pack(side="right", padx=4)
        ttk.Button(bar, text="حذف الفاتورة المحددة", command=lambda: self.delete_invoice(tree)).pack(side="right", padx=4)

    def print_selected(self, tree):
        sel = tree.selection()
        if not sel: return messagebox.showwarning("تنبيه", "حدد فاتورة أولًا")
        self.print_invoice(int(tree.item(sel[0], "values")[0]))

    def delete_invoice(self, tree):
        sel = tree.selection()
        if not sel: return messagebox.showwarning("تنبيه", "حدد فاتورة أولًا")
        inv_id = int(tree.item(sel[0], "values")[0])
        if not messagebox.askyesno("تأكيد", "حذف الفاتورة نهائيًا؟ سيتغير رصيد المخزون وحساب العميل/المورد."): return
        with db() as c:
            inv = c.execute("SELECT kind FROM invoices WHERE id=?", (inv_id,)).fetchone()
            if inv and inv["kind"] == "مشتريات":
                for l in c.execute("SELECT item_id,item_name,qty FROM invoice_lines WHERE invoice_id=?", (inv_id,)).fetchall():
                    stock = c.execute("""SELECT COALESCE(SUM(CASE WHEN i.kind='مشتريات' THEN x.qty ELSE -x.qty END),0) FROM invoice_lines x JOIN invoices i ON i.id=x.invoice_id WHERE x.item_id=?""", (l["item_id"],)).fetchone()[0]
                    if stock - l["qty"] < 0:
                        return messagebox.showerror("لا يمكن الحذف", f"حذف هذه الفاتورة سيجعل رصيد {l['item_name']} بالسالب (تم بيع جزء منه).")
            c.execute("DELETE FROM invoices WHERE id=?", (inv_id,))
        self.show_invoices()

    # ---------------- الإعدادات والنسخ الاحتياطي ----------------
    def show_settings(self):
        self.clear(); self.title_label("إعدادات بيانات الشركة على الفاتورة")
        with db() as c: s = c.execute("SELECT * FROM settings WHERE id=1").fetchone()
        form = tk.LabelFrame(self.body, text="بيانات رأس الفاتورة", padx=12, pady=12); form.pack(fill="x")
        self.settings_vars = {}
        for k, label in [("company", "اسم الشركة بالعربي"), ("english", "اسم الشركة بالإنجليزية"), ("address", "العنوان / الفرع"), ("phone", "رقم الهاتف"), ("taxno", "الرقم الضريبي (اختياري)")]:
            var = tk.StringVar(value=s[k] or ""); self.settings_vars[k] = var
            col = tk.Frame(form); col.pack(fill="x", pady=4); tk.Label(col, text=label, anchor="e").pack(fill="x"); ttk.Entry(col, textvariable=var, justify="right").pack(fill="x")
        ttk.Button(form, text="حفظ الإعدادات", command=self.save_settings).pack(anchor="e", pady=8)

    def save_settings(self):
        v = {k: x.get().strip() for k, x in self.settings_vars.items()}
        with db() as c: c.execute("UPDATE settings SET company=?,english=?,address=?,phone=?,taxno=? WHERE id=1", (v["company"], v["english"], v["address"], v["phone"], v["taxno"]))
        messagebox.showinfo("تم", "تم حفظ بيانات الشركة")

    def backup(self):
        target = filedialog.asksaveasfilename(title="حفظ نسخة احتياطية", defaultextension=".db", filetypes=[("قاعدة بيانات SQLite", "*.db")], initialfile=f"warehouse_backup_{date.today().isoformat()}.db")
        if target:
            with db() as c:
                dest = sqlite3.connect(target)
                c.backup(dest); dest.close()
            messagebox.showinfo("نسخة احتياطية", "تم حفظ النسخة الاحتياطية بنجاح")

if __name__ == "__main__":
    init_db()
    App().mainloop()
