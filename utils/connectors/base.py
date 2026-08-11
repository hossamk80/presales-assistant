"""
utils/connectors/base.py — الطبقة المجرّدة للموصّلات الخارجية (14-10).

كل ما سبق في هذا النظام مغلق داخله: القاعدة على القرص، والنموذج خلف طبقة
موفّرين نتحكّم بها. الموصّل أول شيء **يفتح قناة إلى خادم لا نملكه** — فقواعده
ليست تفصيلاً تقنياً بل حدود ما يغادر جهاز العميل.

**السحب مفتوح، والدفع مغلق حتى يُفتح صراحةً** (ب-6).

كان القرار في 14-10 «سحب فقط، ولا دالّة دفع أصلاً» حتى تُتّخذ الموافقة بوعي.
اتُّخذت، فصار الدفع موجوداً — **ولم يصر مفتوحاً**:

- `supports_push = False` هو الافتراض. موصّلٌ لا يعلنها لا يدفع، فإضافة موصّل
  جديد لا تفتح قناة كتابة إلى نظام العميل سهواً.
- `push_order` وحدها مسار الكتابة، وحمولتها **تُبنى في `utils/orders.py`**
  ببواباتها الخمس: الفائزة وحدها · بلا كمية غير معتمدة · بلا سعر · مسودّة ·
  مرة واحدة. الموصّل يُرسل ما وصله ولا يجمعه بنفسه.
- لا مسار حذف ولا تعديل. نكتب مسودّة واحدة، وما بعدها عملُ من يملك النظام.

**وما يخرج يُعلَن قبل خروجه**: `egress_notice` تصف ما يغادر فعلاً، وتُعرض قبل
كل عملية — لا في صفحة إعدادات يقرؤها المستخدم مرة وينساها. والدفع يُعلَن أشدّ:
السحب يقرأ، والدفع **يترك أثراً في دفاتر غيرنا**.
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

# اتجاه العملية. الدفع مورد مستقل لا صنفٌ من موارد السحب: لا يُختار من القائمة
# نفسها فلا يُضغط سهواً مكان «العملاء».
DIRECTION_PULL = "pull"
DIRECTION_PUSH = "push"
RESOURCE_SALES_ORDER = "sales_order"


class ConnectorError(Exception):
    """فشل في الاتصال أو في استجابة الخادم — يُعرض ولا يُبتلع."""


class PushResult:
    """
    نتيجة الدفع: نجح أم لا، والمرجع في النظام البعيد.

    `remote_id` **يُعاد دائماً عند النجاح**: بلا معرّف لا يستطيع أحد أن يفتح
    ما أُنشئ ولا أن يتحقّق منه، فيصير الدفع فعلاً بلا أثر يُراجَع.
    """

    def __init__(self, ok: bool, remote_id: str = "", message: str = ""):
        self.ok = bool(ok)
        self.remote_id = str(remote_id or "")
        self.message = str(message or "")


class Connector:
    """
    واجهة الموصّل: سحبٌ لكل وارث، ودفعٌ لمن يعلنه.

    الوارث يملأ `name` و `label` و `configured` و `test_connection` و `_fetch`،
    ويضيف `supports_push = True` و `_push_order` إن كان يكتب.
    """

    name = ""
    label = ""

    # الافتراض **لا يدفع**: موصّل جديد لا يفتح قناة كتابة إلى نظام العميل
    # لمجرّد أنه ورث الصنف.
    supports_push = False

    def __init__(self, config: Optional[dict] = None):
        self.config = dict(config or {})

    # ── ما يُعلَن قبل الخروج ──────────────────────────────────────────────────
    def endpoint(self) -> str:
        """المضيف الذي ستغادر إليه البيانات — يُعرض للمستخدم حرفياً."""
        return str(self.config.get("url", "") or "").strip()

    def egress_notice(self, resource: str, direction: str = DIRECTION_PULL) -> dict:
        """
        وصف ما يغادر الجهاز في هذه العملية.

        يُعرض **قبل كل عملية** لا في إعدادات تُقرأ مرة وتُنسى: القناة تُفتح لكل
        منافسة على حدة، والمستخدم يرى وجهة بياناته وقت اتّخاذ القرار.

        و`writes` تميّز الدفع: السحب يقرأ من نظام العميل، والدفع **يُنشئ فيه
        صفّاً** — والفرق يجب أن يظهر للمستخدم لا أن يُخمَّن من اسم الزرّ.
        """
        return {
            "endpoint": self.endpoint(),
            "resource": resource,
            "personal": resource in PERSONAL_RESOURCES,
            "direction": direction,
            "writes": direction == DIRECTION_PUSH,
        }

    # ── العقد ─────────────────────────────────────────────────────────────────
    def configured(self) -> bool:
        raise NotImplementedError

    def test_connection(self) -> tuple:
        """`(نجح, رسالة)` — تُجرَّب قبل أول سحب فلا يُكتشف الخطأ وسط العمل."""
        raise NotImplementedError

    def _fetch(self, resource: str, limit: int) -> list:
        raise NotImplementedError

    def _push_order(self, order: dict) -> "PushResult":
        raise NotImplementedError

    def push_order(self, order: dict) -> "PushResult":
        """
        يكتب أمر بيع **مسودّة** في النظام البعيد.

        الحمولة تُبنى في `utils/orders.py` ببواباتها؛ وهنا تُفحص الشروط التي
        لا يُوثَق فيها بالمستدعي:

        · موصّل لا يعلن الدفع لا يدفع — ولو استُدعي مباشرةً.
        · حمولة بلا بنود لا تُرسل: أمرٌ فارغ في دفاتر العميل ضجيج يُنظَّف يدوياً.
        · **حمولة تحمل سعراً تُرفض.** التسعير عمل الفريق المالي في نظامه،
          ورقمٌ يعبر من هنا يصير رقماً معتمَداً لم يعتمده أحد.
        """
        if not self.supports_push:
            raise ConnectorError("هذا الموصّل لا يدفع")
        if not self.configured():
            raise ConnectorError("الموصّل غير مُعدّ")
        if not (order or {}).get("lines"):
            raise ConnectorError("أمر بلا بنود لا يُرسل")
        if (order or {}).get("priced"):
            raise ConnectorError("لا يُرسل سعر — التسعير في النظام المحاسبي")
        return self._push_order(order)

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
