"""
utils/connectors/odoo.py — موصّل أوديو (سحب فقط).

يستعمل واجهة أوديو الخارجية عبر XML-RPC من المكتبة القياسية — **بلا تبعية
جديدة**: حزمة إضافية لموصّل اختياري تُثقّل كل تركيب ولو لم يُفعَّل.

يقرأ ثلاثة موارد ويطبّعها إلى مخططات سجلات الأدلة (المرحلة 12) فتدخل النظام
كصفوف يُطابَق بها لا كنصّ حرّ.
"""
import xmlrpc.client
from typing import Optional

from utils.connectors.base import (
    RESOURCE_CUSTOMERS,
    RESOURCE_EMPLOYEES,
    RESOURCE_PRODUCTS,
    Connector,
    ConnectorError,
)

# مهلة الاتصال بالثواني — خادم لا يردّ يجب أن يُبلّغ لا أن يُعلّق الواجهة
TIMEOUT = 20


class _Transport(xmlrpc.client.SafeTransport):
    """نقل بمهلة: `ServerProxy` لا يقبل مهلةً مباشرةً."""

    def __init__(self, timeout=TIMEOUT, use_https=True):
        super().__init__()
        self.timeout = timeout
        self._use_https = use_https

    def make_connection(self, host):
        connection = super().make_connection(host)
        connection.timeout = self.timeout
        return connection


class _HttpTransport(xmlrpc.client.Transport):
    def __init__(self, timeout=TIMEOUT):
        super().__init__()
        self.timeout = timeout

    def make_connection(self, host):
        connection = super().make_connection(host)
        connection.timeout = self.timeout
        return connection


def _proxy(url: str, path: str):
    endpoint = f"{url.rstrip('/')}/xmlrpc/2/{path}"
    transport = _Transport() if endpoint.startswith("https") else _HttpTransport()
    return xmlrpc.client.ServerProxy(endpoint, transport=transport, allow_none=True)


class OdooConnector(Connector):
    """
    أوديو عبر XML-RPC. **سحب فقط** — لا دالّة دفع هنا (انظر `base.py`).

    `config`: `url` · `db` · `username` · `api_key`.
    """

    name = "odoo"
    label = "Odoo"

    # المورد ← (نموذج أوديو، الحقول المطلوبة، مرشّح)
    _MODELS = {
        RESOURCE_CUSTOMERS: (
            "res.partner",
            ["name", "email", "phone", "industry_id", "country_id"],
            [("is_company", "=", True), ("customer_rank", ">", 0)],
        ),
        RESOURCE_PRODUCTS: (
            "product.template",
            ["name", "default_code", "categ_id", "description_sale"],
            [("sale_ok", "=", True)],
        ),
        RESOURCE_EMPLOYEES: (
            "hr.employee",
            ["name", "job_title", "work_email", "department_id"],
            [],
        ),
    }

    def configured(self) -> bool:
        return all(str(self.config.get(k, "") or "").strip()
                   for k in ("url", "db", "username", "api_key"))

    def _login(self) -> int:
        common = _proxy(self.config["url"], "common")
        try:
            uid = common.authenticate(
                self.config["db"], self.config["username"],
                self.config["api_key"], {},
            )
        except Exception as e:                       # شبكة · شهادة · بروتوكول
            raise ConnectorError(f"تعذّر الاتصال: {e}") from e
        if not uid:
            # بيانات الدخول خاطئة — تُقال كما هي ولا تُخلط بفشل الشبكة
            raise ConnectorError("رُفض الدخول: تحقّق من المستخدم ومفتاح الواجهة")
        return int(uid)

    def test_connection(self) -> tuple:
        if not self.configured():
            return False, "الموصّل غير مُعدّ"
        try:
            uid = self._login()
        except ConnectorError as e:
            return False, str(e)
        return True, f"تمّ الاتصال (uid={uid})"

    def _read(self, resource: str, limit: int) -> list:
        model, fields, domain = self._MODELS[resource]
        uid = self._login()
        models = _proxy(self.config["url"], "object")
        try:
            return models.execute_kw(
                self.config["db"], uid, self.config["api_key"],
                model, "search_read", [domain],
                {"fields": fields, "limit": limit},
            ) or []
        except Exception as e:
            raise ConnectorError(f"تعذّرت قراءة {model}: {e}") from e

    def _fetch(self, resource: str, limit: int) -> list:
        return [_normalise(resource, row) for row in self._read(resource, limit)]


def _name_of(value) -> str:
    """
    أوديو يعيد الحقول المرتبطة `[id, name]` — نأخذ الاسم.

    وحقل غير مضبوط يعود `False` لا `None`، فالتحويل النصّي المباشر يكتب
    «False» في خانة القطاع.
    """
    if isinstance(value, (list, tuple)) and len(value) > 1:
        return str(value[1])
    if value is False or value is None:
        return ""
    return str(value)


def _normalise(resource: str, row: dict) -> dict:
    """
    صفّ أوديو ← مخطط سجلات الأدلة (المرحلة 12).

    التطبيع هنا لا في الواجهة: الصفّ يدخل النظام بالشكل الذي تُطابَق به
    المتطلبات، فيصير دليلاً لا نصّاً حرّاً.
    """
    if resource == RESOURCE_CUSTOMERS:
        return {
            "name": _name_of(row.get("name")),
            "sector": _name_of(row.get("industry_id")),
            "contacts": " · ".join(filter(None, [
                _name_of(row.get("email")), _name_of(row.get("phone")),
            ])),
            "evaluation_pattern": "",
            "recurring_requirements": "",
        }
    if resource == RESOURCE_PRODUCTS:
        return {
            "vendor": _name_of(row.get("categ_id")),
            "product_line": _name_of(row.get("name")),
            "partnership": "",
            "authorization_letter": "",
            "letter_expiry": "",
            "local_support": "",
            "eol_eos": "",
            "alternative": _name_of(row.get("default_code")),
        }
    # الموظفون: بيانات أشخاص. `legal_basis` يُملأ بـ«عقد» — الموظف تحت عقد،
    # وهو الأساس الوحيد الذي يصحّ افتراضه؛ ما عداه قرار بشري (13-10).
    return {
        "name": _name_of(row.get("name")),
        "role": _name_of(row.get("job_title")) or _name_of(row.get("department_id")),
        "years": "",
        "certifications": "",
        "cert_expiry": "",
        "languages": "",
        "availability": "",
        "cv_document": "",
        "legal_basis": "contract",
    }


def build(config: Optional[dict] = None) -> OdooConnector:
    return OdooConnector(config)
