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
        "ar": "نظرة سريعة على حالة عملك الحالي: تحليل كراسات الشروط وبناء العروض الفنية.",
        "en": "A quick view of where your work stands: tender analysis and technical proposal drafting.",
    },
    "dash.company_name": {"ar": "اسم الشركة", "en": "Company"},
    "dash.sections_done": {"ar": "الأقسام المكتملة", "en": "Sections drafted"},
    "dash.workflow": {"ar": "خطوات سير العمل", "en": "Workflow"},
    "dash.tokens_unit": {"ar": "توكن", "en": "tokens"},
    "dash.not_loaded": {"ar": "لم تُحمَّل", "en": "Not loaded"},
    "dash.step1": {"ar": "١. الإعداد الأولي", "en": "1. Initial setup"},
    "dash.step1d": {
        "ar": "أدخل مفتاح Gemini API وبيانات الشركة.",
        "en": "Add your Gemini API key and company details.",
    },
    "dash.step2": {"ar": "٢. رفع المرفقات", "en": "2. Upload attachments"},
    "dash.step2d": {
        "ar": "ارفع مرفقات المنافسة وصنّفها (مع OCR).",
        "en": "Upload and classify tender attachments (with OCR).",
    },
    "dash.step3": {"ar": "٣. التحليل الذكي", "en": "3. AI analysis"},
    "dash.step3d": {
        "ar": "سياق المشروع · Go/No-Go · الأوزان · الكميات.",
        "en": "Project context · Go/No-Go · weights · BOQ.",
    },
    "dash.step4": {"ar": "٤. بناء العرض", "en": "4. Draft proposal"},
    "dash.step4d": {
        "ar": "اقترح الهيكل وصُغ كل قسم من الكراسة.",
        "en": "Propose the outline and draft each section.",
    },
    "dash.step5": {"ar": "٥. المراجعة النهائية", "en": "5. Final review"},
    "dash.step5d": {
        "ar": "راجع من ثلاث زوايا وصدّر Word أو PDF.",
        "en": "Three-lens review, then export Word or PDF.",
    },

    # ── المنافسات / Tenders ──
    "proj.title": {"ar": "المنافسات المحفوظة", "en": "Saved tenders"},
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
    "proj.history": {"ar": "🧠 ذاكرة العطاءات", "en": "🧠 Bid memory"},
    "proj.history_hint": {
        "ar": "سجّل نتيجة كل منافسة وسببها، فيستدعي النظام المشابه منها عند "
              "عطاء جديد. هذه سوابقك أنت — لا بيانات عن المنافسين.",
        "en": "Record each tender's outcome and why, and the system surfaces the "
              "similar ones on a new bid. These are your own precedents — not "
              "data about competitors.",
    },
    "proj.history_open_first": {
        "ar": "افتح منافسة لعرض السوابق المشابهة لها.",
        "en": "Open a tender to see its similar precedents.",
    },
    "proj.won": {"ar": "فاز", "en": "Won"},
    "proj.lost": {"ar": "خسر", "en": "Lost"},
    "proj.not_submitted": {"ar": "لم يُقدَّم", "en": "Not submitted"},
    "proj.unset": {"ar": "بلا نتيجة", "en": "No outcome"},
    "proj.similar": {"ar": "منافسات سابقة مشابهة", "en": "Similar past tenders"},
    "proj.no_similar": {
        "ar": "لا سوابق مشابهة في قاعدتك بعد.",
        "en": "No similar precedents in your database yet.",
    },
    "proj.same_entity": {"ar": "نفس الجهة", "en": "same entity"},
    "proj.record_outcome": {"ar": "تسجيل نتيجة المنافسة المفتوحة",
                            "en": "Record the open tender's outcome"},
    "proj.outcome": {"ar": "النتيجة", "en": "Outcome"},
    "proj.outcome_note": {"ar": "السبب / الدرس المستفاد", "en": "Reason / lesson"},
    "proj.outcome_note_ph": {
        "ar": "مثال: خسرنا على نسبة المحتوى المحلي رغم قوة العرض الفني",
        "en": "e.g. lost on the local-content percentage despite a strong technical offer",
    },
    "proj.save_outcome": {"ar": "💾 احفظ النتيجة", "en": "💾 Save outcome"},
    "proj.outcome_saved": {"ar": "سُجّلت النتيجة.", "en": "Outcome recorded."},
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
    "an.clean_saved": {
        "ar": "🧹 نُظّف {name} — حُذف {pct}٪ (ترويسات وأرقام صفحات وفهرس) قبل أي استدعاء.",
        "en": "🧹 Cleaned {name} — {pct}% removed (headers, page numbers, TOC) before any call.",
    },
    "an.clean_reverted": {
        "ar": "ℹ️ {name}: تجاوز التنظيف السقف الآمن فأُبقي النص الأصلي كما هو.",
        "en": "ℹ️ {name}: cleanup exceeded the safety cap, so the original text was kept.",
    },
    "an.dedupe_dropped": {
        "ar": "🗂️ أُسقطت مرفقات مكرّرة حرفياً: {files}",
        "en": "🗂️ Byte-identical duplicate attachments dropped: {files}",
    },
    "an.boq_local": {
        "ar": "📊 قُرئ جدول الكميات من {name} حسابياً ({n} بنداً) — بلا استدعاء نموذج.",
        "en": "📊 BOQ read directly from {name} ({n} items) — no model call.",
    },
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
    "an.gonogo_hint": {
        "ar": "يقارن متطلبات التأهيل في الكراسة بملف الشركة ومستودع معرفتها، "
              "ويُخرج فجوات التأهيل. التوصية اقتراح — القرار قرارك.",
        "en": "Compares the tender's qualification requirements against the company "
              "profile and knowledge base, and lists the qualification gaps. The "
              "recommendation is a proposal — the decision is yours.",
    },
    "an.gonogo_no_company": {
        "ar": "⚠️ ملف الشركة فارغ — سيحكم التحليل على المنافسة في المطلق لا على "
              "ملاءمتها لكم. أكمل **ملف الشركة** وارفع الشهادات والمشاريع السابقة "
              "إلى مستودع المعرفة أولاً.",
        "en": "⚠️ The company profile is empty — the analysis will judge the tender "
              "in the abstract, not its fit for you. Fill in the **company profile** "
              "and upload certificates and past projects to the knowledge base first.",
    },
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
    "tb.submission": {"ar": "📎 مستندات التسليم", "en": "📎 Submission documents"},
    "tb.submission_hint": {
        "ar": "أكثر أسباب الاستبعاد شيوعاً مستند ناقص أو شهادة منتهية، لا ضعف "
              "العرض الفني. تُستخرج القائمة من الكراسة — والحيازة والإرفاق قرارك أنت.",
        "en": "The most common reason for exclusion is a missing document or an "
              "expired certificate, not a weak technical proposal. The list is "
              "extracted from the tender — having and attaching them is your call.",
    },
    "tb.sub_total": {"ar": "مستندات مطلوبة", "en": "Documents required"},
    "tb.sub_ready": {"ar": "إلزامي جاهز", "en": "Mandatory ready"},
    "tb.sub_missing": {"ar": "ناقص", "en": "Missing"},
    "tb.sub_missing_list": {
        "ar": "⚠️ مستندات إلزامية غير جاهزة: ",
        "en": "⚠️ Mandatory documents not ready: ",
    },
    "tb.sub_expiring": {
        "ar": "🚨 شهادات تنتهي قبل الموعد النهائي — لن تُقبل يوم الفتح:",
        "en": "🚨 Certificates expiring before the deadline — they will not be "
              "accepted on opening day:",
    },
    "tb.sub_extract": {"ar": "📎 استخرج المستندات", "en": "📎 Extract documents"},
    "tb.sub_none": {
        "ar": "لم يُعثر على مستندات مشترطة في الكراسة — راجع يدوياً.",
        "en": "No required documents found in the tender — check manually.",
    },
    "tb.sub_col_doc": {"ar": "المستند", "en": "Document"},
    "tb.sub_col_mandatory": {"ar": "إلزامي", "en": "Mandatory"},
    "tb.sub_col_have": {"ar": "لدينا", "en": "We have it"},
    "tb.sub_col_expiry": {"ar": "تاريخ الانتهاء", "en": "Expiry date"},
    "tb.sub_col_expiry_help": {
        "ar": "بصيغة 2026-09-01. يُقارَن بالموعد النهائي للمنافسة.",
        "en": "Format 2026-09-01. Compared against the tender deadline.",
    },
    "tb.sub_col_attached": {"ar": "مرفق في المظروف", "en": "In the envelope"},
    "tb.sub_col_notes": {"ar": "ملاحظات", "en": "Notes"},
    "tb.col_coverage": {"ar": "التغطية", "en": "Coverage"},
    "tb.col_covered_in": {"ar": "عولج في", "en": "Addressed in"},
    "tb.coverage": {"ar": "🎯 مصفوفة التتبّع", "en": "🎯 Traceability matrix"},
    "tb.coverage_hint": {
        "ar": "يقارن كل متطلب بنص الأقسام المُدرَجة ويحدّد أين عولج وما لم يُعالَج. "
              "شغّله بعد كتابة الأقسام.",
        "en": "Matches each requirement against the text of the included sections and "
              "shows where it was addressed and what was not. Run it after drafting.",
    },
    "tb.cov_covered": {"ar": "مغطّى", "en": "Covered"},
    "tb.cov_partial": {"ar": "جزئي", "en": "Partial"},
    "tb.cov_missing": {"ar": "غير مغطّى", "en": "Not covered"},
    "tb.cov_unchecked": {"ar": "غير مفحوص", "en": "Unchecked"},
    "tb.cov_run": {"ar": "🎯 افحص التغطية", "en": "🎯 Check coverage"},
    "tb.cov_running": {"ar": "جاري فحص التغطية...", "en": "Checking coverage..."},
    "tb.cov_failed": {
        "ar": "تعذّر الفحص — تأكد من وجود متطلبات في المصفوفة ونص مكتوب في الأقسام.",
        "en": "Check failed — make sure the matrix has requirements and the sections "
              "have text.",
    },
    "tb.cov_blocking": {
        "ar": "🚨 متطلبات عالية الأهمية غير مغطّاة — تمنع التصدير:",
        "en": "🚨 High-criticality requirements not covered — export is blocked:",
    },
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
    "db.chk_coverage": {"ar": "تغطية المتطلبات", "en": "Requirement coverage"},
    "db.envelope_missing": {
        "ar": "📎 مستندات إلزامية غير جاهزة في المظروف (لا تمنع بناء الملف، "
              "لكنها تمنع قبول العرض): ",
        "en": "📎 Mandatory envelope documents not ready (this does not block "
              "building the file, but it blocks acceptance of the bid): ",
    },
    "db.envelope_expiring": {
        "ar": "🚨 شهادات تنتهي قبل الموعد النهائي للمنافسة:",
        "en": "🚨 Certificates expiring before the tender deadline:",
    },
    "db.coverage_blocking": {
        "ar": "🚨 {count} متطلباً عالي الأهمية بلا تغطية مؤكَّدة — التصدير موقوف. "
              "افحص التغطية من شاشة الجداول ثم عالج الناقص:",
        "en": "🚨 {count} high-criticality requirements without confirmed coverage — "
              "export is blocked. Run the coverage check on the Tables screen, then "
              "address what is missing:",
    },
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
    "rv.readiness_hint": {
        "ar": "الجاهزية الإجمالية هي أضعف زاوية لا متوسط الزوايا — زاوية "
              "واحدة ساقطة تكفي لرفض العرض.",
        "en": "Overall readiness is the weakest lens, not the average — one "
              "failing lens is enough to sink the bid.",
    },
    "rv.readiness_label": {"ar": "الجاهزية", "en": "Readiness"},
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
    "co.title": {"ar": "ملف الشركة", "en": "Company profile"},
    "co.subtitle": {
        "ar": "البيانات ومستودع المعرفة الذي يعتمد عليه النموذج في صياغة عروضك.",
        "en": "The data and knowledge base the model draws on when drafting your proposals.",
    },
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


    # ── سجلات الأدلة (المرحلة 12) / Evidence registries ──
    "rec.title": {"ar": "### 📇 سجلات الأدلة", "en": "### 📇 Evidence registries"},
    "rec.intro": {
        "ar": "لجنة الفحص لا تقبل «خبرة واسعة» — تسأل مَن وأين وبأي مستند. هذه السجلات هي الإجابة، وتُحقن في قرار الخوض ومصفوفة الكوادر والملاحق.",
        "en": "An evaluation panel does not accept \u201cextensive experience\u201d — it asks who, where, and with which document. These registries are the answer, and they feed Go/No-Go, the personnel matrix, and the appendices.",
    },
    "rec.save": {"ar": "💾 حفظ السجل", "en": "💾 Save registry"},
    "rec.saved": {"ar": "حُفظ {n} صفاً.", "en": "Saved {n} rows."},
    "rec.dropped_partial": {
        "ar": "\u26a0\ufe0f أُسقط {n} صفاً فيه إدخال بلا اسم/مُعرِّف — الصف بلا هوية ليس دليلاً. أعِد إدخاله باسمه.",
        "en": "\u26a0\ufe0f Dropped {n} rows that had data but no name/identifier — a row without identity is not evidence. Re-enter it with a name.",
    },
    "rec.date_help": {
        "ar": "ميلادي (2027-05-01) أو هجري (1448-11-14).",
        "en": "Gregorian (2027-05-01) or Hijri (1448-11-14).",
    },
    "rec.expiring": {
        "ar": "\u26d4 {n} تنتهي قبل الموعد النهائي لهذه المنافسة: {names}",
        "en": "\u26d4 {n} expire before this tender\u2019s deadline: {names}",
    },
    "rec.undated": {
        "ar": "\u26a0\ufe0f {n} صفاً بتاريخ تعذّرت قراءته — لم يُحكم عليه، راجعه يدوياً.",
        "en": "\u26a0\ufe0f {n} rows have an unreadable date — not judged; review manually.",
    },
    "rec.people": {"ar": "👷 سجل الكوادر", "en": "👷 Personnel registry"},
    "rec.people_hint": {
        "ar": "الكوادر الرئيسية بند تقييم مستقل. الصف هنا هو ما يُرشَّح في مصفوفة الكوادر ويخرج في ملحق السير.",
        "en": "Key personnel is a scored criterion. A row here is what gets nominated in the personnel matrix and printed in the CV appendix.",
    },
    "rec.p_name": {"ar": "الاسم", "en": "Name"},
    "rec.p_role": {"ar": "الدور", "en": "Role"},
    "rec.p_years": {"ar": "سنوات الخبرة", "en": "Years"},
    "rec.p_certs": {"ar": "الشهادات", "en": "Certifications"},
    "rec.p_cert_expiry": {"ar": "انتهاء الشهادة", "en": "Cert expiry"},
    "rec.p_languages": {"ar": "اللغات", "en": "Languages"},
    "rec.p_availability": {"ar": "الإتاحة", "en": "Availability"},
    "rec.p_cv": {"ar": "ملف السيرة", "en": "CV file"},
    "rec.references": {"ar": "🏗️ سابقة الأعمال", "en": "🏗️ Past projects"},
    "rec.references_hint": {
        "ar": "«ثلاثة مشاريع مماثلة» شرط يتكرّر — يُطابَق بصفوف لا بنص.",
        "en": "\u201cThree similar projects\u201d is a recurring condition — matched by rows, not prose.",
    },
    "rec.r_client": {"ar": "العميل", "en": "Client"},
    "rec.r_sector": {"ar": "القطاع", "en": "Sector"},
    "rec.r_scope": {"ar": "النطاق", "en": "Scope"},
    "rec.r_value": {"ar": "نطاق القيمة", "en": "Value band"},
    "rec.r_duration": {"ar": "المدة", "en": "Duration"},
    "rec.r_our_role": {"ar": "دورنا", "en": "Our role"},
    "rec.r_completion": {"ar": "شهادة إنجاز", "en": "Completion cert"},
    "rec.r_contact": {"ar": "جهة مرجعية", "en": "Reference contact"},
    "rec.certificates": {"ar": "📜 الشهادات والتصنيفات", "en": "📜 Certificates & classifications"},
    "rec.certificates_hint": {
        "ar": "شهادة تنتهي قبل الموعد غير مقبولة يوم الفتح ولو كانت بين يديك اليوم.",
        "en": "A certificate expiring before the deadline is invalid on opening day, even if valid today.",
    },
    "rec.c_kind": {"ar": "النوع", "en": "Type"},
    "rec.c_number": {"ar": "الرقم", "en": "Number"},
    "rec.c_issuer": {"ar": "جهة الإصدار", "en": "Issuer"},
    "rec.c_issued": {"ar": "الإصدار", "en": "Issued"},
    "rec.c_expiry": {"ar": "الانتهاء", "en": "Expiry"},
    "rec.c_document": {"ar": "الملف", "en": "File"},
    "rec.vendors": {"ar": "🤝 الموردون الرئيسيون", "en": "🤝 Key vendors"},
    "rec.vendors_hint": {
        "ar": "خطاب تفويض غائب أو منتهٍ يُسقط مستنداً من المظروف — والدعم المحلي يدخل درجة المحتوى المحلي.",
        "en": "A missing or expired authorization letter drops an envelope document — and local support feeds the local-content score.",
    },
    "rec.v_vendor": {"ar": "المورّد", "en": "Vendor"},
    "rec.v_line": {"ar": "خط المنتجات", "en": "Product line"},
    "rec.v_partnership": {"ar": "مستوى الشراكة", "en": "Partnership level"},
    "rec.v_letter": {"ar": "خطاب تفويض", "en": "Authorization letter"},
    "rec.v_letter_expiry": {"ar": "انتهاء الخطاب", "en": "Letter expiry"},
    "rec.v_support": {"ar": "دعم محلي", "en": "Local support"},
    "rec.v_eol": {"ar": "EOL/EOS", "en": "EOL/EOS"},
    "rec.v_alt": {"ar": "البديل", "en": "Alternative"},
    "rec.entities": {"ar": "🏛️ ملف الجهات", "en": "🏛️ Entity profiles"},
    "rec.entities_hint": {
        "ar": "سلوك الجهة في التقييم يتكرّر. يُستدعى ملفها تلقائياً عند فتح منافسة لها، ولو كُتب اسمها بصيغة أخرى.",
        "en": "An entity\u2019s evaluation behaviour repeats. Its profile is recalled automatically when you open a tender for it, even if the name is spelled differently.",
    },
    "rec.e_name": {"ar": "الجهة", "en": "Entity"},
    "rec.e_sector": {"ar": "القطاع", "en": "Sector"},
    "rec.e_contacts": {"ar": "جهات الاتصال", "en": "Contacts"},
    "rec.e_pattern": {"ar": "أنماط التقييم", "en": "Evaluation patterns"},
    "rec.e_recurring": {"ar": "متطلبات متكررة", "en": "Recurring requirements"},
    "rec.entity_matched": {
        "ar": "\u2705 للجهة «{name}» ملف مسجَّل — يُحقن في قرار الخوض.",
        "en": "\u2705 \u201c{name}\u201d has a stored profile — injected into Go/No-Go.",
    },
    "rec.entity_unknown": {
        "ar": "الجهة «{name}» بلا ملف بعد — أضِف صفاً لها لتُستدعى في العطاءات القادمة.",
        "en": "\u201c{name}\u201d has no profile yet — add a row so it is recalled in future bids.",
    },

    # ── مصفوفة الكوادر ودرجة المحتوى المحلي ──
    "tb.personnel": {"ar": "👷 مصفوفة الكوادر الرئيسية", "en": "👷 Key personnel matrix"},
    "tb.personnel_hint": {
        "ar": "كل دور تشترطه الكراسة ← المرشّح من سجل الكوادر ← دليل المطابقة ← الفجوة. الدور بلا مرشّح يظهر فجوةً ولا يُحذف.",
        "en": "Every role the RFP requires \u2192 candidate from the personnel registry \u2192 matching evidence \u2192 gap. A role with no candidate is shown as a gap, never dropped.",
    },
    "tb.personnel_no_registry": {
        "ar": "سجل الكوادر فارغ — املأه من شاشة ملف الشركة أولاً، وإلا فلا مرشّحين للمطابقة.",
        "en": "The personnel registry is empty — fill it from the company screen first, or there are no candidates to match.",
    },
    "tb.personnel_run": {"ar": "🤖 استخرج الأدوار وطابقها", "en": "🤖 Extract & match roles"},
    "tb.personnel_done": {"ar": "استُخرج {n} دوراً.", "en": "Extracted {n} roles."},
    "tb.personnel_gaps": {
        "ar": "\u26d4 {n} دوراً بفجوة: {roles}",
        "en": "\u26d4 {n} roles have a gap: {roles}",
    },
    "tb.pe_role": {"ar": "الدور المطلوب", "en": "Required role"},
    "tb.pe_requirements": {"ar": "اشتراطات الكراسة", "en": "RFP requirements"},
    "tb.pe_candidate": {"ar": "المرشّح", "en": "Candidate"},
    "tb.pe_evidence": {"ar": "دليل المطابقة", "en": "Evidence"},
    "tb.pe_gap": {"ar": "الفجوة", "en": "Gap"},
    "tb.local_content": {"ar": "🇸🇦 درجة المحتوى المحلي والسعودة", "en": "🇸🇦 Local content & Saudization"},
    "tb.local_content_hint": {
        "ar": "رقم صريح بدل التزام نصّي، محسوب من نطاق السعودة وبنود القائمة الإلزامية والموردين ذوي الدعم المحلي.",
        "en": "An explicit number instead of a prose commitment, computed from the Nitaqat band, mandatory-list items, and locally-supported vendors.",
    },
    "tb.lc_estimate": {"ar": "الدرجة التقديرية", "en": "Estimated score"},
    "tb.lc_required": {"ar": "الحد المطلوب", "en": "Required"},
    "tb.lc_gap": {"ar": "الفجوة", "en": "Gap"},
    "tb.lc_not_declared": {"ar": "غير معلن", "en": "Not declared"},
    "tb.lc_below": {
        "ar": "\u26d4 التقدير دون الحد المطلوب في الكراسة.",
        "en": "\u26d4 The estimate is below the level the RFP requires.",
    },
    "tb.lc_meets": {"ar": "\u2705 التقدير يبلغ الحد المطلوب.", "en": "\u2705 The estimate meets the required level."},
    "tb.lc_component": {"ar": "المكوّن", "en": "Component"},
    "tb.lc_value": {"ar": "القيمة", "en": "Value"},
    "tb.lc_weight": {"ar": "الوزن", "en": "Weight"},
    "tb.lc_saudization": {"ar": "نطاق السعودة", "en": "Nitaqat band"},
    "tb.lc_mandatory_items": {"ar": "بنود القائمة الإلزامية", "en": "Mandatory-list items"},
    "tb.lc_local_support": {"ar": "موردون بدعم محلي", "en": "Locally-supported vendors"},
    "tb.lc_missing": {
        "ar": "\u26a0\ufe0f مكوّنات بلا معطيات استُبعدت من الحساب: {fields}",
        "en": "\u26a0\ufe0f Components with no data were excluded from the calculation: {fields}",
    },
    "tb.lc_disclaimer": {
        "ar": "\u2139\ufe0f تقدير داخلي للتخطيط لا شهادة محتوى محلي — الاحتساب الرسمي بمنهجية الهيئة وبمستندات مدقَّقة.",
        "en": "\u2139\ufe0f An internal planning estimate, not a local-content certificate — official scoring follows the authority\u2019s audited methodology.",
    },

    # ── الملاحق ونطاق السعودة ──
    "db.appendices": {"ar": "الملاحق المرقّمة المُلحقة بالعرض", "en": "Numbered appendices to attach"},
    "db.appendices_help": {
        "ar": "تخرج جداول مُهيكلة بترقيم متصل وتدخل الفهرس. الملفات الأصلية (سيرة ممسوحة، شهادة PDF) تُرفق يدوياً في المظروف.",
        "en": "Exported as structured tables with continuous numbering, included in the table of contents. Original files (scanned CVs, PDF certificates) are attached manually in the envelope.",
    },
    "db.appendices_empty": {
        "ar": "لا ملاحق متاحة — املأ سجلات الأدلة من شاشة ملف الشركة.",
        "en": "No appendices available — fill the evidence registries on the company screen.",
    },
    "co.nitaqat": {"ar": "نطاق السعودة", "en": "Nitaqat band"},
    "co.nitaqat_help": {
        "ar": "يدخل في درجة المحتوى المحلي التقديرية بوزن النصف.",
        "en": "Feeds the estimated local-content score at half weight.",
    },

    # ── الإعدادات / Settings ──
    "st.title": {"ar": "إعدادات الذكاء الاصطناعي", "en": "AI settings"},
    "st.keys": {"ar": "🔑 مفاتيح API", "en": "🔑 API keys"},
    "st.key_warning": {
        "ar": "**تنبيه أمني:** مفاتيح API محفوظة في الذاكرة المؤقتة فقط "
              "وتُمسح عند إغلاق المتصفح.",
        "en": "**Security note:** API keys live in session memory only and "
              "are cleared when the browser closes.",
    },
    "st.key_from_env": {
        "ar": "🔐 يوجد مفتاح في متغيّرات البيئة وقد حُمِّل تلقائياً. ما تكتبه هنا يَجُبّه لهذه الجلسة.",
        "en": "🔐 A key was loaded from the environment. What you type here overrides it for this session.",
    },
    "st.test_conn": {"ar": "✅ اختبار الاتصال", "en": "✅ Test connection"},
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
    # المرحلة 11: الموفّرون والاقتصاد
    "st.provider": {"ar": "🧠 الموفّر والنموذج", "en": "🧠 Provider & model"},
    "st.provider_label": {"ar": "موفّر الذكاء الاصطناعي:", "en": "AI provider:"},
    "st.no_key_needed": {
        "ar": "هذا الموفّر محلي ولا يحتاج مفتاح API.",
        "en": "This provider is local and needs no API key.",
    },
    "st.base_url": {"ar": "رابط الخدمة (Base URL):", "en": "Base URL:"},
    "st.base_url_help": {
        "ar": "اتركه فارغاً لاستخدام الرابط الافتراضي. لـ OpenRouter و Groq و Ollama ضع رابط النقطة المتوافقة مع OpenAI.",
        "en": "Leave empty for the default. For OpenRouter, Groq, or Ollama, set the OpenAI-compatible endpoint URL.",
    },
    "st.model_specs": {
        "ar": "نافذة السياق: {context} توكن · السعر لكل مليون: ‏${inp} إدخال / ${out} إخراج",
        "en": "Context window: {context} tokens · Price per 1M: ${inp} in / ${out} out",
    },
    "st.temp_enable": {"ar": "ضبط الحرارة يدوياً", "en": "Set temperature manually"},
    "st.temp": {"ar": "الحرارة", "en": "Temperature"},
    "st.max_tokens": {"ar": "حد المخرَج (توكن)", "en": "Max output tokens"},
    "st.max_tokens_help": {
        "ar": "0 يعني الحد الافتراضي للموفّر.",
        "en": "0 means the provider default.",
    },
    "st.conn_ok_cost": {
        "ar": "✅ الاتصال يعمل! الرد: {reply} · الزمن: {seconds} ث · الكلفة: ${cost}",
        "en": "✅ Connected. Reply: {reply} · time: {seconds}s · cost: ${cost}",
    },
    "st.catalog_hint": {
        "ar": "سجل النماذج والأسعار قابل للتحديث بلا شيفرة عبر الملف: {path}",
        "en": "The model/price catalog is editable without code via: {path}",
    },
    "st.task_models": {"ar": "🎯 نموذج لكل مهمة", "en": "🎯 Model per task"},
    "st.task_models_hint": {
        "ar": "الأخف للاستخراج والتصنيف، والأقوى للكتابة والمراجعة. النجمة ★ تعني الافتراضي المعلن، وأي تغيير هنا يتجاوزه.",
        "en": "Lighter models for extraction/classification, stronger for writing/review. ★ marks the declared default; changing it overrides it.",
    },
    "st.task_extract": {"ar": "الاستخراج المُهيكل", "en": "Structured extraction"},
    "st.task_classify": {"ar": "التصنيف", "en": "Classification"},
    "st.task_write": {"ar": "كتابة الأقسام والهيكل", "en": "Section & outline writing"},
    "st.task_review": {"ar": "لجنة المراجعة", "en": "Review panel"},
    "st.task_chat": {"ar": "المساعد الجانبي", "en": "Side assistant"},
    "st.embed": {"ar": "🧬 موفّر التضمين (المستودع)", "en": "🧬 Embedding provider (knowledge base)"},
    "st.embed_provider": {"ar": "موفّر التضمين:", "en": "Embedding provider:"},
    "st.embed_model": {"ar": "نموذج التضمين:", "en": "Embedding model:"},
    "st.embed_warning": {
        "ar": "⚠️ تغيير نموذج التضمين يُبطل متجهات المستودع المخزَّنة: المقاطع "
              "المفهرسة بالنموذج القديم تُهمَل من البحث حتى تُعاد فهرستها.",
        "en": "⚠️ Changing the embedding model invalidates stored vectors: chunks "
              "indexed with the old model are excluded from search until re-indexed.",
    },
    "st.embed_stale": {
        "ar": "‏{stale} من أصل {total} مقطعاً مفهرس بنموذج آخر — معطَّل عن البحث.",
        "en": "{stale} of {total} chunks are indexed with another model — disabled for search.",
    },
    "st.embed_ok": {
        "ar": "كل المقاطع ({total}) مفهرسة بالنموذج النشط.",
        "en": "All chunks ({total}) are indexed with the active model.",
    },
    "st.reindex": {"ar": "🔄 إعادة فهرسة المستودع", "en": "🔄 Re-index knowledge base"},
    "st.reindexing": {"ar": "جاري إعادة الفهرسة…", "en": "Re-indexing…"},
    "st.reindex_failed": {
        "ar": "تعذّرت إعادة الفهرسة — تحقق من مفتاح موفّر التضمين.",
        "en": "Re-indexing failed — check the embedding provider key.",
    },
    "st.reindex_done": {"ar": "أُعيدت فهرسة {n} مقطعاً.", "en": "Re-indexed {n} chunks."},
    "st.budget": {"ar": "💵 حدّ الإنفاق والذاكرة", "en": "💵 Spend limit & caching"},
    "st.budget_label": {"ar": "حدّ الإنفاق الشهري (دولار):", "en": "Monthly spend limit (USD):"},
    "st.budget_help": {"ar": "0 يعني بلا حدّ.", "en": "0 means no limit."},
    "st.budget_spent": {"ar": "إنفاق شهر {month}", "en": "Spend for {month}"},
    "st.budget_blocked": {
        "ar": "🛑 بلغ الإنفاق حدّه — الاستدعاءات موقوفة حتى رفع الحدّ.",
        "en": "🛑 The limit is reached — calls are blocked until you raise it.",
    },
    "st.budget_warn": {
        "ar": "⚠️ تجاوز الإنفاق 80٪ من الحدّ الشهري.",
        "en": "⚠️ Spend passed 80% of the monthly limit.",
    },
    "st.cache_enable": {"ar": "ذاكرة نتائج الاستدعاءات", "en": "Result cache"},
    "st.cache_help": {
        "ar": "إعادة نفس الطلب بلا تغيير معطيات تُخدم من الذاكرة بلا توكن.",
        "en": "Repeating the same request with unchanged inputs is served from cache with zero tokens.",
    },
    "st.compressed": {"ar": "الموجز المضغوط عند كتابة الأقسام", "en": "Compressed brief for section writing"},
    "st.compressed_help": {
        "ar": "يمرّر السياق الموحّد وموجز المصفوفة وبنود الكراسة ذات الصلة بدل نص الكراسة الكامل.",
        "en": "Passes the unified context, matrix summary, and relevant RFP clauses instead of the full RFP text.",
    },
    "st.cache_clear": {"ar": "🗑️ مسح ذاكرة النتائج", "en": "🗑️ Clear result cache"},
    "st.cache_cleared": {"ar": "مُسحت ذاكرة النتائج.", "en": "Result cache cleared."},
    "st.usage": {"ar": "📊 شاشة الاستهلاك", "en": "📊 Usage dashboard"},
    "st.usage_month_only": {"ar": "الشهر الحالي فقط", "en": "Current month only"},
    "st.usage_calls": {"ar": "الاستدعاءات", "en": "Calls"},
    "st.usage_tokens": {"ar": "إجمالي التوكن", "en": "Total tokens"},
    "st.usage_cached": {"ar": "توكن مخزَّن", "en": "Cached tokens"},
    "st.usage_cost": {"ar": "الكلفة ($)", "en": "Cost ($)"},
    "st.usage_cache_hits": {
        "ar": "إصابات ذاكرة النتائج: {n} استدعاء خُدم بلا توكن.",
        "en": "Result-cache hits: {n} calls served with zero tokens.",
    },
    "st.usage_by_project": {"ar": "حسب المنافسة", "en": "By tender"},
    "st.usage_by_task": {"ar": "حسب المهمة (الوكيل)", "en": "By task (agent)"},
    "st.usage_by_model": {"ar": "مقارنة النماذج والموفّرين", "en": "Models & providers compared"},
    "st.usage_col_group": {"ar": "المجموعة", "en": "Group"},
    "st.usage_in": {"ar": "توكن إدخال", "en": "Input tokens"},
    "st.usage_out": {"ar": "توكن إخراج", "en": "Output tokens"},
    "st.savings": {"ar": "ما وفّرته المعالجة المحلية", "en": "Saved by local processing"},
    "st.savings_hint": {
        "ar": "تقدير محلي للمقارنة قبل وبعد، لا رقم فاتورة. الجدول أعلاه هو المُنفَق الفعلي.",
        "en": "A local before/after estimate, not a bill. The table above is actual spend.",
    },
    "st.savings_tokens": {"ar": "توكن موفَّر", "en": "Tokens saved"},
    "st.savings_avoided": {"ar": "استدعاءات تُجنِّبت", "en": "Calls avoided"},
    "st.savings_sent": {"ar": "توكن أُرسل", "en": "Tokens sent"},
    "st.method_cleanup": {"ar": "تنظيف الكراسة", "en": "RFP cleanup"},
    "st.method_retrieval": {"ar": "استرجاع لفظي", "en": "Lexical retrieval"},
    "st.method_cache": {"ar": "ذاكرة النتائج", "en": "Result cache"},
    "st.method_local_parse": {"ar": "قراءة الجدول محلياً", "en": "Local table parsing"},
    "st.method_dedupe": {"ar": "إسقاط المرفقات المكرّرة", "en": "Duplicate attachments dropped"},
    "st.usage_empty": {
        "ar": "لا استهلاك مسجَّل بعد — يبدأ التسجيل مع أول استدعاء.",
        "en": "No usage recorded yet — logging starts with the first call.",
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
    "dm.title": {"ar": "إدارة البيانات والنسخ الاحتياطي", "en": "Data & backup"},
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

    # ── الجدول الزمني / Timeline ──
    "tl.title": {"ar": "### 🗓️ الجدول الزمني ومعالم التسليم", "en": "### 🗓️ Timeline & milestones"},
    "tl.hint": {
        "ar": "مراحل بأسابيع نسبية لا بتواريخ — تاريخ الترسية غير معلوم بعد. "
              "«معلم دفع» علامة داخلية لا تدخل المستند الفني.",
        "en": "Phases in relative weeks, not dates — the award date is not yet known. "
              "The payment-milestone flag stays internal and never enters the technical document.",
    },
    "tl.extract": {"ar": "🗓️ استخرج الخطة الزمنية", "en": "🗓️ Extract timeline"},
    "tl.extracting": {"ar": "جاري بناء الخطة الزمنية…", "en": "Building the timeline…"},
    "tl.extracted": {"ar": "✅ استُخرجت {n} مرحلة.", "en": "✅ Extracted {n} phases."},
    "tl.none": {"ar": "لم يُستخرج أي مرحلة من الكراسة.", "en": "No phases were extracted."},
    "tl.phases": {"ar": "المراحل", "en": "Phases"},
    "tl.span": {"ar": "امتداد الخطة (أسبوع)", "en": "Plan span (weeks)"},
    "tl.contract": {"ar": "مدة العقد (أسبوع)", "en": "Contract duration (weeks)"},
    "tl.contract_unknown": {"ar": "غير مذكورة", "en": "Not stated"},
    "tl.errors": {"ar": "❌ الخطة غير قابلة للتنفيذ كما هي:", "en": "❌ The plan is not executable as it stands:"},
    "tl.warnings": {"ar": "⚠️ ملاحظات على الخطة:", "en": "⚠️ Notes on the plan:"},
    "tl.ok": {"ar": "✅ لا تعارض مرصود في الخطة.", "en": "✅ No conflicts detected in the plan."},
    "tl.uncovered": {"ar": "تسليمات بلا مرحلة تقابلها:", "en": "Deliverables with no matching phase:"},
    "tl.col_number": {"ar": "#", "en": "#"},
    "tl.col_phase": {"ar": "المرحلة", "en": "Phase"},
    "tl.col_start": {"ar": "البداية (أسبوع)", "en": "Start (week)"},
    "tl.col_duration": {"ar": "المدة (أسبوع)", "en": "Duration (weeks)"},
    "tl.col_depends": {"ar": "يعتمد على", "en": "Depends on"},
    "tl.col_deliverables": {"ar": "التسليمات", "en": "Deliverables"},
    "tl.col_payment": {"ar": "معلم دفع", "en": "Payment milestone"},
    "tl.col_payment_help": {
        "ar": "علامة داخلية للفريق التجاري — لا تُصدَّر في العرض الفني.",
        "en": "Internal flag for the commercial team — never exported in the technical proposal.",
    },
    "tl.col_weight": {"ar": "وزن الإنجاز %", "en": "Progress weight %"},
    "tl.gantt": {"ar": "معاينة المخطط الزمني", "en": "Gantt preview"},

    # ── اتساق الأرقام / Cross-section consistency ──
    "cs.title": {"ar": "🔢 اتساق الأرقام بين الأقسام", "en": "🔢 Cross-section number consistency"},
    "cs.hint": {
        "ar": "فحص حسابي بلا استدعاء نموذج: يقارن مدة التنفيذ المذكورة في الأقسام "
              "بالجدول الزمني وبمدة العقد.",
        "en": "A local check with no model call: compares the execution duration stated in "
              "the sections against the timeline and the contract duration.",
    },
    "cs.ok": {"ar": "✅ لا تناقض مرصود في مدد التنفيذ.", "en": "✅ No contradictions found in stated durations."},
    "cs.found": {"ar": "❌ {n} تناقضاً في الأرقام:", "en": "❌ {n} numeric contradictions:"},
    "cs.no_sections": {
        "ar": "لا أقسام مكتوبة بعد ليُفحص اتساقها.",
        "en": "No written sections yet to check.",
    },

    # ── الملاحق والتعديلات / Addenda ──
    "ad.title": {"ar": "📌 الملاحق والتعديلات", "en": "📌 Addenda & amendments"},
    "ad.hint": {
        "ar": "الجهات تُصدر تعديلات بعد نشر الكراسة. كل رفعة تُحفظ نسخةً، فتُقارَن "
              "بما قبلها ويُعرَف أي متطلب صار على شرط تغيّر.",
        "en": "Entities issue amendments after publication. Every upload is stored as a version "
              "so it can be compared with the previous one.",
    },
    "ad.versions": {"ar": "النسخ المحفوظة: {n}", "en": "Stored versions: {n}"},
    "ad.no_versions": {
        "ar": "لا نسخة محفوظة بعد — تُحفظ نسخة تلقائياً مع كل استخراج.",
        "en": "No versions stored yet — one is saved automatically on each extraction.",
    },
    "ad.need_two": {
        "ar": "المقارنة تحتاج نسختين على الأقل. ارفع الملحق أو التعديل واستخرج مرة أخرى.",
        "en": "Comparison needs at least two versions. Upload the amendment and extract again.",
    },
    "ad.compare": {"ar": "🔍 قارن بالنسخة السابقة", "en": "🔍 Compare with previous version"},
    "ad.no_changes": {"ar": "✅ لا فرق عن النسخة السابقة.", "en": "✅ No difference from the previous version."},
    "ad.changed_summary": {
        "ar": "تغيّر: {changed} ملفاً · أُضيف: {added} · حُذف: {removed} · "
              "أسطر جديدة: {added_lines} · أسطر مرفوعة: {removed_lines}",
        "en": "Changed: {changed} files · Added: {added} · Removed: {removed} · "
              "New lines: {added_lines} · Removed lines: {removed_lines}",
    },
    "ad.affected": {
        "ar": "🎯 {n} متطلباً يُرجَّح أن التعديل مسّه:",
        "en": "🎯 {n} requirements likely touched by the amendment:",
    },
    "ad.affected_none": {
        "ar": "لم يُرصد متطلب متأثر — راجع التغيير يدوياً قبل الاطمئنان.",
        "en": "No affected requirement detected — review the change manually before relying on this.",
    },
    "ad.mark": {"ar": "↩️ أعِد المتأثر إلى «غير مفحوص»", "en": "↩️ Reset affected rows to “unchecked”"},
    "ad.marked": {
        "ar": "أُعيد {n} متطلباً إلى «غير مفحوص» — أعِد فحص التغطية قبل التصدير.",
        "en": "{n} requirements reset to “unchecked” — re-run the coverage check before exporting.",
    },
    "ad.version_label": {"ar": "نسخة {n} · {at}", "en": "Version {n} · {at}"},
    "ad.added_files": {"ar": "ملفات جديدة", "en": "New files"},
    "ad.removed_files": {"ar": "ملفات اختفت", "en": "Removed files"},
    "ad.changed_files": {"ar": "ملفات تغيّرت", "en": "Changed files"},
    "ad.sample_added": {"ar": "أمثلة على النص المُضاف:", "en": "Sample added text:"},

    # ── لوحة المواعيد / Deadline board ──
    "dl.title": {"ar": "⏳ المواعيد", "en": "⏳ Key dates"},
    "dl.deadline": {"ar": "الموعد النهائي", "en": "Submission deadline"},
    "dl.remaining": {"ar": "المتبقّي", "en": "Remaining"},
    "dl.days": {"ar": "{n} يوماً", "en": "{n} days"},
    "dl.today": {"ar": "اليوم!", "en": "Today!"},
    "dl.passed": {"ar": "انقضى منذ {n} يوماً", "en": "Passed {n} days ago"},
    "dl.unreadable": {
        "ar": "الموعد غير مقروء كتاريخ — لا عدّ تنازلي ولا فحص صلاحية.",
        "en": "The deadline is not readable as a date — no countdown and no validity check.",
    },
    "dl.offer_validity": {"ar": "سريان العرض", "en": "Offer validity"},
    "dl.bid_bond": {"ar": "الضمان الابتدائي", "en": "Bid bond"},
    "dl.expiring": {"ar": "مستندات تنتهي قبل الموعد: {n}", "en": "Documents expiring before the deadline: {n}"},
    "dl.soon": {"ar": "⚠️ الموعد النهائي بعد {n} يوماً فقط.", "en": "⚠️ Only {n} days left before the deadline."},

    # ── محرّك النموذج ومستودع المعرفة / Engine & knowledge base ──
    # رسائل تظهر للمستخدم من داخل `utils/`. كانت مكتوبة عربية في الشيفرة،
    # فكان مستخدم الواجهة الإنجليزية يرى خطأً بالعربية.
    "eng.key_missing": {
        "ar": "⚠️ يرجى إدخال مفتاح API للموفّر المختار في **إعدادات النظام** أولاً.",
        "en": "⚠️ Enter the API key for the selected provider in **System settings** first.",
    },
    "eng.budget_stop": {
        "ar": "بلغ الإنفاق الشهري {spent}$ وحدّه {budget}$ — أوقفنا الاستدعاءات. ارفع الحدّ من الإعدادات للمتابعة.",
        "en": "Monthly spend reached ${spent} of the ${budget} limit — calls are blocked. Raise the limit in settings to continue.",
    },
    "eng.budget_warn": {
        "ar": "⚠️ الإنفاق الشهري {spent}$ تجاوز 80٪ من الحدّ ({budget}$).",
        "en": "⚠️ Monthly spend ${spent} passed 80% of the ${budget} limit.",
    },
    "eng.sdk_missing": {
        "ar": "❌ مكتبة google-genai غير مثبّتة. شغّل: pip install google-genai",
        "en": "❌ google-genai is not installed. Run: pip install google-genai",
    },
    "eng.client_failed": {
        "ar": "❌ تعذّر تهيئة عميل Gemini: {error}",
        "en": "❌ Could not initialise the Gemini client: {error}",
    },
    "eng.api_error": {
        "ar": "❌ خطأ Gemini API: {error}",
        "en": "❌ Gemini API error: {error}",
    },
    "eng.empty_reply": {
        "ar": "⚠️ رجع النموذج رداً فارغاً — قد يكون الطلب حُجب بفلاتر الأمان.",
        "en": "⚠️ The model returned an empty reply — the request may have been blocked by safety filters.",
    },
    "eng.retrying": {
        "ar": "⏳ تعذّر الاتصال مؤقتاً — إعادة المحاولة {n} من {total}…",
        "en": "⏳ Temporary connection failure — retry {n} of {total}…",
    },
    "eng.json_failed": {
        "ar": "❌ تعذّر تحليل رد النموذج كـ JSON: {error}",
        "en": "❌ Could not parse the model reply as JSON: {error}",
    },
    "eng.raw_reply": {"ar": "عرض الرد الخام", "en": "Show raw reply"},
    "kb.embed_failed": {
        "ar": "❌ تعذّر توليد متجهات التضمين: {error}",
        "en": "❌ Could not generate embeddings: {error}",
    },
    "kb.no_text": {
        "ar": "⚠️ لم يُستخرج نص من `{name}` — لم يُضَف للمستودع.",
        "en": "⚠️ No text extracted from `{name}` — it was not added to the repository.",
    },

    # ── الدخول والمصادقة (13-2) / Login & authentication ──
    "au.login_title": {"ar": "تسجيل الدخول", "en": "Sign in"},
    "au.login_subtitle": {
        "ar": "ادخل بحسابك للوصول إلى العطاءات",
        "en": "Sign in to reach your tenders",
    },
    "au.login_btn": {"ar": "دخول", "en": "Sign in"},
    "au.logout": {"ar": "خروج", "en": "Sign out"},
    "au.username": {"ar": "اسم المستخدم", "en": "Username"},
    "au.display_name": {"ar": "الاسم الظاهر", "en": "Display name"},
    "au.password": {"ar": "كلمة السر", "en": "Password"},
    "au.password_confirm": {"ar": "تأكيد كلمة السر", "en": "Confirm password"},
    "au.setup_title": {"ar": "تهيئة أول حساب", "en": "Create the first account"},
    "au.setup_subtitle": {
        "ar": "لا حساب في هذا النظام بعد",
        "en": "This system has no account yet",
    },
    "au.setup_hint": {
        "ar": "أول حساب هو مدير النظام، ومنه تُضاف بقية حسابات الفريق من الإعدادات.",
        "en": "The first account is the system administrator; the rest of the team is "
              "added from Settings.",
    },
    "au.setup_btn": {"ar": "إنشاء الحساب والدخول", "en": "Create account and sign in"},
    "au.cooldown_wait": {
        "ar": "⏳ محاولات كثيرة فاشلة — انتظر {seconds} ثانية.",
        "en": "⏳ Too many failed attempts — wait {seconds} seconds.",
    },
    "au.err_bad_credentials": {
        "ar": "❌ اسم المستخدم أو كلمة السر غير صحيحة.",
        "en": "❌ Incorrect username or password.",
    },
    "au.err_cooldown": {
        "ar": "❌ محاولات كثيرة فاشلة — أعد المحاولة بعد قليل.",
        "en": "❌ Too many failed attempts — try again shortly.",
    },
    "au.err_disabled": {
        "ar": "❌ هذا الحساب معطَّل. راجع مدير النظام.",
        "en": "❌ This account is disabled. Contact your administrator.",
    },
    "au.err_username_required": {
        "ar": "❌ اسم المستخدم مطلوب.",
        "en": "❌ A username is required.",
    },
    "au.err_username_taken": {
        "ar": "❌ اسم المستخدم مستعمل.",
        "en": "❌ That username is already taken.",
    },
    "au.err_password_short": {
        "ar": "❌ كلمة السر أقصر من ثمانية أحرف.",
        "en": "❌ The password is shorter than eight characters.",
    },
    "au.err_password_mismatch": {
        "ar": "❌ الكلمتان غير متطابقتين.",
        "en": "❌ The two passwords do not match.",
    },
    "au.err_current_password": {
        "ar": "❌ كلمة السر الحالية غير صحيحة.",
        "en": "❌ The current password is incorrect.",
    },
    "au.err_user_missing": {
        "ar": "❌ هذا المستخدم لم يعد موجوداً.",
        "en": "❌ That user no longer exists.",
    },
    "au.err_setup_done": {
        "ar": "❌ النظام مهيّأ أصلاً — ادخل بحسابك.",
        "en": "❌ The system is already set up — please sign in.",
    },

    # ── إدارة المستخدمين (13-2) / User management ──
    "us.title": {"ar": "👥 المستخدمون", "en": "👥 Users"},
    "us.hint": {
        "ar": "حساب لكل شخص في قسم العطاءات — لا حساب مشترك.",
        "en": "One account per person in the tender team — no shared accounts.",
    },
    "us.my_account": {"ar": "🙍 حسابي", "en": "🙍 My account"},
    "us.signed_in_as": {"ar": "داخل باسم: {username}", "en": "Signed in as: {username}"},
    "us.save_profile": {"ar": "حفظ الاسم الظاهر", "en": "Save display name"},
    "us.profile_saved": {"ar": "✅ حُفظ.", "en": "✅ Saved."},
    "us.change_password": {"ar": "تغيير كلمة السر", "en": "Change password"},
    "us.change_password_btn": {"ar": "تغيير الكلمة", "en": "Change password"},
    "us.current_password": {"ar": "كلمة السر الحالية", "en": "Current password"},
    "us.new_password": {"ar": "كلمة السر الجديدة", "en": "New password"},
    "us.password_changed": {"ar": "✅ تغيّرت كلمة السر.", "en": "✅ Password changed."},
    "us.add": {"ar": "إضافة مستخدم", "en": "Add a user"},
    "us.add_btn": {"ar": "إضافة", "en": "Add"},
    "us.added": {"ar": "✅ أُضيف المستخدم «{username}».", "en": "✅ User “{username}” added."},
    "us.manage": {"ar": "إدارة حساب قائم", "en": "Manage an existing account"},
    "us.pick_user": {"ar": "المستخدم", "en": "User"},
    "us.reset_password": {"ar": "كلمة سر جديدة", "en": "New password"},
    "us.reset_password_help": {
        "ar": "تصفير كلمة سر مستخدم لا يتطلّب معرفة كلمته القديمة.",
        "en": "Resetting a user's password does not require their old one.",
    },
    "us.reset_btn": {"ar": "تصفير الكلمة", "en": "Reset password"},
    "us.enable_btn": {"ar": "تفعيل", "en": "Enable"},
    "us.disable_btn": {"ar": "تعطيل", "en": "Disable"},
    "us.cannot_disable": {
        "ar": "لا يمكن تعطيل آخر حساب فعّال ولا حسابك أنت.",
        "en": "The last active account — and your own — cannot be disabled.",
    },
    "us.delete_confirm": {"ar": "أؤكّد الحذف", "en": "Confirm deletion"},
    "us.delete_btn": {"ar": "حذف", "en": "Delete"},
    "us.col_username": {"ar": "المستخدم", "en": "Username"},
    "us.col_display_name": {"ar": "الاسم الظاهر", "en": "Display name"},
    "us.col_role": {"ar": "الدور", "en": "Role"},
    "us.col_active": {"ar": "فعّال", "en": "Active"},
    "us.col_last_login": {"ar": "آخر دخول", "en": "Last sign-in"},

    # ── تجربة برومبت قبل الاعتماد (14-3) / Prompt trial ──
    "pt.title": {"ar": "🧪 تجربة قبل الاعتماد", "en": "🧪 Trial before adopting"},
    "pt.hint": {
        "ar": "يشغّل النصّين — الساري والمحرَّر — على المنافسة المفتوحة نفسها ويعرض "
              "الناتجين. لا يُحفظ شيء قبل أن تقرّر.",
        "en": "Runs both texts — the active one and your edit — on the same open tender "
              "and shows both outputs. Nothing is saved until you decide.",
    },
    "pt.needs_project": {
        "ar": "افتح منافسة فيها كراسة أولاً — التجربة على عرض حقيقي لا على نصّ مفترض.",
        "en": "Open a tender with an RFP first — the trial runs on a real bid, not a "
              "hypothetical one.",
    },
    "pt.fields": {"ar": "حقول القالب ({n})", "en": "Template fields ({n})"},
    "pt.fields_hint": {
        "ar": "مملوءة مما يعرفه النظام عن المنافسة المفتوحة، وقابلة للتعديل للتجربة وحدها.",
        "en": "Pre-filled from what the system knows about the open tender, and editable "
              "for the trial only.",
    },
    "pt.cost": {
        "ar": "التجربة استدعاءان لا واحد — تقدير المُدخل: {tokens} توكن.",
        "en": "A trial is two calls, not one — input estimate: {tokens} tokens.",
    },
    "pt.run": {"ar": "شغّل المقارنة", "en": "Run the comparison"},
    "pt.running": {"ar": "جارٍ تشغيل النصّين…", "en": "Running both texts…"},
    "pt.no_change": {
        "ar": "لا فرق بين النصّين — عدّل النص أولاً.",
        "en": "The two texts are identical — edit the text first.",
    },
    "pt.side_current": {"ar": "الناتج بالنص الساري", "en": "Output with the active text"},
    "pt.side_edited": {"ar": "الناتج بالنص المحرَّر", "en": "Output with your edit"},
    "pt.no_output": {
        "ar": "لا ناتج — فشل الاستدعاء أو تعذّر ملء الحقول.",
        "en": "No output — the call failed or the fields could not be filled.",
    },
    "pt.decide": {
        "ar": "إن أقنعك الناتج المحرَّر فاحفظه أدناه؛ وإلا اترك الافتراضي كما هو.",
        "en": "If the edited output convinces you, save it below; otherwise leave the "
              "current text as it is.",
    },
    "audit.act_prompt.trial": {"ar": "تجربة تعليمات", "en": "Prompt trialled"},

    # ── إدارة البرومبتات (14-1) / Prompt management ──
    "pm.title": {"ar": "🧠 تعليمات النموذج", "en": "🧠 Model prompts"},
    "pm.hint": {
        "ar": "تعديل التعليمات يسري فوراً بلا إعادة تشغيل. الافتراضي محفوظ في الشيفرة "
              "ويُستعاد بنقرة.",
        "en": "Edits apply immediately, with no restart. The default lives in the code "
              "and is restored with one click.",
    },
    "pm.prompt": {"ar": "التعليمات", "en": "Prompt"},
    "pm.text": {"ar": "النص", "en": "Text"},
    "pm.sector": {"ar": "القطاع", "en": "Sector"},
    "pm.sector_ph": {"ar": "اتركه فارغاً لكل القطاعات", "en": "Leave empty for all sectors"},
    "pm.sector_help": {
        "ar": "نصّ لقطاع بعينه يغلب النص العام عند العمل على منافسة من ذلك القطاع.",
        "en": "A sector-specific text overrides the general one when working on a "
              "tender in that sector.",
    },
    "pm.all_sectors": {"ar": "كل القطاعات", "en": "All sectors"},
    "pm.agent_write": {"ar": "كتابة", "en": "Writing"},
    "pm.agent_extract": {"ar": "استخراج", "en": "Extraction"},
    "pm.agent_review": {"ar": "مراجعة", "en": "Review"},
    "pm.default_in_use": {
        "ar": "النص الافتراضي ساري — لم يُعدَّل.",
        "en": "The default text is in use — not edited.",
    },
    "pm.overridden": {
        "ar": "✏️ نص معدَّل (الإصدار {version}) — {who} · {when}",
        "en": "✏️ Edited text (version {version}) — {who} · {when}",
    },
    "pm.save": {"ar": "حفظ التعديل", "en": "Save edit"},
    "pm.saved": {"ar": "✅ حُفظ — الإصدار {version}.", "en": "✅ Saved — version {version}."},
    "pm.reset": {"ar": "استعادة الافتراضي", "en": "Restore default"},
    "pm.reset_done": {"ar": "✅ عاد النص الافتراضي.", "en": "✅ The default text is back."},
    "pm.version": {"ar": "الإصدار", "en": "Version"},
    "pm.overrides": {"ar": "التعليمات المعدَّلة ({n})", "en": "Edited prompts ({n})"},
    "pm.fixed_rules": {"ar": "القواعد الثابتة — للعرض فقط", "en": "Fixed rules — read-only"},
    "pm.fixed_rules_hint": {
        "ar": "تُلحق بكل استدعاء بعد التعليمات أعلاه، ولا يمكن تعديلها ولا إزالتها "
              "بأي نص تكتبه هنا.",
        "en": "Appended to every call after the prompt above. No text you write here "
              "can change or remove them.",
    },
    "pm.missing_fields": {
        "ar": "⚠️ حقول غابت عن نصّك: {fields} — ما تحمله من سياق لن يصل النموذج.",
        "en": "⚠️ Fields missing from your text: {fields} — the context they carry "
              "will not reach the model.",
    },
    "pm.err_empty": {"ar": "❌ النص فارغ.", "en": "❌ The text is empty."},
    "pm.err_unknown_fields": {
        "ar": "❌ حقول لا يعرفها النظام: {fields} — ستُسقط التوليد وقت التشغيل.",
        "en": "❌ Fields the system does not know: {fields} — they would break "
              "generation at run time.",
    },
    "audit.act_prompt.edit": {"ar": "تعديل تعليمات", "en": "Prompt edited"},
    "audit.act_prompt.reset": {"ar": "استعادة تعليمات افتراضية", "en": "Prompt reset"},

    # ── سياسة البيانات الشخصية (13-10) / Personal-data policy ──
    "pd.title": {"ar": "🧑 سياسة البيانات الشخصية", "en": "🧑 Personal-data policy"},
    "pd.hint": {
        "ar": "رفع السير الذاتية يُدخل النظام في نطاق نظام حماية البيانات الشخصية: "
              "أساس معلن للمعالجة، ومدة احتفاظ، وحذف عند الطلب.",
        "en": "Uploading CVs brings this system under personal-data protection rules: "
              "a declared basis for processing, a retention period, and erasure on request.",
    },
    "pd.basis": {"ar": "أساس المعالجة", "en": "Basis for processing"},
    "pd.basis_contract": {"ar": "تنفيذ عقد", "en": "Performance of a contract"},
    "pd.basis_consent": {"ar": "موافقة صريحة", "en": "Explicit consent"},
    "pd.basis_legitimate_interest": {"ar": "مصلحة مشروعة", "en": "Legitimate interest"},
    "pd.retention": {"ar": "مدة الاحتفاظ (بالأشهر)", "en": "Retention period (months)"},
    "pd.retention_help": {
        "ar": "بعدها تُعرض السير لحذفها. صفر يعني بلا حدّ معلن.",
        "en": "After this, CVs are listed for deletion. Zero means no declared limit.",
    },
    "pd.retention_unlimited": {
        "ar": "⚠️ لا حدّ معلن للاحتفاظ — إعلانه أصدق من حذف صامت، لكنه يبقى قراراً.",
        "en": "⚠️ No declared retention limit — declaring that is more honest than "
              "silent deletion, but it remains a decision.",
    },
    "pd.save_policy": {"ar": "حفظ السياسة", "en": "Save policy"},
    "pd.policy_saved": {"ar": "✅ حُفظت السياسة.", "en": "✅ Policy saved."},
    "pd.expired": {"ar": "السير المتجاوزة للمدة ({n})", "en": "CVs past the retention period ({n})"},
    "pd.expired_hint": {
        "ar": "هذه السير مضى عليها أكثر من {months} شهراً.",
        "en": "These CVs are older than {months} months.",
    },
    "pd.expired_none": {
        "ar": "لا سير تجاوزت المدة.",
        "en": "No CVs are past the retention period.",
    },
    "pd.delete_expired": {"ar": "حذف السير المتجاوزة", "en": "Delete expired CVs"},
    "pd.expired_deleted": {"ar": "✅ حُذفت {n} سيرة.", "en": "✅ Deleted {n} CV(s)."},
    "pd.erase": {"ar": "حذف بيانات شخص عند الطلب", "en": "Erase a person's data on request"},
    "pd.erase_hint": {
        "ar": "يحذف صفّ الشخص في سجل الكوادر وسيرته ومقاطعها من المستودع. لا رجعة فيه.",
        "en": "Deletes the person's row in the personnel registry, their CV, and its "
              "chunks in the repository. It cannot be undone.",
    },
    "pd.person": {"ar": "الشخص", "en": "Person"},
    "pd.footprint": {
        "ar": "سيُحذف: {records} صفّاً · {documents} مستنداً · {chunks} مقطعاً.",
        "en": "Will delete: {records} row(s) · {documents} document(s) · {chunks} chunk(s).",
    },
    "pd.erase_confirm": {"ar": "أؤكّد الحذف النهائي", "en": "Confirm permanent erasure"},
    "pd.erase_btn": {"ar": "حذف بياناته", "en": "Erase their data"},
    "pd.erased": {
        "ar": "✅ حُذفت بيانات {name}: {documents} مستنداً و {chunks} مقطعاً.",
        "en": "✅ Erased {name}'s data: {documents} document(s) and {chunks} chunk(s).",
    },
    "pd.no_people": {
        "ar": "سجل الكوادر فارغ.",
        "en": "The personnel registry is empty.",
    },
    "pd.cv_owner": {"ar": "صاحب السيرة", "en": "CV owner"},
    "pd.cv_owner_none": {"ar": "غير محدَّد", "en": "Not specified"},
    "pd.cv_owner_help": {
        "ar": "ربط السيرة بصاحبها يجعل حذف بياناته لاحقاً كاملاً لا تخميناً بالاسم.",
        "en": "Linking a CV to its owner makes erasing their data later complete, "
              "rather than a guess based on the file name.",
    },
    "rec.p_basis": {"ar": "أساس المعالجة", "en": "Processing basis"},
    "audit.act_pd.policy": {"ar": "تغيير سياسة البيانات", "en": "Data policy changed"},
    "audit.act_pd.erase": {"ar": "حذف بيانات شخص", "en": "Personal data erased"},

    # ── النسخ الاحتياطي (13-9) / Backup & restore ──
    "bk.title": {"ar": "🗄️ نسخة احتياطية واسترجاع", "en": "🗄️ Backup & restore"},
    "bk.hint": {
        "ar": "نسخة من القاعدة كاملةً: المنافسات وملف الشركة والمعرفة والمستخدمون "
              "والسجل والاعتمادات.",
        "en": "A copy of the whole database: tenders, company profile, knowledge "
              "repository, users, audit trail, and approvals.",
    },
    "bk.password": {"ar": "كلمة تشفير النسخة (اختيارية)", "en": "Backup password (optional)"},
    "bk.password_help": {
        "ar": "بكلمة تُشفَّر النسخة ولا تُفتح بدونها — ولا سبيل لاستعادتها إن نُسيت. "
              "بلا كلمة تخرج ملف SQLite يفتحه أي عميل.",
        "en": "With a password the backup is encrypted and cannot be opened without it "
              "— and it cannot be recovered if forgotten. Without one it is a plain "
              "SQLite file any client can open.",
    },
    "bk.build": {"ar": "إنشاء النسخة", "en": "Create backup"},
    "bk.download": {"ar": "تنزيل النسخة", "en": "Download backup"},
    "bk.size": {"ar": "حجم النسخة: {kb} كيلوبايت", "en": "Backup size: {kb} KB"},
    "bk.no_crypto": {
        "ar": "مكتبة التشفير غير مركَّبة — النسخ والاسترجاع يعملان بلا تشفير. "
              "للتشفير: pip install cryptography",
        "en": "The encryption library is not installed — backup and restore work "
              "unencrypted. For encryption: pip install cryptography",
    },
    "bk.restore": {"ar": "استرجاع نسخة", "en": "Restore a backup"},
    "bk.restore_warn": {
        "ar": "⚠️ الاسترجاع يستبدل كل ما في النظام الآن بما في النسخة، ويُخرجك من جلستك.",
        "en": "⚠️ Restoring replaces everything currently in the system with the "
              "backup's contents, and signs you out.",
    },
    "bk.restore_upload": {"ar": "ملف النسخة", "en": "Backup file"},
    "bk.restore_password": {"ar": "كلمة فكّ التشفير", "en": "Decryption password"},
    "bk.restore_confirm": {"ar": "أؤكّد الاستبدال", "en": "Confirm replacement"},
    "bk.restore_btn": {"ar": "استرجاع", "en": "Restore"},
    "bk.restored": {"ar": "✅ استُرجعت النسخة — سجّل الدخول من جديد.", "en": "✅ Backup restored — please sign in again."},
    "bk.file_info": {"ar": "الملف: {kb} كيلوبايت · {state}", "en": "File: {kb} KB · {state}"},
    "bk.encrypted": {"ar": "مشفَّر", "en": "encrypted"},
    "bk.plain": {"ar": "غير مشفَّر", "en": "not encrypted"},
    "bk.err_password_short": {
        "ar": "❌ كلمة التشفير أقصر من ثمانية أحرف.",
        "en": "❌ The backup password is shorter than eight characters.",
    },
    "bk.err_password_needed": {
        "ar": "❌ النسخة مشفَّرة — أدخل كلمة فكّ التشفير.",
        "en": "❌ This backup is encrypted — enter its password.",
    },
    "bk.err_bad_password": {
        "ar": "❌ الكلمة خاطئة أو النسخة عُبث بها.",
        "en": "❌ Wrong password, or the backup was tampered with.",
    },
    "bk.err_not_backup": {
        "ar": "❌ هذا الملف ليس نسخة صالحة من قاعدة النظام.",
        "en": "❌ This file is not a valid backup of the system database.",
    },
    "bk.err_empty": {"ar": "❌ الملف فارغ.", "en": "❌ The file is empty."},
    "bk.err_no_crypto": {
        "ar": "❌ التشفير يتطلّب مكتبة cryptography.",
        "en": "❌ Encryption requires the cryptography library.",
    },
    "audit.act_backup.create": {"ar": "إنشاء نسخة احتياطية", "en": "Backup created"},
    "audit.act_backup.restore": {"ar": "استرجاع نسخة احتياطية", "en": "Backup restored"},

    # ── سير الاعتماد (13-8) / Approval workflow ──
    "ap.title": {"ar": "✅ اعتماد التسليم", "en": "✅ Delivery approval"},
    "ap.hint": {
        "ar": "ثلاث مراحل بترتيبها. الاعتماد يخصّ نسخة العرض التي اعتُمدت — أي تعديل بعده يُسقطه.",
        "en": "Three stages in order. An approval covers the exact version it was given "
              "to — any later edit drops it.",
    },
    "ap.stage_bid_manager": {"ar": "مدير العطاءات", "en": "Bid manager"},
    "ap.stage_finance": {"ar": "المالية", "en": "Finance"},
    "ap.stage_final": {"ar": "الاعتماد النهائي", "en": "Final approval"},
    "ap.approve": {"ar": "اعتماد", "en": "Approve"},
    "ap.reject": {"ar": "ردّ", "en": "Reject"},
    "ap.note": {"ar": "ملاحظة", "en": "Note"},
    "ap.note_ph": {"ar": "سبب الردّ أو ملاحظة الاعتماد…", "en": "Reason or remark…"},
    "ap.not_yet": {"ar": "لم تُعتمد بعد.", "en": "Not approved yet."},
    "ap.approved_by": {
        "ar": "✅ اعتمدها {who} — {when}",
        "en": "✅ Approved by {who} — {when}",
    },
    "ap.rejected_by": {
        "ar": "⛔ ردّها {who} — {when} · {note}",
        "en": "⛔ Rejected by {who} — {when} · {note}",
    },
    "ap.stale": {
        "ar": "⚠️ سقط اعتماد {who} ({when}) — العرض تغيّر بعده.",
        "en": "⚠️ {who}'s approval ({when}) lapsed — the proposal changed after it.",
    },
    "ap.pending": {
        "ar": "⏳ المرحلة المطلوبة الآن: {stage}",
        "en": "⏳ Stage required now: {stage}",
    },
    "ap.complete": {
        "ar": "✅ المراحل الثلاث معتمَدة على النسخة الحالية — التسليم مفتوح.",
        "en": "✅ All three stages approved for the current version — delivery is open.",
    },
    "ap.locked": {
        "ar": "المرحلة مقفلة: إمّا لا تملك صلاحيتها أو لم تُعتمد المرحلة التي قبلها.",
        "en": "Stage locked: either you lack its permission or the previous stage is "
              "not approved.",
    },
    "ap.revision_hint": {
        "ar": "الاعتماد يُسجَّل على نسخة العرض رقم {revision}.",
        "en": "Approvals are recorded against proposal version {revision}.",
    },
    "ap.on_revision": {"ar": "على النسخة {revision}", "en": "on version {revision}"},
    "ap.history": {"ar": "سجل القرارات ({n})", "en": "Decision history ({n})"},
    "ap.no_project": {
        "ar": "افتح منافسة أولاً — الاعتماد يخصّ منافسة بعينها.",
        "en": "Open a tender first — approval belongs to a specific tender.",
    },
    "ap.export_blocked": {
        "ar": "🔒 التصدير محجوب: المرحلة «{stage}» لم تُعتمد على النسخة الحالية.",
        "en": "🔒 Export blocked: stage “{stage}” is not approved for the current version.",
    },
    "ap.export_needs_project": {
        "ar": "🔒 التصدير النهائي يتطلّب منافسة مفتوحة باعتماد مسجَّل.",
        "en": "🔒 Final export requires an open tender with a recorded approval.",
    },
    "audit.act_approval.decision": {"ar": "قرار اعتماد", "en": "Approval decision"},

    # ── تعارض الحفظ (13-7) / Save conflicts ──
    "proj.merged_clean": {
        "ar": "🔀 كتبت جلسة أخرى على هذه المنافسة، ودُمج تعديلك معها ({n} حقلاً) بلا تعارض.",
        "en": "🔀 Another session wrote to this tender; your {n} change(s) were merged "
              "with no conflict.",
    },
    "proj.merged_with_clash": {
        "ar": "⚠️ كتبت جلسة أخرى على هذه المنافسة. دُمج {n} حقلاً، وتعارض: {fields} — "
              "اعتُمدت نسختهم، ونصّك محفوظ في نسخ القسم ويمكن استرجاعه.",
        "en": "⚠️ Another session wrote to this tender. {n} field(s) merged; conflicting: "
              "{fields} — their version was kept, and yours is saved in the section "
              "versions and can be restored.",
    },
    "proj.merge_busy": {
        "ar": "جلسات أخرى تكتب على هذه المنافسة الآن — لم يُحفظ تعديلك بعد، وهو باق أمامك.",
        "en": "Other sessions are writing to this tender right now — your change is not "
              "saved yet, and is still in front of you.",
    },
    "audit.act_project.merge": {"ar": "دمج تعارض حفظ", "en": "Save conflict merged"},

    # ── نسخ الأقسام (13-6) / Section versions ──
    "db.versions": {"ar": "🕘 النسخ ({n})", "en": "🕘 Versions ({n})"},
    "db.versions_empty": {
        "ar": "لا نسخ بعد — تُحفظ نسخة عند كل كتابة على القسم.",
        "en": "No versions yet — one is saved on every write to this section.",
    },
    "db.versions_hint": {
        "ar": "آخر {limit} نسخة محفوظة، الأحدث أولاً. الاسترجاع يحفظ النص الحالي نسخةً قبل استبداله.",
        "en": "The latest {limit} versions, newest first. Restoring saves the current "
              "text as a version before replacing it.",
    },
    "db.versions_pick": {"ar": "النسخة", "en": "Version"},
    "db.versions_diff": {
        "ar": "الفرق بين النسخة المختارة والنص الحالي:",
        "en": "Difference between the selected version and the current text:",
    },
    "db.versions_same": {
        "ar": "هذه النسخة مطابقة للنص الحالي.",
        "en": "This version matches the current text.",
    },
    "db.versions_restore": {"ar": "استرجاع هذه النسخة", "en": "Restore this version"},
    "db.versions_restore_help": {
        "ar": "الاسترجاع لمالك القسم، ولا يعمل إن كانت النسخة مطابقة للنص الحالي.",
        "en": "Restoring is for the section owner, and does nothing when the version "
              "matches the current text.",
    },
    "db.versions_restored": {"ar": "✅ استُرجعت النسخة.", "en": "✅ Version restored."},
    "audit.act_section.restore": {"ar": "استرجاع نسخة", "en": "Version restored"},

    # ── سجل التدقيق (13-5) / Audit trail ──
    "ad2.title": {"ar": "🧾 سجل التدقيق", "en": "🧾 Audit trail"},
    "ad2.hint": {
        "ar": "من غيّر ماذا ومتى، وأي نص مصدره النموذج. يُقرأ ولا يُحرَّر.",
        "en": "Who changed what and when, and which text came from the model. "
              "Read-only by design.",
    },
    "ad2.all": {"ar": "الكل", "en": "All"},
    "ad2.filter_project": {"ar": "المنافسة", "en": "Tender"},
    "ad2.filter_user": {"ar": "المستخدم", "en": "User"},
    "ad2.col_when": {"ar": "الوقت", "en": "When"},
    "ad2.col_who": {"ar": "من", "en": "Who"},
    "ad2.col_what": {"ar": "الحدث", "en": "Event"},
    "ad2.col_target": {"ar": "الهدف", "en": "Target"},
    "ad2.col_source": {"ar": "المصدر", "en": "Source"},
    "ad2.unknown_user": {"ar": "غير معروف", "en": "Unknown"},
    "ad2.empty": {"ar": "لا أحداث مسجَّلة بعد.", "en": "No events recorded yet."},
    "ad2.total": {"ar": "إجمالي الأحداث المسجَّلة: {n}", "en": "Total recorded events: {n}"},
    "db.source_ai": {
        "ar": "🤖 النص الحالي مصدره النموذج",
        "en": "🤖 The current text came from the model",
    },
    "db.source_human": {
        "ar": "✍️ النص الحالي حرّره إنسان",
        "en": "✍️ The current text was edited by a person",
    },
    "audit.act_project.create": {"ar": "إنشاء منافسة", "en": "Tender created"},
    "audit.act_project.delete": {"ar": "حذف منافسة", "en": "Tender deleted"},
    "audit.act_project.duplicate": {"ar": "نسخ منافسة", "en": "Tender duplicated"},
    "audit.act_project.outcome": {"ar": "تسجيل نتيجة", "en": "Outcome recorded"},
    "audit.act_section.generate": {"ar": "توليد قسم", "en": "Section generated"},
    "audit.act_section.refine": {"ar": "تنقيح قسم", "en": "Section refined"},
    "audit.act_section.edit": {"ar": "تحرير قسم", "en": "Section edited"},
    "audit.act_section.assign": {"ar": "إسناد قسم", "en": "Section assigned"},
    "audit.act_section.status": {"ar": "تغيير حالة قسم", "en": "Section status changed"},
    "audit.act_outline.propose": {"ar": "اقتراح هيكل", "en": "Outline proposed"},
    "audit.act_export.build": {"ar": "بناء مستند", "en": "Document built"},
    "audit.act_user.add": {"ar": "إضافة مستخدم", "en": "User added"},
    "audit.act_user.role": {"ar": "تغيير دور", "en": "Role changed"},
    "audit.act_user.active": {"ar": "تفعيل/تعطيل حساب", "en": "Account enabled/disabled"},
    "audit.act_user.delete": {"ar": "حذف مستخدم", "en": "User deleted"},
    "audit.act_user.password": {"ar": "تغيير كلمة سر", "en": "Password changed"},
    "audit.act_auth.login": {"ar": "تسجيل دخول", "en": "Signed in"},

    # ── إسناد الأقسام (13-4) / Section assignment ──
    "db.owner": {"ar": "مالك القسم", "en": "Section owner"},
    "db.owner_none": {"ar": "غير مُسند", "en": "Unassigned"},
    "db.owner_gone": {"ar": "مالك لم يعد متاحاً", "en": "Owner no longer available"},
    "db.owner_help": {
        "ar": "المُسند إليه وحده يعدّل هذا القسم. القسم غير المُسند متاح لكل من يكتب.",
        "en": "Only the assignee may edit this section. An unassigned section is open "
              "to anyone who writes.",
    },
    "db.owner_locked": {
        "ar": "الإسناد لمدير العطاءات ومدير النظام.",
        "en": "Assignment is for the bid manager and the system administrator.",
    },
    "db.owned_by_other": {
        "ar": "🔒 هذا القسم مُسند إلى {name} — للعرض فقط بالنسبة لك.",
        "en": "🔒 This section is assigned to {name} — read-only for you.",
    },
    "db.status": {"ar": "الحالة", "en": "Status"},
    "db.status_todo": {"ar": "لم يبدأ", "en": "Not started"},
    "db.status_in_progress": {"ar": "قيد الكتابة", "en": "In progress"},
    "db.status_ready": {"ar": "جاهز للمراجعة", "en": "Ready for review"},
    "db.board": {"ar": "🗂️ لوحة الأقسام", "en": "🗂️ Section board"},
    "db.board_hint": {
        "ar": "من يكتب ماذا، وأين وصل — بلا فتح كل قسم على حدة.",
        "en": "Who writes what, and how far along — without opening each section.",
    },
    "db.board_section": {"ar": "القسم", "en": "Section"},
    "db.board_owner": {"ar": "المالك", "en": "Owner"},
    "db.board_status": {"ar": "الحالة", "en": "Status"},
    "db.board_text": {"ar": "النص", "en": "Text"},
    "db.board_unassigned": {
        "ar": "⚠️ {n} قسماً بلا مالك.",
        "en": "⚠️ {n} section(s) without an owner.",
    },

    # ── الأدوار (13-3) / Roles ──
    "role.admin": {"ar": "مدير النظام", "en": "System administrator"},
    "role.bid_manager": {"ar": "مدير العطاءات", "en": "Bid manager"},
    "role.writer": {"ar": "كاتب", "en": "Writer"},
    "role.reviewer": {"ar": "مراجع", "en": "Reviewer"},
    "role.viewer": {"ar": "مطّلع", "en": "Viewer"},
    "role.admin_hint": {
        "ar": "كل شيء: المفاتيح · المستخدمون · البيانات · المنافسات.",
        "en": "Everything: API keys, users, data, and tenders.",
    },
    "role.bid_manager_hint": {
        "ar": "يملك المنافسة: يحذفها ويعدّل ملف الشركة ويصدّر — بلا مفاتيح ولا مستخدمين.",
        "en": "Owns the tender: deletes it, edits the company profile, exports — "
              "no API keys, no user management.",
    },
    "role.writer_hint": {
        "ar": "يكتب الأقسام ويملأ الجداول ويصدّر — لا يحذف منافسة ولا يرى المفاتيح.",
        "en": "Writes sections, fills the tables, exports — cannot delete a tender "
              "or see API keys.",
    },
    "role.reviewer_hint": {
        "ar": "يشغّل لجنة المراجعة ويقرأ كل شيء — لا يكتب نص الأقسام.",
        "en": "Runs the review committee and reads everything — does not write "
              "section text.",
    },
    "role.viewer_hint": {
        "ar": "قراءة فقط — بلا كتابة ولا تصدير ولا استدعاء نموذج.",
        "en": "Read only — no writing, no export, no model calls.",
    },
    "role.help": {
        "ar": "الدور يحدّد ما يستطيع هذا الحساب فعله. الافتراضي هو الأقل صلاحية.",
        "en": "The role decides what this account may do. The default is the "
              "least-privileged one.",
    },
    "role.forbidden": {
        "ar": "🔒 دورك لا يسمح بهذا الإجراء.",
        "en": "🔒 Your role does not allow this action.",
    },
    "role.settings_admin_only": {
        "ar": "🔒 مفاتيح الموفّرين وإعدادات النماذج وحدّ الإنفاق لمدير النظام وحده.",
        "en": "🔒 Provider keys, model settings, and the spend limit are for the "
              "system administrator only.",
    },
    "role.data_manager_only": {
        "ar": "🔒 تصدير مساحة العمل واستيرادها ومسحها لمدير النظام ومدير العطاءات.",
        "en": "🔒 Exporting, importing, and clearing the workspace are for the "
              "system administrator and the bid manager.",
    },
    "role.company_read_only": {
        "ar": "🔒 ملف الشركة وسجلاتها ومستودع معرفتها للعرض فقط بدورك الحالي.",
        "en": "🔒 With your role the company profile, registries, and knowledge "
              "repository are read-only.",
    },
    "role.project_read_only": {
        "ar": "🔒 المنافسة للعرض فقط بدورك الحالي — لا رفع مرفقات ولا تعديل.",
        "en": "🔒 With your role this tender is read-only — no uploads, no edits.",
    },
    "role.export_forbidden": {
        "ar": "🔒 دورك لا يسمح بتصدير العرض.",
        "en": "🔒 Your role does not allow exporting the proposal.",
    },
    "au.err_unknown_role": {"ar": "❌ دور غير معروف.", "en": "❌ Unknown role."},
    "au.err_forbidden": {
        "ar": "❌ دورك لا يسمح بهذا الإجراء.",
        "en": "❌ Your role does not allow this action.",
    },
    "au.err_last_admin": {
        "ar": "❌ لا يمكن تغيير دور آخر مدير نظام فعّال ولا دورك أنت.",
        "en": "❌ The last active administrator — and your own role — cannot be changed.",
    },
    "us.save_role": {"ar": "حفظ الدور", "en": "Save role"},
    "us.role_saved": {"ar": "✅ تغيّر الدور.", "en": "✅ Role changed."},
    "us.cannot_change_role": {
        "ar": "لا يُغيَّر دور آخر مدير نظام فعّال ولا دورك أنت.",
        "en": "The last active administrator's role — and your own — cannot be changed.",
    },

    # ── مكتبة المحتوى المعتمد (14-4) / Approved content library ──
    "lib.title": {"ar": "مكتبة المحتوى المعتمد", "en": "Approved content library"},
    "lib.intro": {
        "ar": "كتل نصّية جاهزة تُدرَج في أقسام العرض كما هي — بلا استدعاء نموذج "
              "وبلا كلفة توكن. المعتمد وحده يُدرَج.",
        "en": "Ready-made text blocks inserted into proposal sections as-is — no "
              "model call and no token cost. Only approved blocks can be inserted.",
    },
    "lib.read_only": {
        "ar": "دورك يقرأ المكتبة ولا يحرّرها.",
        "en": "Your role can read the library but not edit it.",
    },
    "lib.empty": {
        "ar": "المكتبة فارغة. أضِف كتلة أولى ليُعاد استخدامها في كل عرض.",
        "en": "The library is empty. Add a first block to reuse across proposals.",
    },
    "lib.add": {"ar": "كتلة جديدة", "en": "New block"},
    "lib.key": {"ar": "المفتاح", "en": "Key"},
    "lib.key_help": {
        "ar": "معرّف ثابت لا يتغيّر — به تُعرَف الكتلة ولو تغيّر عنوانها.",
        "en": "A stable identifier — it names the block even if the title changes.",
    },
    "lib.key_taken": {"ar": "❌ المفتاح مستعمل.", "en": "❌ Key already in use."},
    "lib.key_required": {
        "ar": "❌ المفتاح والعنوان والنصّ مطلوبة.",
        "en": "❌ Key, title and body are required.",
    },
    "lib.block_title": {"ar": "العنوان", "en": "Title"},
    "lib.body": {"ar": "نصّ الكتلة", "en": "Block body"},
    "lib.category": {"ar": "التصنيف", "en": "Category"},
    "lib.sector": {"ar": "القطاع", "en": "Sector"},
    "lib.language": {"ar": "اللغة", "en": "Language"},
    "lib.any": {"ar": "الكل", "en": "Any"},
    "lib.status": {"ar": "الحالة", "en": "Status"},
    "lib.status_draft": {"ar": "مسودّة", "en": "Draft"},
    "lib.status_approved": {"ar": "معتمدة", "en": "Approved"},
    "lib.status_retired": {"ar": "مسحوبة", "en": "Retired"},
    "lib.review_months": {"ar": "دورة المراجعة (أشهر)", "en": "Review cycle (months)"},
    "lib.review_months_help": {
        "ar": "صفر = بلا دورة معلنة فلا تتأخّر الكتلة.",
        "en": "Zero means no declared cycle, so the block never falls due.",
    },
    "lib.reviewed_at": {"ar": "آخر مراجعة", "en": "Last reviewed"},
    "lib.never_reviewed": {"ar": "لم تُراجَع", "en": "Never reviewed"},
    "lib.review_due": {
        "ar": "⚠️ تأخّرت عن مراجعتها — راجِع نصّها قبل الاعتماد عليه.",
        "en": "⚠️ Review overdue — check the text before relying on it.",
    },
    "lib.mark_reviewed": {"ar": "راجعتُها ولم تتغيّر", "en": "Reviewed, unchanged"},
    "lib.reviewed_done": {"ar": "✅ جُدّد تاريخ المراجعة.", "en": "✅ Review date renewed."},
    "lib.approve": {"ar": "اعتماد", "en": "Approve"},
    "lib.approved_done": {"ar": "✅ اعتُمدت الكتلة.", "en": "✅ Block approved."},
    "lib.retire": {"ar": "سحب", "en": "Retire"},
    "lib.retired_done": {"ar": "✅ سُحبت الكتلة.", "en": "✅ Block retired."},
    "lib.to_draft": {"ar": "إعادة إلى المسودّة", "en": "Back to draft"},
    "lib.cannot_approve": {
        "ar": "الاعتماد لمدير العطاءات ومدير النظام — الكاتب يقترح ولا يعتمد نصّه.",
        "en": "Approval is for bid managers and administrators — a writer proposes "
              "but does not approve their own text.",
    },
    "lib.saved": {"ar": "✅ حُفظت الكتلة.", "en": "✅ Block saved."},
    "lib.deleted": {"ar": "✅ حُذفت الكتلة.", "en": "✅ Block deleted."},
    "lib.edit_resets": {
        "ar": "⚠️ تغيير النصّ يُسقط الاعتماد إلى مسودّة — المعتمَد هو النصّ الذي قُرئ.",
        "en": "⚠️ Changing the body drops approval back to draft — what was approved "
              "is the text that was read.",
    },
    "lib.used_count": {"ar": "أُدرجت {count} مرة", "en": "Inserted {count} time(s)"},
    "lib.stats": {
        "ar": "{total} كتلة · {approved} معتمدة · {due} متأخّرة عن المراجعة",
        "en": "{total} blocks · {approved} approved · {due} overdue for review",
    },

    # ── إدراج كتلة في قسم (14-4) / Inserting a block ──
    "lib.insert_title": {"ar": "إدراج كتلة معتمدة", "en": "Insert an approved block"},
    "lib.insert_help": {
        "ar": "تُلحَق بنصّ القسم كما هي — بلا استدعاء نموذج.",
        "en": "Appended to the section text as-is — with no model call.",
    },
    "lib.pick": {"ar": "الكتلة", "en": "Block"},
    "lib.insert": {"ar": "إدراج", "en": "Insert"},
    "lib.inserted": {"ar": "✅ أُدرجت الكتلة في القسم.", "en": "✅ Block inserted into the section."},
    "lib.none_approved": {
        "ar": "لا كتلة معتمدة تناسب هذا القسم بعد — تُضاف من ملف الشركة.",
        "en": "No approved block fits this section yet — add one from the company file.",
    },
    "lib.preview": {"ar": "معاينة", "en": "Preview"},

    # ── نماذج الجهات (ب-4) / Per-entity Word templates ──
    "et.title": {"ar": "نماذج الجهات", "en": "Entity form templates"},
    "et.hint": {
        "ar": "بعض الجهات ترفض عرضاً بغير نموذجها — رفضاً شكلياً لا علاقة له "
              "بجودة المحتوى. النموذج المحفوظ هنا يُختار تلقائياً عند التصدير "
              "حسب جهة المنافسة، وقالب الشركة يبقى للباقي.",
        "en": "Some entities reject a proposal that is not on their own form — a "
              "formal rejection unrelated to content quality. A template saved "
              "here is picked automatically at export based on the tender's "
              "entity; the company template covers the rest.",
    },
    "et.entity": {"ar": "الجهة", "en": "Entity"},
    "et.entity_new": {"ar": "— جهة أخرى —", "en": "— another entity —"},
    "et.entity_name": {"ar": "اسم الجهة", "en": "Entity name"},
    "et.entity_name_help": {
        "ar": "يُطابَق بتوحيد الإملاء نفسه في ذاكرة العطاءات: «وزارة الصحة» "
              "و«وزاره الصحه» جهة واحدة.",
        "en": "Matched with the same name normalisation used by the bid memory: "
              "spelling variants resolve to one entity.",
    },
    "et.upload": {"ar": "ملف النموذج (docx)", "en": "Template file (docx)"},
    "et.save": {"ar": "حفظ النموذج", "en": "Save template"},
    "et.saved": {"ar": "✅ حُفظ نموذج «{entity}».", "en": "✅ Saved the template for \"{entity}\"."},
    "et.empty": {
        "ar": "لا نموذج جهة محفوظ — التصدير يستعمل قالب الشركة.",
        "en": "No entity template saved — export uses the company template.",
    },
    "et.count": {"ar": "{n} نموذجاً محفوظاً.", "en": "{n} template(s) saved."},

    "db.template_entity_on": {
        "ar": "✅ سيُصدَّر بنموذج **{entity}**.",
        "en": "✅ Will export on the **{entity}** form.",
    },
    "db.template_no_entity_form": {
        "ar": "لا نموذج محفوظ لـ «{entity}» — يُضاف من ملف الشركة إن كانت تفرض شكلها.",
        "en": "No template saved for \"{entity}\" — add one from the company page "
              "if that entity mandates its own form.",
    },
    "db.force_company_template": {
        "ar": "استعمل قالب الشركة بدل نموذج الجهة",
        "en": "Use the company template instead of the entity form",
    },
    "db.force_company_help": {
        "ar": "نموذج جهة قديم أسوأ من غيابه — القرار بيدك.",
        "en": "An outdated entity form is worse than none — the choice is yours.",
    },
    "db.template_company_forced": {
        "ar": "سيُصدَّر بقالب الشركة بطلبك، لا بنموذج الجهة.",
        "en": "Will export on the company template at your request, not the entity form.",
    },

    # ── الموصّلات الخارجية (14-10) / External connectors ──
    "cn.title": {"ar": "الموصّلات الخارجية", "en": "External connectors"},
    "cn.hint": {
        "ar": "ربط بنظام خارجي لسحب العملاء والمنتجات والموظفين إلى سجلات الأدلة.",
        "en": "Connect an external system to pull customers, products and employees "
              "into the evidence registries.",
    },
    "cn.egress_warning": {
        "ar": "⚠️ هذه أول قناة تُخرج بيانات من جهازك إلى خادم لا نملكه. "
              "بيانات الاعتماد لمدير النظام وحده، ولا تصل النموذج بأي مسار.",
        "en": "⚠️ This is the first channel that sends data from your machine to a "
              "server we do not own. Credentials are for administrators only, and "
              "never reach the model by any path.",
    },
    "cn.pull_only": {
        "ar": "🔒 **سحب فقط.** الدفع (تحويل الفائزة إلى أمر بيع) غير موجود في "
              "الشيفرة — يكتب في نظامك المحاسبي، فقراره يُتّخذ مرة بوعي.",
        "en": "🔒 **Pull only.** Push (turning a won tender into a sales order) does "
              "not exist in the code — it writes into your accounting system, so "
              "that decision is taken once, deliberately.",
    },
    "cn.connector": {"ar": "الموصّل", "en": "Connector"},
    "cn.url": {"ar": "عنوان الخادم", "en": "Server URL"},
    "cn.db": {"ar": "قاعدة البيانات", "en": "Database"},
    "cn.username": {"ar": "المستخدم", "en": "Username"},
    "cn.api_key": {"ar": "مفتاح الواجهة", "en": "API key"},
    "cn.api_key_help": {
        "ar": "مفتاح واجهة لا كلمة سر الحساب — يُلغى وحده إن لزم.",
        "en": "An API key, not the account password — it can be revoked on its own.",
    },
    "cn.test": {"ar": "اختبار الاتصال", "en": "Test connection"},
    "cn.not_configured": {
        "ar": "الموصّل غير مُعدّ — أعدّه في الإعدادات أولاً.",
        "en": "The connector is not configured — set it up in Settings first.",
    },

    "cn.pull_title": {"ar": "سحب من نظام خارجي", "en": "Pull from an external system"},
    "cn.pull_hint": {
        "ar": "يُضاف المسحوب إلى سجلات الأدلة فيصير صفوفاً تُطابَق بها المتطلبات.",
        "en": "What is pulled joins the evidence registries as rows that "
              "requirements can be matched against.",
    },
    "cn.enable_for_tender": {
        "ar": "فعّل القناة لهذه المنافسة",
        "en": "Enable the channel for this tender",
    },
    "cn.enable_help": {
        "ar": "التفعيل لكل منافسة على حدة — لا مفتاح عامّ. قناة مفتوحة دائماً "
              "تُخرج بيانات منافسة لم يقصد أحد ربطها.",
        "en": "Enabled per tender — there is no global switch. An always-open "
              "channel sends out data from tenders nobody meant to connect.",
    },
    "cn.disabled_note": {
        "ar": "القناة مغلقة لهذه المنافسة — لا شيء يغادر.",
        "en": "The channel is closed for this tender — nothing leaves.",
    },
    "cn.resource": {"ar": "المورد", "en": "Resource"},
    "cn.res_customers": {"ar": "العملاء", "en": "Customers"},
    "cn.res_products": {"ar": "المنتجات", "en": "Products"},
    "cn.res_employees": {"ar": "الموظفون", "en": "Employees"},
    "cn.egress_now": {
        "ar": "⚠️ سيتّصل النظام بـ **{host}** لسحب: {resource}.",
        "en": "⚠️ The system will connect to **{host}** to pull: {resource}.",
    },
    "cn.personal_warning": {
        "ar": "🔴 الموظفون **بيانات أشخاص**: سحبهم يُدخلهم في نطاق سياسة البيانات "
              "الشخصية — يُسجَّل أساس المعالجة «عقد»، ولكل شخص حقّ الحذف من صفحة "
              "ملف الشركة.",
        "en": "🔴 Employees are **personal data**: pulling them brings them under "
              "the personal-data policy — the legal basis is recorded as "
              "\"contract\", and each person keeps the right to erasure from the "
              "company page.",
    },
    "cn.pull": {"ar": "اسحب الآن", "en": "Pull now"},
    "cn.pulled": {
        "ar": "✅ أُضيف {n} صفاً إلى {registry} · وتُخطّي {skipped} موجوداً أصلاً.",
        "en": "✅ Added {n} row(s) to {registry} · skipped {skipped} already present.",
    },
    "cn.failed": {"ar": "❌ تعذّر السحب: {error}", "en": "❌ Pull failed: {error}"},

    # ── تحويل الفائز إلى مشروع (14-11) / Won tender → delivery project ──
    "dlv.title": {"ar": "مشروع التنفيذ والتزاماته", "en": "Delivery project & commitments"},
    "dlv.hint": {
        "ar": "المنافسة الفائزة تصير مشروعاً بقائمة تسليمات مستخرَجة من العرض — "
              "لكل بند مرجعه، فلا يبدأ فريق التنفيذ بقراءة ثمانين صفحة.",
        "en": "A won tender becomes a project with a deliverables list extracted "
              "from the proposal — each item carries its reference, so the delivery "
              "team does not start by reading eighty pages.",
    },
    "dlv.needs_win": {
        "ar": "التحويل للمنافسة **الفائزة** وحدها. سجّل النتيجة «فاز» أولاً — "
              "خطة تسليم لعملٍ لم نفز به تُدخل في اللوحة التزامات لا تخصّ أحداً.",
        "en": "Only a **won** tender can be converted. Record the outcome as won "
              "first — a delivery plan for work we did not win fills the board with "
              "commitments that belong to no one.",
    },
    "dlv.ready": {
        "ar": "✅ هذه المنافسة فائزة — يمكن تحويلها إلى مشروع تنفيذ.",
        "en": "✅ This tender was won — it can be converted into a delivery project.",
    },
    "dlv.convert": {"ar": "حوّل إلى مشروع تنفيذ", "en": "Convert to a delivery project"},
    "dlv.converted": {
        "ar": "✅ حُوّلت، واستُخرج {n} التزاماً. راجِع ما ينتظر الإقرار.",
        "en": "✅ Converted, and {n} commitment(s) extracted. Review what awaits "
              "confirmation.",
    },
    "dlv.already": {"ar": "محوَّلة أصلاً.", "en": "Already converted."},
    "dlv.undo_convert": {"ar": "إلغاء التحويل وحذف بنوده", "en": "Undo conversion and delete its items"},
    "dlv.empty": {
        "ar": "لا بند بعد — أضِف بنداً يدوياً أو أعد التحويل بعد كتابة الأقسام.",
        "en": "No items yet — add one manually, or reconvert after the sections "
              "are written.",
    },
    "dlv.m_total": {"ar": "البنود", "en": "Items"},
    "dlv.m_unconfirmed": {"ar": "بانتظار الإقرار", "en": "Awaiting confirmation"},
    "dlv.m_open": {"ar": "مفتوحة", "en": "Open"},
    "dlv.m_done": {"ar": "منجزة", "en": "Done"},
    "dlv.needs_confirm": {
        "ar": "⏳ {n} بنداً مستخرَجاً من نصّ العرض ينتظر إقرار إنسان — الاستخراج "
              "اقتراح لا قرار، وقائمة يُبنى عليها التنفيذ لا تُملأ بلا مراجعة.",
        "en": "⏳ {n} item(s) extracted from the proposal text await human "
              "confirmation — extraction is a suggestion, not a decision, and a list "
              "that delivery rests on is not filled without review.",
    },
    "dlv.source": {"ar": "المصدر", "en": "Source"},
    "dlv.src_matrix": {"ar": "مصفوفة الامتثال", "en": "Compliance matrix"},
    "dlv.src_section": {"ar": "نصّ قسم في العرض", "en": "Proposal section text"},
    "dlv.src_manual": {"ar": "أُضيف يدوياً", "en": "Added manually"},
    "dlv.no_ref": {"ar": "بلا مرجع", "en": "no reference"},
    "dlv.owner": {"ar": "المسؤول", "en": "Owner"},
    "dlv.due": {"ar": "الاستحقاق", "en": "Due"},
    "dlv.status": {"ar": "الحالة", "en": "Status"},
    "dlv.st_open": {"ar": "مفتوح", "en": "Open"},
    "dlv.st_done": {"ar": "منجز", "en": "Done"},
    "dlv.st_dropped": {"ar": "أُسقط", "en": "Dropped"},
    "dlv.confirm": {"ar": "أقرّ البند", "en": "Confirm item"},
    "dlv.add": {"ar": "بند تسليم إضافي", "en": "Additional deliverable"},
    "dlv.add_ph": {"ar": "التزام لم يُستخرج من العرض…", "en": "A commitment not extracted from the proposal…"},
    "dlv.add_btn": {"ar": "إضافة بند", "en": "Add item"},

    # ── وحدة الاستفسارات (14-9) / Clarifications ──
    "cl.title": {"ar": "الاستفسارات للجهة", "en": "Clarifications to the entity"},
    "cl.hint": {
        "ar": "الغموض المرصود في المصفوفة يصير سؤالاً له موعد وجواب — لا ملاحظة "
              "في بريد تُنسى. وغياب الجواب أخطر من ورودِه مخالفاً لتوقّعنا.",
        "en": "An ambiguity spotted in the matrix becomes a question with a due "
              "date and an answer — not a note in an email that gets forgotten. A "
              "missing answer is more dangerous than one that contradicts you.",
    },
    "cl.needs_project": {
        "ar": "افتح منافسة أولاً — الاستفسار يخصّ منافسةً بعينها.",
        "en": "Open a tender first — a clarification belongs to a specific tender.",
    },
    "cl.empty": {
        "ar": "لا استفسار بعد. أضِف أول سؤال من متطلب غامض في المصفوفة.",
        "en": "No clarification yet. Add the first question from an ambiguous "
              "requirement in the matrix.",
    },
    "cl.m_total": {"ar": "الاستفسارات", "en": "Clarifications"},
    "cl.m_unsent": {"ar": "لم تُرسَل", "en": "Not sent"},
    "cl.m_overdue": {"ar": "متأخّرة", "en": "Overdue"},
    "cl.m_answered": {"ar": "أُجيبت", "en": "Answered"},
    "cl.req": {"ar": "المتطلب", "en": "Requirement"},
    "cl.req_none": {"ar": "غير مرتبط بمتطلب", "en": "Not linked to a requirement"},
    "cl.req_unlinked": {
        "ar": "⚠️ المعرّف لم يعد في المصفوفة — السؤال باقٍ لأنّه أُرسل فعلاً",
        "en": "⚠️ The identifier is no longer in the matrix — the question stays "
              "because it was actually sent",
    },
    "cl.due": {"ar": "موعد الجواب", "en": "Answer due"},
    "cl.due_help": {
        "ar": "ميلادي أو هجري — يُقرأ التقويمان، وتاريخ تعذّرت قراءته لا يُعدّ "
              "فائتاً ولا قائماً.",
        "en": "Gregorian or Hijri — both are read, and a date that cannot be "
              "parsed counts as neither passed nor pending.",
    },
    "cl.due_unreadable": {"ar": "تاريخ لم يُقرأ", "en": "date not parsed"},
    "cl.days_left": {"ar": "{n} يوماً", "en": "{n} day(s)"},
    "cl.question": {"ar": "السؤال", "en": "Question"},
    "cl.question_ph": {
        "ar": "ما المقصود بـ«خبرة مماثلة» في البند 4-2: قيمة العقد أم نطاقه؟",
        "en": "What does \"similar experience\" in clause 4-2 mean: contract value "
              "or scope?",
    },
    "cl.question_required": {"ar": "❌ نصّ السؤال مطلوب.", "en": "❌ The question text is required."},
    "cl.add": {"ar": "إضافة استفسار", "en": "Add clarification"},
    "cl.added": {"ar": "✅ سُجّل الاستفسار كمسودّة — أرسله ثم علّم إرساله.",
                 "en": "✅ Saved as a draft — send it, then mark it as sent."},
    "cl.status_draft": {"ar": "📝 مسودّة", "en": "📝 Draft"},
    "cl.status_sent": {"ar": "📤 أُرسل", "en": "📤 Sent"},
    "cl.status_answered": {"ar": "✅ أُجيب", "en": "✅ Answered"},
    "cl.status_closed": {"ar": "🗄️ مُغلق", "en": "🗄️ Closed"},
    "cl.mark_sent": {"ar": "علّم: أُرسل", "en": "Mark as sent"},
    "cl.close": {"ar": "إغلاق", "en": "Close"},
    "cl.answer": {"ar": "جواب الجهة", "en": "Entity's answer"},
    "cl.save_answer": {"ar": "حفظ الجواب", "en": "Save answer"},
    "cl.answer_saved": {"ar": "✅ حُفظ الجواب.", "en": "✅ Answer saved."},
    "cl.answer_required": {
        "ar": "❌ جواب فارغ لا يُغلق سؤالاً: «أُجيب» حالة تُبنى عليها قرارات امتثال.",
        "en": "❌ An empty answer cannot close a question: \"answered\" is a state "
              "that compliance decisions rest on.",
    },
    "cl.answer_reaches_model": {
        "ar": "🔗 هذا الجواب يُحقن في كتابة الأقسام ويعلو على ظاهر نص الكرّاس. "
              "المعلَّق لا يُحقن بأي صيغة.",
        "en": "🔗 This answer is injected into section writing and overrides the "
              "literal clause. Pending questions are never injected.",
    },
    "cl.risks": {
        "ar": "⚠️ {n} استفساراً يحتاج متابعة:",
        "en": "⚠️ {n} clarification(s) need follow-up:",
    },
    "cl.risks_critical": {
        "ar": "🚨 {n} استفساراً على متطلب **حرج** بلا جواب — الغائب لا يُفترَض:",
        "en": "🚨 {n} clarification(s) on a **critical** requirement with no answer "
              "— a missing answer must not be assumed:",
    },
    "cl.no_risks": {
        "ar": "✅ لا استفسار معلَّق ولا متأخّر.",
        "en": "✅ No pending or overdue clarification.",
    },

    # ── خطّ الأنابيب واستراتيجية العرض (14-8) / Pipeline & win strategy ──
    "pipe.title": {"ar": "خطّ الأنابيب واستراتيجية العرض",
                   "en": "Pipeline & win strategy"},
    "pipe.hint": {
        "ar": "أين هذه المنافسة من دورة البيع، ومن يقودها، ولماذا نفوز بها.",
        "en": "Where this tender sits in the sales cycle, who leads it, and why we win it.",
    },
    "pipe.stage": {"ar": "المرحلة", "en": "Stage"},
    "pipe.owner": {"ar": "مالك المنافسة", "en": "Tender owner"},
    "pipe.probability": {"ar": "احتمال الفوز (تقدير)", "en": "Win probability (forecast)"},
    "pipe.probability_help": {
        "ar": "تقديرك أنت قبل الحسم — لا يدخل قياس نسبة الفوز في اللوحة، فتلك "
              "محسوبة من نتائج مسجَّلة لا من ظنّ.",
        "en": "Your own forecast before the outcome — it never feeds the dashboard "
              "win rate, which is computed from recorded outcomes, not opinion.",
    },
    "pipe.why": {"ar": "لماذا نفوز", "en": "Why we win"},
    "pipe.why_ph": {
        "ar": "ما يميّزنا في هذه المنافسة تحديداً — خبرة مطابقة، فريق محلي، "
              "منهجية أثبتت نفسها عند هذه الجهة…",
        "en": "What sets us apart in this specific tender — matching experience, "
              "a local team, a methodology proven with this entity…",
    },
    "pipe.why_help": {
        "ar": "الحقل الوحيد الذي يصل النموذج: يظهر أثره في اختيار ما تُبرزه "
              "الأقسام، لا كجملة مكرَّرة في كل قسم.",
        "en": "The only field the model sees: it shapes what each section "
              "emphasises, rather than being repeated verbatim in every section.",
    },
    "pipe.only_why_reaches_model": {
        "ar": "🔒 «لماذا نفوز» وحدها تصل النموذج. المرحلة والمالك واحتمال الفوز "
              "بيانات داخلية لا تغادر إلى أي نص مولَّد.",
        "en": "🔒 Only \"why we win\" reaches the model. Stage, owner and win "
              "probability are internal and never leave for any generated text.",
    },
    "pipe.why_active": {
        "ar": "✅ الاستراتيجية تُحقن مع كل قسم يُولَّد بعد الآن.",
        "en": "✅ The strategy is injected into every section generated from now on.",
    },
    "pipe.why_empty": {
        "ar": "بلا استراتيجية مكتوبة تُكتب الأقسام صحيحةً بلا حجّة تميّزها.",
        "en": "With no strategy written, sections come out correct but with no "
              "argument that sets them apart.",
    },

    # ── مؤشرات الأداء (14-7) / Performance metrics ──
    "kpi.title": {"ar": "مؤشرات الأداء", "en": "Performance"},
    "kpi.hint": {
        "ar": "مقيسة من منافساتك المسجَّلة ومن استهلاك النماذج — لا تقديرات.",
        "en": "Measured from your recorded tenders and model usage — not estimates.",
    },
    "kpi.win_rate": {"ar": "نسبة الفوز", "en": "Win rate"},
    "kpi.win_raw": {
        "ar": "{won} من {decided} محسومة",
        "en": "{won} of {decided} decided",
    },
    "kpi.cycle": {"ar": "زمن الإعداد (وسيط)", "en": "Preparation time (median)"},
    "kpi.days": {"ar": "{n} يوماً", "en": "{n} day(s)"},
    "kpi.cost": {"ar": "كلفة الإعداد", "en": "Preparation cost"},
    "kpi.cost_value": {
        "ar": "${median} للمنافسة · ${total} إجمالاً",
        "en": "${median} per tender · ${total} total",
    },
    "kpi.reuse": {"ar": "إعادة الاستخدام", "en": "Reuse"},
    "kpi.reuse_value": {
        "ar": "{n} إدراجاً من {blocks} كتلة معتمدة",
        "en": "{n} insertion(s) from {blocks} approved block(s)",
    },
    "kpi.no_measure": {"ar": "لا قياس بعد", "en": "Not measured yet"},
    "kpi.no_outcomes": {
        "ar": "لم تُسجَّل نتيجة أي منافسة بعد. سجّل «فاز» أو «خسر» في صفحة "
              "المنافسات لتبدأ نسبة الفوز في القياس.",
        "en": "No tender outcome recorded yet. Mark tenders as won or lost on the "
              "tenders page to start measuring the win rate.",
    },
    "kpi.small_sample": {
        "ar": "العدّ خام لا نسبة: النسبة تحتاج {n} منافسات محسومة على الأقل — "
              "دونها تدّعي دقّة لا وجود لها.",
        "en": "Shown as a raw count, not a rate: a rate needs at least {n} decided "
              "tenders — below that it claims a precision it does not have.",
    },
    "kpi.by_entity": {"ar": "حسب الجهة", "en": "By entity"},
    "kpi.by_sector": {"ar": "حسب القطاع", "en": "By sector"},
    "kpi.no_entity": {
        "ar": "لا جهة لها منافسة محسومة بعد.",
        "en": "No entity has a decided tender yet.",
    },
    "kpi.no_sector": {
        "ar": "لا قطاع مسجَّل بعد — أضِف القطاع عند إنشاء المنافسة.",
        "en": "No sector recorded yet — set it when creating a tender.",
    },
    "proj.sector": {"ar": "القطاع", "en": "Sector"},
    "proj.sector_help": {
        "ar": "يُجمَّع عليه قياس الفوز، وتُخصَّص به تعليمات النموذج لهذا القطاع.",
        "en": "Win rate is grouped by it, and model instructions can be scoped to it.",
    },

    # ── مسرد المصطلحات (14-6) / Glossary ──
    "gl.title": {"ar": "مسرد المصطلحات", "en": "Terminology glossary"},
    "gl.intro": {
        "ar": "يوحّد ترجمة المصطلح الفني عبر كل أقسام العرض: صيغة معتمدة واحدة "
              "تُحقن في التوليد، وفحص حسابي يرصد ما خالفها في لوحة المراجعة.",
        "en": "Unifies each technical term across every section: one approved form "
              "is injected into generation, and a calculated check flags anything "
              "that deviates, in the review panel.",
    },
    "gl.empty": {
        "ar": "المسرد فارغ. أضِف أول مصطلح — «SLA» مثلاً — ليخرج بصيغة واحدة.",
        "en": "The glossary is empty. Add a first term — \"SLA\", say — so it "
              "comes out in a single form.",
    },
    "gl.count": {"ar": "{n} مصطلحاً في المسرد.", "en": "{n} term(s) in the glossary."},
    "gl.add": {"ar": "مصطلح جديد", "en": "New term"},
    "gl.term": {"ar": "المصطلح", "en": "Term"},
    "gl.term_help": {
        "ar": "الصيغة المصدر كما ترد في الكرّاس — «SLA» أو «KPI».",
        "en": "The source form as it appears in the tender — \"SLA\" or \"KPI\".",
    },
    "gl.preferred_ar": {"ar": "الصيغة المعتمدة (عربي)", "en": "Approved form (Arabic)"},
    "gl.preferred_en": {"ar": "الصيغة المعتمدة (إنجليزي)", "en": "Approved form (English)"},
    "gl.variants": {"ar": "الصيغ المرفوضة", "en": "Rejected forms"},
    "gl.variants_help": {
        "ar": "افصل بينها بـ · أو فاصلة. بها وحدها يصير التوحيد قابلاً للفحص — "
              "بلا معرفة الخطأ لا يُرصد الانحراف.",
        "en": "Separate with · or commas. These alone make the rule checkable — "
              "without knowing the wrong form, drift cannot be detected.",
    },
    "gl.no_variants": {
        "ar": "بلا صيغ مرفوضة: التعليمة تُحقن، لكن لا يُرصد خروج عنها.",
        "en": "No rejected forms: the instruction is injected, but deviations "
              "cannot be flagged.",
    },
    "gl.note": {"ar": "ملاحظة", "en": "Note"},
    "gl.term_required": {
        "ar": "❌ المصطلح وصيغة معتمدة واحدة على الأقل مطلوبان.",
        "en": "❌ The term and at least one approved form are required.",
    },
    "gl.term_taken": {"ar": "❌ المصطلح موجود في المسرد.", "en": "❌ Term already in the glossary."},
    "gl.saved": {"ar": "✅ حُفظ المصطلح.", "en": "✅ Term saved."},
    "gl.deleted": {"ar": "✅ حُذف المصطلح.", "en": "✅ Term deleted."},

    # ── بصمة الأسلوب من عرض سابق (14-5) / Style fingerprint ──
    "sty.upload_hint": {
        "ar": "يُقرأ من هذه العيّنة **شكل الكتابة وحده** — طول الجملة والفقرة "
              "ونسبة النقاط وصيغة المخاطبة. لا يُنقل منها اسم عميل ولا رقم ولا "
              "التزام، ولا تدخل مستودع الاسترجاع.",
        "en": "Only the **writing form** is read from this sample — sentence and "
              "paragraph length, list density, and voice. No client name, figure, "
              "or commitment is carried over, and it never enters the retrieval pool.",
    },
    "sty.ready": {
        "ar": "✅ {n} عيّنة — بصمة الأسلوب تُحقن في كل قسم.",
        "en": "✅ {n} sample(s) — the style fingerprint is injected into every section.",
    },
    "sty.too_short": {
        "ar": "⚠️ العيّنات أقصر من {words} كلمة — بصمة من فقرة واحدة أسوأ من لا بصمة، "
              "فلن تُحقن.",
        "en": "⚠️ The samples are shorter than {words} words — a fingerprint from a "
              "single paragraph is worse than none, so it will not be injected.",
    },

    # ── فئات المعرفة / KB categories ──
    "kbcat.proposal_sample": {
        "ar": "عروض سابقة (للأسلوب)", "en": "Past proposals (style only)",
    },
    "kbcat.cv": {"ar": "السير الذاتية", "en": "CVs"},
    "kbcat.cert": {"ar": "الشهادات والاعتمادات", "en": "Certifications"},
    "kbcat.project": {"ar": "المشاريع السابقة", "en": "Past projects"},
    "kbcat.other": {"ar": "مستندات أخرى", "en": "Other documents"},
}
