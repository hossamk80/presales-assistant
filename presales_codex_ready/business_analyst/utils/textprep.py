"""
utils/textprep.py — تنظيف نص الكراسة قبل إرساله إلى النموذج.

كراسة اعتماد النموذجية مئات الصفحات، وجزء معتبر منها **ليس معلومة**: ترويسة
تتكرّر في كل صفحة، وتذييل، وأرقام صفحات، وفهرس بنقاط ممتدة، ومسافات فارغة
متراكمة من استخراج الـ PDF. كل ذلك يُرسَل اليوم إلى النموذج ويُدفع ثمنه توكناً
في كل استدعاء — وهو لا يضيف شيئاً إلى فهم المتطلبات.

**القاعدة الحاكمة هنا: لا نحذف إلا ما نُثبت أنه مكرّر أو زخرفة.** بند واحد
يسقط في التنظيف يعني متطلباً لا يراه النموذج فلا يظهر في المصفوفة فلا يُغطّى
في العرض — وهو بالضبط نوع الخطأ الذي بُني هذا النظام ليمنعه. لذلك:

  · لا نحذف سطراً إلا إذا تكرّر حرفياً بما يكفي ليكون ترويسة أو تذييلاً.
  · لا نحذف رقماً إلا إذا كان السطر رقم صفحة وحده.
  · وإن تجاوز الحذف السقف الآمن، نُعيد النص الأصلي كما هو ونُبلّغ بذلك.

الوحدة خالية من Streamlit ليُختبر منطقها وحده.
"""
import hashlib
import re
from collections import Counter
from typing import Optional

# أقصى نسبة يُسمح للتنظيف بحذفها. تجاوزها يعني أن الكشف أخطأ — كراسة مُنسّقة
# تنسيقاً غريباً قد تبدو كلها «تكراراً» — فنتراجع إلى الأصل بدل المخاطرة.
MAX_REMOVAL_RATIO = 0.45

# أقل عدد تكرارات لعدّ السطر ترويسةً أو تذييلاً لا محتوى.
MIN_REPEATS = 4

# السطر الطويل قد يتكرّر لأنه بند متكرّر فعلاً (شرط يتكرّر في ملاحق)، فلا
# نحذف إلا القصير — الترويسات والتذييلات قصيرة بطبعها.
MAX_FURNITURE_CHARS = 90

# رقم صفحة وحده، أو "صفحة 3 من 120"، أو "Page 3 of 120"
_PAGE_LINE_RE = re.compile(
    r"^\s*(?:"
    r"[-–—\[\(]?\s*\d{1,4}\s*[-–—\]\)]?"
    r"|صفحة\s*\d+\s*(?:من|/)\s*\d+"
    r"|ص\s*[/.:]?\s*\d+"
    r"|page\s*\d+\s*(?:of|/)\s*\d+"
    r")\s*$",
    re.IGNORECASE,
)

# سطر فهرس بنقاط ممتدة: "المقدمة .................. 4"
_TOC_LEADER_RE = re.compile(r"^\s*.{0,80}?[.·ـ_]{4,}\s*\d{1,4}\s*$")

# أحرف تحكّم وعلامات اتجاه لا تحمل معنى وتُستهلك توكناً
_INVISIBLE_RE = re.compile(r"[​-‏‪-‮⁦-⁩﻿\xad]")

# فواصل زخرفية: خطوط من الشرطات أو النجوم أو المساواة
_RULE_RE = re.compile(r"^\s*[-=_*·—–~+#.]{3,}\s*$")

# سطر يحمل رقم بند أو عنوان مادة **محتوى بالتعريف**، مهما تكرّر.
#
# الترويسات والتذييلات لا تحمل أرقام بنود. وبدون هذا الاستثناء يُحذف شرط قصير
# تكرّر في عدة صفحات — وهو بالضبط الخطأ الذي لا يُغتفر هنا: متطلب لا يراه
# النموذج لا يظهر في المصفوفة ولا يُغطّى في العرض.
_CLAUSE_LINE_RE = re.compile(
    r"^\s*(?:"
    r"\d+(?:[.\-/]\d+){1,3}\s"                       # 5-2 · 7.3.1
    r"|(?:المادة|البند|الفصل|الملحق|المرفق)\s"
    r"|(?:أولاً|ثانياً|ثالثاً|رابعاً|خامساً|سادساً|سابعاً|ثامناً|تاسعاً|عاشراً)\s*[:.\-]"
    r"|(?:clause|article|section|item)\s+\d"
    r")",
    re.IGNORECASE,
)


def is_clause_line(line: str) -> bool:
    """هل يحمل السطر رقم بند أو عنوان مادة؟ إن كان، فهو محتوى لا زخرفة."""
    return bool(_CLAUSE_LINE_RE.match(str(line or "").strip()))


def _normalize_line(line: str) -> str:
    """صيغة مُوحّدة للمقارنة فقط — لا تُكتب في المخرَج."""
    text = _INVISIBLE_RE.sub("", line)
    text = re.sub(r"\d+", "#", text)          # رقم الصفحة يتغيّر والترويسة لا
    return re.sub(r"\s+", " ", text).strip().lower()


def find_repeated_lines(text: str, min_repeats: int = MIN_REPEATS) -> set:
    """
    الأسطر التي تتكرّر بما يكفي لتكون ترويسة أو تذييلاً.

    نُوحّد الأرقام قبل العدّ لأن «صفحة 3» و«صفحة 4» ترويسة واحدة.
    """
    counts = Counter()
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if not stripped or len(stripped) > MAX_FURNITURE_CHARS:
            continue
        if is_clause_line(stripped):
            continue
        counts[_normalize_line(stripped)] += 1
    return {key for key, n in counts.items() if n >= min_repeats and key}


def _exact_key(text: str) -> str:
    """
    بصمة محتوى تُهمل المسافات وحدها و**تحتفظ بالأرقام**.

    `_normalize_line` تستبدل الأرقام بـ `#` وهو صحيح لكشف الترويسات (رقم
    الصفحة يتغيّر والترويسة لا)، وكارثة لكشف الفقرات المكرّرة: بندان لا
    يختلفان إلا في رقمهما — «5-1 يوفّر المورد…» و«5-2 يوفّر المورد…» — يصيران
    بصمة واحدة فيُحذف أحدهما، وهو متطلب كامل.
    """
    normalized = re.sub(r"\s+", " ", _INVISIBLE_RE.sub("", str(text or ""))).strip()
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def _block_key(block: str) -> str:
    return _exact_key(block)


def clean(text: str, min_repeats: int = MIN_REPEATS) -> tuple[str, dict]:
    """
    ينظّف نص كراسة ويُرجع (النص المنظَّف، إحصاءات).

    الإحصاءات: عدد الأحرف قبل وبعد، وما حُذف مصنَّفاً، ونسبة التوفير، وهل
    تراجعنا إلى الأصل.
    """
    raw = str(text or "")
    stats = {
        "before": len(raw), "after": len(raw), "saved": 0, "ratio": 0.0,
        "repeated_lines": 0, "page_lines": 0, "toc_lines": 0,
        "rules": 0, "blank": 0, "duplicate_blocks": 0, "reverted": False,
    }
    if not raw.strip():
        return raw, stats

    furniture = find_repeated_lines(raw, min_repeats)
    kept: list[str] = []
    blank_run = 0

    for line in raw.splitlines():
        stripped = _INVISIBLE_RE.sub("", line).rstrip()
        bare = stripped.strip()

        if not bare:
            blank_run += 1
            # سطر فارغ واحد يفصل الفقرات؛ ما زاد زخرفة
            if blank_run <= 1:
                kept.append("")
            else:
                stats["blank"] += 1
            continue
        blank_run = 0

        if _PAGE_LINE_RE.match(bare):
            stats["page_lines"] += 1
            continue
        if _TOC_LEADER_RE.match(bare):
            stats["toc_lines"] += 1
            continue
        if _RULE_RE.match(bare):
            stats["rules"] += 1
            continue
        if (len(bare) <= MAX_FURNITURE_CHARS
                and not is_clause_line(bare)
                and _normalize_line(bare) in furniture):
            stats["repeated_lines"] += 1
            continue

        kept.append(re.sub(r"[ \t]{2,}", " ", stripped))

    cleaned = "\n".join(kept)
    cleaned, duplicates = _drop_duplicate_blocks(cleaned)
    stats["duplicate_blocks"] = duplicates
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    stats["after"] = len(cleaned)
    stats["saved"] = max(0, stats["before"] - stats["after"])
    stats["ratio"] = stats["saved"] / stats["before"] if stats["before"] else 0.0

    # سقف أمان: حذف مفرط يعني أن الكشف أخطأ، والخسارة هنا متطلب لا يراه النموذج
    if stats["ratio"] > MAX_REMOVAL_RATIO:
        return raw, {**stats, "after": len(raw), "saved": 0, "ratio": 0.0,
                     "reverted": True}

    return cleaned, stats


def _drop_duplicate_blocks(text: str, min_chars: int = 200) -> tuple[str, int]:
    """
    يحذف الفقرات المتطابقة المتكرّرة — ملحق يُعاد إدراجه كاملاً مثلاً.

    الفقرات القصيرة مستثناة: «نعم» و«لا ينطبق» تتكرّر مشروعةً في الجداول.
    """
    seen, out, dropped = set(), [], 0
    for block in text.split("\n\n"):
        if len(block.strip()) < min_chars:
            out.append(block)
            continue
        key = _block_key(block)
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        out.append(block)
    return "\n\n".join(out), dropped


def dedupe_attachments(texts: Optional[dict]) -> tuple[dict, list]:
    """
    يُسقط المرفقات المكرّرة حرفياً.

    رفع نفس الملحق مرتين باسمين مختلفين يضاعف كلفة كل استدعاء بلا معلومة
    واحدة إضافية. يُرجع (المرفقات بلا تكرار، أسماء ما أُسقط).
    """
    seen, kept, dropped = {}, {}, []
    for name, body in (texts or {}).items():
        key = _exact_key(body)
        if key in seen and str(body or "").strip():
            dropped.append(f"{name} = {seen[key]}")
            continue
        seen[key] = name
        kept[name] = body
    return kept, dropped
