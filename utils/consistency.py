"""
utils/consistency.py — اتساق الأرقام بين أقسام العرض.

قسمان مكتوبان بإتقان قد يتناقضان: المنهجية تعد بالتنفيذ في اثني عشر شهراً
والجدول الزمني يمتد ثمانية عشر. مُقيّم الجهة يرصد التناقض قبل أن يرصده فريق
العطاء، ويقرأه إمّا إهمالاً أو محاولة تجميل.

الفحص **حسابي لا نموذجي**: لا استدعاء ولا توكن، ونتيجته قابلة للتفسير سطراً
سطراً. الوحدة خالية من Streamlit لتُستدعى من المراجعة ومن بوابة التصدير معاً.
"""
import re
from typing import Optional

import pandas as pd

from utils import traceability
from utils.timeline import parse_duration_weeks, contract_weeks

# نُقارن مدة **التنفيذ** وحدها. مدة الضمان ومدة سريان العرض أرقام مشروعة
# تختلف عنها، ومقارنتها بها تُنتج تحذيرات كاذبة تُفقد الفحص مصداقيته.
_EXECUTION_CUES = (
    "مدة التنفيذ", "مدة المشروع", "مدة العقد", "فترة التنفيذ", "زمن التنفيذ",
    "مدة تنفيذ", "خطة التنفيذ خلال", "ينفَّذ خلال", "تنفيذ المشروع خلال",
    "execution period", "project duration", "delivery period",
)

# نافذة البحث عن الرقم بعد العبارة الدالّة
_WINDOW = 60

_DURATION_RE = re.compile(
    r"(\d+(?:[.,]\d+)?|[٠-٩]+|[؀-ۿ]{3,12})\s*"
    r"(أسبوع\w*|اسبوع\w*|أسابيع|اسابيع|شهر\w*|أشهر|اشهر|شهور|"
    r"سنة|سنوات|سنه|عام\w*|أعوام|يوم\w*|أيام|ايام|weeks?|months?|years?|days?)"
)

# فرق أقل من هذا لا يُعدّ تناقضاً: «ثلاثة أشهر» و«12 أسبوعاً» نفس المدة
# مكتوبة بوحدتين، والتقريب بينهما أسبوع.
_TOLERANCE_WEEKS = 1


def execution_durations(text: str) -> list:
    """
    المدد المذكورة في **سياق تنفيذي** داخل نص، بالأسابيع.

    الرقم يُلتقط فقط إن جاء بعد عبارة تدلّ على مدة التنفيذ، فلا تختلط بمدة
    الضمان ولا بسريان العرض.
    """
    body = str(text or "")
    if not body:
        return []

    found = []
    lowered = body.lower()
    for cue in _EXECUTION_CUES:
        start = 0
        while True:
            at = lowered.find(cue.lower(), start)
            if at < 0:
                break
            window = body[at:at + len(cue) + _WINDOW]
            match = _DURATION_RE.search(window)
            if match:
                weeks = parse_duration_weeks(match.group(0))
                if weeks:
                    found.append({"weeks": weeks, "text": match.group(0).strip()})
            start = at + len(cue)
    return found


# ─── تطابق النسختين في وضع «كليهما» (ب-3) ─────────────────────────────────────
#
# وضع «كليهما» يُخرج القسم مرتين: بالعربية ثم بالإنجليزية. والمظروف الواحد يحمل
# النسختين، والمُقيّم يقرأ واحدة — فاختلافهما في **رقم** أو **التزام** مأخذٌ على
# المورّد لا خطأ مطبعي: «مدة الضمان سنتان» عربياً و«three years» إنجليزياً
# تعهّدان مختلفان في مستند واحد.
#
# **الفحص حسابي لا نموذجي** كبقية هذه الوحدة: مقارنة النسختين باستدعاء نموذج
# تكلّف توكناً في كل مراجعة وتعطي حكماً لا يُفسَّر سطراً سطراً.
#
# **وما يُقارَن هو الأرقام وحدها.** طول النصّ وعدد الجمل وصياغتها تختلف بين
# لغتين بطبيعتها — مقارنتها تُنتج تحذيرات كاذبة تُفقد الفحص مصداقيته فيُهمَل،
# ويُهمَل معه ما كان يستحقّ التوقّف.

# فاصل النسختين كما تطلبه تعليمة «كليهما» في `ai_engine.LANGUAGES`.
_ENGLISH_HEADING = re.compile(r"^\s*#{1,6}\s*English\s+Version\s*$",
                              re.IGNORECASE | re.MULTILINE)
_HR_SPLIT = re.compile(r"^\s*-{3,}\s*$", re.MULTILINE)

# الأرقام: خانات عربية-هندية تُطبَّع إلى لاتينية، والفاصلة العشرية العربية معها.
# «١٢» و «12» رقم واحد، ومقارنتهما نصّاً تجعل كل رقم في العرض مخالفاً لنظيره.
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٫٬", "0123456789.,")
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")

# أرقام لا تُقارَن: ترقيم القوائم والعناوين بنية لا محتوى، وهي متطابقة بطبيعتها
# فلا تضيف شيئاً — لكن سنة أو نسبة تُقارَن.
_LIST_MARKER_RE = re.compile(r"^\s*\d+[.)]\s", re.MULTILINE)


def split_bilingual(text: str) -> tuple:
    """
    يفصل قسماً مكتوباً بوضع «كليهما» إلى (عربي، إنجليزي).

    يُجرَّب عنوان `## English Version` أولاً لأنه المطلوب صراحةً في التعليمة،
    وإلا فالفاصل `---`. وبلا فاصل يُعاد `(النصّ، "")` — نصٌّ بلا نسخة ثانية
    حالةٌ تُبلَّغ لا تُخمَّن.
    """
    body = str(text or "")
    if not body.strip():
        return "", ""

    match = _ENGLISH_HEADING.search(body)
    if match:
        return body[:match.start()].strip(), body[match.end():].strip()

    parts = _HR_SPLIT.split(body)
    if len(parts) >= 2:
        # أول فاصل هو الحدّ؛ ما بعده كلّه النسخة الثانية ولو حوى فواصل أخرى
        return parts[0].strip(), "\n".join(parts[1:]).strip()
    return body.strip(), ""


def _numbers(text: str):
    """الأرقام في نصّ، مطبَّعةً، بلا ترقيم القوائم."""
    from collections import Counter

    body = str(text or "").translate(_ARABIC_DIGITS)
    body = _LIST_MARKER_RE.sub(" ", body)
    return Counter(_NUMBER_RE.findall(body))


def bilingual_parity(sections: Optional[list] = None,
                     language: str = "ar") -> list:
    """
    يقارن نسختَي كل قسم في وضع «كليهما». فارغة في أي وضع آخر.

    حالتان:

    · **نسخة ناقصة** ⇒ `حرجة`. المظروف يَعِد بنسختين وفيه واحدة — عيبٌ في
      المُخرَج نفسه، وبلا احتمال إنذار كاذب.
    · **أرقام مختلفة** ⇒ `تنبيه`. رقمٌ في نسخة وليس في الأخرى قد يكون فرقاً
      حقيقياً وقد يكون رقماً كُتب بالحروف في إحداهما («خمسة عشر» مقابل «15»).
      فيُعرض للمراجعة البشرية ولا يُحكَم عليه — ورفعه إلى الحرج مع هذا الاحتمال
      يُغرق اللوحة فيُهمَل ما يستحقّ التوقّف.
    """
    if str(language or "") != "both":
        return []

    findings = []
    for section in sections or []:
        title = str(section.get("title", "") or "")
        arabic, english = split_bilingual(section.get("content", ""))
        if not arabic.strip():
            continue

        if not english.strip():
            findings.append({
                "kind": "bilingual_missing",
                "severity": "حرجة",
                "message": (
                    f"«{title}» مكتوب بلغة واحدة والمخرجات مضبوطة على النسختين — "
                    "المظروف يَعِد بنسختين وفيه واحدة."
                ),
                "sections": [title],
            })
            continue

        only_ar = _numbers(arabic) - _numbers(english)
        only_en = _numbers(english) - _numbers(arabic)
        if not only_ar and not only_en:
            continue

        detail = []
        if only_ar:
            detail.append("في العربية وحدها: " + " · ".join(sorted(only_ar)))
        if only_en:
            detail.append("في الإنجليزية وحدها: " + " · ".join(sorted(only_en)))
        findings.append({
            "kind": "bilingual_numbers",
            "severity": "تنبيه",
            "message": (
                f"«{title}» — أرقام لا تتطابق بين النسختين. "
                + " · ".join(detail)
                + ". راجِعها: قد يكون رقماً كُتب بالحروف في إحداهما، وقد يكون "
                  "تعهّداً مختلفاً في مستند واحد."
            ),
            "sections": [title],
        })

    return findings


def glossary_drift(sections: Optional[list] = None,
                   language: str = "ar") -> list:
    """
    الأقسام التي كتبت مصطلحاً بصيغة مرفوضة بدل الصيغة المعتمدة (14-6).

    هذا هو **شقّ التحقّق** من توحيد المصطلح: التعليمة المحقونة في التوليد تسبق
    الكتابة، وهذه ترصد ما أفلت منها. بلا هذا الشقّ يبقى «صيغة واحدة في كل
    العرض» رجاءً موجَّهاً إلى نموذج احتمالي لا شرطاً يُتحقَّق منه.

    الملاحظة **تنبيه لا حرجة**: صيغة مرادفة لا تُخرج العرض من المنافسة كما
    يُخرجه رقم سعري أو مدة متناقضة، ورفعها إلى الحرج يُغرق اللوحة فيُهمَل ما
    يستحق التوقّف.
    """
    from utils import db

    entries = db.list_glossary()
    if not entries:
        return []

    findings = []
    for entry in entries:
        preferred = db.preferred_form(entry, language)
        rejected = [v for v in entry["variants"] if v and v != preferred]
        if not rejected:
            continue

        offending = {}
        for section in sections or []:
            body = str(section.get("content", "") or "")
            if not body:
                continue
            # الصيغة المعتمدة تُحجب **قبل** البحث عن المرفوضة: «مستوى الخدمة»
            # صيغة مرفوضة وهي في الوقت نفسه جزء من «اتفاقية مستوى الخدمة»
            # المعتمدة، فبلا الحجب يُبلَّغ عن كل قسم كتبها صحيحة.
            lowered = body.lower().replace(preferred.lower(), " ")
            used = sorted({v for v in rejected if v.lower() in lowered})
            if used:
                offending[str(section.get("title", ""))] = used

        if not offending:
            continue

        detail = " · ".join(
            f"«{title}»: {' و '.join(used)}" for title, used in sorted(offending.items())
        )
        findings.append({
            "kind": "glossary_drift",
            "severity": "تنبيه",
            "message": (
                f"مصطلح «{entry['term']}» مكتوب بصيغة غير معتمدة — {detail}. "
                f"المعتمد: {preferred}."
            ),
            "sections": sorted(offending),
        })

    return findings


def check(sections: Optional[list] = None,
          timeline_df: Optional[pd.DataFrame] = None,
          project_context: Optional[dict] = None,
          extracted_weeks=None,
          language: str = "ar",
          df_compliance=None, df_solution=None) -> list:
    """
    يقارن مدد التنفيذ المذكورة في الأقسام بالجدول الزمني وبمدة العقد، ويرصد
    انحراف المصطلحات عن المسرد المعتمد (14-6)، وتفاوت النسختين في وضع
    «كليهما» (ب-3).

    Args:
        sections: [{"title", "content"}] — الأقسام المُدرَجة المكتوبة فعلاً.
        language: لغة المخرجات — بها تُحدَّد الصيغة المعتمدة لكل مصطلح، وبها
            وحدها يُشغَّل فحص النسختين.

    Returns:
        قائمة ملاحظات [{"kind", "severity", "message", "sections"}].
        فارغة تعني لا تناقض **مرصود**، لا أن كل شيء سليم.
    """
    findings = []

    # 1) ما تقوله الأقسام
    stated = {}
    for section in sections or []:
        for hit in execution_durations(section.get("content", "")):
            stated.setdefault(hit["weeks"], {"texts": set(), "sections": set()})
            stated[hit["weeks"]]["texts"].add(hit["text"])
            stated[hit["weeks"]]["sections"].add(str(section.get("title", "")))

    # 2) تناقض بين قسمين
    if len(stated) > 1:
        values = sorted(stated)
        if max(values) - min(values) > _TOLERANCE_WEEKS:
            detail = " · ".join(
                f"{' / '.join(sorted(stated[v]['sections']))}: "
                f"{' أو '.join(sorted(stated[v]['texts']))}"
                for v in values
            )
            findings.append({
                "kind": "sections_disagree",
                "severity": "حرجة",
                "message": f"مدة التنفيذ مذكورة بقيم مختلفة في العرض — {detail}",
                "sections": sorted({s for v in values for s in stated[v]["sections"]}),
            })

    # 3) القسم مقابل الجدول الزمني
    span = _timeline_span(timeline_df)
    if span:
        for weeks, data in stated.items():
            if abs(weeks - span) > _TOLERANCE_WEEKS:
                findings.append({
                    "kind": "section_vs_timeline",
                    "severity": "حرجة",
                    "message": (
                        f"«{' / '.join(sorted(data['sections']))}» يذكر "
                        f"{' أو '.join(sorted(data['texts']))} "
                        f"({weeks} أسبوعاً) والجدول الزمني يمتد {span} أسبوعاً."
                    ),
                    "sections": sorted(data["sections"]),
                })

    # 4) القسم مقابل مدة العقد في الكراسة
    limit = contract_weeks(project_context, extracted_weeks)
    if limit:
        for weeks, data in stated.items():
            if weeks > limit + _TOLERANCE_WEEKS:
                findings.append({
                    "kind": "section_vs_contract",
                    "severity": "حرجة",
                    "message": (
                        f"«{' / '.join(sorted(data['sections']))}» يعد بالتنفيذ في "
                        f"{weeks} أسبوعاً ومدة العقد {limit} أسبوعاً."
                    ),
                    "sections": sorted(data["sections"]),
                })

    # 5) فجوة مصفوفة الحلّ (ب-5): مُلتزَم به بلا مكوّن يلبّيه
    findings.extend(traceability.solution_gaps(df_compliance, df_solution))

    # 6) تطابق النسختين في وضع «كليهما» (ب-3) — قبل التنبيهات، فيه حرِج
    findings.extend(bilingual_parity(sections, language))

    # 7) انحراف المصطلحات عن المسرد (14-6) — تنبيه في آخر القائمة بعد الحرِج
    findings.extend(glossary_drift(sections, language))

    return findings


def _timeline_span(df: Optional[pd.DataFrame]) -> Optional[int]:
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return None
    try:
        starts = pd.to_numeric(df["البداية (أسبوع)"], errors="coerce").fillna(1)
        durations = pd.to_numeric(df["المدة (أسبوع)"], errors="coerce").fillna(0)
    except KeyError:
        return None
    ends = starts + durations - 1
    span = int(ends.max()) if len(ends) else 0
    return span if span > 0 else None
