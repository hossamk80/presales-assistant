"""
اختبارات المرحلة 7 — مستندات المظروف والاستبعاد الشكلي.
"""
import datetime

import pandas as pd
import pytest


@pytest.fixture()
def sub():
    from utils import submission
    return submission


def _df(rows):
    from utils.state import DEFAULT_SUBMISSION_DF, SUBMISSION_COLUMNS
    base = {c: "" for c in SUBMISSION_COLUMNS}
    base.update({"إلزامي": False, "مرفق في المظروف": False,
                 "لدينا": "بانتظار التحقق"})
    return pd.DataFrame([{**base, **r} for r in rows]) if rows \
        else DEFAULT_SUBMISSION_DF.copy()


# ─── قراءة التواريخ ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("text,expected", [
    ("2026-09-01", datetime.date(2026, 9, 1)),
    ("2026/09/01", datetime.date(2026, 9, 1)),
    ("01-09-2026", datetime.date(2026, 9, 1)),
    ("01/09/2026", datetime.date(2026, 9, 1)),
])
def test_common_date_formats_are_read(sub, text, expected):
    assert sub.parse_date(text) == expected


@pytest.mark.parametrize("text", ["", None, "قريباً", "غير محدد", "13/13/2026"])
def test_unreadable_date_is_left_unjudged(sub, text):
    """تاريخ لا يُقرأ لا يُفترض صالحاً ولا منتهياً."""
    assert sub.parse_date(text) is None


def test_deadline_is_found_inside_a_sentence(sub):
    """السياق الموحّد قد يُخرج الموعد داخل جملة لا كتاريخ مجرّد."""
    ctx = {"submission_deadline": "آخر موعد لتقديم العروض 2026-09-01 الساعة 12 ظهراً"}
    assert sub.deadline_date(ctx) == datetime.date(2026, 9, 1)


def test_missing_deadline_is_none(sub):
    assert sub.deadline_date({}) is None
    assert sub.deadline_date(None) is None


# ─── جاهزية المظروف ────────────────────────────────────────────────────────────


def test_mandatory_document_is_ready_only_when_held_and_attached(sub):
    df = _df([
        {"المستند": "السجل التجاري", "إلزامي": True, "لدينا": "نعم",
         "مرفق في المظروف": True},
        {"المستند": "شهادة الزكاة", "إلزامي": True, "لدينا": "نعم",
         "مرفق في المظروف": False},
    ])
    s = sub.submission_summary(df)
    assert s["ready"] == 1
    assert s["missing"] == ["شهادة الزكاة"]


def test_pending_verification_is_not_ready(sub):
    """"بانتظار التحقق" ليس حيازة — لم نتأكد لا تساوي موجود."""
    df = _df([{"المستند": "التأمينات", "إلزامي": True,
               "لدينا": "بانتظار التحقق", "مرفق في المظروف": True}])
    assert sub.submission_summary(df)["missing"] == ["التأمينات"]


def test_not_applicable_document_is_not_counted_missing(sub):
    df = _df([{"المستند": "تصنيف المقاولين", "إلزامي": True, "لدينا": "لا ينطبق"}])
    assert sub.submission_summary(df)["missing"] == []


def test_optional_document_never_blocks(sub):
    df = _df([{"المستند": "شهادة اختيارية", "إلزامي": False, "لدينا": "لا"}])
    s = sub.submission_summary(df)
    assert s["missing"] == []
    assert s["mandatory"] == 0
    assert s["total"] == 1


def test_certificate_expiring_before_the_deadline_is_flagged(sub):
    """
    شهادة بين يديك اليوم لكنها تنتهي قبل الفتح = مستند غير مقبول يوم التقييم.
    """
    df = _df([{"المستند": "شهادة السعودة", "إلزامي": True, "لدينا": "نعم",
               "مرفق في المظروف": True, "تاريخ الانتهاء": "2026-08-15"}])
    s = sub.submission_summary(df, {"submission_deadline": "2026-09-01"})
    assert s["expiring"] and "شهادة السعودة" in s["expiring"][0]
    assert s["ready"] == 1          # حائزها فعلاً — التنبيه على الانتهاء لا الغياب


def test_certificate_valid_past_the_deadline_is_silent(sub):
    df = _df([{"المستند": "شهادة السعودة", "تاريخ الانتهاء": "2027-01-01"}])
    assert sub.submission_summary(df, {"submission_deadline": "2026-09-01"})["expiring"] == []


def test_no_expiry_check_without_a_readable_deadline(sub):
    df = _df([{"المستند": "شهادة", "تاريخ الانتهاء": "2020-01-01"}])
    assert sub.submission_summary(df, {"submission_deadline": "غير محدد"})["expiring"] == []


def test_blank_rows_are_ignored(sub):
    assert sub.submission_summary(_df([{"المستند": ""}]))["total"] == 0


def test_summary_is_safe_on_missing_table(sub):
    assert sub.submission_summary(None)["total"] == 0
    assert sub.submission_summary(pd.DataFrame())["missing"] == []


def test_multiword_columns_are_read(sub):
    """نفس مصيدة itertuples: "مرفق في المظروف" اسم بمسافات."""
    df = _df([{"المستند": "السجل", "إلزامي": True, "لدينا": "نعم",
               "مرفق في المظروف": True}])
    assert sub.submission_summary(df)["ready"] == 1


# ─── الاستخراج ─────────────────────────────────────────────────────────────────


def test_extraction_never_assumes_possession(sub):
    """النموذج يقرأ الكراسة لا خزانة مستنداتك."""
    df = sub.documents_to_df([
        {"document": "الضمان الابتدائي", "mandatory": True,
         "clause_reference": "5-2", "notes": "1% من قيمة العرض"},
    ])
    assert df["لدينا"].iloc[0] == "بانتظار التحقق"
    assert bool(df["مرفق في المظروف"].iloc[0]) is False
    assert df["إلزامي"].iloc[0]
    assert df["ملاحظات"].iloc[0] == "1% من قيمة العرض"


def test_extraction_skips_unnamed_documents(sub):
    from utils.state import DEFAULT_SUBMISSION_DF

    out = sub.documents_to_df([{"document": "", "mandatory": True}])
    assert list(out.columns) == list(DEFAULT_SUBMISSION_DF.columns)
    assert str(out["المستند"].iloc[0]) == ""


def test_submission_prompt_reads_this_tender_not_a_stored_list():
    from utils.ai_engine import EXTRACT_PROMPTS

    prompt = EXTRACT_PROMPTS["submission_docs"]
    assert "هذه الكراسة" in prompt
    assert "لا تنسخ قائمة عامة محفوظة" in prompt
    assert "لا تحكم على ما إذا كانت الشركة تملك المستند" in prompt


def test_submission_prompt_lists_the_commonly_forgotten_documents():
    from utils.ai_engine import EXTRACT_PROMPTS

    prompt = EXTRACT_PROMPTS["submission_docs"]
    for doc in ("السجل التجاري", "الزكاة", "التأمينات الاجتماعية",
                "السعودة", "الضمان الابتدائي"):
        assert doc in prompt


def test_mandatory_means_exclusion_not_merely_required():
    from utils.ai_engine import SUBMISSION_SCHEMA

    desc = SUBMISSION_SCHEMA["properties"]["documents"]["items"]["properties"]["mandatory"]
    assert "استبعاد" in desc["description"]


# ─── الحفظ مع المنافسة ─────────────────────────────────────────────────────────


def test_documents_persist_with_the_tender(fake_streamlit):
    from utils.state import STATE_SCHEMA, get_state_snapshot

    assert "df_submission" in STATE_SCHEMA
    fake_streamlit.session_state["df_submission"] = _df([
        {"المستند": "السجل التجاري", "إلزامي": True},
    ])
    snap = get_state_snapshot()
    assert any(r.get("المستند") == "السجل التجاري" for r in snap["df_submission"])


def test_tender_saved_before_this_feature_still_loads(fake_streamlit):
    from utils.state import SUBMISSION_COLUMNS, migrate_submission_df

    old = pd.DataFrame({"المستند": ["السجل التجاري"]})
    out = migrate_submission_df(old)
    assert list(out.columns) == SUBMISSION_COLUMNS
    assert out["لدينا"].iloc[0] == "بانتظار التحقق"
