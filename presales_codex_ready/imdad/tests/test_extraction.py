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

# ملاحظة: اختبارات جدول الكميات انتقلت إلى tests/test_phase1.py بعد توسيع
# المخطط إلى تسعة حقول — الشكل المختصر السابق (item/notes) لم يعد مستخدماً.
