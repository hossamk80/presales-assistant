"""
utils/history.py — ذاكرة العطاءات.

النظام كان ينسى: كل منافسة تبدأ من الصفر ولو كانت نسخة من عطاء العام الماضي.
هذه الوحدة تسجّل نتيجة كل منافسة وتستدعي المشابه منها عند بدء عطاء جديد.

**هذا ليس ذكاءً سوقياً.** لا نملك أسعار المنافسين ولا نتائجهم ولن نختلقها؛
ما نملكه تاريخك أنت — وهو بيان حقيقي كان مهدوراً.
"""
import re
from typing import Optional

# نتائج المنافسة. "" تعني لم تُسجَّل بعد — لا "قيد التقييم"، فالفرق بينهما
# أن الثانية حالة معلومة والأولى غياب معلومة.
OUTCOME_UNSET = ""
OUTCOME_WON = "فاز"
OUTCOME_LOST = "خسر"
OUTCOME_NOT_SUBMITTED = "لم يُقدَّم"
OUTCOME_PENDING = "قيد التقييم"
OUTCOME_OPTIONS = [
    OUTCOME_UNSET, OUTCOME_PENDING, OUTCOME_WON, OUTCOME_LOST,
    OUTCOME_NOT_SUBMITTED,
]

# كلمات لا تميّز منافسة عن أخرى، فتطابقها يُنتج تشابهاً وهمياً.
_STOPWORDS = {
    "منافسة", "مشروع", "توريد", "تنفيذ", "أعمال", "عقد", "تشغيل", "صيانة",
    "خدمات", "شراء", "في", "من", "على", "الى", "إلى", "عن", "مع", "لدى",
    "the", "and", "for", "of", "project", "tender", "supply", "services",
}

# الحد الأدنى لعدّ منافستين متشابهتين: كلمتان دالّتان مشتركتان.
_MIN_SHARED_TOKENS = 2


def _tokens(text: str) -> set:
    """كلمات دالّة من عنوان منافسة."""
    words = re.split(r"[^\w]+", str(text or ""), flags=re.UNICODE)
    return {
        w.strip("ًٌٍَُِّْ")
        for w in words
        if len(w) > 2 and w.lower() not in _STOPWORDS
    }


def _normalise_entity(name: str) -> str:
    """
    توحيد اسم الجهة: "وزارة الصحة" و"وزاره الصحة " نفس الجهة.

    بدون هذا تُعدّ الجهة الواحدة جهتين فتضيع أهم إشارة في الذاكرة.
    """
    text = str(name or "").strip().lower()
    text = re.sub(r"[ًٌٍَُِّْ]", "", text)
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = text.replace("ة", "ه").replace("ى", "ي")
    return re.sub(r"\s+", " ", text)


# ملف الجهة (12-7) يطابق بالتوحيد نفسه، وإلا بقي غير مستدعىً لأن الاسم كُتب
# بصيغة أخرى. اسم عام لأنه صار مستعملاً خارج هذه الوحدة.
normalize_entity = _normalise_entity


def similar_projects(projects: list, name: str, entity: str = "",
                     exclude_id: Optional[int] = None, limit: int = 5) -> list:
    """
    المنافسات السابقة المشابهة، الأقوى تشابهاً أولاً.

    الجهة نفسها إشارة أقوى من تشابه العنوان: سلوك الجهة في التقييم يتكرّر.
    """
    target_entity = _normalise_entity(entity)
    target_tokens = _tokens(name)

    scored = []
    for project in projects or []:
        if exclude_id is not None and project.get("id") == exclude_id:
            continue

        same_entity = bool(target_entity) and \
            _normalise_entity(project.get("entity")) == target_entity
        shared = target_tokens & _tokens(project.get("name"))

        if not same_entity and len(shared) < _MIN_SHARED_TOKENS:
            continue

        scored.append(({
            **project,
            "same_entity": same_entity,
            "shared_terms": sorted(shared),
        }, (1 if same_entity else 0, len(shared))))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [item for item, _ in scored[:limit]]


def outcome_stats(projects: list) -> dict:
    """عدّاد النتائج المسجّلة عبر كل المنافسات."""
    stats = {"won": 0, "lost": 0, "not_submitted": 0, "pending": 0, "unset": 0}
    key_of = {
        OUTCOME_WON: "won",
        OUTCOME_LOST: "lost",
        OUTCOME_NOT_SUBMITTED: "not_submitted",
        OUTCOME_PENDING: "pending",
    }
    for project in projects or []:
        stats[key_of.get(str(project.get("outcome", "")).strip(), "unset")] += 1
    return stats


def lessons_block(similar: list) -> str:
    """
    دروس المنافسات المشابهة كمقطع سياق.

    تُدرَج المنافسات ذات النتيجة المسجّلة فقط: منافسة بلا نتيجة لا درس فيها،
    وحشوها يوهم النموذج بسابقة لا توجد.
    """
    lines = []
    for project in similar or []:
        outcome = str(project.get("outcome", "")).strip()
        if outcome in (OUTCOME_UNSET, OUTCOME_PENDING):
            continue
        note = str(project.get("outcome_note", "")).strip()
        entity = str(project.get("entity", "")).strip()
        head = f"- {project.get('name', '')}"
        if entity:
            head += f" ({entity})"
        head += f" — {outcome}"
        lines.append(f"{head}: {note}" if note else head)

    if not lines:
        return ""
    return (
        "\n\n--- منافسات سابقة مشابهة ونتائجها ---\n"
        + "\n".join(lines)
        + "\nاستفد من هذه السوابق في تقدير المخاطر، ولا تعامل نتيجة سابقة "
          "كضمان لنتيجة هذه المنافسة."
    )
