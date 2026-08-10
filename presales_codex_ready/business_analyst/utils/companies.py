"""
utils/companies.py — الشركة الفاعلة لكل مستخدم (ب-7)

13-1 جعل القاعدة تحتمل أكثر من شركة، وبقي الاختيار **متغيّراً عاماً في وحدة
`db`**. وخادم Streamlit واحد يخدم كل الجلسات، فمستخدمان يعملان على شركتين
يتنازعان قيمةً واحدة: يبدّلها أحدهما فتنقلب تحت يد الآخر، ويخرج اسم شركةٍ
أخرى على غلاف عرضه بلا أن يلاحظ. هذه الوحدة تُنهي ذلك.

**ثلاث طبقات للاختيار**، من الأخصّ إلى الأعمّ:

1. **الجلسة** — ما اختاره هذا المستخدم في هذه الجلسة.
2. **حساب المستخدم** (`users.company_id`) — اختياره الأخير، فيجده كما تركه.
3. **أقدم شركة** — قاعدة بشركة واحدة تتصرّف تماماً كما كانت قبل 13-1.

**ما يُبدَّل وما لا يُبدَّل**: التبديل يغيّر **ملف الشركة** (البيانات النظامية
والقالب والشعار) لا المنافسات ولا مستودع المعرفة ولا سجلات الأدلة — تلك لم
تُقيَّد بشركة بعد. الواجهة تقول ذلك صراحةً: مستخدمٌ يظنّ أنه بدّل كل شيء يُرفق
شهادات شركةٍ بعرض شركةٍ أخرى.
"""
from typing import Optional

import streamlit as st

from utils import db

# مفتاح الجلسة. يُمسح عند الخروج مع بقية حالة الجلسة.
_SESSION_KEY = "_active_company_id"


def install():
    """
    يركّب مُحلِّل الجلسة في `db`.

    يُستدعى مرة في `app.py`. و`db` تبقى بلا معرفة بالجلسات: تسأل، ولا تعرف من
    يجيب — فتعمل في السكربتات والاختبارات بلا Streamlit كما كانت.
    """
    db.set_company_resolver(_resolve)


def _resolve() -> Optional[int]:
    """الجلسة أولاً ثم حساب المستخدم. `None` تعني «اتبع الافتراض»."""
    chosen = st.session_state.get(_SESSION_KEY)
    if isinstance(chosen, int) and db.company_exists(chosen):
        return chosen

    stored = _stored_choice()
    if stored is not None:
        # نثبّتها في الجلسة فلا تُقرأ القاعدة في كل استدعاء
        st.session_state[_SESSION_KEY] = stored
    return stored


def _stored_choice() -> Optional[int]:
    from utils import auth

    user = auth.current_user()
    if not user:
        return None
    company_id = user.get("company_id")
    if isinstance(company_id, int) and db.company_exists(company_id):
        return company_id
    return None


def active_id() -> Optional[int]:
    return db.active_company_id()


def active_name() -> str:
    current = active_id()
    for row in db.list_companies():
        if row["id"] == current:
            return row["name"] or ""
    return ""


def switch(company_id: int) -> bool:
    """
    ينقل المستخدم إلى شركة أخرى: جلسته وحده، وحسابه لدخوله التالي.

    ويعيد `False` لشركة غير موجودة بدل أن يترك الجلسة على معرّف ميت — تُقرأ
    منه لاحقاً بيانات فارغة فيُظنّ الملف ضائعاً.

    **لا يُحمّل الملف الجديد هنا**: التحميل مسّ لحالة الجلسة تملكه
    `views/company.py` بعد استدعاء هذه الدالة. الفصل مقصود — وحدة القرار لا
    تكتب اثني عشر مفتاحاً في الجلسة.
    """
    from utils import auth

    if not db.company_exists(company_id):
        return False

    st.session_state[_SESSION_KEY] = company_id
    user = auth.current_user()
    if user:
        db.set_user_company(user["id"], company_id)
    return True


def forget(company_id: int):
    """
    ينسى شركة حُذفت: من الجلسة ومن كل حساب اختارها.

    بلا هذا يبقى معرّف ميت في حسابٍ آخر، فيرى صاحبه عند دخوله ملفاً فارغاً
    بلا تفسير — وقد يملأه من جديد فوق شركةٍ أخرى.
    """
    if st.session_state.get(_SESSION_KEY) == company_id:
        st.session_state.pop(_SESSION_KEY, None)
    for user in db.list_users():
        if user.get("company_id") == company_id:
            db.set_user_company(user["id"], None)


def load_into_session():
    """
    يحمّل ملف الشركة الفاعلة إلى الجلسة: البيانات النظامية وقالب Word.

    ويمسح مفاتيح الملف السابق أولاً — **الحقل الذي تملؤه الشركة الجديدة يُكتب،
    والذي تتركه فارغاً يجب أن يُمحى لا أن يبقى من سابقتها**. بلا المسح يخرج
    رقم سجل تجاري لشركة على غلاف عرضٍ لشركة أخرى.
    """
    from utils.state import COMPANY_KEYS, load_company_snapshot

    payload, template, _logo = db.load_company()

    for key in COMPANY_KEYS:
        st.session_state[key] = ""
    st.session_state.pop("c_word_template_bytes", None)

    if payload:
        load_company_snapshot(payload)
    if template:
        st.session_state["c_word_template_bytes"] = template

    st.session_state["_company_loaded"] = True
