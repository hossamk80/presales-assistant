"""
views/settings.py — إعدادات الذكاء الاصطناعي وإدارة البيانات (المرحلة 11)

الشاشة الموسّعة (11-4): اختيار الموفّر ← النموذج ← الحرارة وحد المخرَج،
واختبار اتصال يعرض الزمن والكلفة. لا حقل معطّل ظاهر — كل خيار معروض يعمل.
"""
import json
import os
import time

import pandas as pd
import streamlit as st

from utils import db, knowledge, providers
from utils.i18n import UI_LANGUAGES, t
from utils.providers import catalog
from utils.state import get_state_snapshot, load_state_snapshot
from utils.ai_engine import LANGUAGES


def _provider_section():
    with st.expander(t("st.provider"), expanded=True):
        names = catalog.provider_names()
        st.selectbox(
            t("st.provider_label"),
            names,
            format_func=lambda n: catalog.provider_info(n).get("label", n),
            key="ai_provider",
        )

        active = providers.active_provider_name()
        info = catalog.provider_info(active)

        # مفتاح الموفّر النشط وحده — لا حقول معطّلة لموفّرين آخرين (11-4)
        if info.get("needs_key", True):
            key_state = info.get("key_state", "")
            if active == "gemini" and (
                os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            ):
                st.info(t("st.key_from_env"))
            st.session_state[key_state] = st.text_input(
                f"🔑 {info.get('label', active)} API Key",
                value=st.session_state.get(key_state, ""),
                type="password",
                placeholder=info.get("key_hint", ""),
            )
        else:
            st.caption(t("st.no_key_needed"))

        if info.get("needs_base_url") or info.get("base_url"):
            st.text_input(
                t("st.base_url"),
                key=f"base_url_{active}",
                placeholder=info.get("base_url", ""),
                help=t("st.base_url_help"),
            )

        options = providers.model_options()
        current = st.session_state.get("ai_model_preference", "")
        st.selectbox(
            t("st.model_label"),
            options,
            index=options.index(current) if current in options else 0,
            key="ai_model_preference",
            help=t("st.model_help"),
        )

        model_id = catalog.resolve_label(
            active, st.session_state.get("ai_model_preference", "")
        )
        m_info = catalog.model_info(active, model_id or "") or {}
        if m_info:
            st.caption(t(
                "st.model_specs",
                context=f"{m_info.get('context', 0):,}",
                inp=m_info.get("in", 0), out=m_info.get("out", 0),
            ))

        c1, c2 = st.columns(2)
        with c1:
            st.checkbox(t("st.temp_enable"), key="ai_temperature_enabled")
            st.slider(
                t("st.temp"), 0.0, 2.0, key="ai_temperature", step=0.1,
                disabled=not st.session_state.get("ai_temperature_enabled"),
            )
        with c2:
            st.number_input(
                t("st.max_tokens"), min_value=0, max_value=128_000, step=1000,
                key="ai_max_tokens", help=t("st.max_tokens_help"),
            )

        # اختبار الاتصال: يعرض الزمن والكلفة الفعليين (11-4)
        if st.button(t("st.test_conn"), type="primary"):
            with st.spinner(t("st.testing")):
                try:
                    started = time.monotonic()
                    result = providers.run(
                        model_id or "", "Reply with the two words: connection works",
                        task="chat",
                    )
                    elapsed = time.monotonic() - started
                    cost = catalog.cost_of(
                        result.provider, result.model,
                        result.usage.input_tokens, result.usage.cached_tokens,
                        result.usage.output_tokens,
                    )
                    st.success(t(
                        "st.conn_ok_cost",
                        reply=(result.text or "").strip()[:80],
                        seconds=f"{elapsed:.1f}", cost=f"{cost:.6f}",
                    ))
                except providers.ProviderError as e:
                    if str(e) == "missing_key":
                        st.error(t("st.key_first"))
                    else:
                        st.error(t("st.conn_failed", error=e))
                except Exception as e:
                    st.error(t("st.conn_failed", error=e))

        st.caption(t("st.catalog_hint", path=catalog.MODELS_PATH))


def _task_models_section():
    """نموذج لكل مهمة (11-5): افتراضي معلن وقابل للتجاوز يدوياً."""
    with st.expander(t("st.task_models")):
        st.caption(t("st.task_models_hint"))
        active = providers.active_provider_name()
        models = catalog.models_of(active)
        labels = {mid: info.get("label", mid) for mid, info in models.items()}
        overrides = dict(st.session_state.get("task_models") or {})

        for task in catalog.TASK_TIERS:
            default_id = catalog.task_default_model(active, task) or ""
            options = list(models)
            current = overrides.get(task) if overrides.get(task) in models else default_id
            chosen = st.selectbox(
                t(f"st.task_{task}"),
                options,
                index=options.index(current) if current in options else 0,
                format_func=lambda mid: labels.get(mid, mid)
                + (" ★" if mid == default_id else ""),
                key=f"task_model_{task}",
            )
            if chosen != default_id:
                overrides[task] = chosen
            else:
                overrides.pop(task, None)

        st.session_state["task_models"] = overrides


def _embedding_section():
    """موفّر التضمين المنفصل + تحذير الإبطال وإعادة الفهرسة (11-6)."""
    with st.expander(t("st.embed")):
        embed_providers = [
            name for name in catalog.provider_names()
            if catalog.embed_models_of(name)
        ]
        current_p = st.session_state.get("embed_provider", "gemini")
        st.selectbox(
            t("st.embed_provider"),
            embed_providers,
            index=embed_providers.index(current_p) if current_p in embed_providers else 0,
            format_func=lambda n: catalog.provider_info(n).get("label", n),
            key="embed_provider",
        )
        embed_models = catalog.embed_models_of(
            st.session_state.get("embed_provider", "gemini")
        )
        options = list(embed_models)
        current_m = st.session_state.get("embed_model", "")
        st.selectbox(
            t("st.embed_model"),
            options,
            index=options.index(current_m) if current_m in options else 0,
            format_func=lambda mid: embed_models.get(mid, {}).get("label", mid),
            key="embed_model",
        )

        # التحذير الإلزامي: تغيير نموذج التضمين يُبطل المتجهات المخزَّنة
        st.warning(t("st.embed_warning"))

        stale = knowledge.stale_chunk_count()
        total = db.kb_stats().get("chunks", 0)
        if stale:
            st.error(t("st.embed_stale", stale=stale, total=total))
        else:
            st.caption(t("st.embed_ok", total=total))

        if total and st.button(t("st.reindex"), type="primary"):
            with st.spinner(t("st.reindexing")):
                updated = knowledge.reindex_all()
            if updated is None:
                st.error(t("st.reindex_failed"))
            else:
                st.success(t("st.reindex_done", n=updated))
                st.rerun()


def _budget_section():
    """حدّ الإنفاق الشهري: إنذار عند 80٪ وإيقاف عند 100٪ (11-9)."""
    with st.expander(t("st.budget")):
        st.number_input(
            t("st.budget_label"), min_value=0.0, step=10.0,
            key="ai_month_budget", help=t("st.budget_help"),
        )
        budget = float(st.session_state.get("ai_month_budget") or 0.0)
        spent = providers.month_spend()
        st.metric(t("st.budget_spent", month=providers.month_key()), f"${spent:.2f}")
        if budget > 0:
            ratio = min(spent / budget, 1.0)
            st.progress(ratio)
            if ratio >= 1.0:
                st.error(t("st.budget_blocked"))
            elif ratio >= providers.BUDGET_WARN_RATIO:
                st.warning(t("st.budget_warn"))

        st.checkbox(t("st.cache_enable"), key="ai_cache_enabled",
                    help=t("st.cache_help"))
        st.checkbox(t("st.compressed"), key="compressed_context",
                    help=t("st.compressed_help"))
        if st.button(t("st.cache_clear")):
            db.ai_cache_clear()
            st.success(t("st.cache_cleared"))


def _usage_section():
    """شاشة الاستهلاك (11-8): لكل منافسة وللمهام ومقارنة النماذج."""
    with st.expander(t("st.usage")):
        month_only = st.toggle(t("st.usage_month_only"), value=True)
        month = providers.month_key() if month_only else ""

        totals = db.usage_totals(month)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(t("st.usage_calls"), f"{totals.get('calls') or 0:,}")
        c2.metric(
            t("st.usage_tokens"),
            f"{(totals.get('input_tokens') or 0) + (totals.get('output_tokens') or 0):,}",
        )
        c3.metric(t("st.usage_cached"), f"{totals.get('cached_tokens') or 0:,}")
        c4.metric(t("st.usage_cost"), f"${totals.get('cost') or 0:.2f}")
        st.caption(t("st.usage_cache_hits", n=totals.get("cache_hits") or 0))

        for group, title_key in (
            ("project", "st.usage_by_project"),
            ("task", "st.usage_by_task"),
            ("model", "st.usage_by_model"),
        ):
            rows = db.usage_summary(group, month)
            if rows:
                st.markdown(f"**{t(title_key)}**")
                st.dataframe(
                    pd.DataFrame(rows).rename(columns={
                        "grp": t("st.usage_col_group"),
                        "calls": t("st.usage_calls"),
                        "input_tokens": t("st.usage_in"),
                        "cached_tokens": t("st.usage_cached"),
                        "output_tokens": t("st.usage_out"),
                        "cost": t("st.usage_cost"),
                    }),
                    hide_index=True, width="stretch",
                )
        if not db.usage_totals("").get("calls"):
            st.info(t("st.usage_empty"))


def render_settings():
    st.markdown(t("st.title"))

    st.markdown(
        f"""<div style="background:#FEF3C7;padding:12px 16px;border-radius:8px;
                    margin-bottom:12px;font-family:Tajawal,sans-serif;font-size:14px;
                    color:#92400E;">{t("st.key_warning")}</div>""",
        unsafe_allow_html=True,
    )

    _provider_section()
    _task_models_section()
    _embedding_section()
    _budget_section()
    _usage_section()

    with st.expander(t("st.out_lang"), expanded=False):
        st.caption(t("st.out_lang_caption"))
        st.radio(
            t("st.lang_label"),
            list(LANGUAGES),
            format_func=lambda c: LANGUAGES[c]["label"],
            key="output_language",
        )

    with st.expander(t("st.ui_lang"), expanded=False):
        st.caption(t("st.ui_lang_caption"))
        st.radio(
            t("st.lang_label"),
            list(UI_LANGUAGES),
            format_func=lambda c: UI_LANGUAGES[c],
            key="ui_language",
        )


def render_data():
    st.markdown(t("dm.title"))

    with st.expander(t("dm.export"), expanded=True):
        st.markdown(t("dm.export_hint"))

        snapshot = get_state_snapshot()
        # Remove API keys from export for security
        export_data = {k: v for k, v in snapshot.items() if "api_" not in k}

        json_str = json.dumps(export_data, ensure_ascii=False, indent=2)
        st.download_button(
            t("dm.download"),
            data=json_str.encode("utf-8"),
            file_name="analyst_workspace.json",
            mime="application/json",
        )
        st.caption(t("dm.size", kb=len(json_str) // 1024))

    with st.expander(t("dm.import")):
        uploaded_json = st.file_uploader(t("dm.import_upload"), type=["json"], key="workspace_import")
        if uploaded_json:
            try:
                data = json.loads(uploaded_json.getvalue().decode("utf-8"))
                if st.button(t("dm.import_btn"), type="primary"):
                    load_state_snapshot(data)
                    st.success(t("dm.import_ok"))
                    st.rerun()
            except Exception as e:
                st.error(t("dm.import_failed", error=e))

    with st.expander(t("dm.clear")):
        st.warning(t("dm.clear_warn"))
        c1, c2 = st.columns(2)
        with c1:
            if st.button(t("dm.clear_analysis"), width="stretch"):
                from utils.state import reset_analysis
                reset_analysis()
                st.success(t("dm.cleared"))
                st.rerun()
        with c2:
            confirm = st.checkbox(t("dm.clear_confirm"))
            if st.button(t("dm.clear_all"), width="stretch", disabled=not confirm):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
