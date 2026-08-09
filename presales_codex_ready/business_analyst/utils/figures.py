"""
utils/figures.py — مخططات العرض وصوره (ب-5).

العرض الفني بلا مخطط معماري يخسر درجات في «وضوح الحل»: لجنة الفحص تقرأ خمسين
صفحة نصّاً لتفهم بنيةً يوضّحها شكل واحد.

**الصورة يرفعها المستخدم ولا يولّدها النموذج.** النموذج لا يعرف معمارية الحلّ
الفعلية، ومخططٌ مولَّد **ادّعاءٌ عن الحلّ** لا توضيحٌ له — وهو ما تمنعه القاعدة
الثالثة من القواعد الثابتة (14-2): لا اختراع لما لا دليل عليه.

الوحدة خالية من Streamlit ومن قاعدة البيانات: تأخذ صفوفاً وتعيد أحكاماً وترقيماً.

**ثلاث قواعد:**

1. **الملف يُفحَص عند الرفع لا عند التصدير.** صورة تالفة تُقبل صامتةً ثم تُسقط
   بناء المستند كلّه في يوم التسليم — والخطأ يظهر بعيداً عن سببه.
2. **رقم الشكل يُحسب وقت البناء ولا يُخزَّن.** حذف شكل أو نقل قسم يُعيد الترقيم
   بلا ثغرة — نفس مبدأ ترقيم الملاحق (12-9).
3. **الترتيب ترتيب المستند** لا ترتيب الرفع: القارئ يرى «شكل ٢» بعد «شكل ١».
"""
import re
from typing import Optional

# الصيغ المقبولة وتواقيعها. الفحص **بالتوقيع لا بالامتداد**: ملفٌّ سُمّي
# `.png` وهو شيء آخر يمرّ من فحص الامتداد ويُسقط بناء المستند.
_SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
    (b"GIF87a", "image/gif", "gif"),
    (b"GIF89a", "image/gif", "gif"),
)

# أقصى حجم لصورة واحدة. مخطط معماري بـ PNG لا يقارب هذا الحدّ؛ ما يتجاوزه صورة
# فوتوغرافية خام تُضخّم المستند بلا أن تزيد وضوحاً.
MAX_BYTES = 5 * 1024 * 1024

# عرض الشكل في المستند بالسنتيمترات — يملأ عرض النصّ بلا تجاوز الهوامش.
FIGURE_WIDTH_CM = 15.0

# بادئة التسمية في المستند.
_LABEL_AR = "شكل"
_LABEL_EN = "Figure"


def detect_image(data: bytes) -> Optional[str]:
    """
    نوع الصورة من توقيعها، أو `None` إن لم تكن صورة معروفة.

    التوقيع لا الامتداد: ملفٌّ سُمّي `.png` وهو مستند Word يمرّ من فحص الاسم
    ثم يُسقط `python-docx` عند البناء — بعيداً عن سببه بأيام.
    """
    if not data:
        return None
    for signature, mime, _ext in _SIGNATURES:
        if data.startswith(signature):
            return mime
    return None


def problem(data: bytes) -> Optional[str]:
    """
    مفتاح i18n لأول عيب في الملف المرفوع، أو `None` إن كان مقبولاً.

    يُفحص **عند الرفع**: صورة تالفة تُقبل صامتةً ثم تُسقط بناء المستند كلّه في
    يوم التسليم.
    """
    if not data:
        return "fig.err_empty"
    if len(data) > MAX_BYTES:
        return "fig.err_too_big"
    if detect_image(data) is None:
        return "fig.err_not_image"
    return None


def _section_order(sections: Optional[list]) -> dict:
    """مفتاح القسم ← ترتيبه في المستند. الأقسام غير المُدرَجة تُسقَط."""
    order = {}
    position = 0
    for section in sections or []:
        if not section.get("include", True):
            continue
        key = str(section.get("key", "") or "")
        if key:
            order[key] = position
            position += 1
    return order


def numbered(figures: Optional[list], sections: Optional[list] = None,
             rtl: bool = True) -> list:
    """
    الأشكال مرتّبةً **بترتيب المستند** ومرقّمةً تسلسلياً.

    Returns:
        `[{... , "number": 1, "label": "شكل 1"}]`

    شكلٌ في قسم **غير مُدرَج** يُسقَط: القسم لا يخرج في المستند، فشكله لا مكان
    له — وإدراجه يُنتج «شكل ٣» بلا شكل ٣ في النصّ.
    """
    order = _section_order(sections) if sections is not None else None
    items = []
    for figure in figures or []:
        key = str(figure.get("section_key", "") or "")
        if order is not None:
            if key not in order:
                continue
            position = order[key]
        else:
            position = 0
        items.append((position, int(figure.get("ordinal") or 0),
                      int(figure.get("id") or 0), figure))

    items.sort(key=lambda row: row[:3])
    label = _LABEL_AR if rtl else _LABEL_EN
    return [
        {**figure, "number": index, "label": f"{label} {index}"}
        for index, (_p, _o, _i, figure) in enumerate(items, start=1)
    ]


def for_section(numbered_figures: Optional[list], section_key: str) -> list:
    """أشكال قسم بعينه من القائمة المرقّمة — يستعملها بنّاء المستند."""
    key = str(section_key or "")
    return [f for f in numbered_figures or []
            if str(f.get("section_key", "") or "") == key]


def caption_text(figure: dict) -> str:
    """سطر التسمية أسفل الشكل: «شكل 1: معمارية الحل»."""
    caption = " ".join(str(figure.get("caption", "") or "").split())
    label = str(figure.get("label", "") or "")
    return f"{label}: {caption}" if caption else label


def missing_captions(numbered_figures: Optional[list]) -> list:
    """
    الأشكال بلا تسمية.

    شكلٌ بلا تسمية يُجبر القارئ على استنتاج ما يراه، ولجنة الفحص لا تستنتج —
    تُنبَّه ولا تُمنع: القرار للمستخدم، وقد يكون الشكل مفهوماً بذاته.
    """
    return [f for f in numbered_figures or [] if not str(f.get("caption", "")).strip()]


def referenced_in(text: str, figure: dict) -> bool:
    """
    هل يشير نصّ القسم إلى هذا الشكل («انظر شكل 2»)؟

    شكلٌ لا يشير إليه النصّ يبدو حشواً؛ والإشارة إليه تربطه بالحجّة. تنبيهٌ
    للمستخدم لا شرط — بعض الأشكال تُقرأ بموضعها.
    """
    number = figure.get("number")
    if not number:
        return False
    pattern = rf"({_LABEL_AR}|{_LABEL_EN})\s*[:\-]?\s*0*{int(number)}\b"
    return bool(re.search(pattern, str(text or ""), re.IGNORECASE))
