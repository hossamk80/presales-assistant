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

from utils import audit, auth, backup, db, knowledge, providers, savings
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

        # ما تجنّبناه بالمعالجة المحلية — مقابل ما أُنفق أعلاه
        led = savings.summary()
        if led["tokens_before"] or led["avoided_calls"]:
            st.markdown(f"**{t('st.savings')}**")
            st.caption(t("st.savings_hint"))
            s1, s2, s3 = st.columns(3)
            s1.metric(t("st.savings_tokens"), f"{led['tokens_saved']:,}",
                      delta=f"-{round(led['ratio'] * 100)}%")
            s2.metric(t("st.savings_avoided"), f"{led['avoided_calls']:,}")
            s3.metric(t("st.savings_sent"), f"{led['tokens_after']:,}")
            by_method = {
                t(f"st.method_{method}"): tokens
                for method, tokens in led["by_method"].items() if tokens
            }
            if by_method:
                st.dataframe(
                    pd.DataFrame(
                        [{t("st.usage_col_group"): k, t("st.savings_tokens"): v}
                         for k, v in by_method.items()]
                    ),
                    hide_index=True, width="stretch",
                )


def _my_account_section():
    """حساب المستخدم نفسه: اسمه الظاهر وتغيير كلمته بمعرفة القديمة."""
    user = auth.current_user()
    if user is None:
        return

    with st.expander(t("us.my_account")):
        st.caption(t("us.signed_in_as", username=user["username"]))

        display_name = st.text_input(
            t("au.display_name"), value=user.get("display_name", ""),
            key="me_display_name",
        )
        if st.button(t("us.save_profile"), key="me_save_profile"):
            db.update_user_profile(user["id"], display_name)
            st.success(t("us.profile_saved"))
            st.rerun()

        st.divider()
        st.markdown(f"**{t('us.change_password')}**")
        current = st.text_input(t("us.current_password"), type="password",
                                key="me_current_password")
        new = st.text_input(t("us.new_password"), type="password",
                            key="me_new_password")
        confirm = st.text_input(t("au.password_confirm"), type="password",
                                key="me_confirm_password")
        if st.button(t("us.change_password_btn"), key="me_change_password"):
            problem = auth.change_password(user["id"], new, confirm, current)
            if problem:
                st.error(t(problem))
            else:
                st.success(t("us.password_changed"))


def _permissions_section():
    """
    تحرير مصفوفة الصلاحيات: صلاحية × دور.

    المصفوفة في `utils/auth.py` **افتراضٌ** لا حكم: قسم عطاءات يوزّع مسؤولياته
    بطريقته، ومن أراد أن يعتمد الكميات المحسوبة مراجعُه لا مديرُ عطاءاته لا
    ينتظر إصداراً جديداً من البرنامج.

    ما لا يُلمَس هنا يبقى تابعاً للافتراض، فترقيةٌ تُضيف صلاحية لدور تسري على
    التثبيت القائم بدل أن يتجمّد على صورته يوم أول تشغيل.
    """
    with st.expander(t("perm.title")):
        st.caption(t("perm.hint"))

        current = {
            p: {r: (r in auth.permission_roles(p)) for r in auth.ROLES}
            for p in auth.PERMISSIONS
        }

        table = pd.DataFrame([
            {t("perm.col_permission"): p,
             **{t(f"role.{r}"): current[p][r] for r in auth.ROLES}}
            for p in sorted(auth.PERMISSIONS)
        ])

        edited = st.data_editor(
            table, hide_index=True, width="stretch", key="de_permissions",
            disabled=[t("perm.col_permission")],
            column_config={
                t("perm.col_permission"): st.column_config.TextColumn(
                    t("perm.col_permission"), width="medium"),
                **{t(f"role.{r}"): st.column_config.CheckboxColumn(t(f"role.{r}"))
                   for r in auth.ROLES},
            },
        )

        col_save, col_reset = st.columns([3, 1])
        with col_save:
            if st.button(t("perm.save"), type="primary", key="perm_save"):
                _save_permissions(edited, current)
        with col_reset:
            if st.button(t("perm.reset"), key="perm_reset", width="stretch"):
                auth.reset_all_permissions()
                audit.record(audit.PERMISSION_CHANGE, target=t("perm.reset_target"))
                st.session_state.pop("de_permissions", None)
                st.rerun()

        st.caption(t("perm.locked_note", names=" · ".join(
            auth.LOCKED_ADMIN_PERMISSIONS)))


def _save_permissions(edited, current: dict):
    """
    يحفظ ما تغيّر وحده — الزوج الذي لم يُلمَس لا يُخزَّن فيبقى تابعاً للافتراض.

    والرفض يُقال صراحةً: زوجٌ محميّ يُردّ بلا صمت، وإلا ظنّ المدير أنه نزع
    صلاحيةً وهي باقية.
    """
    labels = {t(f"role.{r}"): r for r in auth.ROLES}
    changed, refused = 0, []

    for row in edited.to_dict("records"):
        permission = row.get(t("perm.col_permission"))
        if permission not in auth.PERMISSIONS:
            continue
        for label, role in labels.items():
            wanted = bool(row.get(label))
            if wanted == current[permission][role]:
                continue
            if auth.set_permission(permission, role, wanted):
                changed += 1
                audit.record(audit.PERMISSION_CHANGE,
                             target=f"{permission} · {role}",
                             detail="منح" if wanted else "نزع")
            else:
                refused.append(f"{permission} · {t(f'role.{role}')}")

    if refused:
        st.error(t("perm.refused", names=" · ".join(refused)))
    if changed:
        st.success(t("perm.saved", n=changed))
        st.rerun()
    elif not refused:
        st.info(t("perm.nothing_changed"))


def _users_section():
    """
    إدارة المستخدمين (13-2): إضافة · تصفير كلمة · تعطيل · حذف.

    التمييز بين من يملك هذه الشاشة ومن لا يملكها يأتي مع الأدوار في 13-3.
    """
    with st.expander(t("us.title")):
        st.caption(t("us.hint"))

        rows = db.list_users()
        if rows:
            st.dataframe(
                pd.DataFrame([{
                    t("us.col_username"): r["username"],
                    t("us.col_display_name"): r["display_name"],
                    t("us.col_role"): t(f'role.{r["role"]}'),
                    t("us.col_active"): "✅" if r["active"] else "⛔",
                    t("us.col_last_login"): r["last_login"] or t("common.none"),
                } for r in rows]),
                hide_index=True, width="stretch",
            )

        st.markdown(f"**{t('us.add')}**")
        c1, c2 = st.columns(2)
        with c1:
            username = st.text_input(t("au.username"), key="new_user_username")
        with c2:
            display_name = st.text_input(t("au.display_name"),
                                         key="new_user_display_name")
        c3, c4 = st.columns(2)
        with c3:
            password = st.text_input(t("au.password"), type="password",
                                     key="new_user_password")
        with c4:
            # الافتراضي أدنى الأدوار — الحساب الجديد لا يرث صلاحيات من أنشأه
            role = st.selectbox(
                t("us.col_role"), auth.ROLES,
                index=auth.ROLES.index(auth.NEW_USER_ROLE),
                format_func=lambda r: t(f"role.{r}"),
                key="new_user_role", help=t("role.help"),
            )
        st.caption(t(f"role.{role}_hint"))
        if st.button(t("us.add_btn"), type="primary", key="new_user_add"):
            problem = auth.add_user(username, password, display_name, role)
            if problem:
                st.error(t(problem))
            else:
                audit.record(audit.USER_ADD, target=username.strip(), detail=role)
                st.success(t("us.added", username=username.strip()))
                st.rerun()

        if len(rows) <= 1:
            return

        st.divider()
        st.markdown(f"**{t('us.manage')}**")
        labels = {r["id"]: f'{r["username"]} — {r["display_name"] or "—"}' for r in rows}
        target_id = st.selectbox(
            t("us.pick_user"), list(labels),
            format_func=lambda i: labels[i], key="manage_user_pick",
        )
        target = db.get_user_by_id(target_id)
        if target is None:
            return

        role_allowed = auth.can_change_role(target_id)
        new_role = st.selectbox(
            t("us.col_role"), auth.ROLES,
            index=auth.ROLES.index(auth.role_of(target)),
            format_func=lambda r: t(f"role.{r}"),
            key="manage_user_role", disabled=not role_allowed,
        )
        st.caption(t(f"role.{new_role}_hint"))
        if not role_allowed:
            st.caption(t("us.cannot_change_role"))
        elif new_role != target["role"] and st.button(
            t("us.save_role"), key="manage_user_save_role", type="primary"
        ):
            problem = auth.set_role(target_id, new_role)
            if problem:
                st.error(t(problem))
            else:
                audit.record(audit.USER_ROLE, target=target["username"],
                             detail=new_role)
                st.success(t("us.role_saved"))
                st.rerun()

        reset = st.text_input(t("us.reset_password"), type="password",
                              key="manage_user_password",
                              help=t("us.reset_password_help"))
        m1, m2, m3 = st.columns(3)
        with m1:
            if st.button(t("us.reset_btn"), key="manage_user_reset"):
                problem = auth.change_password(target_id, reset)
                if problem:
                    st.error(t(problem))
                else:
                    audit.record(audit.USER_PASSWORD, target=target["username"])
                    st.success(t("us.password_changed"))
        with m2:
            allowed = auth.can_disable(target_id)
            toggle_key = "us.enable_btn" if not target["active"] else "us.disable_btn"
            if st.button(t(toggle_key), key="manage_user_toggle",
                         disabled=target["active"] and not allowed):
                db.set_user_active(target_id, not target["active"])
                audit.record(audit.USER_ACTIVE, target=target["username"],
                             detail="off" if target["active"] else "on")
                st.rerun()
            if target["active"] and not allowed:
                st.caption(t("us.cannot_disable"))
        with m3:
            confirm_delete = st.checkbox(t("us.delete_confirm"),
                                         key="manage_user_delete_confirm")
            if st.button(t("us.delete_btn"), key="manage_user_delete",
                         disabled=not (confirm_delete and auth.can_disable(target_id))):
                audit.record(audit.USER_DELETE, target=target["username"])
                db.delete_user(target_id)
                st.rerun()


def render_settings():

    # 13-3: المفاتيح والنماذج وحدّ الإنفاق لمدير النظام. غير المصرَّح له لا
    # يرى الحقول معطَّلة — لا يراها أصلاً: مفتاح معروض ولو معطَّلاً مفتاح مقروء.
    if auth.can("settings.manage"):
        st.warning(t("st.key_warning"))
        _provider_section()
        _task_models_section()
        _embedding_section()
        _budget_section()
        _connectors_section()
    else:
        st.info(t("role.settings_admin_only"))

    _usage_section()
    if auth.can("prompts.manage"):
        _prompts_section()
    _my_account_section()
    if auth.can("users.manage"):
        _users_section()
        _permissions_section()

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


# ─── الموصّلات الخارجية (14-10) ────────────────────────────────────────────────
#
# **بيانات الاعتماد لمدير النظام وحده** (`settings.manage`)، وهي الشرط الذي
# وُضع عليه هذا القسم هنا لا في ملف الشركة: مفتاح واجهة أوديو وصولٌ إلى نظام
# العميل المحاسبي كلّه، لا إلى منافسة.
#
# ولا تصل النموذج بأي مسار — كمفاتيح الموفّرين تماماً.


def _connectors_section():
    """إعداد الموصّلات واختبار الاتصال. لا سحب هنا — السحب لكل منافسة."""
    from utils import connectors

    with st.expander(t("cn.title"), expanded=False):
        st.caption(t("cn.hint"))
        st.warning(t("cn.egress_warning"))

        name = st.selectbox(
            t("cn.connector"), list(connectors.available()),
            format_func=lambda n: n.capitalize(), key="cn_pick",
        )

        c_url, c_db = st.columns(2)
        with c_url:
            st.text_input(t("cn.url"), key=f"cn_{name}_url",
                          placeholder="https://example.odoo.com")
        with c_db:
            st.text_input(t("cn.db"), key=f"cn_{name}_db")
        c_user, c_key = st.columns(2)
        with c_user:
            st.text_input(t("cn.username"), key=f"cn_{name}_username")
        with c_key:
            st.text_input(t("cn.api_key"), key=f"cn_{name}_api_key",
                          type="password", help=t("cn.api_key_help"))

        if st.button(t("cn.test"), key="cn_test"):
            connector = connectors.build(name, _connector_config(name))
            ok, message = connector.test_connection()
            (st.success if ok else st.error)(message)

        st.caption(t("cn.pull_only"))


def _connector_config(name: str) -> dict:
    """بيانات اعتماد الموصّل من الجلسة — لا تُمرَّر إلى أي طبقة أخرى."""
    return {
        field: str(st.session_state.get(f"cn_{name}_{field}", "") or "").strip()
        for field in ("url", "db", "username", "api_key")
    }


def _render_prompt_trial(key: str, edited: str, sector: str, changed: bool,
                         problem):
    """
    تجربة جنباً إلى جنب على المنافسة المفتوحة (14-3).

    التجربة **لا تحفظ شيئاً**: النص المحرَّر يُمرَّر إلى النموذج مباشرةً، فيُرى
    أثره قبل أن يسري على كل عرض تالٍ.
    """
    from utils import ai_engine

    st.divider()
    st.markdown(f"**{t('pt.title')}**")
    st.caption(t("pt.hint"))

    rfp = st.session_state.get("rfp_raw_text", "")
    if not rfp:
        st.info(t("pt.needs_project"))
        return

    fields = {}
    defaults = ai_engine.trial_field_defaults(key)
    if defaults:
        with st.expander(t("pt.fields", n=len(defaults))):
            st.caption(t("pt.fields_hint"))
            for name, value in defaults.items():
                fields[name] = st.text_area(
                    name, value=value, height=70, key=f"pt_field_{key}_{name}",
                )

    model = _trial_model_picker(key)
    tokens = ai_engine.trial_cost_estimate(key, edited, fields, rfp, sector)
    st.caption(t("pt.cost", tokens=f"{tokens:,}"))

    if st.button(t("pt.run"), key=f"pt_run_{key}", disabled=not changed,
                 help=None if changed else t("pt.no_change")):
        status = st.empty()
        with st.spinner(t("pt.running")):
            result = ai_engine.trial_prompt(
                key, edited, model_choice=model, fields=fields, sector=sector,
                rfp_context=rfp,
                on_progress=lambda side: status.caption(t("pt.side_" + side)),
            )
        status.empty()
        if result["problem"]:
            st.error(t(result["problem"]))
        else:
            st.session_state[f"_pt_result_{key}"] = result
            audit.record(audit.PROMPT_TRIAL, target=key, detail=sector or "all")

    result = st.session_state.get(f"_pt_result_{key}")
    if not result:
        return

    c_current, c_edited = st.columns(2)
    with c_current:
        st.markdown(f"**{t('pt.side_current')}**")
        st.write(result["current"] or t("pt.no_output"))
    with c_edited:
        st.markdown(f"**{t('pt.side_edited')}**")
        st.write(result["edited"] or t("pt.no_output"))
    st.caption(t("pt.decide"))


def _trial_model_picker(key: str) -> str:
    from utils.ai_engine import default_model_name, model_names

    options = model_names()
    current = default_model_name()
    return st.selectbox(
        t("common.engine"), options,
        index=options.index(current) if current in options else 0,
        key=f"pt_model_{key}",
    )


def _prompts_section():
    """
    إدارة البرومبتات (14-1): تحرير تعليمات النموذج بلا إعادة تشغيل.

    الافتراضي يبقى في الشيفرة، والجدول يحمل التجاوزات وحدها — فاستعادة
    الافتراضي حذفُ تجاوز لا نسخُ نصّ.
    """
    from utils import ai_engine

    catalog = ai_engine.editable_prompts()
    with st.expander(t("pm.title")):
        st.caption(t("pm.hint"))

        c_key, c_sector = st.columns([3, 2])
        with c_key:
            key = st.selectbox(
                t("pm.prompt"), sorted(catalog),
                format_func=lambda k: f"{t('pm.agent_' + catalog[k][0])} · {k}",
                key="pm_key",
            )
        with c_sector:
            sector = st.text_input(
                t("pm.sector"), key="pm_sector", placeholder=t("pm.sector_ph"),
                help=t("pm.sector_help"),
            ).strip()

        agent, default_text = catalog[key]
        override = db.prompt_override(key, sector)
        current = (override or {}).get("text") or default_text

        if override:
            st.caption(t("pm.overridden",
                         version=override["version"], who=override["updated_by"] or "—",
                         when=override["updated_at"]))
        else:
            st.caption(t("pm.default_in_use"))

        edited = st.text_area(t("pm.text"), value=current, height=320,
                              key=f"pm_text_{key}_{sector}")

        problem = ai_engine.prompt_problem(key, edited)
        missing = ai_engine.missing_prompt_fields(key, edited)
        if problem:
            st.error(t(problem, fields=" · ".join(
                sorted(ai_engine.prompt_fields(edited)
                       - ai_engine.prompt_fields(default_text)))))
        elif missing:
            # حقل غاب يعني سياقاً لن يصل النموذج — تنبيه لا منع
            st.warning(t("pm.missing_fields", fields=" · ".join(sorted(missing))))

        # 14-3: التجربة قبل الاعتماد — لا يُعتمد نصّ لم يُرَ أثره على عرض حقيقي
        _render_prompt_trial(key, edited, sector, changed=edited.strip() != current.strip(),
                             problem=problem)

        c_save, c_reset = st.columns(2)
        with c_save:
            if st.button(t("pm.save"), type="primary", key="pm_save",
                         disabled=bool(problem) or edited.strip() == current.strip()):
                user = auth.current_user() or {}
                version = db.save_prompt(
                    key, edited, agent=agent, sector=sector,
                    updated_by=user.get("display_name") or user.get("username", ""),
                )
                audit.record(audit.PROMPT_EDIT, target=key,
                             detail=f"{sector or 'all'}:v{version}")
                st.success(t("pm.saved", version=version))
                st.rerun()
        with c_reset:
            if st.button(t("pm.reset"), key="pm_reset", disabled=override is None):
                db.delete_prompt(key, sector)
                audit.record(audit.PROMPT_RESET, target=key, detail=sector or "all")
                st.success(t("pm.reset_done"))
                st.rerun()

        # القواعد الثابتة: تُعرض ولا تُحرَّر (14-2)
        st.divider()
        st.markdown(f"**{t('pm.fixed_rules')}**")
        st.caption(t("pm.fixed_rules_hint"))
        st.code(ai_engine.FIXED_RULES.strip(), language="markdown")

        overrides = db.list_prompts()
        if overrides:
            st.divider()
            st.markdown(f"**{t('pm.overrides', n=len(overrides))}**")
            st.dataframe(
                pd.DataFrame([{
                    t("pm.prompt"): row["key"],
                    t("pm.sector"): row["sector"] or t("pm.all_sectors"),
                    t("pm.version"): row["version"],
                    t("ad2.col_who"): row["updated_by"] or "—",
                    t("ad2.col_when"): row["updated_at"],
                } for row in overrides]),
                hide_index=True, width="stretch",
            )


def _audit_section():
    """
    سجل التدقيق (13-5): من فعل ماذا ومتى، وما مصدره النموذج.

    يُعرض ولا يُحرَّر: لا زر حذف ولا تعديل هنا ولا في طبقة التخزين.
    """
    with st.expander(t("ad2.title")):
        st.caption(t("ad2.hint"))

        projects = {p["id"]: p["name"] for p in db.list_projects()}
        people = {u["id"]: (u["display_name"] or u["username"]) for u in db.list_users()}

        c1, c2 = st.columns(2)
        with c1:
            project_id = st.selectbox(
                t("ad2.filter_project"), [None] + list(projects),
                format_func=lambda i: t("ad2.all") if i is None else projects[i],
                key="audit_project",
            )
        with c2:
            user_id = st.selectbox(
                t("ad2.filter_user"), [None] + list(people),
                format_func=lambda i: t("ad2.all") if i is None else people[i],
                key="audit_user",
            )

        rows = audit.entries(limit=200, project_id=project_id, user_id=user_id)
        if not rows:
            st.info(t("ad2.empty"))
            return

        st.dataframe(
            pd.DataFrame([{
                t("ad2.col_when"): r["created_at"],
                t("ad2.col_who"): r["username"] or t("ad2.unknown_user"),
                t("ad2.col_what"): t("audit.act_" + r["action"]),
                t("ad2.col_target"): r["target"] or r["project_name"] or "—",
                t("ad2.col_source"): t("db.source_" + r["source"])
                if r["source"] in ("ai", "human") else r["source"],
            } for r in rows]),
            hide_index=True, width="stretch",
        )
        st.caption(t("ad2.total", n=db.count_audit_entries()))


def _backup_section():
    """
    نسخة احتياطية كاملة واسترجاعها (13-9).

    النسخة ملف القاعدة كله لا تصدير حقول: تصدير مساحة العمل أعلاه يخدم نقل
    منافسة، وهذه تخدم فقد الجهاز.
    """
    with st.expander(t("bk.title")):
        st.caption(t("bk.hint"))

        crypto = backup.encryption_available()
        if not crypto:
            st.info(t("bk.no_crypto"))

        password = st.text_input(
            t("bk.password"), type="password", key="backup_password",
            help=t("bk.password_help"), disabled=not crypto,
        )
        problem = backup.password_problem(password)
        if problem:
            st.error(t(problem))
        elif st.button(t("bk.build"), type="primary", key="backup_build"):
            data = backup.create(password)
            st.session_state["_backup_bytes"] = data
            st.session_state["_backup_encrypted"] = bool(password)
            audit.record(audit.BACKUP_CREATE,
                         detail="encrypted" if password else "plain")

        blob = st.session_state.get("_backup_bytes")
        if blob:
            suffix = "enc" if st.session_state.get("_backup_encrypted") else "db"
            st.download_button(
                t("bk.download"), data=blob,
                file_name=f"analyst_backup.{suffix}",
                mime="application/octet-stream", key="backup_download",
            )
            st.caption(t("bk.size", kb=len(blob) // 1024))

        st.divider()
        st.markdown(f"**{t('bk.restore')}**")
        st.warning(t("bk.restore_warn"))

        uploaded = st.file_uploader(t("bk.restore_upload"), type=["db", "enc"],
                                    key="backup_upload")
        if not uploaded:
            return

        data = uploaded.getvalue()
        info = backup.summary(data)
        st.caption(t("bk.file_info", kb=info["size_kb"],
                     state=t("bk.encrypted") if info["encrypted"]
                     else t("bk.plain")))

        restore_password = st.text_input(
            t("bk.restore_password"), type="password", key="restore_password",
            disabled=not info["encrypted"],
        )
        confirm = st.checkbox(t("bk.restore_confirm"), key="restore_confirm")
        if st.button(t("bk.restore_btn"), type="primary", key="restore_btn",
                     disabled=not confirm):
            failure = backup.restore(data, restore_password)
            if failure:
                st.error(t(failure))
            else:
                audit.record(audit.BACKUP_RESTORE, detail=str(info["size_kb"]))
                # الحالة كلها صارت من قاعدة أخرى — الجلسة تُمسح ويُعاد الدخول
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.success(t("bk.restored"))
                st.rerun()


def render_data():

    if auth.can("audit.view"):
        _audit_section()

    # 13-3: استيراد مساحة عمل أو مسحها يمسّ كل شيء دفعةً واحدة — لا يُترك لكل
    # من يكتب قسماً. التصدير في الحزمة نفسها: نسخة كاملة تخرج من النظام.
    if not auth.can("data.manage"):
        st.info(t("role.data_manager_only"))
        return

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

    _backup_section()

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
