# تعليمات المشروع الدائمة / Standing Project Instructions

المشروع: **محلل متطلبات الأعمال الذكي / Smart Business Requirements Analyst**.
مجلد التطبيق `presales_codex_ready/business_analyst`.

## 1. ثنائية اللغة إلزامية / Bilingual is mandatory

كل ما يُبنى في هذا النظام يجب أن يكون **عربي + إنجليزي**:

- **واجهة المستخدم**: كل نص ظاهر يمر عبر `utils/i18n.py` (`t("key")`).
  ممنوع كتابة نص واجهة مباشرةً في ملفات `views/` أو `app.py`.
- **مخرجات النموذج**: تتبع `output_language` (عربي / إنجليزي / كليهما).
- **المستندات المصدَّرة**: Word و PDF يتبعان اتجاه الكتابة الصحيح لكل لغة.

Every user-facing string must exist in both `ar` and `en` in `UI_STRINGS`.

## 2. عدّل الموجود ولا تكرّر / Extend, don't duplicate

عند وصول متطلب جديد يضيف إلى خاصية قائمة: **عدّل الخاصية الموجودة**.
لا تُنشئ نسخة ثانية منها. مثال: توسيع مخطط جدول الكميات عدّل `BOQ_SCHEMA`
القائم ولم يُنشئ مخططاً موازياً.

When a new requirement extends an existing capability, modify it in place.

## 3. تقرير الإنجاز / Completion report

عند إنهاء أي مهمة: نقاط مختصرة وواضحة — **ماذا تم** و**ماذا أُصلح** — بلا شرح
مطوّل.

وعند وجود Pull Request: أخبر المستخدم **دائماً** هل تمّ الدمج، وهل يمكنه حذف
الفرع — بسطر واحد.

## 3.1 لا مراقبة دائمة بلا طلب / No standing PR watch

مراقبة الـ PR والتذكيرات المجدولة تستهلك توكناً في كل استيقاظ. **لا تبدأها من
تلقائك**: افحص الحالة مرة وأبلغ، واسأل قبل تشغيل أي مراقبة أو جدولة. وأوقفها
فور انتهاء الحاجة.

PR watching and scheduled check-ins burn tokens on every wake. Never start them
unprompted — check once, report, and ask before subscribing or scheduling.
Stop them as soon as the need ends.

Finish with short bullets: what was done, what was fixed. No long prose.
When a PR is involved, always state whether it merged and whether the branch
is safe to delete — one line.

## 4. تحديث ملف README / Keep README current

حدّث `README.md` بآخر التغييرات مع كل دفعة إلى GitHub — بما فيه عدد الاختبارات.

## 5. لغة المحادثة / Chat language

الردود على المستخدم بالإنجليزية.

---

## ملاحظات تقنية / Technical notes

- التشغيل والتحقق يتمّان عبر GitHub Actions — لا يُشترط تشغيل محلي.
- ملفات Replit موجودة لكنها خاملة حتى نقل المشروع لاحقاً.
- قاعدة البيانات `presales_codex_ready/business_analyst/data/analyst.db` مُستثناة من git،
  ومسارها قابل للتغيير بمتغيّر البيئة `ANALYST_DB_PATH`.

### قواعد ثابتة في المنتج / Fixed product rules

هذه ليست تفضيلات تصميم بل قيود تُفقد المنافسة إن كُسرت:

- **الفني والمالي مظروفان منفصلان** — لا رقم سعري في العرض الفني. الهيكل
  يحذّر، والوكيل التجاري يسجّلها ملاحظة حرجة.
- **حالة الامتثال وترشيح القائمة الإلزامية قراران بشريان** — النموذج يقترح
  الاستراتيجية ولا يفترض الالتزام.
- **الجاهزية الإجمالية = أضعف زاوية لا المتوسط** — زاوية ساقطة واحدة تكفي
  لرفض العرض.
- **فشل استدعاء النموذج لا يمسح نص المستخدم** — لا كتابة إلا عند نجاح الاستدعاء.
