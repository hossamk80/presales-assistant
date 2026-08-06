"""
utils/records.py — سجلات الأدلة (المرحلة 12)

قبل هذه الطبقة كانت المطابقة نصية: «لدينا خبرة واسعة» و«نفّذنا مشاريع مماثلة».
لجنة الفحص لا تقبل ذلك — تسأل: **مَن** و**أين** و**بأي مستند**. هنا تُخزَّن
الإجابة صفوفاً: الكوادر · سابقة الأعمال · الشهادات · الموردون · الجهات.

كل السجلات تتبع الشكل نفسه (جدول بأعمدة معلنة) فتُدار بشيفرة واحدة بدل خمس
نسخ متشابهة: التعريف هنا، والتخزين في `db.py`، والعرض في `views/company.py`.

**السجلات ملك الشركة لا المنافسة** — تُحفظ مرة وتُستعمل في كل عطاء. باستثناء
`entities` فهو ملف الجهة المصدِرة، ويُستدعى عند فتح منافسة لها.
"""
from datetime import date
from typing import Optional

# أنواع الأعمدة: text · longtext · int · date · bool · choice
TEXT, LONGTEXT, INT, DATE, BOOL, CHOICE = (
    "text", "longtext", "int", "date", "bool", "choice",
)

PARTNERSHIP_LEVELS = ["", "Registered", "Silver", "Gold", "Platinum", "Elite", "أخرى"]
# 13-10: أسس المعالجة المعلنة في سجل الكوادر
LEGAL_BASES = ("عقد عمل", "موافقة صريحة", "مصلحة مشروعة")

AVAILABILITY = ["متاح", "مرتبط جزئياً", "مرتبط بالكامل", "غير معلوم"]
OUR_ROLES = ["مقاول رئيسي", "مقاول من الباطن", "شريك في تحالف", "مورّد"]


def _col(key, label_key, kind=TEXT, options=None, default=""):
    return {"key": key, "label_key": label_key, "kind": kind,
            "options": options, "default": default}


# ─── تعريف السجلات ────────────────────────────────────────────────────────────

REGISTRIES = {
    # 12-1: الكوادر — «الكوادر الرئيسية» بند تقييم مستقل في اعتماد
    "people": {
        "label_key": "rec.people",
        "hint_key": "rec.people_hint",
        "columns": [
            _col("name", "rec.p_name"),
            _col("role", "rec.p_role"),
            _col("years", "rec.p_years", INT, default=0),
            _col("certifications", "rec.p_certs", LONGTEXT),
            _col("cert_expiry", "rec.p_cert_expiry", DATE),
            _col("languages", "rec.p_languages"),
            _col("availability", "rec.p_availability", CHOICE,
                 options=AVAILABILITY, default="غير معلوم"),
            _col("cv_document", "rec.p_cv"),
            # 13-10: أساس معالجة بيانات هذا الشخص — يُعلن لكل صفّ لا للنظام
            # جملةً، فالموظف والمرشّح والمستشار لا يتساوى أساسهم.
            _col("legal_basis", "rec.p_basis", CHOICE,
                 options=LEGAL_BASES, default=LEGAL_BASES[0]),
        ],
    },
    # 12-3: سابقة الأعمال — «ثلاثة مشاريع مماثلة» تُطابَق بصفوف لا بنص
    "references": {
        "label_key": "rec.references",
        "hint_key": "rec.references_hint",
        "columns": [
            _col("client", "rec.r_client"),
            _col("sector", "rec.r_sector"),
            _col("scope", "rec.r_scope", LONGTEXT),
            _col("value_band", "rec.r_value"),
            _col("duration", "rec.r_duration"),
            _col("our_role", "rec.r_our_role", CHOICE,
                 options=OUR_ROLES, default="مقاول رئيسي"),
            _col("completion_certificate", "rec.r_completion", BOOL, default=False),
            _col("contact", "rec.r_contact"),
        ],
    },
    # 12-4: الشهادات والتصنيفات — انتهاؤها قبل الموعد سبب استبعاد
    "certificates": {
        "label_key": "rec.certificates",
        "hint_key": "rec.certificates_hint",
        "columns": [
            _col("kind", "rec.c_kind"),
            _col("number", "rec.c_number"),
            _col("issuer", "rec.c_issuer"),
            _col("issued", "rec.c_issued", DATE),
            _col("expiry", "rec.c_expiry", DATE),
            _col("document", "rec.c_document"),
        ],
    },
    # 12-5: الموردون — خطاب تفويض منتهٍ أو غائب يُسقط مستندات المظروف
    "vendors": {
        "label_key": "rec.vendors",
        "hint_key": "rec.vendors_hint",
        "columns": [
            _col("vendor", "rec.v_vendor"),
            _col("product_line", "rec.v_line"),
            _col("partnership", "rec.v_partnership", CHOICE,
                 options=PARTNERSHIP_LEVELS),
            _col("authorization_letter", "rec.v_letter", BOOL, default=False),
            _col("letter_expiry", "rec.v_letter_expiry", DATE),
            _col("local_support", "rec.v_support", BOOL, default=False),
            _col("eol_eos", "rec.v_eol", DATE),
            _col("alternative", "rec.v_alt"),
        ],
    },
    # 12-7: ملف الجهة — سلوك الجهة في التقييم يتكرّر
    "entities": {
        "label_key": "rec.entities",
        "hint_key": "rec.entities_hint",
        "columns": [
            _col("name", "rec.e_name"),
            _col("sector", "rec.e_sector"),
            _col("contacts", "rec.e_contacts", LONGTEXT),
            _col("evaluation_pattern", "rec.e_pattern", LONGTEXT),
            _col("recurring_requirements", "rec.e_recurring", LONGTEXT),
        ],
    },
}

# السجلات المملوكة للشركة (تُعرض في شاشة ملف الشركة)
COMPANY_REGISTRIES = ("people", "references", "certificates", "vendors")


def columns_of(registry: str) -> list:
    return REGISTRIES[registry]["columns"]


def column_keys(registry: str) -> list:
    return [c["key"] for c in columns_of(registry)]


def blank_row(registry: str) -> dict:
    return {c["key"]: c["default"] for c in columns_of(registry)}


def normalize_row(registry: str, row: dict) -> dict:
    """يضمن أن الصف يحمل كل الأعمدة بأنواعها — الصفوف تأتي من محرر حر."""
    out = blank_row(registry)
    for col in columns_of(registry):
        value = (row or {}).get(col["key"], col["default"])
        if col["kind"] == INT:
            try:
                out[col["key"]] = int(float(value))
            except (TypeError, ValueError):
                out[col["key"]] = 0
        elif col["kind"] == BOOL:
            out[col["key"]] = bool(value)
        else:
            text = "" if value is None else str(value).strip()
            out[col["key"]] = "" if text.lower() in ("nan", "nat", "none") else text
    return out


def identity_column(registry: str) -> str:
    """
    العمود الذي يُعرَّف به الصف: الاسم · العميل · النوع · المورّد · الجهة.

    أول عمود نصّي في التعريف، وهو دائماً المُعرِّف في هذه السجلات.
    """
    return columns_of(registry)[0]["key"]


def is_blank(registry: str, row: dict) -> bool:
    """
    صف بلا هوية — لا يُحفظ.

    المعيار هو العمود المُعرِّف وحده لا بقية الحقول: «سنوات الخبرة: 7» بلا اسم
    ليست دليلاً، وحقنها في قرار الخوض يُنتج سطراً بلا صاحب. وأعمدة القوائم
    تبدأ بقيمة افتراضية («غير معلوم») فقياس الفراغ وحده كان يعدّ كل صف يتركه
    المحرّر صفاً حقيقياً.

    الصفوف المكتوبة جزئياً بلا هوية لا تختفي صامتةً — `partial_rows` تعدّها
    والواجهة تُبلّغ بها.
    """
    return not str(row.get(identity_column(registry), "")).strip()


def partial_rows(registry: str, rows: list) -> int:
    """صفوف فيها إدخال لكن بلا هوية — تُسقَط، فتُعرَض للمستخدم قبل ضياعها."""
    count = 0
    for row in rows or []:
        if not is_blank(registry, row):
            continue
        for col in columns_of(registry):
            value = row.get(col["key"], col["default"])
            if col["kind"] == BOOL:
                differs = bool(value) != bool(col["default"])
            elif col["kind"] == INT:
                try:
                    differs = int(float(value)) != int(col["default"])
                except (TypeError, ValueError):
                    differs = False
            else:
                differs = str(value).strip() != str(col["default"]).strip()
            if differs:
                count += 1
                break
    return count


# ─── التواريخ والصلاحية ───────────────────────────────────────────────────────

def parse_date(value) -> Optional[date]:
    """
    تاريخ من نص — ميلادياً كان أو **هجرياً**.

    نفوّضه إلى `utils/submission.py` الذي يقرأ تقويم أم القرى: شهادات المقاولين
    والتصنيفات تُؤرَّخ هجرياً كثيراً، وقارئ ميلادي وحده يُرجع None لها فتسقط
    من فحص الصلاحية صامتةً — وهي بالضبط ما يجب أن يُفحص.
    """
    from utils import submission

    parsed = submission.parse_date(value)
    if parsed is None or not submission.is_hijri_year(parsed.year):
        return parsed

    # سنة في المدى الهجري كُتبت بلا وسم: «1448-11-14» تُقرأ ميلادياً فتصير
    # ماضياً سحيقاً، فتُحسب شهادة سارية منتهيةً. نعيد القراءة هجرياً.
    return submission.parse_date(f"{value} هـ")


def expiring_before(rows: list, field: str, deadline: Optional[date]) -> list:
    """
    الصفوف التي ينتهي `field` فيها قبل الموعد.

    تاريخ تعذّرت قراءته **لا يُعدّ سارياً ولا منتهياً** — يُستبعد من النتيجة
    ويبقى قرار البشر. الحكم على شهادة بتخمين تاريخ يُبنى عليه قرار تسليم.
    """
    if deadline is None:
        return []
    out = []
    for row in rows or []:
        parsed = parse_date(row.get(field))
        if parsed is not None and parsed < deadline:
            out.append(row)
    return out


def undated(rows: list, field: str) -> list:
    """صفوف بلا تاريخ صالح في هذا الحقل — تُعرض للمراجعة لا للحكم."""
    return [r for r in rows or []
            if str(r.get(field, "")).strip() and parse_date(r.get(field)) is None]
