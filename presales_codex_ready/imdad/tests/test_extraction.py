"""اختبارات تحويل مخرجات الاستخراج المُهيكل إلى جداول قابلة للتحرير."""
import pytest


@pytest.fixture()
def tables():
    from views import tables as mod
    return mod


def test_compliance_rows_built_from_items(tables):
    items = [
        {"requirement": "شهادة ISO 27001", "category": "تأهيل", "mandatory": True,
         "certificate": "ISO 27001", "source_ref": "بند 4-2"},
        {"requirement": "دعم 24/7", "category": "فني", "mandatory": False},
    ]
    df = tables._compliance_to_df(items)
    assert len(df) == 2
    assert df.iloc[0]["الشهادة المطلوبة"] == "ISO 27001"
    assert "شرط استبعاد" in df.iloc[0]["التبرير / الملاحظة"]
    assert "بند 4-2" in df.iloc[0]["التبرير / الملاحظة"]
    assert "شرط استبعاد" not in df.iloc[1]["التبرير / الملاحظة"]


def test_compliance_status_is_never_assumed(tables):
    """
    حالة الالتزام قرار بشري. لو بدأ النموذج بتعبئتها "نعم" لخرج جدول امتثال
    يدّعي التزاماً غير محقّق — وهذا أخطر من تركه فارغاً.
    """
    items = [{"requirement": f"متطلب {i}", "category": "فني", "mandatory": True}
             for i in range(5)]
    df = tables._compliance_to_df(items)
    assert set(df["الالتزام"]) == {"بانتظار التحقق"}


def test_compliance_skips_blank_requirements(tables):
    items = [
        {"requirement": "   ", "category": "فني", "mandatory": False},
        {"requirement": "متطلب صحيح", "category": "فني", "mandatory": False},
    ]
    assert len(tables._compliance_to_df(items)) == 1


def test_compliance_empty_falls_back_to_default_shape(tables):
    df = tables._compliance_to_df([])
    assert list(df.columns) == [
        "المتطلب التقني", "الالتزام", "التبرير / الملاحظة", "الشهادة المطلوبة"
    ]


def test_boq_normalizes_quantity_and_unit(tables):
    items = [
        {"item": "ترخيص", "quantity": 50, "unit": "ترخيص"},
        {"item": "دعم", "quantity": "12", "unit": "شهر"},
        {"item": "غريب", "quantity": None, "unit": "كيلو"},
        {"item": "سيئ", "quantity": "abc", "unit": "شهر"},
    ]
    df = tables._boq_to_df(items)
    assert len(df) == 4
    assert df.iloc[1]["الكمية"] == 12          # نص رقمي يُحوَّل
    assert df.iloc[2]["الكمية"] == 1           # كمية مفقودة -> 1
    assert df.iloc[2]["الوحدة"] == "أخرى"      # وحدة غير معروفة
    assert df.iloc[3]["الكمية"] == 1           # قيمة غير رقمية لا تُسقط الصف


def test_boq_skips_unnamed_items(tables):
    assert len(tables._boq_to_df([{"item": "", "quantity": 3, "unit": "شهر"}])) == 1
    # صف بلا اسم يُتجاهل فيعود الجدول للشكل الافتراضي (صف فارغ واحد)


def test_boq_units_within_allowed_set(tables):
    items = [{"item": f"بند {i}", "quantity": 1, "unit": u}
             for i, u in enumerate(["شهر", "سنة", "قطعة", "مجهول"])]
    df = tables._boq_to_df(items)
    assert set(df["الوحدة"]) <= set(tables.BOQ_UNITS)
