"""
views/dashboard.py — مؤشرات الأداء في لوحة البداية (14-7).

اللوحة كانت تعرض **تعريفاً**: بطاقات تقول ما يفعله النظام. من فتحها مئة مرة لا
يحتاج أن يُقال له ذلك — يحتاج أن يعرف كيف يبلي قسم العطاءات: هل نفوز أكثر؟ عند
أي جهة نفوز؟ كم يكلّف إعداد عرض؟ وهل نُعيد استخدام ما اعتمدناه أم نكتبه ثانيةً؟

الحساب كلّه في `utils/history.py` بلا Streamlit — وهنا العرض وحده. والقاعدة
الحاكمة: **لا يُعرض رقم لا نملكه**. غياب القياس يُقال «لا قياس بعد» ولا يُكتب
صفراً، وعيّنة أصغر من أن تصير نسبة تُعرض عدّاً خاماً.
"""
import streamlit as st

from utils import db, history
from components import theme
from utils.i18n import t


def _metrics() -> dict:
    projects = db.list_projects()
    return history.performance(
        projects,
        costs=db.project_costs(),
        reuse=db.content_block_stats(),
    )


def _win_label(win: dict) -> str:
    """
    نسبة الفوز، أو العدّ الخام حين تكون العيّنة أصغر من أن تصير نسبة.

    «75%» من أربع منافسات تدّعي دقّة لا وجود لها. «3 من 4» أصدق وأنفع، ولا
    تُقرأ اتجاهاً حيث لا اتجاه.
    """
    if not win["decided"]:
        return t("kpi.no_measure")
    if not win["enough"]:
        return t("kpi.win_raw", won=win["won"], decided=win["decided"])
    return f"{win['rate']}% ({win['won']} / {win['decided']})"


def _cost_label(cost: dict) -> str:
    if cost["median"] is None:
        return t("kpi.no_measure")
    return t("kpi.cost_value", median=f"{cost['median']:.2f}",
             total=f"{cost['total']:.2f}")


def _cycle_label(days) -> str:
    return t("kpi.no_measure") if days is None else t("kpi.days", n=f"{days:g}")


def _reuse_label(reuse: dict) -> str:
    if not reuse["approved"]:
        return t("kpi.no_measure")
    return t("kpi.reuse_value", n=reuse["insertions"], blocks=reuse["approved"])


def _render_breakdown(rows: list, title_key: str, empty_key: str):
    """تفصيل نسبة الفوز على الجهة أو القطاع."""
    st.markdown(f"**{t(title_key)}**")
    if not rows:
        st.caption(t(empty_key))
        return
    for row in rows:
        label = _win_label(row)
        st.markdown(f"- {row['label']} — {label}")


def render_performance() -> bool:
    """
    يرسم لوحة المؤشرات. يعيد `False` إن لم يوجد ما يُقاس بعد.

    القيمة المعادة هي ما تقرّر به `app.py` عرضَ خطوات البدء بدلاً منها: تركيب
    جديد بلا منافسة واحدة لا يُعرض له صفر في كل خانة — الصفر أداء مقيس،
    والغياب غياب قياس، وعرض الأول مكان الثاني يوهم بأداء سيّئ لا وجود له.
    """
    metrics = _metrics()
    if not history.has_measurements(metrics):
        return False

    theme.block_title(t("kpi.title"), bi_icon="graph-up")
    st.caption(t("kpi.hint"))

    win = metrics["win"]
    theme.kpi_row(
        [
            ("trophy", t("kpi.win_rate"), _win_label(win)),
            ("hourglass-split", t("kpi.cycle"), _cycle_label(metrics["cycle_days"])),
            ("cash-coin", t("kpi.cost"), _cost_label(metrics["cost"])),
            ("recycle", t("kpi.reuse"), _reuse_label(metrics["reuse"])),
        ],
    )

    if not win["decided"]:
        st.info(t("kpi.no_outcomes"))
        return True

    if not win["enough"]:
        st.caption(t("kpi.small_sample", n=history.MIN_DECIDED))

    col_entity, col_sector = st.columns(2)
    with col_entity:
        _render_breakdown(metrics["by_entity"], "kpi.by_entity", "kpi.no_entity")
    with col_sector:
        _render_breakdown(metrics["by_sector"], "kpi.by_sector", "kpi.no_sector")

    return True
