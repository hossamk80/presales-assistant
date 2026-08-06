"""
utils/backup.py — النسخ الاحتياطي والاسترجاع والتشفير (13-9)

النسخة **ملف القاعدة كاملاً**: المنافسات وملف الشركة ومستودع المعرفة
والمستخدمون والسجل والاعتمادات. لا انتقاء حقول — نسخة ناقصة تُكتشف يوم
الحاجة إليها لا قبله.

**قرار التشفير**: القاعدة على القرص تبقى SQLite عادياً، و**النسخة المصدَّرة**
هي ما يُشفَّر بكلمة من المستخدم. البديل (`SQLCipher`) يشفّر الملف نفسه لكنه
تبعية ثنائية تُبنى لكل منصة، وتُسقط قابلية فتح القاعدة بأي أداة SQLite —
والنسخة هي ما يغادر الجهاز فعلاً (بريد · قرص · تخزين سحابي)، فهي موضع الخطر.

الاشتقاق `scrypt` من المكتبة القياسية (كما في `auth`)، والتعمية `Fernet` من
`cryptography` — تحمل توقيعاً، فالنسخة المعبوث بها تُرفض لا تُفكّ إلى قمامة.
التشفير **اختياري عند التشغيل**: تركيب بلا `cryptography` ينسخ ويسترجع بلا
تشفير ويقول ذلك، ولا يسقط.

Full-database backup, restore, and optional password encryption.
"""
import base64
import hashlib
import os
from typing import Optional

from utils import db

# ترويسة النسخة المشفَّرة — تميّزها عن ملف SQLite الخام بلا تخمين
MAGIC = b"ANALYSTBK1\n"
_SALT_BYTES = 16
_SCRYPT_N = 2 ** 14
_SCRYPT_R = 8
_SCRYPT_P = 1

MIN_PASSWORD_LENGTH = 8


def encryption_available() -> bool:
    """هل مكتبة التعمية مركَّبة؟ الواجهة تسأل قبل أن تعرض حقل الكلمة."""
    import importlib.util

    try:
        return importlib.util.find_spec("cryptography.fernet") is not None
    except Exception:
        return False


def _key(password: str, salt: bytes) -> bytes:
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt,
        n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32,
    )
    return base64.urlsafe_b64encode(digest)


def is_encrypted(data: bytes) -> bool:
    return bool(data) and data.startswith(MAGIC)


def create(password: str = "") -> bytes:
    """
    نسخة احتياطية كاملة. بكلمة تُشفَّر، وبلا كلمة تخرج ملف SQLite كما هو.

    الملف الخام مقصود لا إهمال: نسخة يفتحها أي عميل SQLite تُثبت أن البيانات
    ليست رهينة هذا البرنامج.
    """
    data = db.snapshot_bytes()
    if not password:
        return data

    from cryptography.fernet import Fernet

    salt = os.urandom(_SALT_BYTES)
    token = Fernet(_key(password, salt)).encrypt(data)
    return MAGIC + salt + token


def password_problem(password: str) -> Optional[str]:
    """يعيد مفتاح i18n إن كانت كلمة النسخة ضعيفة."""
    if password and len(password) < MIN_PASSWORD_LENGTH:
        return "bk.err_password_short"
    if password and not encryption_available():
        return "bk.err_no_crypto"
    return None


def read(data: bytes, password: str = ""):
    """
    يفكّ النسخة إن كانت مشفَّرة ويعيد بايتات القاعدة، أو مفتاح i18n عند الفشل.

    يعيد `(bytes, None)` عند النجاح و `(None, "مفتاح الخطأ")` عند الفشل — كلمة
    خاطئة ونسخة تالفة يُفرَّق بينهما، فالمستخدم يعرف أيهما يصلح.
    """
    if not data:
        return None, "bk.err_empty"

    if not is_encrypted(data):
        return (data, None) if db.validate_snapshot(data) else (None, "bk.err_not_backup")

    if not password:
        return None, "bk.err_password_needed"
    if not encryption_available():
        return None, "bk.err_no_crypto"

    from cryptography.fernet import Fernet, InvalidToken

    salt = data[len(MAGIC):len(MAGIC) + _SALT_BYTES]
    token = data[len(MAGIC) + _SALT_BYTES:]
    try:
        plain = Fernet(_key(password, salt)).decrypt(token)
    except (InvalidToken, ValueError):
        # التوقيع يفرّق بين كلمة خاطئة ونسخة عُبث بها — كلاهما يُرفض هنا
        return None, "bk.err_bad_password"

    return (plain, None) if db.validate_snapshot(plain) else (None, "bk.err_not_backup")


def restore(data: bytes, password: str = "") -> Optional[str]:
    """
    يستبدل القاعدة بالنسخة. يعيد `None` عند النجاح ومفتاح i18n عند الفشل.

    الفحص كله قبل أي كتابة: نسخة تُرفض لا تترك القاعدة القائمة ناقصة.
    """
    plain, problem = read(data, password)
    if problem:
        return problem
    return None if db.restore_bytes(plain) else "bk.err_not_backup"


def summary(data: bytes) -> dict:
    """وصف موجز للنسخة قبل استرجاعها — الحجم وهل هي مشفَّرة."""
    return {"size_kb": len(data or b"") // 1024, "encrypted": is_encrypted(data)}
