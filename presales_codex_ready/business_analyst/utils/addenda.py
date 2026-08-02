"""
utils/addenda.py — الملاحق والتعديلات على الكراسة.

الجهات تُصدر تعديلات وإجابات استفسارات **بعد** نشر الكراسة، فتتغيّر المتطلبات
تحت عرض يُكتب بالفعل. كان النظام يعامل الكراسة وثيقة واحدة ثابتة: تُرفع نسخة
جديدة فتُمحى القديمة بلا أثر، ولا أحد يعرف ما الذي تغيّر ولا أي صف في مصفوفة
الامتثال صار على شرط ملغى.

هذه الوحدة تحفظ نسخة عند كل رفعة، وتقارن نسختين، وتحدّد المتطلبات المتأثرة.
خالية من Streamlit ليُختبر منطقها وحده.
"""
import difflib
import re
from typing import Optional

import pandas as pd

# أقل عدد كلمات دالّة مشتركة لعدّ متطلب متأثراً بنص تغيّر.
_MIN_SHARED_TOKENS = 3

# كلمات لا تميّز متطلباً عن آخر، فتطابقها يُنتج تأثراً وهمياً يُغرق المستخدم.
_STOPWORDS = {
    "يجب", "على", "المورد", "المتعهد", "الشركة", "الجهة", "يكون", "تكون",
    "جميع", "كافة", "وفق", "حسب", "التي", "الذي", "ذلك", "هذه", "هذا",
    "مع", "من", "الى", "إلى", "في", "عن", "أن", "ان", "كل", "بما",
    "shall", "must", "the", "and", "for", "with", "all", "any", "this",
}

_SNIPPET_CHARS = 120


def _tokens(text: str) -> set:
    words = re.split(r"[^\w]+", str(text or ""), flags=re.UNICODE)
    return {
        w.strip("ًٌٍَُِّْ").lower()
        for w in words
        if len(w) > 3 and w.lower() not in _STOPWORDS
    }


def _lines(text: str) -> list:
    return [ln.strip() for ln in str(text or "").splitlines() if ln.strip()]


def diff_versions(old_texts: Optional[dict], new_texts: Optional[dict]) -> dict:
    """
    يقارن رفعتَي مرفقات.

    Returns:
        {
          "added":   [أسماء ملفات جديدة],
          "removed": [أسماء ملفات اختفت],
          "changed": [{"name", "added_lines", "removed_lines"}],
          "new_text": نص كل ما أُضيف — مادة تحديد المتطلبات المتأثرة,
        }
    """
    old = {k: str(v or "") for k, v in (old_texts or {}).items()}
    new = {k: str(v or "") for k, v in (new_texts or {}).items()}

    result = {
        "added": sorted(set(new) - set(old)),
        "removed": sorted(set(old) - set(new)),
        "changed": [],
        "new_text": "",
    }

    fresh = [new[name] for name in result["added"]]

    for name in sorted(set(old) & set(new)):
        if old[name] == new[name]:
            continue
        before, after = _lines(old[name]), _lines(new[name])
        matcher = difflib.SequenceMatcher(a=before, b=after, autojunk=False)
        added_lines, removed_lines = [], []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag in ("replace", "insert"):
                added_lines.extend(after[j1:j2])
            if tag in ("replace", "delete"):
                removed_lines.extend(before[i1:i2])
        if added_lines or removed_lines:
            result["changed"].append({
                "name": name,
                "added_lines": added_lines,
                "removed_lines": removed_lines,
            })
            fresh.extend(added_lines)

    result["new_text"] = "\n".join(fresh)
    return result


def has_changes(diff: dict) -> bool:
    return bool(diff.get("added") or diff.get("removed") or diff.get("changed"))


def summarize(diff: dict) -> dict:
    """أرقام مختصرة للعرض: كم ملفاً أُضيف وحُذف وتغيّر، وكم سطراً."""
    changed = diff.get("changed") or []
    return {
        "added_files": len(diff.get("added") or []),
        "removed_files": len(diff.get("removed") or []),
        "changed_files": len(changed),
        "added_lines": sum(len(c["added_lines"]) for c in changed),
        "removed_lines": sum(len(c["removed_lines"]) for c in changed),
    }


def affected_requirements(df: Optional[pd.DataFrame], diff: dict) -> list:
    """
    المتطلبات التي يُرجَّح أن التعديل مسّها.

    إشارتان: **مرجع البند** يرد حرفياً في النص الجديد (أقوى دليل)، أو تقاطع
    ثلاث كلمات دالّة على الأقل مع سطر تغيّر.

    التحديد ترجيح لا يقين — لذلك نتيجته تُعيد الصف إلى «غير مفحوص» ولا تحكم
    عليه بشيء. الحكم بعد إعادة الفحص.
    """
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return []

    new_text = str(diff.get("new_text") or "")
    if not new_text.strip():
        return []

    new_lines = _lines(new_text)
    line_tokens = [_tokens(ln) for ln in new_lines]
    haystack = new_text

    affected = []
    for position, data in enumerate(df.to_dict("records")):
        req_id = str(data.get("المعرّف", "")).strip()
        summary = str(data.get("المتطلب", "")).strip()
        clause = str(data.get("مرجع البند", "")).strip()
        if not summary and not req_id:
            continue

        reason = ""
        if clause and clause in haystack:
            reason = f"مرجع البند {clause} ورد في النص الجديد"
        else:
            wanted = _tokens(summary)
            if wanted:
                for line, tokens in zip(new_lines, line_tokens):
                    if len(wanted & tokens) >= _MIN_SHARED_TOKENS:
                        reason = f"تشابه مع سطر تغيّر: {line[:_SNIPPET_CHARS]}"
                        break

        if reason:
            affected.append({
                "position": position,
                "req_id": req_id or f"صف {position + 1}",
                "requirement": summary,
                "reason": reason,
            })
    return affected


def mark_unchecked(df: Optional[pd.DataFrame], affected: list) -> Optional[pd.DataFrame]:
    """
    يُعيد المتطلبات المتأثرة إلى «غير مفحوص».

    تعديل على الكراسة يُبطل تغطية سابقة: ما ثبت أنه مغطّى كان مغطّى للنص
    القديم. وإعادتها «غير مفحوص» تُعيد تفعيل بوابة التصدير على المتطلبات
    الحرجة تلقائياً — فلا يُسلَّم عرض مبنيّ على شرط ملغى.
    """
    from utils.state import COVERAGE_UNCHECKED

    if df is None or not isinstance(df, pd.DataFrame) or df.empty or not affected:
        return df

    out = df.copy()
    if "التغطية" not in out.columns:
        return out
    for item in affected:
        position = item.get("position")
        if position is not None and 0 <= position < len(out):
            out.iloc[position, out.columns.get_loc("التغطية")] = COVERAGE_UNCHECKED
            if "القسم المغطّي" in out.columns:
                out.iloc[position, out.columns.get_loc("القسم المغطّي")] = ""
    return out
