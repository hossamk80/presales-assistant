"""
utils/db/_core.py — النواة: المخطّط · الاتصال · الترحيل · تقييد الشركة · المعاملة.

كل وحدة أخرى في هذه الحزمة تعتمد على هذه، وهذه **لا تعتمد على أيٍّ منها** —
وهو ما يمنع الدوران. ولهذا تسكن هنا آلة تحليل الشركة الفاعلة: `_scope`
يستدعيها في كل استعلام مقيَّد، فلو سكنت في `accounts` لدارت الوحدتان.
"""

import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Optional


# ثلاث مرّات لا مرّتين: الملف صار `utils/db/_core.py` بعد تقسيم الوحدة إلى
# حزمة، ومستوىً إضافيّ في المسار يعني `dirname` إضافيّاً. بمرّتين يصير جذر
# التطبيق `utils/`، وقاعدة البيانات `utils/data/analyst.db` — قاعدةٌ جديدة
# فارغة بدل قاعدة المستخدم، بلا خطأ يُرفع.
APP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


DATA_DIR = os.path.join(APP_DIR, "data")


DB_PATH = os.environ.get("ANALYST_DB_PATH") or os.path.join(DATA_DIR, "analyst.db")


_local = threading.local()


SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    reference   TEXT DEFAULT '',
    entity      TEXT DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    payload     TEXT NOT NULL,
    -- 13-7: يزيد مع كل حفظ. الحفظ المشروط يقارنه بما رآه المُحرِّر آخر مرة،
    -- فيكتشف أن جلسة أخرى كتبت بينهما بدل أن يدهس عملها.
    revision    INTEGER NOT NULL DEFAULT 0
);

-- ملف الشركة (13-1): كان الجدول مقيَّداً بصف واحد `CHECK (id = 1)` لأن النظام
-- بُني لفرد يعمل لشركة واحدة. قسم العطاءات قد يخدم أكثر من كيان (شركة أمّ
-- وذراع تنفيذية، أو مكتب استشاري يعدّ عروضاً لعملائه)، وكل ما بعده —
-- المستخدمون والأدوار وإسناد الأقسام — يفترض قاعدة تحتمل أكثر من شركة.
-- القيد أُلغي، وقاعدة قديمة تُرقّى في `_migrate_company` بلا فقد بيانات.
CREATE TABLE IF NOT EXISTS company (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT '',
    payload    TEXT NOT NULL,
    template   BLOB,
    logo       BLOB
);

CREATE TABLE IF NOT EXISTS kb_documents (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    category   TEXT NOT NULL,
    added_at   TEXT NOT NULL,
    char_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS kb_chunks (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id    INTEGER NOT NULL REFERENCES kb_documents(id) ON DELETE CASCADE,
    ordinal   INTEGER NOT NULL,
    text      TEXT NOT NULL,
    dims      INTEGER NOT NULL,
    embedding BLOB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_kb_chunks_doc ON kb_chunks(doc_id);

-- نسخ المرفقات: الجهات تُصدر تعديلات بعد نشر الكراسة، وكانت الرفعة الجديدة
-- تمحو القديمة بلا أثر — فلا يُعرف ما الذي تغيّر ولا أي متطلب صار على شرط
-- ملغى. كل رفعة تُحفظ نسخةً لتُقارَن بما قبلها.
CREATE TABLE IF NOT EXISTS attachment_versions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    label      TEXT DEFAULT '',
    payload    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_attachment_versions_project
    ON attachment_versions(project_id);

-- قياس الاستهلاك (11-7): كل استدعاء نموذج يُسجَّل من عدّادات الموفّر نفسه
-- لا من تقدير محلي. بدونه لا يمكن إثبات نجاح أي من تحسينات الكلفة.
CREATE TABLE IF NOT EXISTS ai_usage (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at    TEXT NOT NULL,
    month         TEXT NOT NULL,
    project_id    INTEGER,
    project_name  TEXT DEFAULT '',
    task          TEXT NOT NULL,
    provider      TEXT NOT NULL,
    model         TEXT NOT NULL,
    input_tokens  INTEGER NOT NULL DEFAULT 0,
    cached_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost          REAL NOT NULL DEFAULT 0,
    elapsed_ms    INTEGER NOT NULL DEFAULT 0,
    status        TEXT NOT NULL DEFAULT 'ok'
);

CREATE INDEX IF NOT EXISTS idx_ai_usage_month ON ai_usage(month);

-- ذاكرة نتائج الاستدعاءات (11-13): بصمة (تعليمات + سياق + نموذج) ← النتيجة.
-- إعادة الضغط على زرّ بلا تغيير معطيات لا تُنفق توكن.
CREATE TABLE IF NOT EXISTS ai_cache (
    fingerprint TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    provider    TEXT NOT NULL,
    model       TEXT NOT NULL,
    result      TEXT NOT NULL
);

-- سجلات الأدلة (المرحلة 12): الكوادر · سابقة الأعمال · الشهادات · الموردون ·
-- الجهات. صفوف تُطابَق بها متطلبات الكراسة بدل نص حر لا يصمد أمام لجنة فحص.
--
-- جدول واحد بحمولة JSON لا خمسة جداول: الأعمدة معلنة في `utils/records.py`،
-- وإضافة حقل هناك لا تستلزم ترحيل قاعدة. السجلات صغيرة (عشرات الصفوف) فلا
-- حاجة إلى فهرسة داخل الحمولة.
CREATE TABLE IF NOT EXISTS company_records (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    registry TEXT NOT NULL,
    ordinal  INTEGER NOT NULL DEFAULT 0,
    payload  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_company_records_registry
    ON company_records(registry);

-- البرومبتات (14-1): تعليمات النموذج قابلة للتحرير من الواجهة بلا إعادة تشغيل.
--
-- الجدول يحمل **التجاوزات وحدها** لا نسخة من كل برومبت: النصوص الافتراضية تبقى
-- في `ai_engine.py` مصدراً واحداً، وصفٌّ هنا يعني «هذا المفتاح عُدّل». وزرْع
-- الجدول بنسخة من كل نصّ يبدو أنظف حتى يتغيّر الافتراضي في الشيفرة فيبقى
-- المزروع قديماً صامتاً — والفرق لا يظهر إلا في جودة عرض خسر.
--
-- «استعادة الافتراضي» تحذف الصف فيعود النص من الشيفرة — لا نسخ ولا مقارنة.
--
-- `sector` و `language` فارغان يعنيان «لكل القطاعات وكل اللغات»، والأخص يغلب.
-- والقواعد الثابتة (14-2) **ليست هنا ولا تُحرَّر**: تُلحق وقت الاستدعاء.
CREATE TABLE IF NOT EXISTS prompts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    key        TEXT NOT NULL,
    agent      TEXT NOT NULL DEFAULT '',
    sector     TEXT NOT NULL DEFAULT '',
    language   TEXT NOT NULL DEFAULT '',
    version    INTEGER NOT NULL DEFAULT 1,
    text       TEXT NOT NULL,
    enabled    INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL DEFAULT '',
    updated_by TEXT NOT NULL DEFAULT ''
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_prompts_scope
    ON prompts(key, sector, language);

-- مكتبة المحتوى المعتمد (14-4): كتل نصّية تُدرَج في الأقسام كما هي.
--
-- الحاجة: نصف العرض الفني لا يتغيّر بين منافسة وأخرى — سياسة الجودة، منهجية
-- التسليم، نبذة الشركة، التزامات الضمان. توليدها بالنموذج كل مرة يكلّف توكناً
-- ويُخرج صياغة مختلفة في كل عرض عن نصّ **راجعه القسم القانوني مرة**. الكتلة
-- المعتمدة تُدرَج **بلا استدعاء نموذج** — وهذا شرط قبول هذا البند.
--
-- `status`: `draft` ← `approved` ← `retired`. والمُدرَج المعتمد وحده: مسودّة
-- تُدرَج تجعل المكتبة مجلّد قصاصات لا مكتبة معتمدة.
--
-- **تحرير النصّ يُسقط الاعتماد** إلى `draft` — كما يسقط اعتماد العرض بتعديله
-- بعده (13-8). كتلة اعتُمدت ثم غُيّر نصّها ليست الكتلة المعتمدة، وإبقاء الختم
-- عليها يجعل «معتمد» ختماً على ورقة تُملأ بعده.
--
-- `reviewed_at` + `review_months`: المحتوى يصدأ — رقم سعودة تغيّر، شهادة
-- انتهت، منهجية استُبدلت. الكتلة المتأخّرة عن مراجعتها تُدرَج **بتحذير لا
-- بمنع**: قفلها يوم انقضاء التاريخ يوقف الكتابة في يوم تسليم، والقرار البشري
-- هو الأصل في هذا النظام. صفر شهراً = بلا دورة مراجعة معلنة فلا شيء يتأخّر.
--
-- `used_count` عدّاد إعادة الاستخدام — الغاية من المكتبة قياسها لا الثقة بها.
CREATE TABLE IF NOT EXISTS content_blocks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    key           TEXT NOT NULL UNIQUE,
    title         TEXT NOT NULL DEFAULT '',
    body          TEXT NOT NULL DEFAULT '',
    category      TEXT NOT NULL DEFAULT '',
    sector        TEXT NOT NULL DEFAULT '',
    language      TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'draft',
    reviewed_at   TEXT NOT NULL DEFAULT '',
    reviewed_by   TEXT NOT NULL DEFAULT '',
    review_months INTEGER NOT NULL DEFAULT 12,
    used_count    INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT '',
    updated_at    TEXT NOT NULL DEFAULT '',
    updated_by    TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_content_blocks_status
    ON content_blocks(status);

-- مسرد المصطلحات (14-6): ترجمة فنية واحدة عبر كل أقسام العرض.
--
-- المشكلة: «SLA» تخرج «اتفاقية مستوى الخدمة» في المنهجية و«مستوى الخدمة» في
-- الدعم و«SLA» كما هي في الملاحق — ثلاث صيغ في مستند واحد. المُقيّم يقرأها
-- ترجمةً غير مضبوطة، وأسوأ منها أن يظنّها ثلاثة مفاهيم لا واحداً.
--
-- `preferred_ar` و `preferred_en`: الصيغة المعتمدة لكل لغة مخرجات — لا عمود
-- واحد، لأن العرض العربي والإنجليزي لا يتفقان على صيغة واحدة بطبيعتهما.
--
-- `variants` قائمة JSON بالصيغ **المرفوضة**. وجودها هو ما يجعل الفحص ممكناً:
-- بلا معرفة الخطأ لا يُرصد الانحراف، وتبقى التوحيد رجاءً موجَّهاً إلى النموذج
-- لا شرطاً يُتحقَّق منه. الفحص في `utils/consistency.py` حسابي بلا استدعاء.
CREATE TABLE IF NOT EXISTS glossary (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    term         TEXT NOT NULL,
    preferred_ar TEXT NOT NULL DEFAULT '',
    preferred_en TEXT NOT NULL DEFAULT '',
    variants     TEXT NOT NULL DEFAULT '[]',
    note         TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL DEFAULT '',
    updated_at   TEXT NOT NULL DEFAULT '',
    updated_by   TEXT NOT NULL DEFAULT ''
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_glossary_term ON glossary(term);

-- وحدة الاستفسارات (14-9): الغموض المرصود يصير سؤالاً مُتتبَّعاً.
--
-- المشكلة: بند غامض في الكرّاس يُرصد في المصفوفة، فيُكتب سؤال في بريد أو ورقة
-- ثم يُنسى. الموعد يمرّ، ولا أحد يعرف أنّ متطلباً حرجاً بُني على **فهمنا** له
-- لا على جواب الجهة. غيابُ الجواب لا يظهر في أي شاشة — وهذا أخطر من ورودِه
-- مخالفاً لتوقّعنا، لأن المخالف يُعالَج والغائب يُبنى عليه.
--
-- `req_id` يربط السؤال بصفّ المصفوفة (عمود «المعرّف»). الربط **بالنص لا بمفتاح
-- أجنبي**: صفوف المصفوفة تعيش في حمولة المنافسة لا في جدول، ومعرّف قديم لم يعد
-- في المصفوفة يُعرض «غير مرتبط» ولا يُخفي السؤال — السؤال أُرسل إلى الجهة
-- فعلاً، فوجوده واقعة لا تُمحى بحذف صفّ عندنا.
--
-- `due_at` موعد الجواب المتوقَّع، ويُقرأ بـ `records.parse_date` لا بقارئ
-- ميلادي: كرّاسات الجهات تؤرّخ هجرياً كثيراً بلا وسم.
CREATE TABLE IF NOT EXISTS clarifications (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER,
    req_id      TEXT NOT NULL DEFAULT '',
    question    TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'draft',
    asked_at    TEXT NOT NULL DEFAULT '',
    due_at      TEXT NOT NULL DEFAULT '',
    answer      TEXT NOT NULL DEFAULT '',
    answered_at TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT '',
    created_by  TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_clarifications_project
    ON clarifications(project_id);

-- تحويل الفائز إلى مشروع (14-11): التزامات العرض تصير قائمة تسليمات.
--
-- المشكلة: نفوز، ثم يبدأ فريق التنفيذ من الصفر بقراءة عرضٍ من ثمانين صفحة
-- ليعرف بماذا التزمنا. وما يُنسى منه لا يُنسى على الجهة: بند وعدنا به في
-- المنهجية ولم يصل خطة التسليم يصير مخالفة عقدية بعد أشهر.
--
-- **جدولان لا خلط**: `deliveries` هي المنافسة بعد فوزها (طور التنفيذ)،
-- و `deliverables` بنودها. وإبقاء حالة التنفيذ في `projects` يخلط طوري البيع
-- والتسليم في صفٍّ واحد، فيصير «مفتوحة» يعني أمرين مختلفين.
CREATE TABLE IF NOT EXISTS deliveries (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    name       TEXT NOT NULL DEFAULT '',
    entity     TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT ''
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_deliveries_project
    ON deliveries(project_id);

-- بنود التسليم. `source` و `source_ref` يقولان **من أين جاء الالتزام**: صفّ
-- في مصفوفة الامتثال أم فقرة في قسم. وهذا هو المكسب كلّه — مدير التنفيذ يسأل
-- «لماذا نحن ملزمون بهذا؟» فيجد مرجع البند لا ذاكرة أحد.
--
-- `confirmed` يفصل ما استخرجه النموذج عمّا أقرّه إنسان: الاستخراج اقتراح،
-- والقائمة التي يُبنى عليها التسليم لا تُملأ بلا مراجعة بشرية.
CREATE TABLE IF NOT EXISTS deliverables (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    delivery_id INTEGER NOT NULL,
    title       TEXT NOT NULL,
    source      TEXT NOT NULL DEFAULT 'manual',
    source_ref  TEXT NOT NULL DEFAULT '',
    clause_ref  TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'open',
    owner       TEXT NOT NULL DEFAULT '',
    due_at      TEXT NOT NULL DEFAULT '',
    confirmed   INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_deliverables_delivery
    ON deliverables(delivery_id);

-- نماذج الجهات (ب-4): قالب Word لكل جهة تفرض شكلها.
--
-- بعض الجهات ترفض عرضاً بغير نموذجها — رفضاً شكلياً لا علاقة له بجودة المحتوى.
-- وكان في النظام قالب **واحد للشركة**، فمن يقدّم لثلاث جهات مختلفة يبدّله يدوياً
-- قبل كل تصدير ويتذكّر أيّها الصحيح.
--
-- `entity_key` اسم الجهة **مُوحَّداً** بـ `history.normalize_entity` (12-7):
-- «وزارة الصحة» و«وزاره الصحه» جهة واحدة، وعدّهما جهتين يُفقد النموذج صاحبَه.
-- و `entity_label` الاسم كما كتبه المستخدم — يُعرض ولا يُطابَق به.
CREATE TABLE IF NOT EXISTS entity_templates (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_key  TEXT NOT NULL UNIQUE,
    entity_label TEXT NOT NULL DEFAULT '',
    filename    TEXT NOT NULL DEFAULT '',
    template    BLOB,
    updated_at  TEXT NOT NULL DEFAULT '',
    updated_by  TEXT NOT NULL DEFAULT ''
);

-- الأشكال: مخططات وصور العرض (ب-5).
--
-- العرض الفني بلا مخطط معماري يخسر درجات في «وضوح الحل»: لجنة الفحص تقرأ
-- خمسين صفحة نصّاً لتفهم بنيةً يوضّحها شكل واحد.
--
-- **الصورة يرفعها المستخدم ولا يولّدها النموذج.** النموذج لا يعرف معمارية
-- الحلّ الفعلية، ومخططٌ مولَّد **ادّعاءٌ عن الحلّ** لا توضيحٌ له — وهو ما
-- تمنعه القاعدة الثالثة من القواعد الثابتة (لا اختراع).
--
-- `section_key` يربط الشكل بقسمه، و `ordinal` ترتيبه داخله. أمّا **رقم الشكل**
-- المعروض فيُحسب وقت البناء من ترتيب المستند لا يُخزَّن: حذف شكل أو نقل قسم
-- يُعيد الترقيم بلا ثغرة — نفس مبدأ ترقيم الملاحق (12-9).
CREATE TABLE IF NOT EXISTS figures (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER,
    section_key TEXT NOT NULL DEFAULT '',
    caption     TEXT NOT NULL DEFAULT '',
    image       BLOB NOT NULL,
    mime        TEXT NOT NULL DEFAULT '',
    filename    TEXT NOT NULL DEFAULT '',
    ordinal     INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_figures_project ON figures(project_id);

-- إعدادات النظام (13-10): مفتاح ← قيمة. جدول واحد صغير بدل عمود لكل إعداد
-- جديد، وأول ساكنيه سياسة البيانات الشخصية (أساس المعالجة ومدة الاحتفاظ).
CREATE TABLE IF NOT EXISTS app_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);

-- أوامر البيع المدفوعة إلى نظام خارجي (ب-6).
--
-- **المفتاح الأساسي (project_id, connector) هو الحارس**: أمر بيع مكرَّر في
-- دفاتر عميل فوضى مالية حقيقية — يُفوتَر مرتين ويُسلَّم مرتين. ومنعُه في
-- الواجهة وحدها يسقط بضغطتين متتاليتين أو بإعادة تحميل الصفحة وقت الإرسال،
-- فالمنع هنا حيث لا يُلتفّ عليه.
--
-- `fingerprint` بصمة ما أُرسل: تغيّر الجدول بعد الدفع يُقال ولا يُصحَّح
-- تلقائياً — التصحيح في نظام العميل عملُ من يملكه لا عملنا.
CREATE TABLE IF NOT EXISTS connector_orders (
    project_id  INTEGER NOT NULL,
    connector   TEXT NOT NULL,
    reference   TEXT NOT NULL DEFAULT '',
    remote_id   TEXT NOT NULL DEFAULT '',
    fingerprint TEXT NOT NULL DEFAULT '',
    pushed_at   TEXT NOT NULL,
    pushed_by   TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (project_id, connector)
);

-- تجاوزات مصفوفة الصلاحيات: صلاحية × دور ← مسموح أو ممنوع.
--
-- المصفوفة في `utils/auth.py` تبقى **الافتراض**، وهذا الجدول يحمل ما غيّره
-- مدير النظام وحده. صفٌّ غائب يعني «اتبع الافتراض» لا «ممنوع» — والفرق جوهري:
-- ترقية تُضيف صلاحية لدور في الشيفرة تسري على التثبيتات القائمة، ولو خزّنّا
-- المصفوفة كاملةً لتجمّدت على صورتها يوم أول تشغيل.
CREATE TABLE IF NOT EXISTS role_permissions (
    permission TEXT NOT NULL,
    role       TEXT NOT NULL,
    allowed    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (permission, role)
);

-- سير الاعتماد قبل التسليم (13-8): مدير العطاءات ← المالية ← الاعتماد النهائي.
--
-- الاعتماد يُسجَّل **على رقم مراجعة بعينه** (13-7) لا على المنافسة مطلقاً: عرض
-- اعتُمد ثم عُدّل ليس هو العرض المعتمَد، فيسقط اعتماده ويُعاد. بلا هذا الربط
-- يصير الاعتماد ختماً على ورقة بيضاء تُملأ بعده.
--
-- الجدول يُضاف إليه فقط: قرار يُلغى يُنقض بقرار تالٍ لا بحذف الأول.
CREATE TABLE IF NOT EXISTS approvals (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    stage      TEXT NOT NULL,
    decision   TEXT NOT NULL,
    revision   INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    user_id    INTEGER,
    username   TEXT NOT NULL DEFAULT '',
    note       TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_approvals_project ON approvals(project_id);

-- نسخ الأقسام (13-6): سجل التدقيق يقول **من** غيّر، وهذا يحفظ **ماذا كان**.
--
-- الحاجة عملية: كاتب يستبدل قسماً بتوليد جديد فيخسر صياغة أفضل، أو مراجعة
-- تُطبَّق فتُفقد فقرة. النسخة تُحفظ عند كل كتابة، فالرجوع خطوة لا إعادة كتابة.
--
-- المحتوى يُخزَّن كاملاً لا فرقاً: القسم بضعة آلاف حرف، وحساب الفروق المتسلسلة
-- عند الاسترجاع يفتح باب سلسلة تالفة تُفقد النص كله.
CREATE TABLE IF NOT EXISTS section_versions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER,
    section_key TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    user_id     INTEGER,
    username    TEXT NOT NULL DEFAULT '',
    source      TEXT NOT NULL DEFAULT 'human',
    content     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_section_versions_lookup
    ON section_versions(project_id, section_key);

-- سجل التدقيق (13-5): من غيّر ماذا ومتى، وأي نص مصدره النموذج.
--
-- لجنة فحص تسأل عن مصدر فقرة، وقسم عطاءات يسأل من حذف منافسة — وكلاهما بلا
-- جواب قبل هذا الجدول. السجل **يُضاف إليه ولا يُعدَّل ولا يُحذف منه**: لا دالة
-- تحديث ولا حذف في هذه الطبقة، فسجل يُنقّح ليس سجلاً.
--
-- `username` لقطة وقت الحدث لا ارتباطاً بالجدول: حذف حساب لاحقاً يجب ألّا
-- يمحو أثر ما فعله، ولا أن يترك صفاً بلا اسم.
-- `source` يميّز ما ولّده النموذج (`ai`) عمّا كتبه إنسان (`human`).
CREATE TABLE IF NOT EXISTS audit_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at   TEXT NOT NULL,
    user_id      INTEGER,
    username     TEXT NOT NULL DEFAULT '',
    action       TEXT NOT NULL,
    target       TEXT NOT NULL DEFAULT '',
    project_id   INTEGER,
    project_name TEXT NOT NULL DEFAULT '',
    source       TEXT NOT NULL DEFAULT 'human',
    detail       TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_audit_log_project ON audit_log(project_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at);

-- المستخدمون (13-2): النظام كان بلا هوية — من يفتح المتصفح يملك كل شيء. قسم
-- عطاءات فيه أكثر من شخص يحتاج حساباً لكل واحد قبل أي شاشة.
--
-- الكلمة لا تُخزَّن ولا تُشفَّر تشفيراً عكسياً: يُخزَّن ناتج اشتقاق بطيء
-- (scrypt) مع ملحه، والتحقق في `utils/auth.py`. القاعدة هنا لا تعرف كلمة سر.
-- `username` بلا حساسية لحالة الأحرف — «Ahmed» و «ahmed» شخص واحد لا اثنان.
--
-- `role` يُخزَّن الآن ويُفرَض في 13-3 (الأدوار الخمسة)؛ وجود العمود من الآن
-- يوفّر ترحيلاً لاحقاً على قواعد صارت تحمل مستخدمين.
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    display_name  TEXT NOT NULL DEFAULT '',
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'admin',
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL,
    last_login    TEXT NOT NULL DEFAULT ''
);
"""


# أعمدة أُضيفت بعد أول إصدار. CREATE TABLE IF NOT EXISTS لا يُعدّل جدولاً
# قائماً، فقواعد البيانات الموجودة تحتاج إضافتها صراحةً.
_ADDED_COLUMNS = (
    ("projects", "outcome", "TEXT DEFAULT ''"),
    ("projects", "outcome_note", "TEXT DEFAULT ''"),
    # 11-6: تغيير نموذج التضمين يُبطل المتجهات المخزَّنة. نحفظ اسم النموذج
    # مع كل مقطع حتى نعدّ المقاطع المعطَّلة صراحةً بدل إهمالها صامتةً.
    ("kb_chunks", "embed_model", "TEXT DEFAULT ''"),
    # 13-7: عدّاد يزيد مع كل حفظ. جلستان على منافسة واحدة تكتشفان تعارضهما
    # بمقارنته بدل أن يمحو آخر كاتب عمل الأول.
    ("projects", "revision", "INTEGER NOT NULL DEFAULT 0"),
    # 13-10: السيرة الذاتية بيانات شخص بعينه. بلا هذا الربط يبقى «احذف بياناتي»
    # بحثاً بالاسم في أسماء الملفات — يُخطئ ويُبقي مقاطع تخصّ إنساناً طلب حذفها.
    ("kb_documents", "person", "TEXT NOT NULL DEFAULT ''"),
    # 13-1: الشركة صارت صفاً من صفوف لا صفاً وحيداً، فلها اسم وتاريخ إنشاء.
    ("company", "name", "TEXT NOT NULL DEFAULT ''"),
    ("company", "created_at", "TEXT NOT NULL DEFAULT ''"),
    # 14-7: القطاع عموداً لا حقلاً في الحمولة — نسبة الفوز تُجمَّع عليه، وتجميع
    # يفكّ حمولة كل منافسة لقراءة حقل واحد لا يُحتمل. وكان `project_sector`
    # يُقرأ في `ai_engine` (14-1) ولا يُكتب في أي مكان، فبقيت البرومبتات
    # المخصَّصة لقطاع بلا قطاع يفعّلها.
    ("projects", "sector", "TEXT NOT NULL DEFAULT ''"),
    # ب-7: الشركة الفاعلة صارت **لكل مستخدم**. تُخزَّن هنا فيجدها كما تركها
    # عند دخوله التالي، وقيمة فارغة تعني «لم يختر» فيتبع أقدم شركة.
    ("users", "company_id", "INTEGER"),
    # ب-8: تقييد البيانات بالشركة. كان تعدّد الشركات يبدّل **ملف الشركة** وحده،
    # فيرى من انتقل إلى كيان آخر منافساتِ الأول ومعرفتَه وشهاداتِه — ويرفقها
    # بعرضٍ باسم كيان لا يملكها.
    #
    # الصفر يعني «قبل التقييد»: يُملأ في `_backfill_company_scope` بأقدم شركة
    # لا يُترك — صفٌّ بلا شركة لا يظهر لأحد، فتختفي منافسات المستخدم عند
    # الترقية وهو يظنّها ضاعت.
    ("projects", "company_id", "INTEGER NOT NULL DEFAULT 0"),
    ("kb_documents", "company_id", "INTEGER NOT NULL DEFAULT 0"),
    ("company_records", "company_id", "INTEGER NOT NULL DEFAULT 0"),
)


# الجداول المقيَّدة بشركة — يمرّ عليها الترحيل، وتُفحص في الاختبارات
COMPANY_SCOPED_TABLES = ("projects", "kb_documents", "company_records")


# نطاق «بلا شركة بعد». تثبيتٌ جديد يُنشئ منافسة قبل أن يملأ ملف الشركة، وقاعدة
# قديمة تُرقّى وهي بلا صفّ شركة — والصفوف حينها تحمل صفراً وتُقرأ به، فلا يختفي
# شيء. وأول شركة تُنشأ يُنسب إليها كل ذلك في `_backfill_company_scope`.
UNSCOPED_COMPANY = 0


# «كل الشركات» — يُمرَّر صراحةً حيث يكون تجاوز التقييد **هو الصواب**: حذف
# بيانات شخص (13-10) يشمل التثبيت كلّه، وصيانة المتجهات لا تقرأ محتوى.
# لا يُستعمل في أي مسار يعرض بيانات أو يبني سياقاً للنموذج.
ANY_COMPANY = -1


def _scope(company_id: Optional[int] = None) -> int:
    """نطاق الاستعلام: الشركة المطلوبة، وإلا الفاعلة، وإلا «بلا شركة بعد»."""
    if company_id is not None:
        return int(company_id)
    active = active_company_id()
    return int(active) if active is not None else UNSCOPED_COMPANY


# أعمدة جدول الشركة بترتيبها في المخطط الحالي — يستعملها الترحيل لنقل ما
# يوجد منها في القاعدة القديمة ويترك الباقي لقيمته الافتراضية.
_COMPANY_COLUMNS = ("id", "name", "created_at", "payload", "template", "logo")


def _migrate_company(conn: sqlite3.Connection):
    """
    يُلغي قيد الصف الواحد `CHECK (id = 1)` من قاعدة أُنشئت قبل 13-1.

    SQLite لا يُسقط قيداً بـ ALTER TABLE، فالسبيل الوحيد إعادة بناء الجدول:
    جدول جديد بالمخطط الحالي ← نسخ الصفوف الموجودة ← إسقاط القديم ← تسمية.
    كل ذلك داخل معاملة واحدة، فإن فشل شيء بقيت القاعدة القديمة كما هي.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'company'"
    ).fetchone()
    if row is None or "CHECK" not in (row["sql"] or "").upper():
        return

    old = {r["name"] for r in conn.execute("PRAGMA table_info(company)")}
    carried = [c for c in _COMPANY_COLUMNS if c in old]
    columns = ", ".join(carried)
    conn.execute("""
        CREATE TABLE company_migrated (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT '',
            payload    TEXT NOT NULL,
            template   BLOB,
            logo       BLOB
        )
    """)
    conn.execute(
        f"INSERT INTO company_migrated ({columns}) SELECT {columns} FROM company"
    )
    conn.execute("DROP TABLE company")
    conn.execute("ALTER TABLE company_migrated RENAME TO company")


def _backfill_company_scope(conn: sqlite3.Connection):
    """
    ينسب كل صفّ بلا شركة إلى أقدم شركة (ب-8).

    **هذا هو الجزء الذي لا يجوز أن يُخطئ.** التقييد يعني أن الاستعلامات صارت
    ترشّح بالشركة؛ وصفٌّ يحمل صفراً لا يطابق أي شركة، فيفتح المستخدم النظام
    بعد الترقية ولا يجد منافساته ولا مستودعه ولا سجلاته. لا رسالة خطأ — فراغ.

    ويُشغَّل في كل إقلاع لا مرةً واحدة: قاعدة رُقِّيت وهي بلا شركة (تثبيت جديد
    لم يُنشئ ملفاً بعد) تبقى صفوفها بصفر حتى تُنشأ أول شركة، فتُنسب حينها.
    """
    row = conn.execute("SELECT MIN(id) AS id FROM company").fetchone()
    oldest = row["id"] if row and row["id"] is not None else None
    if oldest is None:
        return
    for table in COMPANY_SCOPED_TABLES:
        columns = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        if "company_id" in columns:
            conn.execute(
                f"UPDATE {table} SET company_id = ? "
                "WHERE company_id IS NULL OR company_id = 0",
                (oldest,),
            )


def _migrate(conn: sqlite3.Connection):
    """يُرقّي قاعدة بيانات أُنشئت بإصدار أقدم إلى المخطط الحالي."""
    _migrate_company(conn)
    for table, column, decl in _ADDED_COLUMNS:
        existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
    _backfill_company_scope(conn)
    conn.commit()


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


# جيل الاتصالات (13-9): يزيد عند استرجاع نسخة احتياطية، فتُسقط كل الخيوط
# اتصالاتها القديمة وتفتح على الملف الجديد. بدونه يبقى خيط يقرأ من ملف استُبدل.
_generation = 0


def _bump_generation():
    """
    يُبطل اتصالات كل الخيوط. يستدعيه الاسترجاع بعد استبدال ملف القاعدة.

    دالّة لا `global _generation` من وحدة أخرى: الرقم يسكن هنا، و`get_conn`
    هنا يقرؤه. وحدةٌ أخرى تعلنه `global` عندها تزيد **نسختها** من الاسم
    فيبقى الأصل صفراً ويظلّ كل خيط على اتصاله بالملف القديم — استرجاعٌ يقول
    إنه نجح والقراءة من قاعدة استُبدلت.
    """
    global _generation
    _generation += 1


def get_conn() -> sqlite3.Connection:
    """اتصال لكل خيط — Streamlit يعيد التشغيل على خيوط مختلفة."""
    conn = getattr(_local, "conn", None)
    if conn is not None and getattr(_local, "generation", 0) != _generation:
        try:
            conn.close()
        except sqlite3.Error:
            pass
        conn = None
    if conn is None:
        conn = _local.conn = _connect()
        _local.generation = _generation
    return conn


@contextmanager
def transaction():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ─── ملف الشركة ───────────────────────────────────────────────────────────────


# الشركة الفاعلة: النظام يعرض ملف شركة واحدة في كل لحظة.
#
# **ب-7 — الاختيار لكل مستخدم لا لكل عملية**: كان متغيّراً عاماً في الوحدة،
# وخادم Streamlit واحد يخدم كل الجلسات — فجلستان لشركتين تتنازعان قيمة واحدة،
# ويرى أحدهما ملف شركة الآخر على غلاف عرضه.
#
# و`db` **لا تعرف الجلسات ولا المستخدمين** ولا تستورد Streamlit: تسأل مُحلِّلاً
# يركّبه من يعرف (`utils/companies.py`)، وتسقط إلى المتغيّر العام إن لم يُركَّب
# — فسكربت أو اختبار بلا جلسة يعمل كما كان.
_active_company_id: Optional[int] = None


_company_resolver = None


def set_company_resolver(resolver):
    """يركّب مصدر الشركة الفاعلة. `None` يفكّه فتعود القيمة العامة."""
    global _company_resolver
    _company_resolver = resolver


def list_companies() -> list:
    rows = get_conn().execute(
        "SELECT id, name, created_at FROM company ORDER BY id"
    ).fetchall()
    return [dict(r) for r in rows]


def company_exists(company_id: Optional[int]) -> bool:
    if company_id is None:
        return False
    return get_conn().execute(
        "SELECT 1 FROM company WHERE id = ?", (company_id,)
    ).fetchone() is not None


def oldest_company_id() -> Optional[int]:
    """أقدم شركة — الافتراض حين لا اختيار. قاعدة بشركة واحدة تتصرّف كما كانت."""
    row = get_conn().execute("SELECT MIN(id) AS id FROM company").fetchone()
    return row["id"] if row and row["id"] is not None else None


def active_company_id() -> Optional[int]:
    """الشركة المختارة إن كانت لا تزال موجودة، وإلا أقدم شركة، وإلا `None`."""
    chosen = None
    if _company_resolver is not None:
        try:
            chosen = _company_resolver()
        except Exception:
            # جلسة غير جاهزة (خيط خلفي · سكربت) لا تُسقط الملف كله
            chosen = None
    if chosen is None:
        chosen = _active_company_id

    return chosen if company_exists(chosen) else oldest_company_id()


def set_active_company(company_id: Optional[int]):
    """الاختيار على مستوى العملية — الاحتياط حين لا مُحلِّل جلسة مركَّباً."""
    global _active_company_id
    _active_company_id = company_id
