"""
pages/settings.py — System Settings: API Keys + Data Management
"""
import json
import os

import streamlit as st

from utils.state import get_state_snapshot, load_state_snapshot
from utils.ai_engine import (
    DEFAULT_LANGUAGE,
    DEFAULT_MODEL,
    LANGUAGES,
    MODEL_NAMES,
    resolve_model,
)


def render_settings():
    st.markdown("### ⚙️ إعدادات الذكاء الاصطناعي")

    with st.expander("🔑 مفاتيح API", expanded=True):
        st.markdown("""
        <div style="background:#FEF3C7;padding:12px 16px;border-radius:8px;margin-bottom:12px;
                    font-family:Tajawal,sans-serif;font-size:14px;color:#92400E;">
        ⚠️ <strong>تنبيه أمني:</strong> مفاتيح API محفوظة في الذاكرة المؤقتة فقط وتُمسح عند إغلاق المتصفح.
        لا تُشارك session_state مع أي جهة.
        </div>
        """, unsafe_allow_html=True)

        if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
            st.info(
                "🔐 يوجد مفتاح في متغيّرات البيئة (Replit Secrets مثلاً) وقد "
                "حُمِّل تلقائياً. ما تكتبه هنا يَجُبّه لهذه الجلسة فقط."
            )

        st.session_state["api_gemini"] = st.text_input(
            "🔑 Google Gemini API Key",
            value=st.session_state.get("api_gemini", ""),
            type="password",
            placeholder="AIza...",
            help="احصل على مفتاحك من: https://aistudio.google.com/app/apikey",
        )

        c1, c2 = st.columns(2)
        with c1:
            st.session_state["api_openai"] = st.text_input(
                "🔑 OpenAI API Key (قريباً)",
                value=st.session_state.get("api_openai", ""),
                type="password",
                placeholder="sk-...",
                disabled=True,
            )
        with c2:
            st.session_state["api_claude"] = st.text_input(
                "🔑 Claude API Key (قريباً)",
                value=st.session_state.get("api_claude", ""),
                type="password",
                placeholder="sk-ant-...",
                disabled=True,
            )

        # Connectivity Check
        if st.button("✅ اختبار اتصال Gemini", type="primary"):
            if not st.session_state.get("api_gemini"):
                st.error("أدخل المفتاح أولاً.")
            else:
                with st.spinner("جاري الاختبار..."):
                    try:
                        from google import genai
                        client = genai.Client(api_key=st.session_state["api_gemini"])
                        response = client.models.generate_content(
                            model=resolve_model(DEFAULT_MODEL),
                            contents="قل 'الاتصال يعمل' فقط.",
                        )
                        st.success(f"✅ الاتصال يعمل! رد النموذج: {response.text.strip()[:80]}")
                    except Exception as e:
                        st.error(f"❌ فشل الاتصال: {e}")

    with st.expander("🤖 تفضيلات النموذج الافتراضي"):
        current = st.session_state.get("ai_model_preference", DEFAULT_MODEL)
        st.session_state["ai_model_preference"] = st.radio(
            "النموذج الافتراضي:",
            MODEL_NAMES,
            index=MODEL_NAMES.index(current) if current in MODEL_NAMES else 0,
            key="model_pref_radio",
            help="Flash: متوازن وسريع. Pro: أدق للمهام المعقدة. Flash-Lite: الأرخص للمهام البسيطة.",
        )

    with st.expander("🌐 لغة المخرجات", expanded=False):
        st.caption(
            "تتحكم بلغة كل ما يولّده النظام: التحليلات وأقسام العرض والمراجعة، "
            "واتجاه الكتابة في ملفي Word و PDF."
        )
        codes = list(LANGUAGES)
        current_lang = st.session_state.get("output_language", DEFAULT_LANGUAGE)
        st.session_state["output_language"] = st.radio(
            "اللغة:",
            codes,
            index=codes.index(current_lang) if current_lang in codes else 0,
            format_func=lambda c: LANGUAGES[c]["label"],
            key="output_language_radio",
        )


def render_data():
    st.markdown("### 💾 إدارة البيانات والنسخ الاحتياطي")

    with st.expander("📤 تصدير مساحة العمل", expanded=True):
        st.markdown("احفظ العمل الحالي كملف JSON لاستئنافه لاحقاً.")

        snapshot = get_state_snapshot()
        # Remove API keys from export for security
        export_data = {k: v for k, v in snapshot.items() if "api_" not in k}

        json_str = json.dumps(export_data, ensure_ascii=False, indent=2)
        st.download_button(
            "⬇️ تحميل ملف مساحة العمل (.json)",
            data=json_str.encode("utf-8"),
            file_name="imdad_workspace.json",
            mime="application/json",
        )
        st.caption(f"حجم البيانات: {len(json_str) // 1024} KB · يشمل النصوص والجداول · لا يشمل مفاتيح API أو ملفات الشركة.")

    with st.expander("📥 استيراد مساحة عمل محفوظة"):
        uploaded_json = st.file_uploader("ارفع ملف workspace .json", type=["json"], key="workspace_import")
        if uploaded_json:
            try:
                data = json.loads(uploaded_json.getvalue().decode("utf-8"))
                if st.button("📥 تحميل البيانات في مساحة العمل", type="primary"):
                    load_state_snapshot(data)
                    st.success("✅ تم استيراد مساحة العمل بنجاح!")
                    st.rerun()
            except Exception as e:
                st.error(f"❌ فشل قراءة الملف: {e}")

    with st.expander("🗑️ مسح البيانات"):
        st.warning("⚠️ هذه العمليات لا يمكن التراجع عنها.")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🗑️ مسح تحليل الكراسة فقط", width="stretch"):
                from utils.state import reset_analysis
                reset_analysis()
                st.success("تم مسح بيانات التحليل.")
                st.rerun()
        with c2:
            confirm = st.checkbox("تأكيد مسح كل شيء")
            if st.button("🗑️ مسح جميع البيانات", width="stretch", disabled=not confirm):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
