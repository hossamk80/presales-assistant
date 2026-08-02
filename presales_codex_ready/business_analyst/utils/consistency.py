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


def check(sections: Optional[list] = None,
          timeline_df: Optional[pd.DataFrame] = None,
          project_context: Optional[dict] = None,
          extracted_weeks=None) -> list:
    """
    يقارن مدد التنفيذ المذكورة في الأقسام بالجدول الزمني وبمدة العقد.

    Args:
        sections: [{"title", "content"}] — الأقسام المُدرَجة المكتوبة فعلاً.

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
