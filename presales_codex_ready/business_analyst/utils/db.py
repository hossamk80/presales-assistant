"""
utils/db.py — التخزين الدائم (SQLite)

قبل هذه الطبقة كان كل شيء في session_state ويضيع بإغلاق المتصفح. الآن:
  · كل منافسة مشروع مستقل له تحليلاته وأقسامه وجداوله وملاحظات مراجعته.
  · ملف الشركة يُحفظ مرة واحدة ويُشارَك بين كل المنافسات.
  · مستودع المعرفة (مستندات + متجهات التضمين) يُحفظ للشركة كذلك.

قاعدة البيانات ملف واحد على القرص — لا خادم ولا خدمة خارجية، اتساقاً مع كون
النظام يعمل محلياً وبيانات العطاءات لا تغادر الجهاز.
"""
import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Optional

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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

-- إعدادات النظام (13-10): مفتاح ← قيمة. جدول واحد صغير بدل عمود لكل إعداد
-- جديد، وأول ساكنيه سياسة البيانات الشخصية (أساس المعالجة ومدة الاحتفاظ).
CREATE TABLE IF NOT EXISTS app_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
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
)

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


def _migrate(conn: sqlite3.Connection):
    """يُرقّي قاعدة بيانات أُنشئت بإصدار أقدم إلى المخطط الحالي."""
    _migrate_company(conn)
    for table, column, decl in _ADDED_COLUMNS:
        existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
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


# ─── النسخ الاحتياطي والاسترجاع (13-9) ────────────────────────────────────────

# ترويسة ملف SQLite — أول ما يُفحص في أي ملف يُقدَّم للاسترجاع.
SQLITE_MAGIC = b"SQLite format 3\x00"

# جداول لا تكون النسخة نسخةً بدونها. الفحص قبل الاستبدال لا بعده.
REQUIRED_TABLES = ("projects", "company", "kb_documents", "kb_chunks", "users")


def snapshot_bytes() -> bytes:
    """
    نسخة متّسقة من القاعدة كاملةً (المنافسات · الشركة · المعرفة · المستخدمون).

    عبر `sqlite3.Connection.backup` لا بنسخ الملف نسخاً خاماً: الاتصال مفتوح
    وقد تكون هناك كتابة جارية، فنسخ الملف حينها يُنتج نسخة ممزّقة تُستعاد
    بأخطاء لا تظهر إلا بعد فوات الأوان.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as folder:
        target = os.path.join(folder, "snapshot.db")
        destination = sqlite3.connect(target)
        try:
            get_conn().backup(destination)
        finally:
            destination.close()
        with open(target, "rb") as handle:
            return handle.read()


def validate_snapshot(data: bytes) -> bool:
    """هل هذه بايتات قاعدة صالحة تحمل جداول النظام؟"""
    import tempfile

    if not data or not data.startswith(SQLITE_MAGIC):
        return False
    with tempfile.TemporaryDirectory() as folder:
        probe = os.path.join(folder, "probe.db")
        with open(probe, "wb") as handle:
            handle.write(data)
        try:
            conn = sqlite3.connect(probe)
            names = {
                row[0] for row in
                conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
            conn.close()
        except sqlite3.DatabaseError:
            return False
    return all(table in names for table in REQUIRED_TABLES)


def restore_bytes(data: bytes) -> bool:
    """
    يستبدل القاعدة بنسخة احتياطية. يعيد `False` إن كانت النسخة غير صالحة.

    الفحص **قبل** الاستبدال، والاستبدال بـ `os.replace` (ذرّي على المنصة
    الواحدة) — فملف نصفه قديم ونصفه جديد أسوأ من استرجاع فاشل.
    """
    global _generation

    if not validate_snapshot(data):
        return False

    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    staging = f"{DB_PATH}.restoring"
    with open(staging, "wb") as handle:
        handle.write(data)

    conn = getattr(_local, "conn", None)
    if conn is not None:
        try:
            conn.close()
        except sqlite3.Error:
            pass
        _local.__dict__.pop("conn", None)

    os.replace(staging, DB_PATH)
    _generation += 1        # كل خيط آخر يُسقط اتصاله عند أول استعمال
    return True


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


# ─── المنافسات ────────────────────────────────────────────────────────────────


def list_projects() -> list:
    rows = get_conn().execute(
        "SELECT id, name, reference, entity, sector, created_at, updated_at, "
        "outcome, outcome_note FROM projects ORDER BY updated_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def set_outcome(project_id: int, outcome: str, note: str = ""):
    """يسجّل نتيجة المنافسة وسببها — مصدر ذاكرة العطاءات الوحيد."""
    with transaction() as conn:
        conn.execute(
            "UPDATE projects SET outcome = ?, outcome_note = ? WHERE id = ?",
            (outcome, note, project_id),
        )


def create_project(name: str, payload: dict, reference: str = "", entity: str = "",
                   sector: str = "") -> int:
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO projects (name, reference, entity, sector, created_at, "
            "updated_at, payload) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, reference, entity, sector, _now(), _now(),
             json.dumps(payload, ensure_ascii=False)),
        )
        return cur.lastrowid


def load_project(project_id: int) -> Optional[dict]:
    row = get_conn().execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    if row is None:
        return None
    data = dict(row)
    data["payload"] = json.loads(data["payload"])
    return data


def project_revision(project_id: int) -> Optional[int]:
    row = get_conn().execute(
        "SELECT revision FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    return None if row is None else int(row["revision"] or 0)


def save_project(project_id: int, payload: dict, name: Optional[str] = None,
                 reference: Optional[str] = None, entity: Optional[str] = None,
                 expected_revision: Optional[int] = None,
                 sector: Optional[str] = None) -> Optional[int]:
    """
    يحفظ المنافسة ويعيد رقم مراجعتها الجديد.

    **حفظ مشروط (13-7)**: عند تمرير `expected_revision` لا تُكتب الحمولة إلا إن
    كانت المراجعة المخزَّنة مطابقة لما رآه المُحرِّر آخر مرة، ويعيد `None` إن
    تغيّرت — أي أن جلسة أخرى كتبت بينهما. الشرط والكتابة في جملة `UPDATE`
    واحدة، فلا فجوة بين الفحص والكتابة تمرّ منها جلسة ثالثة.

    بلا `expected_revision` يبقى السلوك القديم: كتابة غير مشروطة.
    """
    sets = ["updated_at = ?", "payload = ?", "revision = revision + 1"]
    args: list[Any] = [_now(), json.dumps(payload, ensure_ascii=False)]
    for column, value in (("name", name), ("reference", reference),
                          ("entity", entity), ("sector", sector)):
        if value is not None:
            sets.append(f"{column} = ?")
            args.append(value)
    args.append(project_id)

    where = "id = ?"
    if expected_revision is not None:
        where += " AND revision = ?"
        args.append(expected_revision)

    with transaction() as conn:
        cur = conn.execute(f"UPDATE projects SET {', '.join(sets)} WHERE {where}", args)
        if cur.rowcount == 0:
            return None
    return project_revision(project_id)


def delete_project(project_id: int):
    with transaction() as conn:
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))


def duplicate_project(project_id: int, new_name: str) -> Optional[int]:
    src = load_project(project_id)
    if src is None:
        return None
    return create_project(new_name, src["payload"], src["reference"], src["entity"])


# ─── سير الاعتماد (13-8) ──────────────────────────────────────────────────────

# ثلاث مراحل بترتيبها. المفاتيح ثابتة لا تُترجم — التسميات في `i18n` تحت
# `ap.stage_<key>`، فقرار مخزَّن لا يتغيّر بتغيّر لغة قارئه.
APPROVAL_STAGES = ("bid_manager", "finance", "final")
APPROVED = "approved"
REJECTED = "rejected"


def record_approval(project_id: int, stage: str, decision: str, revision: int,
                    user_id: Optional[int] = None, username: str = "",
                    note: str = "") -> Optional[int]:
    """يسجّل قراراً على مرحلة. القرار السابق يُنقض بهذا لا يُحذف."""
    if stage not in APPROVAL_STAGES or decision not in (APPROVED, REJECTED):
        return None
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO approvals (project_id, stage, decision, revision, "
            "created_at, user_id, username, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (project_id, stage, decision, int(revision or 0), _now(), user_id,
             username, note),
        )
        return cur.lastrowid


def list_approvals(project_id: int, limit: int = 100) -> list:
    rows = get_conn().execute(
        "SELECT * FROM approvals WHERE project_id = ? ORDER BY id DESC LIMIT ?",
        (project_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def approval_state(project_id: int, revision: Optional[int] = None) -> dict:
    """
    حالة كل مرحلة الآن: آخر قرار عليها، وهل سقط لأن العرض تغيّر بعده.

    `stale` هو بيت القصيد: اعتماد على مراجعة أقدم ليس اعتماداً لما يُصدَّر اليوم.
    """
    if revision is None:
        revision = project_revision(project_id) or 0

    state = {}
    for stage in APPROVAL_STAGES:
        row = get_conn().execute(
            "SELECT * FROM approvals WHERE project_id = ? AND stage = ? "
            "ORDER BY id DESC LIMIT 1",
            (project_id, stage),
        ).fetchone()
        if row is None:
            state[stage] = {"decision": "", "username": "", "created_at": "",
                            "note": "", "revision": None, "stale": False}
            continue
        entry = dict(row)
        entry["stale"] = (entry["decision"] == APPROVED
                          and int(entry["revision"] or 0) != int(revision))
        state[stage] = entry
    return state


def approvals_complete(project_id: int, revision: Optional[int] = None) -> bool:
    """المراحل الثلاث معتمَدة على المراجعة الحالية — شرط التصدير النهائي."""
    state = approval_state(project_id, revision)
    return all(
        state[stage]["decision"] == APPROVED and not state[stage]["stale"]
        for stage in APPROVAL_STAGES
    )


def next_approval_stage(project_id: int, revision: Optional[int] = None) -> Optional[str]:
    """المرحلة التالية المطلوبة، أو `None` إن اكتملت كلها."""
    state = approval_state(project_id, revision)
    for stage in APPROVAL_STAGES:
        if state[stage]["decision"] != APPROVED or state[stage]["stale"]:
            return stage
    return None


def delete_approvals(project_id: int) -> int:
    """تُستدعى عند حذف المنافسة — قراراتها تذهب معها."""
    with transaction() as conn:
        cur = conn.execute("DELETE FROM approvals WHERE project_id = ?", (project_id,))
        return cur.rowcount


# ─── نسخ الأقسام (13-6) ───────────────────────────────────────────────────────

# أقصى عدد نسخ محفوظة لكل قسم. الأقدم يسقط تلقائياً — سجل بلا حدّ يُثقل القاعدة
# بنص لا يعود إليه أحد، والحاجة العملية هي الرجوع خطوات لا أشهراً.
SECTION_VERSION_LIMIT = 30


def add_section_version(section_key: str, content: str,
                        project_id: Optional[int] = None, user_id: Optional[int] = None,
                        username: str = "", source: str = "human") -> Optional[int]:
    """
    يحفظ نسخة من نص القسم. يعيد `None` إن كان النص مطابقاً لأحدث نسخة.

    التكرار مرفوض عمداً: دورة رسم تعيد الحفظ بلا تغيير لا يجوز أن تُنتج نسخة
    تُزحزح نسخة حقيقية خارج الحدّ.
    """
    latest = list_section_versions(section_key, project_id, limit=1)
    if latest and latest[0]["content"] == content:
        return None

    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO section_versions (project_id, section_key, created_at, "
            "user_id, username, source, content) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (project_id, section_key, _now(), user_id, username,
             source if source in ("human", "ai") else "human", content),
        )
        new_id = cur.lastrowid

    prune_section_versions(section_key, project_id)
    return new_id


def list_section_versions(section_key: str, project_id: Optional[int] = None,
                          limit: int = SECTION_VERSION_LIMIT) -> list:
    """أحدث النسخ أولاً."""
    rows = get_conn().execute(
        "SELECT * FROM section_versions WHERE section_key = ? "
        "AND project_id IS ? ORDER BY id DESC LIMIT ?",
        (section_key, project_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def get_section_version(version_id: int) -> Optional[dict]:
    row = get_conn().execute(
        "SELECT * FROM section_versions WHERE id = ?", (version_id,)
    ).fetchone()
    return dict(row) if row else None


def prune_section_versions(section_key: str, project_id: Optional[int] = None,
                           keep: int = SECTION_VERSION_LIMIT) -> int:
    """يُسقط أقدم النسخ فوق الحدّ. يعيد عدد ما أُسقط."""
    with transaction() as conn:
        cur = conn.execute(
            "DELETE FROM section_versions WHERE id IN ("
            "  SELECT id FROM section_versions WHERE section_key = ? "
            "  AND project_id IS ? ORDER BY id DESC LIMIT -1 OFFSET ?)",
            (section_key, project_id, keep),
        )
        return cur.rowcount


def delete_section_versions(project_id: int) -> int:
    """تُستدعى عند حذف المنافسة — نسخ أقسامها تذهب معها."""
    with transaction() as conn:
        cur = conn.execute(
            "DELETE FROM section_versions WHERE project_id = ?", (project_id,)
        )
        return cur.rowcount


# ─── سجل التدقيق (13-5) ───────────────────────────────────────────────────────
# إضافة وقراءة فقط. لا تحديث ولا حذف — عمداً.


def add_audit_entry(action: str, username: str = "", user_id: Optional[int] = None,
                    target: str = "", project_id: Optional[int] = None,
                    project_name: str = "", source: str = "human",
                    detail: str = "") -> int:
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO audit_log (created_at, user_id, username, action, target, "
            "project_id, project_name, source, detail) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (_now(), user_id, username, action, target, project_id, project_name,
             source, detail),
        )
        return cur.lastrowid


def list_audit_entries(limit: int = 200, project_id: Optional[int] = None,
                       user_id: Optional[int] = None, action: str = "",
                       target: str = "") -> list:
    """أحدث الأحداث أولاً. المرشّحات تُجمَع بـ AND، وأيّها فارغ يُتجاهل."""
    clauses, args = [], []
    if project_id is not None:
        clauses.append("project_id = ?")
        args.append(project_id)
    if user_id is not None:
        clauses.append("user_id = ?")
        args.append(user_id)
    if action:
        clauses.append("action = ?")
        args.append(action)
    if target:
        clauses.append("target = ?")
        args.append(target)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    args.append(limit)
    rows = get_conn().execute(
        f"SELECT * FROM audit_log {where} ORDER BY id DESC LIMIT ?", args
    ).fetchall()
    return [dict(r) for r in rows]


def count_audit_entries() -> int:
    return get_conn().execute("SELECT COUNT(*) AS n FROM audit_log").fetchone()["n"]


def latest_audit_entry(target: str, project_id: Optional[int] = None) -> Optional[dict]:
    """آخر حدث على هدف بعينه — مصدر جواب «من كتب هذا القسم آخر مرة»."""
    rows = list_audit_entries(limit=1, project_id=project_id, target=target)
    return rows[0] if rows else None


# ─── المستخدمون (13-2) ────────────────────────────────────────────────────────
# هذه الطبقة تخزّن وتقرأ فقط. التجزئة والتحقق ومنطق الجلسة في `utils/auth.py`.


def count_users(active_only: bool = False) -> int:
    sql = "SELECT COUNT(*) AS n FROM users"
    if active_only:
        sql += " WHERE active = 1"
    return get_conn().execute(sql).fetchone()["n"]


def list_users() -> list:
    rows = get_conn().execute(
        "SELECT id, username, display_name, role, active, created_at, last_login "
        "FROM users ORDER BY username"
    ).fetchall()
    return [dict(r) for r in rows]


def get_user(username: str) -> Optional[dict]:
    row = get_conn().execute(
        "SELECT * FROM users WHERE username = ?", (username.strip(),)
    ).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[dict]:
    row = get_conn().execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    return dict(row) if row else None


def create_user(username: str, password_hash: str, display_name: str = "",
                role: str = "admin", active: bool = True) -> Optional[int]:
    """يعيد معرّف المستخدم، أو `None` إن كان الاسم مستعملاً."""
    try:
        with transaction() as conn:
            cur = conn.execute(
                "INSERT INTO users (username, display_name, password_hash, role, "
                "active, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (username.strip(), display_name.strip(), password_hash, role,
                 1 if active else 0, _now()),
            )
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None


def set_user_password(user_id: int, password_hash: str):
    with transaction() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id)
        )


def set_user_role(user_id: int, role: str):
    with transaction() as conn:
        conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))


def set_user_active(user_id: int, active: bool):
    with transaction() as conn:
        conn.execute(
            "UPDATE users SET active = ? WHERE id = ?", (1 if active else 0, user_id)
        )


def update_user_profile(user_id: int, display_name: str):
    with transaction() as conn:
        conn.execute(
            "UPDATE users SET display_name = ? WHERE id = ?",
            (display_name.strip(), user_id),
        )


def touch_user_login(user_id: int):
    with transaction() as conn:
        conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (_now(), user_id))


def delete_user(user_id: int):
    with transaction() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


# ─── ملف الشركة ───────────────────────────────────────────────────────────────


# الشركة الفاعلة: النظام يعرض ملف شركة واحدة في كل لحظة. حتى تصل المستخدمون
# (13-2) يبقى الاختيار على مستوى العملية، وقيمته الافتراضية أقدم شركة مسجَّلة —
# فقاعدة بها شركة واحدة تتصرّف تماماً كما كانت قبل إلغاء القيد.
_active_company_id: Optional[int] = None


def list_companies() -> list:
    rows = get_conn().execute(
        "SELECT id, name, created_at FROM company ORDER BY id"
    ).fetchall()
    return [dict(r) for r in rows]


def active_company_id() -> Optional[int]:
    """الشركة المختارة إن كانت لا تزال موجودة، وإلا أقدم شركة، وإلا `None`."""
    row = get_conn().execute(
        "SELECT id FROM company WHERE id = ?", (_active_company_id,)
    ).fetchone() if _active_company_id is not None else None
    if row is not None:
        return row["id"]
    row = get_conn().execute("SELECT MIN(id) AS id FROM company").fetchone()
    return row["id"] if row and row["id"] is not None else None


def set_active_company(company_id: Optional[int]):
    global _active_company_id
    _active_company_id = company_id


def create_company(name: str = "", payload: Optional[dict] = None) -> int:
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO company (name, created_at, payload) VALUES (?, ?, ?)",
            (name, _now(), json.dumps(payload or {}, ensure_ascii=False)),
        )
        return cur.lastrowid


def rename_company(company_id: int, name: str):
    with transaction() as conn:
        conn.execute("UPDATE company SET name = ? WHERE id = ?", (name, company_id))


def delete_company(company_id: int) -> bool:
    """يحذف شركة. يعيد `False` إن لم تكن موجودة أو كانت الأخيرة الباقية."""
    ids = [r["id"] for r in list_companies()]
    if company_id not in ids or len(ids) <= 1:
        return False
    with transaction() as conn:
        conn.execute("DELETE FROM company WHERE id = ?", (company_id,))
    if _active_company_id == company_id:
        set_active_company(None)
    return True


def _company_row(company_id: Optional[int]):
    target = active_company_id() if company_id is None else company_id
    if target is None:
        return None
    return get_conn().execute(
        "SELECT * FROM company WHERE id = ?", (target,)
    ).fetchone()


def load_company(company_id: Optional[int] = None) -> tuple[dict, Optional[bytes],
                                                            Optional[bytes]]:
    row = _company_row(company_id)
    if row is None:
        return {}, None, None
    return json.loads(row["payload"]), row["template"], row["logo"]


def save_company(payload: dict, template: Optional[bytes] = None,
                 logo: Optional[bytes] = None,
                 company_id: Optional[int] = None) -> int:
    """
    يحفظ ملف الشركة ويعيد معرّفها. القالب والشعار يُحدَّثان فقط عند تمرير قيمة
    صريحة — وإلا فقد المستخدم قالب شركته بمجرد تعديل رقم هاتف.
    """
    existing = _company_row(company_id)
    if existing is None:
        with transaction() as conn:
            cur = conn.execute(
                "INSERT INTO company (id, name, created_at, payload, template, logo) "
                "VALUES (?, '', ?, ?, ?, ?)",
                (company_id, _now(), json.dumps(payload, ensure_ascii=False),
                 template, logo),
            )
            return company_id if company_id is not None else cur.lastrowid

    with transaction() as conn:
        conn.execute(
            "UPDATE company SET payload = ?, template = ?, logo = ? WHERE id = ?",
            (
                json.dumps(payload, ensure_ascii=False),
                existing["template"] if template is None else template,
                existing["logo"] if logo is None else logo,
                existing["id"],
            ),
        )
    return existing["id"]


def clear_company_template(company_id: Optional[int] = None):
    row = _company_row(company_id)
    if row is None:
        return
    with transaction() as conn:
        conn.execute("UPDATE company SET template = NULL WHERE id = ?", (row["id"],))


# ─── مستودع المعرفة ───────────────────────────────────────────────────────────


def add_kb_document(name: str, category: str, char_count: int,
                    person: str = "") -> int:
    """`person` (13-10): صاحب السيرة الذاتية — يربط المستند بمن يملك حذفه."""
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO kb_documents (name, category, added_at, char_count, person) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, category, _now(), char_count, (person or "").strip()),
        )
        return cur.lastrowid


def add_kb_chunks(doc_id: int, chunks: list, embed_model: str = ""):
    """chunks: [(ordinal, text, dims, embedding_bytes)]"""
    with transaction() as conn:
        conn.executemany(
            "INSERT INTO kb_chunks (doc_id, ordinal, text, dims, embedding, embed_model) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [(doc_id, o, t, d, e, embed_model) for o, t, d, e in chunks],
        )


def list_kb_documents() -> list:
    rows = get_conn().execute(
        "SELECT d.*, COUNT(c.id) AS chunks FROM kb_documents d "
        "LEFT JOIN kb_chunks c ON c.doc_id = d.id "
        "GROUP BY d.id ORDER BY d.added_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def all_kb_chunks(categories: Optional[list] = None) -> list:
    sql = (
        "SELECT c.id, c.text, c.dims, c.embedding, c.embed_model, "
        "d.name AS doc_name, d.category "
        "FROM kb_chunks c JOIN kb_documents d ON d.id = c.doc_id"
    )
    args: list[Any] = []
    if categories:
        sql += f" WHERE d.category IN ({','.join('?' * len(categories))})"
        args = list(categories)
    return [dict(r) for r in get_conn().execute(sql, args).fetchall()]


def delete_kb_document(doc_id: int):
    with transaction() as conn:
        conn.execute("DELETE FROM kb_chunks WHERE doc_id = ?", (doc_id,))
        conn.execute("DELETE FROM kb_documents WHERE id = ?", (doc_id,))


def kb_stats() -> dict:
    row = get_conn().execute(
        "SELECT (SELECT COUNT(*) FROM kb_documents) AS docs, "
        "(SELECT COUNT(*) FROM kb_chunks) AS chunks"
    ).fetchone()
    return dict(row)


# ─── البرومبتات (14-1) ────────────────────────────────────────────────────────


def list_prompts(key: str = "") -> list:
    sql = "SELECT * FROM prompts"
    args: list[Any] = []
    if key:
        sql += " WHERE key = ?"
        args.append(key)
    sql += " ORDER BY key, sector, language"
    return [dict(r) for r in get_conn().execute(sql, args).fetchall()]


def prompt_override(key: str, sector: str = "", language: str = "") -> Optional[dict]:
    """
    التجاوز الساري لهذا المفتاح، أو `None`.

    **الأخص يغلب**: (قطاع ولغة) ← (قطاع) ← (لغة) ← (عام). فبرومبت كُتب لقطاع
    الصحة لا يُزيحه عامٌّ كُتب قبله، ولا العكس.
    """
    for candidate in (
        (sector, language), (sector, ""), ("", language), ("", ""),
    ):
        row = get_conn().execute(
            "SELECT * FROM prompts WHERE key = ? AND sector = ? AND language = ? "
            "AND enabled = 1",
            (key, candidate[0], candidate[1]),
        ).fetchone()
        if row is not None:
            return dict(row)
    return None


def save_prompt(key: str, text: str, agent: str = "", sector: str = "",
                language: str = "", updated_by: str = "") -> int:
    """يحفظ تجاوزاً ويعيد رقم إصداره. الإصدار يزيد مع كل حفظ."""
    existing = get_conn().execute(
        "SELECT version FROM prompts WHERE key = ? AND sector = ? AND language = ?",
        (key, sector, language),
    ).fetchone()
    version = (int(existing["version"]) + 1) if existing else 1

    with transaction() as conn:
        conn.execute(
            "INSERT INTO prompts (key, agent, sector, language, version, text, "
            "enabled, updated_at, updated_by) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?) "
            "ON CONFLICT(key, sector, language) DO UPDATE SET "
            "text = excluded.text, agent = excluded.agent, version = excluded.version, "
            "enabled = 1, updated_at = excluded.updated_at, "
            "updated_by = excluded.updated_by",
            (key, agent, sector, language, version, text, _now(), updated_by),
        )
    return version


def set_prompt_enabled(key: str, enabled: bool, sector: str = "",
                       language: str = "") -> bool:
    """تعطيل تجاوز يعيد العمل بالنص الافتراضي بلا فقد ما كُتب."""
    with transaction() as conn:
        cur = conn.execute(
            "UPDATE prompts SET enabled = ? WHERE key = ? AND sector = ? "
            "AND language = ?",
            (1 if enabled else 0, key, sector, language),
        )
        return cur.rowcount > 0


def delete_prompt(key: str, sector: str = "", language: str = "") -> bool:
    """استعادة الافتراضي: يُحذف التجاوز فيعود النص من الشيفرة."""
    with transaction() as conn:
        cur = conn.execute(
            "DELETE FROM prompts WHERE key = ? AND sector = ? AND language = ?",
            (key, sector, language),
        )
        return cur.rowcount > 0


# ─── مكتبة المحتوى المعتمد (14-4) ─────────────────────────────────────────────
#
# كتل جاهزة تُدرَج في أقسام العرض **بلا استدعاء نموذج**. الطبقة هنا لا تعرف
# Streamlit ولا تلمس نص القسم — الإدراج نفسه في `views/doc_builder.py`.

BLOCK_DRAFT = "draft"
BLOCK_APPROVED = "approved"
BLOCK_RETIRED = "retired"
BLOCK_STATUSES = (BLOCK_DRAFT, BLOCK_APPROVED, BLOCK_RETIRED)

# دورة المراجعة الافتراضية بالأشهر. صفر = بلا دورة معلنة فلا تتأخّر الكتلة.
DEFAULT_REVIEW_MONTHS = 12


def _block_row(block_id: int):
    return get_conn().execute(
        "SELECT * FROM content_blocks WHERE id = ?", (int(block_id),)
    ).fetchone()


def get_content_block(block_id: int) -> Optional[dict]:
    row = _block_row(block_id)
    return dict(row) if row is not None else None


def content_block_by_key(key: str) -> Optional[dict]:
    row = get_conn().execute(
        "SELECT * FROM content_blocks WHERE key = ?", ((key or "").strip(),)
    ).fetchone()
    return dict(row) if row is not None else None


def list_content_blocks(status: str = "", category: str = "", sector: str = "",
                        language: str = "") -> list:
    """
    كتل المكتبة مرشّحة اختيارياً. `sector` و `language` يُطابقان **الموسَّع
    أيضاً**: كتلة بلا قطاع تصلح لكل القطاعات، فحصرها على المطابق التام يُخفي
    عن كاتب قطاع الصحة كل ما كُتب ليصلح للجميع.
    """
    sql = "SELECT * FROM content_blocks WHERE 1 = 1"
    args: list[Any] = []
    if status:
        sql += " AND status = ?"
        args.append(status)
    if category:
        sql += " AND category = ?"
        args.append(category)
    if sector:
        sql += " AND sector IN ('', ?)"
        args.append(sector)
    if language:
        sql += " AND language IN ('', ?)"
        args.append(language)
    sql += " ORDER BY category, title, key"
    return [dict(r) for r in get_conn().execute(sql, args).fetchall()]


def block_review_due(block: dict) -> bool:
    """
    هل تأخّرت الكتلة عن مراجعتها؟

    بلا دورة معلنة (صفر) لا شيء يتأخّر. وكتلة معتمدة بلا تاريخ مراجعة تُعدّ
    متأخّرة: «معتمد ولا نعرف متى» أسوأ من «معتمد ومضى عليه عام».
    """
    try:
        months = int(block.get("review_months") or 0)
    except (TypeError, ValueError):
        months = 0
    if months <= 0:
        return False

    reviewed = str(block.get("reviewed_at") or "").strip()
    if not reviewed:
        return True
    try:
        stamp = datetime.strptime(reviewed[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return True
    return datetime.now() - stamp > timedelta(days=30 * months)


def approved_blocks(sector: str = "", language: str = "") -> list:
    """
    ما يجوز إدراجه: المعتمد وحده. المسودّة والمسحوبة تبقيان في المكتبة للتحرير
    ولا تصلان إلى قسم — وهذا الفرق بين مكتبة معتمدة ومجلّد قصاصات.

    الترتيب يُنزل المتأخّر عن مراجعته إلى الآخر: يُدرَج بتحذير، ولا يُقترَح أولاً.
    """
    blocks = list_content_blocks(status=BLOCK_APPROVED, sector=sector,
                                 language=language)
    return sorted(blocks, key=lambda b: (block_review_due(b), b.get("title", "")))


def save_content_block(key: str, title: str, body: str, category: str = "",
                       sector: str = "", language: str = "",
                       review_months: Optional[int] = None,
                       updated_by: str = "") -> Optional[int]:
    """
    ينشئ كتلة أو يعدّلها، ويعيد معرّفها (أو `None` لمفتاح فارغ).

    **تغيير النصّ يُسقط الاعتماد** ويمسح تاريخ المراجعة: المعتمَد هو النصّ الذي
    قُرئ لا المفتاح الذي يحمله. أمّا تغيير العنوان أو التصنيف فلا يمسّ الاعتماد —
    إسقاطه لتصحيح حرف في عنوان يجعل الكتّاب يتجنّبون التصحيح.
    """
    key = (key or "").strip()
    if not key:
        return None
    body = body or ""
    now = _now()

    existing = content_block_by_key(key)
    if existing is None:
        months = (DEFAULT_REVIEW_MONTHS if review_months is None
                  else max(0, int(review_months)))
        with transaction() as conn:
            cur = conn.execute(
                "INSERT INTO content_blocks (key, title, body, category, sector, "
                "language, status, review_months, created_at, updated_at, updated_by) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (key, title or "", body, category or "", sector or "",
                 language or "", BLOCK_DRAFT, months, now, now, updated_by),
            )
            return int(cur.lastrowid)

    months = (int(existing["review_months"]) if review_months is None
              else max(0, int(review_months)))
    body_changed = body != (existing["body"] or "")
    status = BLOCK_DRAFT if body_changed else existing["status"]
    reviewed_at = "" if body_changed else existing["reviewed_at"]
    reviewed_by = "" if body_changed else existing["reviewed_by"]

    with transaction() as conn:
        conn.execute(
            "UPDATE content_blocks SET title = ?, body = ?, category = ?, "
            "sector = ?, language = ?, status = ?, reviewed_at = ?, "
            "reviewed_by = ?, review_months = ?, updated_at = ?, updated_by = ? "
            "WHERE id = ?",
            (title or "", body, category or "", sector or "", language or "",
             status, reviewed_at, reviewed_by, months, now, updated_by,
             int(existing["id"])),
        )
    return int(existing["id"])


def set_block_status(block_id: int, status: str, username: str = "") -> bool:
    """
    يغيّر حالة الكتلة. الاعتماد يختم **تاريخ مراجعة** معه: كتلة تُعتمد اليوم
    مراجَعة اليوم، فلا تُولد متأخّرة عن دورتها.
    """
    if status not in BLOCK_STATUSES:
        return False
    row = _block_row(block_id)
    if row is None:
        return False

    reviewed_at = _now() if status == BLOCK_APPROVED else row["reviewed_at"]
    reviewed_by = username if status == BLOCK_APPROVED else row["reviewed_by"]
    with transaction() as conn:
        conn.execute(
            "UPDATE content_blocks SET status = ?, reviewed_at = ?, "
            "reviewed_by = ?, updated_at = ? WHERE id = ?",
            (status, reviewed_at, reviewed_by, _now(), int(block_id)),
        )
    return True


def mark_block_reviewed(block_id: int, username: str = "") -> bool:
    """
    «راجعتُها ولم تتغيّر» — يجدّد التاريخ بلا لمس النصّ ولا الحالة. بدونه كان
    تأكيد صلاحية كتلة يستلزم تعديلاً وهمياً يُسقط اعتمادها.
    """
    if _block_row(block_id) is None:
        return False
    with transaction() as conn:
        conn.execute(
            "UPDATE content_blocks SET reviewed_at = ?, reviewed_by = ?, "
            "updated_at = ? WHERE id = ?",
            (_now(), username, _now(), int(block_id)),
        )
    return True


def record_block_use(block_id: int) -> int:
    """يزيد عدّاد الاستخدام ويعيد قيمته الجديدة (أو صفراً لكتلة غير موجودة)."""
    with transaction() as conn:
        cur = conn.execute(
            "UPDATE content_blocks SET used_count = used_count + 1 WHERE id = ?",
            (int(block_id),),
        )
        if not cur.rowcount:
            return 0
    row = _block_row(block_id)
    return int(row["used_count"]) if row is not None else 0


def delete_content_block(block_id: int) -> bool:
    with transaction() as conn:
        cur = conn.execute(
            "DELETE FROM content_blocks WHERE id = ?", (int(block_id),)
        )
        return cur.rowcount > 0


def content_block_stats() -> dict:
    """عدّاد لكل حالة + كم كتلة تأخّرت عن مراجعتها."""
    blocks = list_content_blocks()
    stats = {status: 0 for status in BLOCK_STATUSES}
    for block in blocks:
        if block["status"] in stats:
            stats[block["status"]] += 1
    stats["total"] = len(blocks)
    stats["due"] = sum(1 for b in blocks
                       if b["status"] == BLOCK_APPROVED and block_review_due(b))
    stats["used"] = sum(int(b["used_count"] or 0) for b in blocks)
    return stats


def project_costs() -> dict:
    """
    كلفة إعداد كل منافسة بالدولار: `{project_id: cost}` (14-7).

    تُقرأ من `ai_usage` لا تُقدَّر: كل استدعاء سُجّلت كلفته وقت وقوعه (11-8).
    منافسة بلا استدعاء **لا ترد هنا أصلاً** ولا ترد بصفر — الصفر كلفة مقيسة،
    والغياب غياب قياس، والخلط بينهما يهبط بالمتوسّط بمنافسات لم تُعالَج بعد.
    """
    rows = get_conn().execute(
        "SELECT project_id, SUM(cost) AS cost FROM ai_usage "
        "WHERE project_id IS NOT NULL GROUP BY project_id"
    ).fetchall()
    return {int(r["project_id"]): float(r["cost"] or 0.0) for r in rows}


# ─── مسرد المصطلحات (14-6) ────────────────────────────────────────────────────


def _glossary_row(row) -> dict:
    """يفكّ قائمة الصيغ المرفوضة. صفٌّ تالف يُقرأ بلا صيغ لا يُسقط المسرد كله."""
    item = dict(row)
    try:
        variants = json.loads(item.get("variants") or "[]")
    except (ValueError, TypeError):
        variants = []
    item["variants"] = [str(v).strip() for v in variants if str(v).strip()]
    return item


def list_glossary() -> list:
    """
    المسرد مرتّباً بالمصطلح.

    الترتيب ثابت لا عشوائي: الكتلة المحقونة في التوليد تُبنى منه، وترتيب متغيّر
    يعني كتلة مختلفة بين عرض وعرض — والغاية من هذا البند عكس ذلك تماماً.
    """
    rows = get_conn().execute(
        "SELECT * FROM glossary ORDER BY term COLLATE NOCASE"
    ).fetchall()
    return [_glossary_row(r) for r in rows]


def glossary_term(term_id: int) -> Optional[dict]:
    row = get_conn().execute(
        "SELECT * FROM glossary WHERE id = ?", (int(term_id),)
    ).fetchone()
    return _glossary_row(row) if row is not None else None


def glossary_by_term(term: str) -> Optional[dict]:
    row = get_conn().execute(
        "SELECT * FROM glossary WHERE term = ?", ((term or "").strip(),)
    ).fetchone()
    return _glossary_row(row) if row is not None else None


def save_glossary_term(term: str, preferred_ar: str = "", preferred_en: str = "",
                       variants: Optional[list] = None, note: str = "",
                       updated_by: str = "") -> Optional[int]:
    """
    ينشئ مصطلحاً أو يعدّله، ويعيد معرّفه (أو `None` لمصطلح فارغ).

    الصيغة المعتمدة **تُستبعد من الصيغ المرفوضة** ولو كتبها المستخدم فيهما:
    مصطلح يرفض صيغته المعتمدة يجعل كل قسم مخالفاً لنفسه.
    """
    term = (term or "").strip()
    if not term:
        return None

    preferred = {(preferred_ar or "").strip(), (preferred_en or "").strip(), term}
    cleaned = sorted({
        str(v).strip() for v in (variants or [])
        if str(v).strip() and str(v).strip() not in preferred
    })
    payload = json.dumps(cleaned, ensure_ascii=False)
    now = _now()

    existing = glossary_by_term(term)
    with transaction() as conn:
        if existing is None:
            cur = conn.execute(
                "INSERT INTO glossary (term, preferred_ar, preferred_en, variants, "
                "note, created_at, updated_at, updated_by) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (term, (preferred_ar or "").strip(), (preferred_en or "").strip(),
                 payload, note or "", now, now, updated_by),
            )
            return int(cur.lastrowid)
        conn.execute(
            "UPDATE glossary SET preferred_ar = ?, preferred_en = ?, variants = ?, "
            "note = ?, updated_at = ?, updated_by = ? WHERE id = ?",
            ((preferred_ar or "").strip(), (preferred_en or "").strip(), payload,
             note or "", now, updated_by, int(existing["id"])),
        )
    return int(existing["id"])


def delete_glossary_term(term_id: int) -> bool:
    with transaction() as conn:
        cur = conn.execute("DELETE FROM glossary WHERE id = ?", (int(term_id),))
        return cur.rowcount > 0


def preferred_form(entry: dict, language: str) -> str:
    """
    الصيغة المعتمدة للغة المخرجات، وإلا الأخرى، وإلا المصطلح نفسه.

    السقوط إلى الأخرى مقصود: مسرد نصف مملوء يوحّد ما استطاع بدل أن يصمت.
    """
    order = ("preferred_ar", "preferred_en") if str(language).startswith("ar") \
        else ("preferred_en", "preferred_ar")
    for key in order:
        value = str(entry.get(key) or "").strip()
        if value:
            return value
    return str(entry.get("term") or "").strip()


# ─── سياسة البيانات الشخصية (13-10) ───────────────────────────────────────────
#
# رفع السير الذاتية يُدخل النظام في نطاق نظام حماية البيانات الشخصية: لكل معالجة
# **أساس** معلن، ولكل احتفاظ **مدة**، ولكل شخص **حق الحذف**. الثلاثة هنا.

# أسس المعالجة المعلنة. المفاتيح ثابتة والتسميات في `i18n` تحت `pd.basis_<key>`.
LEGAL_BASES = ("contract", "consent", "legitimate_interest")
DEFAULT_LEGAL_BASIS = "contract"
# مدة الاحتفاظ الافتراضية بالأشهر — تُضبط من الواجهة، و0 تعني بلا حدّ معلن.
DEFAULT_RETENTION_MONTHS = 24

_PD_BASIS_KEY = "pd_legal_basis"
_PD_RETENTION_KEY = "pd_retention_months"


def app_setting(key: str, default: str = "") -> str:
    row = get_conn().execute(
        "SELECT value FROM app_settings WHERE key = ?", (key,)
    ).fetchone()
    return row["value"] if row else default


def set_app_setting(key: str, value: str):
    with transaction() as conn:
        conn.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )


def personal_data_policy() -> dict:
    """السياسة المعلنة: أساس المعالجة ومدة الاحتفاظ."""
    basis = app_setting(_PD_BASIS_KEY, DEFAULT_LEGAL_BASIS)
    try:
        months = int(app_setting(_PD_RETENTION_KEY, str(DEFAULT_RETENTION_MONTHS)))
    except ValueError:
        months = DEFAULT_RETENTION_MONTHS
    return {
        "legal_basis": basis if basis in LEGAL_BASES else DEFAULT_LEGAL_BASIS,
        "retention_months": max(0, months),
    }


def set_personal_data_policy(legal_basis: str, retention_months: int) -> bool:
    if legal_basis not in LEGAL_BASES or int(retention_months) < 0:
        return False
    set_app_setting(_PD_BASIS_KEY, legal_basis)
    set_app_setting(_PD_RETENTION_KEY, str(int(retention_months)))
    return True


def expired_cv_documents(months: Optional[int] = None) -> list:
    """
    السير التي تجاوزت مدة الاحتفاظ المعلنة. مدة صفر تعني بلا حدّ فلا يُعدّ شيء
    منتهياً — إعلان «نحتفظ بلا حدّ» أصدق من حذف صامت.
    """
    if months is None:
        months = personal_data_policy()["retention_months"]
    if not months:
        return []

    cutoff = datetime.now() - timedelta(days=30 * int(months))
    limit = cutoff.strftime("%Y-%m-%d %H:%M:%S")
    rows = get_conn().execute(
        "SELECT d.*, COUNT(c.id) AS chunks FROM kb_documents d "
        "LEFT JOIN kb_chunks c ON c.doc_id = d.id "
        "WHERE d.category = 'cv' AND d.added_at < ? "
        "GROUP BY d.id ORDER BY d.added_at",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def person_footprint(name: str) -> dict:
    """ما يخصّ هذا الشخص في النظام — يُعرض قبل الحذف لا بعده."""
    name = (name or "").strip()
    if not name:
        return {"records": 0, "documents": 0, "chunks": 0}

    records = [r for r in list_records("people")
               if str(r.get("name", "")).strip() == name]
    docs = _person_documents(name)
    return {
        "records": len(records),
        "documents": len(docs),
        "chunks": sum(d["chunks"] for d in docs),
    }


def _person_documents(name: str) -> list:
    """
    مستندات الشخص: ما رُبط به صراحةً، وما سمّاه صفّه في سجل الكوادر.

    الاثنان معاً لأن الربط الصريح أُضيف في 13-10: سيرة رُفعت قبله لا تحمل ربطاً،
    وحقّ الشخص في حذفها لا ينتظر ترقية.
    """
    linked_names = {
        str(r.get("cv_document", "")).strip()
        for r in list_records("people")
        if str(r.get("name", "")).strip() == name and str(r.get("cv_document", "")).strip()
    }
    rows = get_conn().execute(
        "SELECT d.*, COUNT(c.id) AS chunks FROM kb_documents d "
        "LEFT JOIN kb_chunks c ON c.doc_id = d.id "
        "GROUP BY d.id"
    ).fetchall()
    return [
        dict(r) for r in rows
        if (r["person"] or "").strip() == name or r["name"] in linked_names
    ]


def forget_person(name: str) -> dict:
    """
    حقّ الحذف عند الطلب: يمحو صفّ الشخص في سجل الكوادر وسيرته ومقاطعها.

    المقاطع أخطر ما في الباب: نصّ السيرة يعيش فيها مُقطَّعاً، فحذف المستند
    وحده يترك بيانات الشخص في المستودع تُسترجَع في كل توليد.
    """
    name = (name or "").strip()
    if not name:
        return {"records": 0, "documents": 0, "chunks": 0}

    removed = {"records": 0, "documents": 0, "chunks": 0}

    documents = _person_documents(name)
    for doc in documents:
        delete_kb_document(doc["id"])
        removed["documents"] += 1
        removed["chunks"] += doc["chunks"]

    people = list_records("people")
    kept = [r for r in people if str(r.get("name", "")).strip() != name]
    removed["records"] = len(people) - len(kept)
    if removed["records"]:
        save_records("people", kept)

    return removed


# ─── نسخ المرفقات ─────────────────────────────────────────────────────────────


def add_attachment_version(project_id: int, texts: dict, roles: dict,
                           label: str = "") -> int:
    """يحفظ لقطة من نصوص المرفقات وأدوارها كما هي وقت الرفع."""
    payload = {"texts": texts or {}, "roles": roles or {}}
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO attachment_versions (project_id, created_at, label, payload) "
            "VALUES (?, ?, ?, ?)",
            (project_id, _now(), label, json.dumps(payload, ensure_ascii=False)),
        )
        return cur.lastrowid


def list_attachment_versions(project_id: int) -> list:
    """بيانات النسخ بلا حمولتها — القائمة تُعرض كثيراً والنصوص ضخمة."""
    rows = get_conn().execute(
        "SELECT id, created_at, label, LENGTH(payload) AS size "
        "FROM attachment_versions WHERE project_id = ? ORDER BY id DESC",
        (project_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def load_attachment_version(version_id: int) -> Optional[dict]:
    row = get_conn().execute(
        "SELECT * FROM attachment_versions WHERE id = ?", (version_id,)
    ).fetchone()
    if row is None:
        return None
    data = dict(row)
    data["payload"] = json.loads(data["payload"])
    return data


def previous_attachment_version(project_id: int,
                                before_id: Optional[int] = None) -> Optional[dict]:
    """أحدث نسخة قبل المعرّف المعطى — طرف المقارنة الافتراضي."""
    if before_id is None:
        rows = get_conn().execute(
            "SELECT id FROM attachment_versions WHERE project_id = ? "
            "ORDER BY id DESC LIMIT 1 OFFSET 1",
            (project_id,),
        ).fetchone()
    else:
        rows = get_conn().execute(
            "SELECT id FROM attachment_versions WHERE project_id = ? AND id < ? "
            "ORDER BY id DESC LIMIT 1",
            (project_id, before_id),
        ).fetchone()
    return load_attachment_version(rows["id"]) if rows else None


def delete_attachment_version(version_id: int):
    with transaction() as conn:
        conn.execute("DELETE FROM attachment_versions WHERE id = ?", (version_id,))


# ─── سجلات الأدلة (المرحلة 12) ───────────────────────────────────────────────


def list_records(registry: str) -> list:
    """صفوف السجل بترتيبها المحفوظ."""
    rows = get_conn().execute(
        "SELECT payload FROM company_records WHERE registry = ? "
        "ORDER BY ordinal, id",
        (registry,),
    ).fetchall()
    out = []
    for row in rows:
        try:
            out.append(json.loads(row["payload"]))
        except ValueError:
            continue
    return out


def save_records(registry: str, rows: list):
    """
    يستبدل صفوف السجل بالكامل.

    الاستبدال الكامل يطابق محرر الجداول في الواجهة: المستخدم يحرّر الجدول كله
    ثم يحفظ، فالمزامنة صفاً صفاً تُعقّد بلا مكسب على عشرات الصفوف.
    """
    with transaction() as conn:
        conn.execute("DELETE FROM company_records WHERE registry = ?", (registry,))
        conn.executemany(
            "INSERT INTO company_records (registry, ordinal, payload) VALUES (?, ?, ?)",
            [(registry, i, json.dumps(row, ensure_ascii=False))
             for i, row in enumerate(rows or [])],
        )


def record_counts() -> dict:
    """عدد الصفوف في كل سجل — لمؤشرات الاكتمال."""
    rows = get_conn().execute(
        "SELECT registry, COUNT(*) AS n FROM company_records GROUP BY registry"
    ).fetchall()
    return {r["registry"]: r["n"] for r in rows}


def find_entity(name: str) -> Optional[dict]:
    """
    ملف الجهة بالاسم، بمطابقة مُوحَّدة الإملاء.

    «وزارة الصحة» و«وزاره الصحه» جهة واحدة — نفس التوحيد المستعمل في ذاكرة
    العطاءات، وإلا بقي الملف غير مستدعىً لأن الاسم كُتب بصيغة أخرى.
    """
    from utils.history import normalize_entity

    target = normalize_entity(name)
    if not target:
        return None
    for row in list_records("entities"):
        if normalize_entity(row.get("name", "")) == target:
            return row
    return None


# ─── قياس الاستهلاك (11-7 / 11-8) ────────────────────────────────────────────


def log_ai_usage(project_id, project_name: str, task: str, provider: str,
                 model: str, input_tokens: int, cached_tokens: int,
                 output_tokens: int, cost: float, elapsed_ms: int,
                 status: str, month: str):
    with transaction() as conn:
        conn.execute(
            "INSERT INTO ai_usage (created_at, month, project_id, project_name, "
            "task, provider, model, input_tokens, cached_tokens, output_tokens, "
            "cost, elapsed_ms, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (_now(), month, project_id, project_name, task, provider, model,
             input_tokens, cached_tokens, output_tokens, cost, elapsed_ms, status),
        )


def usage_month_cost(month: str) -> float:
    row = get_conn().execute(
        "SELECT COALESCE(SUM(cost), 0) AS total FROM ai_usage WHERE month = ?",
        (month,),
    ).fetchone()
    return float(row["total"])


_USAGE_GROUPS = {
    "project": "COALESCE(NULLIF(project_name, ''), 'بلا منافسة / no tender')",
    "task": "task",
    "model": "provider || ' / ' || model",
    "provider": "provider",
}


def usage_summary(group_by: str = "project", month: str = "") -> list:
    """إجماليات الاستهلاك مجمّعة — لشاشة الاستهلاك (11-8)."""
    expr = _USAGE_GROUPS.get(group_by, _USAGE_GROUPS["project"])
    sql = (
        f"SELECT {expr} AS grp, COUNT(*) AS calls, "
        "SUM(input_tokens) AS input_tokens, SUM(cached_tokens) AS cached_tokens, "
        "SUM(output_tokens) AS output_tokens, SUM(cost) AS cost "
        "FROM ai_usage"
    )
    args: list[Any] = []
    if month:
        sql += " WHERE month = ?"
        args.append(month)
    sql += " GROUP BY grp ORDER BY cost DESC"
    return [dict(r) for r in get_conn().execute(sql, args).fetchall()]


def usage_totals(month: str = "") -> dict:
    sql = (
        "SELECT COUNT(*) AS calls, COALESCE(SUM(input_tokens), 0) AS input_tokens, "
        "COALESCE(SUM(cached_tokens), 0) AS cached_tokens, "
        "COALESCE(SUM(output_tokens), 0) AS output_tokens, "
        "COALESCE(SUM(cost), 0) AS cost, "
        "SUM(CASE WHEN status = 'cache' THEN 1 ELSE 0 END) AS cache_hits "
        "FROM ai_usage"
    )
    args: list[Any] = []
    if month:
        sql += " WHERE month = ?"
        args.append(month)
    return dict(get_conn().execute(sql, args).fetchone())


# ─── ذاكرة نتائج الاستدعاءات (11-13) ─────────────────────────────────────────


def ai_cache_get(fingerprint: str) -> Optional[str]:
    row = get_conn().execute(
        "SELECT result FROM ai_cache WHERE fingerprint = ?", (fingerprint,)
    ).fetchone()
    return row["result"] if row else None


def ai_cache_put(fingerprint: str, provider: str, model: str, result: str):
    with transaction() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO ai_cache (fingerprint, created_at, provider, "
            "model, result) VALUES (?, ?, ?, ?, ?)",
            (fingerprint, _now(), provider, model, result),
        )


def ai_cache_clear():
    with transaction() as conn:
        conn.execute("DELETE FROM ai_cache")


# ─── إبطال متجهات المستودع عند تغيير نموذج التضمين (11-6) ────────────────────


def kb_stale_chunk_count(embed_model: str) -> int:
    """عدد المقاطع المفهرسة بنموذج تضمين مختلف عن النشط — مُعطَّلة عن البحث."""
    row = get_conn().execute(
        "SELECT COUNT(*) AS n FROM kb_chunks "
        "WHERE COALESCE(embed_model, '') != ?",
        (embed_model,),
    ).fetchone()
    return int(row["n"])


def kb_chunk_texts() -> list:
    """كل المقاطع (المعرّف والنص) — لإعادة الفهرسة بالنموذج النشط."""
    rows = get_conn().execute("SELECT id, text FROM kb_chunks ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def update_kb_chunk_embeddings(rows: list, embed_model: str):
    """rows: [(chunk_id, dims, embedding_bytes)] — بعد إعادة التضمين."""
    with transaction() as conn:
        conn.executemany(
            "UPDATE kb_chunks SET dims = ?, embedding = ?, embed_model = ? "
            "WHERE id = ?",
            [(d, e, embed_model, cid) for cid, d, e in rows],
        )
