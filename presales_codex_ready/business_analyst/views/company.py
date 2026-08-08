"""
views/company.py — ملف الشركة ومستودع المعرفة

ملف الشركة يُحفظ على القرص ويُشارَك بين كل المنافسات.
مستودع المعرفة يُفهرس مستندات الشركة ليستند إليها الذكاء الاصطناعي عند الصياغة.
"""
import re

import pandas as pd
import streamlit as st

from utils import audit, auth, db, knowledge, local_content, providers, records, submission
from utils.file_handler import BRAND_COLOR, BRAND_FONT_AR
from components import theme
from utils.i18n import t
from utils.state import get_company_snapshot


def render():

    # 13-3: ملف الشركة وسجلاتها ومستودع معرفتها مِلك المنشأة لا المنافسة —
    # يعدّلها مدير النظام ومدير العطاءات. الباقون يقرأون.
    if not auth.can("company.edit"):
        st.info(t("role.company_read_only"))

    # ── Legal Info ─────────────────────────────────────────────────────────────
    with st.expander(t("co.legal"), expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.session_state["c_name"] = st.text_input(
                t("co.name"),
                value=st.session_state.get("c_name", ""),
                placeholder="شركة الحلول التقنية المتقدمة",
            )
            st.session_state["c_cr"] = st.text_input(
                t("co.cr"),
                value=st.session_state.get("c_cr", ""),
                placeholder="1010XXXXXX",
            )
        with c2:
            st.session_state["c_vat"] = st.text_input(
                t("co.vat"),
                value=st.session_state.get("c_vat", ""),
                placeholder="3XXXXXXXXXXXXXXX3",
            )
            st.session_state["c_phone"] = st.text_input(
                t("co.phone"),
                value=st.session_state.get("c_phone", ""),
                placeholder="+966-11-XXXXXXX",
            )
        with c3:
            st.session_state["c_email"] = st.text_input(
                t("co.email"),
                value=st.session_state.get("c_email", ""),
                placeholder="bids@company.com.sa",
            )
            st.session_state["c_web"] = st.text_input(
                t("co.web"),
                value=st.session_state.get("c_web", ""),
                placeholder="https://www.company.com.sa",
            )
        st.session_state["c_address"] = st.text_input(
            t("co.address"),
            value=st.session_state.get("c_address", ""),
            placeholder="الرياض، المملكة العربية السعودية",
        )
        _bands = local_content.BAND_OPTIONS
        _current = st.session_state.get("c_nitaqat_band", "غير محدد")
        st.session_state["c_nitaqat_band"] = st.selectbox(
            t("co.nitaqat"),
            _bands,
            index=_bands.index(_current) if _current in _bands else 0,
            help=t("co.nitaqat_help"),
        )
        st.session_state["c_overview"] = st.text_area(
            t("co.overview"),
            value=st.session_state.get("c_overview", ""),
            height=120,
            placeholder="أدخل نبذة مختصرة عن الشركة: سنوات الخبرة، التخصصات، الشهادات...",
        )

        if st.session_state.get("c_name"):
            st.success(f"✅ الشركة: **{st.session_state['c_name']}**")
        else:
            st.warning(t("co.name_missing"))

    # ── Brand identity ────────────────────────────────────────────────────────
    with st.expander(t("co.brand"), expanded=False):
        st.caption(t("co.brand_hint"))
        b1, b2 = st.columns(2)
        with b1:
            st.session_state["c_brand_color"] = st.color_picker(
                t("co.brand_color"),
                value=st.session_state.get("c_brand_color") or f"#{BRAND_COLOR}",
            )
        with b2:
            st.session_state["c_doc_font"] = st.text_input(
                t("co.doc_font"),
                value=st.session_state.get("c_doc_font", ""),
                placeholder=BRAND_FONT_AR,
                help=t("co.doc_font_help"),
            )

    # ── Templates ─────────────────────────────────────────────────────────────
    with st.expander(t("co.templates"), expanded=False):
        st.session_state["c_cover_template"] = st.text_area(
            t("co.cover_template"),
            value=st.session_state.get("c_cover_template", ""),
            height=180,
            help="هذا النص يُستخدم تلقائياً في كل عرض فني. يمكن تخصيصه لكل عطاء من منشئ الوثائق.",
        )

    # ── Word Template Upload ───────────────────────────────────────────────────
    with st.expander(t("co.word_template"), expanded=False):
        st.markdown(t("co.word_template_hint"))
        uploaded_template = st.file_uploader(
            t("co.template_upload"), type=["docx"], key="template_upload",
            disabled=auth.blocked("company.edit"),
        )
        if uploaded_template and auth.can("company.edit"):
            data = uploaded_template.getvalue()
            if data != st.session_state.get("c_word_template_bytes"):
                st.session_state["c_word_template_bytes"] = data
                db.save_company(get_company_snapshot(), template=data)
                st.success(t("co.template_saved", name=uploaded_template.name))

        if st.session_state.get("c_word_template_bytes"):
            col_info, col_remove = st.columns([3, 1])
            with col_info:
                st.info(t("co.template_active"))
            with col_remove:
                if st.button(t("co.template_delete"), width="stretch",
                             disabled=auth.blocked("company.edit")):
                    st.session_state["c_word_template_bytes"] = None
                    db.clear_company_template()
                    st.rerun()

    st.divider()
    _render_records()

    st.divider()
    _render_knowledge_base()

    st.divider()
    _render_content_library()

    st.divider()
    _render_entity_templates()

    st.divider()
    _render_glossary()

    st.divider()
    _render_personal_data()

    # حفظ ملف الشركة على القرص عند تغيّره — لمن يملك تعديله وحده (13-3)
    snapshot = get_company_snapshot()
    if auth.can("company.edit") and snapshot != st.session_state.get("_company_saved"):
        db.save_company(snapshot)
        st.session_state["_company_saved"] = snapshot


# ─── سجلات الأدلة (المرحلة 12) ───────────────────────────────────────────────


def _column_config(registry: str) -> dict:
    """يبني إعداد أعمدة المحرّر من تعريف السجل — نوع كل عمود يحدّد أداته."""
    config = {}
    for col in records.columns_of(registry):
        label = t(col["label_key"])
        if col["kind"] == records.INT:
            config[col["key"]] = st.column_config.NumberColumn(
                label, min_value=0, step=1,
            )
        elif col["kind"] == records.BOOL:
            config[col["key"]] = st.column_config.CheckboxColumn(label)
        elif col["kind"] == records.CHOICE:
            config[col["key"]] = st.column_config.SelectboxColumn(
                label, options=col["options"],
            )
        elif col["kind"] == records.DATE:
            config[col["key"]] = st.column_config.TextColumn(
                label, help=t("rec.date_help"),
            )
        elif col["kind"] == records.LONGTEXT:
            config[col["key"]] = st.column_config.TextColumn(label, width="large")
        else:
            config[col["key"]] = st.column_config.TextColumn(label)
    return config


def _render_registry(registry: str):
    """محرّر سجل واحد — تعريفه في `utils/records.py` لا هنا."""
    spec = records.REGISTRIES[registry]
    rows = db.list_records(registry)

    with st.expander(f"{t(spec['label_key'])} ({len(rows)})", expanded=False):
        st.caption(t(spec["hint_key"]))

        frame = pd.DataFrame(
            rows or [records.blank_row(registry)],
            columns=records.column_keys(registry),
        )
        edited = st.data_editor(
            frame,
            column_config=_column_config(registry),
            num_rows="dynamic",
            width="stretch",
            key=f"rec_editor_{registry}",
        )

        if st.button(t("rec.save"), key=f"rec_save_{registry}", type="primary",
                     disabled=auth.blocked("company.edit")):
            cleaned = [
                records.normalize_row(registry, row)
                for row in edited.to_dict(orient="records")
            ]
            dropped = records.partial_rows(registry, cleaned)
            cleaned = [r for r in cleaned if not records.is_blank(registry, r)]
            if dropped:
                st.warning(t("rec.dropped_partial", n=dropped))
            db.save_records(registry, cleaned)
            st.success(t("rec.saved", n=len(cleaned)))
            st.rerun()

        _render_expiry_warnings(registry, rows)


# الحقول التي يُفقد انتهاؤها المنافسة — تُفحص عند الموعد النهائي للمنافسة
_EXPIRY_FIELDS = {
    "certificates": "expiry",
    "vendors": "letter_expiry",
    "people": "cert_expiry",
}


def _render_expiry_warnings(registry: str, rows: list):
    """
    شهادة أو خطاب تفويض ينتهي قبل الموعد النهائي للمنافسة الحالية.

    هي بين يديك اليوم لكنها غير مقبولة يوم الفتح — نفس منطق مستندات المظروف،
    وهنا يُقرأ الموعد من السياق الموحّد للمنافسة المفتوحة إن وُجدت.
    """
    field = _EXPIRY_FIELDS.get(registry)
    if not field or not rows:
        return

    deadline = submission.deadline_date(st.session_state.get("project_context"))
    if deadline is not None:
        expiring = records.expiring_before(rows, field, deadline)
        if expiring:
            label_col = records.columns_of(registry)[0]["key"]
            names = " · ".join(str(r.get(label_col, "")) for r in expiring)
            st.error(t("rec.expiring", n=len(expiring), names=names))

    unreadable = records.undated(rows, field)
    if unreadable:
        st.warning(t("rec.undated", n=len(unreadable)))


def _render_records():
    st.markdown(t("rec.title"))
    st.caption(t("rec.intro"))
    for registry in records.COMPANY_REGISTRIES:
        _render_registry(registry)


# ─── مكتبة المحتوى المعتمد (14-4) ─────────────────────────────────────────────
#
# موضعها في ملف الشركة لا في المنافسة: الكتلة مِلك المنشأة تُعاد في كل عرض،
# ونسخة منها لكل منافسة تُعيد المشكلة التي وُجدت المكتبة لحلّها.


def _block_status_label(block: dict) -> str:
    label = t("lib.status_" + block["status"])
    if block["status"] == db.BLOCK_APPROVED and db.block_review_due(block):
        return f"⚠️ {label}"
    return {"draft": "📝", "approved": "✅", "retired": "🗄️"}.get(
        block["status"], ""
    ) + f" {label}"


def _save_block_form(block: dict | None, may_edit: bool):
    """نموذج كتلة — جديدة (`block is None`) أو قائمة."""
    is_new = block is None
    prefix = "libnew" if is_new else f"lib{block['id']}"

    c_key, c_title = st.columns([1, 2])
    with c_key:
        key = st.text_input(t("lib.key"), value="" if is_new else block["key"],
                            key=f"{prefix}_key", disabled=not may_edit or not is_new,
                            help=t("lib.key_help"))
    with c_title:
        title = st.text_input(t("lib.block_title"),
                              value="" if is_new else block["title"],
                              key=f"{prefix}_title", disabled=not may_edit)

    c_cat, c_sec, c_lang, c_rev = st.columns(4)
    with c_cat:
        category = st.text_input(t("lib.category"),
                                 value="" if is_new else block["category"],
                                 key=f"{prefix}_cat", disabled=not may_edit)
    with c_sec:
        sector = st.text_input(t("lib.sector"),
                               value="" if is_new else block["sector"],
                               key=f"{prefix}_sector", disabled=not may_edit)
    with c_lang:
        language = st.text_input(t("lib.language"),
                                 value="" if is_new else block["language"],
                                 key=f"{prefix}_lang", disabled=not may_edit)
    with c_rev:
        months = st.number_input(
            t("lib.review_months"), min_value=0, max_value=120, step=1,
            value=db.DEFAULT_REVIEW_MONTHS if is_new else int(block["review_months"]),
            key=f"{prefix}_months", disabled=not may_edit,
            help=t("lib.review_months_help"),
        )

    body = st.text_area(t("lib.body"), value="" if is_new else block["body"],
                        height=180, key=f"{prefix}_body", disabled=not may_edit)

    if not is_new:
        st.caption(t("lib.edit_resets"))

    if st.button(t("common.save_now"), key=f"{prefix}_save", type="primary",
                 disabled=not may_edit):
        if not key.strip() or not title.strip() or not body.strip():
            st.warning(t("lib.key_required"))
            return
        if is_new and db.content_block_by_key(key.strip()) is not None:
            st.warning(t("lib.key_taken"))
            return
        db.save_content_block(
            key=key.strip(), title=title.strip(), body=body, category=category.strip(),
            sector=sector.strip(), language=language.strip(),
            review_months=int(months), updated_by=auth.display_name(),
        )
        audit.record(audit.BLOCK_EDIT, target=f"block:{key.strip()}",
                     detail=title.strip())
        st.success(t("lib.saved"))
        st.rerun()


def _render_content_library():
    """
    المكتبة: إنشاء الكتل واعتمادها ومراجعتها وسحبها.

    الاعتماد خلف صلاحية مستقلة عن التحرير (`library.approve`): كاتب يعتمد نصّه
    بنفسه يجعل «معتمد» توقيعاً على بياض — والغاية من الحالة أن تعني مراجعةً
    جرت لا مربّعاً أُشّر.
    """
    may_edit = auth.can("library.manage")
    may_approve = auth.can("library.approve")
    stats = db.content_block_stats()

    with st.expander(t("lib.title")):
        st.caption(t("lib.intro"))
        if not may_edit:
            st.info(t("lib.read_only"))
        st.caption(t("lib.stats", total=stats["total"],
                     approved=stats[db.BLOCK_APPROVED], due=stats["due"]))

        status_filter = st.selectbox(
            t("lib.status"), ("",) + db.BLOCK_STATUSES,
            format_func=lambda s: t("lib.any") if not s else t("lib.status_" + s),
            key="lib_status_filter",
        )
        blocks = db.list_content_blocks(status=status_filter)

        if not blocks:
            st.info(t("lib.empty"))

        for block in blocks:
            header = f"{_block_status_label(block)} — {block['title'] or block['key']}"
            with st.expander(header):
                reviewed = block["reviewed_at"] or t("lib.never_reviewed")
                st.caption(f"{t('lib.reviewed_at')}: {reviewed} · "
                           + t("lib.used_count", count=int(block["used_count"] or 0)))
                if block["status"] == db.BLOCK_APPROVED and db.block_review_due(block):
                    st.warning(t("lib.review_due"))

                _save_block_form(block, may_edit)

                if not may_approve:
                    st.caption(t("lib.cannot_approve"))

                c_ap, c_rev, c_ret, c_del = st.columns(4)
                with c_ap:
                    if st.button(t("lib.approve"), key=f"lib_ap_{block['id']}",
                                 width="stretch",
                                 disabled=not may_approve
                                 or block["status"] == db.BLOCK_APPROVED):
                        db.set_block_status(block["id"], db.BLOCK_APPROVED,
                                            auth.display_name())
                        audit.record(audit.BLOCK_STATUS, target=f"block:{block['key']}",
                                     detail=db.BLOCK_APPROVED)
                        st.success(t("lib.approved_done"))
                        st.rerun()
                with c_rev:
                    if st.button(t("lib.mark_reviewed"), key=f"lib_rv_{block['id']}",
                                 width="stretch", disabled=not may_approve):
                        db.mark_block_reviewed(block["id"], auth.display_name())
                        audit.record(audit.BLOCK_REVIEW,
                                     target=f"block:{block['key']}")
                        st.success(t("lib.reviewed_done"))
                        st.rerun()
                with c_ret:
                    retired = block["status"] == db.BLOCK_RETIRED
                    if st.button(t("lib.to_draft") if retired else t("lib.retire"),
                                 key=f"lib_rt_{block['id']}", width="stretch",
                                 disabled=not may_approve):
                        target = db.BLOCK_DRAFT if retired else db.BLOCK_RETIRED
                        db.set_block_status(block["id"], target, auth.display_name())
                        audit.record(audit.BLOCK_STATUS, target=f"block:{block['key']}",
                                     detail=target)
                        st.success(t("lib.retired_done"))
                        st.rerun()
                with c_del:
                    if st.button(t("common.delete"), key=f"lib_del_{block['id']}",
                                 width="stretch", disabled=not may_approve):
                        db.delete_content_block(block["id"])
                        audit.record(audit.BLOCK_DELETE,
                                     target=f"block:{block['key']}")
                        st.success(t("lib.deleted"))
                        st.rerun()

        st.divider()
        st.markdown(f"**{t('lib.add')}**")
        _save_block_form(None, may_edit)


# ─── نماذج الجهات (ب-4) ───────────────────────────────────────────────────────
#
# قالب الشركة واحد، وبعض الجهات تفرض نموذجها وترفض ما عداه رفضاً شكلياً. من
# يقدّم لثلاث جهات كان يبدّل القالب يدوياً قبل كل تصدير ويتذكّر أيّها الصحيح.


def _render_entity_templates():
    """نموذج Word لكل جهة — يُختار تلقائياً عند التصدير حسب جهة المنافسة."""
    may_edit = auth.can("company.edit")
    saved = db.list_entity_templates()

    with st.expander(t("et.title")):
        st.caption(t("et.hint"))

        known = sorted({
            str(r.get("name", "")).strip() for r in db.list_records("entities")
            if str(r.get("name", "")).strip()
        })
        entity = st.selectbox(
            t("et.entity"), [""] + known,
            format_func=lambda n: n or t("et.entity_new"),
            key="et_pick", disabled=not may_edit,
        )
        if not entity:
            # جهة خارج سجل الجهات: تُكتب باسمها، والتوحيد يتكفّل بالإملاء
            entity = st.text_input(t("et.entity_name"), key="et_name",
                                   disabled=not may_edit,
                                   help=t("et.entity_name_help"))

        uploaded = st.file_uploader(t("et.upload"), type=["docx"],
                                    key="et_file", disabled=not may_edit)
        if uploaded is not None and entity.strip() and st.button(
                t("et.save"), type="primary", disabled=not may_edit):
            db.save_entity_template(entity, uploaded.getvalue(),
                                    filename=uploaded.name,
                                    updated_by=auth.display_name())
            st.success(t("et.saved", entity=entity.strip()))
            st.rerun()

        if not saved:
            st.info(t("et.empty"))
            return

        st.caption(t("et.count", n=len(saved)))
        for record in saved:
            cols = st.columns([4, 1])
            with cols[0]:
                st.markdown(
                    f"🏛️ **{record['entity_label']}** — {record['filename'] or '—'} "
                    f"· {int(record['size'] or 0) // 1024} KB · {record['updated_at']}"
                )
            with cols[1]:
                if st.button(t("common.delete"), key=f"et_del_{record['id']}",
                             width="stretch", disabled=not may_edit):
                    db.delete_entity_template(record["entity_label"])
                    st.rerun()


# ─── مسرد المصطلحات (14-6) ────────────────────────────────────────────────────


def _glossary_form(entry: dict | None, may_edit: bool):
    """نموذج مصطلح — جديد (`entry is None`) أو قائم."""
    is_new = entry is None
    prefix = "glnew" if is_new else f"gl{entry['id']}"

    c_term, c_ar, c_en = st.columns(3)
    with c_term:
        term = st.text_input(t("gl.term"), value="" if is_new else entry["term"],
                             key=f"{prefix}_term", help=t("gl.term_help"),
                             disabled=not may_edit or not is_new)
    with c_ar:
        pref_ar = st.text_input(t("gl.preferred_ar"),
                                value="" if is_new else entry["preferred_ar"],
                                key=f"{prefix}_ar", disabled=not may_edit)
    with c_en:
        pref_en = st.text_input(t("gl.preferred_en"),
                                value="" if is_new else entry["preferred_en"],
                                key=f"{prefix}_en", disabled=not may_edit)

    variants = st.text_input(
        t("gl.variants"),
        value="" if is_new else " · ".join(entry["variants"]),
        key=f"{prefix}_var", help=t("gl.variants_help"), disabled=not may_edit,
    )
    note = st.text_input(t("gl.note"), value="" if is_new else entry["note"],
                         key=f"{prefix}_note", disabled=not may_edit)

    if st.button(t("common.save_now"), key=f"{prefix}_save", type="primary",
                 disabled=not may_edit):
        if not term.strip() or not (pref_ar.strip() or pref_en.strip()):
            st.warning(t("gl.term_required"))
            return
        if is_new and db.glossary_by_term(term.strip()) is not None:
            st.warning(t("gl.term_taken"))
            return
        db.save_glossary_term(
            term=term.strip(), preferred_ar=pref_ar, preferred_en=pref_en,
            variants=[v for v in re.split(r"[·,;\n]", variants or "") if v.strip()],
            note=note, updated_by=auth.display_name(),
        )
        audit.record(audit.GLOSSARY_EDIT, target=f"term:{term.strip()}")
        st.success(t("gl.saved"))
        st.rerun()


def _render_glossary():
    """
    المسرد: مصطلح ← صيغته المعتمدة بكل لغة، وصيغه المرفوضة.

    الصيغ المرفوضة ليست زينة: بها وحدها يصير التوحيد **قابلاً للفحص** — بلا
    معرفة الخطأ لا يُرصد الانحراف، ويبقى «صيغة واحدة» رجاءً موجَّهاً إلى نموذج.
    """
    may_edit = auth.can("company.edit")
    entries = db.list_glossary()

    with st.expander(t("gl.title")):
        st.caption(t("gl.intro"))
        if not may_edit:
            st.info(t("role.company_read_only"))

        if not entries:
            st.info(t("gl.empty"))
        else:
            st.caption(t("gl.count", n=len(entries)))

        for entry in entries:
            preferred = " / ".join(filter(None, [entry["preferred_ar"],
                                                 entry["preferred_en"]]))
            with st.expander(f"🔤 {entry['term']} — {preferred}"):
                _glossary_form(entry, may_edit)
                if not entry["variants"]:
                    st.caption(t("gl.no_variants"))
                if st.button(t("common.delete"), key=f"gl_del_{entry['id']}",
                             disabled=not may_edit):
                    db.delete_glossary_term(entry["id"])
                    audit.record(audit.GLOSSARY_EDIT,
                                 target=f"term:{entry['term']}", detail="delete")
                    st.success(t("gl.deleted"))
                    st.rerun()

        st.divider()
        st.markdown(f"**{t('gl.add')}**")
        _glossary_form(None, may_edit)


# ─── مستودع المعرفة ───────────────────────────────────────────────────────────


def _render_personal_data():
    """
    سياسة البيانات الشخصية (13-10): أساس المعالجة · مدة الاحتفاظ · حذف عند
    الطلب. رفع السير يُدخل النظام في نطاق النظام، وهذه أدواته الثلاث.
    """
    may_edit = auth.can("company.edit")
    policy = db.personal_data_policy()

    with st.expander(t("pd.title")):
        st.caption(t("pd.hint"))

        c1, c2 = st.columns(2)
        with c1:
            basis = st.selectbox(
                t("pd.basis"), db.LEGAL_BASES,
                index=db.LEGAL_BASES.index(policy["legal_basis"]),
                format_func=lambda b: t("pd.basis_" + b),
                key="pd_basis", disabled=not may_edit,
            )
        with c2:
            months = st.number_input(
                t("pd.retention"), min_value=0, max_value=240, step=6,
                value=policy["retention_months"], key="pd_retention",
                disabled=not may_edit, help=t("pd.retention_help"),
            )
        if not months:
            st.caption(t("pd.retention_unlimited"))

        if may_edit and (basis != policy["legal_basis"]
                         or int(months) != policy["retention_months"]):
            if st.button(t("pd.save_policy"), type="primary", key="pd_save"):
                db.set_personal_data_policy(basis, int(months))
                audit.record(audit.PD_POLICY, detail=f"{basis}:{int(months)}")
                st.success(t("pd.policy_saved"))
                st.rerun()

        # ── السير التي تجاوزت المدة ──
        expired = db.expired_cv_documents()
        st.markdown(f"**{t('pd.expired', n=len(expired))}**")
        if expired:
            st.warning(t("pd.expired_hint", months=policy["retention_months"]))
            for doc in expired:
                st.markdown(
                    f'· **{doc["name"]}** — {doc["person"] or t("pd.cv_owner_none")}'
                    f' · {doc["added_at"]} · {doc["chunks"]} {t("co.kb_chunk_unit")}'
                )
            if st.button(t("pd.delete_expired"), key="pd_delete_expired",
                         disabled=not may_edit):
                for doc in expired:
                    db.delete_kb_document(doc["id"])
                audit.record(audit.PD_ERASE, detail=f"expired:{len(expired)}")
                st.success(t("pd.expired_deleted", n=len(expired)))
                st.rerun()
        else:
            st.caption(t("pd.expired_none"))

        # ── حذف شخص عند الطلب ──
        st.divider()
        st.markdown(f"**{t('pd.erase')}**")
        st.caption(t("pd.erase_hint"))

        people = [str(r.get("name", "")).strip() for r in db.list_records("people")
                  if str(r.get("name", "")).strip()]
        if not people:
            st.caption(t("pd.no_people"))
            return

        target = st.selectbox(t("pd.person"), people, key="pd_person",
                              disabled=not may_edit)
        footprint = db.person_footprint(target)
        st.caption(t("pd.footprint", records=footprint["records"],
                     documents=footprint["documents"], chunks=footprint["chunks"]))

        confirm = st.checkbox(t("pd.erase_confirm"), key="pd_confirm",
                              disabled=not may_edit)
        if st.button(t("pd.erase_btn"), type="primary", key="pd_erase",
                     disabled=not (may_edit and confirm)):
            removed = db.forget_person(target)
            audit.record(audit.PD_ERASE, target=target,
                         detail=f'{removed["documents"]}:{removed["chunks"]}')
            st.success(t("pd.erased", name=target, documents=removed["documents"],
                         chunks=removed["chunks"]))
            st.rerun()


def _render_knowledge_base():
    st.markdown(t("co.kb"))
    stats = db.kb_stats()
    st.caption(t("co.kb_caption"))

    c1, c2 = st.columns(2)
    c1.metric(t("co.kb_docs"), stats.get("docs", 0))
    c2.metric(t("co.kb_chunks"), stats.get("chunks", 0))

    # الفهرسة تستدعي **موفّر التضمين** لا موفّر النص، فالجاهزية تُقاس عليه.
    has_key = providers.embed_ready()
    if not has_key:
        st.warning(t("co.kb_needs_key"))

    with st.expander(t("co.kb_add"), expanded=stats.get("docs", 0) == 0):
        category = st.selectbox(
            t("co.kb_type"),
            options=list(knowledge.CATEGORIES),
            format_func=lambda k: t(f"kbcat.{k}"),
        )
        # 14-5: العيّنة تُقرأ أسلوباً لا مصدرَ وقائع — يُقال صراحةً عند الرفع
        # كي لا يرفعها أحد ظنّاً أنه يغذّي المستودع بمحتوى.
        if category == knowledge.PROPOSAL_SAMPLE:
            st.info(t("sty.upload_hint"))
            samples = knowledge.sample_stats()
            if samples["documents"]:
                st.caption(
                    t("sty.ready", n=samples["documents"]) if samples["ready"]
                    else t("sty.too_short", words=knowledge.MIN_SAMPLE_WORDS)
                )

        # 13-10: السيرة الذاتية بيانات شخص بعينه — تُربط به عند الرفع، فحذف
        # بياناته لاحقاً لا يصير بحثاً بالاسم في أسماء الملفات.
        person = ""
        if category == "cv":
            names = [""] + [
                str(r.get("name", "")).strip() for r in db.list_records("people")
                if str(r.get("name", "")).strip()
            ]
            person = st.selectbox(
                t("pd.cv_owner"), names,
                format_func=lambda n: n or t("pd.cv_owner_none"),
                key="kb_person", help=t("pd.cv_owner_help"),
                disabled=auth.blocked("company.edit"),
            )

        files = st.file_uploader(
            t("an.formats"),
            accept_multiple_files=True,
            key="kb_upload",
            disabled=auth.blocked("company.edit"),
        )
        if st.button(t("co.kb_index"), type="primary",
                     disabled=not files or not has_key or auth.blocked("company.edit")):
            progress = st.progress(0.0)
            added = 0
            for i, f in enumerate(files, start=1):
                progress.progress((i - 1) / len(files), text=f"فهرسة {f.name}…")
                count = knowledge.ingest_file(f, category, person=person)
                if count:
                    added += 1
                    st.success(t("co.kb_indexed", name=f.name, n=count))
            progress.empty()
            if added:
                st.rerun()

    documents = db.list_kb_documents()
    if not documents:
        return

    with st.expander(t("co.kb_list", n=len(documents)), expanded=False):
        for doc in documents:
            c_info, c_del = st.columns([6, 1])
            with c_info:
                st.markdown(
                    f"**{doc['name']}**<br>"
                    f"<span style='color:{theme.TOKENS['muted']};font-size:12px'>"
                    f"{t('kbcat.' + doc['category'])} · "
                    f"{doc['chunks']} {t('co.kb_chunk_unit')} · "
                    f"{doc['char_count']:,} {t('co.kb_char_unit')} · {doc['added_at']}"
                    f"</span>",
                    unsafe_allow_html=True,
                )
            with c_del:
                if st.button("🗑️", key=f"kbdel_{doc['id']}", width="stretch",
                             disabled=auth.blocked("company.edit")):
                    db.delete_kb_document(doc["id"])
                    st.rerun()

    with st.expander(t("co.kb_try"), expanded=False):
        query = st.text_input(
            t("co.kb_query"), placeholder="…"
        )
        if query and has_key:
            hits = knowledge.search(query)
            if not hits:
                st.info(t("co.kb_no_hits"))
            for h in hits:
                st.markdown(f"**{h['doc_name']}** · {t('co.kb_similarity')} {h['score']:.2f}")
                st.caption(h["text"][:400] + ("…" if len(h["text"]) > 400 else ""))
