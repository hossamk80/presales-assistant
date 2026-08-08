"""
utils/connectors/base.py — الطبقة المجرّدة للموصّلات الخارجية (14-10).

كل ما سبق في هذا النظام مغلق داخله: القاعدة على القرص، والنموذج خلف طبقة
موفّرين نتحكّم بها. الموصّل أول شيء **يفتح قناة إلى خادم لا نملكه** — فقواعده
ليست تفصيلاً تقنياً بل حدود ما يغادر جهاز العميل.

**سحب فقط. لا دفع.**

القرار مقصود ومكتوب في الشيفرة لا في وثيقة: `Connector` **لا تحمل دالّة دفع
أصلاً**. جذعٌ يرفع `NotImplementedError` دعوةٌ لملئه لاحقاً بلا إعادة اتّخاذ
القرار — والدفع يكتب في نظام العميل المحاسبي، وهو قرار يُتّخذ مرة بوعي لا
يُستدرَج إليه بتوفّر خانة فارغة.

**وما يخرج يُعلَن قبل خروجه**: `egress_notice` تصف ما يغادر فعلاً، وتُعرض قبل
كل عملية سحب — لا في صفحة إعدادات يقرؤها المستخدم مرة وينساها.
"""
from typing import Optional

# الموارد التي يجوز سحبها. القائمة **مغلقة**: مورد لا يعرفه النظام يُرفض بدل أن
# يُمرَّر إلى الخادم كما هو — والقائمة المفتوحة تصير قناة استعلام حرّة.
RESOURCE_CUSTOMERS = "customers"
RESOURCE_PRODUCTS = "products"
RESOURCE_EMPLOYEES = "employees"
RESOURCES = (RESOURCE_CUSTOMERS, RESOURCE_PRODUCTS, RESOURCE_EMPLOYEES)

# الموارد التي تحمل **بيانات أشخاص**: سحبها يُدخل النظام في نطاق سياسة البيانات
# الشخصية (13-10)، فلكل شخص أساس معالجة معلَن ومدة احتفاظ وحقّ حذف.
PERSONAL_RESOURCES = (RESOURCE_EMPLOYEES,)


class ConnectorError(Exception):
    """فشل في الاتصال أو في استجابة الخادم — يُعرض ولا يُبتلع."""


class Connector:
    """
    واجهة الموصّل. **سحب فقط** — لا دالّة دفع هنا ولا في ورثتها.

    الوارث يملأ `name` و `label` و `configure` و `test_connection` و `_fetch`.
    """

    name = ""
    label = ""

    def __init__(self, config: Optional[dict] = None):
        self.config = dict(config or {})

    # ── ما يُعلَن قبل الخروج ──────────────────────────────────────────────────
    def endpoint(self) -> str:
        """المضيف الذي ستغادر إليه البيانات — يُعرض للمستخدم حرفياً."""
        return str(self.config.get("url", "") or "").strip()

    def egress_notice(self, resource: str) -> dict:
        """
        وصف ما يغادر الجهاز في هذه العملية.

        يُعرض **قبل كل سحب** لا في إعدادات تُقرأ مرة وتُنسى: القناة تُفتح لكل
        منافسة على حدة، والمستخدم يرى وجهة بياناته وقت اتّخاذ القرار.
        """
        return {
            "endpoint": self.endpoint(),
            "resource": resource,
            "personal": resource in PERSONAL_RESOURCES,
            "direction": "pull",
        }

    # ── العقد ─────────────────────────────────────────────────────────────────
    def configured(self) -> bool:
        raise NotImplementedError

    def test_connection(self) -> tuple:
        """`(نجح, رسالة)` — تُجرَّب قبل أول سحب فلا يُكتشف الخطأ وسط العمل."""
        raise NotImplementedError

    def _fetch(self, resource: str, limit: int) -> list:
        raise NotImplementedError

    def fetch(self, resource: str, limit: int = 200) -> list:
        """
        يسحب مورداً ويعيد صفوفاً مطبَّعة.

        المورد يُفحَص **قبل** مغادرة أي طلب: اسم لا نعرفه لا يُمرَّر إلى الخادم.
        والفشل يرفع `ConnectorError` ولا يعيد قائمة فارغة — «لا نتائج» و«تعذّر
        الاتصال» حالتان مختلفتان، وخلطهما يجعل جدولاً فارغاً يبدو حقيقةً مقيسة.
        """
        if resource not in RESOURCES:
            raise ConnectorError(f"مورد غير معروف: {resource}")
        if not self.configured():
            raise ConnectorError("الموصّل غير مُعدّ")
        return self._fetch(resource, max(1, int(limit)))
