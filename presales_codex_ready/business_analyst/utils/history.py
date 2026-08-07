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


# ─── مؤشرات الأداء (14-7) ─────────────────────────────────────────────────────
#
# لوحة البداية كانت تعرض **تعريفاً**: بطاقات تقول ما يفعله النظام. من فتحها
# مئة مرة لا يحتاج أن يُقال له ذلك في المرة الأولى بعد المئة — يحتاج أن يعرف
# كيف يبلي قسم العطاءات.
#
# الحساب هنا خالٍ من Streamlit ومن قاعدة البيانات: يأخذ صفوف المنافسات كما هي
# ويعيد أرقاماً — فيُختبر بلا تركيب واجهة ولا قاعدة.
#
# **ثلاث قواعد تحكم كل رقم في هذا القسم:**
#
# 1. **غياب القياس ليس صفراً.** بلا منافسة محسومة تُعاد `None` لا `0%`.
#    الصفر يقول «لم نفز قط»، والغياب يقول «لا نعرف» — والفرق قرار استثمار.
# 2. **العيّنة الصغيرة لا تصير نسبة.** «75%» من أربع منافسات تدّعي دقّة لا
#    وجود لها؛ دونها يُعرض العدّ الخام «3 من 4» وهو أصدق وأنفع.
# 3. **الوسيط لا المتوسّط في الزمن.** منافسة هُجرت وبقيت مفتوحة ثمانية أشهر
#    تجرّ المتوسّط وحده إلى رقم لا يصف أي منافسة حقيقية.

# أدنى عدد منافسات محسومة تصير عندها النسبة نسبة.
MIN_DECIDED = 5

# النتائج التي تدخل مقام نسبة الفوز. «لم يُقدَّم» ليست خسارة — عطاء لم نتقدّم
# له لم نخسره، وإدخاله المقام يخفض النسبة بقرار كان لنا لا علينا. و«قيد
# التقييم» لم تُحسم بعد، فإدخالها يخفضها بما لم يقع.
_DECIDED = (OUTCOME_WON, OUTCOME_LOST)


def _outcome(project: dict) -> str:
    return str(project.get("outcome", "") or "").strip()


def _parse_stamp(value: str):
    from datetime import datetime

    text = str(value or "").strip()[:19]
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def win_rate(projects: list) -> dict:
    """
    نسبة الفوز من المنافسات **المحسومة** وحدها.

    Returns:
        `{"won", "lost", "decided", "rate", "enough"}`.
        `rate` = `None` بلا منافسة محسومة، و `enough` تقول هل بلغت العيّنة
        الحدّ الذي تصير عنده النسبة ذات معنى.
    """
    won = sum(1 for p in projects or [] if _outcome(p) == OUTCOME_WON)
    lost = sum(1 for p in projects or [] if _outcome(p) == OUTCOME_LOST)
    decided = won + lost
    return {
        "won": won,
        "lost": lost,
        "decided": decided,
        "rate": round(100 * won / decided) if decided else None,
        "enough": decided >= MIN_DECIDED,
    }


def win_rate_by(projects: list, field: str, limit: int = 5) -> list:
    """
    نسبة الفوز مجمّعة على حقل — «entity» أو «sector».

    المجموعات مرتّبة بعدد المحسوم تنازلياً: جهة تقدّمنا لها مرة لا تتصدّر
    لوحةً على جهة تقدّمنا لها عشرين. والجهة تُوحَّد إملائياً بـ
    `normalize_entity` فلا تُعدّ «وزارة الصحة» و«وزاره الصحه» جهتين.

    المجموعات بلا محسوم **تُسقَط**: صفٌّ بلا نسبة ولا عدّ ليس قياساً.
    """
    groups: dict = {}
    for project in projects or []:
        raw = str(project.get(field, "") or "").strip()
        if not raw:
            continue
        key = normalize_entity(raw) if field == "entity" else raw.lower()
        groups.setdefault(key, {"label": raw, "projects": []})
        groups[key]["projects"].append(project)

    rows = []
    for data in groups.values():
        stats = win_rate(data["projects"])
        if not stats["decided"]:
            continue
        rows.append({"label": data["label"], **stats,
                     "total": len(data["projects"])})

    rows.sort(key=lambda r: (r["decided"], r["won"]), reverse=True)
    return rows[:limit]


def cycle_days(projects: list) -> list:
    """
    أيام الإعداد لكل منافسة: **من الإنشاء إلى آخر تعديل**.

    هذا ما تملكه القاعدة فعلاً، ويُقال للمستخدم بهذه الصيغة لا بـ«زمن الدورة»
    مطلقاً: `set_outcome` لا يمسّ `updated_at`، فالرقم يقيس الإعداد لا الزمن
    حتى صدور النتيجة. تسميته بغير ما يقيس تجعله رقماً لا يُبنى عليه.

    القيم السالبة تُسقَط: قاعدة مستعادة أو ساعة نظام عُدّلت تُنتجها.
    """
    days = []
    for project in projects or []:
        start = _parse_stamp(project.get("created_at"))
        end = _parse_stamp(project.get("updated_at"))
        if start is None or end is None:
            continue
        span = (end - start).days
        if span >= 0:
            days.append(span)
    return sorted(days)


def median_cycle_days(projects: list) -> Optional[float]:
    """وسيط أيام الإعداد، أو `None` بلا بيانات."""
    days = cycle_days(projects)
    if not days:
        return None
    middle = len(days) // 2
    if len(days) % 2:
        return float(days[middle])
    return (days[middle - 1] + days[middle]) / 2


def preparation_cost(projects: list, costs: dict) -> dict:
    """
    كلفة الإعداد: الإجمالي ووسيط ما أُنفق على منافسة.

    `costs` من `db.project_costs` — لا تشمل منافسة بلا استدعاء. تلك تُستبعد
    من الوسيط ولا تدخله صفراً: منافسة لم تُعالَج بعد ليست منافسة رخيصة.
    """
    values = sorted(
        cost for cost in (
            (costs or {}).get(int(p["id"]))
            for p in projects or [] if p.get("id") is not None
        )
        if cost is not None
    )

    if not values:
        return {"total": 0.0, "median": None, "projects": 0}

    middle = len(values) // 2
    median = float(values[middle]) if len(values) % 2 \
        else (values[middle - 1] + values[middle]) / 2
    return {"total": round(sum(values), 4), "median": round(median, 4),
            "projects": len(values)}


def performance(projects: list, costs: Optional[dict] = None,
                reuse: Optional[dict] = None) -> dict:
    """
    كل مؤشرات 14-7 في استدعاء واحد — تستهلكها لوحة البداية.

    `reuse` من `db.content_block_stats` (14-4): عدّاد إدراج الكتل المعتمدة هو
    قياس إعادة الاستخدام، فلا يُبنى له مصدر ثانٍ.
    """
    blocks = reuse or {}
    return {
        "projects": len(projects or []),
        "win": win_rate(projects),
        "by_entity": win_rate_by(projects, "entity"),
        "by_sector": win_rate_by(projects, "sector"),
        "cycle_days": median_cycle_days(projects),
        "cost": preparation_cost(projects, costs or {}),
        "reuse": {
            "insertions": int(blocks.get("used", 0) or 0),
            "approved": int(blocks.get("approved", 0) or 0),
        },
    }


def has_measurements(metrics: dict) -> bool:
    """
    هل يوجد ما يُقاس أصلاً؟

    تركيب جديد بلا منافسة واحدة لا يُعرض له صفر في كل خانة — تُعرض له خطوات
    البدء بدلاً منها. اللوحة تعرض قياساً حين يوجد قياس، وإرشاداً حين لا يوجد.
    """
    return bool(metrics.get("projects"))
