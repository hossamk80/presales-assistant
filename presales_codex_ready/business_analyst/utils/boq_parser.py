"""
utils/boq_parser.py — قراءة جدول الكميات من الملف مباشرةً بلا نموذج.

جدول الكميات في منافسات اعتماد يأتي غالباً ملف Excel أو CSV — أي **بيانات
مُهيكلة أصلاً**. وكان مسارها: تُحوَّل إلى نص، يُرسَل النص كاملاً إلى النموذج،
فيُعيد بناء الجدول JSON. أي أننا ندفع توكناً لنطلب من نموذج لغوي أن يفعل ما
تفعله قراءة أعمدة: عملية حسابية بحتة، أدقّ منه فيها وأسرع وبلا كلفة.

هذه الوحدة تقرأ الملف وتطابق ترويسات أعمدته بمرادفاتها العربية والإنجليزية.
تنجح فتوفّر الاستدعاء كاملاً، وتفشل فيبقى مسار النموذج كما هو — الفشل هنا
رجوع إلى ما كان لا خسارة.

**لا تقرأ الأسعار.** عمود السعر إن وُجد في الملف يُتجاهل: جدول الكميات في هذا
النظام يخدم العرض الفني، والتسعير مظروف منفصل.
"""
import re
from typing import Optional

import pandas as pd

# مرادفات ترويسات الأعمدة. المطابقة على النص المُوحَّد (بلا تشكيل ولا مسافات
# زائدة)، وتقبل الاحتواء الجزئي لأن الترويسات تأتي بصياغات لا تُحصى.
COLUMN_ALIASES = {
    "رقم البند": [
        "رقم البند", "رقم", "م", "ت", "تسلسل", "الرقم", "رقم الصنف", "كود البند",
        "item no", "item number", "no", "sn", "s/n", "serial", "code", "ref",
    ],
    "التصنيف": [
        "التصنيف", "الفئة", "المجموعة", "القسم", "البند الرئيسي",
        "category", "group", "section", "classification",
    ],
    "البند": [
        "البند", "الصنف", "اسم البند", "الخدمة", "المنتج", "بيان الأعمال",
        "item", "description of item", "item name", "service", "product",
    ],
    "الوحدة": [
        "الوحدة", "وحدة القياس", "الوحده",
        "unit", "uom", "unit of measure",
    ],
    "الوصف": [
        "الوصف", "التفاصيل", "بيان", "شرح", "الوصف التفصيلي",
        "description", "details", "scope",
    ],
    "المواصفات": [
        "المواصفات", "المواصفات الفنية", "مواصفات", "ملاحظات", "المتطلبات الفنية",
        "specification", "specifications", "specs", "technical", "remarks", "notes",
    ],
    "كود البناء": [
        "كود البناء", "الكود", "كود", "المرجع", "رقم الكتالوج", "الموديل",
        "construction code", "catalog", "model", "part number", "sku",
    ],
    "الكمية": [
        "الكمية", "العدد", "كمية", "الكميه",
        "quantity", "qty", "count",
    ],
}

# أعمدة مالية تُتجاهل عمداً — الفني والمالي مظروفان منفصلان.
PRICE_HINTS = [
    "سعر", "السعر", "الأسعار", "قيمة", "القيمة", "الإجمالي", "الاجمالي",
    "المجموع", "تكلفة", "التكلفة", "ريال", "ضريبة", "الضريبة",
    "price", "cost", "amount", "total", "value", "vat", "rate", "sar",
]

# أقل نسبة أعمدة مطلوبة نتعرّف عليها لنثق بالقراءة المباشرة.
MIN_CONFIDENCE = 0.5

# عمودان لا معنى للجدول بدونهما
ESSENTIAL = ("البند", "الكمية")

_DIACRITICS = re.compile(r"[ً-ْـ]")
_EASTERN_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def normalize_header(text) -> str:
    """صيغة موحّدة لمقارنة ترويسات الأعمدة."""
    value = _DIACRITICS.sub("", str(text or ""))
    value = value.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    value = value.replace("ة", "ه").replace("ى", "ي")
    value = re.sub(r"[^\w\s/]", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip().lower()


_NORMALIZED_ALIASES = {
    target: [normalize_header(a) for a in aliases]
    for target, aliases in COLUMN_ALIASES.items()
}
_NORMALIZED_PRICE = [normalize_header(p) for p in PRICE_HINTS]


def is_price_column(header) -> bool:
    return any(hint in normalize_header(header) for hint in _NORMALIZED_PRICE)


def match_column(header) -> Optional[str]:
    """
    يطابق ترويسة عمود بأحد أعمدة المخطط، أو None.

    الأعمدة المالية تُرجع None صراحةً حتى لا تُلتقط بالمطابقة الجزئية —
    «سعر الوحدة» يحوي «الوحدة».
    """
    normalized = normalize_header(header)
    if not normalized or is_price_column(header):
        return None

    for target, aliases in _NORMALIZED_ALIASES.items():
        if normalized in aliases:
            return target
    # مطابقة جزئية: «وصف البند التفصيلي» تُطابق «الوصف»
    for target, aliases in _NORMALIZED_ALIASES.items():
        for alias in aliases:
            if len(alias) >= 3 and (alias in normalized or normalized in alias):
                return target
    return None


def find_header_row(frame: "pd.DataFrame", scan_rows: int = 12) -> Optional[int]:
    """
    يبحث عن صف الترويسة.

    ملفات الكميات تبدأ عادةً بشعار الجهة واسم المنافسة قبل الجدول، فترويسة
    `read_excel` الافتراضية تقع على سطر عنوان لا على أسماء الأعمدة.
    """
    best, best_score = None, 0
    for index in range(min(scan_rows, len(frame))):
        row = frame.iloc[index]
        hits = sum(1 for cell in row if match_column(cell))
        if hits > best_score:
            best, best_score = index, hits
    return best if best_score >= 2 else None


def _clean_quantity(value) -> float:
    """يقرأ كمية مكتوبة بأي صيغة. غير المقروء يصير 1 لا 0 — الصفر يوهم بالمجّان."""
    if isinstance(value, (int, float)) and not pd.isna(value):
        return float(value)
    text = str(value or "").translate(_EASTERN_DIGITS)
    match = re.search(r"\d+(?:[.,]\d+)?", text.replace(",", ""))
    return float(match.group(0)) if match else 1.0


def parse_frame(frame: "pd.DataFrame") -> tuple[Optional["pd.DataFrame"], dict]:
    """
    يحوّل ورقة بيانات خاماً إلى جدول كميات بمخطط النظام.

    Returns:
        (الجدول أو None، تقرير: الأعمدة المُطابَقة · المتجاهَلة · الثقة · السبب)
    """
    from utils.state import BOQ_COLUMNS, DEFAULT_BOQ_DF

    report = {"matched": {}, "ignored_price": [], "unmatched": [],
              "confidence": 0.0, "rows": 0, "reason": ""}

    if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
        report["reason"] = "empty"
        return None, report

    # صف الترويسة قد يكون داخل الجدول لا في أعلاه
    header_hits = sum(1 for c in frame.columns if match_column(c))
    if header_hits < 2:
        row = find_header_row(frame)
        if row is None:
            report["reason"] = "no_header"
            return None, report
        frame = frame.copy()
        frame.columns = [str(c) for c in frame.iloc[row]]
        frame = frame.iloc[row + 1:].reset_index(drop=True)

    mapping = {}
    for column in frame.columns:
        if is_price_column(column):
            report["ignored_price"].append(str(column))
            continue
        target = match_column(column)
        if target and target not in mapping.values():
            mapping[column] = target
        elif target is None:
            report["unmatched"].append(str(column))

    report["matched"] = {str(k): v for k, v in mapping.items()}
    matched_targets = set(mapping.values())

    # الثقة = كم فهمنا من أعمدة **هذه الورقة**، لا كم من مخططنا ملأناها.
    # القسمة على المخطط الكامل تعاقب جدولاً صحيحاً مختصراً (بند · وحدة · كمية)
    # وهو أكثر ما يرد فعلاً، وتكافئ ورقة عشوائية واسعة الأعمدة.
    considered = [c for c in frame.columns if not is_price_column(c)]
    report["confidence"] = len(matched_targets) / max(1, len(considered))

    if not all(col in matched_targets for col in ESSENTIAL):
        report["reason"] = "missing_essential"
        return None, report
    if report["confidence"] < MIN_CONFIDENCE:
        report["reason"] = "low_confidence"
        return None, report

    out = pd.DataFrame()
    for source, target in mapping.items():
        out[target] = frame[source]

    for column in BOQ_COLUMNS:
        if column not in out.columns:
            out[column] = 1 if column == "الكمية" else (
                False if column == "القائمة الإلزامية" else "")

    out = out[BOQ_COLUMNS]
    out["الكمية"] = out["الكمية"].map(_clean_quantity)
    for column in BOQ_COLUMNS:
        if column not in ("الكمية", "القائمة الإلزامية"):
            out[column] = out[column].fillna("").astype(str).str.strip()
            out[column] = out[column].replace({"nan": "", "None": ""})

    # صفوف بلا اسم بند ليست بنوداً: مجاميع، وفواصل، وتذييل الورقة
    out = out[out["البند"].str.strip() != ""].reset_index(drop=True)
    # صف المجموع يحمل كلمة إجمالي ولا يقابله عمل يُنفَّذ
    totals = out["البند"].str.contains(
        "إجمالي|الاجمالي|المجموع|total|subtotal", case=False, regex=True, na=False)
    out = out[~totals].reset_index(drop=True)

    if out.empty:
        report["reason"] = "no_rows"
        return None, report

    report["rows"] = len(out)
    # ترشيح القائمة الإلزامية حكم على المحتوى لا قراءة عمود — يبقى للنموذج
    # وللمراجعة البشرية، ويبدأ False كما يبدأ في المخطط.
    return out if len(out) else DEFAULT_BOQ_DF.copy(), report


def parse_file(file) -> tuple[Optional["pd.DataFrame"], dict]:
    """
    يقرأ ملف Excel أو CSV مرفوعاً ويُخرج جدول كميات.

    يجرّب كل أوراق المصنّف ويأخذ أفضلها — ملفات الكميات كثيراً ما تحمل ورقة
    تعليمات وورقة بيانات.
    """
    name = getattr(file, "name", "")
    extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    best, best_report = None, {"reason": "unsupported", "confidence": 0.0, "rows": 0}

    try:
        if extension in ("xlsx", "xls"):
            file.seek(0)
            sheets = pd.read_excel(file, sheet_name=None, header=None)
        elif extension == "csv":
            file.seek(0)
            sheets = {"csv": pd.read_csv(file, header=None)}
        else:
            return None, best_report
    except Exception as exc:
        return None, {"reason": f"unreadable: {exc}", "confidence": 0.0, "rows": 0}

    for sheet_name, frame in (sheets or {}).items():
        parsed, report = parse_frame(frame)
        report["sheet"] = sheet_name
        if parsed is not None and report["rows"] > best_report.get("rows", 0):
            best, best_report = parsed, report
        elif best is None and report.get("confidence", 0) > best_report.get("confidence", 0):
            best_report = report

    return best, best_report
