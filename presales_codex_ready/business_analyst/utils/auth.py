"""
utils/auth.py — الهوية والمصادقة (13-2)

طبقة واحدة بين الشاشات وجدول `users`. كل ما يمسّ كلمة السر يمر من هنا، فلا
تعرف بقية الشيفرة كيف تُخزَّن ولا كيف تُتحقَّق.

**التجزئة**: `scrypt` من المكتبة القياسية — اشتقاق بطيء مقصود يجعل تخمين
الكلمات مكلفاً حتى لو تسرّب ملف القاعدة. لكل كلمة ملحها العشوائي، فكلمتان
متطابقتان لا تعطيان التجزئة نفسها. المقارنة بزمن ثابت
(`hmac.compare_digest`) حتى لا يُسرّب طول التطابق شيئاً.
تُقبل صيغة `pbkdf2` القديمة عند التحقق للتوافق مع قاعدة أُنشئت بها.

**لا وصول قبل الدخول**: `is_authenticated` هي الحارس الوحيد، ويستدعيها
`app.py` قبل رسم أي شاشة. تتحقق في كل دورة من أن المستخدم لا يزال موجوداً
وفعّالاً — فتعطيل حساب يُخرج صاحبه من جلسته القائمة بلا انتظار.

**الأدوار**: العمود يُخزَّن هنا ويُفرَض في 13-3. لا شاشة تسأل عن الدور بعد.

Authentication layer: scrypt password hashing, session guard, first-run setup.
"""
import hashlib
import hmac
import os
import time
from typing import Optional

import streamlit as st

from utils import db

# معاملات scrypt — تكلفة تُحسّ بها آلة التخمين ولا يُحسّ بها المستخدم.
_SCRYPT_N = 2 ** 14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SALT_BYTES = 16
_KEY_BYTES = 32

# أقصر كلمة مقبولة. أقصر من ذلك يُخمَّن مهما قويت التجزئة.
MIN_PASSWORD_LENGTH = 8

# الدور الافتراضي حتى تصل الأدوار الخمسة في 13-3
DEFAULT_ROLE = "admin"

# حدّ محاولات الدخول الفاشلة قبل تهدئة إجبارية — يوقف التخمين الآلي بلا أن
# يقفل حساباً فعلياً (القفل الدائم سلاح بيد المهاجم ضد صاحب الحساب).
MAX_FAILED_ATTEMPTS = 5
COOLDOWN_SECONDS = 60

_SESSION_KEY = "auth_user_id"
_FAILED_KEY = "auth_failed_attempts"
_COOLDOWN_KEY = "auth_cooldown_until"


# ─── كلمة السر ────────────────────────────────────────────────────────────────


def hash_password(password: str) -> str:
    """`scrypt$n$r$p$salt$hash` — كل ما يلزم للتحقق لاحقاً في نص واحد."""
    salt = os.urandom(_SALT_BYTES)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt,
        n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_KEY_BYTES,
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """يتحقق بلا كشف طول التطابق، ويعيد `False` لأي تجزئة تالفة أو مجهولة."""
    try:
        parts = (stored or "").split("$")
        algorithm = parts[0]
        if algorithm == "scrypt":
            _, n, r, p, salt_hex, digest_hex = parts
            expected = bytes.fromhex(digest_hex)
            actual = hashlib.scrypt(
                password.encode("utf-8"), salt=bytes.fromhex(salt_hex),
                n=int(n), r=int(r), p=int(p), dklen=len(expected),
            )
        elif algorithm == "pbkdf2":
            _, iterations, salt_hex, digest_hex = parts
            expected = bytes.fromhex(digest_hex)
            actual = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"),
                bytes.fromhex(salt_hex), int(iterations), dklen=len(expected),
            )
        else:
            return False
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def password_problem(password: str, confirm: Optional[str] = None) -> Optional[str]:
    """يعيد مفتاح i18n لأول عيب في الكلمة، أو `None` إن كانت مقبولة."""
    if len(password or "") < MIN_PASSWORD_LENGTH:
        return "au.err_password_short"
    if confirm is not None and password != confirm:
        return "au.err_password_mismatch"
    return None


def username_problem(username: str) -> Optional[str]:
    if not (username or "").strip():
        return "au.err_username_required"
    return None


# ─── الجلسة ───────────────────────────────────────────────────────────────────


def current_user() -> Optional[dict]:
    """
    المستخدم الحالي من القاعدة لا من الجلسة — الجلسة تحمل المعرّف فقط.

    فالاسم والدور وحالة التفعيل تُقرأ طازجة في كل دورة، فلا يبقى مستخدم
    عُطِّل أو تغيّر دوره يعمل بصلاحياته القديمة حتى ينتهي متصفحه.
    """
    user_id = st.session_state.get(_SESSION_KEY)
    if not user_id:
        return None
    user = db.get_user_by_id(user_id)
    if user is None or not user.get("active"):
        st.session_state.pop(_SESSION_KEY, None)
        return None
    user.pop("password_hash", None)
    return user


def is_authenticated() -> bool:
    return current_user() is not None


def needs_setup() -> bool:
    """قاعدة بلا مستخدم فعّال: أول زائر يُنشئ حساب مدير النظام."""
    return db.count_users(active_only=True) == 0


def cooldown_remaining() -> int:
    """الثواني الباقية من التهدئة بعد محاولات فاشلة متتالية."""
    until = st.session_state.get(_COOLDOWN_KEY, 0)
    return max(0, int(until - time.time()))


def _register_failure():
    attempts = int(st.session_state.get(_FAILED_KEY, 0)) + 1
    st.session_state[_FAILED_KEY] = attempts
    if attempts >= MAX_FAILED_ATTEMPTS:
        st.session_state[_COOLDOWN_KEY] = time.time() + COOLDOWN_SECONDS
        st.session_state[_FAILED_KEY] = 0


def login(username: str, password: str) -> Optional[str]:
    """
    يفتح جلسة عند نجاح الدخول ويعيد `None`، أو مفتاح i18n لسبب الرفض.

    سبب الرفض واحد لاسم مجهول ولكلمة خاطئة — التفريق بينهما يكشف أي الأسماء
    مسجَّل. والتجزئة تُحسب حتى لاسم غير موجود كي لا يفضح زمنُ الرد ذلك.
    """
    if cooldown_remaining() > 0:
        return "au.err_cooldown"

    user = db.get_user((username or "").strip())
    stored = user["password_hash"] if user else hash_password("no-such-user")
    ok = verify_password(password or "", stored)

    if not user or not ok:
        _register_failure()
        return "au.err_bad_credentials"
    if not user.get("active"):
        _register_failure()
        return "au.err_disabled"

    start_session(user["id"])
    return None


def start_session(user_id: int):
    """يبدأ جلسة مستخدم — يستعملها الدخول وإنشاء أول حساب."""
    st.session_state[_SESSION_KEY] = user_id
    st.session_state[_FAILED_KEY] = 0
    st.session_state.pop(_COOLDOWN_KEY, None)
    db.touch_user_login(user_id)


def logout():
    """
    يُنهي الجلسة ويمسح حالتها كاملة.

    مسح المفتاح وحده يترك تحليل المستخدم السابق وأقسامه في الذاكرة، فيراها من
    يدخل بعده على الجهاز نفسه.
    """
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def create_first_admin(username: str, password: str, display_name: str = "") -> Optional[str]:
    """
    ينشئ أول حساب ويدخل به. يعيد مفتاح i18n عند الرفض و `None` عند النجاح.

    مسموح فقط ما دامت القاعدة بلا مستخدم فعّال — وإلا صار بوابة خلفية تلتفّ
    على الدخول.
    """
    if not needs_setup():
        return "au.err_setup_done"
    problem = username_problem(username) or password_problem(password)
    if problem:
        return problem

    user_id = db.create_user(
        username, hash_password(password), display_name, role=DEFAULT_ROLE
    )
    if user_id is None:
        # اسم موجود لكنه معطَّل — لا يُعاد تفعيله من شاشة التهيئة
        return "au.err_username_taken"
    start_session(user_id)
    return None


# ─── إدارة المستخدمين ─────────────────────────────────────────────────────────


def add_user(username: str, password: str, display_name: str = "",
             role: str = DEFAULT_ROLE) -> Optional[str]:
    """يضيف مستخدماً. يعيد مفتاح i18n عند الرفض و `None` عند النجاح."""
    problem = username_problem(username) or password_problem(password)
    if problem:
        return problem
    if db.create_user(username, hash_password(password), display_name, role) is None:
        return "au.err_username_taken"
    return None


def change_password(user_id: int, new_password: str,
                    confirm: Optional[str] = None,
                    current_password: Optional[str] = None) -> Optional[str]:
    """
    يغيّر كلمة السر. عند تمرير `current_password` تُتحقَّق أولاً — المستخدم
    يغيّر كلمته بمعرفة القديمة، ومدير النظام يُصفّرها بلا معرفتها.
    """
    user = db.get_user_by_id(user_id)
    if user is None:
        return "au.err_user_missing"
    if current_password is not None and not verify_password(
        current_password, user["password_hash"]
    ):
        return "au.err_current_password"
    problem = password_problem(new_password, confirm)
    if problem:
        return problem
    db.set_user_password(user_id, hash_password(new_password))
    return None


def can_disable(user_id: int) -> bool:
    """
    تعطيل آخر حساب فعّال يقفل النظام على الجميع بلا سبيل للدخول — يُمنع.
    وكذلك لا يُعطّل المستخدم نفسه، فهو خروج بلا رجعة بلا قصد.
    """
    user = current_user()
    if user and user["id"] == user_id:
        return False
    return db.count_users(active_only=True) > 1
