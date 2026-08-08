"""
utils/connectors/ — الموصّلات إلى الأنظمة الخارجية (14-10).

**سحب فقط في هذه الدفعة.** الدفع (تحويل المنافسة الفائزة إلى أمر بيع) قرار
يكتب في نظام العميل المحاسبي، وتُرك عمداً لدفعة تُتّخذ فيها الموافقة صراحةً —
والطبقة هنا **لا تحمل مساراً له** حتى لا يُستدرَج إليه بتوفّر خانة فارغة.

الطبقة مجرّدة عن أوديو: `Connector` في `base.py` هي العقد، و `odoo.py` أول
تحقيق له. موصّل ثانٍ لا يمسّ شيئاً خارج مجلده.

**التفعيل لكل منافسة على حدة** (`enabled_for`) — لا مفتاح عامّ: قناة مفتوحة
دائماً تُخرج بيانات منافسة لم يقصد أحد ربطها.
"""
from utils.connectors.base import (
    PERSONAL_RESOURCES,
    RESOURCES,
    RESOURCE_CUSTOMERS,
    RESOURCE_EMPLOYEES,
    RESOURCE_PRODUCTS,
    Connector,
    ConnectorError,
)

# تُصدَّر للمستوردين — `pyflakes` لا يعرف `# noqa`, و `__all__` تُعلن أنّها
# إعادة تصدير مقصودة لا استيراد منسيّ.
__all__ = [
    "PERSONAL_RESOURCES", "RESOURCES", "RESOURCE_CUSTOMERS",
    "RESOURCE_EMPLOYEES", "RESOURCE_PRODUCTS", "Connector", "ConnectorError",
    "RESOURCE_REGISTRY", "available", "build", "enabled_for", "set_enabled",
]

# المورد ← السجلّ الذي تدخله صفوفه (المرحلة 12)
RESOURCE_REGISTRY = {
    RESOURCE_CUSTOMERS: "entities",
    RESOURCE_PRODUCTS: "vendors",
    RESOURCE_EMPLOYEES: "people",
}

# مفتاح تفعيل القناة لمنافسة بعينها، في `app_settings`
_ENABLED_PREFIX = "connector_enabled_"


def available() -> dict:
    """اسم الموصّل ← صانعه. إضافة موصّل سطرٌ هنا وملفٌّ في المجلد."""
    from utils.connectors import odoo

    return {odoo.OdooConnector.name: odoo.build}


def build(name: str, config=None):
    """يبني موصّلاً باسمه، أو `None` لاسم لا نعرفه."""
    factory = available().get(str(name or "").strip())
    return factory(config) if factory else None


def enabled_for(name: str, project_id) -> bool:
    """
    هل القناة مفعّلة **لهذه المنافسة**؟

    الافتراض **لا**: قناة مفتوحة بلا قرار تُخرج بيانات منافسة لم يقصد أحد
    ربطها بنظام خارجي، وأول من يعلم بذلك قد يكون مالك البيانات.
    """
    from utils import db

    if project_id is None:
        return False
    return db.app_setting(f"{_ENABLED_PREFIX}{name}_{int(project_id)}", "") == "1"


def set_enabled(name: str, project_id, enabled: bool):
    from utils import db

    if project_id is None:
        return
    db.set_app_setting(f"{_ENABLED_PREFIX}{name}_{int(project_id)}",
                       "1" if enabled else "0")
