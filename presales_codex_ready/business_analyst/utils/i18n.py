"""
utils/i18n.py — نصوص الواجهة بالعربية والإنجليزية / Bilingual UI strings.

كل نص ظاهر للمستخدم يمر من هنا عبر ``t("key")``. لغة الواجهة مستقلة عن لغة
مخرجات النموذج (``output_language``): قد يعمل المستخدم بواجهة إنجليزية بينما
يولّد عرضاً عربياً.

الأوضاع الثلاثة: ``ar`` · ``en`` · ``both`` (يعرض النصّين معاً بفاصل).

Every user-facing string goes through ``t("key")``. UI language is separate
from model output language.
"""
import streamlit as st

UI_LANGUAGES = {
    "ar": "العربية",
    "en": "English",
    "both": "العربية / English",
}
DEFAULT_UI_LANGUAGE = "ar"

# فاصل وضع اللغتين معاً
BOTH_SEPARATOR = " / "


def ui_language() -> str:
    lang = st.session_state.get("ui_language", DEFAULT_UI_LANGUAGE)
    return lang if lang in UI_LANGUAGES else DEFAULT_UI_LANGUAGE


def ui_is_rtl() -> bool:
    """الواجهة من اليمين لليسار ما لم تكن إنجليزية خالصة."""
    return ui_language() != "en"


def t(key: str, **fmt) -> str:
    """
    نص الواجهة حسب اللغة المختارة.

    مفتاح غير معرّف يعود كما هو بدل الانهيار — يظهر خاماً في الواجهة فيسهل
    رصده، ويحرسه اختبار يتحقق من اكتمال المفاتيح.
    """
    entry = UI_STRINGS.get(key)
    if entry is None:
        return key

    lang = ui_language()
    if lang == "both":
        ar, en = entry.get("ar", ""), entry.get("en", "")
        text = f"{ar}{BOTH_SEPARATOR}{en}" if ar and en else (ar or en)
    else:
        text = entry.get(lang) or entry.get("ar") or entry.get("en") or key

    return text.format(**fmt) if fmt else text


# ─── النصوص / Strings ─────────────────────────────────────────────────────────

UI_STRINGS: dict[str, dict[str, str]] = {
    # ── التنقل / Navigation ──
    "nav.dashboard": {"ar": "لوحة التحكم", "en": "Dashboard"},
    "nav.tenders": {"ar": "المنافسات", "en": "Tenders"},
    "nav.workspace": {"ar": "مساحة العمل", "en": "Workspace"},
    "nav.company": {"ar": "ملف الشركة", "en": "Company Profile"},
    "nav.settings": {"ar": "إعدادات النظام", "en": "Settings"},
    "nav.data": {"ar": "إدارة البيانات", "en": "Data Management"},

    # ── عام / Common ──
    "common.engine": {"ar": "المحرك:", "en": "Model:"},
    "common.generate": {"ar": "توليد", "en": "Generate"},
    "common.save_now": {"ar": "حفظ الآن", "en": "Save now"},
    "common.close": {"ar": "إغلاق", "en": "Close"},
    "common.open": {"ar": "فتح", "en": "Open"},
    "common.copy": {"ar": "نسخ", "en": "Duplicate"},
    "common.delete": {"ar": "حذف", "en": "Delete"},
    "common.confirm": {"ar": "تأكيد؟", "en": "Confirm?"},
    "common.reset": {"ar": "إعادة ضبط", "en": "Reset"},
    "common.clear": {"ar": "مسح", "en": "Clear"},
    "common.default": {"ar": "الافتراضي", "en": "Default"},
    "common.undo": {"ar": "تراجع", "en": "Undo"},
    "common.none": {"ar": "—", "en": "—"},
    "common.not_set": {"ar": "غير محددة", "en": "Not set"},
    "common.generating": {"ar": "جاري التوليد...", "en": "Generating..."},
    "common.extracting": {"ar": "جاري الاستخراج...", "en": "Extracting..."},
    "common.your_notes": {
        "ar": "✍️ ملاحظاتك / التعديلات المعتمدة:",
        "en": "✍️ Your notes / approved edits:",
    },

    # ── الشريط الجانبي / Sidebar ──
    "side.brand": {
        "ar": "محلل متطلبات الأعمال الذكي",
        "en": "Smart Business Requirements Analyst",
    },
    "side.tagline": {"ar": "إدارة العطاءات", "en": "Enterprise Bid Management"},
    "side.tender": {"ar": "المنافسة", "en": "Tender"},
    "side.tender_none": {
        "ar": "لم تُفتح — العمل غير محفوظ",
        "en": "None open — work is not saved",
    },
    "side.api_connected": {"ar": "متصل", "en": "Connected"},
    "side.api_missing": {"ar": "غير مُهيأ", "en": "Not configured"},
    "side.company": {"ar": "الشركة", "en": "Company"},
    "side.rfp": {"ar": "كراسة الشروط", "en": "Tender documents"},
    "side.rfp_loaded": {"ar": "محمّلة", "en": "Loaded"},
    "side.rfp_missing": {"ar": "لم تُحمَّل بعد", "en": "Not loaded"},
    "side.tokens": {"ar": "التوكنز:", "en": "Tokens:"},

    # ── لوحة التحكم / Dashboard ──
    "dash.title": {"ar": "لوحة التحكم", "en": "Dashboard"},
    "dash.welcome": {
        "ar": "مرحباً بك في **محلل متطلبات الأعمال الذكي** لتحليل كراسات الشروط وبناء العروض الفنية.",
        "en": "Welcome to the **Smart Business Requirements Analyst** — tender analysis and technical proposal drafting.",
    },
    "dash.company_name": {"ar": "اسم الشركة", "en": "Company"},
    "dash.sections_done": {"ar": "الأقسام المكتملة", "en": "Sections drafted"},
    "dash.workflow": {"ar": "🗺️ خطوات سير العمل", "en": "🗺️ Workflow"},
    "dash.capabilities": {"ar": "✨ قدرات المنصة", "en": "✨ Capabilities"},
    "dash.tokens_unit": {"ar": "توكن", "en": "tokens"},
    "dash.not_loaded": {"ar": "لم تُحمَّل", "en": "Not loaded"},
    "dash.step1": {"ar": "⚙️ الإعدادات", "en": "⚙️ Settings"},
    "dash.step1d": {
        "ar": "أدخل مفتاح Gemini API وبيانات الشركة.",
        "en": "Add your Gemini API key and company details.",
    },
    "dash.step2": {"ar": "📥 رفع المرفقات", "en": "📥 Upload attachments"},
    "dash.step2d": {
        "ar": "ارفع مرفقات المنافسة وصنّفها (مع OCR).",
        "en": "Upload and classify tender attachments (with OCR).",
    },
    "dash.step3": {"ar": "🤖 التحليل الذكي", "en": "🤖 AI analysis"},
    "dash.step3d": {
        "ar": "سياق المشروع · Go/No-Go · الأوزان · الكميات.",
        "en": "Project context · Go/No-Go · weights · BOQ.",
    },
    "dash.step4": {"ar": "📄 بناء العرض", "en": "📄 Draft proposal"},
    "dash.step4d": {
        "ar": "اقترح الهيكل وصُغ كل قسم من الكراسة.",
        "en": "Propose the outline and draft each section.",
    },
    "dash.step5": {"ar": "🔍 المراجعة والتسليم", "en": "🔍 Review & deliver"},
    "dash.step5d": {
        "ar": "راجع من ثلاث زوايا وصدّر Word أو PDF.",
        "en": "Three-lens review, then export Word or PDF.",
    },
    "dash.cap1": {"ar": "🤖 تحليل ذكي شامل", "en": "🤖 Full AI analysis"},
    "dash.cap1d": {
        "ar": "Go/No-Go · مصفوفة التقييم · فجوات الامتثال",
        "en": "Go/No-Go · evaluation matrix · compliance gaps",
    },
    "dash.cap2": {"ar": "📄 منشئ الوثائق", "en": "📄 Document builder"},
    "dash.cap2d": {
        "ar": "هيكل مقترح · حقن القوالب · تصدير Word و PDF",
        "en": "Proposed outline · template injection · Word & PDF",
    },
    "dash.cap3": {"ar": "🔍 مراجعة ثلاثية", "en": "🔍 Three-lens review"},
    "dash.cap3d": {
        "ar": "فنية · تجارية · قانونية · تطبيق بنقرة",
        "en": "Technical · commercial · legal · one-click apply",
    },

    # ── المنافسات / Tenders ──
    "proj.title": {"ar": "📁 المنافسات المحفوظة", "en": "📁 Saved tenders"},
    "proj.caption": {
        "ar": "كل منافسة تُحفظ على القرص محلياً مع تحليلاتها وأقسامها وجداولها.",
        "en": "Each tender is stored locally with its analyses, sections and tables.",
    },
    "proj.db_path": {"ar": "ملف قاعدة البيانات:", "en": "Database file:"},
    "proj.open_now": {"ar": "📂 المنافسة المفتوحة:", "en": "📂 Open tender:"},
    "proj.none_open": {
        "ar": "لا توجد منافسة مفتوحة. أنشئ واحدة جديدة أو افتح محفوظة أدناه.",
        "en": "No tender open. Create one or open a saved tender below.",
    },
    "proj.new": {"ar": "➕ منافسة جديدة", "en": "➕ New tender"},
    "proj.name": {"ar": "اسم المنافسة *", "en": "Tender name *"},
    "proj.entity": {"ar": "الجهة", "en": "Issuing entity"},
    "proj.reference": {"ar": "رقم المنافسة", "en": "Tender reference"},
    "proj.carry": {
        "ar": "انقل بيانات الجلسة الحالية إلى المنافسة الجديدة",
        "en": "Carry the current session data into the new tender",
    },
    "proj.create": {"ar": "➕ أنشئ المنافسة", "en": "➕ Create tender"},
    "proj.name_required": {"ar": "أدخل اسم المنافسة.", "en": "Enter a tender name."},
    "proj.created": {"ar": "✅ أُنشئت المنافسة «{name}».", "en": "✅ Created tender “{name}”."},
    "proj.saved": {"ar": "💾 حُفظت المنافسة.", "en": "💾 Tender saved."},
    "proj.count": {"ar": "**{n} منافسة محفوظة**", "en": "**{n} saved tenders**"},
    "proj.updated": {"ar": "آخر تحديث:", "en": "Updated:"},
    "proj.copy_suffix": {"ar": "(نسخة)", "en": "(copy)"},
    "proj.not_found": {"ar": "❌ لم يُعثر على المنافسة.", "en": "❌ Tender not found."},
    "proj.autosave_failed": {
        "ar": "⚠️ تعذّر الحفظ التلقائي: {error}",
        "en": "⚠️ Auto-save failed: {error}",
    },

    # ── تبويبات مساحة العمل / Workspace tabs ──
    "an.tab": {"ar": "التحليل والمخاطر", "en": "Analysis & risk"},
    "tb.tab": {"ar": "الامتثال وجدول الكميات", "en": "Compliance & BOQ"},
    "db.tab": {"ar": "منشئ العرض الفني", "en": "Proposal builder"},
    "rv.tab": {"ar": "المراجعة والتسليم", "en": "Review & delivery"},

    # ── التحليل / Analysis ──
    "an.upload_title": {"ar": "### 📥 رفع مرفقات المنافسة", "en": "### 📥 Upload tender attachments"},
    "an.formats": {
        "ar": "يدعم: PDF · Word · Excel · CSV · TXT · HTML",
        "en": "Supports: PDF · Word · Excel · CSV · TXT · HTML",
    },
    "an.extract": {"ar": "📂 استخراج النصوص", "en": "📂 Extract text"},
    "an.extract_failed": {
        "ar": "❌ لم يتم استخراج أي نص. تأكد من الملفات المرفوعة.",
        "en": "❌ No text extracted. Check the uploaded files.",
    },
    "an.start_hint": {
        "ar": "ارفع مرفقات المنافسة واضغط **استخراج النصوص** للبدء.",
        "en": "Upload the tender attachments and press **Extract text** to begin.",
    },
    "an.attachments": {"ar": "📎 المرفقات ({n})", "en": "📎 Attachments ({n})"},
    "an.tokens_est": {"ar": "تقدير التوكنز: {n}", "en": "Estimated tokens: {n}"},
    "an.role_hint": {
        "ar": "الدور مُرجَّح من اسم الملف — عدّله إن أخطأ.",
        "en": "The role is guessed from the filename — change it if wrong.",
    },
    "an.role": {"ar": "الدور", "en": "Role"},
    "an.chars": {"ar": "{n} حرف", "en": "{n} chars"},
    "an.context_title": {
        "ar": "0️⃣ سياق المشروع الموحّد (من كل المرفقات)",
        "en": "0️⃣ Unified project context (all attachments)",
    },
    "an.context_run": {"ar": "🧩 دمج المرفقات", "en": "🧩 Fuse attachments"},
    "an.context_hint": {
        "ar": "اضغط **دمج المرفقات** لاستخراج بيانات المشروع الأساسية وقيوده.",
        "en": "Press **Fuse attachments** to extract the project's core data and constraints.",
    },
    "an.context_merging": {"ar": "جاري الدمج...", "en": "Fusing..."},
    "an.entity": {"ar": "الجهة", "en": "Entity"},
    "an.deadline": {"ar": "الموعد النهائي", "en": "Deadline"},
    "an.certs_count": {"ar": "الشهادات المطلوبة", "en": "Required certifications"},
    "an.deliverables": {"ar": "🎯 التسليمات الرئيسية", "en": "🎯 Key deliverables"},
    "an.constraints": {"ar": "⚙️ القيود الفنية", "en": "⚙️ Technical constraints"},
    "an.penalties": {"ar": "⚠️ الغرامات التعاقدية", "en": "⚠️ Contractual penalties"},
    "an.certs": {"ar": "📜 الشهادات المطلوبة", "en": "📜 Required certifications"},
    "an.local_content": {"ar": "🇸🇦 **المحتوى المحلي:**", "en": "🇸🇦 **Local content:**"},
    "an.gonogo": {
        "ar": "1️⃣ قرار الملاءمة والجدوى (Go / No-Go)",
        "en": "1️⃣ Bid/no-bid decision (Go / No-Go)",
    },
    "an.gonogo_btn": {"ar": "توليد تقرير Go/No-Go", "en": "Generate Go/No-Go report"},
    "an.gonogo_note": {
        "ar": "✍️ قرار المهندس المعتمد (يُمرَّر للـ AI لاحقاً):",
        "en": "✍️ Approved engineer decision (passed to the AI later):",
    },
    "an.eval": {"ar": "2️⃣ مصفوفة معايير التقييم والأوزان", "en": "2️⃣ Evaluation criteria & weights"},
    "an.eval_btn": {"ar": "استخراج الأوزان", "en": "Extract weights"},
    "an.eval_note": {
        "ar": "✍️ الأوزان المعتمدة (توجيه لكتابة المنهجية):",
        "en": "✍️ Approved weights (guide the methodology):",
    },
    "an.comp": {"ar": "3️⃣ الشروط الحاكمة وفجوات الامتثال", "en": "3️⃣ Governing terms & compliance gaps"},
    "an.comp_btn": {"ar": "فحص الشروط الإلزامية", "en": "Check mandatory terms"},
    "an.comp_note": {
        "ar": "✍️ الشهادات والفجوات المعتمدة للمعالجة:",
        "en": "✍️ Approved certifications and gaps to address:",
    },

    "an.preview": {
        "ar": "👁️ معاينة النص المستخرج",
        "en": "👁️ Preview extracted text",
    },
    "an.truncated": {"ar": "... [تم الاختصار]", "en": "... [truncated]"},

    # ── الجداول / Tables ──
    "tb.title": {"ar": "### 📊 جداول المراجعة والكميات", "en": "### 📊 Compliance & quantities"},
    "tb.compliance": {
        "ar": "📋 جدول الامتثال بالمواصفات (Compliance Matrix)",
        "en": "📋 Compliance Matrix",
    },
    "tb.boq": {
        "ar": "📦 جدول الكميات (Bill of Quantities — BOQ)",
        "en": "📦 Bill of Quantities (BOQ)",
    },
    "tb.upload_first": {
        "ar": "💡 ارفع كراسة الشروط في التبويب الأول لتفعيل التعبئة الآلية.",
        "en": "💡 Upload the tender documents in the first tab to enable auto-fill.",
    },
    "tb.extract_reqs": {"ar": "استخراج المتطلبات من الكراسة", "en": "Extract requirements"},
    "tb.extract_boq": {"ar": "استخراج بنود الكميات", "en": "Extract BOQ items"},
    "tb.boq_source": {
        "ar": "📄 المصدر: الملفات المصنّفة **جدول الكميات**.",
        "en": "📄 Source: files classified as **BOQ**.",
    },
    "tb.nothing_found": {
        "ar": "⚠️ لم يعثر النموذج على بنود قابلة للاستخراج.",
        "en": "⚠️ The model found no extractable items.",
    },
    "tb.extracted": {
        "ar": "✅ تم استخراج **{n}** بند. راجعها وعدّلها قبل الاعتماد.",
        "en": "✅ Extracted **{n}** items. Review and edit before approving.",
    },
    "tb.total_reqs": {"ar": "إجمالي المتطلبات", "en": "Total requirements"},
    "tb.compliant": {"ar": "✅ ملتزم", "en": "✅ Compliant"},
    "tb.partial": {"ar": "⚠️ جزئي", "en": "⚠️ Partial"},
    "tb.non_compliant": {"ar": "❌ غير ملتزم", "en": "❌ Non-compliant"},
    "tb.total_items": {"ar": "إجمالي البنود", "en": "Total items"},
    "tb.flagged": {"ar": "🇸🇦 مرشّح للقائمة الإلزامية", "en": "🇸🇦 Mandatory-list candidates"},
    "tb.reset_table": {"ar": "↩️ إعادة ضبط الجدول", "en": "↩️ Reset table"},
    "tb.mandatory_warning": {
        "ar": (
            "⚠️ عمود **القائمة الإلزامية** ترشيح من النموذج لا حكم نهائي — تحقّق منه "
            "مقابل القائمة الرسمية للمحتوى المحلي قبل الاعتماد. رفع القائمة الرسمية "
            "في **مستودع المعرفة** يحسّن دقة الترشيح."
        ),
        "en": (
            "⚠️ The **Mandatory list** column is a model suggestion, not a ruling — "
            "verify it against the official Local Content list before approving. "
            "Adding the official list to the **Knowledge base** improves accuracy."
        ),
    },
    "tb.high_criticality": {"ar": "🔴 أهمية عالية", "en": "🔴 High criticality"},
    "tb.compliance_note": {
        "ar": "⚠️ عمود **الالتزام** قرار بشري — النموذج يقترح الاستراتيجية ولا يحكم بالالتزام.",
        "en": "⚠️ The **Compliance** column is a human decision — the model proposes a "
              "strategy, it does not declare compliance.",
    },
    "tb.col_category": {"ar": "التصنيف", "en": "Category"},
    "tb.col_clause": {"ar": "مرجع البند", "en": "Clause"},
    "tb.col_requirement": {"ar": "المتطلب", "en": "Requirement"},
    "tb.col_criticality": {"ar": "الأهمية", "en": "Criticality"},
    "tb.col_strategy": {"ar": "استراتيجية الاستجابة", "en": "Compliance strategy"},
    "tb.col_status": {"ar": "الالتزام", "en": "Compliance"},
    "tb.col_certificate": {"ar": "الشهادة المطلوبة", "en": "Required certificate"},
    "tb.export": {"ar": "#### 📥 تصدير الجداول", "en": "#### 📥 Export tables"},
    "tb.export_comp": {"ar": "📥 تصدير Compliance Matrix (CSV)", "en": "📥 Export Compliance Matrix (CSV)"},
    "tb.export_boq": {"ar": "📥 تصدير BOQ (CSV)", "en": "📥 Export BOQ (CSV)"},
    "tb.download_comp": {"ar": "⬇️ تحميل compliance_matrix.csv", "en": "⬇️ Download compliance_matrix.csv"},
    "tb.download_boq": {"ar": "⬇️ تحميل boq.csv", "en": "⬇️ Download boq.csv"},

    # ── منشئ العرض / Builder ──
    "db.title": {"ar": "### 📄 منشئ العرض الفني", "en": "### 📄 Proposal builder"},
    "db.outline": {"ar": "🗂️ هيكل العرض الفني", "en": "🗂️ Proposal outline"},
    "db.outline_source": {"ar": "المصدر الحالي: **{source}**", "en": "Source: **{source}**"},
    "db.outline_stats": {
        "ar": "{total} قسم · {included} مُدرَج",
        "en": "{total} sections · {included} included",
    },
    "db.propose": {"ar": "🤖 اقترح هيكلاً من الكراسة", "en": "🤖 Propose outline from documents"},
    "db.propose_hint": {
        "ar": "ارفع كراسة الشروط أولاً من التبويب الأول.",
        "en": "Upload the tender documents in the first tab.",
    },
    "db.proposing": {"ar": "جاري اقتراح الهيكل...", "en": "Proposing outline..."},
    "db.proposed": {
        "ar": "✅ اقتُرح هيكل من **{n}** قسماً. راجعه وعدّله قبل الصياغة.",
        "en": "✅ Proposed an outline of **{n}** sections. Review before drafting.",
    },
    "db.no_sections": {"ar": "⚠️ لم يقترح النموذج أي أقسام.", "en": "⚠️ The model proposed no sections."},
    "db.sections_hint": {
        "ar": "**الأقسام** — رتّبها واختر ما يُدرَج في المستند النهائي:",
        "en": "**Sections** — reorder and choose what goes into the final document:",
    },
    "db.include": {"ar": "إدراج", "en": "Include"},
    "db.priority": {"ar": " · أولوية {value}", "en": " · priority {value}"},
    "db.new_section": {"ar": "عنوان قسم جديد", "en": "New section title"},
    "db.new_section_ph": {"ar": "مثال: خطة نقل المعرفة", "en": "e.g. Knowledge transfer plan"},
    "db.add_section": {"ar": "➕ أضف قسماً", "en": "➕ Add section"},
    "db.src.default": {"ar": "افتراضي", "en": "Default"},
    "db.src.proposed": {"ar": "مقترح من الكراسة", "en": "Proposed from documents"},
    "db.src.custom": {"ar": "مخصص", "en": "Custom"},
    "db.proposal_title": {"ar": "عنوان العرض المقترح:", "en": "Proposed title:"},
    "db.submitted_to": {"ar": "مقدَّم إلى:", "en": "Submitted to:"},
    "db.key_points": {"ar": "النقاط الجوهرية", "en": "Key points"},
    "db.missing_mandatory": {
        "ar": "⚠️ أقسام إلزامية وفق معايير اعتماد غير مُدرَجة: {names}",
        "en": "⚠️ Mandatory Etimad sections not included: {names}",
    },
    "db.financial_warning": {
        "ar": "🚨 **العرض الفني يجب أن يخلو من التسعير.** جدول الكميات مُدرَج — "
              "أدرجه فقط إن نصّت الكراسة على ذلك، وتأكد أنه بلا أسعار.",
        "en": "🚨 **The technical proposal must contain no pricing.** A BOQ section is "
              "included — only do so if the tender requires it, and ensure it has no prices.",
    },
    "db.editors": {"ar": "### ✍️ محررات الأقسام", "en": "### ✍️ Section editors"},
    "db.no_included": {
        "ar": "لم تختر أي قسم بعد. فعّل الأقسام من قائمة الهيكل أعلاه.",
        "en": "No sections selected yet. Enable them in the outline above.",
    },
    "db.table_injected": {
        "ar": "يُحقن من التبويب الثاني ({n} صف).",
        "en": "Injected from the second tab ({n} rows).",
    },
    "db.cover_mode": {"ar": "طريقة الإعداد:", "en": "Mode:"},
    "db.cover_template": {"ar": "قالب ثابت (من ملف الشركة)", "en": "Fixed template (company profile)"},
    "db.cover_ai": {"ar": "توليد ديناميكي (AI)", "en": "AI generated"},
    "db.cover_uses": {
        "ar": "سيُستخدم القالب المحفوظ في **ملف الشركة**:",
        "en": "The template saved in **Company Profile** will be used:",
    },
    "db.cover_generate": {"ar": "⚡ توليد الخطاب", "en": "⚡ Generate letter"},
    "db.cover_text": {"ar": "نص الخطاب", "en": "Letter text"},
    "db.covers": {"ar": "يغطي: {value}", "en": "Covers: {value}"},
    "db.section_text": {"ar": "النص (قابل للتحرير)", "en": "Text (editable)"},
    "db.placeholder_warn": {
        "ar": "⚠️ يحتوي هذا القسم على نص نائب بين [ ] يحتاج تعبئة.",
        "en": "⚠️ This section contains [ ] placeholders that need filling.",
    },
    "db.steering": {"ar": "🎯 توجيه الكتابة (اختياري)", "en": "🎯 Writing steering (optional)"},
    "db.steering_ph": {
        "ar": "مثال: ركّز على التكامل مع الأنظمة القائمة، وأبرز خبرتنا في القطاع الصحي",
        "en": "e.g. focus on integration with existing systems; highlight our health-sector work",
    },
    "db.assistant": {"ar": "🤖 المساعد الجانبي — تنقيح النص", "en": "🤖 Side assistant — refine text"},
    "db.assistant_ph": {
        "ar": "اكتب طلب التعديل… مثال: اجعله أكثر إيجازاً",
        "en": "Describe the edit… e.g. make it more concise",
    },
    "db.refine": {"ar": "✨ نقّح", "en": "✨ Refine"},
    "db.refining": {"ar": "جاري التنقيح...", "en": "Refining..."},
    "db.ask": {"ar": "💬 اسأل", "en": "💬 Ask"},
    "db.ask_help": {
        "ar": "يجيب عن سؤالك دون تعديل نص القسم.",
        "en": "Answers your question without touching the section text.",
    },
    "db.asking": {"ar": "جاري الإجابة...", "en": "Thinking..."},
    "db.qa_clear": {"ar": "امسح النقاش", "en": "Clear discussion"},
    "db.quick_concise": {"ar": "أكثر إيجازاً", "en": "More concise"},
    "db.quick_kpis": {"ar": "أضف مؤشرات أداء", "en": "Add KPIs"},
    "db.quick_risk": {"ar": "أبرز إدارة المخاطر", "en": "Emphasize risk"},
    "db.quick_formal": {"ar": "صياغة أكثر رسمية", "en": "More formal"},
    "db.refine_needs_text": {
        "ar": "اكتب القسم أولاً ثم نقّحه.",
        "en": "Draft the section first, then refine it.",
    },
    "db.export_title": {
        "ar": "### 📥 مراجعة وتصدير العرض الفني",
        "en": "### 📥 Review & export the proposal",
    },
    "db.chk_company": {"ar": "ملف الشركة", "en": "Company profile"},
    "db.chk_rfp": {"ar": "تحليل الكراسة", "en": "Tender analysis"},
    "db.chk_written": {"ar": "أقسام مكتوبة", "en": "Sections drafted"},
    "db.chk_placeholders": {"ar": "لا يوجد نص ناقص", "en": "No missing text"},
    "db.empty_sections": {"ar": "📝 أقسام مُدرَجة وفارغة: ", "en": "📝 Included but empty: "},
    "db.placeholders_found": {
        "ar": "🚨 يوجد نص بين أقواس [ ] يحتاج تعبئة يدوية قبل التصدير:",
        "en": "🚨 [ ] placeholders must be filled before export:",
    },
    "db.template_on": {
        "ar": "✅ سيتم الحقن داخل قالب الشركة الرسمي (Word).",
        "en": "✅ Content will be injected into your official Word template.",
    },
    "db.template_off": {
        "ar": "💡 لا يوجد قالب مخصص. سيُصدَّر كمستند قياسي. (أضف قالباً في **ملف الشركة**).",
        "en": "💡 No custom template. A standard document will be produced. "
              "(Add one in **Company Profile**.)",
    },
    "db.opt_toc": {"ar": "إدراج فهرس المحتويات", "en": "Include table of contents"},
    "db.opt_pageno": {"ar": "ترقيم الصفحات", "en": "Page numbers"},
    "db.build_word": {"ar": "📄 بناء ملف Word", "en": "📄 Build Word file"},
    "db.build_pdf": {"ar": "📕 بناء ملف PDF", "en": "📕 Build PDF file"},
    "db.building": {"ar": "جاري بناء المستند...", "en": "Building document..."},
    "db.built_word": {"ar": "✅ تم بناء ملف Word.", "en": "✅ Word file built."},
    "db.built_pdf": {"ar": "✅ تم بناء ملف PDF.", "en": "✅ PDF file built."},
    "db.build_failed": {"ar": "❌ فشل بناء المستند: {error}", "en": "❌ Build failed: {error}"},
    "db.pdf_missing_libs": {
        "ar": "❌ مكتبات الـ PDF غير مثبّتة: {error}",
        "en": "❌ PDF libraries are not installed: {error}",
    },
    "db.download_word": {"ar": "⬇️ تحميل Word", "en": "⬇️ Download Word"},
    "db.download_pdf": {"ar": "⬇️ تحميل PDF", "en": "⬇️ Download PDF"},

    # ── المراجعة / Review ──
    "rv.title": {"ar": "### 🔍 المراجعة الشاملة قبل التسليم", "en": "### 🔍 Pre-submission review"},
    "rv.caption": {
        "ar": "فحص العرض من ثلاث زوايا — فنية وتجارية وقانونية — مقابل كراسة الشروط.",
        "en": "Reviews the proposal from three angles — technical, commercial, legal.",
    },
    "rv.no_content": {
        "ar": "لا يوجد محتوى للمراجعة بعد. اكتب أقسام العرض في تبويب **منشئ العرض الفني** أولاً.",
        "en": "Nothing to review yet. Draft sections in the **Proposal builder** tab first.",
    },
    "rv.no_rfp": {
        "ar": "⚠️ لم تُحمَّل كراسة الشروط. المراجعة ستفحص اتساق العرض داخلياً فقط.",
        "en": "⚠️ No tender documents loaded. The review will only check internal consistency.",
    },
    "rv.will_review": {"ar": "سيُراجَع **{n}** قسماً مكتوباً.", "en": "**{n}** drafted sections will be reviewed."},
    "rv.lenses": {"ar": "الزوايا:", "en": "Angles:"},
    "rv.run": {"ar": "🔍 شغّل المراجعة", "en": "🔍 Run review"},
    "rv.running": {"ar": "⏳ جاري المراجعة {lens}…", "en": "⏳ Reviewing — {lens}…"},
    "rv.clean": {"ar": "✅ لم تُرصد ملاحظات في آخر مراجعة.", "en": "✅ No findings in the last review."},
    "rv.readiness": {"ar": "درجة الجاهزية", "en": "Readiness"},
    "rv.overall_readiness": {"ar": "🎯 الجاهزية الإجمالية", "en": "🎯 Overall readiness"},
    "rv.assessment": {"ar": "التقييم", "en": "Assessment"},
    "rv.recommendations": {"ar": "توصيات قابلة للتنفيذ", "en": "Actionable recommendations"},
    "rv.not_ready": {
        "ar": "🚨 الجاهزية دون 60 — العرض غير جاهز للتسليم.",
        "en": "🚨 Readiness below 60 — the proposal is not ready to submit.",
    },
    "rv.agents": {"ar": "🤖 لجنة المراجعة", "en": "🤖 Review panel"},
    "rv.strengths": {"ar": "نقاط القوة", "en": "Strengths"},
    "rv.gaps": {"ar": "الثغرات المرصودة", "en": "Gaps identified"},
    "rv.critical": {"ar": "🔴 حرجة", "en": "🔴 Critical"},
    "rv.medium": {"ar": "🟡 متوسطة", "en": "🟡 Medium"},
    "rv.minor": {"ar": "🔵 طفيفة", "en": "🔵 Minor"},
    "rv.applied": {"ar": "✅ طُبِّقت", "en": "✅ Applied"},
    "rv.last_run": {"ar": "آخر مراجعة: {when}", "en": "Last review: {when}"},
    "rv.hide_applied": {"ar": "إخفاء الملاحظات المُطبَّقة", "en": "Hide applied findings"},
    "rv.all_applied": {"ar": "✅ طُبِّقت جميع الملاحظات.", "en": "✅ All findings applied."},
    "rv.issue": {"ar": "**المشكلة:**", "en": "**Issue:**"},
    "rv.impact": {"ar": "**الأثر:**", "en": "**Impact:**"},
    "rv.suggestion": {"ar": "💡 الصياغة المقترحة", "en": "💡 Suggested wording"},
    "rv.apply": {"ar": "✨ طبّق التحسين", "en": "✨ Apply fix"},
    "rv.apply_blocked": {
        "ar": "الملاحظة غير مرتبطة بقسم محدد أو طُبِّقت بالفعل.",
        "en": "Not linked to a section, or already applied.",
    },
    "rv.improving": {"ar": "جاري تحسين «{title}»...", "en": "Improving “{title}”..."},
    "rv.section_unknown": {"ar": "قسم غير محدد", "en": "Unknown section"},
    "rv.review_of": {"ar": "مراجعة", "en": "review"},

    # ── ملف الشركة / Company ──
    "co.title": {"ar": "### 🏢 ملف الشركة", "en": "### 🏢 Company profile"},
    "co.legal": {"ar": "📋 البيانات الأساسية والقانونية", "en": "📋 Core & legal details"},
    "co.name": {"ar": "اسم الشركة *", "en": "Company name *"},
    "co.cr": {"ar": "رقم السجل التجاري", "en": "Commercial registration"},
    "co.vat": {"ar": "الرقم الضريبي", "en": "VAT number"},
    "co.phone": {"ar": "الهاتف", "en": "Phone"},
    "co.email": {"ar": "البريد الإلكتروني", "en": "Email"},
    "co.web": {"ar": "الموقع الإلكتروني", "en": "Website"},
    "co.address": {"ar": "العنوان", "en": "Address"},
    "co.overview": {
        "ar": "نبذة عن الشركة (يستخدمها الذكاء الاصطناعي للتخصيص)",
        "en": "Company overview (used by the AI for tailoring)",
    },
    "co.name_missing": {
        "ar": "⚠️ أدخل اسم الشركة — سيُستخدم في جميع وثائق العرض الفني.",
        "en": "⚠️ Enter the company name — it appears in every proposal document.",
    },
    "co.brand": {"ar": "🎨 الهوية البصرية للمستندات", "en": "🎨 Document brand identity"},
    "co.brand_hint": {
        "ar": "تُطبَّق على غلاف Word و PDF وعناوينهما وترويسات الجداول. "
              "قالب Word المرفوع يحمل هويته الخاصة فلا تُفرض عليه.",
        "en": "Applied to the Word and PDF cover, headings and table headers. "
              "An uploaded Word template keeps its own identity and is left alone.",
    },
    "co.brand_color": {"ar": "لون العناوين", "en": "Heading colour"},
    "co.doc_font": {"ar": "خط المستند", "en": "Document font"},
    "co.doc_font_help": {
        "ar": "اتركه فارغاً للخط الافتراضي. الخط يجب أن يكون مثبَّتاً على جهاز "
              "من يفتح الملف وإلا استبدله Word بغيره.",
        "en": "Leave empty for the default. The font must be installed on the "
              "reader's machine or Word will substitute another.",
    },
    "co.templates": {"ar": "📝 قوالب الصياغة", "en": "📝 Writing templates"},
    "co.cover_template": {"ar": "قالب خطاب التقديم الثابت", "en": "Fixed cover letter template"},
    "co.word_template": {"ar": "📄 قالب Word المخصص (اختياري)", "en": "📄 Custom Word template (optional)"},
    "co.word_template_hint": {
        "ar": "ارفع ملف Word بهوية شركتك — سيُحقن محتوى العرض داخله.",
        "en": "Upload a Word file with your branding — proposal content is injected into it.",
    },
    "co.template_upload": {"ar": "ارفع القالب (صيغة .docx)", "en": "Upload template (.docx)"},
    "co.template_saved": {"ar": "✅ حُفظ القالب: **{name}**", "en": "✅ Template saved: **{name}**"},
    "co.template_active": {"ar": "✅ قالب الشركة محفوظ ومفعّل.", "en": "✅ Company template saved and active."},
    "co.template_delete": {"ar": "🗑️ حذف القالب", "en": "🗑️ Delete template"},
    "co.kb": {"ar": "### 🗂️ مستودع المعرفة", "en": "### 🗂️ Knowledge base"},
    "co.kb_caption": {
        "ar": "مستندات شركتك الحقيقية — يسترجع منها المساعد ما يخص كل قسم أثناء الصياغة.",
        "en": "Your real company documents — retrieved per section while drafting.",
    },
    "co.kb_docs": {"ar": "المستندات المفهرسة", "en": "Indexed documents"},
    "co.kb_chunks": {"ar": "المقاطع القابلة للاسترجاع", "en": "Retrievable chunks"},
    "co.kb_needs_key": {
        "ar": "⚠️ الفهرسة تحتاج مفتاح Gemini API — أدخله في **إعدادات النظام** أولاً.",
        "en": "⚠️ Indexing needs a Gemini API key — add it in **Settings** first.",
    },
    "co.kb_add": {"ar": "📤 إضافة مستندات للمستودع", "en": "📤 Add documents"},
    "co.kb_type": {"ar": "نوع المستندات:", "en": "Document type:"},
    "co.kb_index": {"ar": "🔎 فهرسة المستندات", "en": "🔎 Index documents"},
    "co.kb_indexed": {"ar": "✅ `{name}` — {n} مقطع.", "en": "✅ `{name}` — {n} chunks."},
    "co.kb_list": {"ar": "📚 المستندات المفهرسة ({n})", "en": "📚 Indexed documents ({n})"},
    "co.kb_try": {"ar": "🔍 جرّب الاسترجاع", "en": "🔍 Test retrieval"},
    "co.kb_query": {"ar": "استعلام تجريبي", "en": "Test query"},
    "co.kb_no_hits": {
        "ar": "لا توجد مقاطع ذات صلة كافية بهذا الاستعلام.",
        "en": "No sufficiently relevant chunks for this query.",
    },
    "co.kb_similarity": {"ar": "تشابه", "en": "similarity"},
    "co.kb_chunk_unit": {"ar": "مقطع", "en": "chunks"},
    "co.kb_char_unit": {"ar": "حرف", "en": "chars"},

    # ── الإعدادات / Settings ──
    "st.title": {"ar": "### ⚙️ إعدادات الذكاء الاصطناعي", "en": "### ⚙️ AI settings"},
    "st.keys": {"ar": "🔑 مفاتيح API", "en": "🔑 API keys"},
    "st.key_warning": {
        "ar": "⚠️ <strong>تنبيه أمني:</strong> مفاتيح API محفوظة في الذاكرة المؤقتة فقط "
              "وتُمسح عند إغلاق المتصفح.",
        "en": "⚠️ <strong>Security note:</strong> API keys live in session memory only and "
              "are cleared when the browser closes.",
    },
    "st.key_from_env": {
        "ar": "🔐 يوجد مفتاح في متغيّرات البيئة وقد حُمِّل تلقائياً. ما تكتبه هنا يَجُبّه لهذه الجلسة.",
        "en": "🔐 A key was loaded from the environment. What you type here overrides it for this session.",
    },
    "st.test_conn": {"ar": "✅ اختبار اتصال Gemini", "en": "✅ Test Gemini connection"},
    "st.key_first": {"ar": "أدخل المفتاح أولاً.", "en": "Enter the key first."},
    "st.testing": {"ar": "جاري الاختبار...", "en": "Testing..."},
    "st.conn_ok": {"ar": "✅ الاتصال يعمل! رد النموذج: {reply}", "en": "✅ Connected. Model replied: {reply}"},
    "st.conn_failed": {"ar": "❌ فشل الاتصال: {error}", "en": "❌ Connection failed: {error}"},
    "st.model_pref": {"ar": "🤖 تفضيلات النموذج الافتراضي", "en": "🤖 Default model"},
    "st.model_label": {"ar": "النموذج الافتراضي:", "en": "Default model:"},
    "st.model_help": {
        "ar": "Flash: متوازن وسريع. Pro: أدق للمهام المعقدة. Flash-Lite: الأرخص.",
        "en": "Flash: balanced. Pro: most accurate. Flash-Lite: cheapest.",
    },
    "st.out_lang": {"ar": "🌐 لغة المخرجات", "en": "🌐 Output language"},
    "st.out_lang_caption": {
        "ar": "تتحكم بلغة ما يولّده النظام واتجاه الكتابة في Word و PDF.",
        "en": "Controls generated content and the text direction in Word and PDF.",
    },
    "st.lang_label": {"ar": "اللغة:", "en": "Language:"},
    "st.ui_lang": {"ar": "🖥️ لغة الواجهة", "en": "🖥️ Interface language"},
    "st.ui_lang_caption": {
        "ar": "لغة عناصر الواجهة فقط — مستقلة عن لغة المخرجات.",
        "en": "Interface labels only — independent of the output language.",
    },

    # ── إدارة البيانات / Data ──
    "dm.title": {"ar": "### 💾 إدارة البيانات والنسخ الاحتياطي", "en": "### 💾 Data & backup"},
    "dm.export": {"ar": "📤 تصدير مساحة العمل", "en": "📤 Export workspace"},
    "dm.export_hint": {
        "ar": "احفظ العمل الحالي كملف JSON لاستئنافه لاحقاً.",
        "en": "Save the current work as JSON to resume later.",
    },
    "dm.download": {"ar": "⬇️ تحميل ملف مساحة العمل (.json)", "en": "⬇️ Download workspace (.json)"},
    "dm.size": {
        "ar": "حجم البيانات: {kb} KB · لا يشمل مفاتيح API.",
        "en": "Size: {kb} KB · excludes API keys.",
    },
    "dm.import": {"ar": "📥 استيراد مساحة عمل محفوظة", "en": "📥 Import saved workspace"},
    "dm.import_upload": {"ar": "ارفع ملف workspace .json", "en": "Upload workspace .json"},
    "dm.import_btn": {"ar": "📥 تحميل البيانات في مساحة العمل", "en": "📥 Load into workspace"},
    "dm.import_ok": {"ar": "✅ تم استيراد مساحة العمل بنجاح!", "en": "✅ Workspace imported."},
    "dm.import_failed": {"ar": "❌ فشل قراءة الملف: {error}", "en": "❌ Could not read the file: {error}"},
    "dm.clear": {"ar": "🗑️ مسح البيانات", "en": "🗑️ Clear data"},
    "dm.clear_warn": {
        "ar": "⚠️ هذه العمليات لا يمكن التراجع عنها.",
        "en": "⚠️ These actions cannot be undone.",
    },
    "dm.clear_analysis": {"ar": "🗑️ مسح تحليل الكراسة فقط", "en": "🗑️ Clear analysis only"},
    "dm.cleared": {"ar": "تم مسح بيانات التحليل.", "en": "Analysis data cleared."},
    "dm.clear_all": {"ar": "🗑️ مسح جميع البيانات", "en": "🗑️ Clear everything"},
    "dm.clear_confirm": {"ar": "تأكيد مسح كل شيء", "en": "Confirm clearing everything"},

    # ── أدوار المرفقات / Attachment roles ──
    "role.rfp": {"ar": "كراسة الشروط", "en": "Tender booklet"},
    "role.annex": {"ar": "ملحق فني / مواصفات", "en": "Technical annex / specs"},
    "role.boq": {"ar": "جدول الكميات", "en": "Bill of quantities"},
    "role.other": {"ar": "مرفق آخر", "en": "Other attachment"},

    # ── فئات المعرفة / KB categories ──
    "kbcat.cv": {"ar": "السير الذاتية", "en": "CVs"},
    "kbcat.cert": {"ar": "الشهادات والاعتمادات", "en": "Certifications"},
    "kbcat.project": {"ar": "المشاريع السابقة", "en": "Past projects"},
    "kbcat.other": {"ar": "مستندات أخرى", "en": "Other documents"},
}
