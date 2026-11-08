/* سيستم المخازن والمبيعات — النسخة الأوفلاين (نفس واجهة زلط). */
"use strict";

/* ===================== الاتصال بالبرنامج ===================== */
function pyReady() {
  return new Promise((res) => {
    if (window.pywebview && window.pywebview.api) return res(true);
    if (window.ZALAT_WEB) return res(false);                                   // الموقع (من المتصفح أو الموبايل)
    // البرنامج على الجهاز كمان بيفتح من http://127.0.0.1 (سيرفر pywebview) — فنستنى الـ api بدل ما نفتكره موقع
    window.addEventListener("pywebviewready", () => res(true), { once: true });
    const t0 = Date.now(), poll = setInterval(() => {
      if (window.pywebview && window.pywebview.api && window.pywebview.api.call) { clearInterval(poll); res(true); }
      else if (Date.now() - t0 > 15000) { clearInterval(poll); res(false); }
    }, 100);
  });
}
let IN_APP = false;
async function api(name, ...args) {
  let r;
  if (IN_APP) r = await window.pywebview.api.call(name, args);
  else {
    const resp = await fetch("/api/" + name, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(args) });
    r = await resp.json();
  }
  if (r && r.print_html) printHtml(r.print_html);
  if (r && r.__error === "__LOGIN__") {                                          // الجلسة خلصت: يرجع لشاشة الدخول
    S.me = null; if (S.boot) renderLogin(); throw new Error("الجلسة خلصت — ادخل تاني");
  }
  if (r && r.__error !== undefined) {
    const msg = String(r.__error);
    if (msg.startsWith(DAYLOCK) && name !== "day_unlock") {          // يوم مقفول: باسوورد المحاسب أو المالك وبعدين نعيد نفس الطلب
      if (await askDayPassword(msg.slice(DAYLOCK.length))) return api(name, ...args);
      throw new Error("اتلغى — اليوم مقفول");
    }
    throw new Error(msg === "unknown" ? "أمر مش معروف: " + name : msg);
  }
  if (/^(save_|delete_|add_|close_day|pay_)/.test(name)) setTimeout(loadTodayBar, 150);
  if (/^(save_invoice|save_voucher|req_decide|rep_checkin)$/.test(name) && S.me && !S.me.rep) setTimeout(loadReqCount, 200);
  return r ? r.result : null;
}
function printHtml(html) {                     // من الموقع: الطباعة من المتصفح نفسه
  const w = window.open("", "_blank");
  if (!w) return toast("المتصفح منع فتح صفحة الطباعة — اسمح بالنوافذ المنبثقة", "err", 5000);
  w.document.open(); w.document.write(html); w.document.close();
  setTimeout(() => { try { w.focus(); w.print(); } catch (e) { } }, 400);
}
let TB_BUSY = false;
async function loadTodayBar() {
  const el = $("#todaybar"); if (!el || TB_BUSY || !S.me) return;
  TB_BUSY = true;
  try {
    const t = await api("today_bar");
    const lu = $("#last-up b"); if (lu) lu.textContent = new Date().toLocaleTimeString("ar-EG", { hour: "2-digit", minute: "2-digit" });
    const it = (label, v, cls = "") => h("span", { class: "tb-i " + cls }, label, h("b", null, v));
    el.replaceChildren(h("b", { class: "tb-h" }, "اليوم"), it("عدد فواتير اليوم:", String(t.count)), it("مبيعات:", fmt(t.sales)),
      t.n_buys ? it("مشتريات:", fmt(t.buys)) : null, t.ret ? it("مرتجع مبيعات:", fmt(t.ret)) : null,
      it("تحصيلات:", fmt(t.collections)), t.expenses ? it("مصروفات:", fmt(t.expenses)) : null,
      h("span", { style: { flex: 1 } }), t.closed ? h("span", { class: "tb-closed" }, icon("lock", 15), "اليوم متقفل") : null);
  } catch (e) { } finally { TB_BUSY = false; }
}
const DAYLOCK = "__DAYLOCK__";
async function askDayPassword(msg) {
  while (true) {
    const pw = await promptBox(msg + "\n\nاكتب باسوورد المحاسب أو المالك علشان تكمّل:", "🔒 اليوم مقفول", { password: true });
    if (pw === null) return false;
    try { await api("day_unlock", pw); toast("✔ اتفتح للتعديل 10 دقايق", "ok"); return true; } catch (e) { toast(e.message, "err"); }
  }
}

/* الحذف في العملاء/الموظفين/الأصناف/الحسابات: تأكيد + باسوورد المحاسب أو المالك */
async function askDelPw(msg) {
  const pw = await promptBox(msg + "\n\nاكتب باسوورد المحاسب أو المالك علشان تحذف:", "🔒 حذف", { password: true });
  return pw === null || pw === "" ? null : pw;
}

/* ===================== أدوات ===================== */
// replaceChildren بتقبل قوايم وبتتجاهل الفاضي (null/false) — زي h() بالظبط
{ const rc = Element.prototype.replaceChildren;
  Element.prototype.replaceChildren = function (...kids) { return rc.apply(this, kids.flat(Infinity).filter((k) => k !== null && k !== undefined && k !== false)); }; }
const $ = (s, el = document) => el.querySelector(s);
function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  if (attrs) for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2).toLowerCase(), v);
    else if (k === "html") el.innerHTML = v;
    else if (v === true) el.setAttribute(k, "");
    else el.setAttribute(k, v);
  }
  for (const c of kids.flat(Infinity)) {
    if (c === null || c === undefined || c === false) continue;
    el.appendChild(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}
const NF = new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const fmt = (n) => NF.format(Number(n) || 0);
const fq = (n) => { const x = Number(n) || 0; return Number.isInteger(x) ? String(x) : NF.format(x); };
const num = (s) => { const t = String(s ?? "").replace(/[٠-٩]/g, (d) => "٠١٢٣٤٥٦٧٨٩".indexOf(d)).replace(/[٫]/g, ".").replace(/,/g, "").trim(); return t === "" ? 0 : Number(t); };
function norm(s) {
  return String(s || "").toLowerCase().replace(/[أإآٱ]/g, "ا").replace(/ة/g, "ه").replace(/ى/g, "ي").replace(/ؤ/g, "و").replace(/ئ/g, "ي")
    .replace(/[ً-ْـ]/g, "").replace(/\s+/g, " ").trim();
}
const BAGS_PER_TON = 20;
function qtyText(lines) {
  let bags = 0, tons = 0;
  for (const l of lines) {
    const u = l.unit || "";
    if (u.includes("طن")) { tons += +l.qty; bags += l.qty * BAGS_PER_TON; }
    else if (u.includes("شك") || u.includes("شيك")) { bags += +l.qty; tons += l.qty / BAGS_PER_TON; }
  }
  return `${fmt(tons)} طن (${fmt(bags)} شيكارة)`;
}
function store(k, v) { try { if (v === undefined) return JSON.parse(localStorage.getItem("zalat." + k)); localStorage.setItem("zalat." + k, JSON.stringify(v)); } catch (e) { return null; } }
function fitNum(el) { const n = el.textContent.length; el.classList.toggle("long", n > 11 && n <= 14); el.classList.toggle("xlong", n > 14); }
function countUp(el, to, money = true) {
  const fin = money ? fmt(to) : String(Math.round(to)); el.textContent = fin; fitNum(el);
  const start = performance.now(), dur = 900, from = 0;
  const f = (t) => {
    const p = Math.min(1, (t - start) / dur), e = 1 - Math.pow(1 - p, 3), v = from + (to - from) * e;
    el.textContent = p >= 1 ? fin : money ? fmt(v) : Math.round(v);
    if (p < 1) requestAnimationFrame(f);
  };
  requestAnimationFrame(f);
}
const kindClass = (k) => (k.startsWith("مرتجع") ? "k-مرتجع" : "k-" + k);

/* ===================== أيقونات ===================== */
const ICONS = {
  home: "M3 11 12 3l9 8M5 10v10h5v-6h4v6h5V10",
  sale: "M7 17 17 7M9 7h8v8",
  buy: "M17 7 7 17M15 17H7V9",
  ret: "M9 14 4 9l5-5M4 9h11a5 5 0 0 1 0 10h-3",
  list: "M6 2h12v20l-3-2-3 2-3-2-3 2V2ZM9 7h6M9 11h6M9 15h4",
  inbox: "M22 12h-6l-2 3h-4l-2-3H2M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z",
  box: "M21 8 12 3 3 8v8l9 5 9-5V8ZM3 8l9 5 9-5M12 13v8",
  bell: "M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10.3 21a1.94 1.94 0 0 0 3.4 0",
  chart: "M4 20V10M10 20V4M16 20v-7M22 20H2",
  cash: "M3 6h18v12H3zM3 10h18M7 14h4",
  menu: "M4 6h16M4 12h16M4 18h16",
  x: "M6 6l12 12M18 6 6 18",
  plus: "M12 5v14M5 12h14",
  edit: "M4 20h4L19 9l-4-4L4 16v4ZM13.5 6.5l4 4",
  trash: "M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13",
  print: "M7 9V3h10v6M7 17H4v-7h16v7h-3M7 14h10v7H7z",
  save: "M5 3h11l3 3v15H5zM8 3v5h7M8 21v-7h8v7",
  refresh: "M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7",
  phone: "M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.7 2Z",
  calc: "M6 2h12a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2ZM8 6h8v4H8zM8 14h.01M12 14h.01M16 14h.01M8 18h.01M12 18h.01M16 18h.01",
  check: "M5 12l5 5L20 7",
  lock: "M5 11h14v10H5zM8 11V7a4 4 0 0 1 8 0v4M12 15v2",
  undo: "M9 14 4 9l5-5M4 9h11a5 5 0 0 1 0 10h-3",
  logout: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9",
  users: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8",
  truck: "M3 6h11v10H3zM14 9h4l3 3v4h-7M7.5 19a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3ZM17.5 19a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z",
};
function icon(name, size = 20, cls = "") {
  const ns = "http://www.w3.org/2000/svg";
  const s = document.createElementNS(ns, "svg");
  s.setAttribute("width", size); s.setAttribute("height", size); s.setAttribute("viewBox", "0 0 24 24");
  s.setAttribute("fill", "none"); s.setAttribute("stroke", "currentColor"); s.setAttribute("stroke-width", "1.9");
  s.setAttribute("stroke-linecap", "round"); s.setAttribute("stroke-linejoin", "round"); s.setAttribute("aria-hidden", "true");
  if (cls) s.setAttribute("class", cls);
  const p = document.createElementNS(ns, "path"); p.setAttribute("d", ICONS[name] || ""); s.appendChild(p);
  return s;
}

/* ===================== رسايل ونوافذ ===================== */
function toast(text, kind = "", ms = 3200, action = null) {
  const t = h("div", { class: "toast " + kind, role: "status" }, text);
  if (action) {
    const b = h("button", { class: "btn ghost", style: { color: "#fde68a", minHeight: "30px", marginInlineStart: "10px" }, onclick: () => { action.fn(); close(); } }, action.label);
    t.appendChild(b);
  }
  $("#toasts").appendChild(t);
  const close = () => { t.classList.add("out"); setTimeout(() => t.remove(), 300); };
  setTimeout(close, ms);
}
let MODALS = 0; const MODAL_STACK = [];
function modal({ title, body, actions = [], wide = false, onClose, enter = true }) {
  return new Promise((resolve) => {
    MODALS++;
    const done = (v) => { if (!wrap.isConnected) return; MODALS--; const k = MODAL_STACK.indexOf(box); if (k >= 0) MODAL_STACK.splice(k, 1); wrap.remove(); document.removeEventListener("keydown", key, true); if (onClose) onClose(v); resolve(v); };
    const box = h("div", { class: "modal" + (wide ? " wide" : ""), role: "dialog", "aria-modal": "true", "aria-label": title },
      h("div", { class: "hd" }, h("h2", null, title), h("button", { class: "btn ghost icon-btn", "aria-label": "قفل", onclick: () => done(null) }, icon("x"))),
      h("div", { class: "bd" }, body),
      actions.length ? h("div", { class: "ft" }, actions.map((a) => h("button", { class: "btn " + (a.cls || ""), onclick: async () => { const v = a.value ? await a.value() : a.ret; if (v !== undefined && v !== false) done(v); } }, a.icon ? icon(a.icon, 18) : null, a.label))) : null);
    const wrap = h("div", { class: "modal-wrap", onmousedown: (e) => { if (e.target === wrap) done(null); } }, box);
    const key = (e) => {
      if (MODAL_STACK[MODAL_STACK.length - 1] !== box) return;      // بس النافذة اللي فوق خالص
      if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); done(null); }
      if (e.key === "Enter" && enter && !e.shiftKey && actions.length && e.target.tagName !== "TEXTAREA" && e.target.tagName !== "BUTTON") {
        e.preventDefault(); e.stopPropagation(); box.querySelector(".ft .btn:first-child").click();
      }
    };
    document.addEventListener("keydown", key, true);
    $("#modal-root").appendChild(wrap); MODAL_STACK.push(box);
    setTimeout(() => { const f = box.querySelector("input,select,textarea") || box.querySelector(".ft .btn"); if (f) f.focus(); }, 60);
    box._done = done;
  });
}
const alertBox = (msg, title = "تنبيه") => modal({ title, body: h("div", { class: "msg" }, msg), actions: [{ label: "تمام", cls: "primary", ret: true }] });
const confirmBox = (msg, title = "تأكيد", yes = "أيوه") => modal({ title, body: h("div", { class: "msg" }, msg), actions: [{ label: yes, cls: "primary", ret: true }, { label: "لأ", ret: false, value: () => null }] }).then((v) => v === true);
function promptBox(msg, title, { password = false, value = "" } = {}) {
  const inp = h("input", { class: "in", type: password ? "password" : "text", value, "aria-label": title });
  return modal({ title, body: [h("div", { class: "msg" }, msg), inp], actions: [{ label: "تمام", cls: "primary", value: () => inp.value }, { label: "إلغاء", value: () => null }] });
}
async function askOwner(msg) {
  while (true) {
    const pw = await promptBox(msg + "\n\nاكتب كلمة سر المالك علشان تكمّل:", "مقفول — كلمة سر المالك", { password: true });
    if (pw === null) return null;
    try { await api("verify_owner", pw); return pw; } catch (e) { toast(e.message, "err"); }
  }
}

/* ===================== قايمة بحث (العميل / الصنف) ===================== */
function combo({ items, placeholder = "", label, sub, onPick, id }) {
  let list = null, act = 0, shown = [], chosen = null;
  const input = h("input", { class: "in", placeholder, autocomplete: "off", id, role: "combobox", "aria-label": label, "aria-expanded": "false" });
  const wrap = h("div", { class: "combo" }, input);
  const close = () => { if (list) { list.remove(); list = null; input.setAttribute("aria-expanded", "false"); } };
  const mark = (text, words) => {
    if (!words.length) return [text];
    const n = norm(text); let best = -1, w = "";
    for (const x of words) { const i = n.indexOf(x); if (i >= 0 && (best < 0 || i < best)) { best = i; w = x; } }
    if (best < 0 || norm(text).length !== text.length) return [text];
    return [text.slice(0, best), h("mark", null, text.slice(best, best + w.length)), text.slice(best + w.length)];
  };
  const open = () => {
    const q = norm(input.value), words = q ? q.split(" ") : [];
    // الترتيب: الاسم بالظبط ← الاسم بيبدأ بيه ← كلمة كاملة ← أي جزء (وبعدين الأقصر)
    const B = (s, i, len) => (i === 0 || s[i - 1] === " ") && (i + len === s.length || " -—[(".includes(s[i + len]));
    const score = (it) => {
      const nm = norm(it.name || it.label), lb = norm(it.label), code = norm(it.code || "");
      if (nm === q || code === q || String(it.id) === q) return 0;
      if (nm.startsWith(q) && B(nm, 0, q.length)) return 1;
      const i = lb.indexOf(q);
      if (i >= 0 && B(lb, i, q.length)) return 2;
      if (nm.startsWith(q)) return 3;
      return i >= 0 ? 4 : 5;
    };
    shown = items().filter((it) => { const n = norm(it.label); return words.every((w) => n.includes(w)); });
    if (q) shown = shown.map((it) => [score(it), it.label.length, it]).sort((a, b) => a[0] - b[0] || a[1] - b[1]).map((x) => x[2]);
    shown = shown.slice(0, 80);
    act = 0; close();
    list = h("div", { class: "list", role: "listbox" });
    if (!shown.length) list.appendChild(h("div", { class: "none" }, "مفيش نتايج"));
    shown.forEach((it, i) => {
      const o = h("div", { class: "opt" + (i === 0 ? " act" : ""), role: "option", onmousedown: (e) => { e.preventDefault(); pick(it, true); } },
        h("span", null, mark(it.label, words)), sub ? h("small", null, sub(it)) : null);
      list.appendChild(o);
    });
    wrap.appendChild(list); input.setAttribute("aria-expanded", "true");
  };
  const setAct = (i) => {
    if (!list || !shown.length) return;
    act = (i + shown.length) % shown.length;
    [...list.children].forEach((c, j) => c.classList.toggle("act", j === act));
    list.children[act].scrollIntoView({ block: "nearest" });
  };
  const pick = (it, advance) => { chosen = it; input.value = it.label; input.classList.remove("bad"); close(); if (onPick) onPick(it, advance); };
  input.addEventListener("input", () => { chosen = null; open(); });
  input.addEventListener("focus", () => { if (!chosen && input.value.trim()) open(); });   // فتح الشاشة مش بيفتح القايمة لوحده
  input.addEventListener("mousedown", () => { if (!list && !chosen) setTimeout(open, 0); });
  input.addEventListener("blur", () => setTimeout(close, 120));
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); if (!list) open(); else setAct(act + 1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setAct(act - 1); }
    else if (e.key === "Escape" && list) { e.preventDefault(); e.stopPropagation(); close(); }
    else if (e.key === "Enter") {
      if (list && shown.length) { e.preventDefault(); e.stopPropagation(); pick(shown[act], true); }
      else if (!chosen) { e.preventDefault(); e.stopPropagation(); input.classList.add("bad", "shake"); setTimeout(() => input.classList.remove("shake"), 500); }
    } else if (e.key === "Backspace" && chosen && input.selectionStart === input.value.length) {
      e.preventDefault(); chosen = null; input.value = ""; if (onPick) onPick(null); open();
    }
  });
  return { el: wrap, input, get: () => chosen, set: (it) => { chosen = it; input.value = it ? it.label : ""; }, focus: () => input.focus(), close };
}

/* Enter = الخانة اللي بعدها */
function enterChain(inputs, last) {
  inputs.forEach((el, i) => {
    el.addEventListener("keydown", (e) => {
      if (e.key !== "Enter" || e.defaultPrevented) return;
      const nx = inputs[i + 1];
      if (!nx && !last) return;          // آخر خانة في فورم: Enter يعمل submit عادي
      e.preventDefault();
      if (nx) { nx.focus(); if (nx.select) nx.select(); } else if (last) last();
    });
  });
}

/* ===================== الحالة ===================== */
const S = { boot: null, me: null, screen: "home", mini: store("mini") !== false, drafts: {}, expected: [], dirty: false };
const SCREENS = {
  home: { title: "الرئيسية", icon: "home" },
  "inv:مبيعات": { title: "فاتورة مبيعات", icon: "sale", key: "F1" },
  "inv:مشتريات": { title: "فاتورة مشتريات", icon: "buy", key: "F2" },
  "inv:مرتجع مبيعات": { title: "مرتجع مبيعات", icon: "ret" },
  "inv:مرتجع مشتريات": { title: "مرتجع مشتريات", icon: "ret" },
  log: { title: "سجل الفواتير", icon: "list", key: "F3" },
  "vch:new": { title: "سند جديد", icon: "cash", key: "F6" },
  "vch:log": { title: "سجل السندات", icon: "list", key: "F7" },
  "acc:statement": { title: "كشف الحساب", icon: "list" },
  "acc:balances": { title: "أرصدة الحسابات", icon: "calc", key: "Ctrl+B" },
  "acc:cash": { title: "الخزنة", icon: "cash" },
  "par:list": { title: "العملاء والموردون", icon: "users" },
  "itm:list": { title: "الأصناف", icon: "box" },
  "itm:stock": { title: "أرصدة الأصناف", icon: "box", key: "Ctrl+I" },
  "itm:sales": { title: "المبيعات (لكل صنف)", icon: "sale" },
  "itm:buys": { title: "المشتريات (لكل صنف)", icon: "buy" },
  "itm:damaged": { title: "الهالك والتالف", icon: "trash" },
  "smp:items": { title: "أصناف العينات", icon: "box" },
  "smp:out": { title: "عينات مبيعات", icon: "sale" },
  "smp:in": { title: "عينات مشتريات", icon: "buy" },
  "acc:subcash": { title: "الصندوق الفرعي", icon: "cash" },
  "acc:assets": { title: "الأصول وأرباح الملاك 🔒", icon: "box" },
  "rep:daily": { title: "التقرير اليومي", icon: "chart" },
  "rep:monthly": { title: "التقرير الشهري 🔒", icon: "chart" },
  "rep:profit": { title: "تقرير الأرباح 🔒", icon: "chart" },
  "rep:reps": { title: "تقرير المناديب", icon: "users" },
  "rep:targets": { title: "تارجت المناديب", icon: "chart" },
  "rep:log": { title: "سجل النشاط", icon: "list" },
  "emp:list": { title: "الموظفون", icon: "users" },
  "emp:att": { title: "الحضور والغياب", icon: "check" },
  "emp:attlog": { title: "سجل الحضور", icon: "list" },
  "emp:attreq": { title: "حضور المناديب بالموقع", icon: "phone" },
  "emp:repreq": { title: "طلبات تحصيل المناديب", icon: "phone" },
  "emp:veh": { title: "العربيات", icon: "truck" },
  "set:main": { title: "الإعدادات", icon: "edit" },
  "req": { title: "طلبات المناديب", icon: "check" },
  "set:users": { title: "المستخدمين وكلمات السر 🔒", icon: "users" },
};

/* ===================== التشغيل ===================== */
/* آيفون (أيقونة على الشاشة الرئيسية): iOS ساعات بيقصّر الشاشة بارتفاع شريط الساعة فيفضل فراغ فاتح تحت.
   بنكتشفه ونلوّن اللي تحت كحلي عشان يبان كمّلة لشريط «اليوم». */
function fixIosGap() {
  const sa = window.navigator.standalone || (window.matchMedia && matchMedia("(display-mode: standalone)").matches);
  document.documentElement.classList.toggle("standalone", !!sa);
  const portrait = innerHeight > innerWidth;
  const gap = sa && portrait ? Math.round(screen.height - innerHeight) : 0;
  document.documentElement.classList.toggle("ios-gap", gap > 20);
}
addEventListener("resize", fixIosGap); addEventListener("orientationchange", () => setTimeout(fixIosGap, 300));
async function start() {
  fixIosGap();
  $("#app").replaceChildren(h("div", { class: "loading" }, h("div", { class: "spin" })));
  IN_APP = await pyReady();
  try { S.boot = await api("boot"); } catch (e) { return fatal(e.message); }
  if (S.boot.db_error) return fatal("السيرفر مش متاح:\n" + S.boot.db_error + "\n\nاتأكد إن جهاز السيرفر شغال، وبعدين اقفل البرنامج وافتحه تاني.");
  document.title = S.boot.company;
  if (S.boot.web) {                                   // الموقع: لو لسه داخل (الجلسة شغالة) يكمّل على طول
    try { const m = await api("me"); if (m && m.id) { S.me = m; S.screen = firstScreen(); return renderShell(); } } catch (e) { }
  }
  renderLogin();
}
function fatal(msg) {
  $("#app").replaceChildren(h("div", { class: "login" }, h("div", { class: "box" }, h("b", { style: { fontSize: "20px", color: "var(--navy)" } }, "مش قادر يفتح"), h("div", { class: "msg" }, msg),
    h("button", { class: "btn primary", onclick: start }, icon("refresh", 18), "حاول تاني"),
    h("button", { class: "btn", onclick: () => serverSettings(true) }, icon("edit", 18), "إعدادات الاتصال بالسيرفر"))));
}

function renderLogin() {
  if (!S.boot.has_users) {
    const n = h("input", { class: "in", "aria-label": "اسم المستخدم" }), p1 = h("input", { class: "in", type: "password", "aria-label": "كلمة السر" }), p2 = h("input", { class: "in", type: "password", "aria-label": "تأكيد كلمة السر" });
    const err = h("div", { class: "err", role: "alert" });
    const box = h("form", { class: "box", onsubmit: async (e) => { e.preventDefault(); try { S.me = await api("first_owner", n.value, p1.value, p2.value); S.screen = firstScreen(); renderShell(); } catch (x) { err.textContent = x.message; } } },
      h("div", { class: "logo" }, h("img", { src: S.boot.logo, alt: "" }), h("b", null, S.boot.company)),
      h("div", { class: "msg", style: { textAlign: "center", color: "var(--red)" } }, "أول مرة: اعمل حساب المالك (ليه كل الصلاحيات).\n⚠️ اكتب كلمة السر في مكان آمن — مفيش طريقة استرجاع."),
      h("label", { class: "fld" }, "اسم المستخدم", n), h("label", { class: "fld" }, "كلمة السر", p1), h("label", { class: "fld" }, "تأكيد كلمة السر", p2), err,
      h("button", { class: "btn primary", type: "submit", style: { minHeight: "48px" } }, "إنشاء والدخول"),
      h("button", { class: "btn ghost", type: "button", onclick: () => serverSettings(true) }, "الجهاز ده هيشتغل على سيرفر؟ إعدادات الاتصال"));
    $("#app").replaceChildren(h("div", { class: "login" }, box)); n.focus(); enterChain([n, p1, p2]); return;
  }
  const u = h("input", { class: "in", id: "lg-user", autocomplete: "username", "aria-label": "اسم المستخدم", value: store("lastUser") || "" });
  const p = h("input", { class: "in", id: "lg-pass", type: "password", autocomplete: "current-password", "aria-label": "كلمة السر" });
  const err = h("div", { class: "err", role: "alert" });
  const btn = h("button", { class: "btn primary", style: { minHeight: "48px", fontSize: "16px" }, type: "submit" }, "دخول");
  const box = h("form", { class: "box", onsubmit: async (e) => {
    e.preventDefault(); btn.disabled = true; btn.replaceChildren(h("div", { class: "spin" })); err.textContent = "";
    try { S.me = await api("login", u.value, p.value); store("lastUser", u.value.trim()); S.screen = firstScreen(); renderShell(); }
    catch (x) { err.textContent = x.message; p.value = ""; p.focus(); box.classList.add("shake"); setTimeout(() => box.classList.remove("shake"), 500); }
    finally { btn.disabled = false; btn.replaceChildren("دخول"); }
  } },
    h("div", { class: "logo" }, h("img", { src: S.boot.logo, alt: "" }), h("b", null, S.boot.company)),
    h("label", { class: "fld", for: "lg-user" }, "اسم المستخدم", u),
    h("label", { class: "fld", for: "lg-pass" }, "كلمة السر", p), err, btn,
    h("div", { class: "meta" }, S.boot.version + " • " + S.boot.server, " • ", h("a", { href: "#", onclick: (e) => { e.preventDefault(); serverSettings(true); } }, "إعدادات الاتصال")));
  $("#app").replaceChildren(h("div", { class: "login" }, box));
  (u.value ? p : u).focus();
  enterChain([u, p]);
}

/* ===================== الهيكل: القايمة الجانبية + الشريط اللي فوق ===================== */
// الصلاحيات: المالك كله، وغيره الشاشات المسموحله بيها بس
const can = (k) => !!S.me && (S.me.owner || (S.me.screens || []).includes(k));
const firstScreen = () => (can("home") ? "home" : (S.me.screens || [])[0] || "home");
function navBtn(key) {
  const sc = SCREENS[key];
  return h("button", { class: "nav" + (S.screen === key ? " on" : ""), "data-screen": key, title: sc.title, onclick: () => go(key) },
    icon(sc.icon, 22), h("span", { class: "lbl" }, sc.title), sc.key ? h("span", { class: "key" }, sc.key) : null);
}
/* القايمة الجانبية: مجموعات بتتفتح وتتقفل (المجموعة اللي فيها الشاشة المفتوحة بتفتح لوحدها) */
const trustPrint = async () => { try { await api("print_trust_form"); toast("🖨 شاشة الطباعة هتفتح خلال ثواني ...", "ok"); } catch (e) { toast(e.message, "err"); } };
function navGroups() {
  const G = [
    ["الفواتير", "list", ["inv:مبيعات", "inv:مشتريات", "inv:مرتجع مبيعات", "inv:مرتجع مشتريات", "log"]],
    ["السندات", "cash", ["vch:new", "vch:log"], [["طباعة إيصال أمانة", "print", trustPrint]]],
    ["الطلبات", "check", ["req"]],
    ["العملاء والموردون", "users", ["par:list"]],
    ["الأصناف والمخزون", "box", ["itm:list", "itm:stock", "itm:sales", "itm:buys", "itm:damaged", ["العينات", "box", ["smp:items", "smp:out", "smp:in"]]]],
    ["الموظفون", "users", ["emp:list", "emp:att", "emp:attlog", "emp:veh"]],
    ["الحسابات", "calc", ["acc:statement", "acc:balances", "acc:cash", "acc:subcash", "acc:assets"]],
    ["التقارير", "chart", ["rep:daily", S.me.owner ? "rep:monthly" : null, S.me.owner ? "rep:profit" : null, "rep:reps", "rep:targets", "rep:log"]],
    ["الإعدادات", "edit", ["set:main", S.me.owner ? "set:users" : null], [["إصدار نسخة احتياطية", "save", backupNow]]],
  ];
  S.openGroups = S.openGroups || new Set();
  const flat = (keys) => keys.flatMap((k) => Array.isArray(k) ? flat(k[2]) : [k]).filter(Boolean);
  const allowedKeys = (keys) => keys.filter(Boolean).map((k) => (Array.isArray(k) ? [k[0], k[1], allowedKeys(k[2]), k[3]] : k)).filter((k) => (Array.isArray(k) ? k[2].length : can(k)));
  const group = ([label, ic, keys, extra], sub) => {
    keys = allowedKeys(keys);
    const all = flat(keys);
    const box = h("div", { class: "grp" + (sub ? " sub" : "") + (S.openGroups.has(label) || all.includes(S.screen) ? " open" : ""), "data-keys": all.join("|") },
      h("button", { class: "nav grp-h", "aria-expanded": "false", title: label, onclick: () => {
        const open = !box.classList.contains("open");
        [...box.parentElement.children].forEach((g) => { if (g !== box && g.classList.contains("grp") && g.classList.contains("open")) { g.classList.remove("open"); S.openGroups.delete(g.querySelector(".grp-h .lbl").textContent); } });
        box.classList.toggle("open", open); open ? S.openGroups.add(label) : S.openGroups.delete(label);
      } }, icon(ic, sub ? 20 : 22), h("span", { class: "lbl" }, label), h("span", { class: "chev" }, "‹")),
      h("div", { class: "grp-items" }, h("div", null, keys.map((k) => Array.isArray(k) ? group(k, true) : navBtn(k)), (extra || []).map(([t, i, fn]) => h("button", { class: "nav", onclick: fn }, icon(i, 20), h("span", { class: "lbl" }, t))))));
    return box;
  };
  return G.map((g) => [g[0], g[1], allowedKeys(g[2]), g[0] === "السندات" ? (can("vch:new") ? g[3] : null) : g[0] === "الإعدادات" ? (can("set:main") ? g[3] : null) : g[3]])
    .filter((g) => g[2].length || (g[3] && g[3].length)).map((g) => group(g));
}
function renderShell() {
  SCREENS.req.title = S.me.rep ? "طلباتي" : "طلبات المناديب";
  const side = h("nav", { class: "side" + (S.mini ? " mini" : ""), "aria-label": "القايمة الرئيسية" },
    h("div", { class: "brand" }, h("img", { src: S.boot.logo, alt: "" }), h("div", { class: "t" }, h("b", null, S.boot.company), S.boot.tagline ? h("small", null, S.boot.tagline) : null)),
    can("home") ? navBtn("home") : null,
    ...navGroups(),
    h("div", { class: "spacer" }),
    h("button", { class: "nav", title: "القايمة بتكبر لما الماوس ييجي عليها — أو ثبّتها مفتوحة", onclick: (e) => { S.mini = !S.mini; store("mini", S.mini); side.classList.toggle("mini", S.mini);
      e.currentTarget.querySelector(".lbl").textContent = S.mini ? "تثبيت القايمة مفتوحة" : "تصغير القايمة"; } }, icon("menu", 22), h("span", { class: "lbl" }, S.mini ? "تثبيت القايمة مفتوحة" : "تصغير القايمة")),
    h("div", { class: "who" }, h("div", { class: "av" }, (S.me.username || "?").slice(0, 1)),
      h("div", { class: "lbl" }, h("b", null, S.me.username), h("small", null, S.me.role)),
      h("button", { class: "btn ghost", style: { color: "#c9d6e6", marginInlineStart: "auto", padding: "0 8px" }, title: "خروج", "aria-label": "خروج", onclick: logout }, icon("logout", 18))),
    h("div", { class: "sig", title: S.boot.version || "" }, h("span", { dir: "ltr", class: "sig-v" }, S.boot.build ? `V1.0.${S.boot.build}` : "dev"), h("span", { dir: "ltr", class: "sig-n" }, "by Ali ElMenshawy")));
  const top = h("header", { class: "top" },
    h("button", { class: "btn icon-btn m-menu", "aria-label": "القايمة", onclick: () => toggleMobileNav() }, icon("menu", 22)),
    h("div", { class: "grow" }, h("h1", { id: "top-title" }, ""), h("div", { class: "sub", id: "top-sub" }, "")),
    h("span", { class: "last-up", id: "last-up" }, "آخر تحديث: ", h("b", null, "—")),
    h("button", { class: "btn gold icon-btn", id: "refresh-all", title: "تحديث الشاشة", "aria-label": "تحديث", onclick: refreshAll }, icon("refresh", 22)),
    S.me.rep ? h("button", { class: "btn gold close-day", id: "checkin", onclick: repCheckin }, icon("check", 18), "تسجيل حضور") : null,
    S.me.rep ? null : h("button", { class: "btn gold close-day", id: "close-day", onclick: closeDay }, icon("lock", 18), "تقفيل اليوم"),
    !S.me.rep && can("req") ? h("button", { class: "btn gold icon-btn", id: "req-btn", title: "طلبات المناديب", "aria-label": "طلبات المناديب", onclick: () => go("req") }, icon("inbox", 22), h("span", { class: "badge zero", id: "req-n" }, "0")) : null,
    !can("home") ? null : h("button", { class: "btn gold icon-btn", id: "bell", "aria-label": "العملاء المتوقعين", onclick: openDrawer }, icon("bell", 22, "ring"), h("span", { class: "badge zero", id: "bell-n" }, "0")));
  const main = h("div", { class: "main" }, top, h("div", { id: "screen" }), h("footer", { class: "todaybar", id: "todaybar", "aria-label": "ملخص النهارده" }), h("footer", { class: "pagebar", id: "pagebar", hidden: true, "aria-label": "إجمالي الجدول" }));
  $("#app").replaceChildren(h("div", { class: "shell" }, side, main), h("div", { class: "shade", id: "shade", onclick: closeDrawer }), h("aside", { class: "drawer", id: "drawer", "aria-label": "العملاء المتوقعين" }));
  go(S.screen, true); REQ_LAST = -1; loadReqCount();
  loadExpected();
  setInterval(loadExpected, 5 * 60 * 1000);
  loadTodayBar(); setInterval(loadTodayBar, 60 * 1000);
}
// الموبايل: القايمة بتطلع من اليمين فوق الشاشة وبتقفل لما تختار شاشة أو تدوس برة
const isPhone = () => matchMedia("(max-width: 760px)").matches;
function toggleMobileNav(force) {
  const sd = $(".side"); if (!sd) return;
  const on = force !== undefined ? force : !sd.classList.contains("m-open");
  sd.classList.toggle("m-open", on); document.body.classList.toggle("m-nav", on);
}
document.addEventListener("click", (e) => {
  if (!document.body.classList.contains("m-nav")) return;
  if (e.target.closest(".m-menu")) return;
  const nb = e.target.closest(".side .nav[data-screen], .side .grp-items .nav:not(.grp-h)");
  if (nb || !e.target.closest(".side")) toggleMobileNav(false);
}, true);
async function logout() {
  if (S.dirty && !(await confirmBox("فيه فاتورة لسه ماتحفظتش. تخرج برضه؟"))) return;
  await api("logout"); S.me = null; S.drafts = {}; S.dirty = false; renderLogin();
}
async function go(key, force) {
  if (!can(key)) { if (S.me) toast("مش مسموحلك بالشاشة دي", "err"); if (S.screen && can(S.screen)) return; key = firstScreen(); }
  if (!force && key === S.screen) return;
  if (!force && S.dirty && (S.screen.startsWith("inv:") || S.screen === "vch:new") && !(await confirmBox("الفاتورة اللي مفتوحة فيها أصناف ولسه ماتحفظتش. تسيبها وتفتح الشاشة التانية؟\n(هتلاقيها زي ما هي لما ترجع)"))) return;
  if (key === "rep:profit" && S.screen !== key) S.pfSt = null;      // الأرباح بتفتح دايمًا على النهارده
  if (key === "emp:veh" && S.screen !== key && S.vehSt) S.vehSt = { from: S.boot.today, to: S.boot.today, sel: S.vehSt.sel };   // العربيات كمان (والعربية المختارة تفضل)
  S.screen = key;
  document.querySelectorAll(".nav[data-screen]").forEach((b) => b.classList.toggle("on", b.dataset.screen === key));
  document.querySelectorAll(".grp").forEach((g) => { const has = g.dataset.keys.split("|").includes(key); g.classList.toggle("has", has); if (has) g.classList.add("open"); });
  const ed = key.startsWith("inv:") && S.drafts[key.slice(4)] && S.drafts[key.slice(4)].edit_id;
  $("#top-title").textContent = ed ? `تعديل ${SCREENS[key].title} رقم ${S.drafts[key.slice(4)].number}` : (key === "vch:new" && S.voucherEdit ? "تعديل سند" : SCREENS[key].title);
  $("#top-sub").textContent = `${S.me.username} (${S.me.role}) • ${new Date().toLocaleDateString("ar-EG", { weekday: "long", year: "numeric", month: "long", day: "numeric" })}`;
  const box = $("#screen");
  if ($("#pagebar")) $("#pagebar").replaceChildren();
  box.replaceChildren(h("div", { class: "page" }, h("div", { class: "empty" }, "بيحمّل ...")));
  try {
    if (key === "home") await renderHome(box);
    else if (key === "log") await renderLog(box);
    else if (key === "vch:new") await renderVoucher(box);
    else if (key === "vch:log") await renderVouchers(box);
    else if (key === "acc:statement") await renderStatement(box);
    else if (key === "acc:balances") await renderBalances(box);
    else if (key === "acc:cash") await renderCash(box);
    else if (key === "par:list") await renderParties(box);
    else if (key === "itm:list") await renderItems(box);
    else if (key === "itm:stock") await renderStock(box);
    else if (key === "itm:sales") await renderFlow(box, "مبيعات");
    else if (key === "itm:buys") await renderFlow(box, "مشتريات");
    else if (key === "itm:damaged") await renderDamaged(box);
    else if (key === "smp:items") await renderSampleItems(box);
    else if (key === "smp:out") await renderSamples(box, "عينات مبيعات");
    else if (key === "smp:in") await renderSamples(box, "عينات مشتريات");
    else if (key === "acc:subcash") await renderSubcash(box);
    else if (key === "acc:assets") await renderAssets(box);
    else if (key === "rep:daily") await renderDaily(box);
    else if (key === "rep:monthly") await renderMonthly(box);
    else if (key === "rep:profit") await renderProfit(box);
    else if (key === "rep:reps") await renderReps(box);
    else if (key === "rep:targets") await renderTargets(box);
    else if (key === "rep:log") await renderActivity(box);
    else if (key === "emp:list") await renderEmployees(box);
    else if (key === "emp:att") await renderAttendance(box);
    else if (key === "emp:attlog") await renderAttLog(box);
    else if (key === "emp:attreq") await renderRequests(box, "att");
    else if (key === "emp:repreq") await renderRequests(box, "rep");
    else if (key === "emp:veh") await renderVehicles(box);
    else if (key === "set:main") await renderSettings(box);
    else if (key === "set:users") await renderUsers(box);
    else if (key === "req") await renderReq(box);
    else await renderInvoice(box, key.slice(4));
  } catch (e) { box.replaceChildren(h("div", { class: "page" }, h("div", { class: "card empty" }, e.message))); }
  pinTotals();
}

/* ===================== الرئيسية ===================== */
async function renderHome(box) {
  const d = await api("dashboard");
  const sales = d.inv["مبيعات"], buys = d.inv["مشتريات"];
  markClosed(d.closed);
  const rows = d.rows.map((r) => h("tr", { class: "click", tabindex: "0", ondblclick: () => showInvoice(r.id), onkeydown: (e) => { if (e.key === "Enter") showInvoice(r.id); },
      oncontextmenu: (e) => { e.preventDefault(); ctxMenu(e, invoiceMenu(r, () => go("home", true))); } },
    h("td", null, h("span", { class: "pill " + kindClass(r.kind) }, r.kind)), h("td", null, h("b", null, r.number)), h("td", { class: "hint" }, r.time),
    h("td", null, r.party), h("td", { class: "hint" }, r.rep), h("td", { class: "hint" }, r.pay), h("td", { class: "num" }, h("b", null, fmt(r.net))),
    h("td", { title: r.printed ? "اتطبعت" : "لسه ماتطبعتش" }, r.printed ? icon("check", 18) : "")));
  const day = new Date(S.boot.today + "T12:00:00").toLocaleDateString("ar-EG", { weekday: "long" });
  box.replaceChildren(h("div", { class: "home" },
    h("section", { class: "hero anim-up d1" },
      h("div", { class: "hero-in" }, h("img", { src: S.boot.logo, alt: "" }),
        h("div", { class: "hero-t" }, h("b", null, S.boot.company), S.boot.tagline ? h("span", null, S.boot.tagline) : null)),
      h("div", { class: "hero-date" }, `${day}  ${S.boot.today.split("-").reverse().join("-")}`)),
    h("section", { class: "card home-inv anim-up d2" },
      h("div", { class: "card-h" }, h("h2", null, "فواتير اليوم"), h("span", { class: "hint" }, "ضغطتين على فاتورة = تفتحها")),
      d.rows.length ? h("div", { class: "tbl-wrap" }, h("table", { class: "t" },
        h("thead", null, h("tr", null, ["النوع", "رقم", "الوقت", "العميل / المورد", "المندوب", "الدفع"].map((x) => h("th", null, x)), h("th", { class: "num" }, "الصافي"), h("th", null, ""))),
        h("tbody", null, rows))) : h("div", { class: "empty" }, "لسه مفيش فواتير النهارده"))));
}

/* عدد طلبات المناديب المستنية — بيتحدث كل دقيقة ومع أي تحديث */
let REQ_LAST = -1;
async function loadReqCount() {
  const b = $("#req-n"); if (!b) return;
  let n; try { n = await api("req_counts"); } catch (e) { return; }
  b.textContent = n.total > 99 ? "99+" : String(n.total); b.classList.toggle("zero", !n.total);
  $("#req-btn").title = `طلبات المناديب: ${n.inv} فاتورة • ${n.pay} تحصيل • ${n.att} حضور`;
  if (REQ_LAST >= 0 && n.total > REQ_LAST) toast(`📥 وصل طلب جديد من مندوب (المستني: ${n.total})`, "", 6000, { label: "افتح", fn: () => go("req") });
  REQ_LAST = n.total;
}
setInterval(() => { if (S.me && !S.me.rep && document.visibilityState !== "hidden") loadReqCount(); }, 60000);
async function refreshAll() {
  const b = $("#refresh-all"); if (b) { b.classList.remove("spin-once"); void b.offsetWidth; b.classList.add("spin-once"); }
  if (S.dirty && (S.screen.startsWith("inv:") || S.screen === "vch:new")) { loadTodayBar(); loadExpected(); return toast("✔ اتحدث (الفاتورة اللي مفتوحة زي ما هي)", "ok"); }
  await go(S.screen, true); loadTodayBar(); loadExpected(); loadReqCount();
}
async function backupNow() {
  toast("💾 بيعمل نسخة احتياطية ...");
  try {
    const r = await api("backup_now");
    alertBox("✔ اتعملت نسخة احتياطية جديدة — النسخ القديمة زي ما هي ماتمسحتش.\n\nالنسخة اتحفظت في:\n" + r.path + (r.warn ? "\n\n⚠ " + r.warn : ""), "💾 نسخة احتياطية");
  } catch (e) { alertBox(e.message, "النسخة الاحتياطية فشلت"); }
}

/* ===================== طلبات المناديب (فواتير / تحصيل / حضور) ===================== */
function getPos(timeout = 15000) {
  return new Promise((res, rej) => {
    if (!navigator.geolocation || !window.isSecureContext) return rej(new Error("insecure"));
    navigator.geolocation.getCurrentPosition((p) => res(p.coords), (e) => rej(e), { enableHighAccuracy: true, timeout, maximumAge: 0 });
  });
}
async function repCheckin() {
  if (!(await confirmBox("تسجّل حضورك دلوقتي؟\nالموبايل هياخد موقعك: لو انت جوه المخزن حضورك يتسجل على طول، غير كده يروح طلب للمحاسب.", "📍 تسجيل حضور", "أيوه، سجّل"))) return;
  let pos = null, why = "";
  const w = toast("📍 بيجيب موقعك ...", "", 4000);
  try { pos = await getPos(); }
  catch (e) { why = e && e.code === 1 ? "انت رفضت إذن الموقع — افتح إعدادات الموبايل ← Safari/Chrome ← الموقع ← اسمح" : e && e.message === "insecure" ? "الموقع مش متاح من اللينك ده — افتح السيستم من لينك https" : "الموبايل ماعرفش يجيب الموقع (شغّل الـ GPS)"; }
  finally { try { w && w.remove && w.remove(); } catch (_) {} }
  if (!pos && !(await confirmBox(why + "\n\nتبعت طلب حضور من غير موقع؟ (المحاسب لازم يوافق)", "📍 تسجيل حضور", "ابعت من غير موقع"))) return;
  try {
    const r = await api("rep_checkin", pos ? pos.latitude : null, pos ? pos.longitude : null, pos ? pos.accuracy : null);
    if (r.done) alertBox(`✅ حضورك اتسجل الساعة ${r.time}` + (r.late ? `\nمتأخر ${r.late} دقيقة` : "") + `\n(انت على بعد ${r.dist} من المخزن)`, "تسجيل حضور");
    else alertBox(`📨 اتبعت طلب حضورك الساعة ${r.time}\n${r.reason}\nمستني موافقة المحاسب`, "تسجيل حضور");
  } catch (e) { alertBox(e.message, "تسجيل حضور"); }
}
async function reviewInvoiceRequest(rid) {
  let pl; try { pl = await api("inv_request_get", rid); } catch (e) { return alertBox(e.message); }
  if (S.drafts[pl.kind] && S.drafts[pl.kind].lines.length && !(await confirmBox("فيه فاتورة مفتوحة لسه ماتحفظتش. تسيبها وتفتح طلب المندوب؟"))) return;
  S.drafts[pl.kind] = null; S.pendingReq = pl; S.dirty = false; closeModals(); go("inv:" + pl.kind, true);
  toast("راجع الفاتورة واضغط حفظ عشان توافق على الطلب", "", 4500);
}
async function renderReq(box) {
  const rep = !!S.me.rep;
  const R = S.reqSt || (S.reqSt = { which: "inv", st: rep ? "all" : "pending" });
  const tabs = h("div", { class: "seg" }, [["inv", "فواتير"], ["pay", "تحصيل"], ["att", "حضور"]].map(([k, l]) => h("button", { class: R.which === k ? "on" : "", onclick: () => { R.which = k; go("req", true); } }, l)));
  const stSel = h("select", { class: "in", "aria-label": "الحالة", onchange: () => { R.st = stSel.value; load(); } }, h("option", { value: "pending" }, "مستنية موافقة"), h("option", { value: "all" }, "الكل"));
  stSel.value = R.st;
  const pill = (r) => h("span", { class: "pill " + (r.status === "approved" ? "k-مبيعات" : r.status === "rejected" ? "k-مرتجع" : "k-مشتريات") }, r.status_text);
  const colsBy = {
    inv: [{ h: "رقم", key: "id", cls: "hint" }, { h: "الوقت", key: "created_at", cls: "hint" }, { h: "المندوب", key: "rname" }, { h: "العميل", fn: (r) => h("b", null, r.pname) },
      { h: "النوع", key: "kind" }, { h: "أصناف", key: "lines", num: true }, { h: "الصافي", num: true, sort: (r) => r.net, fn: (r) => h("b", null, fmt(r.net)) }, { h: "الحالة", fn: pill, sort: (r) => r.status }, { h: "ملاحظة", key: "reason", cls: "hint" }],
    pay: [{ h: "رقم", key: "id", cls: "hint" }, { h: "الوقت", key: "created_at", cls: "hint" }, { h: "المندوب", key: "rname" }, { h: "العميل", fn: (r) => h("b", null, r.pname) },
      { h: "المبلغ", num: true, sort: (r) => +r.amount, fn: (r) => h("b", null, fmt(r.amount)) }, { h: "ملاحظات", key: "notes", cls: "hint" }, { h: "الحالة", fn: pill, sort: (r) => r.status }],
    att: [{ h: "رقم", key: "id", cls: "hint" }, { h: "اليوم", key: "a_date" }, { h: "المندوب", fn: (r) => h("b", null, r.rname) }, { h: "الساعة", key: "check_in" }, { h: "البعد عن المخزن", sort: (r) => (r.dist == null ? 1e12 : r.dist), fn: (r) => r.dist == null ? "—" : (r.dist >= 1000 ? (r.dist / 1000).toFixed(1) + " كم" : Math.round(r.dist) + " م") },
      { h: "الخريطة", fn: (r) => r.lat == null ? "" : h("a", { href: `https://maps.google.com/?q=${r.lat},${r.lon}`, target: "_blank", rel: "noopener" }, "🗺 افتح") }, { h: "ملاحظة", key: "reason", cls: "hint" }, { h: "الحالة", fn: pill, sort: (r) => r.status }],
  };
  const decide = async (r, ok) => {
    if (R.which === "inv" && ok) return reviewInvoiceRequest(r.id);
    let reason = "";
    if (!ok) { reason = await promptBox("سبب الرفض (اختياري — المندوب هيشوفه):", "رفض الطلب"); if (reason === null) return; }
    try { const x = await api("req_decide", R.which, r.id, ok, reason); toast(x.text, x.done ? "ok" : "err"); load(); } catch (e) { alertBox(e.message); }
  };
  const T = selTable({ cols: colsBy[R.which], empty: rep ? "مفيش طلبات" : "مفيش طلبات مستنية",
    onOpen: (r) => (!rep && r.status === "pending" ? decide(r, true) : r.invoice_id ? showInvoice(r.invoice_id) : null),
    menu: rep ? null : (r) => r.status === "pending" ? [{ label: R.which === "inv" ? "👁 مراجعة وحفظ (موافقة)" : "✅ موافقة", fn: () => decide(r, true) }, { label: "❌ رفض", danger: true, fn: () => decide(r, false) }] : [{ label: "خلاص اتقرر", disabled: true }],
    totals: (rs, isSel) => [h("b", null, isSel ? "المحدد" : "الإجمالي"), totItem("العدد", rs.length),
      R.which === "inv" ? totItem("الصافي", fmt(rs.reduce((a, r) => a + r.net, 0)), true) : R.which === "pay" ? totItem("المبلغ", fmt(rs.reduce((a, r) => a + (+r.amount || 0), 0)), true) : null] });
  async function load() { try { T.setRows(await api("req_list", R.which, R.st)); } catch (e) { toast(e.message, "err"); } if (!rep) loadReqCount(); }
  const one = (ok) => () => { const r = T.selected()[0]; if (!r) return toast("حدد طلب الأول"); if (r.status !== "pending") return toast("الطلب ده اتقرر خلاص"); decide(r, ok); };
  box.replaceChildren(h("div", { class: "page" }, h("section", { class: "card anim-up d1" },
    h("div", { class: "card-h" }, h("h2", null, rep ? "طلباتي" : "طلبات المناديب"), tabs, h("label", { class: "fld", style: { flexDirection: "row", alignItems: "center", gap: "8px" } }, "الحالة", stSel),
      rep ? h("span", { class: "hint" }, "الطلبات بتتسجل لما المحاسب يوافق") : [h("button", { class: "btn primary", onclick: one(true) }, icon("check", 18), R.which === "inv" ? "مراجعة وحفظ" : "موافقة"),
        h("button", { class: "btn danger", onclick: one(false) }, icon("x", 18), "رفض")]), T.el)));
  await load();
}

/* ===================== جرد الخزنة المفصّل (مع المناديب / مع الملاك / الدرج) ===================== */
async function cashCountModal() {
  let st; try { st = await api("cash_count_setup"); } catch (e) { return alertBox(e.message); }
  const groups = [["rep", "١. مع المناديب", st.reps], ["owner", "٢. مع الملاك", st.owners]];
  const rows = { rep: [], owner: [] };
  const sumEl = h("div", { class: "cc-sum" }), drawerIn = h("input", { class: "in num", inputmode: "decimal", "aria-label": "الدرج" });
  let drawerTouched = false;
  drawerIn.addEventListener("input", () => { drawerTouched = true; recalc(); });
  const others = () => ["rep", "owner"].reduce((a, g) => a + rows[g].reduce((x, r) => x + num(r.amt.value), 0), 0);
  function recalc() {
    if (!drawerTouched) drawerIn.value = Math.max(0, +(st.system - others()).toFixed(2));
    const counted = others() + num(drawerIn.value), diff = counted - st.system;
    sumEl.replaceChildren(h("div", null, "المعدود: ", h("b", null, fmt(counted))), h("div", null, "رصيد الخزنة في السيستم: ", h("b", null, fmt(st.system))),
      h("div", { class: Math.abs(diff) < 0.005 ? "ok" : diff > 0 ? "up" : "down" }, Math.abs(diff) < 0.005 ? "✔ مطابق" : diff > 0 ? `⬆ زيادة ${fmt(diff)}` : `⬇ عجز ${fmt(-diff)}`));
  }
  const boxes = {};
  const addRow = (g, l = {}) => {
    const who = h("select", { class: "in", "aria-label": "الاسم" }, (g === "rep" ? st.reps : st.owners).map((x) => h("option", { value: x }, x)));
    if (l.who && ![...who.options].some((o) => o.value === l.who)) who.appendChild(h("option", { value: l.who }, l.who));
    if (l.who) who.value = l.who;
    const meth = h("select", { class: "in", "aria-label": "طريقة الدفع" }, st.methods.filter((m) => m !== "درج").map((m) => h("option", { value: m }, m))); meth.value = l.method && l.method !== "درج" ? l.method : "كاش";
    const amt = h("input", { class: "in num", inputmode: "decimal", value: l.amount ?? "", "aria-label": "المبلغ", oninput: recalc });
    const r = { who, meth, amt }; rows[g].push(r);
    const el = h("div", { class: "cc-row" }, who, meth, amt, l.src ? h("span", { class: "hint" }, l.src) : null,
      h("button", { class: "btn ghost icon-btn", type: "button", "aria-label": "شيل السطر", onclick: () => { rows[g] = rows[g].filter((x) => x !== r); el.remove(); recalc(); } }, icon("x", 16)));
    boxes[g].appendChild(el); recalc();
  };
  const body = h("div", { class: "cc" },
    ...groups.map(([g, title]) => { boxes[g] = h("div", { class: "cc-rows" }); return h("section", { class: "cc-g" }, h("div", { class: "cc-gh" }, h("b", null, title),
      h("button", { class: "btn ghost", type: "button", onclick: () => addRow(g) }, icon("plus", 16), "سطر")), boxes[g]); }),
    h("section", { class: "cc-g" }, h("div", { class: "cc-gh" }, h("b", null, "٣. الدرج (خزنة المخزن)"), h("span", { class: "hint" }, "بيتحسب لوحده = السيستم − اللي مع الناس، وتقدر تكتب المعدود فعلًا")), drawerIn),
    h("section", { class: "cc-g" }, h("div", { class: "cc-gh" }, h("b", null, "🔁 التحويلات من آخر جرد"),
      h("button", { class: "btn ghost", type: "button", onclick: () => cashTransferModal(st) }, icon("plus", 16), "تحويل")),
      (st.transfers || []).length ? h("div", { class: "cc-rows" }, st.transfers.map((t) => h("div", { class: "cc-tr" },
        h("span", null, h("b", null, t.from_who), t.from_who === st.drawer ? "" : ` (${t.from_method})`, "  ←  ", h("b", null, t.to_who), t.to_who === st.drawer ? "" : ` (${t.to_method})`),
        h("b", { class: "num" }, fmt(t.amount)), t.notes ? h("span", { class: "hint" }, t.notes) : null, h("span", { class: "hint" }, (t.created_at || "").slice(5, 16)),
        h("button", { class: "btn ghost icon-btn", type: "button", "aria-label": "حذف التحويل", onclick: async () => {
          if (!(await confirmBox(`تمسح تحويل ${fmt(t.amount)} من «${t.from_who}» لـ «${t.to_who}»؟`))) return;
          try { await api("cash_transfer_delete", t.id); closeModals(); cashCountModal(); } catch (e) { alertBox(e.message); } } }, icon("x", 16)))))
        : h("div", { class: "hint" }, "مفيش — مثلًا: سحبت من فودافون كاش بتاع المندوب للدرج، أو مالك خد من الدرج للبيت")),
    h("label", { class: "fld" }, "ملاحظات", h("input", { class: "in", id: "cc-notes" })), sumEl,
    st.last ? h("div", { class: "hint" }, `آخر جرد: ${st.last.date} ${st.last.at ? st.last.at.slice(11, 16) : ""}`) : null);
  st.lines.forEach((l) => addRow(l.group, l)); if (!rows.rep.length) addRow("rep"); recalc();
  const collect = () => ({ lines: [...["rep", "owner"].flatMap((g) => rows[g].map((r) => ({ group: g, who: r.who.value, method: r.meth.value, amount: r.amt.value }))),
    { group: "drawer", who: "درج", method: "كاش", amount: drawerIn.value }], notes: $("#cc-notes") ? $("#cc-notes").value : "" });
  let saved = null;
  const save = async () => { if (saved) return saved; try { saved = await api("cash_count_save", collect()); toast("✔ اتحفظ الجرد", "ok"); return saved; } catch (e) { alertBox(e.message); return null; } };
  await modal({ title: "🧮 جرد الخزنة", wide: true, enter: false, body, actions: [
    { label: "حفظ الجرد", cls: "primary", icon: "save", value: async () => !!(await save()) },
    { label: "حفظ وطباعة", cls: "gold", icon: "print", value: async () => { const r = await save(); if (!r) return false; try { await api("cash_count_print", r.id); toast("🖨 شاشة الطباعة هتفتح ...", "ok"); } catch (e) { toast(e.message, "err"); } return true; } },
    S.boot.web ? null : { label: "حفظ PDF على سطح المكتب", icon: "save", value: async () => { const r = await save(); if (!r) return false; try { const pth = await api("cash_count_pdf", r.id, true); alertBox("✔ الجرد اتحفظ PDF:\n" + pth, "PDF"); } catch (e) { alertBox(e.message); } return true; } },
    { label: "إلغاء", value: () => null }].filter(Boolean) });
}

async function cashTransferModal(st) {
  const who = () => h("select", { class: "in" }, h("option", { value: st.drawer }, "الدرج (خزنة المخزن)"),
    st.reps.length ? h("optgroup", { label: "المناديب" }, st.reps.map((x) => h("option", { value: x }, x))) : null,
    st.owners.length ? h("optgroup", { label: "الملاك والمحاسبين" }, st.owners.map((x) => h("option", { value: x }, x))) : null);
  const meth = () => h("select", { class: "in" }, st.methods.map((m) => h("option", { value: m }, m)));
  const fw = who(), fm = meth(), tw = who(), tm = meth();
  const amt = h("input", { class: "in num", inputmode: "decimal", "aria-label": "المبلغ" }), notes = h("input", { class: "in", "aria-label": "ملاحظات" });
  if (st.reps.length) fw.value = st.reps[0];
  const sync = () => { fm.disabled = fw.value === st.drawer; tm.disabled = tw.value === st.drawer; if (fm.disabled) fm.value = "كاش"; if (tm.disabled) tm.value = "كاش"; };
  fw.onchange = sync; tw.onchange = sync; sync();
  const ok = await modal({ title: "🔁 تحويل فلوس", enter: false, body: h("div", { class: "form", style: { padding: 0 } },
      h("label", { class: "fld" }, "من", fw), h("label", { class: "fld" }, "طريقة (من)", fm),
      h("label", { class: "fld" }, "إلى", tw), h("label", { class: "fld" }, "طريقة (إلى)", tm),
      h("label", { class: "fld" }, "المبلغ", amt), h("label", { class: "fld" }, "ملاحظات", notes),
      h("div", { class: "hint span2" }, "أمثلة: من «المندوب — فودافون كاش» إلى «الدرج» لما تسحب فلوسه • من «الدرج» إلى «المالك — كاش» لما ياخد فلوس للبيت")),
    actions: [{ label: "حفظ التحويل", cls: "primary", icon: "save", value: async () => {
      try { await api("cash_transfer_add", { from_who: fw.value, from_method: fm.value, to_who: tw.value, to_method: tm.value, amount: amt.value, notes: notes.value }); return true; }
      catch (e) { alertBox(e.message); return false; } } }, { label: "إلغاء", value: () => null }] });
  if (ok) { toast("✔ اتسجل التحويل", "ok"); closeModals(); cashCountModal(); }
}

/* ===================== تقفيل اليوم ===================== */
async function closeDay() {
  if (!(await confirmBox("هيحصل دلوقتي:\n• جرد الخزنة يتحفظ PDF\n• نسخة احتياطية تتعمل في المجلد المختار\n• أي تعديل أو إضافة أو حذف لفواتير وسندات النهارده وقبلها هيحتاج باسوورد المحاسب أو المالك\n\nتقفل اليوم؟", "🔒 تقفيل اليوم", "أيوه، اقفل اليوم"))) return;
  const body = h("div", { class: "close-steps" }, h("div", { class: "cs-wait" }, h("div", { class: "spin dark" }), "بيحفظ الجرد ويعمل النسخة ... استنى ثواني"));
  modal({ title: "🔒 تقفيل اليوم", body, actions: [{ label: "تمام", cls: "primary", ret: true }] });
  try {
    const r = await api("close_day");
    body.replaceChildren(r.steps.map((s) => h("div", { class: "cs " + (s.ok ? "ok" : s.ok === false ? "bad" : "skip") }, h("span", { class: "cs-i" }, s.ok ? "✔" : s.ok === false ? "✖" : "—"), h("span", null, s.t))));
    markClosed(r.day);
  } catch (e) { body.replaceChildren(h("div", { class: "cs bad" }, h("span", { class: "cs-i" }, "✖"), h("span", null, e.message))); }
}
function markClosed(day) {
  const b = $("#close-day"); if (!b) return;
  const on = day && day === S.boot.today;
  b.classList.toggle("done", !!on); b.title = on ? "اليوم اتقفل — تقدر تدوس تاني تعمل نسخة من جديد" : "";
  b.lastChild.textContent = on ? "اليوم متقفل ✔" : "تقفيل اليوم";
}

/* ===================== التقرير اليومي ===================== */
async function dailyReport() {
  let r;
  try { r = await api("daily_report"); } catch (e) { return toast(e.message, "err"); }
  const body = h("div", null, r.rows.map(([t, a, b]) => h("div", { class: "rep-row " + (t === "h" ? "h" : t === "b" ? "b" : "") }, h("span", null, a), h("span", { class: "num" }, b))));
  modal({ title: `📊 تقرير يوم ${r.day}`, body, enter: false, actions: [{ label: "قفل", cls: "primary", ret: true }] });
}

/* ===================== الجرس: العملاء المتوقعين ===================== */
async function loadExpected() {
  try { S.expected = await api("expected"); } catch (e) { return; }
  const n = S.expected.filter((x) => !x.called).length, b = $("#bell-n");
  if (b) { b.textContent = n; b.classList.toggle("zero", n === 0); }
  if ($("#drawer") && $("#drawer").classList.contains("on")) fillDrawer();
}
function openDrawer() { fillDrawer(); $("#drawer").classList.add("on"); $("#shade").classList.add("on"); }
function closeDrawer() { $("#drawer").classList.remove("on"); $("#shade").classList.remove("on"); }
function fillDrawer() {
  const dr = $("#drawer");
  const act = async (fn, ...a) => { try { S.expected = await api(fn, ...a); loadExpected(); } catch (e) { toast(e.message, "err"); } };
  const items = S.expected.map((x, i) => h("div", { class: "exp" + (x.called ? " done" : ""), style: { animationDelay: (i * 0.04) + "s" } },
    h("div", { class: "n" }, x.name),
    h("div", { class: "m" }, x.late === 0 ? h("span", { class: "late" }, "المفروض يطلب النهارده") : h("span", { class: "late" }, `متأخر ${x.late} يوم`),
      ` • بيطلب كل ${fq(x.every)} يوم • آخر مرة ${x.last}`),
    h("div", { class: "m" }, (x.tons ? `عادةً ${fmt(x.tons)} طن` : "") + (x.amount ? ` • حوالي ${fmt(x.amount)} ج.م` : "") + (x.rep ? ` • المندوب: ${x.rep}` : "")),
    x.phone ? h("div", { class: "m" }, icon("phone", 14), " ", x.phone) : null,
    x.called ? h("div", { class: "m", style: { color: "var(--green)", fontWeight: 800 } }, "✔ اتكلمت معاه" + (x.note ? ` — ${x.note}` : "")) : null,
    h("div", { class: "acts" },
      x.called ? h("button", { class: "btn", onclick: () => act("unmark_called", x.id) }, icon("undo", 16), "رجّعه")
        : h("button", { class: "btn", onclick: async () => { const note = await promptBox(`«${x.name}» — ملاحظة (اختياري، مثلًا: هيطلب بكرة):`, "اتكلمت معاه"); if (note !== null) act("mark_called", x.id, note); } }, icon("phone", 16), "اتكلمت معاه"),
      h("button", { class: "btn primary", onclick: () => { closeDrawer(); newInvoiceFor(x.id); } }, icon("plus", 16), "فاتورة"),
      h("button", { class: "btn danger", title: "شيله من القايمة", onclick: () => { act("hide_expected", x.id); toast(`«${x.name}» اتشال من القايمة`, "", 6000, { label: "↩ تراجع", fn: () => act("unhide_expected", x.id) }); } }, icon("x", 16), "شيل"))));
  dr.replaceChildren(h("div", { class: "hd" }, h("h2", null, `عملاء متوقعين النهارده (${S.expected.filter((x) => !x.called).length})`),
    h("button", { class: "btn ghost icon-btn", "aria-label": "قفل", onclick: closeDrawer }, icon("x"))),
    h("div", { class: "bd" }, items.length ? items : h("div", { class: "empty" }, "✅ مفيش عملاء متوقعين النهارده")));
}
async function newInvoiceFor(pid) {
  S.pendingParty = pid;
  await go("inv:مبيعات", S.screen === "inv:مبيعات");
}

/* ===================== الفاتورة ===================== */
function newDraft(setup) {
  return { kind: setup.kind, number: setup.number, autoNo: setup.number, date: setup.date, due: "", party: null, rep_id: null, notes: "",
    lines: [], discount: "0", paid: "0", pay_type: "آجل", negPw: null, sel: new Set() };
}
function invoiceMenu(r, reload) {
  const label = `فاتورة ${r.kind} رقم ${r.number}`;
  return [{ label: "👁 عرض", fn: () => showInvoice(r.id) },
    { label: "🗑 حذف", danger: true, fn: async () => { if (await deleteInvoice(r.id, label)) reload ? reload() : go(S.screen, true); } },
    { label: "✏️ تعديل", fn: () => editInvoice(r.id) }];
}
async function editInvoice(id) {
  if (S.dirty && !(await confirmBox("فيه فاتورة لسه ماتحفظتش. تسيبها وتفتح الفاتورة دي للتعديل؟"))) return;
  let v; try { v = await api("invoice_for_edit", id); } catch (e) { return alertBox(e.message, "مش هينفع تتعدّل"); }
  S.drafts[v.kind] = { kind: v.kind, edit_id: v.id, number: v.number, autoNo: null, date: v.date, due: v.due, party: { id: v.party_id }, rep_id: v.rep_id, vehicle_id: v.vehicle_id || null,
    notes: v.notes, lines: v.lines, discount: String(v.discount), paid: String(v.paid), pay_type: v.pay_type, negPw: null, sel: new Set() };
  closeModals(); go("inv:" + v.kind, true);
}
async function deleteInvoice(id, label) {
  if (!(await confirmBox(`تحذف ${label} نهائيًا؟\nرصيد المخزون وحساب العميل/المورد هيتغيروا، وأي مبلغ مدفوع مسجّل معاها هيتحذف.`, "حذف فاتورة", "احذف"))) return false;
  let pw = null;
  while (true) {
    let r; try { r = await api("delete_invoice", id, pw); } catch (e) { alertBox(e.message, "مش هينفع تتحذف"); return false; }
    if (r.ok) { toast("✔ الفاتورة اتحذفت", "ok"); return true; }
    if (r.need === "neg") { pw = await askOwner(r.error); if (!pw) return false; continue; }
    alertBox(r.error); return false;
  }
}
function closeModals() { document.querySelectorAll(".modal").forEach((m) => m._done && m._done(null)); }
async function renderInvoice(box, kind) {
  const setup = await api("invoice_setup", kind);
  let D = S.drafts[kind];
  if (!D) D = S.drafts[kind] = newDraft(setup);
  if (S.pendingReq && S.pendingReq.kind === kind) {          // مراجعة طلب مندوب: الفاتورة بتتفتح بأصنافه والمحاسب يحفظها
    const q = S.pendingReq; S.pendingReq = null;
    Object.assign(D, { request_id: q.request_id, party: { id: q.party_id }, rep_id: q.rep_id, vehicle_id: q.vehicle_id || null, notes: q.notes || "", lines: q.lines, discount: String(q.discount || 0),
      paid: String(q.paid || 0), pay_type: q.pay_type || D.pay_type, due: q.due || "" });
    S.dirty = true;
  }
  const itemsById = new Map(setup.items.map((i) => [i.id, i]));
  const partiesById = new Map(setup.parties.map((p) => [p.id, p]));
  if (S.pendingParty && kind === "مبيعات") { D.party = partiesById.get(S.pendingParty) || null; S.pendingParty = null; if (D.party) D.rep_id = D.party.rep_id || null; }
  if (D.party && !D.party.label) D.party = partiesById.get(D.party.id) || null;
  if (D.edit_id && kind === "مبيعات" && D.rep_id && !setup.reps.some((r) => r.id === D.rep_id)) setup.reps.push({ id: D.rep_id, label: "مندوب (مش نشط)" });

  // --- بيانات الفاتورة ---
  const noIn = h("input", { class: "in", id: "f-no", value: D.number, "aria-label": "رقم الفاتورة" });
  const dateIn = h("input", { class: "in", id: "f-date", type: "date", value: D.date, "aria-label": "التاريخ" });
  const dueIn = h("input", { class: "in", id: "f-due", type: "date", value: D.due, "aria-label": "تاريخ الاستحقاق" });
  const notesIn = h("input", { class: "in", id: "f-notes", value: D.notes, "aria-label": "ملاحظات" });
  const party = combo({ id: "f-party", label: "العميل / المورد", placeholder: "اكتب جزء من الاسم ...", items: () => setup.parties, sub: (p) => p.kind,
    onPick: (p, adv) => { D.party = p; if (p && kind === "مبيعات" && repSel) { D.rep_id = p.rep_id || null; repSel.value = String(D.rep_id ?? ""); } refreshInfo(); if (adv) (repSel || notesIn).focus(); } });
  if (D.party) party.set(D.party);
  let repSel = null;
  if (kind === "مبيعات") {
    repSel = h("select", { class: "in", id: "f-rep", "aria-label": "المندوب", onchange: () => { D.rep_id = repSel.value ? +repSel.value : null; } },
      setup.reps.map((r) => h("option", { value: r.id ?? "" }, r.label)));
    repSel.value = String(D.rep_id ?? "");
  }
  let vehSel = null;                    // التوصيل: العربية اللي هتوصّل أو استلام مكتب
  if (setup.delivery) {
    vehSel = h("select", { class: "in", id: "f-veh", "aria-label": "التوصيل", onchange: () => { D.vehicle_id = vehSel.value ? +vehSel.value : null; } },
      h("option", { value: "" }, "🏢 استلام مكتب"), (setup.vehicles || []).map((v) => h("option", { value: v.id }, "🚚 " + v.label)));
    if (D.vehicle_id && !(setup.vehicles || []).some((v) => v.id === D.vehicle_id)) vehSel.appendChild(h("option", { value: D.vehicle_id }, "🚚 عربية (مش نشطة)"));
    vehSel.value = String(D.vehicle_id ?? "");
  }
  noIn.oninput = () => { D.number = noIn.value; };
  dateIn.onchange = async () => {
    D.date = dateIn.value;
    if (D.number.trim() === "" || D.number === D.autoNo) { try { D.autoNo = D.number = await api("next_number", kind, D.date); noIn.value = D.number; } catch (e) { } }
  };
  dueIn.onchange = () => { D.due = dueIn.value; };
  notesIn.oninput = () => { D.notes = notesIn.value; };

  // --- إضافة صنف ---
  const qtyIn = h("input", { class: "in num", id: "f-qty", value: "1", inputmode: "decimal", "aria-label": "الكمية" });
  const priceIn = h("input", { class: "in num", id: "f-price", value: "0", inputmode: "decimal", "aria-label": "سعر الوحدة" });
  const dmgIn = h("input", { type: "checkbox", id: "f-dmg" });
  const item = combo({ id: "f-item", label: "الصنف", placeholder: "اكتب اسم الصنف أو الكود ...", items: () => setup.items,
    sub: (it) => `${fq(it.stock)} ${it.unit} • ${fmt(it.price)}`,
    onPick: (it, adv) => { if (it) priceIn.value = it.price; refreshInfo(); if (adv) { qtyIn.focus(); qtyIn.select(); } } });
  const addBtn = h("button", { class: "btn primary", id: "f-add", onclick: () => addLine() }, icon("plus", 18), "إضافة الصنف");

  // --- الأصناف والإجماليات ---
  const chips = h("div", { class: "chips" });
  const tbody = h("tbody");
  const tfoot = h("tfoot");
  const discIn = h("input", { class: "in num", id: "f-disc", value: D.discount, "aria-label": "الخصم", oninput: () => { D.discount = discIn.value; totals(); } });
  const paidIn = h("input", { class: "in num", id: "f-paid", value: D.paid, "aria-label": setup.paid_label, oninput: () => { D.paid = paidIn.value; totals(); } });
  const tv = { total: h("div", { class: "v" }), net: h("div", { class: "v" }), rest: h("div", { class: "v" }), profit: h("div", { class: "v" }) };
  const seg = setup.paytypes ? h("div", { class: "seg" }, ["نقدي", "آجل"].map((v) => h("button", { class: D.pay_type === v ? "on" : "", "data-v": v, onclick: () => { D.pay_type = v; seg.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.v === v)); if (v === "آجل") { paidIn.value = D.paid = "0"; } totals(); } }, v))) : null;

  const lineAmount = () => D.lines.reduce((s, l) => s + l.qty * l.price, 0);
  let profitTimer = null;
  function totals() {
    const total = lineAmount(), disc = num(D.discount), net = total - disc;
    if (setup.paytypes && D.pay_type === "نقدي") { D.paid = net.toFixed(2); paidIn.value = D.paid; paidIn.disabled = true; } else paidIn.disabled = false;
    tv.total.textContent = fmt(total); tv.net.textContent = fmt(net); tv.rest.textContent = fmt(net - num(D.paid)); [tv.total, tv.net, tv.rest].forEach(fitNum);
    discIn.classList.toggle("bad", disc < 0 || disc > total + 0.005);
    S.dirty = D.lines.length > 0;
    if (setup.show_profit) { clearTimeout(profitTimer); profitTimer = setTimeout(refreshProfit, 250); }
  }
  async function refreshProfit() {
    if (!D.lines.length) { tv.profit.textContent = fmt(0); return; }
    try {
      const pr = await api("lines_profit", D.lines, D.edit_id || null);
      if (!pr) return;
      pr.forEach((x, i) => { const c = tbody.children[i]; if (c) { c.querySelector(".c-cost").textContent = fmt(x.cost); const p = c.querySelector(".c-prof"); p.textContent = fmt(x.profit); p.style.color = x.profit < 0 ? "var(--red)" : "var(--green)"; } });
      const tot = pr.reduce((s, x) => s + x.profit, 0) - num(D.discount);
      tv.profit.textContent = fmt(tot); tv.profit.style.color = tot < 0 ? "var(--red)" : "var(--green)";
    } catch (e) { }
  }
  function drawLines(newIdx = -1) {
    tbody.replaceChildren(...D.lines.map((l, i) => h("tr", { class: "click" + (D.sel.has(i) ? " sel" : "") + (i === newIdx ? " new" : ""), tabindex: "0",
      onclick: (e) => { if (!e.ctrlKey && !e.shiftKey) D.sel.clear(); D.sel.has(i) ? D.sel.delete(i) : D.sel.add(i); drawLines(); },
      ondblclick: () => editLine(i), onkeydown: (e) => { if (e.key === "Delete") { D.sel.add(i); removeLines(); } if (e.key === "Enter") editLine(i); } },
      h("td", { class: "hint" }, i + 1), h("td", null, h("b", null, l.name)), h("td", { class: "num" }, fq(l.qty)), h("td", { class: "hint" }, l.unit),
      h("td", { class: "num" }, fmt(l.price)), h("td", { class: "num" }, h("b", null, fmt(l.qty * l.price))),
      setup.returns_damaged ? h("td", { style: { color: l.damaged ? "var(--red)" : "var(--muted)", fontWeight: 700 } }, l.damaged ? "✔ هالك" : "يرجع للمخزن") : null,
      setup.show_profit ? [h("td", { class: "num hint c-cost" }, "…"), h("td", { class: "num c-prof", style: { fontWeight: 800 } }, "…")] : null)));
    if (!D.lines.length) tbody.replaceChildren(h("tr", null, h("td", { colspan: 9, class: "empty" }, "اختار صنف من فوق واكتب الكمية واضغط Enter")));
    tfoot.replaceChildren(D.lines.length ? h("tr", null, h("td", null, ""), h("td", null, `${D.lines.length} صنف`), h("td", { colspan: 3, class: "hint" }, qtyText(D.lines)),
      h("td", { class: "num" }, fmt(lineAmount())), setup.returns_damaged ? h("td") : null, setup.show_profit ? [h("td"), h("td")] : null) : "");
    totals();
  }
  async function refreshInfo() {
    const it = item.get(), p = D.party;
    chips.replaceChildren();
    if (!it && !p) return;
    let info;
    try { info = await api("item_info", kind, it ? it.id : null, p ? p.id : null); } catch (e) { return; }
    if (p && info.balance !== undefined) chips.appendChild(h("div", { class: "chip" }, "رصيد الحساب: ", h("b", null, fmt(info.balance))));
    if (it && info.stock !== undefined) {
      const inLines = D.lines.filter((l) => l.item_id === it.id).reduce((s, l) => s + l.qty, 0);
      chips.appendChild(h("div", { class: "chip" + (setup.out_side && info.available - inLines <= 0 ? " warn" : "") }, "رصيد الصنف: ", h("b", null, `${fq(info.stock)} ${it.unit}`),
        info.reserved > 0 ? ` (محجوز لفواتير قادمة ${fq(info.reserved)})` : "", inLines ? ` • في الفاتورة ${fq(inLines)}` : ""));
    }
    if (it && p) {
      const side = kind.includes("مبيعات") ? "بيع" : "شراء";
      chips.appendChild(h("div", { class: "chip info" }, info.last ? ["آخر سعر " + side + ": ", h("b", null, fmt(info.last.price)), ` — ${info.last.date} (فاتورة ${info.last.number})`] : `أول مرة: الصنف ده ${side === "بيع" ? "ما اتباعش للعميل ده" : "ما اتشراش من المورد ده"} قبل كده`));
    }
  }
  async function stockOk(it, qty, exceptIdx = -1) {
    if (!setup.out_side || D.negPw || D.edit_id) return true;
    let info; try { info = await api("item_info", kind, it.id, null); } catch (e) { return true; }
    const used = D.lines.reduce((s, l, i) => s + (l.item_id === it.id && i !== exceptIdx ? l.qty : 0), 0);
    const avail = info.available - used;
    if (qty <= avail + 1e-9) return true;
    const pw = await askOwner(`الرصيد المتاح من «${it.name}» هو ${fq(avail)} بس، وانت كاتب ${fq(qty)}.\nالرصيد هيبقى بالسالب — مسموح بس بكلمة سر المالك.`);
    if (!pw) return false;
    D.negPw = pw; return true;
  }
  async function addLine() {
    const it = item.get();
    if (!it) { item.input.classList.add("bad", "shake"); setTimeout(() => item.input.classList.remove("shake"), 500); item.focus(); return; }
    const qty = num(qtyIn.value), price = num(priceIn.value);
    if (!(qty > 0)) { qtyIn.classList.add("bad"); qtyIn.focus(); return toast("الكمية لازم تكون أكبر من صفر", "err"); }
    if (!(price >= 0) || isNaN(price)) { priceIn.classList.add("bad"); priceIn.focus(); return toast("السعر لازم يكون رقم ومش بالسالب", "err"); }
    qtyIn.classList.remove("bad"); priceIn.classList.remove("bad");
    if (!(await stockOk(it, qty))) return;
    D.lines.push({ item_id: it.id, name: it.name, unit: it.unit, qty, price, damaged: setup.returns_damaged && dmgIn.checked ? 1 : 0 });
    D.sel.clear(); drawLines(D.lines.length - 1);
    item.set(null); qtyIn.value = "1"; priceIn.value = "0"; dmgIn.checked = false; refreshInfo();
    item.focus();
  }
  async function editLine(i) {
    const l = D.lines[i];
    const q = h("input", { class: "in num", value: l.qty, "aria-label": "الكمية" }), p = h("input", { class: "in num", value: l.price, "aria-label": "سعر الوحدة" });
    const dm = h("input", { type: "checkbox" }); dm.checked = !!l.damaged;
    const ok = await modal({ title: "تعديل الصنف", body: [h("b", { style: { fontSize: "17px", color: "var(--navy)" } }, l.name),
      h("label", { class: "fld" }, `الكمية (${l.unit})`, q), h("label", { class: "fld" }, "سعر الوحدة", p),
      setup.returns_damaged ? h("label", { class: "chk" }, dm, "هالك (لا يرجع للمخزن)") : null],
      actions: [{ label: "حفظ", cls: "primary", value: () => { const nq = num(q.value), np = num(p.value); if (!(nq > 0) || !(np >= 0)) { toast("الكمية لازم تكون أكبر من صفر والسعر مش بالسالب", "err"); return false; } return { nq, np }; } }, { label: "إلغاء", value: () => null }] });
    if (!ok) return;
    if (ok.nq > l.qty && !(await stockOk(itemsById.get(l.item_id) || { id: l.item_id, name: l.name }, ok.nq, i))) return;
    l.qty = ok.nq; l.price = ok.np; if (setup.returns_damaged) l.damaged = dm.checked ? 1 : 0;
    drawLines(i);
  }
  async function removeLines() {
    let idx = [...D.sel].sort((a, b) => b - a);
    if (!idx.length) { if (!D.lines.length) return; idx = [D.lines.length - 1]; }
    if (idx.length > 1 && !(await confirmBox(`تحذف ${idx.length} صنف من الفاتورة؟`))) return;
    idx.forEach((i) => D.lines.splice(i, 1)); D.sel.clear(); drawLines();
  }
  async function save(print) {
    if (saving) return;
    if (!D.party) { party.input.classList.add("bad", "shake"); setTimeout(() => party.input.classList.remove("shake"), 500); party.focus(); return toast("اختار العميل أو المورد", "err"); }
    saving = true; saveBtns.forEach((b) => (b.disabled = true));
    const p = { kind, edit_id: D.edit_id || null, party_id: D.party.id, number: D.number, auto_no: D.number === D.autoNo, date: D.date, due: D.due, discount: D.discount, paid: D.paid,
      pay_type: setup.paytypes ? D.pay_type : null, notes: D.notes, rep_id: kind === "مبيعات" ? D.rep_id : null, vehicle_id: kind === "مبيعات" ? (D.vehicle_id || null) : null, lines: D.lines, request_id: D.request_id || null };
    let creditPw = null;
    try {
      while (true) {
        const r = await api("save_invoice", p, creditPw, D.negPw, !!print);
        if (r.ok && r.request_id) {                 // المندوب: الفاتورة اتبعتت طلب
          toast(`✔ اتبعت طلب الفاتورة (رقم ${r.request_id}) للمحاسب — الصافي ${fmt(r.net)}. هتلاقيه في «طلباتي»`, "ok", 5000);
          S.drafts[kind] = null; S.dirty = false; return go(S.screen, true);
        }
        if (r.ok) {
          if (D.request_id) toast("✔ اتوافق على طلب المندوب", "ok");
          toast(`✔ ${D.edit_id ? "اتحفظ تعديل" : "اتحفظت"} فاتورة ${kind} رقم ${r.number} — الصافي ${fmt(r.net)}` + (print ? " • شاشة الطباعة هتفتح" : ""), "ok", 4200);
          const wasEdit = !!D.edit_id;
          S.drafts[kind] = null; S.dirty = false; loadExpected();
          return go(wasEdit ? "log" : S.screen, true);
        }
        if (r.need === "credit") { creditPw = await askOwner(r.error); if (!creditPw) return; continue; }
        if (r.need === "neg") { D.negPw = await askOwner(r.error); if (!D.negPw) return; continue; }
        return alertBox(r.error, r.title || "مش هينفع تتحفظ");
      }
    } catch (e) { alertBox(e.message, "خطأ"); }
    finally { saving = false; saveBtns.forEach((b) => (b.disabled = false)); }
  }
  let saving = false;
  const saveBtns = [h("button", { class: "btn gold", style: { minHeight: "48px", fontSize: "16px" }, onclick: () => save(true) }, icon("print", 18), "حفظ وطباعة"),
    h("button", { class: "btn primary", style: { minHeight: "48px", fontSize: "16px" }, onclick: () => save(false) }, icon("save", 18), "حفظ (Ctrl+S)")];

  const formCard = h("section", { class: "card anim-up d1" }, h("div", { class: "card-h" }, h("h2", null, "بيانات الفاتورة"), h("span", { class: "pill " + kindClass(kind) }, kind)),
    h("div", { class: "form" },
      h("label", { class: "fld" }, "رقم الفاتورة", noIn), h("label", { class: "fld" }, "التاريخ", dateIn), h("label", { class: "fld" }, "تاريخ الاستحقاق (اختياري)", dueIn),
      h("div", { class: "fld span2" }, h("label", { for: "f-party" }, "العميل / المورد"), party.el),
      repSel ? h("label", { class: "fld" }, "المندوب", repSel) : null, vehSel ? h("label", { class: "fld" }, "التوصيل", vehSel) : null, h("label", { class: "fld" }, "ملاحظات", notesIn)));
  const addCard = h("section", { class: "card anim-up d2" }, h("div", { class: "card-h" }, h("h2", null, "إضافة صنف"), h("span", { class: "hint" }, "Enter بينقلك للخانة اللي بعدها • Enter في السعر = إضافة")),
    h("div", { class: "form add" }, h("div", { class: "fld" }, h("label", { for: "f-item" }, "الصنف"), item.el), h("label", { class: "fld" }, "الكمية", qtyIn),
      h("label", { class: "fld" }, "سعر الوحدة", priceIn), setup.returns_damaged ? h("label", { class: "chk" }, dmgIn, "هالك (لا يرجع للمخزن)") : null,
      h("div", { class: "fld", style: { justifyContent: "flex-end" } }, addBtn)), chips);
  const linesCard = h("section", { class: "card anim-up d3" }, h("div", { class: "card-h" }, h("h2", null, "أصناف الفاتورة"), h("span", { class: "hint" }, "ضغطتين = تعديل • Delete = حذف"),
    h("button", { class: "btn", onclick: () => { const i = [...D.sel][0]; if (i === undefined) return toast("حدد الصنف من الجدول الأول"); editLine(i); } }, icon("edit", 18), "تعديل"),
    h("button", { class: "btn danger", onclick: removeLines }, icon("trash", 18), "حذف")),
    h("div", { class: "tbl-wrap" }, h("table", { class: "t" }, h("thead", null, h("tr", null, h("th", null, "م"), h("th", null, "الصنف"), h("th", { class: "num" }, "الكمية"), h("th", null, "الوحدة"),
      h("th", { class: "num" }, "السعر"), h("th", { class: "num" }, "الإجمالي"), setup.returns_damaged ? h("th", null, "هالك؟") : null,
      setup.show_profit ? [h("th", { class: "num" }, "التكلفة 🔒"), h("th", { class: "num" }, "الربح 🔒")] : null)), tbody, tfoot)));
  const tiles = h("div", { class: "tiles side-tiles" },
    h("div", { class: "tile" }, h("div", { class: "h" }, "الإجمالي"), tv.total),
    h("div", { class: "tile" }, h("div", { class: "h" }, "الخصم"), discIn),
    h("div", { class: "tile net span" }, h("div", { class: "h" }, "الصافي"), tv.net),
    seg ? h("div", { class: "tile span" }, h("div", { class: "h" }, "طريقة الدفع"), seg) : null,
    h("div", { class: "tile" }, h("div", { class: "h" }, setup.paid_label), paidIn),
    h("div", { class: "tile" }, h("div", { class: "h" }, "الباقي"), tv.rest),
    setup.show_profit ? h("div", { class: "tile span" }, h("div", { class: "h" }, "ربح الفاتورة 🔒 (مش بيتطبع)"), tv.profit) : null);
  const side = h("aside", { class: "card inv-side anim-up d2" }, h("h2", { class: "side-h" }, "الحساب"), tiles,
    h("div", { class: "side-acts" }, saveBtns,
      h("button", { class: "btn ghost", onclick: async () => { if (D.lines.length && !(await confirmBox(D.edit_id ? "تلغي التعديل؟ (الفاتورة هتفضل زي ما كانت)" : "تفضّي الفاتورة وتبدأ من الأول؟"))) return; const ed = D.edit_id; S.drafts[kind] = null; S.dirty = false; go(ed ? "log" : S.screen, true); } }, icon("refresh", 18), D.edit_id ? "إلغاء التعديل" : "فاتورة جديدة")));

  box.replaceChildren(h("div", { class: "page" }, h("div", { class: "inv-grid" }, h("div", { class: "inv-main" }, formCard, addCard, linesCard), side)));
  box._save = save;
  enterChain([noIn, dateIn, dueIn]);
  dueIn.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); party.focus(); } });
  enterChain([repSel, vehSel, notesIn].filter(Boolean), () => item.focus());
  enterChain([qtyIn, priceIn], addLine);
  drawLines(); refreshInfo();
  (D.party ? item : party).focus();
}

/* ===================== سجل الفواتير ===================== */
async function renderLog(box) {
  const today = S.boot.today;
  const st = S.logState || (S.logState = { from: today, to: today, kind: "", q: "" });
  const from = h("input", { class: "in", type: "date", value: st.from, "aria-label": "من تاريخ" }), to = h("input", { class: "in", type: "date", value: st.to, "aria-label": "إلى تاريخ" });
  const kind = h("select", { class: "in", "aria-label": "النوع" }, h("option", { value: "" }, "كل الأنواع"), ["مبيعات", "مشتريات", "مرتجع مبيعات", "مرتجع مشتريات"].map((k) => h("option", { value: k }, k)));
  kind.value = st.kind;
  const q = h("input", { class: "in", placeholder: "اسم العميل أو رقم الفاتورة أو المندوب ...", value: st.q, "aria-label": "بحث" });
  let timer = null;
  const T = selTable({ maxH: "calc(100vh - 330px)",
    cols: [{ h: "النوع", key: "kind", fn: (r) => h("span", { class: "pill " + kindClass(r.kind) }, r.kind) }, { h: "رقم", sort: (r) => +r.number || r.number, fn: (r) => h("b", null, r.number) },
      { h: "التاريخ", key: "date" }, { h: "الوقت", key: "time", cls: "hint", sort: (r) => r.date + " " + (r.created_at || r.time) }, { h: "العميل / المورد", key: "party" }, { h: "المندوب", key: "rep", cls: "hint" }, { h: "التوصيل", key: "delivery", cls: "hint" },
      { h: "الدفع", key: "pay", cls: "hint" }, { h: "الصافي", num: true, sort: (r) => r.net, fn: (r) => h("b", null, fmt(r.net)) }, { h: "المدفوع", num: true, cls: "hint", sort: (r) => r.paid, fn: (r) => fmt(r.paid) },
      { h: "طُبعت", sort: (r) => (r.printed ? 1 : 0), fn: (r) => h("span", { title: r.printed ? "اتطبعت" : "لسه ماتطبعتش" }, r.printed ? icon("check", 18) : "") }],
    onOpen: (r) => showInvoice(r.id), empty: "مفيش فواتير في الفترة دي",
    menu: (r) => invoiceMenu(r, load),
    totals: (rs, isSel) => {
      const by = {}; rs.forEach((r) => { by[r.kind] = (by[r.kind] || 0) + r.net; });
      return [h("b", null, isSel ? `المحدد (${rs.length} فاتورة)` : `الإجمالي (${rs.length} فاتورة)`), ...Object.entries(by).map(([k, v]) => totItem(k, fmt(v), k === "مبيعات"))];
    } });
  async function load() {
    st.from = from.value; st.to = to.value || from.value; st.kind = kind.value; st.q = q.value;
    try { T.setRows(await api("invoices", st.from, st.to, st.kind, st.q)); } catch (e) { return toast(e.message, "err"); }
  }
  [from, to, kind].forEach((x) => x.addEventListener("change", load));
  q.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(load, 250); });
  box.replaceChildren(h("div", { class: "page" },
    h("section", { class: "card anim-up d1" }, h("div", { class: "form" }, h("label", { class: "fld" }, "من تاريخ", from), h("label", { class: "fld" }, "إلى تاريخ", to),
      h("label", { class: "fld" }, "النوع", kind), h("label", { class: "fld span2" }, "بحث سريع", q))),
    h("section", { class: "card anim-up d2" }, h("div", { class: "card-h" }, h("h2", null, "الفواتير"), h("span", { class: "hint" }, "ضغطتين = تفتح الفاتورة • اسحب أو Ctrl + ضغطة = تحدد أكتر من واحدة • اضغط على عنوان العمود = ترتيب")),
      T.el)));
  await load();
}

/* اسم العميل/المورد كلينك: يقفل الشاشة ويفتح كشف حسابه */
function partyLink(name, pid) {
  if (!pid || !can("acc:statement")) return h("b", null, name);
  return h("a", { href: "#", class: "plink", title: "افتح كشف الحساب", onclick: (e) => { e.preventDefault(); closeModals(); S.pendingStatement = pid; go("acc:statement", true); } }, name);
}

/* ===================== عرض فاتورة ===================== */
async function showInvoice(id) {
  let v;
  try { v = await api("invoice", id); } catch (e) { return toast(e.message, "err"); }
  const body = [
    h("div", { class: "chips", style: { padding: 0 } },
      h("div", { class: "chip" }, "التاريخ: ", h("b", null, `${v.date} ${v.time}`)), v.due ? h("div", { class: "chip" }, "الاستحقاق: ", h("b", null, v.due)) : null,
      h("div", { class: "chip" }, "الحساب: ", partyLink(v.party, v.party_id)), v.rep ? h("div", { class: "chip" }, "المندوب: ", h("b", null, v.rep)) : null, v.delivery ? h("div", { class: "chip" }, "التوصيل: ", h("b", null, v.delivery)) : null,
      v.pay ? h("div", { class: "chip" }, "الدفع: ", h("b", null, v.pay)) : null, v.printed ? h("div", { class: "chip info" }, `اتطبعت ${v.print_count} مرة`) : null),
    h("div", { class: "tbl-wrap card" }, h("table", { class: "t" },
      h("thead", null, h("tr", null, h("th", null, "م"), h("th", null, "الصنف"), h("th", { class: "num" }, "الكمية"), h("th", null, "الوحدة"), h("th", { class: "num" }, "السعر"), h("th", { class: "num" }, "الإجمالي"))),
      h("tbody", null, v.lines.map((l, i) => h("tr", null, h("td", { class: "hint" }, i + 1), h("td", null, h("b", null, l.name), l.damaged ? h("span", { style: { color: "var(--red)" } }, " (هالك)") : null),
        h("td", { class: "num" }, fq(l.qty)), h("td", { class: "hint" }, l.unit), h("td", { class: "num" }, fmt(l.price)), h("td", { class: "num" }, h("b", null, fmt(l.total)))))),
      h("tfoot", null, h("tr", null, h("td"), h("td", null, `${v.lines.length} صنف`), h("td", { colspan: 3, class: "hint" }, qtyText(v.lines)), h("td", { class: "num" }, fmt(v.total)))))),
    h("div", { class: "tiles" }, h("div", { class: "tile" }, h("div", { class: "h" }, "الإجمالي"), h("div", { class: "v" }, fmt(v.total))),
      h("div", { class: "tile" }, h("div", { class: "h" }, "الخصم"), h("div", { class: "v" }, fmt(v.discount))),
      h("div", { class: "tile net" }, h("div", { class: "h" }, "الصافي"), h("div", { class: "v" }, fmt(v.net))),
      h("div", { class: "tile" }, h("div", { class: "h" }, "المدفوع مع الفاتورة"), h("div", { class: "v" }, fmt(v.paid))),
      v.profit !== undefined ? h("div", { class: "tile" }, h("div", { class: "h" }, "ربح الفاتورة 🔒"), h("div", { class: "v", style: { color: v.profit < 0 ? "var(--red)" : "var(--green)" } }, fmt(v.profit))) : null),
    v.notes ? h("div", { class: "hint" }, "ملاحظات: " + v.notes) : null,
  ];
  modal({ title: `فاتورة ${v.kind} رقم ${v.number}`, body, wide: true, enter: false, actions: [
    { label: "طباعة", cls: "gold", icon: "print", value: async () => { try { await api("print_invoice", id); toast("🖨 شاشة الطباعة هتفتح خلال ثواني ...", "ok"); } catch (e) { toast(e.message, "err"); } return true; } },
    { label: "تعديل", icon: "edit", value: () => { editInvoice(id); return true; } },
    { label: "حذف", cls: "danger", icon: "trash", value: async () => { if (await deleteInvoice(id, `فاتورة ${v.kind} رقم ${v.number}`)) { if (S.screen === "log" || S.screen === "home") go(S.screen, true); return true; } return false; } },
    { label: "قفل", ret: true }] });
}

/* ===================== أدوات الجداول ===================== */
const dateIn = (v, label) => h("input", { class: "in", type: "date", value: v, "aria-label": label });
const monthStart = () => S.boot.today.slice(0, 8) + "01";
/* جدول بتحديد (ضغطة / Ctrl / Shift / سحب)، وضغطتين = فتح، وإجمالي المحدد */
function selTable({ cols, onOpen, onKey, totals, empty = "مفيش بيانات", maxH = "calc(100vh - 340px)", rowClass, menu }) {
  let rows = [], base = [], sel = new Set(), anchor = -1, drag = false, sortCol = -1, sortDir = 0;
  const tbody = h("tbody"), foot = h("div", { class: "tot-bar" });
  // الترتيب: ضغطة = من الأصغر للأكبر • ضغطتين = من الأكبر للأصغر • التالتة = زي ما كان
  const sortVal = (c, r) => {
    let v = c.sort ? c.sort(r) : c.key !== undefined ? r[c.key] : c.fn ? c.fn(r) : "";
    if (v instanceof Node) v = v.textContent;
    if (typeof v === "number") return v;
    const t = String(v ?? "").trim(), n = t.replace(/,/g, "").replace(/[^\d.\-]/g, "");
    if ((c.num || /^-?[\d,]+(\.\d+)?$/.test(t)) && n !== "" && !isNaN(+n)) return +n;
    return c.num ? -Infinity : t;
  };
  const ths = cols.map((c, ci) => h("th", { class: (c.num ? "num " : "") + (c.nosort ? "" : "sortable"), title: c.nosort ? null : "اضغط للترتيب",
    onclick: c.nosort ? null : () => { if (sortCol !== ci) { sortCol = ci; sortDir = 1; } else sortDir = sortDir === 1 ? -1 : sortDir === -1 ? 0 : 1; if (!sortDir) sortCol = -1; render(); } },
    c.h, h("span", { class: "sort-i" })));
  const table = h("table", { class: "t" }, h("thead", null, h("tr", null, ths)), tbody);
  const wrap = h("div", { class: "tbl-wrap", style: { maxHeight: maxH } }, table);
  foot._wrap = wrap;
  const paint = () => { [...tbody.children].forEach((tr, i) => tr.classList.toggle("sel", sel.has(i))); drawTot(); };
  const drawTot = () => { if (!totals) return; const picked = sel.size > 1 ? rows.filter((_, i) => sel.has(i)) : rows; foot.replaceChildren(...[].concat(totals(picked, sel.size > 1)).filter((x) => x !== null && x !== undefined && x !== false)); };
  function setRows(rs) { base = rs.slice(); render(); }
  function render() {
    rows = base.slice();
    if (sortCol >= 0 && sortDir) {
      const c = cols[sortCol], vals = new Map(rows.map((r) => [r, sortVal(c, r)]));
      const blank = (v) => v === -Infinity || v === "";          // الخانات الفاضية دايمًا في الآخر
      rows.sort((a, b) => { const x = vals.get(a), y = vals.get(b); if (blank(x) !== blank(y)) return blank(x) ? 1 : -1;
        const r = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y), "ar", { numeric: true }); return r * sortDir; });
    }
    ths.forEach((th, i) => { th.classList.toggle("asc", i === sortCol && sortDir === 1); th.classList.toggle("desc", i === sortCol && sortDir === -1); });
    sel = new Set(); anchor = -1;
    tbody.replaceChildren(...rows.map((r, i) => {
      const tr = h("tr", { class: "click " + (rowClass ? rowClass(r) || "" : ""), tabindex: "0",
        onmousedown: (e) => {
          if (e.button !== 0) return;
          if (e.shiftKey && anchor >= 0) { sel = new Set(); for (let k = Math.min(anchor, i); k <= Math.max(anchor, i); k++) sel.add(k); }
          else if (e.ctrlKey) { sel.has(i) ? sel.delete(i) : sel.add(i); anchor = i; }
          else { sel = new Set([i]); anchor = i; drag = true; startAuto(e); }
          paint();
        },
        onmouseenter: () => { if (drag && anchor >= 0) { sel = new Set(); for (let k = Math.min(anchor, i); k <= Math.max(anchor, i); k++) sel.add(k); paint(); } },
        ondblclick: () => onOpen && onOpen(r),
        oncontextmenu: menu ? (e) => { e.preventDefault(); if (!sel.has(i)) { sel = new Set([i]); anchor = i; paint(); } ctxMenu(e, menu(r)); } : null,
        onkeydown: (e) => { if (e.key === "Enter" && onOpen) onOpen(r); else if (onKey) onKey(e, r); } },
        cols.map((c) => h("td", { class: (c.num ? "num " : "") + (c.cls || "") }, c.fn ? c.fn(r) : r[c.key])));
      return tr;
    }));
    if (!rows.length) tbody.replaceChildren(h("tr", null, h("td", { colspan: cols.length, class: "empty" }, empty)));
    drawTot();
  }
  // وانت بتحدد بالسحب: لما الماوس يقرّب من تحت (أو فوق) الجدول/الشاشة، بينزل (أو يطلع) لوحده ويكمّل التحديد
  let ax = 0, ay = 0, raf = 0;
  const onMove = (e) => { ax = e.clientX; ay = e.clientY; if (drag) extendAt(); };
  // المنطقة الظاهرة فعلًا من الجدول (من غير الهيدر اللي فوق والشريط اللي تحت)
  function visRect() {
    const w = wrap.getBoundingClientRect();
    const hdr = (document.querySelector(".top") || { getBoundingClientRect: () => ({ bottom: 0 }) }).getBoundingClientRect().bottom;
    const bar = document.querySelector("#pagebar:not([hidden]), #todaybar:not([hidden])");
    const barTop = bar ? bar.getBoundingClientRect().top : innerHeight;
    return { top: Math.max(w.top, hdr, 0), bottom: Math.min(w.bottom, barTop, innerHeight), wTop: w.top, wBottom: w.bottom, barTop, hdr };
  }
  function extendAt() {
    const v = visRect();
    const y = Math.min(Math.max(ay, v.top + 6), v.bottom - 6);           // لو الماوس على الشريط اللي تحت: ناخد آخر سطر ظاهر
    const el = document.elementFromPoint(Math.min(Math.max(ax, 1), innerWidth - 2), y);
    const tr = el && el.closest && el.closest("tr"); if (!tr || tr.parentNode !== tbody) return;
    const i = [...tbody.children].indexOf(tr);
    if (i >= 0 && anchor >= 0) { const ns = new Set(); for (let k = Math.min(anchor, i); k <= Math.max(anchor, i); k++) ns.add(k); if (ns.size !== sel.size || ![...ns].every((k) => sel.has(k))) { sel = ns; paint(); } }
  }
  function tick() {
    if (!drag) { raf = 0; return; }
    const r = visRect(), edge = 56; let v = 0;
    if (ay > r.bottom - edge) v = Math.min(30, Math.ceil((ay - (r.bottom - edge)) / 3));
    else if (ay < r.top + edge) v = -Math.min(30, Math.ceil(((r.top + edge) - ay) / 3));
    if (v) {
      const se = document.scrollingElement || document.documentElement;
      // الأول الصفحة نفسها لو الجدول مكمّل برا الشاشة، وبعدين الجدول من جوه
      const pageCan = v > 0 ? (r.wBottom > r.barTop + 1 && se.scrollTop + se.clientHeight < se.scrollHeight - 1) : (r.wTop < r.hdr - 1 && se.scrollTop > 0);
      if (pageCan) window.scrollBy(0, v);
      else if (wrap.scrollHeight > wrap.clientHeight + 2) wrap.scrollTop += v;
      else window.scrollBy(0, v);
      extendAt();
    }
    raf = requestAnimationFrame(tick);
  }
  function startAuto(e) { ax = e.clientX; ay = e.clientY; document.addEventListener("mousemove", onMove); if (!raf) raf = requestAnimationFrame(tick); }
  document.addEventListener("mouseup", () => { drag = false; document.removeEventListener("mousemove", onMove); });
  if (totals) setTimeout(pinTotals, 0);
  return { el: h("div", null, wrap, totals ? foot : null), setRows, selected: () => rows.filter((_, i) => sel.has(i)), rows: () => rows };
}
// شريط الإجمالي بتاع الجدول الأساسي في الشاشة بيتثبت تحت (مكان شريط «اليوم») زي السيستم القديم
function pinTotals() {
  const pb = $("#pagebar"), tb = $("#todaybar"); if (!pb || !tb) return;
  const cur = pb.firstElementChild;
  if (!cur || !(cur._wrap && cur._wrap.isConnected)) {
    const t = [...document.querySelectorAll("#screen .tot-bar")].find((x) => x._wrap && x._wrap.isConnected);
    pb.replaceChildren(...(t ? [t] : []));
  }
  const on = !!pb.firstElementChild;
  pb.hidden = !on; tb.hidden = on || S.screen !== "home";      // شريط «اليوم» في الرئيسية بس، والشاشات اللي فيها جداول بيظهر إجماليها
}
const totItem = (label, value, strong) => h("span", { class: "ti" + (strong ? " strong" : "") }, label + ": ", h("b", null, value));
const money = (v) => fmt(v);
const numOrEmpty = (v) => (Math.abs(v) > 0.004 ? fmt(v) : "");

/* قايمة كليك يمين صغيرة */
function ctxMenu(e, items) {
  document.querySelectorAll(".ctx").forEach((m) => m.remove());
  const m = h("div", { class: "ctx", role: "menu" }, items.map((it) => h("button", { class: "ctx-i" + (it.danger ? " danger" : ""), disabled: it.disabled ? true : null,
    onclick: () => { m.remove(); if (it.fn) it.fn(); } }, it.label)));
  document.body.appendChild(m);
  const r = m.getBoundingClientRect();
  m.style.left = Math.min(e.clientX, innerWidth - r.width - 8) + "px"; m.style.top = Math.min(e.clientY, innerHeight - r.height - 8) + "px";
  const off = (ev) => { if (!m.contains(ev.target) || ev.key === "Escape") { m.remove(); document.removeEventListener("mousedown", off, true); document.removeEventListener("keydown", off, true); document.removeEventListener("touchstart", off, true); } };
  setTimeout(() => { document.addEventListener("mousedown", off, true); document.addEventListener("keydown", off, true); document.addEventListener("touchstart", off, true); }, 0);
}
/* الموبايل: الضغط المطوّل على أي حاجة ليها قايمة كليك يمين = يفتح القايمة (آيفون مابيبعتش كليك يمين لوحده) */
(() => {
  let tm = null, x0 = 0, y0 = 0, tgt = null, nativeFired = false, fired = false;
  const cancel = () => { clearTimeout(tm); tm = null; };
  document.addEventListener("touchstart", (e) => {
    if (e.touches.length !== 1) return cancel();
    const t = e.touches[0]; x0 = t.clientX; y0 = t.clientY; tgt = e.target; nativeFired = false; fired = false;
    if (tgt.closest(".ctx, input, textarea, select")) return;
    cancel();
    tm = setTimeout(() => {
      tm = null; if (nativeFired) return;
      fired = true;
      const el = (tgt && tgt.isConnected ? tgt : null) || document.elementFromPoint(x0, y0) || tgt;   // الجدول ممكن يكون اترسم من جديد
      el.dispatchEvent(new MouseEvent("contextmenu", { bubbles: true, cancelable: true, clientX: x0, clientY: y0 }));
      if (navigator.vibrate) try { navigator.vibrate(15); } catch (_) {}
    }, 550);
  }, { passive: true });
  document.addEventListener("touchmove", (e) => { const t = e.touches[0]; if (t && Math.hypot(t.clientX - x0, t.clientY - y0) > 10) cancel(); }, { passive: true });
  document.addEventListener("touchend", (e) => { cancel(); if (fired) { e.preventDefault(); fired = false; } }, { passive: false });
  document.addEventListener("touchcancel", cancel, { passive: true });
  document.addEventListener("contextmenu", (e) => { if (e.isTrusted) { nativeFired = true; cancel(); } }, true);
})();

/* ===================== السندات: سند جديد / تعديل ===================== */
const VKINDS = [["تحصيل", "تحصيل من عميل"], ["دفع", "دفع لمورد"], ["مصروف", "مصروفات"], ["خصم مسموح به", "خصم مسموح به"]];
async function renderVoucher(box) {
  const st = await api("voucher_setup");
  const E = S.voucherEdit || null;           // { edit_id, kind, ... }
  const V = { kind: E ? E.kind : (S.lastVKind || "تحصيل"), party: null, rep_id: E ? E.rep_id : null, cat: E ? E.cat || "" : "", date: E ? E.date : st.today,
    amount: E ? String(E.amount) : "", notes: E ? E.notes : "" };
  if (E && E.party_id) V.party = st.parties.find((p) => p.id === E.party_id) || null;
  if (S.pendingVoucherParty) { V.party = st.parties.find((p) => p.id === S.pendingVoucherParty) || null; S.pendingVoucherParty = null; }
  if (S.me.rep) V.kind = "تحصيل";                     // المندوب: تحصيل بس
  const seg = h("div", { class: "seg" }, VKINDS.filter(([k]) => !S.me.rep || k === "تحصيل").map(([k, lab]) => h("button", { "data-v": k, class: V.kind === k ? "on" : "", disabled: E && E.kind !== k ? true : null,
    onclick: () => { V.kind = k; S.lastVKind = k; seg.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.v === k)); layout(); preview(); } }, lab)));
  const party = combo({ id: "v-party", label: "العميل / المورد", placeholder: "اكتب جزء من الاسم ...", items: () => st.parties, sub: (p) => p.kind,
    onPick: (p, adv) => { V.party = p; if (p && V.kind === "تحصيل") { V.rep_id = p.rep_id || null; repSel.value = String(V.rep_id ?? ""); layout(); } preview(); if (adv) (V.kind === "تحصيل" ? repSel : amountIn).focus(); } });
  if (V.party) party.set(V.party);
  const repSel = h("select", { class: "in", "aria-label": "المندوب", onchange: () => { V.rep_id = repSel.value ? +repSel.value : null; layout(); } }, st.reps.map((r) => h("option", { value: r.id ?? "" }, r.label)));
  // طريقة الدفع + مع مين الفلوس (للجرد)
  V.method = (E && E.method) || V.method || "كاش"; V.holder = (E && E.holder) || V.holder || "";
  const methodSel = h("select", { class: "in", "aria-label": "طريقة الدفع", onchange: () => { V.method = methodSel.value; } }, (st.methods || ["كاش"]).map((m) => h("option", { value: m }, m)));
  if (!(st.methods || []).includes(V.method)) V.method = "كاش";
  methodSel.value = V.method;
  const hs = st.holders || { owners: [], accountants: [], drawer: "درج" };
  const holderSel = h("select", { class: "in", "aria-label": "الفلوس مع", onchange: () => { V.holder = holderSel.value; } });
  const repName = () => { const r = st.reps.find((x) => x.id === V.rep_id); return r ? r.label.replace(/^\d+\s*-\s*/, "") : "المندوب"; };
  function fillHolders() {                     // لو فيه مندوب: الفلوس معاه (الافتراضي) أو سلّمها للدرج / مالك / محاسب
    const keep = V.holder;
    holderSel.replaceChildren(V.rep_id ? h("option", { value: "" }, `مع المندوب (${repName()})`) : null, h("option", { value: hs.drawer }, "الدرج (خزنة المخزن)"),
      hs.owners.length ? h("optgroup", { label: "الملاك" }, hs.owners.map((o) => h("option", { value: o }, o))) : null,
      hs.accountants.length ? h("optgroup", { label: "المحاسبين" }, hs.accountants.map((o) => h("option", { value: o }, o))) : null);
    holderSel.value = [...holderSel.options].some((o) => o.value === keep) ? keep : (V.rep_id ? "" : hs.drawer);
    V.holder = holderSel.value;
  }
  if (E && E.rep_id && E.holder && E.holder !== hs.drawer && !hs.owners.includes(E.holder) && !hs.accountants.includes(E.holder)) V.holder = "";
  fillHolders();
  const fMethod = h("label", { class: "fld" }, "طريقة الدفع", methodSel), fHolder = h("label", { class: "fld" }, "الفلوس مع", holderSel);
  if (V.rep_id && !st.reps.some((r) => r.id === V.rep_id)) repSel.appendChild(h("option", { value: V.rep_id }, "مندوب (مش نشط)"));
  repSel.value = String(V.rep_id ?? "");
  const catSel = h("select", { class: "in", "aria-label": "البند", onchange: () => { V.cat = catSel.value; } }, h("option", { value: "" }, "— اختار البند —"), st.cats.map((c) => h("option", { value: c }, c)));
  catSel.value = V.cat;
  catSel.addEventListener("contextmenu", (e) => {            // كليك يمين = تعديل أو حذف البند المختار (بكلمة سر اليوزر)
    e.preventDefault();
    const name = catSel.value;
    const askPw = (what) => promptBox(`اكتب كلمة السر بتاعتك (${S.me.username}) عشان ${what}:`, "🔒 تأكيد", { password: true });
    if (!name) return ctxMenu(e, [{ label: "اختار البند الأول وبعدين كليك يمين", disabled: true }]);
    ctxMenu(e, [
      { label: `🗑 حذف «${name}»`, danger: true, fn: async () => {
        if (!(await confirmBox(`تمسح البند «${name}» من القايمة؟\n(المصروفات القديمة اللي عليه هتفضل زي ما هي)`, "حذف بند", "أيوه، امسحه"))) return;
        const pw = await askPw("تمسح البند"); if (pw === null) return;
        try {
          const r = await api("delete_expense_cat", name, pw);
          st.cats = st.cats.filter((c) => c !== name); [...catSel.options].forEach((o) => { if (o.value === name) o.remove(); }); catSel.value = V.cat = "";
          toast(`✔ اتمسح البند «${name}»` + (r.used ? ` — ${r.used} مصروف قديم فضل زي ما هو` : ""), "ok", 4500);
        } catch (x) { alertBox(x.message, "مينفعش يتمسح"); }
      } },
      { label: `✏️ تعديل اسم «${name}»`, fn: async () => {
        const nn = await promptBox(`الاسم الجديد للبند «${name}»:`, "تعديل بند", { value: name }); if (nn === null || !nn.trim() || nn.trim() === name) return;
        const pw = await askPw("تعدّل البند"); if (pw === null) return;
        try {
          const r = await api("rename_expense_cat", name, nn, pw);
          st.cats = st.cats.map((c) => (c === name ? r.name : c));
          [...catSel.options].forEach((o) => { if (o.value === name) { o.value = r.name; o.textContent = r.name; } }); catSel.value = V.cat = r.name;
          toast(`✔ البند بقى «${r.name}»` + (r.used ? ` — واتعدّل في ${r.used} مصروف قديم` : ""), "ok", 4500);
        } catch (x) { alertBox(x.message, "مينفعش يتعدّل"); }
      } }]);
  });
  const addCat = h("button", { class: "btn", type: "button", onclick: async () => { const n = await promptBox("اسم البند (مثال: صيانة، كهربا، شيال):", "بند جديد"); if (!n) return;
    try { const nm = await api("add_expense_cat", n); if (!st.cats.includes(nm)) { st.cats.push(nm); catSel.appendChild(h("option", { value: nm }, nm)); } catSel.value = V.cat = nm; } catch (e) { toast(e.message, "err"); } } }, icon("plus", 16), "بند جديد");
  const dIn = h("input", { class: "in", type: "date", value: V.date, "aria-label": "التاريخ", onchange: () => { V.date = dIn.value; } });
  const amountIn = h("input", { class: "in num", id: "v-amount", value: V.amount, inputmode: "decimal", "aria-label": "المبلغ", oninput: () => { V.amount = amountIn.value; S.dirty = !!V.amount; preview(); } });
  const notesIn = h("input", { class: "in", value: V.notes, "aria-label": "ملاحظات", oninput: () => { V.notes = notesIn.value; } });
  const fParty = h("div", { class: "fld span2" }, h("label", { for: "v-party" }, "العميل / المورد"), party.el);
  const fRep = h("label", { class: "fld" }, "المندوب (للتحصيل)", repSel);
  const fCat = h("div", { class: "fld span2" }, h("span", null, "البند"), h("div", { style: { display: "flex", gap: "8px" } }, catSel, addCat));
  const tBefore = h("div", { class: "v" }, "—"), tAmt = h("div", { class: "v" }, "0.00"), tAfter = h("div", { class: "v" }, "—");
  const tiles = h("div", { class: "tiles" }, h("div", { class: "tile" }, h("div", { class: "h" }, "رصيد الحساب الحالي"), tBefore),
    h("div", { class: "tile net" }, h("div", { class: "h" }, "مبلغ السند"), tAmt), h("div", { class: "tile" }, h("div", { class: "h" }, "الرصيد بعد السند"), tAfter));
  let pvT = null;
  function preview() {
    tAmt.textContent = fmt(num(V.amount));
    clearTimeout(pvT);
    pvT = setTimeout(async () => {
      if (V.kind === "مصروف" || !V.party) { tBefore.textContent = tAfter.textContent = "—"; return; }
      try { const r = await api("voucher_preview", V.kind, V.party.id, V.amount, E ? E.edit_id : null); tBefore.textContent = fmt(r.before); tAfter.textContent = fmt(r.after); } catch (e) { }
    }, 200);
  }
  function layout() {
    const exp = V.kind === "مصروف";
    fParty.style.display = exp ? "none" : ""; fCat.style.display = exp ? "" : "none"; fRep.style.display = V.kind === "تحصيل" ? "" : "none";
    fMethod.style.display = V.kind === "تحصيل" ? "" : "none";
    fHolder.style.display = V.kind === "تحصيل" && !S.me.rep ? "" : "none";
    fillHolders();
    tiles.style.display = exp ? "none" : ""; printBtn.style.display = exp ? "none" : "";
  }
  let saving = false;
  async function save(print) {
    if (saving) return;
    if (V.kind !== "مصروف" && !V.party) { party.input.classList.add("bad", "shake"); setTimeout(() => party.input.classList.remove("shake"), 500); party.focus(); return toast("اختار الاسم", "err"); }
    saving = true;
    try {
      const sv = await api("save_voucher", { kind: V.kind, party_id: V.party ? V.party.id : null, rep_id: V.rep_id, cat: V.cat, date: V.date, amount: V.amount, notes: V.notes, edit_id: E ? E.edit_id : null,
        method: V.method, holder: V.holder || "" }, !!print);
      if (sv && sv.request_id) toast(`✔ اتبعت طلب التحصيل (رقم ${sv.request_id}) — ${fmt(num(V.amount))} للمحاسب. هتلاقيه في «طلباتي»`, "ok", 5000);
      else toast(E ? "✔ اتحفظ تعديل السند" : `✔ اتحفظ السند — ${fmt(num(V.amount))}` + (print ? " • شاشة الطباعة هتفتح" : ""), "ok");
      S.dirty = false;
      if (E) { S.voucherEdit = null; return go("vch:log", true); }
      V.amount = ""; V.notes = ""; amountIn.value = ""; notesIn.value = ""; party.set(null); V.party = null; preview();
      (V.kind === "مصروف" ? catSel : party.input).focus();
    } catch (e) { alertBox(e.message, "مش هينفع يتحفظ"); }
    finally { saving = false; }
  }
  const printBtn = h("button", { class: "btn gold", style: { minHeight: "48px" }, onclick: () => save(true) }, icon("print", 18), "حفظ وطباعة إيصال");
  box.replaceChildren(h("div", { class: "page" },
    h("section", { class: "card anim-up d1" }, h("div", { class: "card-h" }, h("h2", null, E ? `تعديل سند رقم ${E.edit_id}` : "سند جديد"), h("span", { class: "hint" }, "Enter بينقلك للخانة اللي بعدها • Ctrl+S = حفظ")),
      h("div", { class: "form" }, h("div", { class: "fld span2" }, h("span", null, "نوع السند"), seg), fParty, fRep, fMethod, fHolder, fCat,
        h("label", { class: "fld" }, "التاريخ", dIn), h("label", { class: "fld", style: { gridColumnStart: "1" } }, "المبلغ", amountIn), h("label", { class: "fld span2" }, "ملاحظات", notesIn))),
    h("div", { class: "anim-up d2" }, tiles),
    h("div", { class: "bar-actions anim-up d3" }, h("button", { class: "btn primary", style: { minHeight: "48px" }, onclick: () => save(false) }, icon("save", 18), E ? "حفظ التعديل" : "حفظ السند (Ctrl+S)"), printBtn,
      E ? h("button", { class: "btn ghost", onclick: () => { S.voucherEdit = null; S.dirty = false; go("vch:log", true); } }, "إلغاء التعديل") : null,
      h("span", { style: { flex: 1 } }), h("button", { class: "btn", onclick: () => go("vch:log") }, icon("list", 18), "سجل السندات"))));
  box._save = save;
  enterChain([amountIn, notesIn], () => save(false));
  repSel.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); amountIn.focus(); } });
  catSel.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); amountIn.focus(); } });
  layout(); preview();
  if (E) amountIn.focus(); else (V.kind === "مصروف" ? catSel : party.input).focus();
}

/* ===================== سجل السندات ===================== */
async function renderVouchers(box) {
  const st = await api("voucher_setup");
  const L = S.vlog || (S.vlog = { from: S.boot.today, to: S.boot.today, type: "الكل", rep: "الكل", q: "" });
  const from = dateIn(L.from, "من"), to = dateIn(L.to, "إلى");
  const typ = h("select", { class: "in", "aria-label": "النوع" }, ["الكل", "تحصيل من عميل", "دفع لمورد", "خصم مسموح به", "مصروفات", "مرتبات", "سلف", "عمولات"].map((x) => h("option", { value: x }, x)));
  typ.value = L.type;
  const rep = h("select", { class: "in", "aria-label": "المندوب" }, h("option", { value: "الكل" }, "كل المناديب"), st.reps.map((r) => h("option", { value: r.id ?? "office" }, r.label)));
  rep.value = L.rep;
  const q = h("input", { class: "in", placeholder: "الاسم أو البند أو الملاحظات ...", value: L.q, "aria-label": "بحث" });
  const T = selTable({
    cols: [{ h: "التاريخ", key: "date" }, { h: "الوقت", key: "time", cls: "hint" }, { h: "النوع", fn: (r) => h("span", { class: "pill " + (r.type.startsWith("تحصيل") ? "k-مبيعات" : r.type.startsWith("دفع") ? "k-مشتريات" : "k-مرتجع") }, r.type) },
      { h: "الاسم / البند", fn: (r) => h("b", null, r.name) }, { h: "المندوب", key: "rep", cls: "hint" }, { h: "المبلغ", num: true, fn: (r) => h("b", null, fmt(r.amount)) },
      { h: "ملاحظات", fn: (r) => [r.notes, r.invoice ? h("span", { class: "pill k-مشتريات", style: { marginInlineStart: "6px" } }, "مع فاتورة " + r.invoice) : null], cls: "hint" }],
    onOpen: (r) => openVoucher(r),
    onKey: (e) => { if (e.key === "Delete") del(); },
    menu: (r) => [{ label: "👁 عرض", fn: () => viewVoucher(r) }, { label: "🗑 حذف", danger: true, fn: () => del() }, { label: "✏️ تعديل", fn: () => openVoucher(r) }],
    totals: (rs, isSel) => {
      const sum = (f) => rs.filter(f).reduce((a, r) => a + r.amount, 0);
      const inn = sum((r) => r.type === "تحصيل من عميل"), out = sum((r) => r.type === "دفع لمورد"), dsc = sum((r) => r.type === "خصم مسموح به");
      const exp = sum((r) => ["مصروفات", "مرتبات", "سلف", "عمولات"].includes(r.type.split(" (")[0]));
      return [h("b", null, isSel ? "إجمالي المحدد" : "الإجمالي"), totItem("العدد", rs.length), totItem("التحصيلات", fmt(inn)), totItem("المدفوعات", fmt(out)),
        totItem("المصروفات والمرتبات والسلف", fmt(exp)), dsc ? totItem("خصم مسموح به", fmt(dsc)) : null, totItem("الصافي", fmt(inn - out - exp), true)];
    } });
  async function load() {
    L.from = from.value; L.to = to.value || from.value; L.type = typ.value; L.rep = rep.value; L.q = q.value;
    try { T.setRows(await api("vouchers", L.from, L.to, L.type, L.rep === "الكل" ? null : L.rep, L.q)); } catch (e) { toast(e.message, "err"); }
  }
  async function openVoucher(r) {
    if (r.invoice_id) return showInvoice(r.invoice_id);
    try { const v = await api("voucher", r.key); S.voucherEdit = v; go("vch:new", true); } catch (e) { alertBox(e.message); }
  }
  function viewVoucher(r) {
    if (r.invoice_id) return showInvoice(r.invoice_id);
    const row = (k, v) => v ? h("div", { class: "chip" }, k + ": ", h("b", null, v)) : null;
    modal({ title: `سند ${r.type}`, enter: false, body: h("div", { class: "chips", style: { padding: 0, flexWrap: "wrap" } },
        row("التاريخ", `${r.date} ${r.time || ""}`), r.party_id ? h("div", { class: "chip" }, "الاسم: ", partyLink(r.name, r.party_id)) : row("الاسم / البند", r.name), row("المبلغ", fmt(r.amount)), row("المندوب", r.rep), row("ملاحظات", r.notes)),
      actions: [r.key.startsWith("p-") ? { label: "طباعة إيصال", cls: "gold", icon: "print", value: async () => { try { await api("print_receipt", r.id); toast("🖨 شاشة الطباعة هتفتح خلال ثواني ...", "ok"); } catch (e) { toast(e.message, "err"); } return true; } } : null,
        { label: "تعديل", icon: "edit", value: () => { openVoucher(r); return true; } }, { label: "قفل", ret: true }].filter(Boolean) });
  }
  async function del() {
    const r = T.selected()[0]; if (!r) return toast("حدد سند الأول");
    if (r.invoice_id) return alertBox("السند ده دفعة مع فاتورة. عدّل المبلغ المدفوع من تعديل الفاتورة.");
    if (!(await confirmBox(`تحذف السند «${r.type} — ${r.name} — ${fmt(r.amount)}» نهائيًا؟`, "حذف سند", "احذف"))) return;
    try { await api("delete_voucher", r.key); toast("✔ السند اتحذف", "ok"); load(); } catch (e) { alertBox(e.message); }
  }
  async function printSel() {
    const r = T.selected()[0]; if (!r) return toast("حدد سند الأول");
    if (!r.key.startsWith("p-")) return toast("الإيصال لسندات التحصيل والدفع بس");
    try { await api("print_receipt", r.id); toast("🖨 شاشة الطباعة هتفتح خلال ثواني ...", "ok"); } catch (e) { toast(e.message, "err"); }
  }
  function summary() {
    const agg = new Map(); T.rows().forEach((r) => { const k = r.type + "|" + r.name; agg.set(k, (agg.get(k) || 0) + r.amount); });
    const rows = [...agg.entries()].map(([k, v]) => [...k.split("|"), v]).sort((a, b) => a[0].localeCompare(b[0]) || b[2] - a[2]);
    modal({ title: `ملخص السندات من ${L.from} إلى ${L.to}`, enter: false, body: h("div", { class: "tbl-wrap card" }, h("table", { class: "t" },
      h("thead", null, h("tr", null, h("th", null, "النوع"), h("th", null, "الاسم / البند"), h("th", { class: "num" }, "الإجمالي"))),
      h("tbody", null, rows.map((r) => h("tr", null, h("td", null, r[0]), h("td", null, h("b", null, r[1])), h("td", { class: "num" }, fmt(r[2]))))))), actions: [{ label: "قفل", ret: true }] });
  }
  [from, to, typ, rep].forEach((x) => x.addEventListener("change", load));
  let t = null; q.addEventListener("input", () => { clearTimeout(t); t = setTimeout(load, 250); });
  box.replaceChildren(h("div", { class: "page" },
    h("section", { class: "card anim-up d1" }, h("div", { class: "form" }, h("label", { class: "fld" }, "من", from), h("label", { class: "fld" }, "إلى", to),
      h("label", { class: "fld" }, "النوع", typ), h("label", { class: "fld" }, "المندوب (التحصيل)", rep), h("label", { class: "fld span2" }, "بحث", q))),
    h("section", { class: "card anim-up d2" }, h("div", { class: "card-h" }, h("h2", null, "السندات"),
      h("button", { class: "btn primary", onclick: () => { S.voucherEdit = null; go("vch:new", true); } }, icon("plus", 18), "سند جديد"),
      h("button", { class: "btn", onclick: () => { const r = T.selected()[0]; if (!r) return toast("حدد سند الأول"); openVoucher(r); } }, icon("edit", 18), "تعديل"),
      h("button", { class: "btn gold", onclick: printSel }, icon("print", 18), "طباعة إيصال"),
      h("button", { class: "btn", onclick: summary }, icon("chart", 18), "ملخص البنود"),
      h("button", { class: "btn danger", onclick: del }, icon("trash", 18), "حذف")), T.el)));
  await load();
}

/* ===================== كشف الحساب ===================== */
async function renderStatement(box) {
  const parties = await api("parties_list");
  const A = S.stmt || (S.stmt = { pid: null, from: monthStart(), to: S.boot.today });
  if (S.pendingStatement) { A.pid = S.pendingStatement; A.from = "2000-01-01"; A.to = S.boot.today; S.pendingStatement = null; }
  const from = dateIn(A.from, "من تاريخ"), to = dateIn(A.to, "إلى تاريخ");
  const party = combo({ id: "s-party", label: "الاسم", placeholder: "اكتب جزء من الاسم ...", items: () => parties, sub: (p) => p.kind, onPick: (p) => { A.pid = p ? p.id : null; if (p) load(); } });
  if (A.pid) party.set(parties.find((p) => p.id === A.pid) || null);
  const head = h("div", { class: "chips", style: { padding: "0 18px 14px" } });
  const T = selTable({ maxH: "calc(100vh - 380px)",
    cols: [{ h: "التاريخ", key: "date" }, { h: "الوقت", key: "time", cls: "hint" }, { h: "المرجع", key: "ref" }, { h: "البيان", fn: (r) => h("b", null, r.what) },
      { h: "مدين", num: true, fn: (r) => numOrEmpty(r.debit) }, { h: "دائن", num: true, fn: (r) => numOrEmpty(r.credit) }, { h: "الرصيد", num: true, fn: (r) => h("b", null, fmt(r.balance)) }],
    rowClass: (r) => (r.type === "open" ? "open-row" : ""),
    onOpen: async (r) => {
      if (r.type === 0) return showInvoice(r.rid);
      if (r.type === 1) { try { const p = await api("payment_detail", r.rid); if (p.invoice_id) return showInvoice(p.invoice_id);
        alertBox(`التاريخ: ${p.date} ${p.time}\nالنوع: ${p.kind}\nالمبلغ: ${fmt(p.amount)} ج.م` + (p.rep ? `\nالمندوب: ${p.rep}` : "") + `\nملاحظات: ${p.notes || "-"}`, `سند رقم ${p.id}`); } catch (e) { toast(e.message, "err"); } }
    },
    totals: (rs, isSel) => { const real = rs.filter((r) => r.type !== "open"); return [h("b", null, isSel ? "إجمالي المحدد" : "الإجمالي"), totItem("إجمالي المدين", fmt(real.reduce((a, r) => a + r.debit, 0))),
      totItem("إجمالي الدائن", fmt(real.reduce((a, r) => a + r.credit, 0))), totItem("الرصيد الختامي", fmt(T._closing || 0) + " ج.م", true)]; } });
  async function load() {
    A.from = from.value; A.to = to.value;
    if (!A.pid) return;
    let r; try { r = await api("statement", A.pid, A.from, A.to); } catch (e) { return toast(e.message, "err"); }
    T._closing = r.closing;
    head.replaceChildren(h("div", { class: "chip" }, "الحساب: ", h("b", null, r.party)), r.phone ? h("div", { class: "chip" }, "تليفون: ", h("b", null, r.phone)) : null,
      h("div", { class: "chip" }, "رصيد سابق: ", h("b", null, fmt(r.opening))), h("div", { class: "chip " + (r.closing > 0 ? "warn" : "info") }, "الرصيد الختامي: ", h("b", null, fmt(r.closing))),
      r.note ? h("div", { class: "chip info" }, r.note) : null);
    T.setRows([{ type: "open", date: "", time: "", ref: "", what: "رصيد سابق (مرحّل)", debit: 0, credit: 0, balance: r.opening }, ...r.rows]);
  }
  [from, to].forEach((x) => x.addEventListener("change", load));
  box.replaceChildren(h("div", { class: "page" },
    h("section", { class: "card anim-up d1" }, h("div", { class: "form" }, h("div", { class: "fld span2" }, h("label", { for: "s-party" }, "الاسم"), party.el),
      h("label", { class: "fld" }, "من تاريخ", from), h("label", { class: "fld" }, "إلى تاريخ", to),
      h("div", { class: "fld", style: { justifyContent: "flex-end", flexDirection: "row", gap: "8px", alignItems: "flex-end" } },
        h("button", { class: "btn primary", onclick: load }, "عرض"),
        h("button", { class: "btn gold", onclick: async () => { if (!A.pid) return toast("اختار الاسم الأول"); try { await api("print_statement", A.pid, from.value, to.value); toast("🖨 شاشة الطباعة هتفتح خلال ثواني ...", "ok"); } catch (e) { toast(e.message, "err"); } } }, icon("print", 18), "طباعة / PDF"))), head),
    h("section", { class: "card anim-up d2" }, h("div", { class: "card-h" }, h("h2", null, "الحركة"), h("span", { class: "hint" }, "ضغطتين على فاتورة أو سند = تفاصيله • موجب = على العميل ، سالب = للمورد"),
      h("button", { class: "btn", onclick: () => { if (!A.pid) return toast("اختار الاسم الأول"); S.pendingVoucherParty = A.pid; S.voucherEdit = null; go("vch:new", true); } }, icon("cash", 18), "سند للحساب ده")), T.el)));
  if (A.pid) await load(); else party.focus();
}

/* ===================== أرصدة الحسابات ===================== */
async function renderBalances(box) {
  const b = await api("balances");
  const q = h("input", { class: "in", placeholder: "الاسم أو النوع ...", "aria-label": "بحث سريع" });
  const c = b.cards;
  const card = (cls, ic, bg, fg, t, v, onclick, tip) => { const el = h("div", { class: "v" + (v < 0 ? " neg" : "") }, "0"); setTimeout(() => countUp(el, v), 100);
    return h("div", { class: "card kpi lift anim-up " + cls + (onclick ? " click" : ""), onclick, title: tip || "", role: onclick ? "button" : null, tabindex: onclick ? 0 : null,
      onkeydown: onclick ? (e) => { if (e.key === "Enter") onclick(); } : null }, h("div", { class: "h" }, h("span", { class: "ic", style: { background: bg, color: fg } }, icon(ic, 20)), t), el); };
  const T = selTable({
    cols: [{ h: "ID", key: "id", cls: "hint" }, { h: "الاسم", fn: (r) => h("b", null, r.name) }, { h: "النوع", key: "kind", cls: "hint" },
      { h: "مدين (عليه)", num: true, fn: (r) => (r.balance > 0.005 ? h("b", { style: { color: "var(--red)" } }, fmt(r.balance)) : "") },
      { h: "دائن (له)", num: true, fn: (r) => (r.balance < -0.005 ? h("b", { style: { color: "var(--green)" } }, fmt(-r.balance)) : "") },
      { h: "آخر تحصيل", key: "lc", cls: "hint" }, { h: "آخر دفع", key: "lp", cls: "hint" }, { h: "آخر فاتورة", key: "li", cls: "hint" }],
    onOpen: (r) => { S.pendingStatement = r.id; go("acc:statement", true); },
    onKey: (e) => { if (e.key === "Delete") del(); },
    menu: (r) => [{ label: "👁 عرض (كشف الحساب)", fn: () => { S.pendingStatement = r.id; go("acc:statement", true); } }, { label: "🗑 حذف", danger: true, fn: () => del() },
      can("par:list") ? { label: "✏️ تعديل", fn: async () => { if (await partyForm(r.id)) go("acc:balances", true); } } : null].filter(Boolean),
    totals: (rs, isSel) => { const r_ = rs.filter((x) => x.balance > 0).reduce((a, x) => a + x.balance, 0), p_ = -rs.filter((x) => x.balance < 0).reduce((a, x) => a + x.balance, 0);
      return [h("b", null, isSel ? "إجمالي المحدد" : "الإجمالي"), totItem("العدد", rs.length), totItem("إجمالي المدين", fmt(r_)), totItem("إجمالي الدائن", fmt(p_)), totItem("الصافي", fmt(r_ - p_), true)]; } });
  const all = [...b.rows].sort((x, y) => Math.abs(y.balance) - Math.abs(x.balance));
  const fill = () => { const n = norm(q.value); T.setRows(all.filter((r) => !n || (n === norm("أصول") ? r.kind === "أصول" : norm(r.name + " " + r.kind).includes(n)))); };
  async function del() {
    const sel = T.selected(); if (!sel.length) return toast("حدد حساب أو أكتر (Ctrl أو Shift + ضغطة)");
    const pw = await askDelPw(`تحذف ${sel.length} حساب؟\n${sel.slice(0, 8).map((r) => r.name).join("، ")}\n\n(الحسابات اللي ليها فواتير أو سندات مش هتتحذف)`); if (!pw) return;
    try { const r = await api("delete_parties", sel.map((x) => x.id), pw);
      if (r.kept.length) alertBox(`اتحذف ${r.deleted.length}.\nمتحذفوش علشان ليهم فواتير أو سندات: ${r.kept.slice(0, 8).join("، ")}`); else toast(`✔ اتحذف ${r.deleted.length} حساب`, "ok");
      go("acc:balances", true); } catch (e) { alertBox(e.message); }
  }
  q.addEventListener("input", fill);
  box.replaceChildren(h("div", { class: "page" },
    c.rep ? h("div", { class: "kpis" }, card("d1", "sale", "#e6f4ec", "#15803d", "على العملاء (لنا)", c.recv)) : h("div", { class: "kpis" }, card("d1", "sale", "#e6f4ec", "#15803d", "على العملاء (لنا)", c.recv), card("d2", "buy", "#fdecec", "#b91c1c", "علينا للموردين", c.pay),
      card("d3 dark", "cash", "rgba(200,162,74,.2)", "#e6c878", "الخزنة", c.cash, can("acc:cash") ? () => go("acc:cash") : null, "افتح الخزنة"),
      card("d4", "box", "#fbf3e0", "#8a6514", "المخزون (بسعر الشراء)", c.inv, can("itm:stock") ? () => go("itm:stock") : null, "افتح أرصدة الأصناف"),
      card("d5", "box", "#e6f6f4", "#0f766e", "المخزون (بسعر البيع)", c.sale, can("itm:stock") ? () => go("itm:stock") : null, "افتح أرصدة الأصناف"), card("d6", "chart", "#f2edff", "#6d28d9", "صافي الأملاك", c.net)),
    h("section", { class: "card anim-up d5" }, h("div", { class: "card-h" }, h("h2", null, "الحسابات"), h("div", { style: { flex: "1 1 260px" } }, q),
      h("button", { class: "btn", onclick: () => { const r = T.selected()[0]; if (!r) return toast("حدد حساب الأول"); S.pendingStatement = r.id; go("acc:statement", true); } }, icon("list", 18), "كشف الحساب"),
      h("button", { class: "btn gold", onclick: async () => { const sel = T.selected(); try { await api("print_balances", sel.length > 1 ? sel.map((x) => x.id) : null, sel.length > 1 ? "" : q.value.trim()); toast("🖨 شاشة الطباعة هتفتح (منها تقدر تحفظ PDF) ...", "ok"); } catch (e) { toast(e.message, "err"); } } }, icon("print", 18), "طباعة / PDF"),
      h("button", { class: "btn danger", onclick: del }, icon("trash", 18), "حذف")),
      h("div", { class: "hint", style: { padding: "8px 18px 0" } }, "ضغطتين على الاسم = كشف حسابه • موجب = على العميل ، سالب = للمورد"), T.el)));
  fill(); q.focus();
}

/* ===================== الخزنة ===================== */
async function renderCash(box) {
  const C = S.cashSt || (S.cashSt = { from: S.boot.today, to: S.boot.today });
  const from = dateIn(C.from, "من"), to = dateIn(C.to, "إلى");
  const cur = h("div", { class: "v" }, "0"), sub = h("div", { class: "s" }, "");
  const kind = h("div", { class: "seg" }, ["إيداع", "سحب"].map((k) => h("button", { "data-v": k, class: k === "إيداع" ? "on" : "", onclick: () => { kind.dataset.v = k; kind.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.v === k)); } }, k)));
  kind.dataset.v = "إيداع";
  const mDate = dateIn(S.boot.today, "التاريخ"), mAmt = h("input", { class: "in num", inputmode: "decimal", "aria-label": "المبلغ" }), mNotes = h("input", { class: "in", "aria-label": "ملاحظات" });
  const T = selTable({ maxH: "calc(100vh - 420px)",
    cols: [{ h: "التاريخ", key: "date" }, { h: "الوقت", key: "time", cls: "hint" }, { h: "البيان", fn: (r) => h("b", null, r.what) },
      { h: "وارد", num: true, fn: (r) => (r.in ? h("span", { style: { color: "var(--green)", fontWeight: 800 } }, fmt(r.in)) : "") },
      { h: "صادر", num: true, fn: (r) => (r.out ? h("span", { style: { color: "var(--red)", fontWeight: 800 } }, fmt(r.out)) : "") },
      { h: "الرصيد", num: true, fn: (r) => h("b", null, fmt(r.balance)) }],
    onKey: (e) => { if (e.key === "Delete") del(); },
    totals: (rs, isSel) => { const real = rs.filter((r) => r.key); return [h("b", null, isSel ? "إجمالي المحدد" : "الفترة"), totItem("وارد", fmt(real.reduce((a, r) => a + r.in, 0))),
      totItem("صادر", fmt(real.reduce((a, r) => a + r.out, 0))), isSel ? null : totItem("الرصيد في آخر الفترة", fmt(T._end || 0), true)]; } });
  async function load() {
    C.from = from.value; C.to = to.value || from.value;
    let r; try { r = await api("cash", C.from, C.to); } catch (e) { return toast(e.message, "err"); }
    countUp(cur, r.current); sub.textContent = `خلال الفترة: وارد ${fmt(r.in)} • صادر ${fmt(r.out)}`; T._end = r.end;
    T.setRows([{ key: null, date: "", time: "", what: "رصيد سابق (مرحّل)", in: 0, out: 0, balance: r.start }, ...r.rows]);
  }
  async function addMove() {
    try { await api("add_cash_move", kind.dataset.v, mDate.value, mAmt.value, mNotes.value); toast(`✔ اتسجل ${kind.dataset.v} ${fmt(num(mAmt.value))}`, "ok"); mAmt.value = ""; mNotes.value = ""; load(); }
    catch (e) { alertBox(e.message); }
  }
  async function del() {
    const r = T.selected()[0]; if (!r || !r.key) return toast("حدد سطر من الجدول");
    if (!r.key.startsWith("c-")) return alertBox("هنا بتحذف الإيداع والسحب اليدوي بس.\nالفواتير والسندات والمصروفات بتتحذف من شاشاتها.");
    if (!(await confirmBox(`تحذف «${r.what}» (${fmt(r.in || r.out)})؟`, "حذف", "احذف"))) return;
    try { await api("delete_cash_move", r.key); toast("✔ اتحذفت", "ok"); load(); } catch (e) { alertBox(e.message); }
  }
  async function count() { await cashCountModal(); load(); }
  [from, to].forEach((x) => x.addEventListener("change", load));
  enterChain([mAmt, mNotes], addMove);
  box.replaceChildren(h("div", { class: "page" },
    h("div", { class: "kpis" }, h("div", { class: "card kpi dark anim-up d1" }, h("div", { class: "h" }, h("span", { class: "ic", style: { background: "rgba(200,162,74,.2)", color: "#e6c878" } }, icon("cash", 20)), "رصيد الخزنة الحالي"), cur, sub),
      h("div", { class: "card anim-up d2", style: { padding: "14px 16px", display: "flex", flexDirection: "column", gap: "8px", justifyContent: "center" } },
        h("button", { class: "btn gold", style: { minHeight: "52px" }, onclick: count }, icon("check", 18), "جرد الخزنة"),
        h("span", { class: "hint" }, "رصيد أول المدة بيتغير من الإعدادات بكلمة سر المالك"))),
    h("section", { class: "card anim-up d3" }, h("div", { class: "card-h" }, h("h2", null, "إيداع / سحب يدوي")),
      h("div", { class: "form" }, h("div", { class: "fld" }, h("span", null, "النوع"), kind), h("label", { class: "fld" }, "التاريخ", mDate), h("label", { class: "fld" }, "المبلغ", mAmt),
        h("label", { class: "fld span2" }, "ملاحظات", mNotes), h("div", { class: "fld", style: { justifyContent: "flex-end" } }, h("button", { class: "btn primary", onclick: addMove }, icon("save", 18), "حفظ")))),
    h("section", { class: "card anim-up d4" }, h("div", { class: "card-h" }, h("h2", null, "حركة الخزنة"), h("label", { class: "fld", style: { flexDirection: "row", alignItems: "center" } }, "من", from),
      h("label", { class: "fld", style: { flexDirection: "row", alignItems: "center" } }, "إلى", to), h("button", { class: "btn danger", onclick: del }, icon("trash", 18), "حذف الإيداع/السحب")), T.el)));
  await load();
}

/* ===================== فورم في نافذة ===================== */
function formModal(title, fields, { saveLabel = "حفظ", onSave, onOpen }) {
  const ins = {};
  const body = h("div", { class: "form", style: { padding: 0 } }, fields.map((f) => {
    let el;
    if (f.options) { el = h("select", { class: "in", "aria-label": f.label }, f.options.map((o) => h("option", { value: o.value ?? o }, o.label ?? o))); el.value = String(f.value ?? ""); }
    else el = h("input", { class: "in" + (f.num ? " num" : ""), type: f.type || "text", value: f.value ?? "", inputmode: f.num ? "decimal" : null, "aria-label": f.label, placeholder: f.ph || "" });
    ins[f.key] = el;
    return h("label", { class: "fld" + (f.wide ? " span2" : "") }, f.label, el, f.hint ? h("small", { class: "hint", style: { fontWeight: 600 } }, f.hint) : null);
  }));
  const get = () => Object.fromEntries(Object.entries(ins).map(([k, el]) => [k, el.value]));
  if (onOpen) onOpen(body);
  return modal({ title, body, actions: [{ label: saveLabel, cls: "primary", icon: "save", value: async () => { try { const r = await onSave(get()); return r === false ? false : true; } catch (e) { alertBox(e.message); return false; } } },
    { label: "إلغاء", value: () => null }] });
}
async function ownerRetry(fn) {     // fn(pw) → {ok} أو {need, error}
  let pw = null;
  while (true) {
    const r = await fn(pw);
    if (r.ok !== false) return r;
    if (r.need) { pw = await askOwner(r.error); if (!pw) return null; continue; }
    if (r.error) { alertBox(r.error); return null; }
    return r;
  }
}

/* ===================== فواتير صنف ===================== */
async function showItemInvoices(id, from, to, kinds) {
  let d; try { d = await api("item_invoices", id, from || null, to || null, kinds || null); } catch (e) { return toast(e.message, "err"); }
  const sg = (r) => (r.kind.startsWith("مرتجع") ? -1 : 1);
  const head = from ? [h("div", { class: "chip" }, "الفترة: ", h("b", null, from === to ? from : `${from} ← ${to}`)), h("div", { class: "chip" }, "عدد الفواتير: ", h("b", null, new Set(d.rows.map((r) => r.id)).size)),
    h("div", { class: "chip" }, "الكمية: ", h("b", null, fq(d.rows.reduce((a, r) => a + sg(r) * r.qty, 0)))), h("div", { class: "chip" }, "القيمة: ", h("b", null, fmt(d.rows.reduce((a, r) => a + sg(r) * r.amount, 0)))),
    h("div", { class: "chip info" }, "الرصيد الحالي: ", h("b", null, `${fq(d.stock)} ${d.unit}`))]
    : (() => { const k = (n) => d.rows.filter((r) => r.kind === n).reduce((a, r) => a + r.qty, 0);
      return [h("div", { class: "chip" }, "أول المدة: ", h("b", null, fq(d.opening))), h("div", { class: "chip" }, "مشتريات: ", h("b", null, fq(k("مشتريات")))), h("div", { class: "chip" }, "مبيعات: ", h("b", null, fq(k("مبيعات")))),
        h("div", { class: "chip" }, "مرتجع مبيعات: ", h("b", null, fq(k("مرتجع مبيعات")))), h("div", { class: "chip" }, "مرتجع مشتريات: ", h("b", null, fq(k("مرتجع مشتريات")))), h("div", { class: "chip info" }, "الرصيد الحالي: ", h("b", null, `${fq(d.stock)} ${d.unit}`))]; })();
  const T = selTable({ maxH: "55vh", cols: [{ h: "التاريخ", key: "date" }, { h: "الوقت", key: "time", cls: "hint" }, { h: "رقم", fn: (r) => h("b", null, r.number) }, { h: "النوع", fn: (r) => h("span", { class: "pill " + kindClass(r.kind) }, r.kind) },
    { h: "العميل / المورد", key: "party" }, { h: "الكمية", num: true, fn: (r) => fq(r.qty) }, { h: "السعر", num: true, fn: (r) => fmt(r.price) }, { h: "الإجمالي", num: true, fn: (r) => h("b", null, fmt(r.amount)) }],
    onOpen: (r) => showInvoice(r.id) });
  T.setRows(d.rows);
  modal({ title: `فواتير الصنف: ${d.name}`, wide: true, enter: false, body: [h("div", { class: "chips", style: { padding: 0 } }, head), h("div", { class: "card" }, T.el), h("div", { class: "hint" }, "ضغطتين على فاتورة = تفتحها")], actions: [{ label: "قفل", ret: true }] });
}

/* ===================== العملاء والموردون ===================== */
async function partyForm(id) {
  let p = { id: null, name: "", kind: "عميل", phone: "", address: "", opening: 0, rep_id: null, limit: 0 }, reps;
  try { if (id) { p = await api("party_get", id); reps = p.reps; } else reps = await api("party_reps"); } catch (e) { return alertBox(e.message); }
  let saved = false;
  await formModal(id ? `تعديل «${p.name}»` : "إضافة عميل / مورد", [
    { key: "name", label: "الاسم", value: p.name, wide: true }, { key: "kind", label: "النوع", value: p.kind, options: ["عميل", "مورد", "عميل/مورد"].concat(S.me.owner ? ["أصول"] : []) },
    { key: "phone", label: "الهاتف", value: p.phone }, { key: "address", label: "العنوان", value: p.address, wide: true },
    { key: "rep_id", label: "المندوب (للعملاء)", value: p.rep_id ?? "", options: reps.map((r) => ({ value: r.id ?? "", label: r.label })) },
    { key: "opening", label: "الرصيد الافتتاحي", value: p.opening, num: true, hint: "موجب = على العميل ، سالب = للمورد" },
    { key: "limit", label: "الحد الائتماني 🔒 (0 = بدون)", value: p.limit, num: true, hint: "بيتغيّر بكلمة سر المالك" }],
    { onSave: async (v) => { const r = await ownerRetry((pw) => api("save_party", { ...v, id: p.id, rep_id: v.rep_id ? +v.rep_id : null }, pw)); if (!r) return false; saved = true; toast(`✔ اتحفظ «${v.name}»`, "ok"); } });
  return saved;
}
async function renderParties(box) {
  const P = S.parSt || (S.parSt = { kf: "الكل", q: "" });
  const kf = h("div", { class: "seg wrap" }, ["الكل", "عملاء", "موردين"].concat(S.me.owner ? ["أصول"] : [], ["عليهم فلوس", "ليهم فلوس", "عدّوا الحد الائتماني"]).map((k) => h("button", { "data-v": k, class: P.kf === k ? "on" : "",
    onclick: () => { P.kf = k; kf.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.v === k)); load(); } }, k)));
  const q = h("input", { class: "in", placeholder: "الاسم أو التليفون أو المندوب أو العنوان ...", value: P.q, "aria-label": "بحث" });
  const T = selTable({
    cols: [{ h: "ID", key: "id", cls: "hint" }, { h: "الاسم", fn: (r) => h("b", null, r.name) }, { h: "النوع", key: "kind", cls: "hint" }, { h: "المندوب", key: "rep", cls: "hint" },
      { h: "الهاتف", key: "phone" }, { h: "العنوان", key: "address", cls: "hint" }, { h: "الرصيد", num: true, fn: (r) => h("b", { style: { color: r.balance > 0.005 ? "var(--red)" : r.balance < -0.005 ? "var(--green)" : "" } }, fmt(r.balance)) },
      { h: "الحد الائتماني", num: true, fn: (r) => (r.limit ? h("span", { class: r.over ? "pill k-مرتجع" : "" }, fmt(r.limit)) : "—") }, { h: "آخر تحصيل", key: "lc", cls: "hint" }, { h: "آخر دفع", key: "lp", cls: "hint" }],
    onOpen: async (r) => { if (await partyForm(r.id)) load(); },
    onKey: (e) => { if (e.key === "Delete") del(); },
    menu: (r) => [{ label: "👁 عرض (كشف الحساب)", fn: () => { S.pendingStatement = r.id; go("acc:statement", true); } }, { label: "🗑 حذف", danger: true, fn: () => del() },
      { label: "✏️ تعديل", fn: async () => { if (await partyForm(r.id)) load(); } }, { label: "💵 سند", fn: () => { S.pendingVoucherParty = r.id; S.voucherEdit = null; go("vch:new", true); } },
      r.kind !== "مورد" && r.kind !== "أصول" ? { label: "🧾 فاتورة مبيعات", fn: () => newInvoiceFor(r.id) } : null].filter(Boolean),
    totals: (rs, isSel) => { const recv = rs.filter((x) => x.balance > 0).reduce((a, x) => a + x.balance, 0), pay = -rs.filter((x) => x.balance < 0).reduce((a, x) => a + x.balance, 0);
      return [h("b", null, isSel ? "إجمالي المحدد" : "الإجمالي"), totItem("العدد", rs.length), totItem("لينا عندهم", fmt(recv)), totItem("علينا لهم", fmt(pay))]; } });
  async function load() { P.q = q.value; try { T.setRows(await api("parties_full", P.kf, P.q)); } catch (e) { toast(e.message, "err"); } }
  async function del() {
    const sel = T.selected(); if (!sel.length) return toast("حدد حساب الأول");
    const pw = await askDelPw(`تحذف ${sel.length === 1 ? "«" + sel[0].name + "»" : sel.length + " حساب"}؟\n(اللي ليهم فواتير أو سندات مش هيتحذفوا)`); if (!pw) return;
    try { const r = await api("delete_parties", sel.map((x) => x.id), pw); if (r.kept.length) alertBox(`متحذفوش علشان ليهم فواتير أو سندات: ${r.kept.slice(0, 8).join("، ")}`); else toast("✔ اتحذف", "ok"); load(); } catch (e) { alertBox(e.message); }
  }
  const one = (fn) => () => { const r = T.selected()[0]; if (!r) return toast("حدد حساب الأول"); fn(r); };
  let t = null; q.addEventListener("input", () => { clearTimeout(t); t = setTimeout(load, 250); });
  box.replaceChildren(h("div", { class: "page" },
    h("section", { class: "card anim-up d1", style: { padding: "14px 18px", display: "flex", flexDirection: "column", gap: "10px" } }, kf, q),
    h("section", { class: "card anim-up d2" }, h("div", { class: "card-h" }, h("h2", null, "الحسابات"),
      h("button", { class: "btn primary", onclick: async () => { if (await partyForm(null)) load(); } }, icon("plus", 18), "إضافة"),
      h("button", { class: "btn", onclick: one(async (r) => { if (await partyForm(r.id)) load(); }) }, icon("edit", 18), "تعديل"),
      h("button", { class: "btn", onclick: one((r) => { S.pendingStatement = r.id; go("acc:statement", true); }) }, icon("list", 18), "كشف الحساب"),
      h("button", { class: "btn", onclick: one((r) => { S.pendingVoucherParty = r.id; S.voucherEdit = null; go("vch:new", true); }) }, icon("cash", 18), "سند"),
      h("button", { class: "btn", onclick: one((r) => newInvoiceFor(r.id)) }, icon("sale", 18), "فاتورة مبيعات"),
      S.me.owner ? h("button", { class: "btn", onclick: () => importExcel("parties") }, "استيراد من Excel") : null,
      h("button", { class: "btn danger", onclick: del }, icon("trash", 18), "حذف")), T.el)));
  await load(); q.focus();
}

/* ===================== الأصول وأرباح الملاك (للملاك بس) ===================== */
async function renderAssets(box) {
  const A = S.astSt || (S.astSt = { from: monthStart(), to: S.boot.today, tab: "مالك" });
  const fromIn = dateIn(A.from, "من تاريخ"), toIn = dateIn(A.to, "إلى تاريخ");
  fromIn.onchange = () => { A.from = fromIn.value; load(); }; toIn.onchange = () => { A.to = toIn.value; load(); };
  const cardsEl = h("div", { class: "kpis" }), sugEl = h("div"), head = h("div", { class: "card-h" }), hint = h("div", { class: "hint", style: { padding: "8px 18px 0" } });
  let ALL = [], T = null; const wrap = h("div");
  const statement = (r) => { S.pendingStatement = r.id; go("acc:statement", true); };
  const one = (fn) => () => { const r = T && T.selected()[0]; if (!r) return toast(A.tab === "مالك" ? "حدد مالك الأول" : "حدد أصل الأول"); fn(r); };
  const tabs = h("div", { class: "seg" }, [["مالك", "💰 أرباح الملاك"], ["أصل", "🛺 الأصول"]].map(([k, l]) => h("button", { "data-v": k, class: A.tab === k ? "on" : "",
    onclick: () => { A.tab = k; tabs.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.v === k)); build(); } }, l)));
  function build() {
    const own = A.tab === "مالك";
    T = selTable({ maxH: "calc(100vh - 400px)",
      cols: own ? [{ h: "المالك", fn: (r) => h("b", null, r.name) }, { h: "رصيد افتتاحي", num: true, fn: (r) => fmt(r.opening) },
          { h: "اتصرف في الفترة", num: true, fn: (r) => h("b", { style: { color: r.p_took ? "var(--red)" : "" } }, fmt(r.p_took)) },
          { h: "إجمالي اللي اتصرف", num: true, fn: (r) => h("b", null, fmt(r.balance)) }, { h: "عدد المرات", num: true, key: "times" },
          { h: "آخر صرف", key: "last_date", sort: (r) => r.last_date || "" }, { h: "مبلغ آخر صرف", num: true, fn: (r) => (r.last_amount ? fmt(r.last_amount) : "") }]
        : [{ h: "الأصل", fn: (r) => h("b", null, r.name) }, { h: "اتشترى بـ", num: true, fn: (r) => h("b", null, fmt(r.balance)) }, { h: "تاريخ الشرا", key: "first_date", sort: (r) => r.first_date || "" }],
      onOpen: (r) => statement(r), onKey: (e) => { if (e.key === "Delete") del(); },
      menu: (r) => (own ? [{ label: "💸 صرف أرباح", fn: () => pay(r, "دفع") }, { label: "↩ رجّع فلوس للخزنة", fn: () => pay(r, "تحصيل") }] : [])
        .concat([{ label: "👁 عرض (كشف الحساب)", fn: () => statement(r) }, { label: "✏️ تعديل", fn: () => form(r) }, { label: "🗑 حذف", danger: true, fn: () => del() }]),
      totals: (rs, isSel) => own ? [h("b", null, isSel ? "إجمالي المحدد" : "الإجمالي"), totItem("الملاك", rs.length), totItem("اتصرف في الفترة", fmt(rs.reduce((a, r) => a + r.p_took, 0))), totItem("إجمالي اللي اتصرف", fmt(rs.reduce((a, r) => a + r.balance, 0)))]
        : [h("b", null, isSel ? "إجمالي المحدد" : "الإجمالي"), totItem("الأصول", rs.length), totItem("اتشترت بـ", fmt(rs.reduce((a, r) => a + r.balance, 0)))] });
    head.replaceChildren(h("h2", null, own ? "أرباح الملاك" : "الأصول"),
      own ? h("label", { class: "fld", style: { flexDirection: "row", alignItems: "center" } }, "من", fromIn) : null, own ? h("label", { class: "fld", style: { flexDirection: "row", alignItems: "center" } }, "إلى", toIn) : null,
      own ? h("button", { class: "btn gold", onclick: one((r) => pay(r, "دفع")) }, "💸 صرف أرباح") : h("button", { class: "btn primary", onclick: () => newAsset() }, icon("plus", 18), "أصل جديد"),
      own ? h("button", { class: "btn primary", onclick: () => form(null) }, icon("plus", 18), "مالك جديد") : null,
      h("button", { class: "btn", onclick: one(form) }, icon("edit", 18), "تعديل"), h("button", { class: "btn", onclick: one(statement) }, icon("list", 18), "كشف الحساب"),
      h("button", { class: "btn danger", onclick: del }, icon("trash", 18), "حذف"));
    hint.textContent = own ? "«صرف أرباح» = الفلوس بتطلع من الخزنة وتتسجل على المالك • ضغطتين = كشف حسابه • الشاشة دي للملاك بس" : "«أصل جديد» = اللي اشتريناه للشركة (تريسكل، كمبيوتر ...) — لو اتدفع من الخزنة بيطلع منها • ضغطتين = كشف الحساب";
    wrap.replaceChildren(T.el); fill();
  }
  const fill = () => T && T.setRows(ALL.filter((r) => r.atype === A.tab));
  async function load() {
    let d; try { d = await api("assets_report", A.from, A.to); } catch (e) { return toast(e.message, "err"); }
    const k = (t, v, ic) => h("div", { class: "card kpi dark" }, h("div", { class: "h" }, h("span", { class: "ic" }, icon(ic, 20)), t), h("div", { class: "v" }, fmt(v)));
    cardsEl.replaceChildren(k("أرباح الملاك (إجمالي اللي اتصرف)", d.cards.owners, "cash"), k("أرباح اتصرفت في الفترة", d.cards.p_took, "cash"), k("الأصول (اتشترت بـ)", d.cards.assets, "box"));
    sugEl.replaceChildren(d.suggest.length ? h("div", { class: "card", style: { padding: "12px 18px", display: "flex", flexWrap: "wrap", gap: "10px", alignItems: "center", background: "#fffbea" } },
      h("b", null, "لقيت حسابات أرباح متسجلة عملاء:"), h("span", null, d.suggest.map((x) => x.name).join("، ")),
      h("button", { class: "btn gold", onclick: async () => { if (!(await confirmBox(`تنقل ${d.suggest.length} حساب لأرباح الملاك؟ (هيطلعوا من العملاء)`))) return; await api("assets_adopt", d.suggest.map((x) => x.id)); toast("✔ اتنقلوا", "ok"); load(); } }, "انقلهم لأرباح الملاك")) : "");
    ALL = d.rows; fill();
  }
  async function form(r) {
    const own = r ? r.atype === "مالك" : A.tab === "مالك";
    r = r || { id: null, name: "", opening: 0 };
    let ok = false;
    await formModal(r.id ? `تعديل «${r.name}»` : own ? "مالك جديد" : "أصل جديد", [{ key: "name", label: own ? "اسم المالك" : "اسم الأصل", value: r.name, wide: true },
      { key: "opening", label: own ? "رصيد افتتاحي (اللي خده قبل البرنامج)" : "اتشترى بكام (قبل البرنامج)", value: r.opening, num: true }],
      { onSave: async (v) => { await api("save_asset", { ...v, id: r.id, atype: own ? "مسحوبات مالك" : "أصل" }); ok = true; } });
    if (ok) { toast("✔ اتحفظ", "ok"); load(); }
  }
  async function newAsset() {
    const st = await api("voucher_setup").catch(() => ({ methods: ["كاش"] }));
    let ok = false;
    await formModal("🛺 أصل جديد", [{ key: "name", label: "اسم الأصل", value: "", ph: "تريسكل / كمبيوتر المخزن / تلاجة ...", wide: true },
      { key: "price", label: "اتشترى بكام", value: "", num: true }, { key: "date", label: "تاريخ الشرا", value: S.boot.today, type: "date" },
      { key: "src", label: "الفلوس", value: "خزنة", options: [{ value: "خزنة", label: "اتدفعت من الخزنة دلوقتي" }, { value: "قديم", label: "اتشترى قبل البرنامج (مش من الخزنة)" }] },
      { key: "method", label: "اتدفع إزاي", value: "كاش", options: st.methods || ["كاش"] }],
      { onSave: async (v) => {
          if (!(num(v.price) > 0)) throw new Error("اكتب السعر");
          const pid = await api("save_asset", { name: v.name, opening: v.src === "قديم" ? v.price : 0, atype: "أصل" });
          if (v.src === "خزنة") await api("save_voucher", { kind: "دفع", party_id: pid, amount: v.price, date: v.date, method: v.method, holder: "", notes: "شرا أصل: " + v.name, rep_id: null }, false);
          ok = true; } });
    if (ok) { toast("✔ اتسجل الأصل", "ok"); load(); }
  }
  async function pay(r, kind) {
    const st = await api("voucher_setup").catch(() => ({ methods: ["كاش"] }));
    let ok = false;
    await formModal(kind === "دفع" ? `💸 صرف أرباح — ${r.name}` : `↩ رجوع فلوس للخزنة — ${r.name}`, [
      { key: "amount", label: "المبلغ", value: "", num: true }, { key: "date", label: "التاريخ", value: S.boot.today, type: "date" },
      { key: "method", label: kind === "دفع" ? "اتصرفت إزاي" : "رجعت إزاي", value: "كاش", options: st.methods || ["كاش"] }, { key: "notes", label: "ملاحظات", value: "", wide: true }],
      { onSave: async (v) => { await api("save_voucher", { kind, party_id: r.id, amount: v.amount, date: v.date, method: v.method, holder: "", notes: v.notes || (kind === "دفع" ? "صرف أرباح" : ""), rep_id: null }, false); ok = true; } });
    if (ok) { toast(kind === "دفع" ? "✔ اتصرفت (طلعت من الخزنة)" : "✔ رجعت الخزنة", "ok"); load(); }
  }
  async function del() {
    const sel = T.selected(); if (!sel.length) return toast("حدد الأول");
    const pw = await askDelPw(`تحذف «${sel[0].name}»؟ (لو ليه سندات مش هيتحذف)`); if (!pw) return;
    try { const r = await api("delete_parties", sel.map((x) => x.id), pw); if (r.kept.length) alertBox("متحذفش علشان ليه سندات — امسح سنداته الأول من سجل السندات"); else toast("✔ اتحذف", "ok"); load(); } catch (e) { alertBox(e.message); }
  }
  box.replaceChildren(h("div", { class: "page" }, cardsEl, sugEl,
    h("section", { class: "card anim-up d1" }, h("div", { style: { padding: "14px 18px 0" } }, tabs), head, hint, wrap)));
  build(); await load();
}

/* ===================== الأصناف ===================== */
async function itemForm(it) {
  it = it || { id: null, code: "", name: "", unit: "قطعة", buy: 0, sell: 0, min: 0, opening: 0 };
  let saved = false;
  await formModal(it.id ? `تعديل «${it.name}»` : "صنف جديد", [
    { key: "name", label: "اسم الصنف", value: it.name, wide: true }, { key: "code", label: "الكود", value: it.code }, { key: "unit", label: "الوحدة", value: it.unit, ph: "شيكارة / طن / قطعة" },
    { key: "buy", label: "سعر الشراء", value: it.buy, num: true }, { key: "sell", label: "سعر البيع", value: it.sell, num: true },
    { key: "min", label: "حد أدنى للتنبيه", value: it.min, num: true }, { key: "opening", label: "رصيد أول المدة", value: it.opening, num: true, hint: "الكمية اللي كانت موجودة قبل البرنامج" }],
    { onSave: async (v) => { const r = await ownerRetry((pw) => api("save_item", { ...v, id: it.id }, pw)); if (!r) return false; saved = true; toast(`✔ اتحفظ «${v.name}»`, "ok"); } });
  return saved;
}
async function renderItems(box) {
  const q = h("input", { class: "in", placeholder: "الكود أو الاسم ...", "aria-label": "بحث" });
  const T = selTable({
    cols: [{ h: "ID", key: "id", cls: "hint" }, { h: "الكود", key: "code" }, { h: "اسم الصنف", fn: (r) => h("b", null, r.name) }, { h: "الوحدة", key: "unit", cls: "hint" },
      { h: "سعر الشراء", num: true, fn: (r) => fmt(r.buy) }, { h: "سعر البيع", num: true, fn: (r) => fmt(r.sell) }, { h: "حد أدنى", num: true, fn: (r) => fq(r.min) },
      { h: "أول المدة", num: true, fn: (r) => fq(r.opening) }, { h: "الرصيد", num: true, fn: (r) => h("b", { style: { color: r.low ? "var(--red)" : "" } }, fq(r.stock)) }],
    onOpen: (r) => showItemInvoices(r.id), onKey: (e) => { if (e.key === "Delete") del(); },
    menu: (r) => [{ label: "👁 عرض (فواتير الصنف)", fn: () => showItemInvoices(r.id) }, { label: "🗑 حذف", danger: true, fn: () => del() }, { label: "✏️ تعديل", fn: async () => { if (await itemForm(r)) load(); } }],
    totals: (rs, isSel) => [h("b", null, isSel ? "المحدد" : "الإجمالي"), totItem("عدد الأصناف", rs.length), totItem("وصلوا للحد الأدنى", rs.filter((r) => r.low).length)] });
  let all = [];
  async function load() { try { all = await api("items_full", ""); fill(); } catch (e) { toast(e.message, "err"); } }
  const fill = () => { const n = norm(q.value); T.setRows(all.filter((r) => !n || norm(r.name + " " + r.code).includes(n))); };
  async function del() {
    const r = T.selected()[0]; if (!r) return toast("حدد صنف الأول");
    const pw = await askDelPw(`تحذف الصنف «${r.name}»؟`); if (!pw) return;
    try { await api("delete_item", r.id, pw); toast("✔ اتحذف", "ok"); load(); } catch (e) { alertBox(e.message); }
  }
  const one = (fn) => () => { const r = T.selected()[0]; if (!r) return toast("حدد صنف الأول"); fn(r); };
  q.addEventListener("input", fill);
  box.replaceChildren(h("div", { class: "page" },
    h("section", { class: "card anim-up d1" }, h("div", { class: "card-h" }, h("h2", null, "الأصناف"), h("div", { style: { flex: "1 1 260px" } }, q),
      h("button", { class: "btn primary", onclick: async () => { if (await itemForm(null)) load(); } }, icon("plus", 18), "صنف جديد"),
      h("button", { class: "btn", onclick: one(async (r) => { if (await itemForm(r)) load(); }) }, icon("edit", 18), "تعديل"),
      h("button", { class: "btn", onclick: one((r) => showItemInvoices(r.id)) }, icon("list", 18), "فواتير الصنف"),
      S.me.owner ? h("button", { class: "btn", onclick: () => importExcel("items") }, "استيراد من Excel") : null,
      h("button", { class: "btn danger", onclick: del }, icon("trash", 18), "حذف")),
      h("div", { class: "hint", style: { padding: "8px 18px 0" } }, "ضغطتين على صنف = فواتيره • الأحمر = وصل للحد الأدنى"), T.el)));
  await load(); q.focus();
}

/* ===================== أرصدة الأصناف ===================== */
async function renderStock(box) {
  const q = h("input", { class: "in", placeholder: "الكود أو الاسم ...", "aria-label": "بحث" });
  const pName = h("b", { style: { color: "var(--navy)", fontSize: "16px", minWidth: "220px" } }, "اختار صنف من الجدول");
  const pBuy = h("input", { class: "in num", "aria-label": "سعر الشراء", style: { maxWidth: "150px" } }), pSell = h("input", { class: "in num", "aria-label": "سعر البيع", style: { maxWidth: "150px" } });
  let cur = null;
  const T = selTable({ maxH: "calc(100vh - 360px)",
    cols: [{ h: "الكود", key: "code", cls: "hint" }, { h: "اسم الصنف", fn: (r) => h("b", null, r.name) }, { h: "الوحدة", key: "unit", cls: "hint" },
      { h: "شراء", num: true, fn: (r) => h("span", { class: "c-buy" }, fmt(r.buy)) }, { h: "بيع", num: true, fn: (r) => h("span", { class: "c-sell" }, fmt(r.sell)) },
      { h: "أول المدة", num: true, fn: (r) => fq(r.opening) }, { h: "الوارد", num: true, fn: (r) => fq(r.in) }, { h: "الصادر", num: true, fn: (r) => fq(r.out) }, { h: "هالك", num: true, fn: (r) => (r.dmg ? fq(r.dmg) : "") },
      { h: "الرصيد الحالي", num: true, fn: (r) => h("b", { style: { color: r.low ? "var(--red)" : "" } }, fq(r.stock)) },
      { h: "محجوز لفواتير قادمة", num: true, fn: (r) => (r.reserved ? fq(r.reserved) : "") }, { h: "بعد الفواتير القادمة", num: true, fn: (r) => (r.reserved ? fq(r.after) : "") }],
    onOpen: (r) => showItemInvoices(r.id),
    menu: (r) => [{ label: "👁 عرض (فواتير الصنف)", fn: () => showItemInvoices(r.id) }, can("itm:list") ? { label: "✏️ تعديل", fn: async () => { if (await itemForm({ id: r.id, code: r.code, name: r.name, unit: r.unit, buy: r.buy, sell: r.sell, min: r.min || 0, opening: r.opening })) go("itm:stock", true); } } : null].filter(Boolean),
    totals: (rs) => { pick(T.selected()[0]); return [totItem("عدد الأصناف", rs.length), totItem("وصلوا للحد الأدنى", rs.filter((r) => r.low).length)]; } });
  function pick(r) { if (!r || r === cur) return; cur = r; pName.textContent = r.name; pBuy.value = r.buy; pSell.value = r.sell; }
  let all = [];
  async function load() { try { all = await api("stock"); fill(); } catch (e) { toast(e.message, "err"); } }
  const fill = () => { const n = norm(q.value); T.setRows(all.filter((r) => !n || norm(r.name + " " + r.code).includes(n))); cur = null; };
  async function savePrice(nextFocus) {
    if (!cur) return toast("اختار صنف من الجدول الأول");
    try {
      const r = await api("save_price", cur.id, pBuy.value, pSell.value);
      cur.buy = num(pBuy.value); cur.sell = num(pSell.value);
      const rows = T.rows(), i = rows.indexOf(cur), tr = T.el.querySelectorAll("tbody tr")[i];
      if (tr) { tr.querySelector(".c-buy").textContent = fmt(cur.buy); tr.querySelector(".c-sell").textContent = fmt(cur.sell); tr.classList.add("new"); }
      toast(r.warn ? `⚠ «${cur.name}»: سعر البيع أقل من سعر الشراء` : r.changed ? `✔ اتحفظ سعر «${cur.name}»` : "مفيش تغيير في السعر", r.warn ? "err" : "ok", 2200);
      const nx = rows[i + 1]; if (nx && T.el.querySelectorAll("tbody tr")[i + 1]) { T.el.querySelectorAll("tbody tr")[i + 1].dispatchEvent(new MouseEvent("mousedown", { bubbles: true })); document.dispatchEvent(new MouseEvent("mouseup")); pick(nx); }
      if (nextFocus) { nextFocus.focus(); nextFocus.select(); }
    } catch (e) { alertBox(e.message); }
  }
  pBuy.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); pSell.focus(); pSell.select(); } });
  pSell.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); savePrice(pBuy); } });
  q.addEventListener("input", fill);
  box.replaceChildren(h("div", { class: "page" },
    h("section", { class: "card anim-up d1", style: { padding: "12px 18px", display: "flex", flexWrap: "wrap", gap: "10px", alignItems: "center" } },
      h("span", { class: "hint" }, "تعديل سعر الصنف المحدد:"), pName, h("label", { class: "fld", style: { flexDirection: "row", alignItems: "center" } }, "شراء", pBuy),
      h("label", { class: "fld", style: { flexDirection: "row", alignItems: "center" } }, "بيع", pSell), h("button", { class: "btn primary", onclick: () => savePrice() }, icon("save", 18), "حفظ السعر"),
      h("span", { class: "hint" }, "Enter بيحفظ وينزل على اللي بعده")),
    h("section", { class: "card anim-up d2" }, h("div", { class: "card-h" }, h("h2", null, "الأرصدة لحد النهارده"), h("div", { style: { flex: "1 1 260px" } }, q),
      h("button", { class: "btn gold", onclick: async () => { try { await api("print_stock_count"); toast("🖨 شاشة الطباعة هتفتح خلال ثواني ...", "ok"); } catch (e) { toast(e.message, "err"); } } }, icon("print", 18), "طباعة للجرد")),
      h("div", { class: "hint", style: { padding: "8px 18px 0" } }, "ضغطتين على صنف = فواتيره • الأحمر = وصل للحد الأدنى • «محجوز» = كميات في فواتير تاريخ استحقاقها لسه ماجاش"), T.el)));
  await load(); q.focus();
}

/* ===================== المبيعات / المشتريات لكل صنف ===================== */
async function renderFlow(box, kind) {
  const F = S["flow" + kind] || (S["flow" + kind] = { from: S.boot.today, to: S.boot.today });
  const from = dateIn(F.from, "من"), to = dateIn(F.to, "إلى"), q = h("input", { class: "in", placeholder: "الصنف ...", "aria-label": "بحث" });
  let data = { rows: [], kinds: [] };
  const T = selTable({
    cols: [{ h: "الكود", key: "code", cls: "hint" }, { h: "اسم الصنف", fn: (r) => h("b", null, r.name) }, { h: "الوحدة", key: "unit", cls: "hint" },
      { h: "الكمية", num: true, fn: (r) => fq(r.qty) }, { h: "القيمة", num: true, fn: (r) => h("b", null, fmt(r.amount)) }],
    onOpen: (r) => showItemInvoices(r.id, F.from, F.to, data.kinds),
    totals: (rs, isSel) => [h("b", null, isSel ? "إجمالي المحدد" : "الإجمالي"), totItem("عدد الأصناف", rs.length), totItem("الكمية", qtyText(rs)), totItem("إجمالي القيمة", fmt(rs.reduce((a, r) => a + r.amount, 0)), true)] });
  const fill = () => { const n = norm(q.value); T.setRows(data.rows.filter((r) => !n || norm(r.name + " " + r.code).includes(n))); };
  async function load() { F.from = from.value; F.to = to.value || from.value; try { data = await api("items_flow", kind, F.from, F.to); fill(); } catch (e) { toast(e.message, "err"); } }
  [from, to].forEach((x) => x.addEventListener("change", load)); q.addEventListener("input", fill);
  box.replaceChildren(h("div", { class: "page" },
    h("section", { class: "card anim-up d1" }, h("div", { class: "form" }, h("label", { class: "fld" }, "من تاريخ", from), h("label", { class: "fld" }, "إلى تاريخ", to), h("label", { class: "fld span2" }, "بحث سريع", q))),
    h("section", { class: "card anim-up d2" }, h("div", { class: "card-h" }, h("h2", null, kind === "مبيعات" ? "الأصناف اللي اتباعت" : "الأصناف اللي اتشرت"),
      h("span", { class: "hint" }, `الكمية والقيمة بعد خصم مرتجع ${kind} • ضغطتين على صنف = فواتيره في الفترة دي`)), T.el)));
  await load();
}

/* ===================== الهالك ===================== */
async function renderDamaged(box) {
  const items = await api("items_full", "");
  const Dm = S.dmgSt || (S.dmgSt = { from: monthStart(), to: S.boot.today, src: "الكل", q: "" });
  const dDate = dateIn(S.boot.today, "التاريخ"), qty = h("input", { class: "in num", value: "1", "aria-label": "الكمية" }), notes = h("input", { class: "in", "aria-label": "السبب / ملاحظات" });
  const item = combo({ id: "d-item", label: "الصنف", placeholder: "اكتب اسم الصنف ...", items: () => items.map((i) => ({ ...i, label: `${i.id} - ${i.name}${i.code ? " [" + i.code + "]" : ""}` })), sub: (i) => `${fq(i.stock)} ${i.unit}`,
    onPick: (it, adv) => { if (adv) { qty.focus(); qty.select(); } } });
  const from = dateIn(Dm.from, "من"), to = dateIn(Dm.to, "إلى");
  const src = h("select", { class: "in", "aria-label": "المصدر" }, ["الكل", "مرتجع هالك", "هالك من المخزن"].map((x) => h("option", { value: x }, x))); src.value = Dm.src;
  const q = h("input", { class: "in", value: Dm.q, placeholder: "الصنف أو الاسم أو الملاحظات ...", "aria-label": "بحث" });
  const T = selTable({
    cols: [{ h: "التاريخ", key: "date" }, { h: "الوقت", key: "time", cls: "hint" }, { h: "الصنف", fn: (r) => h("b", null, r.item) }, { h: "الكمية", num: true, fn: (r) => fq(r.qty) },
      { h: "التكلفة للوحدة", num: true, fn: (r) => fmt(r.cost) }, { h: "القيمة", num: true, fn: (r) => h("b", null, fmt(r.value)) }, { h: "المصدر", key: "src", cls: "hint" }, { h: "ملاحظات", key: "notes", cls: "hint" }],
    onOpen: (r) => r.invoice_id && showInvoice(r.invoice_id), onKey: (e) => { if (e.key === "Delete") del(); },
    totals: (rs, isSel) => [h("b", null, isSel ? "إجمالي المحدد" : "الإجمالي"), totItem("عدد الحركات", rs.length), totItem("الكمية", fq(rs.reduce((a, r) => a + r.qty, 0))), totItem("القيمة (بالتكلفة)", fmt(rs.reduce((a, r) => a + r.value, 0)), true)] });
  async function load() { Dm.from = from.value; Dm.to = to.value || from.value; Dm.src = src.value; Dm.q = q.value; try { T.setRows(await api("damaged", Dm.from, Dm.to, Dm.src, Dm.q)); } catch (e) { toast(e.message, "err"); } }
  async function save() {
    const it = item.get(); if (!it) { item.focus(); return toast("اختار الصنف", "err"); }
    const r = await ownerRetry((pw) => api("save_damaged", it.id, dDate.value, qty.value, notes.value, pw)); if (!r) return;
    toast(`✔ اتسجل هالك «${it.name}»`, "ok"); item.set(null); qty.value = "1"; notes.value = ""; item.focus(); load();
  }
  async function del() {
    const r = T.selected()[0]; if (!r) return toast("حدد حركة الأول");
    if (r.invoice_id) return alertBox("ده مرتجع هالك — عدّله أو احذفه من فاتورة المرتجع نفسها (ضغطتين تفتحها).");
    if (!(await confirmBox("تحذف حركة الهالك؟ الكمية هترجع للمخزن.", "حذف", "احذف"))) return;
    try { await api("delete_damaged", r.key); toast("✔ اتحذفت", "ok"); load(); } catch (e) { alertBox(e.message); }
  }
  enterChain([qty, notes], save);
  [from, to, src].forEach((x) => x.addEventListener("change", load)); let t = null; q.addEventListener("input", () => { clearTimeout(t); t = setTimeout(load, 250); });
  box.replaceChildren(h("div", { class: "page" },
    h("div", { class: "hint" }, "الهالك = مرتجعات مبيعات اتعلّمت «هالك» + بضاعة باظت عندك وبتسجّلها هنا. التكلفة بسعر الشراء (FIFO) وبتتخصم من الربح."),
    h("section", { class: "card anim-up d1" }, h("div", { class: "card-h" }, h("h2", null, "تسجيل هالك من المخزن")),
      h("div", { class: "form add" }, h("div", { class: "fld" }, h("label", { for: "d-item" }, "الصنف"), item.el), h("label", { class: "fld" }, "الكمية", qty), h("label", { class: "fld" }, "التاريخ", dDate),
        h("div", { class: "fld", style: { justifyContent: "flex-end" } }, h("button", { class: "btn primary", onclick: save }, icon("save", 18), "حفظ")), h("label", { class: "fld", style: { gridColumn: "1/-1" } }, "السبب / ملاحظات", notes))),
    h("section", { class: "card anim-up d2" }, h("div", { class: "form" }, h("label", { class: "fld" }, "من", from), h("label", { class: "fld" }, "إلى", to), h("label", { class: "fld" }, "المصدر", src), h("label", { class: "fld span2" }, "بحث", q))),
    h("section", { class: "card anim-up d3" }, h("div", { class: "card-h" }, h("h2", null, "السجل"), h("button", { class: "btn danger", onclick: del }, icon("trash", 18), "حذف (الهالك من المخزن)")), T.el)));
  await load(); item.focus();
}

/* ===================== العينات ===================== */
async function renderSampleItems(box) {
  const q = h("input", { class: "in", placeholder: "الكود أو الاسم ...", "aria-label": "بحث" });
  const T = selTable({
    cols: [{ h: "ID", key: "id", cls: "hint" }, { h: "الكود", key: "code" }, { h: "اسم العينة", fn: (r) => h("b", null, r.name) }, { h: "الوحدة", key: "unit", cls: "hint" },
      { h: "الوارد", num: true, fn: (r) => fq(r.in) }, { h: "المنصرف", num: true, fn: (r) => fq(r.out) }, { h: "الرصيد", num: true, fn: (r) => h("b", null, fq(r.balance)) }],
    onOpen: (r) => moves(r), onKey: (e) => { if (e.key === "Delete") del(); } });
  let all = [];
  async function load() { try { all = await api("sample_items"); fill(); } catch (e) { toast(e.message, "err"); } }
  const fill = () => { const n = norm(q.value); T.setRows(all.filter((r) => !n || norm(r.name + " " + r.code).includes(n))); };
  const form = async (r) => { r = r || { id: null, code: "", name: "", unit: "قطعة" }; let ok = false;
    await formModal(r.id ? `تعديل «${r.name}»` : "صنف عينة جديد", [{ key: "name", label: "اسم العينة", value: r.name, wide: true }, { key: "code", label: "الكود", value: r.code }, { key: "unit", label: "الوحدة", value: r.unit }],
      { onSave: async (v) => { await api("save_sample_item", { ...v, id: r.id }); ok = true; toast("✔ اتحفظ", "ok"); } }); if (ok) load(); };
  async function moves(r) {
    let d; try { d = await api("sample_moves", r.id); } catch (e) { return toast(e.message, "err"); }
    const M = selTable({ maxH: "55vh", cols: [{ h: "التاريخ", key: "date" }, { h: "الوقت", key: "time", cls: "hint" }, { h: "النوع", key: "kind" }, { h: "العميل / المورد", key: "party" },
      { h: "وارد", num: true, fn: (x) => (x.in ? fq(x.in) : "") }, { h: "منصرف", num: true, fn: (x) => (x.out ? fq(x.out) : "") }, { h: "الرصيد", num: true, fn: (x) => h("b", null, fq(x.balance)) },
      { h: "التكلفة (للعلم)", num: true, fn: (x) => fmt(x.cost) }, { h: "ملاحظات", key: "notes", cls: "hint" }] });
    M.setRows(d.rows);
    modal({ title: `حركات العينة: ${d.name}`, wide: true, enter: false, body: [h("div", { class: "card" }, M.el), h("div", { class: "chip info" }, "الرصيد الحالي: ", h("b", null, `${fq(d.balance)} ${d.unit}`))], actions: [{ label: "قفل", ret: true }] });
  }
  async function del() { const r = T.selected()[0]; if (!r) return toast("حدد عينة الأول"); if (!(await confirmBox(`تحذف العينة «${r.name}»؟`, "حذف", "احذف"))) return;
    try { await api("delete_sample_item", r.id); toast("✔ اتحذفت", "ok"); load(); } catch (e) { alertBox(e.message); } }
  const one = (fn) => () => { const r = T.selected()[0]; if (!r) return toast("حدد عينة الأول"); fn(r); };
  q.addEventListener("input", fill);
  box.replaceChildren(h("div", { class: "page" }, h("div", { class: "hint" }, "أصناف العينات منفصلة تمامًا: مش بتأثر على المخزون ولا الأرباح ولا الخزنة ولا أرصدة العملاء."),
    h("section", { class: "card anim-up d1" }, h("div", { class: "card-h" }, h("h2", null, "أصناف العينات"), h("div", { style: { flex: "1 1 240px" } }, q),
      h("button", { class: "btn primary", onclick: () => form(null) }, icon("plus", 18), "عينة جديدة"), h("button", { class: "btn", onclick: one(form) }, icon("edit", 18), "تعديل"),
      h("button", { class: "btn", onclick: one(moves) }, icon("list", 18), "الحركات"), h("button", { class: "btn danger", onclick: del }, icon("trash", 18), "حذف")), T.el)));
  await load(); q.focus();
}
async function renderSamples(box, kind) {
  const inn = kind === "عينات مشتريات";
  const [sitems, parties] = await Promise.all([api("sample_items"), api("parties_list")]);
  const Sm = S["smp" + kind] || (S["smp" + kind] = { from: monthStart(), to: S.boot.today, q: "" });
  const item = combo({ id: "sm-item", label: "العينة", placeholder: "اكتب اسم العينة ...", items: () => sitems, sub: (i) => `رصيد ${fq(i.balance)} ${i.unit}`, onPick: (i, adv) => { if (adv) { qty.focus(); qty.select(); } } });
  const party = combo({ id: "sm-party", label: inn ? "المورد" : "العميل", placeholder: "(اختياري)", items: () => parties, sub: (p) => p.kind, onPick: (p, adv) => { if (adv) notes.focus(); } });
  const sDate = dateIn(S.boot.today, "التاريخ"), qty = h("input", { class: "in num", value: "1", "aria-label": "الكمية" }), cost = h("input", { class: "in num", value: "0", "aria-label": "التكلفة" }), notes = h("input", { class: "in", "aria-label": "ملاحظات" });
  const from = dateIn(Sm.from, "من"), to = dateIn(Sm.to, "إلى"), q = h("input", { class: "in", value: Sm.q, placeholder: "العينة أو الاسم أو الملاحظات ...", "aria-label": "بحث" });
  const T = selTable({
    cols: [{ h: "التاريخ", key: "date" }, { h: "الوقت", key: "time", cls: "hint" }, { h: "العينة", fn: (r) => h("b", null, r.item) }, { h: "الكمية", num: true, fn: (r) => `${fq(r.qty)} ${r.unit}` },
      { h: "التكلفة (للعلم)", num: true, fn: (r) => fmt(r.cost) }, { h: inn ? "المورد" : "العميل", key: "party" }, { h: "ملاحظات", key: "notes", cls: "hint" }],
    onKey: (e) => { if (e.key === "Delete") del(); },
    totals: (rs, isSel) => [h("b", null, isSel ? "إجمالي المحدد" : "الإجمالي"), totItem("عدد الحركات", rs.length), totItem("الكمية", fq(rs.reduce((a, r) => a + r.qty, 0))), totItem("التكلفة (للعلم)", fmt(rs.reduce((a, r) => a + r.cost, 0)))] });
  async function load() { Sm.from = from.value; Sm.to = to.value || from.value; Sm.q = q.value; try { T.setRows(await api("samples", kind, Sm.from, Sm.to, Sm.q)); } catch (e) { toast(e.message, "err"); } }
  async function save() {
    const it = item.get(); if (!it) { item.focus(); return toast("اختار العينة", "err"); }
    const p = { item_id: it.id, qty: qty.value, cost: cost.value, date: sDate.value, party_id: party.get() ? party.get().id : null, notes: notes.value };
    try {
      let r = await api("save_sample", kind, p, false);
      if (r.confirm) { if (!(await confirmBox(r.confirm, "رصيد العينات", "كمّل"))) return; r = await api("save_sample", kind, p, true); }
      toast("✔ اتسجلت", "ok"); qty.value = "1"; cost.value = "0"; notes.value = ""; item.set(null); item.focus(); load();
    } catch (e) { alertBox(e.message); }
  }
  async function del() { const r = T.selected()[0]; if (!r) return toast("حدد حركة الأول"); if (!(await confirmBox("تحذف حركة العينة نهائيًا؟", "حذف", "احذف"))) return;
    try { await api("delete_sample", r.id); toast("✔ اتحذفت", "ok"); load(); } catch (e) { alertBox(e.message); } }
  enterChain([qty, cost], () => party.focus()); enterChain([notes], save);
  [from, to].forEach((x) => x.addEventListener("change", load)); let t = null; q.addEventListener("input", () => { clearTimeout(t); t = setTimeout(load, 250); });
  box.replaceChildren(h("div", { class: "page" },
    h("div", { class: "hint" }, inn ? "عينات واردة لينا (بتزوّد رصيد العينات)" : "عينات خارجة مننا (بتقلل رصيد العينات)", " — مش بتأثر على المخزون ولا الحسابات."),
    sitems.length ? null : h("div", { class: "chip warn" }, "لسه مفيش أصناف عينات — ضيفها من «أصناف العينات» الأول"),
    h("section", { class: "card anim-up d1" }, h("div", { class: "card-h" }, h("h2", null, "تسجيل حركة")),
      h("div", { class: "form" }, h("div", { class: "fld span2" }, h("label", { for: "sm-item" }, "العينة"), item.el), h("label", { class: "fld" }, "الكمية", qty), h("label", { class: "fld" }, "التكلفة (للعلم)", cost),
        h("label", { class: "fld" }, "التاريخ", sDate), h("div", { class: "fld span2" }, h("label", { for: "sm-party" }, inn ? "المورد (اختياري)" : "العميل (اختياري)"), party.el), h("label", { class: "fld span2" }, "ملاحظات", notes),
        h("div", { class: "fld", style: { justifyContent: "flex-end" } }, h("button", { class: "btn primary", onclick: save }, icon("save", 18), "حفظ")))),
    h("section", { class: "card anim-up d2" }, h("div", { class: "form" }, h("label", { class: "fld" }, "من", from), h("label", { class: "fld" }, "إلى", to), h("label", { class: "fld span2" }, "بحث", q))),
    h("section", { class: "card anim-up d3" }, h("div", { class: "card-h" }, h("h2", null, "السجل"), h("button", { class: "btn danger", onclick: del }, icon("trash", 18), "حذف")), T.el)));
  await load(); item.focus();
}

/* ===================== التقارير ===================== */
function reportRows(rows) {
  return h("div", { class: "card", style: { padding: "8px 18px 14px" } }, rows.map(([t, a, b]) => h("div", { class: "rep-row " + (t === "h" ? "h" : t === "b" ? "b" : "") }, h("span", null, a), h("span", { class: "num" }, b))));
}
async function renderDaily(box) {
  const day = dateIn(S.dailyDay || S.boot.today, "اليوم");
  const out = h("div", { class: "anim-up d2" });
  const side = h("div", { class: "anim-up d3" });
  // جدول المقارنة: ليه فترة لوحده (من / إلى) ومش بيتغير لما تختار يوم في التقرير
  const TR = S.trSt || (S.trSt = { from: "", to: "" });
  if (!TR.to) { const t = new Date(S.boot.today); TR.to = S.boot.today; t.setDate(t.getDate() - 13); TR.from = t.toISOString().slice(0, 10); }
  const trFrom = dateIn(TR.from, "من تاريخ"), trTo = dateIn(TR.to, "إلى تاريخ");
  trFrom.onchange = () => { TR.from = trFrom.value; trend(); }; trTo.onchange = () => { TR.to = trTo.value; trend(); };
  let TT = null, trOwn = false, mx = {};
  const bar = (v, m, cls) => h("div", { class: "dt-bar" }, h("i", { class: cls, style: { width: Math.max(0, Math.round(Math.abs(v) / (m || 1) * 100)) + "%" } }), h("span", null, fmt(v)));
  async function trend() {
    let t; try { t = await api("daily_trend", TR.from, TR.to); } catch (e) { return toast(e.message, "err"); }
    trOwn = t.profit; TR.from = t.from; TR.to = t.to; trFrom.value = t.from; trTo.value = t.to;
    const m = (k) => Math.max(1, ...t.rows.map((r) => Math.abs(r[k] || 0)));
    mx = { sales: m("sales"), collect: m("collect"), profit: trOwn ? m("profit") : 1 };
    TT = selTable({ maxH: "calc(100vh - 290px)", rowClass: (r) => (r.date === day.value ? "on" : ""),
      cols: [{ h: "اليوم", fn: (r) => h("span", null, h("b", null, r.day), " ", h("span", { class: "hint" }, r.date.slice(5))), sort: (r) => r.date },
        { h: "فواتير", num: true, fn: (r) => r.n || "—", sort: (r) => r.n },
        { h: "المبيعات", fn: (r) => bar(r.sales, mx.sales, "s"), sort: (r) => r.sales }, { h: "التحصيلات", fn: (r) => bar(r.collect, mx.collect, "c"), sort: (r) => r.collect }]
        .concat(trOwn ? [{ h: "الربح", fn: (r) => bar(r.profit, mx.profit, r.profit < 0 ? "n" : "p"), sort: (r) => r.profit }] : []),
      onOpen: (r) => { day.value = r.date; load(false); },
      totals: (rs, isSel) => [h("b", null, isSel ? `إجمالي المحدد (${rs.length} يوم)` : `الإجمالي (${rs.length} يوم)`), totItem("فواتير", rs.reduce((a, r) => a + r.n, 0)),
        totItem("مبيعات", fmt(rs.reduce((a, r) => a + r.sales, 0))), totItem("تحصيلات", fmt(rs.reduce((a, r) => a + r.collect, 0))),
        trOwn ? totItem("الربح", fmt(rs.reduce((a, r) => a + (r.profit || 0), 0)), true) : null].filter(Boolean) });
    TT.setRows(t.rows);
    side.replaceChildren(h("section", { class: "card" }, h("div", { class: "card-h" }, h("h2", null, "مقارنة الأيام"),
        h("label", { class: "fld", style: { flexDirection: "row", alignItems: "center" } }, "من", trFrom), h("label", { class: "fld", style: { flexDirection: "row", alignItems: "center" } }, "إلى", trTo)),
      h("div", { class: "hint", style: { padding: "6px 18px 0" } }, "للعرض بس — مش بيتطبع • حدد كذا يوم (Ctrl / Shift أو اسحب) = إجماليهم تحت • ضغطتين على يوم = تقريره"), TT.el));
  }
  async function load(withTrend = true) {
    S.dailyDay = day.value; try { const r = await api("daily_report", day.value); out.replaceChildren(reportRows(r.rows)); } catch (e) { toast(e.message, "err"); }
    if (withTrend || !TT) trend(); else TT.el.querySelectorAll("tbody tr").forEach((tr, i) => tr.classList.toggle("on", (TT.rows()[i] || {}).date === day.value));
  }
  day.addEventListener("change", () => load(false));
  box.replaceChildren(h("div", { class: "page daily-grid" }, h("div", { style: { minWidth: 0 } },
    h("section", { class: "card anim-up d1", style: { padding: "14px 18px", display: "flex", gap: "10px", alignItems: "flex-end", flexWrap: "wrap" } }, h("label", { class: "fld" }, "اليوم", day),
      h("button", { class: "btn gold", onclick: async () => { try { await api("print_daily", day.value); toast("🖨 شاشة الطباعة هتفتح خلال ثواني ...", "ok"); } catch (e) { toast(e.message, "err"); } } }, icon("print", 18), "طباعة")), out), side));
  await load();
}
async function renderMonthly(box) {
  const M = S.monSt || (S.monSt = { month: S.boot.today.slice(0, 7) });
  const mIn = h("input", { class: "in", type: "month", value: M.month, "aria-label": "الشهر" });
  const out = h("div", { class: "page", style: { padding: 0 } });
  const pct = (a, b, good = true) => { if (!b) return h("span", { class: "hint" }, "—"); const p = (a - b) / Math.abs(b) * 100; return h("span", { class: "chg " + ((p >= 0) === good ? "up" : "down") }, (p >= 0 ? "▲ " : "▼ ") + Math.abs(p).toFixed(0) + "%"); };
  const tbl = (cols, rows, opts = {}) => { const T = selTable({ maxH: opts.maxH || "420px", cols, onOpen: opts.onOpen, menu: opts.menu, totals: opts.totals }); T.setRows(rows); return T.el; };
  const sec = (title, el, cls = "") => h("section", { class: "card " + cls }, h("div", { class: "card-h" }, h("h2", null, title)), el);
  async function load() {
    M.month = mIn.value || S.boot.today.slice(0, 7);
    let d; try { d = await api("monthly_report", M.month); } catch (e) { return toast(e.message, "err"); }
    const k = d.k, pk = d.pk;
    const tile = (t, a, b, ic, good = true) => h("div", { class: "card kpi dark" }, h("div", { class: "h" }, h("span", { class: "ic" }, icon(ic, 20)), t), h("div", { class: "v" + (a < 0 ? " neg" : "") }, fmt(a)),
      h("div", { class: "kpi-sub" }, "الشهر اللي قبله: ", fmt(b), " ", pct(a, b, good)));
    const kv = (rows) => h("div", { style: { padding: "6px 18px 12px" } }, rows.map(([l, v, b]) => h("div", { class: "rep-row" + (b === true ? " b" : "") }, h("span", null, l), h("span", { class: "num" }, b === "n" ? String(v) : fmt(v)))));
    out.replaceChildren(
      h("div", { class: "kpis" }, tile("المبيعات الصافية", k.sales - k.ret, pk.sales - pk.ret, "sale"), tile("التحصيلات", k.collect, pk.collect, "cash"), tile("إجمالي الربح", k.gross, pk.gross, "chart"),
        tile("المصروفات", k.exp, pk.exp, "list", false), tile("صافي الربح", k.net, pk.net, "chart"), tile("المشتريات", k.buys, pk.buys, "box", false)),
      h("div", { class: "mon-grid" },
        sec("الأرباح بالتفصيل", kv(d.metrics.map(([l, v]) => [l, v, l === "صافي الربح" || l.includes("Total")]))),
        sec("الخزنة والأرصدة", kv([["رصيد الخزنة أول الشهر", d.cash.open], ["دخل الخزنة", d.cash.in], ["خرج من الخزنة", d.cash.out], ["رصيد الخزنة آخر الشهر", d.cash.close, true],
          ["على العملاء (لنا) آخر الشهر", d.end.recv], ["علينا للموردين آخر الشهر", d.end.pay], ["أرباح اتصرفت للملاك", d.end.owners], ["عدد فواتير المبيعات", k.n_sales, "n"]])),
        sec("المناديب", tbl([{ h: "المندوب", fn: (r) => h("b", null, r.name) }, { h: "فواتير", num: true, key: "n" }, { h: "مبيعات", num: true, fn: (r) => fmt(r.sales) }, { h: "تحصيل", num: true, fn: (r) => fmt(r.collect) }], d.reps)),
        sec("المصروفات", d.exp_cats.length ? tbl([{ h: "البند", fn: (r) => r[0] }, { h: "المبلغ", num: true, fn: (r) => fmt(r[1]) }], d.exp_cats) : h("div", { class: "hint", style: { padding: "14px 18px" } }, "مفيش مصروفات عامة الشهر ده"))),
      sec("أكبر العملاء (صافي المبيعات)", tbl([{ h: "العميل", fn: (r) => h("b", null, r.name) }, { h: "فواتير", num: true, key: "n" }, { h: "صافي المبيعات", num: true, fn: (r) => fmt(r.net) }, { h: "اتحصّل منه", num: true, fn: (r) => fmt(r.collect) }], d.customers,
        { onOpen: (r) => { S.pendingStatement = r.id; go("acc:statement", true); } })),
      sec("أكتر الأصناف ربح", tbl([{ h: "الصنف", fn: (r) => h("b", null, r.name) }, { h: "الكمية", num: true, fn: (r) => fq(r.qty) }, { h: "المبيعات", num: true, fn: (r) => fmt(r.rev) }, { h: "التكلفة", num: true, fn: (r) => fmt(r.cost) },
        { h: "الربح", num: true, fn: (r) => h("b", { style: { color: r.profit < 0 ? "var(--red)" : "var(--green)" } }, fmt(r.profit)) }], d.items)),
      d.items_low.length ? sec("⚠ أصناف خسرانة", tbl([{ h: "الصنف", key: "name" }, { h: "الكمية", num: true, fn: (r) => fq(r.qty) }, { h: "الربح", num: true, fn: (r) => h("b", { style: { color: "var(--red)" } }, fmt(r.profit)) }], d.items_low)) : null,
      sec("الأيام", tbl([{ h: "اليوم", key: "date" }, { h: "فواتير", num: true, key: "n" }, { h: "مبيعات", num: true, fn: (r) => fmt(r.sales) }, { h: "مرتجع", num: true, fn: (r) => (r.ret ? fmt(r.ret) : "") },
        { h: "مشتريات", num: true, fn: (r) => (r.buys ? fmt(r.buys) : "") }, { h: "تحصيل", num: true, fn: (r) => fmt(r.collect) }, { h: "مصروفات", num: true, fn: (r) => (r.exp ? fmt(r.exp) : "") }], d.days,
        { maxH: "520px", onOpen: (r) => { S.dailyDay = r.date; go("rep:daily", true); },
          totals: (rs, isSel) => [h("b", null, isSel ? "المحدد" : "الإجمالي"), totItem("الأيام", rs.length), totItem("مبيعات", fmt(rs.reduce((a, r) => a + r.sales, 0))), totItem("تحصيل", fmt(rs.reduce((a, r) => a + r.collect, 0)))] })));
  }
  mIn.addEventListener("change", load);
  const shift = (n) => { const [y, m] = (mIn.value || M.month).split("-").map(Number); const d = new Date(y, m - 1 + n, 1); mIn.value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`; load(); };
  box.replaceChildren(h("div", { class: "page" },
    h("section", { class: "card anim-up d1", style: { padding: "14px 18px", display: "flex", gap: "10px", alignItems: "flex-end", flexWrap: "wrap" } },
      h("button", { class: "btn ghost", onclick: () => shift(-1) }, "→ الشهر اللي قبله"), h("label", { class: "fld" }, "الشهر", mIn), h("button", { class: "btn ghost", onclick: () => shift(1) }, "الشهر اللي بعده ←"),
      h("button", { class: "btn gold", onclick: async () => { try { await api("monthly_print", mIn.value); toast("🖨 شاشة الطباعة هتفتح خلال ثواني ...", "ok"); } catch (e) { toast(e.message, "err"); } } }, icon("print", 18), "طباعة / PDF")), out));
  await load();
}
async function renderProfit(box) {
  const P = S.pfSt || (S.pfSt = { from: S.boot.today, to: S.boot.today });
  const from = dateIn(P.from, "من"), to = dateIn(P.to, "إلى");
  const sum = h("div"), detail = h("div"), cats = h("div", { class: "hint" });
  const T = selTable({ maxH: "60vh", cols: [{ h: "الصنف", fn: (r) => h("b", null, r.name) }, { h: "الكمية الصافية", num: true, fn: (r) => fq(r.qty) }, { h: "المبيعات الصافية", num: true, fn: (r) => fmt(r.rev) },
    { h: "متوسط التكلفة", num: true, fn: (r) => fmt(r.avg) }, { h: "إجمالي التكلفة", num: true, fn: (r) => fmt(r.cost) }, { h: "الربح", num: true, fn: (r) => h("b", { style: { color: r.profit < 0 ? "var(--red)" : "var(--green)" } }, fmt(r.profit)) }],
    onOpen: (r) => r.id ? showItemInvoices(r.id, P.from, P.to, ["مبيعات", "مرتجع مبيعات"]) : toast("الصنف ده مش موجود في الأصناف"),
    menu: (r) => r.id ? [{ label: "👁 مبيعاته في الفترة", fn: () => showItemInvoices(r.id, P.from, P.to, ["مبيعات", "مرتجع مبيعات"]) }, { label: "📋 كل فواتيره", fn: () => showItemInvoices(r.id) }] : [],
    totals: (rs, isSel) => [h("b", null, isSel ? "المحدد" : "الإجمالي"), totItem("المبيعات", fmt(rs.reduce((a, r) => a + r.rev, 0))), totItem("التكلفة", fmt(rs.reduce((a, r) => a + r.cost, 0))), totItem("الربح", fmt(rs.reduce((a, r) => a + r.profit, 0)), true)] });
  async function load() {
    P.from = from.value; P.to = to.value;
    let r; try { r = await api("profit", P.from, P.to); } catch (e) { return toast(e.message, "err"); }
    sum.replaceChildren(h("div", { class: "card", style: { padding: "8px 18px 14px" } }, r.metrics.map(([l, v]) => h("div", { class: "rep-row" + (l === "صافي الربح" || l.includes("Total") || l === "إجمالي الربح" ? " b" : "") },
      h("span", null, l), h("span", { class: "num", style: { color: l === "صافي الربح" ? (v < 0 ? "var(--red)" : "var(--green)") : "" } }, fmt(v))))));
    T.setRows(r.rows);
    cats.textContent = r.by_cat.length ? "المصروفات العامة: " + r.by_cat.map(([n, v]) => `${n}: ${fmt(v)}`).join(" • ") : "";
  }
  async function compare() {
    const mode = h("select", { class: "in", "aria-label": "طريقة المقارنة" }, ["الشهر السابق", "الفترة السابقة بنفس الطول", "فترة أخرى"].map((x) => h("option", { value: x }, x)));
    const cf = dateIn("", "من"), ct = dateIn("", "إلى"); const res = h("div");
    const run = async () => {
      let r; try { r = await api("profit_compare", from.value, to.value, mode.value, cf.value || null, ct.value || null); } catch (e) { return toast(e.message, "err"); }
      res.replaceChildren(h("div", { class: "hint" }, `الحالية: ${r.cur[0]} ← ${r.cur[1]}  •  المقارنة: ${r.prev[0]} ← ${r.prev[1]}`),
        h("div", { class: "tbl-wrap card" }, h("table", { class: "t" }, h("thead", null, h("tr", null, h("th", null, "البند"), h("th", { class: "num" }, "الحالية"), h("th", { class: "num" }, "المقارنة"), h("th", { class: "num" }, "الفرق"), h("th", { class: "num" }, "%"))),
          h("tbody", null, r.rows.map(([l, x, y]) => { const d = x - y; return h("tr", null, h("td", null, h("b", null, l)), h("td", { class: "num" }, fmt(x)), h("td", { class: "num" }, fmt(y)),
            h("td", { class: "num", style: { color: d < 0 ? "var(--red)" : "var(--green)" } }, (d >= 0 ? "+" : "") + fmt(d)), h("td", { class: "num" }, Math.abs(y) > 1e-9 ? ((d / Math.abs(y)) * 100).toFixed(1) + "%" : "—")); })))));
    };
    [mode, cf, ct].forEach((x) => x.addEventListener("change", run));
    modal({ title: "مقارنة الأرباح", wide: true, enter: false, body: [h("div", { class: "form", style: { padding: 0 } }, h("label", { class: "fld" }, "طريقة المقارنة", mode), h("label", { class: "fld" }, "من (فترة أخرى)", cf), h("label", { class: "fld" }, "إلى (فترة أخرى)", ct)), res], actions: [{ label: "قفل", ret: true }] });
    run();
  }
  [from, to].forEach((x) => x.addEventListener("change", load));
  box.replaceChildren(h("div", { class: "page" },
    h("section", { class: "card anim-up d1", style: { padding: "14px 18px", display: "flex", gap: "10px", alignItems: "flex-end", flexWrap: "wrap" } }, h("label", { class: "fld" }, "من تاريخ", from), h("label", { class: "fld" }, "إلى تاريخ", to),
      h("button", { class: "btn", onclick: compare }, icon("chart", 18), "مقارنة بفترة تانية")),
    h("div", { class: "grid2" }, h("div", { class: "narrow anim-up d2" }, h("h2", { class: "side-h", style: { margin: "0 0 8px" } }, "ملخص الفترة"), sum),
      h("section", { class: "card wide anim-up d3" }, h("div", { class: "card-h" }, h("h2", null, "تفصيل الأصناف"), h("span", { class: "hint" }, "ضغطتين على صنف = مبيعاته وفواتيره في الفترة")), T.el)), cats,
    h("div", { class: "hint" }, "التكلفة = الوارد أولًا يُصرف أولًا (FIFO). الأرباح للمالك بس.")));
  await load();
}
async function renderReps(box) {
  const R = S.rpSt || (S.rpSt = { from: monthStart(), to: S.boot.today });
  const from = dateIn(R.from, "من"), to = dateIn(R.to, "إلى");
  const T = selTable({
    cols: [{ h: "المندوب", fn: (r) => h("b", null, r.name) }, { h: "عدد الفواتير", num: true, key: "n" }, { h: "طن", num: true, fn: (r) => fmt(r.tons) }, { h: "شيكارة", num: true, fn: (r) => fmt(r.qty) },
      { h: "المبيعات", num: true, fn: (r) => fmt(r.sales) }, { h: "التحصيلات", num: true, fn: (r) => fmt(r.col) }, { h: "المستحق على عملائه (الآن)", num: true, fn: (r) => fmt(r.cust) },
      { h: "عمولة الفترة", num: true, fn: (r) => (r.key ? fmt(r.comm) : "—") }, { h: "عمولة باقية له", num: true, fn: (r) => (r.key ? h("b", null, fmt(r.due)) : "—") }],
    onOpen: (r) => detail(r), menu: (r) => [{ label: "👁 عرض حركاته وعملاؤه", fn: () => detail(r) }],
    totals: (rs) => [totItem("الفواتير", rs.reduce((a, r) => a + r.n, 0)), totItem("الكمية", `${fmt(rs.reduce((a, r) => a + r.tons, 0))} طن (${fmt(rs.reduce((a, r) => a + r.qty, 0))} شيكارة)`),
      totItem("المبيعات", fmt(rs.reduce((a, r) => a + r.sales, 0))), totItem("التحصيلات", fmt(rs.reduce((a, r) => a + r.col, 0))), totItem("المستحق على العملاء", fmt(rs.reduce((a, r) => a + r.cust, 0))), totItem("عمولات الفترة", fmt(rs.reduce((a, r) => a + r.comm, 0)))] });
  async function load() { R.from = from.value; R.to = to.value; try { T.setRows(await api("reps_report", R.from, R.to)); } catch (e) { toast(e.message, "err"); } }
  async function detail(r) {
    let d; try { d = await api("rep_detail", r.key, R.from, R.to); } catch (e) { return toast(e.message, "err"); }
    const M = selTable({ maxH: "45vh", cols: [{ h: "التاريخ", key: "date" }, { h: "الوقت", key: "time", cls: "hint" }, { h: "البيان", key: "what" }, { h: "المرجع", key: "ref" }, { h: "العميل", fn: (x) => h("b", null, x.party) },
      { h: "مبيعات", num: true, fn: (x) => numOrEmpty(x.sales) }, { h: "تحصيل", num: true, fn: (x) => numOrEmpty(x.col) }, { h: "طن", num: true, fn: (x) => numOrEmpty(x.tons) }, { h: "شيكارة", num: true, fn: (x) => numOrEmpty(x.qty) }, { h: "عمولة", num: true, fn: (x) => numOrEmpty(x.comm) }],
      onOpen: (x) => { if (x.key.startsWith("0-")) showInvoice(+x.key.slice(2)); } });
    M.setRows(d.rows);
    const C = selTable({ maxH: "30vh", cols: [{ h: "العميل", fn: (x) => h("b", null, x.name) }, { h: "الهاتف", key: "phone" }, { h: "الرصيد الحالي", num: true, fn: (x) => h("b", { style: { color: x.balance > 0 ? "var(--red)" : "var(--green)" } }, fmt(x.balance)) }],
      onOpen: (x) => { closeModals(); S.pendingStatement = x.id; go("acc:statement", true); } });
    C.setRows(d.customers);
    modal({ title: `حركات ${r.name} من ${R.from} إلى ${R.to}`, wide: true, enter: false, body: [h("div", { class: "card" }, M.el), h("b", { style: { color: "var(--navy)" } }, "عملاؤه اللي ليهم رصيد"), h("div", { class: "card" }, C.el)], actions: [{ label: "قفل", ret: true }] });
  }
  [from, to].forEach((x) => x.addEventListener("change", load));
  box.replaceChildren(h("div", { class: "page" },
    h("section", { class: "card anim-up d1", style: { padding: "14px 18px", display: "flex", gap: "10px", alignItems: "flex-end", flexWrap: "wrap" } }, h("label", { class: "fld" }, "من تاريخ", from), h("label", { class: "fld" }, "إلى تاريخ", to),
      h("span", { class: "hint" }, "المبيعات = صافي فواتير المبيعات باسم المندوب • ضغطتين = حركاته وعملاؤه")),
    h("section", { class: "card anim-up d2" }, T.el)));
  await load();
}
async function renderTargets(box) {
  const month = h("input", { class: "in", type: "month", value: S.tgMonth || S.boot.today.slice(0, 7), "aria-label": "الشهر" });
  const cards = h("div", { class: "kpis" });
  async function load() {
    S.tgMonth = month.value; let rows; try { rows = await api("targets", month.value); } catch (e) { return toast(e.message, "err"); }
    cards.replaceChildren(...rows.map((r, i) => {
      const pct = r.pct ?? 0, color = pct >= 100 ? "#15803d" : pct >= 60 ? "#c8a24a" : "#c2410c";
      return h("div", { class: "card kpi lift anim-up", style: { animationDelay: i * 0.05 + "s", gap: "8px" } },
        h("div", { class: "h" }, h("span", { class: "ic", style: { background: "#e8effa", color: "#1e5aa8" } }, icon("users", 20)), h("b", { style: { color: "var(--navy)", fontSize: "16px" } }, r.name)),
        h("div", { class: "s" }, r.target ? `المحقق ${fmt(r.done)} من ${fmt(r.target)} ${r.unit}` : `المحقق ${fmt(r.tons)} طن (${fmt(r.bags)} شيكارة دقيق) — مفيش تارجت`),
        h("div", { class: "track", style: { height: "12px", borderRadius: "6px", background: "#edf2f8", overflow: "hidden" } }, h("div", { class: "fill", style: { height: "100%", width: Math.min(100, pct) + "%", background: color, transformOrigin: "right", animation: "grow 1s var(--ease) .2s both" } })),
        h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center" } }, h("b", { style: { color, fontSize: "20px" } }, r.target ? pct + "%" : "—"),
          h("div", { style: { display: "flex", gap: "6px" } },
            h("button", { class: "btn", style: { minHeight: "34px" }, onclick: async () => {
              const unit = h("select", { class: "in" }, ["طن", "شيكارة"].map((u) => h("option", { value: u }, u))); unit.value = r.unit || "طن";
              const qty = h("input", { class: "in num", value: r.target || "", "aria-label": "التارجت" });
              const ok = await modal({ title: `تارجت ${r.name} من شهر ${month.value}`, body: [h("label", { class: "fld" }, "الكمية", qty), h("label", { class: "fld" }, "الوحدة", unit), h("div", { class: "hint" }, "بيتطبق على الشهر ده واللي بعده لحد ما تغيّره")],
                actions: [{ label: "حفظ", cls: "primary", value: async () => { try { await api("set_target", r.id, month.value, qty.value, unit.value); return true; } catch (e) { toast(e.message, "err"); return false; } } }, { label: "إلغاء", value: () => null }] });
              if (ok) { toast("✔ اتحفظ التارجت", "ok"); load(); } } }, icon("edit", 16), "تحديد"),
            r.target ? h("button", { class: "btn danger", style: { minHeight: "34px" }, onclick: async () => { if (!(await confirmBox(`تلغي تارجت «${r.name}» من شهر ${month.value}؟`))) return; await api("clear_target", r.id, month.value); load(); } }, icon("x", 16)) : null)));
    }));
    if (!rows.length) cards.replaceChildren(h("div", { class: "card empty" }, "مفيش مناديب شغالين"));
  }
  async function itemsModal() {
    let its; try { its = await api("target_items"); } catch (e) { return toast(e.message, "err"); }
    const q = h("input", { class: "in", placeholder: "دوّر على صنف ...", "aria-label": "بحث" });
    const boxes = its.map((it) => ({ it, cb: h("input", { type: "checkbox", checked: it.on }) }));
    const list = h("div", { class: "tgt-list" }, boxes.map(({ it, cb }) => h("label", { class: "tgt-it", "data-n": norm(it.name) }, cb, h("span", null, it.name), h("span", { class: "hint" }, it.unit))));
    const cnt = h("b"); const upd = () => (cnt.textContent = boxes.filter((b) => b.cb.checked).length + " صنف متعلّم");
    list.addEventListener("change", upd); upd();
    q.addEventListener("input", () => { const n = norm(q.value); list.querySelectorAll(".tgt-it").forEach((l) => (l.style.display = !n || l.dataset.n.includes(n) ? "" : "none")); });
    const ok = await modal({ title: "🌾 الأصناف اللي بتتحسب في التارجت", enter: false,
      body: [h("div", { class: "hint" }, "التارجت بيتحسب على شكاير الأصناف المعلّمة بس (الدقيق). علّم أو شيل العلامة وبعدين احفظ."), q, cnt, list],
      actions: [{ label: "حفظ", cls: "primary", icon: "save", value: async () => { try { await api("set_target_items", boxes.filter((b) => b.cb.checked).map((b) => b.it.id)); return true; } catch (e) { toast(e.message, "err"); return false; } } }, { label: "إلغاء", value: () => null }] });
    if (ok) { toast("✔ اتحفظ — التارجت اتحسب من جديد", "ok"); load(); }
  }
  month.addEventListener("change", load);
  box.replaceChildren(h("div", { class: "page" }, h("section", { class: "card anim-up", style: { padding: "14px 18px", display: "flex", gap: "10px", alignItems: "flex-end", flexWrap: "wrap" } }, h("label", { class: "fld" }, "الشهر", month),
    h("button", { class: "btn gold", onclick: itemsModal }, "🌾 أصناف التارجت"), h("span", { class: "hint", style: { alignSelf: "center" } }, "التارجت بيتحسب على شكاير الدقيق بس")), cards));
  await load();
}
async function renderActivity(box) {
  const L = S.lgSt || (S.lgSt = { from: new Date(Date.now() - 7 * 864e5).toISOString().slice(0, 10), to: S.boot.today, act: "الكل", q: "" });
  const from = dateIn(L.from, "من"), to = dateIn(L.to, "إلى"), act = h("select", { class: "in", "aria-label": "العملية" }, h("option", { value: "الكل" }, "كل العمليات")), q = h("input", { class: "in", value: L.q, placeholder: "بحث في التفاصيل ...", "aria-label": "بحث" });
  const T = selTable({ cols: [{ h: "الوقت", key: "at", cls: "hint" }, { h: "المستخدم", fn: (r) => h("b", null, r.user) }, { h: "العملية", fn: (r) => h("span", { class: "pill k-مشتريات" }, r.action) }, { h: "التفاصيل", key: "details" }],
    onOpen: (r) => alertBox(`${r.at}\n${r.user}\n${r.action}\n\n${String(r.details || "").replace(" — اللي اتغير: ", "\n\nاللي اتغير:\n").split(" • ").join("\n")}`, "تفاصيل العملية"), totals: (rs) => [totItem("عدد العمليات", rs.length)] });
  let first = true;
  async function load() {
    L.from = from.value; L.to = to.value; L.act = act.value; L.q = q.value;
    let r; try { r = await api("activity_log", L.from, L.to, L.act, L.q); } catch (e) { return toast(e.message, "err"); }
    if (first) { r.actions.forEach((a) => act.appendChild(h("option", { value: a }, a))); act.value = L.act; first = false; }
    T.setRows(r.rows);
  }
  [from, to, act].forEach((x) => x.addEventListener("change", load)); let t = null; q.addEventListener("input", () => { clearTimeout(t); t = setTimeout(load, 300); });
  box.replaceChildren(h("div", { class: "page" }, h("section", { class: "card anim-up d1" }, h("div", { class: "form" }, h("label", { class: "fld" }, "من", from), h("label", { class: "fld" }, "إلى", to), h("label", { class: "fld" }, "العملية", act), h("label", { class: "fld span2" }, "بحث", q))),
    h("section", { class: "card anim-up d2" }, h("div", { class: "card-h" }, h("h2", null, "سجل النشاط (للقراءة بس)")), T.el)));
  await load();
}
async function renderSubcash(box) {
  const C = S.scSt || (S.scSt = { from: monthStart(), to: S.boot.today });
  const from = dateIn(C.from, "من"), to = dateIn(C.to, "إلى");
  const kind = h("div", { class: "seg" }, ["إيداع", "سحب"].map((k) => h("button", { "data-v": k, class: k === "إيداع" ? "on" : "", onclick: () => { kind.dataset.v = k; kind.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.v === k)); } }, k))); kind.dataset.v = "إيداع";
  const d = dateIn(S.boot.today, "التاريخ"), amt = h("input", { class: "in num", "aria-label": "المبلغ" }), notes = h("input", { class: "in", "aria-label": "ملاحظات" });
  const vTot = h("div", { class: "v" }, "0"), vIn = h("div", { class: "v" }, "0"), vOut = h("div", { class: "v" }, "0");
  const T = selTable({ maxH: "calc(100vh - 430px)", cols: [{ h: "التاريخ", key: "date" }, { h: "الوقت", key: "time", cls: "hint" }, { h: "البيان", fn: (r) => h("b", null, r.what) },
    { h: "وارد", num: true, fn: (r) => (r.in ? h("span", { style: { color: "var(--green)", fontWeight: 800 } }, fmt(r.in)) : "") }, { h: "صادر", num: true, fn: (r) => (r.out ? h("span", { style: { color: "var(--red)", fontWeight: 800 } }, fmt(r.out)) : "") },
    { h: "الرصيد", num: true, fn: (r) => h("b", null, fmt(r.balance)) }], onKey: (e) => { if (e.key === "Delete") del(); } });
  async function load() { C.from = from.value; C.to = to.value; let r; try { r = await api("subcash", C.from, C.to); } catch (e) { return toast(e.message, "err"); }
    countUp(vTot, r.total); countUp(vIn, r.in); countUp(vOut, r.out); T.setRows([{ id: null, date: "", time: "", what: "رصيد سابق (مرحّل)", in: 0, out: 0, balance: r.start }, ...r.rows]); }
  async function save() {
    try { let r = await api("save_subcash", kind.dataset.v, d.value, amt.value, notes.value, false);
      if (r.confirm) { if (!(await confirmBox(r.confirm, "رصيد غير كافٍ", "كمّل"))) return; await api("save_subcash", kind.dataset.v, d.value, amt.value, notes.value, true); }
      toast(`✔ اتسجل ${kind.dataset.v} ${fmt(num(amt.value))}`, "ok"); amt.value = ""; notes.value = ""; amt.focus(); load(); } catch (e) { alertBox(e.message); }
  }
  async function del() { const r = T.selected()[0]; if (!r || !r.id) return toast("حدد حركة الأول"); if (!(await confirmBox(`تحذف «${r.what}»؟`, "حذف", "احذف"))) return; await api("delete_subcash", r.id); toast("✔ اتحذفت", "ok"); load(); }
  enterChain([amt, notes], save); [from, to].forEach((x) => x.addEventListener("change", load));
  box.replaceChildren(h("div", { class: "page" },
    h("div", { class: "tiles anim-up d1" }, h("div", { class: "tile net" }, h("div", { class: "h" }, "رصيد الصندوق الفرعي"), vTot), h("div", { class: "tile" }, h("div", { class: "h" }, "وارد الفترة"), vIn), h("div", { class: "tile" }, h("div", { class: "h" }, "صادر الفترة"), vOut)),
    h("section", { class: "card anim-up d2" }, h("div", { class: "card-h" }, h("h2", null, "إيداع / سحب"), h("span", { class: "hint" }, "الصندوق الفرعي منفصل عن الخزنة الرئيسية")),
      h("div", { class: "form" }, h("div", { class: "fld" }, h("span", null, "النوع"), kind), h("label", { class: "fld" }, "التاريخ", d), h("label", { class: "fld" }, "المبلغ", amt), h("label", { class: "fld span2" }, "ملاحظات", notes),
        h("div", { class: "fld", style: { justifyContent: "flex-end" } }, h("button", { class: "btn primary", onclick: save }, icon("save", 18), "حفظ")))),
    h("section", { class: "card anim-up d3" }, h("div", { class: "card-h" }, h("h2", null, "الحركة"), h("label", { class: "fld", style: { flexDirection: "row", alignItems: "center" } }, "من", from),
      h("label", { class: "fld", style: { flexDirection: "row", alignItems: "center" } }, "إلى", to), h("button", { class: "btn danger", onclick: del }, icon("trash", 18), "حذف")), T.el)));
  await load();
}

/* ===================== الموظفون ===================== */
async function renderEmployees(box) {
  const E = S.empSt || (S.empSt = { f: "الكل" });
  let meta = { kinds: ["موظف", "عامل", "مندوب"], left_label: "اللي سابوا الشغل", default_start: "09:00", default_grace: "09:30" };
  const seg = h("div", { class: "seg wrap" });
  const T = selTable({
    cols: [{ h: "ID", key: "id", cls: "hint" }, { h: "الاسم", fn: (r) => h("b", null, r.name) }, { h: "النوع", fn: (r) => r.kind + (r.left ? ` — ساب ${r.left_date}` : "") }, { h: "الصفة", key: "job", cls: "hint" },
      { h: "الهاتف", key: "phone" }, { h: "المرتب / اليومية", num: true, sort: (r) => r.salary, fn: (r) => [fmt(r.salary), h("span", { class: "hint", style: { marginInlineStart: "6px" } }, r.pay_period)] }, { h: "رصيد السلف", num: true, fn: (r) => (r.adv ? h("b", { style: { color: "var(--orange)" } }, fmt(r.adv)) : fmt(0)) },
      { h: "العمولة", fn: (r) => (r.is_rep ? `${fmt(r.commission)} / ${r.comm_unit}` : "") }, { h: "عمولة باقية له", num: true, fn: (r) => (r.is_rep ? fmt(r.due) : "") }, { h: "ميعاد الحضور", fn: (r) => (r.att_start ? `${r.att_start} – ${r.att_grace}` : ""), cls: "hint" }],
    onOpen: (r) => statement(r), onKey: (e) => { if (e.key === "Delete") del(); },
    menu: (r) => [{ label: "👁 عرض (كشف الموظف)", fn: () => statement(r) }, { label: "🗑 حذف", danger: true, fn: () => del() }, { label: "✏️ تعديل", fn: () => form(r) }],
    totals: (rs) => { acts(); return [totItem("العدد", rs.length), totItem("المرتبات (بالشهر)", fmt(rs.filter((r) => r.kind !== "عامل").reduce((a, r) => a + r.salary * ({ "أسبوعي": 52 / 12, "كل أسبوعين": 26 / 12, "يومي": 26 }[r.pay_period] || 1), 0))),
      totItem("يوميات العمال", fmt(rs.filter((r) => r.kind === "عامل").reduce((a, r) => a + r.salary, 0))), totItem("رصيد السلف", fmt(rs.reduce((a, r) => a + r.adv, 0))), totItem("عمولات باقية", fmt(rs.reduce((a, r) => a + (r.is_rep ? r.due : 0), 0)))]; } });
  async function load() { let r; try { r = await api("employees", E.f); } catch (e) { return toast(e.message, "err"); } meta = r;
    if (!seg.children.length) ["الكل", ...r.kinds, r.left_label].forEach((k) => seg.appendChild(h("button", { "data-v": k, class: E.f === k ? "on" : "", onclick: () => { E.f = k; seg.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.v === k)); load(); } }, k)));
    T.setRows(r.rows); acts(); }
  const sel = () => T.selected()[0];
  const one = (fn) => () => { const r = sel(); if (!r) return toast("حدد موظف الأول"); fn(r); };
  async function form(r) {
    r = r || { id: null, name: "", kind: "موظف", job: "", phone: "", salary: 0, commission: 0, comm_unit: "شيكارة", t_start: meta.default_start, t_grace: meta.default_grace, pay_period: "" };
    let ok = false;
    await formModal(r.id ? `تعديل «${r.name}»` : "موظف جديد", [{ key: "name", label: "الاسم", value: r.name, wide: true }, { key: "kind", label: "النوع", value: r.kind, options: meta.kinds },
      { key: "job", label: "الصفة (سواق، محاسب، شيال...)", value: r.job }, { key: "phone", label: "الهاتف", value: r.phone }, { key: "salary", label: "المرتب (للعامل: اليومية)", value: r.salary, num: true },
      { key: "pay_period", label: "بيقبض", value: r.pay_period || (r.kind === "عامل" ? "يومي" : "شهري"), options: ["يومي", "أسبوعي", "كل أسبوعين", "شهري"],
        hint: "العامل الأسبوعي: المرتب هنا = اليومية، والصرف بيحسب اليومية × أيام حضوره في الأسبوع" },
      { key: "commission", label: "عمولة المندوب", value: r.commission, num: true }, { key: "comm_unit", label: "العمولة على كل", value: r.comm_unit, options: ["شيكارة", "طن"] },
      { key: "t_start", label: "ميعاد الحضور", value: r.t_start, type: "time" }, { key: "t_grace", label: "آخر ميعاد من غير تأخير", value: r.t_grace, type: "time" }],
      { onSave: async (v) => { await api("save_employee", { ...v, id: r.id }); ok = true; toast(`✔ اتحفظ «${v.name}»`, "ok"); } });
    if (ok) load();
  }
  async function money(title, msg, fields, call) {
    let ok = false; await formModal(title, fields.map((f) => ({ ...f })).concat(msg ? [] : []), { saveLabel: "صرف", onSave: async (v) => { await call(v); ok = true; } });
    if (ok) { toast("✔ اتصرف", "ok"); load(); }
  }
  const paySalary = one(async (r) => {
    let sg; try { sg = await api("salary_suggest", r.id, S.boot.today); } catch (e) { return toast(e.message, "err"); }
    const what = sg.period === "يومي" ? "يومية" : sg.period === "شهري" ? "مرتب" : `مرتب ${sg.period}`;
    money(`صرف ${what}: ${r.name} — رصيد السلف ${fmt(r.adv)}`, null,
      [{ key: "amount", label: "المبلغ", value: sg.amount, num: true }, { key: "deduct", label: `خصم من السلفة (عليه ${fmt(r.adv)})`, value: 0, num: true },
        { key: "label", label: "عن", value: sg.label, wide: true }, { key: "date", label: "التاريخ", value: S.boot.today, type: "date" }],
      (v) => api("pay_salary", r.id, v.amount, v.deduct, v.date, "", v.label));
  });
  const payAdv = one((r) => money(`صرف سلفة: ${r.name} — رصيده الحالي ${fmt(r.adv)}`, null, [{ key: "amount", label: "المبلغ", num: true }, { key: "date", label: "التاريخ", value: S.boot.today, type: "date" }, { key: "notes", label: "ملاحظات", wide: true }],
    (v) => api("pay_advance", r.id, v.amount, v.date, v.notes)));
  const payComm = one((r) => { if (!r.is_rep) return toast("ده مش مندوب"); money(`صرف عمولة: ${r.name} — الباقي له ${fmt(r.due)}`, null, [{ key: "amount", label: "المبلغ", value: r.due > 0 ? r.due : "", num: true }, { key: "date", label: "التاريخ", value: S.boot.today, type: "date" }, { key: "notes", label: "ملاحظات", wide: true }],
    (v) => api("pay_commission", r.id, v.amount, v.date, v.notes)); });
  async function statement(r) {
    let d; try { d = await api("employee_statement", r.id); } catch (e) { return toast(e.message, "err"); }
    const M = selTable({ maxH: "50vh", cols: [{ h: "التاريخ", key: "date" }, { h: "الوقت", key: "time", cls: "hint" }, { h: "البيان", fn: (x) => h("b", null, x.what) }, { h: "المبلغ", num: true, fn: (x) => fmt(x.gross) },
      { h: "خصم سلفة", num: true, fn: (x) => numOrEmpty(x.ded) }, { h: "المدفوع", num: true, fn: (x) => fmt(x.paid) }, { h: "رصيد السلف", num: true, fn: (x) => fmt(x.adv) }, { h: "ملاحظات", key: "notes", cls: "hint" }],
      menu: (x) => [{ label: "👁 عرض", fn: () => alertBox(`${x.date} ${x.time || ""}\n${x.what}\nالمبلغ: ${fmt(x.gross)}` + (x.ded ? `\nخصم سلفة: ${fmt(x.ded)}` : "") + `\nالمدفوع: ${fmt(x.paid)}` + (x.notes ? `\nملاحظات: ${x.notes}` : ""), x.what) },
        { label: "🗑 حذف", danger: true, fn: async () => { if (!(await confirmBox(`تحذف «${x.what}» بتاريخ ${x.date} بمبلغ ${fmt(x.paid)}؟\nالمبلغ هيرجع للخزنة.`, "حذف", "احذف"))) return;
          try { await api("delete_voucher", x.key); toast("✔ اتحذف", "ok"); closeModals(); statement(r); load(); } catch (e) { alertBox(e.message, "مينفعش يتحذف"); } } },
        { label: "✏️ تعديل (احذفه وسجّله من جديد)", disabled: true }] });
    M.setRows(d.rows);
    modal({ title: `كشف الموظف: ${d.name} (${d.kind}) — المرتب ${fmt(d.salary)}`, wide: true, enter: false, body: [h("div", { class: "card" }, M.el),
      h("div", { class: "chips", style: { padding: 0 } }, h("div", { class: "chip warn" }, "رصيد السلف الحالي: ", h("b", null, fmt(d.adv))), d.earned || d.cpaid ? [h("div", { class: "chip" }, "العمولة المستحقة: ", h("b", null, fmt(d.earned))),
        h("div", { class: "chip" }, "المصروف منها: ", h("b", null, fmt(d.cpaid))), h("div", { class: "chip info" }, "الباقي له: ", h("b", null, fmt(d.earned - d.cpaid)))] : null)], actions: [{ label: "قفل", ret: true }] });
  }
  async function workers(mode) {
    const d = dateIn(S.boot.today, "التاريخ"), list = h("div", { style: { display: "flex", flexDirection: "column", gap: "6px" } }), tot = h("b", { style: { color: "var(--navy)" } });
    const tons = h("input", { class: "in num", "aria-label": "الأطنان" }), bags = h("input", { class: "in num", "aria-label": "أو الشكاير" }), price = h("input", { class: "in num", "aria-label": "سعر الطن" }), notes = h("input", { class: "in", "aria-label": "ملاحظات" });
    let rows = [];
    const recalc = () => {
      if (mode === "load_add") { const t = num(tons.value), total = t * num(price.value), picked = rows.filter((r) => r.chk.checked); const each = picked.length ? total / picked.length : 0;
        rows.forEach((r) => (r.amt.value = r.chk.checked && total ? each.toFixed(2) : "")); tot.textContent = `التشوين = ${fmt(t)} طن × ${fmt(num(price.value))} = ${fmt(total)}` + (picked.length && total ? ` • لكل عامل ${fmt(each)}` : ""); }
      else tot.textContent = "الإجمالي: " + fmt(rows.filter((r) => r.chk.checked).reduce((a, r) => a + num(r.amt.value), 0));
    };
    async function fill() {
      let ws; try { ws = await api("workers", mode, d.value); } catch (e) { return toast(e.message, "err"); }
      rows = ws.map((w) => ({ ...w, chk: h("input", { type: "checkbox", checked: w.checked ? true : null, onchange: recalc }), amt: h("input", { class: "in num", value: w.amount || "", style: { maxWidth: "140px" }, oninput: recalc, readonly: mode === "load_add" ? true : null }) }));
      list.replaceChildren(...rows.map((r) => h("label", { class: "exp", style: { flexDirection: "row", alignItems: "center", gap: "10px", animation: "none" } }, r.chk, h("b", { style: { flex: 1 } }, r.name), h("span", { class: "hint" }, r.info), r.amt)));
      if (!rows.length) list.replaceChildren(h("div", { class: "empty" }, mode === "daily" ? "مفيش عمال شغالين" : "مفيش شيالين (عامل صفته فيها «شيال»)"));
      recalc();
    }
    bags.addEventListener("input", () => { const b = num(bags.value); tons.value = b ? (b / 20).toString() : ""; recalc(); }); [tons, price].forEach((x) => x.addEventListener("input", recalc)); d.addEventListener("change", fill);
    const title = { daily: "صرف يوميات العمال", load_pay: "صرف تشوين اليوم", load_add: "إضافة تشوين (نقلة)" }[mode];
    const extra = mode === "load_add" ? h("div", { class: "form", style: { padding: 0 } }, h("label", { class: "fld" }, "عدد الأطنان", tons), h("label", { class: "fld" }, "أو عدد الشكاير", bags), h("label", { class: "fld" }, "سعر الطن", price), h("label", { class: "fld span2" }, "ملاحظات (العربية / المورد …)", notes)) : null;
    fill();
    const ok = await modal({ title, wide: true, enter: false, body: [h("label", { class: "fld", style: { maxWidth: "220px" } }, "التاريخ", d), extra,
      h("div", { class: "hint" }, mode === "daily" ? "المعلّم = هيتصرفله. الغايب واللي اتصرفله قبل كده في نفس اليوم مش متعلّمين." : mode === "load_pay" ? "المبلغ = التشوين المتسجل للشيال في اليوم ده ولسه ماتصرفش." : "التشوين بيتقسم على الشيالين المعلّمين، وبيتصرف آخر اليوم من «صرف تشوين اليوم»."), list, tot],
      actions: [{ label: mode === "load_add" ? "تسجيل" : "صرف", cls: "primary", value: async () => {
        try { if (mode === "load_add") await api("add_loading", d.value, tons.value, price.value, rows.filter((r) => r.chk.checked).map((r) => r.id), notes.value);
          else await api("pay_workers", mode, d.value, rows.filter((r) => r.chk.checked).map((r) => [r.id, r.amt.value])); return true; } catch (e) { alertBox(e.message); return false; } } }, { label: "إلغاء", value: () => null }] });
    if (ok) { toast("✔ تم", "ok"); load(); }
    return fill;
  }
  const wk = (mode) => { const p = workers(mode); setTimeout(async () => { (await p); }, 0); };
  async function loadLog() {
    const from = dateIn(S.boot.today, "من"), to = dateIn(S.boot.today, "إلى");
    const M = selTable({ maxH: "50vh", cols: [{ h: "التاريخ", key: "date" }, { h: "الشيال", fn: (x) => h("b", null, x.name) }, { h: "طن", num: true, fn: (x) => fq(x.tons) }, { h: "سعر الطن", num: true, fn: (x) => fmt(x.price) },
      { h: "نصيبه", num: true, fn: (x) => fmt(x.amount) }, { h: "عدد الشيالين", num: true, key: "crew" }, { h: "الحالة", fn: (x) => (x.paid ? h("span", { class: "pill k-مبيعات" }, "اتصرف") : h("span", { class: "pill k-مرتجع" }, "مستني الصرف")) }, { h: "ملاحظات", key: "notes", cls: "hint" }],
      onOpen: (x) => editLoad(x), menu: (x) => [{ label: "✏️ تعديل", fn: () => editLoad(x) }],
      totals: (rs) => [totItem("الإجمالي", fmt(rs.reduce((a, x) => a + x.amount, 0))), totItem("اتصرف", fmt(rs.filter((x) => x.paid).reduce((a, x) => a + x.amount, 0))), totItem("مستني الصرف", fmt(rs.filter((x) => !x.paid).reduce((a, x) => a + x.amount, 0)), true)] });
    const fill = async () => { try { M.setRows(await api("loading_logs", from.value, to.value)); } catch (e) { toast(e.message, "err"); } };
    async function editLoad(x) {
      if (x.paid) return alertBox("السطر ده اتصرف خلاص. لو عايز تعدّله امسح صرفه من سجل السندات الأول.");
      const tons = h("input", { class: "in num", value: x.tons, inputmode: "decimal", "aria-label": "الأطنان" }), price = h("input", { class: "in num", value: x.price, inputmode: "decimal", "aria-label": "سعر الطن" });
      const amt = h("input", { class: "in num", value: x.amount, inputmode: "decimal", "aria-label": "نصيبه" }), notes = h("input", { class: "in", value: x.notes || "", "aria-label": "ملاحظات" });
      let manual = false; amt.addEventListener("input", () => (manual = true));
      const recalc = () => { if (!manual) amt.value = ((num(tons.value) * num(price.value)) / Math.max(1, x.crew || 1)).toFixed(2); };
      tons.addEventListener("input", recalc); price.addEventListener("input", recalc);
      const ok = await modal({ title: `تعديل تشوين ${x.name} — ${x.date}`, body: [h("label", { class: "fld" }, "الأطنان (أو الشكاير)", tons), h("label", { class: "fld" }, "سعر الطن", price),
          h("label", { class: "fld" }, `نصيبه (الإجمالي ÷ ${x.crew || 1} شيال) — تقدر تكتبه بإيدك`, amt), h("label", { class: "fld" }, "ملاحظات", notes)],
        actions: [{ label: "حفظ", cls: "primary", icon: "save", value: async () => { try { await api("update_loading", x.id, tons.value, price.value, amt.value, notes.value); return true; } catch (e) { alertBox(e.message); return false; } } }, { label: "إلغاء", value: () => null }] });
      if (ok) { toast("✔ اتعدّل", "ok"); fill(); }
    }
    [from, to].forEach((x) => x.addEventListener("change", fill));
    modal({ title: "سجل التشوين", wide: true, enter: false, body: [h("div", { style: { display: "flex", gap: "10px" } }, h("label", { class: "fld" }, "من", from), h("label", { class: "fld" }, "إلى", to)), h("div", { class: "card" }, M.el)],
      actions: [{ label: "✏️ تعديل السطر المحدد", value: async () => { const x = M.selected()[0]; if (!x) { toast("حدد سطر الأول"); return false; } await editLoad(x); return false; } },
        { label: "حذف السطر المحدد", cls: "danger", value: async () => { const x = M.selected()[0]; if (!x) { toast("حدد سطر الأول"); return false; } if (!(await confirmBox("تمسح النقلة دي؟"))) return false;
        try { await api("delete_loading", x.id); fill(); } catch (e) { alertBox(e.message); } return false; } }, { label: "قفل", ret: true }] });
    fill();
  }
  async function del() { const r = sel(); if (!r) return toast("حدد موظف الأول"); const pw = await askDelPw(`حذف «${r.name}»؟`); if (!pw) return; try { await api("delete_employee", r.id, pw); toast("✔ اتحذف", "ok"); load(); } catch (e) { alertBox(e.message, "مينفعش يتحذف"); } }
  async function toggle() { const r = sel(); if (!r) return toast("حدد موظف الأول");
    const msg = r.left ? `«${r.name}» رجع الشغل تاني؟` : `«${r.name}» ساب الشغل؟\nهيختفي من الحضور والمناديب، وسجله كله هيفضل زي ما هو.` + (r.adv ? `\n• عليه سلف لسه: ${fmt(r.adv)}` : "") + (r.is_rep && r.due ? `\n• ليه عمولة لسه: ${fmt(r.due)}` : "");
    if (!(await confirmBox(msg))) return; await api("toggle_employee", r.id); load(); }
  const bar = h("div", { class: "card-h" });
  function acts() {
    const r = sel();
    bar.replaceChildren(h("h2", null, "الموظفون"), h("button", { class: "btn primary", onclick: () => form(null) }, icon("plus", 18), "إضافة"),
      h("button", { class: "btn", onclick: one(form) }, icon("edit", 18), "تعديل"), h("button", { class: "btn gold", onclick: paySalary }, icon("cash", 18), r && r.kind === "عامل" ? "صرف يومية" : "صرف مرتب"),
      h("button", { class: "btn", onclick: payAdv }, "صرف سلفة"), !r || r.is_rep ? h("button", { class: "btn", onclick: payComm }, "صرف عمولة") : null,
      h("button", { class: "btn", onclick: () => wk("daily") }, "صرف يوميات العمال"),
      !r || r.loader ? [h("button", { class: "btn", onclick: () => wk("load_add") }, "➕ تشوين"), h("button", { class: "btn", onclick: () => wk("load_pay") }, "صرف تشوين اليوم"), h("button", { class: "btn", onclick: loadLog }, "سجل التشوين")] : null,
      h("button", { class: "btn", onclick: one(statement) }, icon("list", 18), "كشف الموظف"), h("button", { class: "btn", onclick: toggle }, r && r.left ? "رجع الشغل" : "ساب الشغل"),
      h("button", { class: "btn danger", onclick: del }, icon("trash", 18), "حذف"));
  }
  acts();
  box.replaceChildren(h("div", { class: "page" }, h("section", { class: "card anim-up d1", style: { padding: "12px 18px" } }, seg), h("section", { class: "card anim-up d2" }, bar, T.el)));
  await load();
}

/* ===================== الحضور ===================== */
async function renderAttendance(box) {
  const day = dateIn(S.attDay || S.boot.today, "التاريخ"), list = h("div", { class: "card" }), count = h("div", { class: "chips", style: { padding: 0 } });
  let rows = [];
  const lateOf = (r) => { if (!r.p.checked || !r.t.value) return 0; const [a, b] = r.t.value.split(":").map(Number), [c, d] = r.grace.split(":").map(Number); return Math.max(0, a * 60 + b - (c * 60 + d)); };
  function status(r) { const l = lateOf(r); r.st.textContent = !r.p.checked ? "غياب" : !r.t.value ? "حاضر" : l ? `متأخر ${l} د` : "في الميعاد ✔"; r.st.style.color = !r.p.checked ? "var(--red)" : l ? "var(--orange)" : "var(--green)"; counts(); }
  function counts() { const p = rows.filter((r) => r.p.checked).length, l = rows.filter((r) => lateOf(r)).length;
    count.replaceChildren(h("div", { class: "chip" }, "حاضر: ", h("b", null, p)), h("div", { class: "chip warn" }, "غياب: ", h("b", null, rows.length - p)), h("div", { class: "chip info" }, "متأخر: ", h("b", null, l))); }
  async function load() {
    S.attDay = day.value; let d; try { d = await api("attendance_day", day.value); } catch (e) { return toast(e.message, "err"); }
    rows = d.rows.map((e) => { const r = { ...e, p: h("input", { type: "checkbox", checked: e.present ? true : null, "aria-label": "حاضر" }), t: h("input", { class: "in", type: "time", value: e.check_in || "", style: { maxWidth: "150px" }, "aria-label": "ساعة الوصول" }),
      n: h("input", { class: "in", value: e.notes, placeholder: "ملاحظات", "aria-label": "ملاحظات" }), st: h("b") };
      r.p.addEventListener("change", () => status(r)); r.t.addEventListener("input", () => { if (r.t.value) r.p.checked = true; status(r); }); return r; });
    list.replaceChildren(h("div", { class: "tbl-wrap" }, h("table", { class: "t" }, h("thead", null, h("tr", null, ["حاضر", "الاسم", "النوع", "الميعاد", "ساعة الوصول", "الحالة", "ملاحظات"].map((x) => h("th", null, x)))),
      h("tbody", null, rows.map((r) => h("tr", null, h("td", null, r.p), h("td", null, h("b", null, r.name)), h("td", { class: "hint" }, r.kind + (r.job ? " — " + r.job : "")), h("td", { class: "hint" }, `${r.start} – ${r.grace}`), h("td", null, r.t), h("td", null, r.st), h("td", null, r.n)))))));
    rows.forEach(status);
    if (!d.saved) toast("لسه محدش اتسجل في اليوم ده", "", 2200);
  }
  async function save() {
    try { const r = await api("save_attendance", day.value, rows.map((r) => ({ id: r.id, name: r.name, present: r.p.checked, check_in: r.t.value, notes: r.n.value })));
      toast(`✔ اتحفظ حضور ${day.value}: حاضر ${r.present} • غياب ${r.absent} • متأخر ${r.late}`, "ok", 4000); } catch (e) { alertBox(e.message); }
  }
  day.addEventListener("change", load);
  box.replaceChildren(h("div", { class: "page" }, h("section", { class: "card anim-up d1", style: { padding: "12px 18px", display: "flex", flexWrap: "wrap", gap: "12px", alignItems: "flex-end" } },
    h("label", { class: "fld" }, "التاريخ", day), h("button", { class: "btn", onclick: () => { rows.forEach((r) => { r.p.checked = true; status(r); }); } }, icon("check", 18), "الكل حاضر"),
    h("button", { class: "btn primary", onclick: save }, icon("save", 18), "حفظ الحضور"), count), h("div", { class: "anim-up d2" }, list)));
  box._save = save;
  await load();
}
async function renderAttLog(box) {
  const A = S.alSt || (S.alSt = { from: monthStart(), to: S.boot.today, emp: "" });
  const from = dateIn(A.from, "من"), to = dateIn(A.to, "إلى"), emp = h("select", { class: "in", "aria-label": "الموظف" }, h("option", { value: "" }, "كل الموظفين"));
  const oneDay = dateIn(A.from === A.to ? A.from : "", "يوم معين");          // يوم واحد بس: بيظبط «من» و«إلى» على نفس اليوم
  oneDay.addEventListener("change", () => { if (!oneDay.value) return; from.value = to.value = oneDay.value; load(); });
  const Sm = selTable({ maxH: "30vh", cols: [{ h: "الموظف", fn: (r) => h("b", null, r.name) }, { h: "أيام الحضور", num: true, key: "pres" }, { h: "أيام الغياب", num: true, key: "abs" }, { h: "مرات التأخير", num: true, key: "late_n" }, { h: "إجمالي التأخير", key: "late_t" }],
    onOpen: (r) => { emp.value = String(r.id); load(); }, menu: (r) => [{ label: "👁 عرض تفاصيله", fn: () => { emp.value = String(r.id); load(); } }] });
  const D = selTable({ maxH: "40vh", cols: [{ h: "التاريخ", key: "date" }, { h: "اليوم", key: "day", cls: "hint" }, { h: "الموظف", fn: (r) => h("b", null, r.name) },
    { h: "الحالة", fn: (r) => h("span", { class: "pill " + (r.state === "غياب" ? "k-مرتجع" : r.state === "متأخر" ? "k-مشتريات" : "k-مبيعات") }, r.state) }, { h: "ساعة الوصول", key: "in" }, { h: "التأخير", key: "late" }, { h: "ملاحظات", key: "notes", cls: "hint" }],
    onKey: (e) => { if (e.key === "Delete") del(); },
    menu: (r) => [{ label: "👁 عرض", fn: () => alertBox(`${r.date} (${r.day})\n${r.name}\nالحالة: ${r.state}` + (r.in ? `\nساعة الوصول: ${r.in}` : "") + (r.notes ? `\nملاحظات: ${r.notes}` : ""), "حضور") },
      { label: "🗑 حذف", danger: true, fn: () => del() }, { label: "✏️ تعديل (يفتح حضور اليوم ده)", fn: () => { S.attDay = r.date; go("emp:att", true); } }],
    totals: (rs) => [totItem("حضور", rs.filter((r) => r.state !== "غياب").length), totItem("غياب", rs.filter((r) => r.state === "غياب").length), totItem("تأخير", rs.filter((r) => r.state === "متأخر").length)] });
  let first = true;
  async function load() { A.from = from.value; A.to = to.value; A.emp = emp.value; let r; try { r = await api("attendance_log", A.from, A.to, A.emp || null); } catch (e) { return toast(e.message, "err"); }
    if (first) { r.emps.forEach((e) => emp.appendChild(h("option", { value: e.id }, e.name))); emp.value = A.emp; first = false; } Sm.setRows(r.summary); D.setRows(r.rows); }
  async function del() { const r = D.selected()[0]; if (!r) return toast("حدد سطر الأول"); if (!(await confirmBox(`تحذف حضور «${r.name}» يوم ${r.date}؟`, "حذف", "احذف"))) return; await api("delete_attendance", r.id); load(); }
  [from, to, emp].forEach((x) => x.addEventListener("change", () => { oneDay.value = from.value === to.value ? from.value : ""; load(); }));
  box.replaceChildren(h("div", { class: "page" }, h("section", { class: "card anim-up d1" }, h("div", { class: "form" }, h("label", { class: "fld" }, "يوم معين", oneDay), h("label", { class: "fld" }, "من", from), h("label", { class: "fld" }, "إلى", to), h("label", { class: "fld" }, "الموظف", emp))),
    h("section", { class: "card anim-up d2" }, h("div", { class: "card-h" }, h("h2", null, "الملخص"), h("span", { class: "hint" }, "ضغطتين على موظف = تفاصيله بس")), Sm.el),
    h("section", { class: "card anim-up d3" }, h("div", { class: "card-h" }, h("h2", null, "التفاصيل"), h("button", { class: "btn danger", onclick: del }, icon("trash", 18), "حذف السطر")), D.el)));
  await load();
}
async function renderRequests(box, which) {
  const st = h("select", { class: "in", "aria-label": "الحالة" }, [["pending", "⏳ مستني موافقة"], ["approved", "✅ اتوافق"], ["rejected", "❌ اترفض"], ["all", "الكل"]].map(([v, l]) => h("option", { value: v }, l)));
  const cols = which === "att"
    ? [{ h: "رقم", key: "id", cls: "hint" }, { h: "المندوب", fn: (r) => h("b", null, r.rname || "") }, { h: "اليوم", key: "a_date" }, { h: "الساعة", key: "check_in" }, { h: "المسافة", fn: (r) => (r.dist != null ? Math.round(r.dist) + " م" : "—") },
       { h: "السبب", fn: (r) => r.reason || "", cls: "hint" }, { h: "الحالة", key: "status_text" }]
    : [{ h: "رقم", key: "id", cls: "hint" }, { h: "المندوب", fn: (r) => h("b", null, r.rname || "") }, { h: "العميل", key: "pname" }, { h: "المبلغ", num: true, fn: (r) => fmt(r.amount || 0) }, { h: "ملاحظات", fn: (r) => r.notes || "" , cls: "hint" }, { h: "الحالة", key: "status_text" }];
  const T = selTable({ cols });
  async function load() { try { T.setRows(await api("requests", which, st.value)); } catch (e) { toast(e.message, "err"); } }
  async function decide(ok) {
    const r = T.selected()[0]; if (!r) return toast("حدد طلب الأول");
    if (!(await confirmBox(which === "att" ? `${ok ? "توافق على" : "ترفض"} حضور «${r.rname}»؟` : ok ? `توافق على تحصيل ${fmt(r.amount)} ج.م من «${r.pname}»؟\nهيتعمل سند تحصيل بتاريخ النهارده.` : `ترفض طلب رقم ${r.id}؟`))) return;
    try { const x = await api("decide_request", which, r.id, ok); toast(x.text || "✔ تم", x.done ? "ok" : "err", 3500); load(); } catch (e) { alertBox(e.message); }
  }
  st.addEventListener("change", load);
  box.replaceChildren(h("div", { class: "page" }, h("section", { class: "card anim-up d1" }, h("div", { class: "card-h" }, h("h2", null, which === "att" ? "طلبات حضور المناديب (تليجرام)" : "طلبات تحصيل المناديب (تليجرام)"),
    h("label", { class: "fld", style: { flexDirection: "row", alignItems: "center" } }, "الحالة", st), h("button", { class: "btn primary", onclick: () => decide(true) }, icon("check", 18), "موافقة"),
    h("button", { class: "btn danger", onclick: () => decide(false) }, icon("x", 18), "رفض")), T.el),
    which === "att" && S.me.owner ? h("button", { class: "btn", style: { alignSelf: "flex-start" }, onclick: placeSettings }, icon("edit", 18), "مكان المخزن والمسافة") : null));
  await load();
}

/* ===================== العربيات ===================== */
async function renderVehicles(box) {
  const V = S.vehSt || (S.vehSt = { from: S.boot.today, to: S.boot.today, sel: null });
  const from = dateIn(V.from, "من"), to = dateIn(V.to, "إلى"), cards = h("div", { class: "kpis" }), logs = h("div");
  const fKind = h("select", { class: "in", "aria-label": "النوع" }), fDate = dateIn(S.boot.today, "التاريخ"), fOdo = h("input", { class: "in num", "aria-label": "العداد" }), fLit = h("input", { class: "in num", "aria-label": "لترات" }),
    fAmt = h("input", { class: "in num", "aria-label": "المبلغ" }), fNotes = h("input", { class: "in", "aria-label": "ملاحظات" });
  let data = { rows: [], kinds: [] };
  async function load() {
    V.from = from.value; V.to = to.value; try { data = await api("vehicles", V.from, V.to); } catch (e) { return toast(e.message, "err"); }
    if (!fKind.children.length) data.kinds.forEach((k) => fKind.appendChild(h("option", { value: k }, k)));
    if (!data.rows.some((v) => v.id === V.sel)) V.sel = data.rows[0] ? data.rows[0].id : null;
    cards.replaceChildren(...data.rows.map((v, i) => h("div", { class: "card kpi lift anim-up", style: { animationDelay: i * 0.05 + "s", cursor: "pointer", outline: v.id === V.sel ? "3px solid var(--gold)" : "" }, onclick: () => { V.sel = v.id; load(); } },
      h("div", { class: "h" }, h("span", { class: "ic", style: { background: "#e8effa", color: "#1e5aa8" } }, icon("truck", 20)), h("b", { style: { color: "var(--navy)", fontSize: "16px" } }, v.name), v.active ? null : h("span", { class: "pill k-مرتجع" }, "متوقفة")),
      h("div", { class: "s" }, [v.plate, v.driver].filter(Boolean).join(" • ") || " "), h("div", { class: "v" }, fmt(v.total)),
      h("div", { class: "s" }, `${fmt(v.km)} كم • ${fmt(v.liters)} لتر` + (v.km_per_l ? ` • ${fmt(v.km_per_l)} كم/لتر` : "") + (v.cost_km ? ` • ${fmt(v.cost_km)} ج/كم` : "")),
      h("div", { class: "s" }, v.last_odo != null ? `آخر عداد: ${fmt(v.last_odo)}` : ""))));
    if (!data.rows.length) cards.replaceChildren(h("div", { class: "card empty" }, "لسه مفيش عربيات — ضيف عربية"));
    const v = data.rows.find((x) => x.id === V.sel);
    const T = selTable({ maxH: "40vh", cols: [{ h: "التاريخ", key: "date" }, { h: "النوع", fn: (l) => h("b", null, l.kind) }, { h: "العداد", num: true, fn: (l) => (l.odo != null ? fmt(l.odo) : "") }, { h: "لترات", num: true, fn: (l) => numOrEmpty(l.liters) },
      { h: "المبلغ", num: true, fn: (l) => numOrEmpty(l.amount) }, { h: "ملاحظات", key: "notes", cls: "hint" }], onKey: async (e, l) => { if (e.key === "Delete") delLog(T); },
      totals: (rs) => [totItem("الحركات", rs.length), totItem("المصروفات", fmt(rs.reduce((a, l) => a + l.amount, 0)), true)] });
    T.setRows(v ? v.logs : []);
    logs.replaceChildren(h("section", { class: "card anim-up" }, h("div", { class: "card-h" }, h("h2", null, v ? `حركات ${v.name}` : "الحركات"), h("button", { class: "btn danger", onclick: () => delLog(T) }, icon("trash", 18), "حذف السطر")), T.el));
  }
  async function delLog(T) { const l = T.selected()[0]; if (!l) return toast("حدد سطر الأول"); if (!(await confirmBox("تحذف السطر ده؟" + (l.amount ? "\nوالمصروف المربوط بيه هيتحذف كمان ويرجع للخزنة." : ""), "حذف", "احذف"))) return;
    try { await api("delete_vehicle_log", l.id); load(); } catch (e) { alertBox(e.message); } }
  async function saveLog() {
    if (!V.sel) return toast("ضيف عربية الأول");
    const p = { vehicle_id: V.sel, date: fDate.value, kind: fKind.value, odo: fOdo.value, liters: fLit.value, amount: fAmt.value, notes: fNotes.value };
    try { let r = await api("save_vehicle_log", p, false); if (r.confirm) { if (!(await confirmBox(r.confirm, "قراءة العداد", "سجّلها"))) return; await api("save_vehicle_log", p, true); }
      toast(`✔ اتسجل: ${fKind.value}`, "ok"); [fOdo, fLit, fAmt, fNotes].forEach((x) => (x.value = "")); load(); } catch (e) { alertBox(e.message); }
  }
  async function vform(v) { v = v || { id: null, name: "", plate: "", driver: "", notes: "", active: true }; let ok = false;
    await formModal(v.id ? `تعديل «${v.name}»` : "عربية جديدة", [{ key: "name", label: "اسم العربية", value: v.name }, { key: "plate", label: "رقم اللوحة", value: v.plate }, { key: "driver", label: "السواق", value: v.driver },
      { key: "notes", label: "ملاحظات", value: v.notes, wide: true }, { key: "active", label: "الحالة", value: v.active ? "1" : "0", options: [{ value: "1", label: "شغالة" }, { value: "0", label: "متوقفة" }] }],
      { onSave: async (x) => { await api("save_vehicle", { ...x, id: v.id, active: x.active === "1" }); ok = true; } }); if (ok) load(); }
  async function delVeh() { const v = data.rows.find((x) => x.id === V.sel); if (!v) return; if (!(await confirmBox(`تحذف «${v.name}» وكل حركاتها؟\n(المصروفات المربوطة بيها هتتحذف وترجع للخزنة)`, "حذف عربية", "احذف"))) return;
    try { await api("delete_vehicle", v.id); V.sel = null; load(); } catch (e) { alertBox(e.message); } }
  [from, to].forEach((x) => x.addEventListener("change", load)); enterChain([fOdo, fLit, fAmt, fNotes], saveLog);
  box.replaceChildren(h("div", { class: "page" },
    h("section", { class: "card anim-up d1", style: { padding: "12px 18px", display: "flex", flexWrap: "wrap", gap: "10px", alignItems: "flex-end" } }, h("label", { class: "fld" }, "من", from), h("label", { class: "fld" }, "إلى", to),
      h("button", { class: "btn primary", onclick: () => vform(null) }, icon("plus", 18), "عربية جديدة"), h("button", { class: "btn", onclick: () => vform(data.rows.find((x) => x.id === V.sel)) }, icon("edit", 18), "تعديل العربية"),
      h("button", { class: "btn danger", onclick: delVeh }, icon("trash", 18), "حذف العربية")), cards,
    h("section", { class: "card anim-up d2" }, h("div", { class: "card-h" }, h("h2", null, "تسجيل للعربية المحددة")), h("div", { class: "form" }, h("label", { class: "fld" }, "النوع", fKind), h("label", { class: "fld" }, "التاريخ", fDate),
      h("label", { class: "fld" }, "العداد", fOdo), h("label", { class: "fld" }, "لترات", fLit), h("label", { class: "fld" }, "المبلغ", fAmt), h("label", { class: "fld span2" }, "ملاحظات", fNotes),
      h("div", { class: "fld", style: { justifyContent: "flex-end" } }, h("button", { class: "btn primary", onclick: saveLog }, icon("save", 18), "حفظ")))), logs));
  await load();
}

/* ===================== الإعدادات ===================== */
async function renderSettings(box) {
  const st = await api("settings_get");
  const inp = (v, label, extra = {}) => h("input", { class: "in", value: v ?? "", "aria-label": label, ...extra });
  const brandRO = st.brand_locked || !st.owner;   // الاسم والشعار مقفولين جوه النسخة (بيتغيروا بنسخة جديدة من المطور)
  const coName = inp(st.company, "اسم الشركة", brandRO ? { disabled: true } : {}), coTag = inp(st.tagline, "تحت الاسم", brandRO ? { disabled: true } : {});
  const logoImg = h("img", { src: S.boot.logo, alt: "الشعار", style: { height: "64px", width: "64px", objectFit: "contain", borderRadius: "12px", border: "1px solid var(--line-2)", background: "#fff" } });
  const logoFile = h("input", { type: "file", accept: "image/png,image/jpeg", style: { display: "none" }, onchange: () => {
    const f = logoFile.files[0]; if (!f) return; const rd = new FileReader();
    rd.onload = async () => { try { const uri = await api("set_logo", rd.result); S.boot.logo = uri; logoImg.src = uri; document.querySelectorAll(".brand img, .hero-in img").forEach((i) => (i.src = uri)); toast("✔ اتغيّر الشعار", "ok"); } catch (e) { alertBox(e.message); } logoFile.value = ""; };
    rd.readAsDataURL(f); } });
  const co = { company: coName, tagline: coTag, english: inp(st.english, "الاسم بالإنجليزي"), address: inp(st.address, "العنوان"), phone: inp(st.phone, "التليفون"), taxno: inp(st.taxno, "الرقم الضريبي"), owners_list: inp(st.owners_list, "أسماء الملاك") };
  const tr = { trust_from: inp(st.trust_from, "من (الاسم)"), trust_to: inp(st.trust_to, "إلى (الاسم)"), trust_to_addr: inp(st.trust_to_addr, "العنوان") };
  const lockD = h("input", { class: "in", type: "date", value: st.lock_until || "", "aria-label": "مقفول لحد" }), lockA = h("input", { type: "checkbox", checked: st.lock_auto ? true : null });
  const lockNow = h("b", { style: { color: "var(--navy)" } }, st.lock_now ? `🔒 مقفول لحد ${st.lock_now}` : "مفيش إقفال");
  const vals = (o) => Object.fromEntries(Object.entries(o).map(([k, el]) => [k, el.value]));
  const sec = (title, d, ...kids) => h("section", { class: "card anim-up " + d }, h("div", { class: "card-h" }, h("h2", null, title)), ...kids);
  box.replaceChildren(h("div", { class: "page", style: { maxWidth: "1000px" } },
    sec("بيانات الشركة", "d1", h("div", { class: "form" }, h("label", { class: "fld" }, "اسم الشركة", coName), h("label", { class: "fld" }, "تحت الاسم (مثلًا: للتوريدات العمومية)", coTag),
      st.brand_locked ? h("div", { class: "fld span2", style: { flexDirection: "row", alignItems: "center", gap: "12px" } }, logoImg,
        h("span", { class: "hint" }, "🔒 اسم الشركة والشعار مقفولين في النسخة دي — بيتغيروا بنسخة جديدة من المطور")) :
      st.owner ? h("div", { class: "fld span2", style: { flexDirection: "row", alignItems: "center", gap: "12px" } }, logoImg, logoFile,
        h("button", { class: "btn", type: "button", onclick: () => logoFile.click() }, icon("edit", 18), "تغيير الشعار"),
        h("button", { class: "btn ghost", type: "button", onclick: async () => { try { const uri = await api("set_logo", ""); S.boot.logo = uri; logoImg.src = uri; toast("✔ رجع الشعار العام", "ok"); } catch (e) { alertBox(e.message); } } }, "الشعار العام"),
        h("span", { class: "hint" }, "PNG أو JPG — بيظهر في البرنامج والطباعة")) : null,
      h("label", { class: "fld" }, "الاسم بالإنجليزي", co.english), h("label", { class: "fld span2" }, "العنوان", co.address), h("label", { class: "fld" }, "التليفون", co.phone), h("label", { class: "fld" }, "الرقم الضريبي", co.taxno), st.owner ? h("label", { class: "fld span2" }, "أسماء الملاك (للجرد — بينهم «،»)", co.owners_list) : null,
      h("div", { class: "fld", style: { justifyContent: "flex-end" } }, h("button", { class: "btn primary", onclick: async () => { try { await api("settings_save", vals(co)); if (!st.brand_locked) { S.boot.company = coName.value || S.boot.company; S.boot.tagline = coTag.value; } toast("✔ اتحفظت بيانات الشركة", "ok"); } catch (e) { alertBox(e.message); } } }, icon("save", 18), "حفظ")))),
    sec("بيانات إيصال الأمانة", "d2", h("div", { class: "form" }, h("label", { class: "fld" }, "من (الاسم)", tr.trust_from), h("label", { class: "fld" }, "إلى (الاسم)", tr.trust_to), h("label", { class: "fld span2" }, "العنوان", tr.trust_to_addr),
      h("div", { class: "fld", style: { justifyContent: "flex-end", flexDirection: "row", gap: "8px", alignItems: "flex-end" } },
        h("button", { class: "btn primary", onclick: async () => { try { await api("trust_save", vals(tr)); toast("✔ اتحفظ", "ok"); } catch (e) { alertBox(e.message); } } }, icon("save", 18), "حفظ"),
        h("button", { class: "btn gold", onclick: async () => { try { await api("print_trust_form"); toast("🖨 شاشة الطباعة هتفتح ...", "ok"); } catch (e) { toast(e.message, "err"); } } }, icon("print", 18), "طباعة")))),
    st.owner ? sec("إقفال الشهور 🔒", "d3", h("div", { class: "form" }, h("label", { class: "fld" }, "مقفول لحد (فاضي = مفتوح)", lockD), h("label", { class: "chk", style: { color: "var(--navy)" } }, lockA, "اقفل الشهر اللي فات أوتوماتيك أول كل شهر"),
      h("div", { class: "fld", style: { justifyContent: "center" } }, lockNow),
      h("div", { class: "fld", style: { justifyContent: "flex-end" } }, h("button", { class: "btn primary", onclick: async () => { try { const d = await api("lock_save", lockD.value, lockA.checked); lockNow.textContent = d ? `🔒 مقفول لحد ${d}` : "مفيش إقفال"; toast("✔ اتحفظ", "ok"); } catch (e) { alertBox(e.message); } } }, icon("save", 18), "حفظ"))),
      h("div", { class: "hint", style: { padding: "0 18px 14px" } }, "محدش يقدر يضيف أو يعدّل أو يحذف فواتير أو سندات بتاريخ في الفترة المقفولة.")) : null,
    sec("رصيد أول مدة الخزنة 🔒", "d4", h("div", { style: { padding: "14px 18px", display: "flex", flexWrap: "wrap", gap: "10px", alignItems: "center" } },
      h("span", null, "الرصيد الحالي: ", h("b", null, fmt(st.cash_opening))),
      h("button", { class: "btn", onclick: async () => {
        const v = await promptBox("رصيد أول المدة الجديد للخزنة:", "رصيد أول مدة الخزنة", { value: String(st.cash_opening) }); if (v === null) return;
        if (isNaN(num(v))) return toast("اكتب رقم صحيح", "err");
        const pw = await promptBox(`هيتغير رصيد أول مدة الخزنة من ${fmt(st.cash_opening)} لـ ${fmt(num(v))}\n\nاكتب كلمة سر المالك:`, "🔒 كلمة سر المالك", { password: true }); if (pw === null) return;
        try { await api("set_cash_opening", v, pw); toast("✔ اتغير رصيد أول المدة", "ok"); go("set:main", true); } catch (e) { alertBox(e.message); } } }, icon("edit", 18), "تغيير (بكلمة سر المالك)"),
      h("span", { class: "hint" }, "أي تغيير بيتسجل في سجل النشاط"))),
    sec("النسخ الاحتياطي", "d4", h("div", { style: { padding: "14px 18px", display: "flex", flexWrap: "wrap", gap: "10px", alignItems: "center" } },
      h("span", { class: "hint" }, "المكان: ", h("b", null, st.backup_dir)),
      h("button", { class: "btn primary", onclick: async (e) => { const b = e.currentTarget; b.disabled = true; try { await backupNow(); } finally { b.disabled = false; } } }, icon("save", 18), "نسخة احتياطية دلوقتي"),
      S.boot.web ? null : h("button", { class: "btn", onclick: () => api("open_backup_folder").catch((e) => toast(e.message, "err")) }, "افتح الفولدر"),
      st.owner && !S.boot.web ? h("button", { class: "btn", onclick: async () => { try { const d = await api("pick_file", "folder"); if (!d) return; await api("backup_dir_set", d); toast("✔ اتغير مكان النسخ", "ok"); go("set:main", true); } catch (e) { alertBox(e.message); } } }, "اختيار مكان تاني (فلاشة مثلًا)") : null,
      st.owner && !S.boot.web ? h("button", { class: "btn ghost", onclick: async () => { await api("backup_dir_set", ""); toast("✔ رجع لمجلد الجهاز", "ok"); go("set:main", true); } }, "الرجوع للافتراضي") : null)),
    sec("كلمة السر بتاعتي", "d5", h("div", { style: { padding: "14px 18px" } }, h("button", { class: "btn", onclick: () => changePw(null, S.me.username) }, icon("edit", 18), "غيّر كلمة السر"))),
    st.owner ? sec("📍 مكان المخزن (حضور المناديب بالموقع)", "d6", h("div", { style: { padding: "14px 18px", display: "flex", gap: "10px", flexWrap: "wrap", alignItems: "center" } },
      h("span", { class: "hint" }, "المندوب بيدوس «تسجيل حضور» من الموبايل: لو جوه المسافة دي من المخزن حضوره يتسجل على طول"), h("button", { class: "btn", onclick: placeSettings }, icon("edit", 18), "تظبيط المكان والمسافة"))) : null,
    st.owner && !S.boot.web ? sec("📥 الاستيراد من Excel", "d6", h("div", { style: { padding: "14px 18px", display: "flex", gap: "10px", flexWrap: "wrap", alignItems: "center" } },
      h("span", { class: "hint" }, "بياخد نسخة احتياطية قبل أي تغيير"), h("button", { class: "btn", onclick: () => importExcel("items") }, icon("box", 18), "استيراد أصناف"),
      h("button", { class: "btn", onclick: () => importExcel("parties") }, icon("users", 18), "استيراد عملاء وموردين"))) : null,
    st.owner && !S.boot.web ? sec("🌐 الموقع (الدخول من الموبايل والمتصفح)", "d6", webBox()) : null,
    st.owner && !S.boot.web ? sec("🌐 الشبكة وقاعدة البيانات", "d6", h("div", { style: { padding: "14px 18px", display: "flex", gap: "10px", flexWrap: "wrap", alignItems: "center" } },
      h("span", { class: "hint" }, `الداتا محفوظة: ${st.server} • ${st.version}`), h("button", { class: "btn", onclick: () => serverSettings(false) }, icon("edit", 18), "إعدادات الاتصال بالسيرفر"))) : null));
}
function webBox() {
  const box = h("div", { style: { padding: "14px 18px", display: "flex", flexDirection: "column", gap: "10px" } }, h("span", { class: "hint" }, "بيحمّل ..."));
  const draw = (w) => {
    const en = h("input", { type: "checkbox" }); en.checked = w.enabled;
    const port = h("input", { class: "in num", value: w.port, style: { maxWidth: "120px" }, "aria-label": "البورت" });
    box.replaceChildren(
      h("div", { style: { display: "flex", flexWrap: "wrap", gap: "12px", alignItems: "center" } }, h("label", { class: "chk" }, en, "شغّل الموقع من الجهاز ده"),
        h("label", { class: "fld", style: { flexDirection: "row", alignItems: "center", gap: "8px" } }, "البورت", port),
        h("button", { class: "btn primary", onclick: async () => { try { draw(await api("web_save", en.checked, port.value)); toast(en.checked ? "✔ الموقع شغال" : "✔ الموقع اتقفل", "ok"); } catch (e) { alertBox(e.message); } } }, icon("save", 18), "حفظ")),
      w.running ? h("div", { class: "chips", style: { padding: 0, flexWrap: "wrap" } }, h("div", { class: "chip info" }, `✔ شغال على البورت ${w.running} • داخلين دلوقتي: ${w.sessions}`),
        ...w.links.map((l) => h("div", { class: "chip" }, "من نفس الواي فاي: ", h("b", { dir: "ltr" }, l))),
        ...w.ts_links.map((l) => h("div", { class: "chip ok" }, "🌍 من أي مكان (Tailscale): ", h("b", { dir: "ltr" }, l)))) : h("span", { class: "hint" }, "الموقع مقفول"),
      w.running && !w.ts_links.length ? h("div", { class: "hint" }, "عشان يفتح من برة المخزن: سطّب Tailscale على الجهاز ده واعمل دخول، وبعدين اضغط حفظ تاني هنا وهيظهرلك لينك 🌍") : null,
      h("span", { class: "hint" }, "الجهاز ده لازم يفضل شغال والبرنامج مفتوح عشان الموقع يشتغل."));
  };
  api("web_get").then(draw).catch((e) => box.replaceChildren(h("span", { class: "hint" }, e.message)));
  return box;
}
async function changePw(uid, name) {
  const p1 = h("input", { class: "in", type: "password", "aria-label": "كلمة السر الجديدة" }), p2 = h("input", { class: "in", type: "password", "aria-label": "تأكيد كلمة السر" });
  const ok = await modal({ title: `كلمة سر «${name}»`, body: [h("label", { class: "fld" }, "كلمة السر الجديدة", p1), h("label", { class: "fld" }, "تأكيد كلمة السر", p2)],
    actions: [{ label: "حفظ", cls: "primary", value: async () => { try { await api("change_password", uid ?? S.me.id ?? 0, p1.value, p2.value); return true; } catch (e) { toast(e.message, "err"); return false; } } }, { label: "إلغاء", value: () => null }] });
  if (ok) toast("✔ اتغيرت كلمة السر", "ok");
}
// شاشة الصلاحيات: المالك بيعلّم على الشاشات اللي كل يوزر يفتحها
async function accessModal(u, setup) {
  const role = h("select", { class: "in", "aria-label": "الصلاحية" }, setup.roles.map((r) => h("option", { value: r }, r)));
  role.value = u ? u.role : "محاسب";
  const emp = h("select", { class: "in", "aria-label": "المندوب" }, h("option", { value: "" }, "— اختار المندوب —"), setup.reps.map((r) => h("option", { value: r.id }, r.name)));
  emp.value = u && u.emp_id ? String(u.emp_id) : "";
  const fEmp = h("label", { class: "fld" }, "المندوب (من الموظفين)", emp);
  const groups = [["الرئيسية", ["home"]], ["الفواتير", ["inv:مبيعات", "inv:مشتريات", "inv:مرتجع مبيعات", "inv:مرتجع مشتريات", "log"]], ["السندات", ["vch:new", "vch:log"]],
    ["العملاء والموردون", ["par:list"]], ["الأصناف والمخزون", ["itm:list", "itm:stock", "itm:sales", "itm:buys", "itm:damaged", "smp:items", "smp:out", "smp:in"]],
    ["الموظفون", ["emp:list", "emp:att", "emp:attlog", "emp:veh"]], ["الحسابات", ["acc:statement", "acc:balances", "acc:cash", "acc:subcash"]],
    ["التقارير", ["rep:daily", "rep:reps", "rep:targets", "rep:log"]], ["الإعدادات", ["set:main"]]];
  const chk = {};
  const cur = new Set(u ? u.screens : setup.defaults["محاسب"]);
  const grid = h("div", { class: "acc-grid" }, groups.map(([g, keys]) => h("div", { class: "acc-g" }, h("b", null, g),
    keys.map((k) => { const c = h("input", { type: "checkbox" }); c.checked = cur.has(k); chk[k] = c; return h("label", { class: "chk" }, c, SCREENS[k].title.replace(" 🔒", "")); }))));
  const preset = (r) => { const d = new Set(setup.defaults[r] || []); Object.entries(chk).forEach(([k, c]) => (c.checked = d.has(k))); };
  const lay = () => { const r = role.value; fEmp.style.display = r === "مندوب" ? "" : "none"; grid.style.display = r === "المالك" ? "none" : ""; };
  role.addEventListener("change", () => { preset(role.value); lay(); }); lay();
  const tools = h("div", { style: { display: "flex", gap: "8px", flexWrap: "wrap" } },
    h("button", { class: "btn ghost", type: "button", onclick: () => Object.values(chk).forEach((c) => (c.checked = true)) }, "علّم الكل"),
    h("button", { class: "btn ghost", type: "button", onclick: () => Object.values(chk).forEach((c) => (c.checked = false)) }, "شيل الكل"),
    h("button", { class: "btn ghost", type: "button", onclick: () => preset(role.value) }, "الافتراضي للصلاحية دي"));
  return { role, emp, fEmp, grid, tools, screens: () => Object.entries(chk).filter(([, c]) => c.checked).map(([k]) => k) };
}
async function renderUsers(box) {
  const setup = await api("access_setup");
  const T = selTable({ cols: [{ h: "المستخدم", fn: (r) => h("b", null, r.username) }, { h: "الصلاحية", fn: (r) => h("span", { class: "pill " + (r.role === "المالك" ? "k-مبيعات" : r.role === "مندوب" ? "k-مرتجع" : "k-مشتريات") }, r.role + (r.emp ? ` — ${r.emp}` : "")) },
    { h: "الشاشات", fn: (r) => (r.role === "المالك" ? "كل الشاشات" : `${r.screens.length} شاشة`), sort: (r) => r.screens.length },
    { h: "الحالة", fn: (r) => (r.active ? "✔ شغال" : h("span", { style: { color: "var(--red)" } }, "موقوف")) }, { h: "اتعمل في", key: "created", cls: "hint" }],
    onOpen: (r) => access(r),
    menu: (r) => [{ label: "🔑 الصلاحيات والشاشات", fn: () => access(r) }, { label: "✏️ تغيير كلمة السر", fn: () => changePw(r.id, r.username) }] });
  async function load() { try { T.setRows(await api("users")); } catch (e) { toast(e.message, "err"); } }
  const one = (fn) => async () => { const r = T.selected()[0]; if (!r) return toast("حدد مستخدم الأول"); try { await fn(r); } catch (e) { alertBox(e.message); } load(); };
  async function access(u) {
    const A = await accessModal(u, setup);
    const ok = await modal({ title: `صلاحيات «${u.username}»`, wide: true, body: [h("div", { class: "form", style: { padding: 0 } }, h("label", { class: "fld" }, "الصلاحية", A.role), A.fEmp),
      h("div", { class: "hint" }, "علّم على الشاشات اللي اليوزر ده يفتحها (من البرنامج ومن الموقع). المندوب بيشوف عملاءه وفواتيره وسنداته بس."), A.tools, A.grid],
      actions: [{ label: "حفظ", cls: "primary", value: async () => { try { await api("set_user_access", u.id, A.role.value, A.screens(), A.emp.value || null); return true; } catch (e) { toast(e.message, "err"); return false; } } }, { label: "إلغاء", value: () => null }] });
    if (ok) { toast("✔ اتحفظت الصلاحيات — بتسري على طول", "ok"); load(); }
  }
  async function add() {
    const n = h("input", { class: "in", "aria-label": "اسم المستخدم" }), p1 = h("input", { class: "in", type: "password", "aria-label": "كلمة السر" }), p2 = h("input", { class: "in", type: "password", "aria-label": "تأكيد كلمة السر" });
    const A = await accessModal(null, setup);
    const ok = await modal({ title: "مستخدم جديد", wide: true, body: [h("div", { class: "form", style: { padding: 0 } }, h("label", { class: "fld" }, "اسم المستخدم", n), h("label", { class: "fld" }, "كلمة السر", p1), h("label", { class: "fld" }, "تأكيد كلمة السر", p2),
        h("label", { class: "fld" }, "الصلاحية", A.role), A.fEmp), A.tools, A.grid],
      actions: [{ label: "إضافة", cls: "primary", value: async () => { try {
        await api("add_user", n.value, p1.value, p2.value, A.role.value, A.emp.value || null);
        if (A.role.value !== "المالك") { const us = await api("users"); const nu = us.find((x) => x.username === n.value.trim()); if (nu) await api("set_user_access", nu.id, A.role.value, A.screens(), A.emp.value || null); }
        return true; } catch (e) { toast(e.message, "err"); return false; } } }, { label: "إلغاء", value: () => null }] });
    if (ok) { toast("✔ اتضاف", "ok"); load(); }
  }
  box.replaceChildren(h("div", { class: "page", style: { maxWidth: "1000px" } }, h("section", { class: "card anim-up d1" }, h("div", { class: "card-h" }, h("h2", null, "المستخدمين"),
    h("button", { class: "btn primary", onclick: add }, icon("plus", 18), "إضافة"),
    h("button", { class: "btn gold", onclick: one((r) => access(r)) }, icon("users", 18), "الصلاحيات والشاشات"),
    h("button", { class: "btn", onclick: one((r) => changePw(r.id, r.username)) }, icon("edit", 18), "تغيير كلمة السر"),
    h("button", { class: "btn", onclick: one((r) => api("toggle_user", r.id)) }, "إيقاف / تفعيل"),
    h("button", { class: "btn danger", onclick: one(async (r) => { if (await confirmBox(`حذف المستخدم «${r.username}» نهائيًا؟ (سجل نشاطه هيفضل موجود)`, "حذف", "احذف")) await api("delete_user", r.id); }) }, icon("trash", 18), "حذف")), T.el)));
  await load();
}

/* ===================== الإعدادات المتقدمة ===================== */
async function importExcel(what) {
  const title = what === "items" ? "استيراد أصناف" : "استيراد عملاء وموردين";
  let path; try { path = await api("pick_file", "excel"); } catch (e) { return alertBox(e.message); }
  if (!path) return;
  let st; try { st = await api("import_start", what, path); } catch (e) { return alertBox(e.message, title); }
  const asof = await promptBox("الأرصدة اللي في الملف ده لحد أنهي يوم؟ (YYYY-MM-DD)\n\n• الفواتير والسندات اللي في البرنامج بتاريخ بعد اليوم ده هتتحسب فوق الأرصدة.\n• اللي بتاريخه أو قبله مش هتتحسب تاني.\n\nسيبها فاضية = الأرصدة دي هي أول المدة والفواتير كلها بتتحسب فوقها.", title, { value: st.found });
  if (asof === null) return;
  let pv; try { pv = await api("import_preview", what, path, asof); } catch (e) { return alertBox(e.message, title); }
  const choice = await modal({ title, enter: false, body: h("div", { class: "msg", style: { maxHeight: "55vh", overflow: "auto" } }, pv.msg),
    actions: [{ label: "استبدال (ياخد اللي في الملف بس)", cls: "danger", ret: "replace" }, { label: "إضافة وتحديث بس", cls: "primary", ret: "merge" }, { label: "إلغاء", value: () => null }] });
  if (!choice) return;
  try {
    let r = await api("import_run", choice === "replace", false);
    if (r.confirm) { if (!(await confirmBox(r.confirm, title, "كمّل"))) return; r = await api("import_run", choice === "replace", true); }
    alertBox(r.done, title); if (S.screen === "itm:list" || S.screen === "par:list") go(S.screen, true);
  } catch (e) { alertBox(e.message, title); }
}
async function placeSettings() {
  let p; try { p = await api("place_get"); } catch (e) { return alertBox(e.message); }
  let ok = false;
  await formModal("مكان المخزن", [{ key: "pos", label: "الإحداثيات (من خرائط جوجل: اضغط مطولًا على المكان وانسخ الرقمين — أو دوس «موقعي دلوقتي» وانت في المخزن)", value: p.pos, wide: true, ph: "30.123456, 31.234567" },
    { key: "radius", label: "المسافة المسموحة (متر)", value: p.radius, num: true }, { key: "auto", label: "اللي جوه المخزن حضوره يتسجل لوحده", value: p.auto ? "1" : "0", options: [{ value: "1", label: "أيوه" }, { value: "0", label: "لأ (يستنى موافقة)" }] }],
    { onSave: async (v) => { await api("place_save", v.pos, v.radius, v.auto === "1", false); ok = true; },
      onOpen: (m) => {
        const inp = m.querySelector("input"); if (!inp) return;
        const b = h("button", { class: "btn", type: "button", style: { marginTop: "6px" }, onclick: async () => {
          b.disabled = true; b.textContent = "بيجيب الموقع ...";
          try { const q = await getPos(); inp.value = q.latitude.toFixed(6) + ", " + q.longitude.toFixed(6); inp.dispatchEvent(new Event("input", { bubbles: true })); toast(`✔ اتحط موقعك (دقة ±${Math.round(q.accuracy)} م)`, "ok"); }
          catch (e) { alertBox(e && e.message === "insecure" ? "الموقع محتاج تفتح السيستم من لينك https (أو من البرنامج على جهاز فيه GPS)" : "ماعرفش يجيب الموقع — اسمح بإذن الموقع وشغّل الـ GPS"); }
          finally { b.disabled = false; b.textContent = "📍 موقعي دلوقتي"; } } }, "📍 موقعي دلوقتي");
        inp.closest("label").after(b);
      } });
  if (ok) toast("✔ اتحفظ مكان المخزن", "ok");
}
async function serverSettings(boot) {
  let c; try { c = await api(boot ? "server_settings_boot" : "server_get"); } catch (e) { return alertBox(e.message); }
  const mode = h("select", { class: "in", "aria-label": "الوضع" }, h("option", { value: "sqlite" }, "الجهاز ده بس (SQLite)"), h("option", { value: "postgres" }, "سيرفر على الشبكة (PostgreSQL)"));
  mode.value = c.mode;
  const f = { host: h("input", { class: "in", value: c.host, "aria-label": "عنوان الجهاز الأساسي", placeholder: "192.168.1.3" }), port: h("input", { class: "in num", value: c.port, "aria-label": "المنفذ" }),
    dbname: h("input", { class: "in", value: c.dbname, "aria-label": "اسم قاعدة البيانات" }), user: h("input", { class: "in", value: c.user, "aria-label": "المستخدم" }), password: h("input", { class: "in", type: "password", value: c.password, "aria-label": "كلمة السر" }) };
  const msg = h("div", { class: "msg", style: { fontWeight: 700 } });
  const pg = h("div", { class: "form", style: { padding: 0 } }, h("label", { class: "fld span2" }, "عنوان الجهاز الأساسي (IP)", f.host), h("label", { class: "fld" }, "المنفذ", f.port),
    h("label", { class: "fld" }, "اسم قاعدة البيانات", f.dbname), h("label", { class: "fld" }, "المستخدم", f.user), h("label", { class: "fld" }, "كلمة السر", f.password));
  const sync = () => { pg.style.display = mode.value === "postgres" ? "" : "none"; }; mode.addEventListener("change", sync); sync();
  const val = () => ({ mode: mode.value, ...Object.fromEntries(Object.entries(f).map(([k, el]) => [k, el.value])) });
  const done = await modal({ title: "الاتصال بالسيرفر", enter: false, body: [h("label", { class: "fld" }, "الداتا محفوظة فين", mode), pg, msg],
    actions: [{ label: "حفظ", cls: "primary", value: async () => {
      msg.textContent = "بيجهّز ...";
      try {
        if (boot) { await api("server_save_boot", val()); return true; }
        let r = await api("server_save", val(), null);
        if (r.ask_migrate) { const yes = await confirmBox(r.ask_migrate, "نقل الداتا للسيرفر", "انقلها"); msg.textContent = yes ? "بينقل الداتا — استنى شوية ..." : "";
          r = await api("server_save", val(), yes); }
        return !!r.ok;
      } catch (e) { msg.textContent = e.message; msg.style.color = "var(--red)"; return false; } } },
      { label: "اختبار الاتصال", value: async () => { msg.style.color = "var(--navy)"; msg.textContent = "بيجرّب ..."; try { msg.textContent = await api("server_test", val()); msg.style.color = "var(--green)"; } catch (e) { msg.textContent = e.message; msg.style.color = "var(--red)"; } return false; } },
      { label: "إلغاء", value: () => null }] });
  if (done) { toast("✔ اتحفظ — البرنامج هيفتح من جديد", "ok"); setTimeout(start, 900); }
}
async function onlineSettings() {
  let c; try { c = await api("online_get"); } catch (e) { return alertBox(e.message); }
  const B = (k, t) => { const el = h("input", { type: "checkbox", checked: c[k] ? true : null }); el.dataset.k = k; return h("label", { class: "chk", style: { color: "var(--text)", fontWeight: 600, minHeight: "34px" } }, el, t); };
  const T = (k, label, ph, extra = {}) => { const el = h("input", { class: "in", value: c[k] ?? "", placeholder: ph || "", style: { direction: "ltr", textAlign: "left" }, ...extra }); el.dataset.k = k; return h("label", { class: "fld" }, label, el); };
  const usersBox = h("div"), tgMsg = h("div", { class: "msg", style: { fontWeight: 700 } }), gsMsg = h("div", { class: "msg", style: { fontWeight: 700 } });
  const keyLbl = h("div", { class: "hint" }), keyEmail = h("input", { class: "in", readonly: true, value: c.gs_email || "", style: { direction: "ltr" }, "aria-label": "إيميل المفتاح" });
  const showKey = () => { keyLbl.textContent = c.gs_email ? "✔ ملف المفتاح متحط. شارك الشيت (Editor) مع الإيميل ده:" : "لسه مفيش ملف مفتاح Google (JSON)"; keyEmail.value = c.gs_email || ""; };
  const roleSel = (u, emps, reps) => {
    const sel = h("select", { class: "in", style: { maxWidth: "260px" } }, h("option", { value: "" }, "— اختار الصفة —"), h("option", { value: "manager" }, "مدير (تقارير وتنبيهات وموافقات)"),
      h("optgroup", { label: "محاسب" }, emps.map((e) => h("option", { value: "acct:" + e.id }, "محاسب: " + e.name))), h("optgroup", { label: "مندوب" }, reps.map((e) => h("option", { value: "rep:" + e.id }, "مندوب: " + e.name))),
      h("option", { value: "remove" }, "❌ إلغاء الربط"));
    sel.addEventListener("change", async () => { if (!sel.value) return; const [r, id] = sel.value.split(":");
      try { c.users = await api("tg_assign", u.cid, r, id ? +id : null); drawUsers(); toast("✔ تم", "ok"); } catch (e) { alertBox(e.message); } });
    return sel;
  };
  let lists = { emps: [], reps: [] };
  function drawUsers() {
    usersBox.replaceChildren(c.users.length ? h("div", { class: "tbl-wrap card" }, h("table", { class: "t" }, h("thead", null, h("tr", null, ["الاسم على تليجرام", "الصفة", "اسمه في البرنامج", "تغيير"].map((x) => h("th", null, x)))),
      h("tbody", null, c.users.map((u) => h("tr", null, h("td", null, h("b", null, u.name)), h("td", null, u.role), h("td", { class: "hint" }, u.emp), h("td", null, roleSel(u, lists.emps, lists.reps))))))) : h("div", { class: "hint" }, "لسه مفيش موبايل مربوط"));
  }
  drawUsers();
  const tok = T("tg_token", "توكن البوت (من @BotFather)", "123456:ABC...");
  const body = [
    h("div", { class: "card", style: { padding: "12px 16px", display: "flex", flexDirection: "column", gap: "6px" } }, B("enabled", "تشغيل المتابعة من الموبايل"), B("show_profit", "إظهار الأرباح في التقارير")),
    h("b", { style: { color: "var(--navy)", fontSize: "17px" } }, "Telegram"),
    h("div", { class: "hint" }, "1) من تليجرام كلّم @BotFather واعمل بوت جديد (/newbot) وانسخ التوكن هنا.  2) من الموبايل افتح البوت وابعتله /start.  3) دوس «ربط الموبايل» واختار صفته."),
    tok,
    h("div", { class: "bar-actions" }, h("button", { class: "btn primary", onclick: async () => { tgMsg.style.color = "var(--navy)"; tgMsg.textContent = "بيدوّر على رسالة /start ...";
      try { const r = await api("tg_find", tok.querySelector("input").value); lists = r; c.users = (await api("online_get")).users; drawUsers();
        tgMsg.style.color = "var(--green)"; tgMsg.textContent = r.pending.length ? `البوت @${r.bot} شغال ✔ — فيه ${r.pending.length} موبايل مستني ربط: اختار صفة كل واحد من الجدول.` : `البوت @${r.bot} شغال ✔ — بس لسه موصلتلوش رسالة جديدة. ابعتله رسالة من الموبايل واستنى 5 ثواني ودوس تاني.`;
      } catch (e) { tgMsg.style.color = "var(--red)"; tgMsg.textContent = e.message; } } }, icon("phone", 18), "ربط الموبايل"),
      h("button", { class: "btn", onclick: async () => { try { await api("tg_test"); tgMsg.style.color = "var(--green)"; tgMsg.textContent = "✔ الرسالة اتبعتت"; } catch (e) { tgMsg.style.color = "var(--red)"; tgMsg.textContent = e.message; } } }, "رسالة تجربة"),
      h("button", { class: "btn danger", onclick: async () => { if (!(await confirmBox("تلغي ربط كل الموبايلات (المديرين والمناديب)؟"))) return; await api("tg_unlink_all"); c.users = []; drawUsers(); } }, "إلغاء ربط الكل")),
    tgMsg, c.status_tg ? h("div", { class: "hint" }, c.status_tg) : null, usersBox,
    h("div", { class: "form", style: { padding: 0 } }, B("tg_daily", "تقرير آخر اليوم"), T("tg_time", "ساعة التقرير (مثال 21:00)", "21:00"), B("tg_commands", "البوت يرد على الأسئلة (اليوم، امبارح، خزنة، حضور، طلبات، شيت)")),
    h("b", { style: { color: "var(--navy)" } }, "التنبيهات الفورية"),
    h("div", { class: "form", style: { padding: 0 } }, B("al_low", "صنف وصل للحد الأدنى"), B("al_returns", "مرتجع مبيعات أو مشتريات"), B("al_sensitive", "جرد الخزنة والحذف وتغيير المستخدمين"),
      B("al_credit", "عميل عدّى الحد الائتماني"), B("al_attendance", "ملخص الحضور أول ما يتسجل"), B("al_expected", "الصبح: العملاء المتوقع يطلبوا النهارده"), T("al_big", "تنبيه لفاتورة مبيعات أكبر من (0 = لأ)", "0")),
    h("b", { style: { color: "var(--navy)", fontSize: "17px" } }, "Google Sheets"),
    B("gs_enabled", "تحديث شيت Google تلقائي (الأصناف، العملاء والموردين، فواتير وسندات آخر 30 يوم)"), keyLbl, keyEmail,
    h("div", { class: "bar-actions" }, h("button", { class: "btn", onclick: async () => { try { const p = await api("pick_file", "json"); if (!p) return; const r = await api("gs_set_key", p); c.gs_key = r.gs_key; c.gs_email = r.gs_email; showKey(); } catch (e) { gsMsg.style.color = "var(--red)"; gsMsg.textContent = e.message; } } }, "اختيار ملف المفتاح (JSON)"),
      h("button", { class: "btn", onclick: () => { try { navigator.clipboard.writeText(keyEmail.value); gsMsg.textContent = "✔ الإيميل اتنسخ"; } catch (e) { keyEmail.select(); } } }, "نسخ الإيميل")),
    T("gs_sheet", "لينك الشيت (من المتصفح)", "https://docs.google.com/spreadsheets/d/..."), T("gs_every", "التحديث كل كام دقيقة", "10"),
    h("div", { class: "bar-actions" }, h("button", { class: "btn", onclick: async () => { gsMsg.style.color = "var(--navy)"; gsMsg.textContent = "بيحدّث الشيت ..."; try { await save(false); gsMsg.textContent = await api("gs_sync_now"); gsMsg.style.color = "var(--green)"; } catch (e) { gsMsg.style.color = "var(--red)"; gsMsg.textContent = e.message; } } }, "تحديث الشيت دلوقتي")),
    gsMsg, c.status_gs ? h("div", { class: "hint" }, c.status_gs) : null];
  showKey();
  const wrapBox = h("div", { style: { display: "flex", flexDirection: "column", gap: "10px" } }, body);
  async function save(close = true) {
    const v = { gs_key: c.gs_key };
    wrapBox.querySelectorAll("[data-k]").forEach((el) => { v[el.dataset.k] = el.type === "checkbox" ? el.checked : el.value; });
    await api("online_save", v); if (close) toast("✔ اتحفظت إعدادات الموبايل", "ok");
  }
  modal({ title: "📱 المتابعة من الموبايل — Telegram و Google Sheets", wide: true, enter: false, body: wrapBox,
    actions: [{ label: "حفظ", cls: "primary", value: async () => { try { await save(); return true; } catch (e) { alertBox(e.message); return false; } } }, { label: "قفل", ret: true }] });
}

/* ===================== اختصارات الكيبورد ===================== */
document.addEventListener("keydown", (e) => {
  if (!S.me || MODALS) return;
  const k = e.key;
  if (k === "F1") { e.preventDefault(); go("inv:مبيعات"); }
  else if (k === "F2") { e.preventDefault(); go("inv:مشتريات"); }
  else if (k === "F3") { e.preventDefault(); go("log"); }
  else if (k === "F6") { e.preventDefault(); S.voucherEdit = null; go("vch:new", S.screen === "vch:new"); }
  else if (k === "F7") { e.preventDefault(); go("vch:log"); }
  else if ((e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey && (e.code === "KeyB")) { e.preventDefault(); go("acc:balances"); }
  else if ((e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey && (e.code === "KeyI")) { e.preventDefault(); go("itm:stock"); }
  else if (k === "Escape" && $("#drawer") && $("#drawer").classList.contains("on")) closeDrawer();
  else if ((e.ctrlKey || e.metaKey) && (k === "s" || k === "س") && (S.screen.startsWith("inv:") || S.screen === "vch:new")) { e.preventDefault(); const b = $("#screen"); if (b._save) b._save(false); }
});
window.addEventListener("beforeunload", (e) => { if (S.dirty) { e.preventDefault(); e.returnValue = ""; } });

start();
