# سيستم المخازن والمبيعات — النسخة الأوفلاين (Warehouse)

النسخة دي هي **نفس كود «زلط»** (repo `alielmenshawy26-hash/Zalat_system`، نسخة V2.1.60) بعد ما اتعملها هوية منفصلة،
علشان تتباع / تتسطّب لعملاء تانيين وتشتغل من غير نت. أي تطوير للعملاء التانيين بيتعمل هنا، وزلط ليه الـ repo بتاعه.

## الملفات
| الملف | شغلته |
|---|---|
| `Warehouse_app.py` | المحرك: قاعدة البيانات (SQLite أو PostgreSQL)، الحسابات، FIFO، الطباعة (HTML → PDF)، النسخ الاحتياطي. فيه كمان واجهة Tkinter القديمة (مش مستخدمة في البرنامج الجديد). |
| `zalat_ui.py` | البرنامج نفسه: `Api` (كل دوال الشاشات)، الصلاحيات (`ALL_SCREENS`/`OWNER_ONLY_SCREENS`/`DEFAULT_SCREENS`/`METHOD_SCREENS`)، `_guard`/`_scope`، سيرفر الموقع، و`main()` (pywebview). |
| `ui/` | الواجهة: `index.html`، `app.js` (كل الشاشات)، `app.css`، `fonts/` (خط Cairo جوه البرنامج — مفيش جوجل)، `icons/`، `sw.js`، `manifest.webmanifest`. |
| `installer.iss` | Inno Setup: `Warehouse-Setup-<slug>.exe`، الـ AppId نفس warehouseDesktop القديم (بيحدّث فوقه). |
| `clients/<slug>/` | عميل: `client.json` (`company`، `tagline`) + `logo.png`. كل فولدر = Setup لوحده. |
| `tools/make_brand.py` | بيعمل `client_brand.py` (اسم + تحت الاسم + شعار base64) لعميل قبل الـ build. الملف ده متجاهل في git. |
| `.github/workflows/build.yml` | مع كل push على main: Setup لكل عميل في `clients/` + Release `V1.0.N` فيه كلهم. |

لينك التحميل: `https://github.com/alielmenshawy26-hash/warehouseDesktop/releases/latest/download/Warehouse-Setup-<slug>.exe`
(`Warehouse-Setup.exe` القديم = نسخة فرحات علشان التحديث القديم يفضل شغال).

## الاسم والشعار مقفولين (علشان محدش ياخد البرنامج ويبيعه)
- كل عميل ليه build: `W.BRAND_COMPANY` / `BRAND_TAGLINE` / `BRAND_LOGO_B64` من `client_brand.py`. من غيره = «نسخة تجريبية» بالشعار العام.
- `init_db` بيكتب الاسم وتحت الاسم بتوع النسخة في `settings` كل مرة، و`logo_bytes()` بيرجع شعار النسخة دايمًا.
- `settings_save` مبيغيّرش الاسم، و`set_logo` بيرفض (`W.BRAND_LOCKED`)، والإعدادات بتعرضهم مقفولين.
- عميل جديد = فولدر في `clients/` + push. تغيير اسم/شعار عميل = تعديل الفولدر بتاعه + push (نسخة جديدة).
- تجربة محلية لعميل: `python tools/make_brand.py farahat` وبعدين `python zalat_ui.py --serve` (امسح `client_brand.py` بعدها).

## الفرق عن زلط
- مجلد الداتا: `%LOCALAPPDATA%\WarehouseDesktop` (نفس البرنامج الأوفلاين القديم → داتا العملاء القدام بتكمّل وبتتحدّث لوحدها في `init_db`). زلط بيستخدم `WarehouseOnline`.
- اسم الشركة و«تحت الاسم» والشعار **مقفولين جوه كل نسخة** (`clients/<slug>/`) — مش بيتغيروا من الإعدادات.
- رقم النسخة `V1.0.N` (زلط `V2.1.N`). اسم البرنامج `Warehouse.exe`.
- الخط محلي (`ui/fonts/cairo.css`) — البرنامج شغال 100% من غير نت.
- الموقع (للموبايل) موجود بس **مقفول افتراضيًا** (الإعدادات ← 🌐 الموقع).
- مفيش تليجرام ولا جوجل شيت (اتشالوا من زلط).

## إزاي بيشتغل
- الديسكتوب: pywebview بيفتح `ui/index.html`، وJS بيكلم بايثون عن طريق `window.pywebview.api.call(name, args)` → `call_api` → `Api.<name>`.
  الموقع: نفس الـ `Api` عن طريق `POST /api` (سيرفر `make_handler`، كوكي `zs`). `ui/web.js` بيتبعت من السيرفر بس (علامة إن ده الموقع).
- أي دالة جديدة في `Api` لازم تتضاف في `METHOD_SCREENS` (للشاشة اللي بتستخدمها) وإلا هترجع «مش مسموحلك».
- الأدوار: المالك (كل حاجة) / محاسب (كل حاجة إلا الأرباح والمستخدمين والأصول والتقرير الشهري) / مندوب (فواتيره وسنداته كطلبات + حضور).
- إقفال اليوم: `W.check_day` + `__DAYLOCK__` → JS بيطلب باسوورد المحاسب/المالك.
- الحذف في العملاء/الموظفين/الأصناف بيطلب باسوورد المحاسب/المالك (`_del_pw`).

## التجربة قبل أي push
- تشغيل محلي من غير ويندوز: `python zalat_ui.py --serve` (المتصفح على 127.0.0.1:8765، وضع تطوير) أو `--web 8780`.
- اتأكد إن `python -m py_compile Warehouse_app.py zalat_ui.py` و`node --check ui/app.js` نضاف.
- اختبار بالـ Playwright: ادخل كل الشاشات ودوس كل زرار (مالك + محاسب + مندوب على مقاس موبايل) واتأكد مفيش أخطاء JS.

## طريقة الشغل مع المستخدم (Omar)
- الرد بالمصري، خطوة خطوة.
- بيكتب عربي على كيبورد إنجليزي أحيانًا (مثلًا "hfuj" = «ابعت»، ";]i" = «كده»).
- اعمل commit محلي، وارفع (push) وابني **بس لما يقول «ابعت»**.
