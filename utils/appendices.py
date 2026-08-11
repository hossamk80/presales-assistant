"""
utils/appendices.py — ملاحق العرض المرقّمة (12-9)

لجنة الفحص تقرأ العرض ثم تسأل: أين السير الذاتية؟ أين شهادة الإنجاز؟ وكانت
تلك الأدلة تعيش في سجلات النظام ولا تخرج مع المستند، فتُرسل يدوياً أو تُنسى.

هنا تُحوَّل السجلات إلى **ملاحق مرقّمة** (ملحق أ · ب · ج) تُلحق بالعرض في
Word و PDF معاً، بترقيم متصل وفهرس يشملها.

**السجلات تخرج كجداول مُهيكلة لا كنسخ من الملفات الأصلية**: النظام يحفظ صفوفاً
لا مرفقات ثنائية، والملف الأصلي (شهادة ممسوحة، سيرة PDF) يبقى مسؤولية فريق
المظروف — عمود «الملف» في كل سجل يسمّيه ليُرفق يدوياً.

**لا رقم مالي في أي ملحق** — الملاحق جزء من العرض الفني.
"""
from typing import Optional

from utils import records

# ترتيب الملاحق وحروفها. الحروف عربية لأن المستند عربي في الأغلب؛ الترقيم
# يُحسب من المُدرَج فعلاً لا من القائمة، فحذف ملحق لا يترك ثغرة في التسلسل.
APPENDIX_LETTERS = ["أ", "ب", "ج", "د", "هـ", "و", "ز", "ح"]

# السجلات القابلة للإلحاق وعناوينها. الموردون مُدرَجون: خطاب التفويض دليل
# يُطلب صراحةً في كثير من الكراسات.
APPENDIX_REGISTRIES = ("people", "references", "certificates", "vendors")

_TITLES = {
    "people": "السير الذاتية للكوادر الرئيسية",
    "references": "سابقة الأعمال والمشاريع المماثلة",
    "certificates": "الشهادات والتصنيفات",
    "vendors": "خطابات التفويض والدعم المحلي",
}

# أعمدة تُستبعد من الملحق المصدَّر: تخدم الفريق داخلياً ولا تُعرض للجهة.
_INTERNAL_COLUMNS = {
    "people": {"availability"},
    "references": {"contact"},
    "certificates": set(),
    "vendors": {"alternative"},
}


def _display_value(col: dict, value) -> str:
    if col["kind"] == records.BOOL:
        return "نعم" if value else "لا"
    text = str(value or "").strip()
    return text if text and text != "0" else "—"


def build_appendix(registry: str, rows: list, letter: str,
                   labels: Optional[dict] = None) -> Optional[dict]:
    """
    يبني ملحقاً واحداً: عنوان + ترويسة أعمدة + صفوف.

    يُرجع None إن لا صفوف — ملحق فارغ في عرض يوحي بدليل غير موجود.
    """
    rows = [r for r in rows or [] if any(str(v).strip() for v in r.values())]
    if not rows:
        return None

    labels = labels or {}
    columns = [c for c in records.columns_of(registry)
               if c["key"] not in _INTERNAL_COLUMNS.get(registry, set())]

    return {
        "registry": registry,
        "letter": letter,
        "title": f"ملحق ({letter}) — {_TITLES.get(registry, registry)}",
        "headers": [labels.get(c["label_key"], c["key"]) for c in columns],
        "rows": [[_display_value(c, row.get(c["key"])) for c in columns]
                 for row in rows],
    }


def build_all(loader, labels: Optional[dict] = None,
              selected: Optional[list] = None) -> list:
    """
    كل الملاحق المطلوبة بترقيم متصل.

    Args:
        loader: دالة تُرجع صفوف سجل باسمه (تُمرَّر `db.list_records`).
        selected: أسماء السجلات المطلوبة، أو None لكلها.

    الترقيم يُسند بعد التأكد من وجود صفوف، فلا يُهدر حرف على سجل فارغ.
    """
    wanted = [r for r in APPENDIX_REGISTRIES
              if selected is None or r in selected]
    out = []
    for registry in wanted:
        letter = APPENDIX_LETTERS[len(out)] if len(out) < len(APPENDIX_LETTERS) \
            else str(len(out) + 1)
        appendix = build_appendix(registry, loader(registry), letter, labels)
        if appendix:
            out.append(appendix)
    return out


def available(loader) -> list:
    """السجلات التي فيها صفوف — لعرض خيارات الإلحاق في الواجهة."""
    return [r for r in APPENDIX_REGISTRIES if loader(r)]
