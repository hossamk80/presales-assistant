"""
utils/submission.py — جاهزية مظروف التسليم.

أكثر أسباب الاستبعاد شيوعاً ليست ضعف العرض الفني بل مستند ناقص أو شهادة
منتهية. المنطق هنا خالٍ من Streamlit ليُحسب مرة واحدة ويُقرأ في شاشة الجداول
وفي بوابة التصدير معاً.
"""
import datetime
import re
from typing import Optional

import pandas as pd

# صيغ التواريخ الشائعة في إدخال المستخدم، بالترتيب.
_DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y")


def parse_date(value) -> Optional[datetime.date]:
    """
    يقرأ تاريخاً مكتوباً بأي من الصيغ الشائعة، ويُرجع None إن تعذّر.

    التاريخ غير المقروء لا يُفترض صالحاً ولا منتهياً — يُترك بلا حكم.
    """
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value

    text = str(value or "").strip()
    if not text:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def deadline_date(project_context: Optional[dict]) -> Optional[datetime.date]:
    """الموعد النهائي من السياق الموحّد، إن أمكن قراءته."""
    raw = str((project_context or {}).get("submission_deadline", "")).strip()
    direct = parse_date(raw)
    if direct:
        return direct
    # الموعد قد يأتي داخل جملة ("آخر موعد 2026-09-01 الساعة 12 ظهراً")
    match = re.search(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}", raw)
    return parse_date(match.group(0)) if match else None


def _records(df: Optional[pd.DataFrame]) -> list:
    """صفوف الجدول بأسماء أعمدتها كما هي (لا itertuples — يُعيد التسمية)."""
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return []
    return df.to_dict("records")


def submission_summary(df: Optional[pd.DataFrame],
                       project_context: Optional[dict] = None) -> dict:
    """
    جاهزية المظروف: كم مستنداً إلزامياً، وكم منها جاهز، وما المعطِّل.

    "بانتظار التحقق" ليس جاهزاً: لم نتأكد بعد لا تساوي موجود.
    """
    summary = {"total": 0, "mandatory": 0, "ready": 0,
               "missing": [], "expiring": []}
    deadline = deadline_date(project_context)

    for data in _records(df):
        name = str(data.get("المستند", "")).strip()
        if not name:
            continue

        summary["total"] += 1
        mandatory = bool(data.get("إلزامي", False))
        have = str(data.get("لدينا", "")).strip()
        attached = bool(data.get("مرفق في المظروف", False))

        if mandatory:
            summary["mandatory"] += 1
            if have == "نعم" and attached:
                summary["ready"] += 1
            elif have != "لا ينطبق":
                summary["missing"].append(name)

        # شهادة تنتهي قبل الموعد النهائي = مستند غير مقبول يوم الفتح، حتى لو
        # كان بين يديك اليوم.
        expiry = parse_date(data.get("تاريخ الانتهاء"))
        if expiry and deadline and expiry < deadline:
            summary["expiring"].append(f"{name} — تنتهي {expiry.isoformat()}")

    return summary


def documents_to_df(items: list) -> pd.DataFrame:
    """تحويل المستندات المستخرجة إلى جدول قابل للتحرير."""
    from utils.state import DEFAULT_SUBMISSION_DF, SUBMISSION_COLUMNS

    rows = []
    for item in items or []:
        name = str(item.get("document", "")).strip()
        if not name:
            continue
        rows.append({
            "المستند": name,
            "مرجع البند": str(item.get("clause_reference", "")).strip(),
            "إلزامي": bool(item.get("mandatory", False)),
            # الحيازة والإرفاق قراران بشريان — الاستخراج يقرأ الكراسة لا خزانتك.
            "لدينا": "بانتظار التحقق",
            "تاريخ الانتهاء": "",
            "مرفق في المظروف": False,
            "ملاحظات": str(item.get("notes", "")).strip(),
        })
    return pd.DataFrame(rows)[SUBMISSION_COLUMNS] if rows \
        else DEFAULT_SUBMISSION_DF.copy()
