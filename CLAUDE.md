# تعليمات المشروع الدائمة / Standing Project Instructions

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

Finish with short bullets: what was done, what was fixed. No long prose.

## 4. تحديث ملف README / Keep README current

حدّث `README.md` بآخر التغييرات مع كل دفعة إلى GitHub.

## 5. لغة المحادثة / Chat language

الردود على المستخدم بالإنجليزية.

---

## ملاحظات تقنية / Technical notes

- التشغيل والتحقق يتمّان عبر GitHub Actions — لا يُشترط تشغيل محلي.
- ملفات Replit موجودة لكنها خاملة حتى نقل المشروع لاحقاً.
- قاعدة البيانات `presales_codex_ready/business_analyst/data/analyst.db` مُستثناة من git.
