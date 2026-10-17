# -*- coding: utf-8 -*-
"""
برنامج مخازن ومبيعات محلي لويندوز.
التخزين في SQLite داخل مجلد البرنامج؛ لا يحتاج إنترنت أو متصفح.
"""
import os, sys, sqlite3, subprocess, tempfile, webbrowser
from datetime import date
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# Store data in the user's local AppData folder so the installed app can save without admin rights.
APP_DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "WarehouseDesktop")
os.makedirs(APP_DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(APP_DATA_DIR, "warehouse.db")

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
        """)
        n = c.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
        if n == 0:
            c.execute("INSERT OR IGNORE INTO settings(id) VALUES(1)")

def fmt(n):
    return f"{float(n or 0):,.2f}"

def next_no(kind):
    prefix = "م" if kind == "مبيعات" else "ش"
    with db() as c:
        row = c.execute("SELECT number FROM invoices WHERE kind=? ORDER BY id DESC LIMIT 1", (kind,)).fetchone()
    if row:
        try: n = int(''.join(ch for ch in row['number'] if ch.isdigit())) + 1
        except: n = 1
    else: n = 102820 if kind == "مبيعات" else 1
    return f"{prefix}{n}"

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("سيستم المخازن والمبيعات")
        self.geometry("1180x760")
        self.minsize(980, 650)
        self.configure(bg="#eef3f8")
        self.style = ttk.Style(self)
        try: self.style.theme_use("clam")
        except: pass
        self.style.configure("TButton", padding=7, font=("Tahoma", 10))
        self.style.configure("TLabel", font=("Tahoma", 10), background="#eef3f8")
        self.style.configure("Treeview", font=("Tahoma", 10), rowheight=27)
        self.style.configure("Treeview.Heading", font=("Tahoma", 10, "bold"))
        self.current_lines = []
        self.invoice_kind = "مبيعات"
        self.build_shell()
        self.show_home()

    def build_shell(self):
        top = tk.Frame(self, bg="#123b67", height=78)
        top.pack(fill="x")
        tk.Label(top, text="سيستم المخازن والمبيعات", font=("Tahoma", 21, "bold"), fg="white", bg="#123b67").pack(side="right", padx=22, pady=18)
        tk.Label(top, text="يعمل بدون إنترنت • حفظ محلي تلقائي بقاعدة بيانات", font=("Tahoma", 10), fg="#d9eaff", bg="#123b67").pack(side="left", padx=22)
        nav = tk.Frame(self, bg="#dbe7f4")
        nav.pack(fill="x")
        for label, fn in [("الرئيسية", self.show_home), ("الأصناف", self.show_items), ("العملاء والموردون", self.show_parties), ("فاتورة مبيعات", lambda:self.show_invoice("مبيعات")), ("فاتورة مشتريات", lambda:self.show_invoice("مشتريات")), ("أرصدة الأصناف", self.show_stock), ("كشف الحساب", self.show_account), ("الفواتير", self.show_invoices), ("الإعدادات", self.show_settings), ("نسخة احتياطية", self.backup)]:
            ttk.Button(nav, text=label, command=fn).pack(side="right", padx=3, pady=7)
        self.body = tk.Frame(self, bg="#eef3f8")
        self.body.pack(fill="both", expand=True, padx=15, pady=14)
        self.status = tk.Label(self, text="جاهز — البيانات محفوظة على هذا الكمبيوتر", anchor="e", bg="#dbe7f4", fg="#173b60", font=("Tahoma", 9), padx=10, pady=6)
        self.status.pack(fill="x", side="bottom")

    def clear(self):
        for w in self.body.winfo_children(): w.destroy()

    def title_label(self, text):
        tk.Label(self.body, text=text, font=("Tahoma", 17, "bold"), bg="#eef3f8", fg="#123b67").pack(anchor="e", pady=(0,12))

    def show_home(self):
        self.clear(); self.title_label("الرئيسية")
        with db() as c:
            items=c.execute("SELECT COUNT(*) FROM items").fetchone()[0]
            sales=c.execute("SELECT COUNT(*) FROM invoices WHERE kind='مبيعات'").fetchone()[0]
            buys=c.execute("SELECT COUNT(*) FROM invoices WHERE kind='مشتريات'").fetchone()[0]
        row=tk.Frame(self.body,bg="#eef3f8"); row.pack(fill="x")
        for title,val in [("عدد الأصناف",items),("فواتير المبيعات",sales),("فواتير المشتريات",buys)]:
            card=tk.Frame(row,bg="white",highlightbackground="#cbd8e7",highlightthickness=1,padx=28,pady=22)
            card.pack(side="right",expand=True,fill="x",padx=7)
            tk.Label(card,text=title,bg="white",fg="#50647b",font=("Tahoma",11)).pack()
            tk.Label(card,text=str(val),bg="white",fg="#1762a5",font=("Tahoma",24,"bold")).pack(pady=8)
        tk.Label(self.body,text="طريقة الاستخدام: أضف الأصناف والعملاء/الموردين، ثم أنشئ فواتير المشتريات والمبيعات. كل عملية حفظ تُسجّل مباشرة في قاعدة البيانات.",wraplength=950,justify="right",bg="#eef3f8",font=("Tahoma",12)).pack(anchor="e",pady=30)
        tk.Label(self.body,text="مهم: استخدم زر «نسخة احتياطية» بانتظام واحفظ النسخة على فلاشة أو قرص آخر.",fg="#9b2c2c",bg="#eef3f8",font=("Tahoma",11,"bold")).pack(anchor="e")

    def tree(self, parent, columns, headings, widths=None):
        box=tk.Frame(parent); box.pack(fill="both",expand=True)
        t=ttk.Treeview(box,columns=columns,show="headings")
        for i,col in enumerate(columns):
            t.heading(col,text=headings[i],anchor="e")
            t.column(col,width=(widths[i] if widths else 130),anchor="e")
        y=ttk.Scrollbar(box,orient="vertical",command=t.yview); t.configure(yscrollcommand=y.set)
        t.pack(side="right",fill="both",expand=True); y.pack(side="left",fill="y")
        return t

    def show_items(self):
        self.clear(); self.title_label("إدارة الأصناف")
        form=tk.LabelFrame(self.body,text="بيانات الصنف",padx=10,pady=10); form.pack(fill="x",pady=(0,12))
        fields=[("code","كود الصنف"),("name","اسم الصنف"),("unit","الوحدة"),("buy","سعر الشراء"),("sell","سعر البيع")]
        self.item_vars={k:tk.StringVar(value="قطعة" if k=="unit" else "0" if k in ("buy","sell") else "") for k,_ in fields}
        for k,label in fields:
            col=tk.Frame(form); col.pack(side="right",expand=True,fill="x",padx=5)
            tk.Label(col,text=label,anchor="e").pack(fill="x")
            ttk.Entry(col,textvariable=self.item_vars[k],justify="right").pack(fill="x")
        actions=tk.Frame(form); actions.pack(fill="x",pady=8)
        ttk.Button(actions,text="حفظ الصنف",command=self.save_item).pack(side="right",padx=4)
        ttk.Button(actions,text="تفريغ الحقول",command=lambda:[v.set("قطعة" if k=="unit" else "0" if k in ("buy","sell") else "") for k,v in self.item_vars.items()]).pack(side="right",padx=4)
        self.items_tree=self.tree(self.body,("id","code","name","unit","buy","sell","stock"),("ID","الكود","اسم الصنف","الوحدة","سعر الشراء","سعر البيع","الرصيد"),[45,100,280,90,120,120,100])
        self.refresh_items()

    def stock_qty(self,item_id):
        with db() as c:
            r=c.execute("""SELECT COALESCE(SUM(CASE WHEN i.kind='مشتريات' THEN l.qty ELSE -l.qty END),0)
            FROM invoice_lines l JOIN invoices i ON i.id=l.invoice_id WHERE l.item_id=?""",(item_id,)).fetchone()
        return r[0]

    def save_item(self):
        v={k:x.get().strip() for k,x in self.item_vars.items()}
        if not v["name"]: return messagebox.showwarning("تنبيه","اسم الصنف مطلوب")
        try:
            with db() as c:
                c.execute("INSERT INTO items(code,name,unit,buy_price,sell_price) VALUES(?,?,?,?,?)",
                    (v["code"] or None,v["name"],v["unit"] or "قطعة",float(v["buy"] or 0),float(v["sell"] or 0)))
            self.status.config(text="تم حفظ الصنف")
            self.refresh_items()
        except sqlite3.IntegrityError: messagebox.showerror("خطأ","كود الصنف مستخدم بالفعل")
        except ValueError: messagebox.showerror("خطأ","راجع الأسعار؛ يجب أن تكون أرقامًا")

    def refresh_items(self):
        if not hasattr(self,"items_tree") or not self.items_tree.winfo_exists(): return
        for x in self.items_tree.get_children(): self.items_tree.delete(x)
        with db() as c: rows=c.execute("SELECT * FROM items ORDER BY name").fetchall()
        for r in rows:self.items_tree.insert("","end",values=(r["id"],r["code"] or "",r["name"],r["unit"],fmt(r["buy_price"]),fmt(r["sell_price"]),fmt(self.stock_qty(r["id"]))))

    def show_parties(self):
        self.clear(); self.title_label("العملاء والموردون")
        form=tk.LabelFrame(self.body,text="بيانات عميل / مورد",padx=10,pady=10);form.pack(fill="x",pady=(0,12))
        self.party_vars={k:tk.StringVar() for k in ("name","kind","phone","address","opening")}
        self.party_vars["kind"].set("عميل")
        for k,label in [("name","الاسم"),("kind","النوع"),("phone","الهاتف"),("address","العنوان"),("opening","الرصيد الافتتاحي")]:
            col=tk.Frame(form);col.pack(side="right",expand=True,fill="x",padx=5);tk.Label(col,text=label,anchor="e").pack(fill="x")
            if k=="kind": ttk.Combobox(col,textvariable=self.party_vars[k],values=["عميل","مورد","عميل/مورد"],state="readonly",justify="right").pack(fill="x")
            else: ttk.Entry(col,textvariable=self.party_vars[k],justify="right").pack(fill="x")
        ttk.Button(form,text="حفظ الاسم",command=self.save_party).pack(anchor="e",pady=8)
        self.parties_tree=self.tree(self.body,("id","name","kind","phone","address","opening"),("ID","الاسم","النوع","الهاتف","العنوان","الرصيد الافتتاحي"),[50,260,120,150,300,140])
        self.refresh_parties()

    def save_party(self):
        v={k:x.get().strip() for k,x in self.party_vars.items()}
        if not v["name"]:return messagebox.showwarning("تنبيه","الاسم مطلوب")
        try:
            with db() as c:c.execute("INSERT INTO parties(name,kind,phone,address,opening) VALUES(?,?,?,?,?)",(v["name"],v["kind"],v["phone"],v["address"],float(v["opening"] or 0)))
            self.refresh_parties();self.status.config(text="تم حفظ العميل / المورد")
        except ValueError:messagebox.showerror("خطأ","الرصيد الافتتاحي يجب أن يكون رقمًا")

    def refresh_parties(self):
        if not hasattr(self,"parties_tree") or not self.parties_tree.winfo_exists():return
        for x in self.parties_tree.get_children():self.parties_tree.delete(x)
        with db() as c:rows=c.execute("SELECT * FROM parties ORDER BY name").fetchall()
        for r in rows:self.parties_tree.insert("","end",values=(r["id"],r["name"],r["kind"],r["phone"],r["address"],fmt(r["opening"])))

    def show_invoice(self,kind):
        self.clear();self.invoice_kind=kind;self.current_lines=[]
        self.title_label("فاتورة "+kind)
        with db() as c:
            parties=c.execute("SELECT id,name FROM parties ORDER BY name").fetchall()
            items=c.execute("SELECT id,code,name,unit,buy_price,sell_price FROM items ORDER BY name").fetchall()
        form=tk.LabelFrame(self.body,text="بيانات الفاتورة",padx=10,pady=8);form.pack(fill="x")
        self.inv_no=tk.StringVar(value=next_no(kind));self.inv_date=tk.StringVar(value=date.today().isoformat());self.inv_party=tk.StringVar();self.inv_notes=tk.StringVar()
        self.party_lookup={f'{p["id"]} - {p["name"]}':p["id"] for p in parties}
        self.item_lookup={f'{p["id"]} - {p["name"]}':dict(p) for p in items}
        for key,label,var in [("no","رقم الفاتورة",self.inv_no),("date","التاريخ YYYY-MM-DD",self.inv_date),("party","العميل / المورد",self.inv_party),("notes","ملاحظات",self.inv_notes)]:
            col=tk.Frame(form);col.pack(side="right",expand=True,fill="x",padx=5);tk.Label(col,text=label,anchor="e").pack(fill="x")
            if key=="party":ttk.Combobox(col,textvariable=var,values=list(self.party_lookup),state="readonly",justify="right").pack(fill="x")
            else:ttk.Entry(col,textvariable=var,justify="right").pack(fill="x")
        add=tk.LabelFrame(self.body,text="إضافة صنف للفاتورة",padx=10,pady=8);add.pack(fill="x",pady=8)
        self.inv_item=tk.StringVar();self.inv_qty=tk.StringVar(value="1");self.inv_price=tk.StringVar(value="0")
        col=tk.Frame(add);col.pack(side="right",expand=True,fill="x",padx=5);tk.Label(col,text="الصنف").pack(anchor="e");cb=ttk.Combobox(col,textvariable=self.inv_item,values=list(self.item_lookup),state="readonly",justify="right");cb.pack(fill="x")
        def price_changed(_=None):
            item=self.item_lookup.get(self.inv_item.get())
            if item:self.inv_price.set(str(item["sell_price"] if kind=="مبيعات" else item["buy_price"]))
        cb.bind("<<ComboboxSelected>>",price_changed)
        for label,var in [("الكمية",self.inv_qty),("سعر الوحدة",self.inv_price)]:
            col=tk.Frame(add);col.pack(side="right",expand=True,fill="x",padx=5);tk.Label(col,text=label).pack(anchor="e");ttk.Entry(col,textvariable=var,justify="right").pack(fill="x")
        ttk.Button(add,text="إضافة الصنف",command=self.add_invoice_line).pack(side="right",padx=10,pady=15)
        self.inv_tree=self.tree(self.body,("name","qty","unit","price","total"),("الصنف","الكمية","الوحدة","سعر الوحدة","الإجمالي"),[380,120,100,150,160])
        bottom=tk.Frame(self.body,bg="#eef3f8");bottom.pack(fill="x",pady=8)
        self.inv_total_label=tk.Label(bottom,text="الإجمالي: 0.00 ج.م",font=("Tahoma",15,"bold"),fg="#123b67",bg="#eef3f8");self.inv_total_label.pack(side="right")
        ttk.Button(bottom,text="حذف آخر صنف",command=self.remove_invoice_line).pack(side="left",padx=4)
        ttk.Button(bottom,text="حفظ الفاتورة وطباعة نسختين",command=self.save_invoice).pack(side="left",padx=4)

    def add_invoice_line(self):
        item=self.item_lookup.get(self.inv_item.get())
        if not item:return messagebox.showwarning("تنبيه","اختر الصنف")
        try:qty=float(self.inv_qty.get());price=float(self.inv_price.get())
        except ValueError:return messagebox.showerror("خطأ","الكمية والسعر يجب أن يكونا أرقامًا")
        if qty<=0 or price<0:return messagebox.showerror("خطأ","الكمية يجب أن تكون أكبر من صفر والسعر غير سالب")
        if self.invoice_kind=="مبيعات":
            stock=self.stock_qty(item["id"])-sum(l["qty"] for l in self.current_lines if l["item_id"]==item["id"])
            if qty>stock:return messagebox.showwarning("رصيد غير كافٍ",f"الرصيد المتاح من {item['name']} هو {fmt(stock)}")
        self.current_lines.append({"item_id":item["id"],"name":item["name"],"unit":item["unit"],"qty":qty,"price":price})
        self.refresh_invoice_lines()

    def remove_invoice_line(self):
        if self.current_lines:self.current_lines.pop();self.refresh_invoice_lines()

    def refresh_invoice_lines(self):
        for x in self.inv_tree.get_children():self.inv_tree.delete(x)
        total=0
        for l in self.current_lines:
            amount=l["qty"]*l["price"];total+=amount
            self.inv_tree.insert("","end",values=(l["name"],fmt(l["qty"]),l["unit"],fmt(l["price"]),fmt(amount)))
        self.inv_total_label.config(text=f"الإجمالي: {fmt(total)} ج.م")

    def save_invoice(self):
        if not self.current_lines:return messagebox.showwarning("تنبيه","أضف صنفًا واحدًا على الأقل")
        party=self.party_lookup.get(self.inv_party.get())
        if not party:return messagebox.showwarning("تنبيه","اختر العميل أو المورد")
        kind=self.invoice_kind;number=self.inv_no.get().strip() or next_no(kind)
        try:
            date.fromisoformat(self.inv_date.get().strip())
            with db() as c:
                cur=c.execute("INSERT INTO invoices(number,kind,inv_date,party_id,notes) VALUES(?,?,?,?,?)",(number,kind,self.inv_date.get().strip(),party,self.inv_notes.get().strip()))
                inv_id=cur.lastrowid
                for l in self.current_lines:
                    if kind=="مبيعات":
                        stock=c.execute("""SELECT COALESCE(SUM(CASE WHEN i.kind='مشتريات' THEN x.qty ELSE -x.qty END),0) FROM invoice_lines x JOIN invoices i ON i.id=x.invoice_id WHERE x.item_id=?""",(l["item_id"],)).fetchone()[0]
                        if l["qty"]>stock:raise ValueError("الرصيد أصبح غير كافٍ للصنف "+l["name"])
                    c.execute("INSERT INTO invoice_lines(invoice_id,item_id,item_name,unit,qty,price) VALUES(?,?,?,?,?,?)",(inv_id,l["item_id"],l["name"],l["unit"],l["qty"],l["price"]))
            self.status.config(text=f"تم حفظ فاتورة {kind} رقم {number} في قاعدة البيانات")
            self.print_invoice(inv_id)
            self.show_invoice(kind)
        except sqlite3.IntegrityError:messagebox.showerror("خطأ","رقم الفاتورة موجود بالفعل؛ غيّر رقم الفاتورة")
        except ValueError as e:messagebox.showerror("خطأ",str(e) or "صيغة التاريخ غير صحيحة")

    def invoice_html(self,inv_id):
        with db() as c:
            inv=c.execute("SELECT i.*,p.id party_id,p.name party_name,p.phone party_phone,p.address party_address FROM invoices i LEFT JOIN parties p ON p.id=i.party_id WHERE i.id=?",(inv_id,)).fetchone()
            lines=c.execute("SELECT * FROM invoice_lines WHERE invoice_id=?",(inv_id,)).fetchall()
            settings=c.execute("SELECT * FROM settings WHERE id=1").fetchone()
            prior_rows=c.execute("""SELECT i.kind,COALESCE(SUM(l.qty*l.price),0) total
                FROM invoices i LEFT JOIN invoice_lines l ON l.invoice_id=i.id
                WHERE i.party_id=? AND (i.inv_date<? OR (i.inv_date=? AND i.id<?))
                GROUP BY i.id""",(inv["party_id"],inv["inv_date"],inv["inv_date"],inv_id)).fetchall()
        total=sum(x["qty"]*x["price"] for x in lines)
        prior=0.0
        with db() as c:
            party=c.execute("SELECT opening FROM parties WHERE id=?",(inv["party_id"],)).fetchone()
        prior=float(party["opening"] or 0)
        for r in prior_rows:
            prior += float(r["total"]) if r["kind"]=="مبيعات" else -float(r["total"])
        current = prior + (total if inv["kind"]=="مبيعات" else -total)
        def e(s):return str(s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
        rows="".join(f"<tr><td>{n}</td><td>{e(l['item_name'])}</td><td>{fmt(l['qty'])}</td><td>{e(l['unit'])}</td><td>{fmt(l['price'])}</td><td>{fmt(l['qty']*l['price'])}</td></tr>" for n,l in enumerate(lines,1))
        company = e(settings["company"]) or "اسم الشركة"
        english = e(settings["english"])
        address = e(settings["address"])
        phone = e(settings["phone"])
        # Two matching invoice copies side-by-side on one A4 landscape sheet.
        copy = f"""<section class="copy">
          <div class="head"><div class="brand"><h1>{company}</h1><div>{english}</div><div>{address}　 {phone}</div></div>
          <h2>فاتورة {e(inv['kind'])}　{e(inv['number'])}</h2></div>
          <div class="meta"><div>التاريخ: <b>{e(inv['inv_date'])}</b></div><div>اسم الحساب: <b>{e(inv['party_name'])}</b></div><div>الهاتف: {e(inv['party_phone'])}</div></div>
          <table><thead><tr><th>م</th><th>اسم الصنف</th><th>الكمية</th><th>الوحدة</th><th>السعر</th><th>الإجمالي</th></tr></thead><tbody>{rows}</tbody></table>
          <div class="sum"><div>الإجمالي: {fmt(total)} ج.م</div><div>الخصم: 0.00 ج.م</div><div>الصافي: {fmt(total)} ج.م</div></div>
          <div class="balance"><div>الرصيد السابق: {fmt(prior)} ج.م</div><div>الرصيد الحالي: {fmt(current)} ج.م</div></div>
          <div class="notes">ملاحظات: {e(inv['notes'])}</div>
          <div class="sign"><span>توقيع المستلم</span><span>توقيع البائع</span></div>
        </section>"""
        return f"""<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8"><title>فاتورة {e(inv['number'])}</title><style>
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

    def print_invoice(self,inv_id):
        html=self.invoice_html(inv_id)
        path=os.path.join(APP_DIR,f"فاتورة_{inv_id}.html")
        with open(path,"w",encoding="utf-8") as f:f.write(html)
        # Open the generated printable invoice; it is a local file and does not require internet.
        try: os.startfile(path)
        except: webbrowser.open("file:///"+path.replace("\\","/"))
        messagebox.showinfo("تم الحفظ","تم حفظ الفاتورة في قاعدة البيانات. افتح نافذة الفاتورة ثم اطبعها مرتين من Ctrl+P إذا أردت نسختين.")

    def show_stock(self):
        self.clear();self.title_label("أرصدة الأصناف")
        tree=self.tree(self.body,("code","name","unit","buy","sell","stock"),("الكود","اسم الصنف","الوحدة","إجمالي المشتريات","إجمالي المبيعات","الرصيد الحالي"),[100,300,100,170,170,150])
        with db() as c:items=c.execute("SELECT * FROM items ORDER BY name").fetchall()
        for i in items:
            with db() as c:
                r=c.execute("""SELECT COALESCE(SUM(CASE WHEN inv.kind='مشتريات' THEN l.qty ELSE 0 END),0) p,COALESCE(SUM(CASE WHEN inv.kind='مبيعات' THEN l.qty ELSE 0 END),0) s FROM invoice_lines l JOIN invoices inv ON inv.id=l.invoice_id WHERE l.item_id=?""",(i["id"],)).fetchone()
            tree.insert("","end",values=(i["code"] or "",i["name"],i["unit"],fmt(r["p"]),fmt(r["s"]),fmt(r["p"]-r["s"])))

    def show_account(self):
        self.clear();self.title_label("كشف حساب عميل / مورد")
        with db() as c:parties=c.execute("SELECT * FROM parties ORDER BY name").fetchall()
        self.account_lookup={f'{p["id"]} - {p["name"]}':p["id"] for p in parties}
        form=tk.Frame(self.body,bg="#eef3f8");form.pack(fill="x",pady=5)
        self.acc_party=tk.StringVar();self.acc_from=tk.StringVar(value=date.today().replace(day=1).isoformat());self.acc_to=tk.StringVar(value=date.today().isoformat())
        for label,var,values in [("الاسم",self.acc_party,list(self.account_lookup)),("من تاريخ",self.acc_from,None),("إلى تاريخ",self.acc_to,None)]:
            col=tk.Frame(form,bg="#eef3f8");col.pack(side="right",expand=True,fill="x",padx=5);tk.Label(col,text=label,bg="#eef3f8").pack(anchor="e")
            if values is not None:ttk.Combobox(col,textvariable=var,values=values,state="readonly",justify="right").pack(fill="x")
            else:ttk.Entry(col,textvariable=var,justify="right").pack(fill="x")
        ttk.Button(form,text="عرض الكشف",command=self.render_account).pack(side="right",padx=8,pady=20)
        self.acc_result=tk.Frame(self.body,bg="#eef3f8");self.acc_result.pack(fill="both",expand=True)

    def render_account(self):
        for w in self.acc_result.winfo_children():w.destroy()
        pid=self.account_lookup.get(self.acc_party.get())
        if not pid:return messagebox.showwarning("تنبيه","اختر الاسم")
        with db() as c:
            party=c.execute("SELECT * FROM parties WHERE id=?",(pid,)).fetchone()
            rows=c.execute("SELECT i.*,COALESCE(SUM(l.qty*l.price),0) total FROM invoices i LEFT JOIN invoice_lines l ON l.invoice_id=i.id WHERE i.party_id=? AND i.inv_date BETWEEN ? AND ? GROUP BY i.id ORDER BY i.inv_date,i.id",(pid,self.acc_from.get(),self.acc_to.get())).fetchall()
        tree=self.tree(self.acc_result,("date","number","kind","debit","credit","balance"),("التاريخ","رقم الفاتورة","البيان","مدين","دائن","الرصيد"),[120,140,140,140,140,140])
        running=float(party["opening"] or 0)
        for r in rows:
            debit=float(r["total"]) if r["kind"]=="مبيعات" else 0
            credit=float(r["total"]) if r["kind"]=="مشتريات" else 0
            running+=debit-credit
            tree.insert("","end",values=(r["inv_date"],r["number"],r["kind"],fmt(debit),fmt(credit),fmt(running)))
        tk.Label(self.acc_result,text=f"الرصيد الختامي: {fmt(running)} ج.م",font=("Tahoma",14,"bold"),bg="#eef3f8",fg="#123b67").pack(anchor="e",pady=8)

    def show_invoices(self):
        self.clear();self.title_label("سجل الفواتير")
        with db() as c:rows=c.execute("SELECT i.id,i.number,i.kind,i.inv_date,p.name party,COALESCE(SUM(l.qty*l.price),0) total FROM invoices i LEFT JOIN parties p ON p.id=i.party_id LEFT JOIN invoice_lines l ON l.invoice_id=i.id GROUP BY i.id ORDER BY i.id DESC").fetchall()
        tree=self.tree(self.body,("id","kind","number","date","party","total"),("ID","النوع","رقم الفاتورة","التاريخ","العميل / المورد","الإجمالي"),[45,100,130,130,300,150])
        for r in rows:tree.insert("","end",values=(r["id"],r["kind"],r["number"],r["inv_date"],r["party"] or "",fmt(r["total"])))
        ttk.Button(self.body,text="طباعة الفاتورة المحددة",command=lambda:self.print_selected(tree)).pack(anchor="e",pady=8)

    def print_selected(self,tree):
        sel=tree.selection()
        if not sel:return messagebox.showwarning("تنبيه","حدد فاتورة أولًا")
        self.print_invoice(tree.item(sel[0],"values")[0])

    def show_settings(self):
        self.clear();self.title_label("إعدادات بيانات الشركة على الفاتورة")
        with db() as c:s=c.execute("SELECT * FROM settings WHERE id=1").fetchone()
        form=tk.LabelFrame(self.body,text="بيانات رأس الفاتورة",padx=12,pady=12);form.pack(fill="x")
        self.settings_vars={}
        for k,label in [("company","اسم الشركة بالعربي"),("english","اسم الشركة بالإنجليزية"),("address","العنوان / الفرع"),("phone","رقم الهاتف"),("taxno","الرقم الضريبي (اختياري)")]:
            var=tk.StringVar(value=s[k] or "");self.settings_vars[k]=var
            col=tk.Frame(form);col.pack(fill="x",pady=4);tk.Label(col,text=label,anchor="e").pack(fill="x");ttk.Entry(col,textvariable=var,justify="right").pack(fill="x")
        ttk.Button(form,text="حفظ الإعدادات",command=self.save_settings).pack(anchor="e",pady=8)

    def save_settings(self):
        v={k:x.get().strip() for k,x in self.settings_vars.items()}
        with db() as c:c.execute("UPDATE settings SET company=?,english=?,address=?,phone=?,taxno=? WHERE id=1",(v["company"],v["english"],v["address"],v["phone"],v["taxno"]))
        messagebox.showinfo("تم","تم حفظ بيانات الشركة")

    def backup(self):
        target=filedialog.asksaveasfilename(title="حفظ نسخة احتياطية",defaultextension=".db",filetypes=[("قاعدة بيانات SQLite","*.db")],initialfile="warehouse_backup.db")
        if target:
            with db() as c:
                dest=sqlite3.connect(target)
                c.backup(dest);dest.close()
            messagebox.showinfo("نسخة احتياطية","تم حفظ النسخة الاحتياطية بنجاح")

if __name__=="__main__":
    init_db()
    App().mainloop()
